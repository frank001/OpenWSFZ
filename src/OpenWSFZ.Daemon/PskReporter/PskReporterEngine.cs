using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Daemon.PskReporter;

/// <summary>The receiver identity the upload runs under, read fresh each time (the operator can change it at run time).</summary>
/// <param name="Callsign"><c>tx.callsign</c>.</param>
/// <param name="Locator"><c>tx.grid</c>.</param>
/// <param name="Antenna"><c>pskReporter.antennaInformation</c>.</param>
/// <param name="Software">The <c>decodingSoftware</c> string, <c>OpenWSFZ &lt;VERSION&gt;</c>.</param>
internal sealed record PskIdentity(string Callsign, string Locator, string Antenna, string Software)
{
    /// <summary>
    /// Nothing is uploaded under a placeholder identity: an empty or Q-prefix call (the ITU-unallocated range, default <c>Q1OFZ</c>) or
    /// an empty locator.
    /// </summary>
    public bool IsPlaceholder
        => string.IsNullOrWhiteSpace(Callsign)
           || Callsign.TrimStart().StartsWith('Q') || Callsign.TrimStart().StartsWith('q')
           || string.IsNullOrWhiteSpace(Locator);
}

/// <summary>A datagram the engine has built and handed out; the service sends it and reports back through <c>Complete</c>.</summary>
/// <param name="Bytes">The wire bytes.</param>
/// <param name="Spots">The sender records in it, in queue order.</param>
/// <param name="IncludesTemplates">Whether the template sets are in it.</param>
/// <param name="FromWindow">Whether this datagram is the 5-minute window's (as opposed to a full one sent at once).</param>
internal sealed record PskDatagram(byte[] Bytes, IReadOnlyList<PskSpot> Spots, bool IncludesTemplates, bool FromWindow);

/// <summary>
/// The decision logic of the PSK Reporter upload (issue #262), with no sockets, timers or threads of its own: the clock is an argument
/// and the service drives it, so every rule is testable under a fake clock. Thread-safe (one lock).
/// <para>
/// It decides which decodes become records (identity guard, dial frequency, region exclusion, strict sender, own call, dedup),
/// queues them in a bounded queue, and builds at most one datagram per 5-minute window (a full one goes at once). It never logs a
/// callsign or message text, only counts.
/// </para>
/// </summary>
internal sealed class PskReporterEngine
{
    /// <summary>Minimum time between two records of one call, on any band.</summary>
    public static readonly TimeSpan PerCallInterval = TimeSpan.FromMinutes(5);

    /// <summary>Minimum time between two records of one (call, band).</summary>
    public static readonly TimeSpan PerCallBandInterval = TimeSpan.FromMinutes(60);

    /// <summary>The send window: at most one datagram per window unless one is full.</summary>
    public static readonly TimeSpan SendWindow = TimeSpan.FromMinutes(5);

    /// <summary>The template sets go in this many of the first datagrams of a socket's life ...</summary>
    public const int InitialTemplateDatagrams = 3;

    /// <summary>... and then at least this often.</summary>
    public static readonly TimeSpan TemplateInterval = TimeSpan.FromHours(1);

    /// <summary>Upper bound on records held across failures; the oldest are dropped and counted beyond it.</summary>
    public const int MaxPendingRecords = 1000;

    /// <summary>When the dedup tables grow past this many keys, entries older than the longest interval are pruned.</summary>
    private const int DedupPruneThreshold = 5000;

    private readonly object _gate = new();
    private readonly Func<PskIdentity> _identity;
    private readonly ILogger _logger;
    private readonly uint _sessionId;

    private readonly List<PskSpot> _pending = [];
    private readonly Dictionary<string, DateTime> _lastAnyBand = new(StringComparer.OrdinalIgnoreCase);
    private readonly Dictionary<(string Call, string Band), DateTime> _lastCallBand = new();

    private bool     _active;
    private DateTime _nextWindowUtc;
    private uint     _sequence;
    private int      _datagramsSent;
    private DateTime _lastTemplatesUtc = DateTime.MinValue;
    private bool     _failureWarnedThisWindow;
    private DateTime _holdFullUntilUtc = DateTime.MinValue;   // after a failed send, full datagrams wait for the next window too

    // Counts since the last datagram (logged with it) and for the placeholder-identity warning of the current window.
    private int _exRegion, _exHashed, _exUnparseable, _exOwn, _exNoDial, _exDedup, _exDropped, _identityRefused;

    /// <param name="identity">Reads the receiver identity (called on every ingest and every build).</param>
    /// <param name="logger">Receives counts only, never callsigns.</param>
    /// <param name="sessionId">The 4-byte session id, constant for the process (random in production).</param>
    public PskReporterEngine(Func<PskIdentity> identity, ILogger logger, uint sessionId)
    {
        _identity  = identity ?? throw new ArgumentNullException(nameof(identity));
        _logger    = logger   ?? throw new ArgumentNullException(nameof(logger));
        _sessionId = sessionId;
    }

    /// <summary>The next sender record's sequence number (counts sender records sent, from 0 for the process).</summary>
    public uint Sequence { get { lock (_gate) return _sequence; } }

    /// <summary>The records queued and not yet sent.</summary>
    public int PendingCount { get { lock (_gate) return _pending.Count; } }

    /// <summary>
    /// Starts an enabled period (a new socket): the first window falls <paramref name="firstSendOffset"/> (0 to 60 s, random, so the
    /// timer is not aligned to the wall clock) after <paramref name="nowUtc"/>, and the template cadence restarts for the new source port.
    /// </summary>
    public void Activate(DateTime nowUtc, TimeSpan firstSendOffset)
    {
        lock (_gate)
        {
            ResetUnsafe();
            _active         = true;
            _nextWindowUtc  = nowUtc + firstSendOffset;
            _datagramsSent  = 0;
            _lastTemplatesUtc = DateTime.MinValue;
        }
    }

    /// <summary>Ends an enabled period: nothing stays queued, nothing is remembered.</summary>
    public void Deactivate()
    {
        lock (_gate)
        {
            _active = false;
            ResetUnsafe();
        }
    }

    /// <summary>
    /// Turns the results of one batch into queued records, applying every exclusion in order and counting each by reason.
    /// </summary>
    public void Ingest(DecodeBatch batch, DateTime nowUtc)
    {
        lock (_gate)
        {
            if (!_active || batch.Results.Count == 0) return;

            var id = _identity();
            if (id.IsPlaceholder)
            {
                _identityRefused += batch.Results.Count;
                return;
            }
            // No dial frequency, or one outside the band table (N-3, Architect spec 12): nothing is reported, counted as no-dial-frequency.
            if (batch.DialFrequencyMHz is not { } dialMHz || dialMHz <= 0 || BandTable.DeriveBand(dialMHz) is not { } band)
            {
                _exNoDial += batch.Results.Count;
                return;
            }

            long dialHz = (long)Math.Round(dialMHz * 1_000_000d);
            uint flow   = ToUnixSeconds(batch.CycleStart.UtcDateTime);

            foreach (var r in batch.Results)
            {
                // Same absolute rule as external-reporting (never weakened): an unknown-region or synthetic decode is never encoded.
                if (r.Region is null || r.Region.Synthetic) { _exRegion++; continue; }

                if (!PskSenderExtractor.TryExtract(r.Message, id.Callsign, out var sender, out var why))
                {
                    switch (why)
                    {
                        case PskSenderRejection.Hashed:  _exHashed++;      break;
                        case PskSenderRejection.OwnCall: _exOwn++;         break;
                        default:                         _exUnparseable++; break;
                    }
                    continue;
                }

                if (IsDuplicate(sender!.Callsign, band, nowUtc)) { _exDedup++; continue; }
                _lastAnyBand[sender.Callsign]             = nowUtc;
                _lastCallBand[(sender.Callsign, band)]    = nowUtc;

                long freq = Math.Clamp(dialHz + r.FreqHz, 0L, uint.MaxValue);
                _pending.Add(new PskSpot(sender.Callsign, sender.Locator, (uint)freq, r.Snr, flow));
            }

            TrimPendingUnsafe();
            PruneDedupUnsafe(nowUtc);
        }
    }

    /// <summary>
    /// Builds the next datagram if one is due: the window's (every <see cref="SendWindow"/>, never earlier) or a full one (the queue
    /// holds more than one datagram's worth). Records leave the queue here; <see cref="Complete"/> puts them back if the send failed.
    /// </summary>
    public PskDatagram? Prepare(DateTime nowUtc)
    {
        lock (_gate)
        {
            if (!_active) return null;

            bool due = nowUtc >= _nextWindowUtc;
            if (due)
            {
                if (_identityRefused > 0)
                {
                    _logger.LogWarning(
                        "psk-reporter: nothing uploaded in this window: the receiver identity is a placeholder (empty or Q-prefix tx.callsign, or empty tx.grid); {Refused} decode(s) refused.",
                        _identityRefused);
                    _identityRefused = 0;
                }
                _failureWarnedThisWindow = false;
            }

            var id = _identity();
            if (id.IsPlaceholder || _pending.Count == 0)
            {
                if (due) _nextWindowUtc = nowUtc + SendWindow;
                return null;
            }

            bool templates = _datagramsSent < InitialTemplateDatagrams || nowUtc - _lastTemplatesUtc >= TemplateInterval;
            var receiver   = new PskReceiver(id.Callsign, id.Locator, id.Software, id.Antenna);
            int fit        = Math.Max(1, PskReporterEncoder.CountThatFit(receiver, _pending, templates));
            bool full      = fit < _pending.Count;
            if (!due && (!full || nowUtc < _holdFullUntilUtc)) return null;

            var spots = _pending.Take(fit).ToList();
            _pending.RemoveRange(0, fit);
            if (due) _nextWindowUtc = nowUtc + SendWindow;

            var bytes = PskReporterEncoder.Encode(receiver, spots, ToUnixSeconds(nowUtc), _sequence, _sessionId, templates);
            return new PskDatagram(bytes, spots, templates, due);
        }
    }

    /// <summary>
    /// Reports the outcome of a send. A sent datagram advances the sequence by its sender records (the receiver record is not counted),
    /// the template cadence, and logs its one Information line; an unsent one advances nothing, its records go back to the front of the
    /// queue (bounded) and one Warning per window is logged.
    /// </summary>
    public void Complete(PskDatagram datagram, bool sent, DateTime nowUtc, Exception? error = null)
    {
        lock (_gate)
        {
            if (!_active) return;

            if (sent)
            {
                _sequence += (uint)datagram.Spots.Count;
                _datagramsSent++;
                if (datagram.IncludesTemplates) _lastTemplatesUtc = nowUtc;

                _logger.LogInformation(
                    "psk-reporter: datagram sent at {UtcTime:O}: {Records} record(s); excluded since the last datagram: region={Region} hashed={Hashed} unparseable={Unparseable} own-call={Own} no-dial-frequency={NoDial} dedup={Dedup} queue-dropped={Dropped}; sequence after={Sequence}.",
                    nowUtc, datagram.Spots.Count, _exRegion, _exHashed, _exUnparseable, _exOwn, _exNoDial, _exDedup, _exDropped, _sequence);
                _exRegion = _exHashed = _exUnparseable = _exOwn = _exNoDial = _exDedup = _exDropped = 0;
                return;
            }

            _pending.InsertRange(0, datagram.Spots);
            TrimPendingUnsafe();
            _holdFullUntilUtc = _nextWindowUtc;   // retry at the next window, not every tick
            if (!_failureWarnedThisWindow)
            {
                _failureWarnedThisWindow = true;
                _logger.LogWarning(
                    "psk-reporter: could not send a datagram ({Error}); {Queued} record(s) kept for the next window.",
                    error?.GetType().Name ?? "unknown", _pending.Count);
            }
        }
    }

    // ── internals (call under the lock) ─────────────────────────────────────────────────────────────────────────────

    private bool IsDuplicate(string call, string band, DateTime nowUtc)
        => (_lastAnyBand.TryGetValue(call, out var any) && nowUtc - any < PerCallInterval)
           || (_lastCallBand.TryGetValue((call, band), out var cb) && nowUtc - cb < PerCallBandInterval);

    private void TrimPendingUnsafe()
    {
        int excess = _pending.Count - MaxPendingRecords;
        if (excess <= 0) return;
        _pending.RemoveRange(0, excess);   // the oldest go first
        _exDropped += excess;
    }

    private void PruneDedupUnsafe(DateTime nowUtc)
    {
        if (_lastCallBand.Count + _lastAnyBand.Count <= DedupPruneThreshold) return;
        foreach (var k in _lastCallBand.Where(kv => nowUtc - kv.Value >= PerCallBandInterval).Select(kv => kv.Key).ToList()) _lastCallBand.Remove(k);
        foreach (var k in _lastAnyBand.Where(kv => nowUtc - kv.Value >= PerCallBandInterval).Select(kv => kv.Key).ToList()) _lastAnyBand.Remove(k);
    }

    private void ResetUnsafe()
    {
        _pending.Clear();
        _lastAnyBand.Clear();
        _lastCallBand.Clear();
        _exRegion = _exHashed = _exUnparseable = _exOwn = _exNoDial = _exDedup = _exDropped = _identityRefused = 0;
        _failureWarnedThisWindow = false;
        _holdFullUntilUtc = DateTime.MinValue;
    }

    private static uint ToUnixSeconds(DateTime utc)
        => (uint)Math.Clamp(new DateTimeOffset(DateTime.SpecifyKind(utc, DateTimeKind.Utc)).ToUnixTimeSeconds(), 0L, uint.MaxValue);
}
