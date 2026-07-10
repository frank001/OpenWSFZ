using System.Threading.Channels;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Ft8;
using OpenWSFZ.Web;

namespace OpenWSFZ.Daemon;

/// <summary>
/// Background service that drives the FT8 QSO caller state machine (qso-caller feature).
///
/// <para>
/// On each decode cycle the service reads a batch of <see cref="DecodeResult"/> items from
/// a shared <c>Channel</c> (fed by the main decode pump) and advances the caller state machine:
/// </para>
/// <list type="table">
///   <item><term>Idle</term><description>When armed, transmit <c>CQ {callsign} {grid}</c>.</description></item>
///   <item><term>WaitAnswer</term><description>Scan for a response to our CQ; select partner and transmit report.</description></item>
///   <item><term>WaitRr73</term><description>Await partner's <c>R+{report}</c>; send <c>RR73</c> to complete.</description></item>
/// </list>
///
/// <para>
/// <c>CallerPartnerSelect = First</c>: auto-engage the first responder.
/// <c>CallerPartnerSelect = None</c>: operator clicks a highlighted decode-table row;
/// <see cref="SelectResponderAsync"/> stores the pending responder and wakes the service.
/// </para>
///
/// <para>
/// All watchdog, retry, ADIF-logging, H6 AP decode, and HoldTxFreq mechanics are
/// identical to <see cref="QsoAnswererService"/>.
/// </para>
///
/// <para>
/// Registered in DI only when <c>TxConfig.Role == TxRole.Caller</c>; the answerer
/// is not instantiated in that case (D3 in design.md).
/// </para>
/// </summary>
public sealed class QsoCallerService : BackgroundService, IQsoController
{
    // ── Private state ─────────────────────────────────────────────────────────

    private readonly ChannelReader<DecodeBatch> _decodeChannel;
    private readonly IConfigStore                               _configStore;
    private readonly IPttController                             _pttController;
    private readonly ITxEventBus                                 _txEventBus;
    private readonly AudioOffsetEventBus                        _audioOffsetEventBus;
    private readonly ILogger<QsoCallerService>                  _logger;
    private readonly Ft8AudioSynthesiser                        _synthesiser = new();
    private readonly IAdifLogWriter                              _adifLog;
    private readonly IApConstraintSink?                         _decoder;
    // D-013: live CAT state for resolving the true dial frequency at QSO-completion time
    // (WebApp.ResolveEffectiveFrequency's tier 1); null means CAT genuinely not wired up.
    private readonly ICatState?                                  _catState;
    // decode-panel-filtering: consulted once at the responder-selection decision point in
    // HandleWaitAnswerAsync and SelectResponderAsync; null behaves as fully unfiltered (no
    // regression for callers that don't supply one — mirrors D-013's ICatState? posture).
    private readonly IDecodeFilterStore?                         _decodeFilterStore;

    // Volatile: readable from the HTTP handler thread without a lock.
    private volatile CallerState _callerState = CallerState.Idle;
    private volatile string?     _partner     = null;

    // True only while TransmitAsync is inside its KeyDownAsync call (dev-task
    // 2026-07-10-tx-btn-live-verify-and-settings-tab-wrap.md item A). Volatile for the same
    // reason as _callerState/_partner — read from the HTTP handler thread via Keying.
    private volatile bool _keying;

    /// <summary>
    /// When <see langword="false"/>, <see cref="HandleIdleAsync"/> returns immediately without
    /// initiating any new CQ session.  Managed by <see cref="QsoControllerRouter"/>; defaults
    /// to <see langword="true"/> so unit tests and the single-role startup path work without a router.
    /// </summary>
    internal bool IsActive { get; set; } = true;

    /// <summary>
    /// Optional callback invoked by <see cref="SafeAbortToIdleAsync"/> after the service
    /// transitions to <see cref="CallerState.Idle"/>.  Set by <see cref="QsoControllerRouter"/>
    /// to revert the active role back to Answerer after a caller QSO completes or is aborted.
    /// </summary>
    internal Action? OnBecameIdle;

    // Per-session TX state.
    private int      _lastTxFreqHz  = 0;
    private string   _rstRcvd       = "+00";
    private int      _retryCount    = 0;
    private bool     _skipNextRetry = false;
    private DateTime _qsoStartUtc   = DateTime.MinValue;

    // Phase-aware pending-responder for SelectResponderAsync (None mode).
    // Mirrors _pendingTargetCallsign in QsoAnswererService.
    private readonly object  _stateLock                   = new();
    private string?          _pendingResponderCallsign;
    private double           _pendingResponderFrequencyHz;
    private bool             _pendingResponderIsAPhase;
    private DateTimeOffset   _pendingResponderSetAt;

    // decode-panel-filtering: the most recently observed DecodeResult for each responder
    // callsign seen this WaitAnswer session (CallerPartnerSelectMode.None path), keyed by
    // callsign. Lets SelectResponderAsync — which receives only a callsign, not a DecodeResult
    // — evaluate the active filter at the moment of operator selection. A callsign absent from
    // this map (e.g. a caller that bypasses the normal decode-batch path) fails open, matching
    // every other "unresolved data" case in this feature. Cleared on every return to Idle.
    private readonly Dictionary<string, DecodeResult> _recentResponderDecodes =
        new(StringComparer.OrdinalIgnoreCase);

    private volatile CancellationTokenSource _txCts = new();
    private volatile bool _operatorAbortRequested;

    /// <summary>
    /// Set by <see cref="GracefulStopAsync"/> (f-004-operator-visibility-improvements,
    /// design.md Decision 2b). Mirrors <see cref="_operatorAbortRequested"/> but drives a
    /// graceful stop rather than an immediate one: checked in <see cref="ProcessBatchAsync"/>
    /// alongside the existing <c>_txCts.IsCancellationRequested</c> check, never inside
    /// <see cref="TransmitAsync"/> — so an in-progress TX sample is never interrupted.
    /// </summary>
    private volatile bool _gracefulStopRequested;

    // Dedicated abort signal used by ReadNextBatchAsync in the Idle/WaitAnswer path.
    // Token.Register on _txCts.Token has ordering fragility (volatile reference swap);
    // a TCS set directly by AbortAsync is simpler and provably correct.
    // Reset to a fresh TCS in SafeAbortToIdleAsync so subsequent sessions can abort.
    private volatile TaskCompletionSource _abortTcs =
        new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);

    // Non-null only in unit tests — avoids 60-second watchdog waits.
    private readonly TimeSpan? _watchdogDurationOverride;

    /// <summary>
    /// Written by <see cref="SelectResponderAsync"/> so the background loop wakes up
    /// without waiting for the next regular decode batch.
    /// Exposed as <c>internal</c> so unit tests can drain it to avoid phase-dependent races.
    /// </summary>
    internal readonly Channel<DecodeBatch> _wakeupChannel =
        Channel.CreateUnbounded<DecodeBatch>(
            new UnboundedChannelOptions { SingleWriter = true, SingleReader = true });

    // ── Constructors ──────────────────────────────────────────────────────────

    /// <summary>Production constructor — all dependencies from DI.</summary>
    public QsoCallerService(
        ChannelReader<DecodeBatch>  decodeChannel,
        IConfigStore                configStore,
        IPttController              pttController,
        ITxEventBus                 txEventBus,
        IAdifLogWriter              adifLog,
        AudioOffsetEventBus         audioOffsetEventBus,
        ILogger<QsoCallerService>   logger,
        IApConstraintSink?          decoder = null,
        ICatState?                  catState = null,
        IDecodeFilterStore?         decodeFilterStore = null)
    {
        _decodeChannel       = decodeChannel;
        _configStore         = configStore;
        _pttController       = pttController;
        _txEventBus          = txEventBus;
        _audioOffsetEventBus = audioOffsetEventBus;
        _adifLog             = adifLog;
        _logger              = logger;
        _decoder             = decoder;
        _catState            = catState;
        _decodeFilterStore   = decodeFilterStore;
    }

    /// <summary>
    /// Test constructor — allows watchdog duration override, and (f-003-ap-assist-nonstandard-
    /// callsigns) an optional <see cref="IApConstraintSink"/> so tests can verify H6 AP
    /// constraint arming without waiting through the production watchdog duration. Also accepts
    /// an optional <see cref="ICatState"/> (D-013) so tests can exercise the live-CAT
    /// dial-frequency resolution path without waiting through the real watchdog duration.
    /// </summary>
    internal QsoCallerService(
        ChannelReader<DecodeBatch>  decodeChannel,
        IConfigStore                configStore,
        IPttController              pttController,
        ITxEventBus                 txEventBus,
        IAdifLogWriter              adifLog,
        AudioOffsetEventBus         audioOffsetEventBus,
        ILogger<QsoCallerService>   logger,
        TimeSpan                    watchdogDurationOverride,
        IApConstraintSink?          decoder = null,
        ICatState?                  catState = null,
        IDecodeFilterStore?         decodeFilterStore = null)
        : this(decodeChannel, configStore, pttController, txEventBus, adifLog, audioOffsetEventBus, logger, decoder, catState, decodeFilterStore)
    {
        _watchdogDurationOverride = watchdogDurationOverride;
    }

    // ── IQsoController ───────────────────────────────────────────────────────

    /// <summary>
    /// Maps <see cref="CallerState"/> to the nearest <see cref="QsoState"/> proxy (design.md D8).
    /// TODO: remove this mapping when QsoState is renamed to AnswererState and the interface
    ///       is updated to use a role-discriminated state type.
    /// </summary>
    public QsoState State => _callerState switch
    {
        CallerState.Idle        => QsoState.Idle,
        CallerState.TxCq        => QsoState.TxAnswer,    // nearest: TX active
        CallerState.WaitAnswer  => QsoState.WaitReport,  // nearest: waiting for partner
        CallerState.TxReport    => QsoState.TxReport,
        CallerState.WaitRr73    => QsoState.WaitRr73,
        CallerState.TxRr73      => QsoState.Tx73,
        CallerState.QsoComplete => QsoState.QsoComplete,
        _                       => QsoState.Idle,
    };

    /// <inheritdoc/>
    public string? Partner => _partner;

    /// <inheritdoc/>
    public QsoRole Role => QsoRole.Caller;

    /// <inheritdoc/>
    public bool Keying => _keying;

    /// <inheritdoc/>
    public async Task AbortAsync(CancellationToken ct = default)
    {
        if (_callerState == CallerState.Idle) return;

        _logger.LogInformation(
            "QsoCallerService: abort requested (HTTP) — partner: {Partner}, state: {State}.",
            _partner, _callerState);

        _operatorAbortRequested = true;
        _txCts.Cancel();
        // Signal the dedicated TCS so ReadNextBatchAsync wakes up from the Idle/WaitAnswer
        // Task.WhenAny even though _txCts is not directly linked there.
        _abortTcs.TrySetResult();

        try
        {
            await _pttController.KeyUpAsync(ct).ConfigureAwait(false);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "QsoCallerService: KeyUpAsync threw during abort — ignoring.");
        }
    }

    /// <inheritdoc/>
    /// <remarks>
    /// f-004-operator-visibility-improvements, design.md Decision 2b (FR-CQ-STOP-001).
    /// Unlike <see cref="AbortAsync"/>, this does NOT cancel <see cref="_txCts"/> or call
    /// <c>IPttController.KeyUpAsync</c> — any TX sample already in flight completes normally.
    /// The state machine picks up the request the next time <see cref="ProcessBatchAsync"/>
    /// runs (i.e. once it has returned to a Wait state), at which point it transitions to
    /// <see cref="CallerState.Idle"/> via <see cref="SafeAbortToIdleAsync"/> without
    /// transmitting again.
    /// </remarks>
    public Task GracefulStopAsync(CancellationToken ct = default)
    {
        if (_callerState == CallerState.Idle) return Task.CompletedTask;

        _gracefulStopRequested = true;

        // Post a wakeup so the service exits ReadNextBatchAsync promptly in
        // Wait states, rather than waiting up to 15 s for the next decode batch.
        // In TX states the wakeup is queued and consumed after TransmitAsync returns
        // and the state machine re-enters a Wait state.
        var wakeupCycleStart = RoundDownTo15s(DateTimeOffset.UtcNow) - TimeSpan.FromSeconds(15);
        _wakeupChannel.Writer.TryWrite(new DecodeBatch(wakeupCycleStart, []));

        return Task.CompletedTask;
    }

    /// <inheritdoc/>
    public Task AnswerCqAsync(
        string callsign, double frequencyHz, DateTimeOffset cqCycleStart, CancellationToken ct)
        => Task.CompletedTask; // Caller does not answer CQs.

    /// <inheritdoc/>
    public Task SelectResponderAsync(
        string callsign, double frequencyHz, DateTimeOffset responseCycleStart, CancellationToken ct)
    {
        lock (_stateLock)
        {
            if (_callerState != CallerState.WaitAnswer)
                return Task.CompletedTask; // Guard: only valid in WaitAnswer

            // decode-panel-filtering: reject a call naming a currently filtered-out callsign —
            // the filter applies uniformly regardless of partner-selection mode, not only to
            // the automatic First path. No _pendingResponder is stored and no state transition
            // occurs. Fails open when the callsign isn't in _recentResponderDecodes.
            var filterState = _decodeFilterStore?.Current ?? DecodeFilterState.Unfiltered;
            if (_recentResponderDecodes.TryGetValue(callsign, out var recentDecode) &&
                !DecodeFilterEvaluator.IsVisible(recentDecode, filterState))
            {
                return Task.CompletedTask;
            }

            // The responder answered on phase P → we reply on the opposite phase.
            bool responseIsAPhase          = IsAPhase(responseCycleStart);
            _pendingResponderCallsign      = callsign;
            _pendingResponderFrequencyHz   = frequencyHz;
            _pendingResponderIsAPhase      = !responseIsAPhase;   // opposite phase
            _pendingResponderSetAt         = DateTimeOffset.UtcNow;
        }

        // Wake the service so it can fire TX within the current cycle window.
        var wakeupCycleStart = RoundDownTo15s(DateTimeOffset.UtcNow) - TimeSpan.FromSeconds(15);
        _wakeupChannel.Writer.TryWrite(new DecodeBatch(wakeupCycleStart, []));

        return Task.CompletedTask;
    }

    /// <inheritdoc/>
    /// <remarks>
    /// Not implemented: <see cref="QsoControllerRouter"/> always delegates
    /// <c>EngageAtAsync</c> to <see cref="QsoAnswererService"/> (D-CALLER-012).
    /// </remarks>
    public Task EngageAtAsync(
        string partnerCallsign,
        double frequencyHz,
        DateTimeOffset theirCycleStart,
        EngagePoint point,
        CancellationToken ct)
        => Task.CompletedTask;

    /// <summary>
    /// Test-only helper: directly set pending-responder fields without pushing a wakeup batch.
    /// This avoids the race in unit tests between the service reading the wakeup channel and
    /// the test trying to drain it.  Only call from within tests that verify the pending-
    /// responder state machine; production code must always use <see cref="SelectResponderAsync"/>.
    /// </summary>
    internal void TestSetPendingResponder(
        string callsign, double freqHz, bool isAPhase, DateTimeOffset? setAt = null)
    {
        lock (_stateLock)
        {
            _pendingResponderCallsign    = callsign;
            _pendingResponderFrequencyHz = freqHz;
            _pendingResponderIsAPhase    = isAPhase;
            _pendingResponderSetAt       = setAt ?? DateTimeOffset.UtcNow;
        }
    }

    // ── BackgroundService ─────────────────────────────────────────────────────

    /// <inheritdoc/>
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        _logger.LogInformation("QsoCallerService started; initial state: {State}.", _callerState);

        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                var batch = await ReadNextBatchAsync(stoppingToken).ConfigureAwait(false);
                if (batch is null)
                {
                    _logger.LogInformation(
                        "QsoCallerService: TX session cancelled while waiting (state: {State}).",
                        _callerState);
                    var reason1 = _operatorAbortRequested ? "Operator abort" : "Watchdog timeout";
                    _operatorAbortRequested = false;
                    await SafeAbortToIdleAsync(stoppingToken, reason1).ConfigureAwait(false);
                    continue;
                }

                await ProcessBatchAsync(batch, stoppingToken).ConfigureAwait(false);
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
            {
                break;
            }
            catch (OperationCanceledException)
            {
                _logger.LogInformation(
                    "QsoCallerService: TX session cancelled during TX (state: {State}).",
                    _callerState);
                var reason2 = _operatorAbortRequested ? "Operator abort" : "Watchdog timeout";
                _operatorAbortRequested = false;
                await SafeAbortToIdleAsync(stoppingToken, reason2).ConfigureAwait(false);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex,
                    "QsoCallerService: unexpected error in state {State}; resetting to Idle.",
                    _callerState);
                await SafeAbortToIdleAsync(stoppingToken, $"Internal error: {ex.GetType().Name}").ConfigureAwait(false);
            }
        }

        _logger.LogInformation("QsoCallerService stopped.");
    }

    // ── Batch read helper ─────────────────────────────────────────────────────

    /// <summary>
    /// Awaits the next <see cref="DecodeBatch"/> from either the main decode channel or
    /// the internal wakeup channel. When in <see cref="CallerState.Idle"/>,
    /// <see cref="CallerState.WaitAnswer"/>, or <see cref="CallerState.WaitRr73"/>, both
    /// channels are raced so that a wakeup posted by <see cref="SelectResponderAsync"/> or
    /// <see cref="GracefulStopAsync"/> can fire immediately. <see cref="CallerState.WaitRr73"/>
    /// was added to this set for <see cref="GracefulStopAsync"/>
    /// (f-004-operator-visibility-improvements) — without it, a stop requested while holding
    /// in WaitRr73 would stall for up to the current 15 s decode cycle instead of firing
    /// immediately. In all other states only the decode channel is read, with the TX CTS
    /// also linked.
    /// </summary>
    private async ValueTask<DecodeBatch?> ReadNextBatchAsync(CancellationToken stoppingToken)
    {
        bool needsWakeup = _callerState is CallerState.Idle or CallerState.WaitAnswer or CallerState.WaitRr73;

        if (!needsWakeup)
        {
            using var linked = CancellationTokenSource.CreateLinkedTokenSource(
                stoppingToken, _txCts.Token);
            try
            {
                return await _decodeChannel.ReadAsync(linked.Token).ConfigureAwait(false);
            }
            catch (OperationCanceledException) when (!stoppingToken.IsCancellationRequested)
            {
                return null;
            }
        }

        // Idle or WaitAnswer: race decode channel, wakeup channel, and the abort TCS.
        // _abortTcs is set directly by AbortAsync — simpler and more reliable than
        // linking _txCts.Token through Task.Delay or Token.Register approaches.
        if (_txCts.IsCancellationRequested) return null;
        if (_wakeupChannel.Reader.TryRead(out var pending)) return pending;

        while (!stoppingToken.IsCancellationRequested)
        {
            if (_txCts.IsCancellationRequested)                  return null;
            if (_decodeChannel.TryRead(out var decode))          return decode;
            if (_wakeupChannel.Reader.TryRead(out var wakeup)) return wakeup;

            var decodeReady = _decodeChannel.WaitToReadAsync(stoppingToken).AsTask();
            var wakeupReady = _wakeupChannel.Reader.WaitToReadAsync(stoppingToken).AsTask();
            await Task.WhenAny(decodeReady, wakeupReady, _abortTcs.Task).ConfigureAwait(false);
            stoppingToken.ThrowIfCancellationRequested();
            if (_txCts.IsCancellationRequested) return null;
        }

        stoppingToken.ThrowIfCancellationRequested();
        return null!;
    }

    // ── State machine ─────────────────────────────────────────────────────────

    private async Task ProcessBatchAsync(DecodeBatch batch, CancellationToken stoppingToken)
    {
        // An abort written to the wakeup channel (see AbortAsync comment) arrives here as a
        // regular batch.  Detect the cancelled CTS before dispatching to state handlers so we
        // never start a TX operation on a cancelled session.
        if (_txCts.IsCancellationRequested)
        {
            var reason = _operatorAbortRequested ? "Operator abort" : "Watchdog timeout";
            _operatorAbortRequested = false;
            await SafeAbortToIdleAsync(stoppingToken, reason).ConfigureAwait(false);
            return;
        }

        // f-004-operator-visibility-improvements: graceful stop requested via
        // POST /api/v1/tx/stop-cq (GracefulStopAsync). By the time ProcessBatchAsync runs,
        // the state machine is always in a Wait state or Idle (Tx* states are transient,
        // handled synchronously inside the Handle*Async methods below) — so no TX is ever
        // in flight here, and this transition never interrupts an in-progress transmission.
        if (_gracefulStopRequested)
        {
            _gracefulStopRequested = false;
            await SafeAbortToIdleAsync(stoppingToken, "Operator stop").ConfigureAwait(false);
            return;
        }

        var tx = _configStore.Current.Tx ?? new TxConfig();

        switch (_callerState)
        {
            case CallerState.Idle:
                await HandleIdleAsync(batch, tx, stoppingToken).ConfigureAwait(false);
                break;

            case CallerState.WaitAnswer:
                await HandleWaitAnswerAsync(batch, tx, stoppingToken).ConfigureAwait(false);
                break;

            case CallerState.WaitRr73:
                await HandleWaitRr73Async(batch, tx, stoppingToken).ConfigureAwait(false);
                break;

            default:
                _logger.LogWarning(
                    "QsoCallerService received a batch in unexpected state {State}; ignoring.",
                    _callerState);
                break;
        }
    }

    // ── Idle handler ──────────────────────────────────────────────────────────

    private async Task HandleIdleAsync(
        DecodeBatch       batch,
        TxConfig          tx,
        CancellationToken stoppingToken)
    {
        // Router guard: when the active role is Answerer, the caller must not initiate
        // any CQ session (even if AutoAnswer is set).
        if (!IsActive) return;

        if (!tx.AutoAnswer)
            return;

        if (string.IsNullOrWhiteSpace(tx.Callsign) || string.IsNullOrWhiteSpace(tx.Grid))
        {
            _logger.LogWarning(
                "QsoCallerService: TX suppressed — callsign or grid is not configured. " +
                "Set both in Settings → FT8 auto-answer (TX) before enabling auto-answer.");
            return;
        }

        // Initialise session.
        _partner     = null;
        _retryCount  = 0;
        _rstRcvd     = "+00";
        _qsoStartUtc = DateTime.UtcNow;

        // HoldTxFreq semantics — identical to QsoAnswererService's ExecuteTxAnswerAsync.
        int txFreqHz;
        if (tx.HoldTxFreq)
        {
            txFreqHz = tx.TxAudioOffsetHz;
            _logger.LogDebug(
                "QsoCallerService: HoldTxFreq=true — transmitting at operator-set {Freq} Hz.", txFreqHz);
        }
        else
        {
            txFreqHz = tx.TxAudioOffsetHz; // CQ always uses configured offset; no caller freqHz yet
            // No need to save TxAudioOffsetHz here — we're using the stored value.
        }

        _lastTxFreqHz = txFreqHz;
        StartWatchdog(tx);

        var cqMessage = $"CQ {tx.Callsign} {tx.Grid}";
        SetStateAndNotify(CallerState.TxCq);
        await TransmitAsync(cqMessage, _lastTxFreqHz, stoppingToken).ConfigureAwait(false);

        ResetWatchdog(tx);
        _skipNextRetry = true; // A-01: next cycle is the answer window — do not count as missed
        SetStateAndNotify(CallerState.WaitAnswer);
    }

    // ── WaitAnswer handler ────────────────────────────────────────────────────

    private async Task HandleWaitAnswerAsync(
        DecodeBatch       batch,
        TxConfig          tx,
        CancellationToken stoppingToken)
    {
        var ours = tx.Callsign;

        // ── None mode: pending-responder path ────────────────────────────────
        string?        pendingCallsign;
        double         pendingFrequencyHz;
        bool           pendingIsAPhase;
        DateTimeOffset pendingSetAt;

        lock (_stateLock)
        {
            pendingCallsign    = _pendingResponderCallsign;
            pendingFrequencyHz = _pendingResponderFrequencyHz;
            pendingIsAPhase    = _pendingResponderIsAPhase;
            pendingSetAt       = _pendingResponderSetAt;
        }

        if (pendingCallsign is not null)
        {
            // Timeout guard: stale pending responder.
            if (DateTimeOffset.UtcNow - pendingSetAt > TimeSpan.FromSeconds(60))
            {
                _logger.LogWarning(
                    "QsoCallerService: pending responder '{Callsign}' expired after 60 s — discarding.",
                    pendingCallsign);
                lock (_stateLock) { _pendingResponderCallsign = null; }
            }
            else
            {
                // Phase check: only fire on the correct answer phase.
                bool nextCycleIsAPhase = IsAPhase(batch.CycleStart + TimeSpan.FromSeconds(15));
                if (nextCycleIsAPhase != pendingIsAPhase)
                {
                    // Wrong phase — retain pending responder.
                    return;
                }

                // Correct phase — fire TxReport for the pending responder.
                _logger.LogInformation(
                    "QsoCallerService: pending responder '{Callsign}' at {FreqHz} Hz — sending report at {Phase} phase.",
                    pendingCallsign, (int)Math.Round(pendingFrequencyHz), pendingIsAPhase ? "A" : "B");
                lock (_stateLock) { _pendingResponderCallsign = null; }

                _skipNextRetry = false; // responding — clear skip guard
                await ExecuteTxReportAsync(pendingCallsign, pendingFrequencyHz, tx, stoppingToken)
                    .ConfigureAwait(false);
                return;
            }
        }

        // ── First mode: auto-engage ───────────────────────────────────────────
        // decode-panel-filtering: skip any responder whose callsign fails the active filter;
        // select the first non-filtered-out one. If every response in the cycle is filtered
        // out, the loop falls through to the retry/watchdog accounting below exactly as if
        // the cycle had been genuinely empty.
        if (tx.CallerPartnerSelect == CallerPartnerSelectMode.First)
        {
            var filterState = _decodeFilterStore?.Current ?? DecodeFilterState.Unfiltered;

            foreach (var r in batch.Results)
            {
                if (!TryParseResponder(r.Message, ours, out var responder, out var freqHz, _logger))
                    continue;

                if (!DecodeFilterEvaluator.IsVisible(r, filterState))
                    continue; // filtered out — skip entirely, do not deprioritise

                _logger.LogInformation(
                    "QsoCallerService: {Responder} answered our CQ at {FreqHz} Hz — sending report.",
                    responder, (int)Math.Round(freqHz > 0 ? freqHz : r.FreqHz));

                _skipNextRetry = false; // matched — clear skip guard
                var effectiveFreq = freqHz > 0 ? freqHz : r.FreqHz;
                await ExecuteTxReportAsync(responder, effectiveFreq, tx, stoppingToken)
                    .ConfigureAwait(false);
                return;
            }
        }
        // None mode with no pending responder: stay in WaitAnswer if this batch
        // contains at least one response to our CQ — the operator must click a
        // highlighted row.  Only proceed to retry when the batch is genuinely empty
        // of responses. Every recognised responder decode is recorded (regardless of
        // filter state) so a later SelectResponderAsync call can evaluate the filter at
        // the moment of operator selection (decode-panel-filtering).
        if (tx.CallerPartnerSelect == CallerPartnerSelectMode.None)
        {
            var sawResponse = false;

            foreach (var r in batch.Results)
            {
                if (!TryParseResponder(r.Message, ours, out var responder, out _, _logger))
                    continue;

                sawResponse = true;
                lock (_stateLock) { _recentResponderDecodes[responder] = r; }
            }

            if (sawResponse) return; // responses present — hold in WaitAnswer
        }

        // No matching message — retry or abort.
        // A-01: first empty cycle after entering WaitAnswer = our own TX window; skip it.
        if (_skipNextRetry) { _skipNextRetry = false; return; }
        await RetryOrAbortAsync(tx, stoppingToken).ConfigureAwait(false);
    }

    // ── ExecuteTxReportAsync ─────────────────────────────────────────────────

    private async Task ExecuteTxReportAsync(
        string            partner,
        double            frequencyHz,
        TxConfig          tx,
        CancellationToken stoppingToken)
    {
        if (string.IsNullOrWhiteSpace(tx.Callsign))
        {
            _logger.LogWarning("QsoCallerService: TX suppressed — callsign not configured.");
            return;
        }

        _partner     = partner;
        _retryCount  = 0;

        // Adopt the responder's frequency (HoldTxFreq semantics mirror the answerer).
        int txFreqHz;
        if (tx.HoldTxFreq)
        {
            txFreqHz = tx.TxAudioOffsetHz;
        }
        else
        {
            txFreqHz = (int)Math.Round(frequencyHz);
            var currentTx = _configStore.Current.Tx ?? new TxConfig();
            try
            {
                await _configStore.SaveAsync(
                    _configStore.Current with
                    {
                        Tx = currentTx with { TxAudioOffsetHz = txFreqHz }
                    },
                    stoppingToken).ConfigureAwait(false);
                _audioOffsetEventBus.Publish(currentTx.RxAudioOffsetHz, txFreqHz, holdTxFreq: false);
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "QsoCallerService: failed to save TxAudioOffsetHz — ignoring.");
            }
        }

        _lastTxFreqHz = txFreqHz;

        // Arm H6 AP decode (D-001).
        ApplyApConstraints(tx.Callsign, partner);

        var reportMessage = $"{partner} {tx.Callsign} +00";
        SetStateAndNotify(CallerState.TxReport);
        await TransmitAsync(reportMessage, _lastTxFreqHz, stoppingToken).ConfigureAwait(false);

        ResetWatchdog(tx);
        _skipNextRetry = true; // A-01
        SetStateAndNotify(CallerState.WaitRr73);
    }

    // ── WaitRr73 handler ─────────────────────────────────────────────────────

    private async Task HandleWaitRr73Async(
        DecodeBatch       batch,
        TxConfig          tx,
        CancellationToken stoppingToken)
    {
        var ours    = tx.Callsign;
        var partner = _partner!;

        foreach (var r in batch.Results)
        {
            if (!TryParseMessage(r.Message, out var dest, out var src, out var payload))
                continue;

            bool fromPartner = src.Equals(partner, StringComparison.OrdinalIgnoreCase);
            bool toUs        = dest.Equals(ours,   StringComparison.OrdinalIgnoreCase);

            if (fromPartner && toUs)
            {
                // Partner sending R+nn or R-nn (roger report) → fire RR73.
                if (IsRogerReport(payload))
                {
                    _rstRcvd = payload.StartsWith("R", StringComparison.OrdinalIgnoreCase)
                        ? payload[1..]  // strip leading R → "+07", "-05", etc.
                        : payload;
                    _logger.LogInformation(
                        "QsoCallerService: roger report {Report} from {Partner} — sending RR73.",
                        payload, partner);
                    _skipNextRetry = false;
                    await ExecuteTxRr73Async(tx, stoppingToken).ConfigureAwait(false);
                    return;
                }
            }

            // Partner working another station.
            if (fromPartner && !toUs)
            {
                _logger.LogInformation(
                    "QsoCallerService: {Partner} is working {OtherDest} — aborting.",
                    partner, dest);
                await SafeAbortToIdleAsync(stoppingToken, $"Partner {partner} is working another station")
                    .ConfigureAwait(false);
                return;
            }
        }

        // No matching message.
        if (_skipNextRetry) { _skipNextRetry = false; return; }
        await RetryOrAbortAsync(tx, stoppingToken).ConfigureAwait(false);
    }

    // ── ExecuteTxRr73Async ────────────────────────────────────────────────────

    private async Task ExecuteTxRr73Async(TxConfig tx, CancellationToken stoppingToken)
    {
        var ours    = tx.Callsign;
        var partner = _partner!;

        var rr73Message = $"{partner} {ours} RR73";

        // Build the QSO record (used for both qsoReview event and ADIF write).
        var record = new QsoRecord
        {
            PartnerCallsign  = partner,
            PartnerGrid      = null,        // caller does not capture partner's grid in WaitRr73
            RstSent          = "+00",       // fixed report (TX-D04 deferred)
            RstRcvd          = _rstRcvd,
            QsoStartUtc      = _qsoStartUtc,
            QsoEndUtc        = Ft8TimeHelper.DeriveFt8CycleStartUtc(DateTime.UtcNow),
            OperatorCallsign = ours,
            OperatorGrid     = tx.Grid,
            DialFrequencyMHz = WebApp.ResolveEffectiveFrequency(_catState, _configStore.Current),
        };

        // qso-log-dialog: if confirmation is enabled, emit the qsoReview WS event so the
        // browser opens the confirmation dialog.  The browser is responsible for calling
        // POST /api/v1/tx/log-qso once the operator clicks OK.
        if (tx.QsoConfirmation)
        {
            _txEventBus.PublishQsoReview(
                record,
                retainedTxPower:  tx.RetainedTxPower,
                retainedComment:  tx.RetainedComment,
                retainedPropMode: tx.RetainedPropMode);
        }

        SetStateAndNotify(CallerState.TxRr73);
        await TransmitAsync(rr73Message, _lastTxFreqHz, stoppingToken).ConfigureAwait(false);

        SetStateAndNotify(CallerState.QsoComplete);
        _logger.LogInformation("QsoCallerService: QSO with {Partner} complete!", partner);

        // Write ADIF log entry.
        // When qsoConfirmation is enabled the browser sends the record via POST /api/v1/tx/log-qso;
        // the daemon must NOT also write it here (double-entry prevention — qso-log-dialog D3).
        if (!tx.QsoConfirmation)
        {
            await _adifLog.AppendQsoAsync(record).ConfigureAwait(false);
        }

        await SafeAbortToIdleAsync(stoppingToken).ConfigureAwait(false);
    }

    // ── Retry / abort ─────────────────────────────────────────────────────────

    private async Task RetryOrAbortAsync(TxConfig tx, CancellationToken stoppingToken)
    {
        _retryCount++;
        var maxRetries = tx.RetryCount;

        if (_callerState == CallerState.WaitAnswer)
        {
            // Caller-specific retry: retransmit CQ (not last TX message — D9 in design.md).
            if (maxRetries > 0 && _retryCount > maxRetries)
            {
                _logger.LogInformation(
                    "QsoCallerService: retry count {Count} exceeded {Max} — aborting.",
                    _retryCount - 1, maxRetries);
                await SafeAbortToIdleAsync(stoppingToken, $"No response after {maxRetries} CQ retries")
                    .ConfigureAwait(false);
                return;
            }

            _logger.LogInformation(
                "QsoCallerService: no response to CQ (retry {Retry}/{Max}) — retransmitting CQ.",
                _retryCount, maxRetries);

            // Retransmit CQ.
            var cqMessage = $"CQ {tx.Callsign} {tx.Grid}";
            SetStateAndNotify(CallerState.TxCq);
            await TransmitAsync(cqMessage, _lastTxFreqHz, stoppingToken).ConfigureAwait(false);
            _skipNextRetry = true;
            SetStateAndNotify(CallerState.WaitAnswer);
        }
        else
        {
            // WaitRr73 retry: same as answerer (retransmit last message).
            if (maxRetries > 0 && _retryCount > maxRetries)
            {
                _logger.LogInformation(
                    "QsoCallerService: retry count {Count} exceeded {Max} — aborting QSO with {Partner}.",
                    _retryCount - 1, maxRetries, _partner);
                await SafeAbortToIdleAsync(stoppingToken, $"No response from {_partner} after {maxRetries} retries")
                    .ConfigureAwait(false);
                return;
            }

            _logger.LogInformation(
                "QsoCallerService: no response from {Partner} (retry {Retry}/{Max}) — retransmitting report.",
                _partner, _retryCount, maxRetries);

            var reportMessage = $"{_partner} {tx.Callsign} +00";
            SetStateAndNotify(CallerState.TxReport);
            await TransmitAsync(reportMessage, _lastTxFreqHz, stoppingToken).ConfigureAwait(false);
            _skipNextRetry = true;
            SetStateAndNotify(CallerState.WaitRr73);
        }
    }

    // ── TX helper ────────────────────────────────────────────────────────────

    private async Task TransmitAsync(string message, int freqHz, CancellationToken stoppingToken)
    {
        _logger.LogInformation(
            "QsoCallerService: TX → \"{Message}\" at {FreqHz} Hz.", message, freqHz);

        var tones = new byte[Ft8Encoder.ToneCount];
        Ft8Encoder.EncodeMessage(message, tones);

        var samples = _synthesiser.Synthesise(tones, freqHz);
        _pttController.LoadAudio(samples);

        using var linked = CancellationTokenSource.CreateLinkedTokenSource(stoppingToken, _txCts.Token);

        // Keying (dev-task 2026-07-10-tx-btn-live-verify-and-settings-tab-wrap.md item A):
        // bracket the one KeyDownAsync call site with the true/false transitions and their
        // own broadcast, independent of the Tx*/Wait* state broadcasts around this method.
        _keying = true;
        PublishKeyingTransition();
        try
        {
            await _pttController.KeyDownAsync(linked.Token).ConfigureAwait(false);
        }
        finally
        {
            _keying = false;
            PublishKeyingTransition();
        }
        linked.Token.ThrowIfCancellationRequested();

        _logger.LogDebug("QsoCallerService: TX complete for \"{Message}\".", message);
    }

    /// <summary>
    /// Broadcasts the current <see cref="_callerState"/>/<see cref="_partner"/> together with
    /// the just-updated <see cref="_keying"/> value, without advancing <see cref="_callerState"/>
    /// itself. Called from <see cref="TransmitAsync"/> immediately before and after the
    /// bracketed <c>KeyDownAsync</c> call (dev-task
    /// 2026-07-10-tx-btn-live-verify-and-settings-tab-wrap.md item A).
    /// </summary>
    private void PublishKeyingTransition()
    {
        _txEventBus.Publish(
            state:             _callerState.ToString(),
            role:              "caller",
            partner:           _partner,
            autoAnswerEnabled: true,
            keying:            _keying);
    }

    // ── State transitions ─────────────────────────────────────────────────────

    private void SetStateAndNotify(CallerState newState)
    {
        var partner = _partner;
        _callerState = newState;
        _logger.LogDebug("QsoCallerService: state → {State} (partner: {Partner}).",
            newState, partner ?? "(none)");
        _txEventBus.Publish(
            state:              newState.ToString(),
            role:               "caller",
            partner:            partner,
            autoAnswerEnabled:  true,
            keying:             _keying);
    }

    /// <summary>
    /// Aborts to <see cref="CallerState.Idle"/>, calls <see cref="IPttController.KeyUpAsync"/>,
    /// resets session state, clears pending responder, and replaces <see cref="_txCts"/>.
    /// </summary>
    private async Task SafeAbortToIdleAsync(CancellationToken stoppingToken, string? abortReason = null)
    {
        var effectiveReason = abortReason
            ?? (_operatorAbortRequested ? "Operator abort" : (string?)null);
        _operatorAbortRequested = false;
        // Clear any pending graceful-stop flag — a superseding immediate abort (or any other
        // path into Idle) must not leave a stale request that fires on a future session.
        _gracefulStopRequested = false;

        // Clear pending responder under lock.
        lock (_stateLock)
        {
            _pendingResponderCallsign    = null;
            _pendingResponderFrequencyHz = 0.0;
            _pendingResponderIsAPhase    = false;
            _pendingResponderSetAt       = default;
            // decode-panel-filtering: discard stale per-session responder decode data so a
            // future WaitAnswer session never evaluates SelectResponderAsync against a
            // previous session's decode.
            _recentResponderDecodes.Clear();
        }

        var wasPartner = _partner;
        _partner       = null;
        _skipNextRetry = false;

        // Clear H6 AP constraints.
        _decoder?.SetApConstraints(null);

        _txCts    = new CancellationTokenSource();
        // Reset the abort TCS so future sessions can also be aborted cleanly.
        _abortTcs = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        // Drain any stale wakeup batches (e.g. from a SelectResponderAsync call that
        // raced with the abort) so re-entering Idle does not immediately re-arm the
        // CQ loop via HandleIdleAsync.
        while (_wakeupChannel.Reader.TryRead(out _)) { }

        try
        {
            await _pttController.KeyUpAsync(stoppingToken).ConfigureAwait(false);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "QsoCallerService: KeyUpAsync threw during abort — ignoring.");
        }

        // Supervised disarm: save autoAnswer=false so the operator must re-arm explicitly.
        try
        {
            var currentTx = _configStore.Current.Tx ?? new TxConfig();
            await _configStore.SaveAsync(
                _configStore.Current with { Tx = currentTx with { AutoAnswer = false } },
                stoppingToken).ConfigureAwait(false);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "QsoCallerService: failed to save autoAnswer=false on disarm — ignoring.");
        }

        if (_callerState != CallerState.Idle)
        {
            _logger.LogInformation(
                "QsoCallerService: aborted to Idle (was: {State}, partner: {Partner}).",
                _callerState, wasPartner ?? "(none)");
        }

        _callerState = CallerState.Idle;
        _retryCount  = 0;
        _txEventBus.Publish(
            state:             "Idle",
            role:              "caller",
            partner:           null,
            autoAnswerEnabled: false,
            abortReason:       effectiveReason,
            keying:            _keying);

        // Notify the router (if wired) that this service has become idle.
        // The router uses this to revert the active role back to Answerer when
        // the configured role is Answerer (e.g. after a "Call CQ" session ends).
        OnBecameIdle?.Invoke();
    }

    // ── H6 AP decode helper ───────────────────────────────────────────────────

    private void ApplyApConstraints(string mycall, string hiscall)
    {
        if (_decoder is null) return;

        byte[] mc = Ft8CallsignPacker.Pack28(mycall);
        byte[] hc = Ft8CallsignPacker.Pack28(hiscall);

        if (mc.Length == 0 || hc.Length == 0)
        {
            _logger.LogWarning(
                "QsoCallerService H6: callsign packing failed — AP decode disabled " +
                "(mycall='{Mycall}' {McOk}, hiscall='{Hiscall}' {HcOk}).",
                mycall, mc.Length > 0 ? "OK" : "FAILED",
                hiscall, hc.Length > 0 ? "OK" : "FAILED");
            _decoder.SetApConstraints(null);
            return;
        }

        _decoder.SetApConstraints(new Ft8ApConstraints(mc, hc));
        _logger.LogDebug(
            "QsoCallerService H6: AP constraints armed (mycall={Mycall}, hiscall={Hiscall}).",
            mycall, hiscall);
    }

    // ── Watchdog ──────────────────────────────────────────────────────────────

    private void StartWatchdog(TxConfig tx)
    {
        var minutes = Math.Clamp(tx.WatchdogMinutes, 1, 60);
        var timeout = _watchdogDurationOverride ?? TimeSpan.FromMinutes(minutes);
        _txCts.CancelAfter(timeout);
        _logger.LogInformation("QsoCallerService: watchdog armed for {Minutes} minutes.", minutes);
    }

    private void ResetWatchdog(TxConfig tx)
    {
        var minutes = Math.Clamp(tx.WatchdogMinutes, 1, 60);
        var timeout = _watchdogDurationOverride ?? TimeSpan.FromMinutes(minutes);
        _txCts = new CancellationTokenSource(timeout);
        _logger.LogInformation("QsoCallerService: watchdog reset for {Minutes} minutes.", minutes);
    }

    // ── Phase helpers ─────────────────────────────────────────────────────────

    /// <summary>
    /// Returns <c>true</c> if the cycle starting at <paramref name="cycleStart"/> is
    /// A-phase (:00 or :30 seconds within the minute).
    /// </summary>
    private static bool IsAPhase(DateTimeOffset cycleStart)
        => cycleStart.Second % 30 == 0;

    private static DateTimeOffset RoundDownTo15s(DateTimeOffset t) =>
        new DateTimeOffset(t.Year, t.Month, t.Day,
            t.Hour, t.Minute, (t.Second / 15) * 15, 0, TimeSpan.Zero);

    // ── Message parsers ───────────────────────────────────────────────────────

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
    /// Returns <c>true</c> if <paramref name="msg"/> appears to be a response to our CQ:
    /// <c>{ourCallsign} {theirCallsign} {theirGrid|signalReport}</c>.
    /// The third token may be a Maidenhead grid (first two chars are letters) OR a signal
    /// report (<c>+NN</c>, <c>-NN</c>, <c>R+NN</c>, <c>R-NN</c>): some operators skip the
    /// grid exchange and answer a CQ directly with a report, which is valid FT8 behaviour.
    /// Accepts both the full compound callsign (e.g. <c>PD2FZ/P</c>) and the base callsign
    /// (<c>PD2FZ</c>), because some FT8 decoder implementations drop the portable suffix
    /// when packing the destination token.
    /// </summary>
    internal static bool TryParseResponder(
        string msg, string ourCallsign, out string partner, out double freqHz,
        ILogger? logger = null)
    {
        partner = string.Empty;
        freqHz  = 0.0;

        var parts = msg.Trim().Split(' ', StringSplitOptions.RemoveEmptyEntries);
        if (parts.Length != 3)
            return false;

        // Accept both the full compound callsign ("PD2FZ/P") and the base callsign
        // ("PD2FZ"), because some FT8 decoder implementations drop the portable suffix
        // when packing the destination token.
        var baseCallsign = ourCallsign.Contains('/')
            ? ourCallsign[..ourCallsign.IndexOf('/')]
            : ourCallsign;

        if (!parts[0].Equals(ourCallsign, StringComparison.OrdinalIgnoreCase) &&
            !parts[0].Equals(baseCallsign, StringComparison.OrdinalIgnoreCase))
            return false;

        // Third token must be either a Maidenhead grid (first two chars are letters)
        // or a signal report (+NN / -NN / R+NN / R-NN).
        // Some operators skip the grid-square exchange and respond to a CQ directly
        // with a signal report; this is valid FT8 behaviour.
        var thirdToken = parts[2];
        var isGrid   = thirdToken.Length >= 2
                       && char.IsLetter(thirdToken[0])
                       && char.IsLetter(thirdToken[1]);
        var isReport = IsSignalReport(thirdToken);
        if (!isGrid && !isReport)
            return false;

        partner = parts[1];

        logger?.LogDebug(
            "QsoCallerService TryParseResponder: msg='{Msg}' ourCallsign='{Ours}' → match={Match}",
            msg, ourCallsign, true);

        return true;
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

    /// <summary>
    /// Returns <c>true</c> if <paramref name="payload"/> is a roger report:
    /// <c>R+NN</c> or <c>R-NN</c> (i.e. a signal report with a leading <c>R</c>).
    /// </summary>
    internal static bool IsRogerReport(string payload)
        => payload.Length >= 3 &&
           payload.StartsWith("R", StringComparison.OrdinalIgnoreCase) &&
           IsSignalReport(payload);
}
