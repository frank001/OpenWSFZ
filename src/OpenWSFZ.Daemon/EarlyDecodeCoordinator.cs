using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Web;

namespace OpenWSFZ.Daemon;

/// <summary>
/// decode-early-batch-panel (design.md D2, D5, D8): the state shared by the early decode service and the decode pump.
///
/// <list type="bullet">
///   <item><b>The decode gate</b> (<see cref="Gate"/>, a <c>SemaphoreSlim(1,1)</c>): held by the early decode while it
///   runs and by the ordinary decode while it runs, so the two are mutually exclusive. That exclusivity is what makes the
///   native save / decode / restore bracket of the early decode safe (no other decode can run between the save and the
///   restore). The early service uses <c>Wait(0)</c> and SKIPS when busy; the pump waits, and the wait is measured.</item>
///   <item><b>The early batch of the current cycle</b>, kept so that batch 1 can be matched against it and the panel told,
///   in one frame, what became of each early row.</item>
///   <item><b>The R7 log line</b>, one per cycle, aggregates only (HK-037): written when the pump has taken the gate for
///   the final decode, because <c>finalWaitMs</c> is only known then.</item>
/// </list>
/// Nothing here reaches ALL.TXT, UDP, the QSO channels or the archive (R3): the only outputs are the two panel frames.
/// </summary>
internal sealed class EarlyDecodeCoordinator
{
    private sealed class CycleSlot
    {
        public DateTime                CycleStart;
        public IReadOnlyList<EarlyRow> Rows        = [];
        public int                     Count;
        public double                  ElapsedMs;
        public string?                 SkipReason;     // null = the early decode ran
        public bool                    Logged;
    }

    private readonly ILogger _logger;
    private readonly Func<IReadOnlyList<DecodeResult>, IReadOnlyList<EarlyResolution>?, Task> _publishWithResolves;
    private readonly object   _lock = new();
    private CycleSlot?        _slot;
    private long              _nextEarlyId;

    /// <summary>Creates the coordinator.</summary>
    /// <param name="logger">The daemon logger (the R7 line).</param>
    /// <param name="publishWithResolves">Publishes batch 1 and the <c>resolves</c> list in ONE <c>decode</c> frame (<c>DecodeEventBus.Publish</c>).</param>
    internal EarlyDecodeCoordinator(
        ILogger logger,
        Func<IReadOnlyList<DecodeResult>, IReadOnlyList<EarlyResolution>?, Task> publishWithResolves)
    {
        _logger              = logger;
        _publishWithResolves = publishWithResolves;
    }

    /// <summary>The decode gate. See the class remarks.</summary>
    internal SemaphoreSlim Gate { get; } = new(1, 1);

    /// <summary>A new early-row id, unique for the daemon's lifetime.</summary>
    internal long NextEarlyId() => Interlocked.Increment(ref _nextEarlyId);

    /// <summary>
    /// Records that the early decode of <paramref name="cycleStart"/> ran and produced <paramref name="rows"/>. An older cycle
    /// whose final batch never arrived is resolved first (all <c>unconfirmed</c>), so no early row stays marked forever.
    /// </summary>
    internal void RecordEarly(DateTime cycleStart, IReadOnlyList<EarlyRow> rows, double elapsedMs)
    {
        IReadOnlyList<EarlyRow>? stale = null;
        lock (_lock)
        {
            if (_slot is { } old && old.CycleStart != cycleStart && old.Rows.Count > 0) stale = old.Rows;
            _slot = new CycleSlot { CycleStart = cycleStart, Rows = rows, Count = rows.Count, ElapsedMs = elapsedMs };
        }
        if (stale is not null) ResolveAllUnconfirmed(stale);
    }

    /// <summary>Records that the early decode of <paramref name="cycleStart"/> was skipped, and why (counted by the R7 line).</summary>
    internal void RecordSkip(DateTime cycleStart, string reason)
    {
        IReadOnlyList<EarlyRow>? stale = null;
        lock (_lock)
        {
            if (_slot is { } old && old.CycleStart != cycleStart && old.Rows.Count > 0) stale = old.Rows;
            _slot = new CycleSlot { CycleStart = cycleStart, SkipReason = reason };
        }
        if (stale is not null) ResolveAllUnconfirmed(stale);
    }

    /// <summary>
    /// The pump has taken the gate for the final decode of <paramref name="cycleStart"/> after waiting
    /// <paramref name="finalWaitMs"/>: writes the cycle's one R7 line, if an early window of this cycle was seen at all.
    /// A cycle with no line either had the feature OFF or lost its early window to a full channel.
    /// </summary>
    internal void NoteFinalDecodeStarted(DateTime cycleStart, double finalWaitMs)
    {
        CycleSlot? slot;
        lock (_lock)
        {
            slot = _slot;
            if (slot is null || slot.CycleStart != cycleStart || slot.Logged) return;
            slot.Logged = true;
        }
        _logger.LogInformation(
            "Early decode: cycle={Cycle:HH:mm:ss}, n={Count}, elapsedMs={ElapsedMs:F0}, skipped={Skipped}, skipReason={SkipReason}, finalWaitMs={FinalWaitMs:F0}.",
            cycleStart, slot.Count, slot.ElapsedMs, slot.SkipReason is null ? 0 : 1, slot.SkipReason ?? "none", finalWaitMs);
    }

    /// <summary>
    /// Publishes the cycle's batch 1 to the panel. With no early rows for this cycle this is exactly
    /// <paramref name="publishPlain"/> (the ordinary frame, byte-identical to before). With early rows, ONE frame carries
    /// batch 1 and the <c>resolves</c> list; an empty batch 1 still resolves the cycle.
    /// </summary>
    internal Task PublishBatch1Async(
        IReadOnlyList<DecodeResult> visibleResults, DateTime cycleStart,
        Func<IReadOnlyList<DecodeResult>, Task> publishPlain)
    {
        IReadOnlyList<EarlyRow>? rows = null;
        lock (_lock)
        {
            if (_slot is { } slot && slot.CycleStart == cycleStart && slot.Rows.Count > 0)
            {
                rows  = slot.Rows;
                _slot = new CycleSlot { CycleStart = cycleStart, Count = slot.Count, ElapsedMs = slot.ElapsedMs, Logged = true };
            }
        }
        if (rows is null) return publishPlain(visibleResults);
        return _publishWithResolves(visibleResults, EarlyDecodeMatcher.Match(rows, visibleResults));
    }

    /// <summary>
    /// The cycle's final decode will never publish (a discarded cycle, a decode error): resolves its early rows as
    /// <c>unconfirmed</c> so none stays marked <i>early</i> forever.
    /// </summary>
    internal void Abandon(DateTime cycleStart)
    {
        IReadOnlyList<EarlyRow>? rows = null;
        lock (_lock)
        {
            if (_slot is { } slot && slot.CycleStart == cycleStart && slot.Rows.Count > 0)
            {
                rows  = slot.Rows;
                _slot = new CycleSlot { CycleStart = cycleStart, Logged = true };
            }
        }
        if (rows is not null) ResolveAllUnconfirmed(rows);
    }

    private void ResolveAllUnconfirmed(IReadOnlyList<EarlyRow> rows)
        => _ = _publishWithResolves([], EarlyDecodeMatcher.Match(rows, []));
}
