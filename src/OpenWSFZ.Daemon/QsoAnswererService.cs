using System.Threading.Channels;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Ft8;
using OpenWSFZ.Web;

namespace OpenWSFZ.Daemon;

/// <summary>
/// Background service that drives the FT8 QSO answerer state machine (FR-050).
///
/// <para>
/// On each decode cycle the service reads a batch of <see cref="DecodeResult"/> items from
/// a shared <c>Channel</c> (fed by the main decode pump) and advances the state machine:
/// </para>
/// <list type="table">
///   <item><term>Idle</term><description>Scan for CQ; answer the first CQ found.</description></item>
///   <item><term>WaitReport</term><description>Await signal report from partner; retry or abort on silence.</description></item>
///   <item><term>WaitRr73</term><description>Await RR73/RRR; retry or abort on silence.</description></item>
/// </list>
///
/// <para>
/// TX operations are performed by calling <see cref="IPttController.LoadAudio"/> then
/// <see cref="IPttController.KeyDownAsync"/>; audio is synthesised from FT8 tones by
/// <see cref="Ft8AudioSynthesiser"/>.
/// </para>
///
/// <para>
/// A watchdog timer starts when the service leaves <c>Idle</c>.  If the watchdog fires
/// (configurable via <c>tx.watchdogMinutes</c>) before <c>QsoComplete</c> is reached,
/// the session is aborted.  The timer resets on every successful state transition.
/// </para>
///
/// <para>
/// Operator abort is available via <see cref="AbortAsync"/> (called from
/// <c>POST /api/v1/tx/abort</c>); it cancels the active TX CTS and signals
/// <see cref="IPttController.KeyUpAsync"/>.
/// </para>
/// </summary>
public sealed class QsoAnswererService : BackgroundService, IQsoAnswerer
{
    // ── Private state ─────────────────────────────────────────────────────────

    private readonly ChannelReader<IReadOnlyList<DecodeResult>> _decodeChannel;
    private readonly IConfigStore                               _configStore;
    private readonly IPttController                             _pttController;
    private readonly TxEventBus                                 _txEventBus;
    private readonly ILogger<QsoAnswererService>                _logger;
    private readonly Ft8AudioSynthesiser                        _synthesiser = new();
    private readonly AdifLogWriter                               _adifLog;

    // Volatile: readable from the HTTP handler thread without a lock.
    private volatile QsoState _state   = QsoState.Idle;
    private volatile string?  _partner = null;

    // Per-session TX state.
    private string   _lastTxMessage = string.Empty;
    private int      _lastTxFreqHz  = 0;
    private string   _rstRcvd       = "+00"; // signal report received from partner
    private int      _retryCount    = 0;
    private DateTime _qsoStartUtc   = DateTime.MinValue;

    // Cancellation for the active TX session; cancelled on watchdog expiry or operator abort.
    // Volatile reference so AbortAsync (HTTP thread) can safely read and cancel the current CTS.
    // Never Disposed to avoid ObjectDisposedException race in AbortAsync; let GC handle old instances.
    private volatile CancellationTokenSource _txCts = new();

    // ── Constructors ──────────────────────────────────────────────────────────

    /// <summary>Production constructor — all dependencies from DI.</summary>
    public QsoAnswererService(
        ChannelReader<IReadOnlyList<DecodeResult>> decodeChannel,
        IConfigStore                               configStore,
        IPttController                             pttController,
        TxEventBus                                 txEventBus,
        AdifLogWriter                              adifLog,
        ILogger<QsoAnswererService>                logger)
    {
        _decodeChannel = decodeChannel;
        _configStore   = configStore;
        _pttController = pttController;
        _txEventBus    = txEventBus;
        _adifLog       = adifLog;
        _logger        = logger;
    }

    // ── IQsoAnswerer ──────────────────────────────────────────────────────────

    /// <inheritdoc/>
    public QsoState State   => _state;

    /// <inheritdoc/>
    public string?  Partner => _partner;

    /// <inheritdoc/>
    public async Task AbortAsync(CancellationToken ct = default)
    {
        if (_state == QsoState.Idle) return;

        _logger.LogInformation(
            "TX abort requested (HTTP) — cancelling active session (partner: {Partner}, state: {State}).",
            _partner, _state);

        // Cancel the TX CTS; this propagates to any awaited KeyDownAsync or channel ReadAsync.
        _txCts.Cancel();

        // Belt-and-suspenders: stop any hardware TX immediately.
        try
        {
            await _pttController.KeyUpAsync(ct).ConfigureAwait(false);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "KeyUpAsync threw during abort — ignoring.");
        }
    }

    // ── BackgroundService ─────────────────────────────────────────────────────

    /// <inheritdoc/>
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        _logger.LogInformation("QsoAnswererService started; initial state: {State}.", _state);

        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                var batch = await ReadNextBatchAsync(stoppingToken).ConfigureAwait(false);
                if (batch is null)
                {
                    // TX session was cancelled (watchdog or abort) while waiting for a batch.
                    _logger.LogInformation(
                        "QsoAnswererService: TX session cancelled while waiting (state: {State}).",
                        _state);
                    await SafeAbortToIdleAsync(stoppingToken).ConfigureAwait(false);
                    continue;
                }

                await ProcessBatchAsync(batch, stoppingToken).ConfigureAwait(false);
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
            {
                break; // clean shutdown
            }
            catch (OperationCanceledException)
            {
                // Watchdog or abort fired during a TX operation.
                _logger.LogInformation(
                    "QsoAnswererService: TX session cancelled during TX (state: {State}).",
                    _state);
                await SafeAbortToIdleAsync(stoppingToken).ConfigureAwait(false);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex,
                    "QsoAnswererService: unexpected error in state {State}; resetting to Idle.",
                    _state);
                await SafeAbortToIdleAsync(stoppingToken).ConfigureAwait(false);
            }
        }

        _logger.LogInformation("QsoAnswererService stopped.");
    }

    // ── Batch read helper ─────────────────────────────────────────────────────

    /// <summary>
    /// Reads the next decode batch.  In <see cref="QsoState.Idle"/> only the stopping
    /// token applies; in all other states the TX CTS (<see cref="_txCts"/>) is also linked
    /// so that watchdog expiry or operator abort interrupts the wait.
    /// </summary>
    private async ValueTask<IReadOnlyList<DecodeResult>?> ReadNextBatchAsync(
        CancellationToken stoppingToken)
    {
        if (_state == QsoState.Idle)
            return await _decodeChannel.ReadAsync(stoppingToken).ConfigureAwait(false);

        using var linked = CancellationTokenSource.CreateLinkedTokenSource(
            stoppingToken, _txCts.Token);
        try
        {
            return await _decodeChannel.ReadAsync(linked.Token).ConfigureAwait(false);
        }
        catch (OperationCanceledException) when (!stoppingToken.IsCancellationRequested)
        {
            return null; // TX CTS fired
        }
    }

    // ── State machine ─────────────────────────────────────────────────────────

    private async Task ProcessBatchAsync(
        IReadOnlyList<DecodeResult> batch,
        CancellationToken stoppingToken)
    {
        var tx = _configStore.Current.Tx ?? new TxConfig();

        switch (_state)
        {
            case QsoState.Idle:
                await HandleIdleAsync(batch, tx, stoppingToken).ConfigureAwait(false);
                break;

            case QsoState.WaitReport:
                await HandleWaitReportAsync(batch, tx, stoppingToken).ConfigureAwait(false);
                break;

            case QsoState.WaitRr73:
                await HandleWaitRr73Async(batch, tx, stoppingToken).ConfigureAwait(false);
                break;

            // TX states (TxAnswer, TxReport, Tx73) and QsoComplete are transient:
            // they are entered and exited within the same HandleXxx call and are
            // never the current state at the top of the batch-processing loop.
            default:
                _logger.LogWarning(
                    "QsoAnswererService received a batch in unexpected state {State}; ignoring.",
                    _state);
                break;
        }
    }

    // ── Idle handler ──────────────────────────────────────────────────────────

    private async Task HandleIdleAsync(
        IReadOnlyList<DecodeResult> batch,
        TxConfig                    tx,
        CancellationToken           stoppingToken)
    {
        // Guard: auto-answer disabled → stay Idle regardless of decoded CQs.
        if (!tx.AutoAnswer)
            return;

        // Guard: callsign and grid must be configured before transmitting (FR-050).
        // An empty/whitespace callsign would produce a malformed FT8 message that
        // ft8_lib rejects at encode time.  Log a clear warning and stay Idle so
        // the operator knows why TX is suppressed.
        if (string.IsNullOrWhiteSpace(tx.Callsign) || string.IsNullOrWhiteSpace(tx.Grid))
        {
            _logger.LogWarning(
                "QsoAnswererService: TX suppressed — callsign or grid is not configured. " +
                "Set both in Settings → FT8 auto-answer (TX) before enabling auto-answer.");
            return;
        }

        // Scan for the first CQ in the batch (FR-050: auto-answer first decoded CQ).
        DecodeResult? cqResult = null;
        string        partner  = string.Empty;

        foreach (var r in batch)
        {
            if (TryParseCq(r.Message, out var callsign, out _))
            {
                cqResult = r;
                partner  = callsign;
                break;
            }
        }

        if (cqResult is null) return; // no CQ found — stay Idle

        _logger.LogInformation(
            "QsoAnswererService: CQ detected from {Partner} at {FreqHz} Hz — answering.",
            partner, cqResult.FreqHz);

        // Record session state.
        _partner      = partner;
        _retryCount   = 0;
        _rstRcvd      = "+00";
        _lastTxFreqHz = cqResult.FreqHz;
        _qsoStartUtc  = DateTime.UtcNow;

        // Start watchdog (fires after tx.WatchdogMinutes if no state advance).
        StartWatchdog(tx);

        // Compose and transmit the answer: PARTNER OURS GRID
        var answerMessage = $"{partner} {tx.Callsign} {tx.Grid}";
        _lastTxMessage = answerMessage;

        SetStateAndNotify(QsoState.TxAnswer);
        await TransmitAsync(answerMessage, _lastTxFreqHz, stoppingToken).ConfigureAwait(false);

        // Transmission completed — advance to WaitReport.
        ResetWatchdog(tx);
        SetStateAndNotify(QsoState.WaitReport);
    }

    // ── WaitReport handler ────────────────────────────────────────────────────

    private async Task HandleWaitReportAsync(
        IReadOnlyList<DecodeResult> batch,
        TxConfig                    tx,
        CancellationToken           stoppingToken)
    {
        var ours    = tx.Callsign;
        var partner = _partner!;

        foreach (var r in batch)
        {
            if (!TryParseMessage(r.Message, out var dest, out var src, out var payload))
                continue;

            // A message from our partner to us?
            bool fromPartner = src.Equals(partner,  StringComparison.OrdinalIgnoreCase);
            bool toUs        = dest.Equals(ours,    StringComparison.OrdinalIgnoreCase);

            if (fromPartner && toUs)
            {
                // ── Early RR73/RRR (skip TxReport, jump straight to Tx73) ──
                if (payload.Equals("RR73", StringComparison.OrdinalIgnoreCase) ||
                    payload.Equals("RRR",  StringComparison.OrdinalIgnoreCase))
                {
                    _logger.LogInformation(
                        "QsoAnswererService: early {Payload} from {Partner} — skipping to Tx73.",
                        payload, partner);
                    await ExecuteTx73Async(tx, stoppingToken).ConfigureAwait(false);
                    return;
                }

                // ── Signal report ──
                if (IsSignalReport(payload))
                {
                    _rstRcvd    = payload;
                    _retryCount = 0;
                    _logger.LogInformation(
                        "QsoAnswererService: received report {Report} from {Partner}.",
                        payload, partner);

                    // TxReport: PARTNER OURS R+00
                    var reportMessage = $"{partner} {ours} R+00";
                    _lastTxMessage = reportMessage;

                    ResetWatchdog(tx);
                    SetStateAndNotify(QsoState.TxReport);
                    await TransmitAsync(reportMessage, _lastTxFreqHz, stoppingToken).ConfigureAwait(false);

                    ResetWatchdog(tx);
                    SetStateAndNotify(QsoState.WaitRr73);
                    return;
                }
            }

            // ── Partner is working another station — abort ──
            if (fromPartner && !toUs)
            {
                _logger.LogInformation(
                    "QsoAnswererService: {Partner} is working {OtherDest} — aborting.",
                    partner, dest);
                await SafeAbortToIdleAsync(stoppingToken).ConfigureAwait(false);
                return;
            }
        }

        // No matching message — retry or abort.
        await RetryOrAbortAsync(tx, stoppingToken).ConfigureAwait(false);
    }

    // ── WaitRr73 handler ─────────────────────────────────────────────────────

    private async Task HandleWaitRr73Async(
        IReadOnlyList<DecodeResult> batch,
        TxConfig                    tx,
        CancellationToken           stoppingToken)
    {
        var ours    = tx.Callsign;
        var partner = _partner!;

        foreach (var r in batch)
        {
            if (!TryParseMessage(r.Message, out var dest, out var src, out var payload))
                continue;

            bool fromPartner = src.Equals(partner, StringComparison.OrdinalIgnoreCase);
            bool toUs        = dest.Equals(ours,   StringComparison.OrdinalIgnoreCase);

            if (fromPartner && toUs &&
                (payload.Equals("RR73", StringComparison.OrdinalIgnoreCase) ||
                 payload.Equals("RRR",  StringComparison.OrdinalIgnoreCase)))
            {
                _logger.LogInformation(
                    "QsoAnswererService: {Payload} from {Partner} received.", payload, partner);
                await ExecuteTx73Async(tx, stoppingToken).ConfigureAwait(false);
                return;
            }
        }

        // No RR73/RRR — retry or abort.
        await RetryOrAbortAsync(tx, stoppingToken).ConfigureAwait(false);
    }

    // ── Tx73 helper ───────────────────────────────────────────────────────────

    private async Task ExecuteTx73Async(TxConfig tx, CancellationToken stoppingToken)
    {
        var ours    = tx.Callsign;
        var partner = _partner!;

        var msg73 = $"{partner} {ours} 73";
        _lastTxMessage = msg73;

        ResetWatchdog(tx);
        SetStateAndNotify(QsoState.Tx73);
        await TransmitAsync(msg73, _lastTxFreqHz, stoppingToken).ConfigureAwait(false);

        // QSO complete.
        SetStateAndNotify(QsoState.QsoComplete);
        _logger.LogInformation(
            "QsoAnswererService: QSO with {Partner} complete!", partner);

        // Write ADIF log entry (task 7.6 — failures are logged as Warning; never throw).
        var record = new QsoRecord
        {
            PartnerCallsign  = partner,
            PartnerGrid      = null,               // grid not tracked at this layer
            RstSent          = "R+00",
            RstRcvd          = _rstRcvd,
            QsoStartUtc      = _qsoStartUtc,
            QsoEndUtc        = DateTime.UtcNow,
            OperatorCallsign = tx.Callsign,
            OperatorGrid     = tx.Grid,
            DialFrequencyMHz = _configStore.Current.DecodeLog.DialFrequencyMHz,
        };
        await _adifLog.AppendQsoAsync(record).ConfigureAwait(false);

        // Return to Idle.
        await SafeAbortToIdleAsync(stoppingToken).ConfigureAwait(false);
    }

    // ── Retry / abort ─────────────────────────────────────────────────────────

    private async Task RetryOrAbortAsync(TxConfig tx, CancellationToken stoppingToken)
    {
        _retryCount++;
        if (_retryCount > tx.RetryCount)
        {
            _logger.LogInformation(
                "QsoAnswererService: retry count {Count} exceeded {Max} — aborting QSO with {Partner}.",
                _retryCount - 1, tx.RetryCount, _partner);
            await SafeAbortToIdleAsync(stoppingToken).ConfigureAwait(false);
            return;
        }

        _logger.LogInformation(
            "QsoAnswererService: no response from {Partner} (retry {Retry}/{Max}) — retransmitting.",
            _partner, _retryCount, tx.RetryCount);

        // Retransmit the last TX message.
        await TransmitAsync(_lastTxMessage, _lastTxFreqHz, stoppingToken).ConfigureAwait(false);
        ResetWatchdog(tx);
        // Stay in current state (WaitReport or WaitRr73).
    }

    // ── TX helper ────────────────────────────────────────────────────────────

    /// <summary>
    /// Encodes <paramref name="message"/> to FT8 tones, synthesises audio at
    /// <paramref name="freqHz"/>, loads it into the PTT controller, and awaits
    /// full playback.
    /// </summary>
    private async Task TransmitAsync(string message, int freqHz, CancellationToken stoppingToken)
    {
        _logger.LogInformation(
            "QsoAnswererService: TX → \"{Message}\" at {FreqHz} Hz.", message, freqHz);

        var tones = new byte[Ft8Encoder.ToneCount];
        Ft8Encoder.EncodeMessage(message, tones);

        var samples = _synthesiser.Synthesise(tones, freqHz);
        _pttController.LoadAudio(samples);

        // Link stoppingToken + _txCts so both watchdog and operator abort interrupt TX.
        using var linked = CancellationTokenSource.CreateLinkedTokenSource(stoppingToken, _txCts.Token);
        await _pttController.KeyDownAsync(linked.Token).ConfigureAwait(false);

        _logger.LogDebug("QsoAnswererService: TX complete for \"{Message}\".", message);
    }

    // ── State transitions ─────────────────────────────────────────────────────

    private void SetStateAndNotify(QsoState newState)
    {
        var partner = _partner;
        _state = newState;
        _logger.LogDebug("QsoAnswererService: state → {State} (partner: {Partner}).",
            newState, partner ?? "(none)");
        _txEventBus.Publish(newState, partner);
    }

    /// <summary>
    /// Aborts to <see cref="QsoState.Idle"/>, calls <see cref="IPttController.KeyUpAsync"/>,
    /// resets session state, and replaces <see cref="_txCts"/> with a fresh CTS.
    /// Safe to call from any state, including Idle.
    /// </summary>
    private async Task SafeAbortToIdleAsync(CancellationToken stoppingToken)
    {
        var wasPartner = _partner;
        _partner = null;

        // Replace the TX CTS with a fresh no-timeout CTS so the next session starts clean.
        // Do NOT dispose the old CTS here — AbortAsync may be holding a reference to it.
        _txCts = new CancellationTokenSource();

        // Stop any active TX output.
        try
        {
            await _pttController.KeyUpAsync(stoppingToken).ConfigureAwait(false);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "KeyUpAsync threw during abort — ignoring.");
        }

        if (_state != QsoState.Idle)
        {
            _logger.LogInformation(
                "QsoAnswererService: aborted to Idle (was: {State}, partner: {Partner}).",
                _state, wasPartner ?? "(none)");
        }

        _state      = QsoState.Idle;
        _retryCount = 0;
        _txEventBus.Publish(QsoState.Idle, null);
    }

    // ── Watchdog ──────────────────────────────────────────────────────────────

    /// <summary>
    /// Starts the watchdog by scheduling a cancellation on <see cref="_txCts"/> after
    /// <c>tx.WatchdogMinutes</c>.  Call when leaving <see cref="QsoState.Idle"/>.
    /// </summary>
    private void StartWatchdog(TxConfig tx)
    {
        var timeout = TimeSpan.FromMinutes(tx.WatchdogMinutes);
        _txCts.CancelAfter(timeout);
        _logger.LogDebug("QsoAnswererService: watchdog armed for {Minutes} minutes.", tx.WatchdogMinutes);
    }

    /// <summary>
    /// Resets the watchdog to <c>tx.WatchdogMinutes</c> from now by creating a fresh
    /// <see cref="_txCts"/> with the new timeout.
    /// </summary>
    private void ResetWatchdog(TxConfig tx)
    {
        var timeout = TimeSpan.FromMinutes(tx.WatchdogMinutes);
        // Create a fresh CTS with the new timeout; the old one is dropped (GC will collect it).
        _txCts = new CancellationTokenSource(timeout);
        _logger.LogDebug("QsoAnswererService: watchdog reset for {Minutes} minutes.", tx.WatchdogMinutes);
    }

    // ── Message parsers ───────────────────────────────────────────────────────

    /// <summary>
    /// Returns <c>true</c> if <paramref name="msg"/> matches the CQ pattern
    /// (<c>CQ callsign [grid]</c>) and extracts the caller callsign.
    /// Ignores <c>CQ DX callsign</c> directional CQs — grid is the DX direction,
    /// not a Maidenhead locator.
    /// </summary>
    internal static bool TryParseCq(string msg, out string callsign, out string? grid)
    {
        var parts = msg.Trim().Split(' ', StringSplitOptions.RemoveEmptyEntries);

        if (parts.Length >= 2 &&
            parts[0].Equals("CQ", StringComparison.OrdinalIgnoreCase))
        {
            // Skip "CQ DX callsign" — parts[1] = "DX" is a directional hint, not a grid.
            if (parts[1].Equals("DX", StringComparison.OrdinalIgnoreCase) && parts.Length >= 3)
            {
                callsign = parts[2];
                grid     = null;
                return true;
            }

            if (!parts[1].Equals("DX", StringComparison.OrdinalIgnoreCase))
            {
                callsign = parts[1];
                grid     = parts.Length >= 3 ? parts[2] : null;
                return true;
            }
        }

        callsign = string.Empty;
        grid     = null;
        return false;
    }

    /// <summary>
    /// Returns <c>true</c> if <paramref name="msg"/> is a standard three-part FT8
    /// exchange message (<c>dest src payload</c>) and extracts the three parts.
    /// </summary>
    internal static bool TryParseMessage(
        string msg, out string dest, out string src, out string payload)
    {
        var parts = msg.Trim().Split(' ', StringSplitOptions.RemoveEmptyEntries);
        if (parts.Length == 3)
        {
            dest    = parts[0];
            src     = parts[1];
            payload = parts[2];
            return true;
        }

        dest = src = payload = string.Empty;
        return false;
    }

    /// <summary>
    /// Returns <c>true</c> if <paramref name="payload"/> looks like an FT8 signal
    /// report — <c>+NN</c>, <c>-NN</c>, <c>R+NN</c>, or <c>R-NN</c>.
    /// </summary>
    internal static bool IsSignalReport(string payload)
    {
        var s = payload.StartsWith("R", StringComparison.OrdinalIgnoreCase)
            ? payload[1..]
            : payload;
        return s.Length >= 2 &&
               (s[0] == '+' || s[0] == '-') &&
               s[1..].All(char.IsAsciiDigit);
    }
}
