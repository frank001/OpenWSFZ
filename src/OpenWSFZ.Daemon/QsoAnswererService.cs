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
public sealed class QsoAnswererService : BackgroundService, IQsoController
{
    // ── Private state ─────────────────────────────────────────────────────────

    private readonly ChannelReader<DecodeBatch> _decodeChannel;
    private readonly IConfigStore                               _configStore;
    private readonly IPttController                             _pttController;
    private readonly ITxEventBus                                 _txEventBus;
    private readonly AudioOffsetEventBus                        _audioOffsetEventBus;
    private readonly ILogger<QsoAnswererService>                _logger;
    private readonly Ft8AudioSynthesiser                        _synthesiser = new();
    private readonly IAdifLogWriter                              _adifLog;
    // H6 AP decode (D-001): null means AP disabled (default before any QSO is active).
    private readonly IApConstraintSink?                         _decoder;
    // D-013: live CAT state for resolving the true dial frequency at QSO-completion time
    // (WebApp.ResolveEffectiveFrequency's tier 1); null means CAT genuinely not wired up.
    private readonly ICatState?                                  _catState;
    // decode-panel-filtering: consulted once at the CQ-selection decision point in
    // HandleIdleAsync; null behaves as fully unfiltered (no regression for callers that don't
    // supply one — mirrors D-013's ICatState? backward-compatibility posture).
    private readonly IDecodeFilterStore?                         _decodeFilterStore;
    // engagement-target-validation: consulted in the CQ auto-answer scan in HandleIdleAsync
    // before arming a candidate; null behaves as always-Allowed (no regression for callers that
    // don't supply one — same backward-compatibility posture as the fields above).
    private readonly IEngagementTargetValidator?                 _engagementValidator;

    // Volatile: readable from the HTTP handler thread without a lock.
    private volatile QsoState _state   = QsoState.Idle;
    private volatile string?  _partner = null;

    // True only while TransmitAsync is inside its KeyDownAsync call (dev-task
    // 2026-07-10-tx-btn-live-verify-and-settings-tab-wrap.md item A). Volatile for the same
    // reason as _state/_partner — read from the HTTP handler thread via the Keying property.
    private volatile bool _keying;

    /// <summary>
    /// When <see langword="false"/>, <see cref="HandleIdleAsync"/> returns immediately without
    /// initiating any new QSO session.  Set to <see langword="false"/> by
    /// <see cref="QsoControllerRouter"/> when the active role has been switched to Caller at runtime,
    /// and restored to <see langword="true"/> when the active role reverts to Answerer.
    /// Defaults to <see langword="true"/> so the service behaves normally when used without a router
    /// (e.g. unit tests and the legacy single-role startup path).
    /// </summary>
    internal bool IsActive { get; set; } = true;

    // Per-session TX state.
    private string   _lastTxMessage = string.Empty;
    private int      _lastTxFreqHz  = 0;
    private string   _rstRcvd       = "+00"; // signal report received from partner
    private string?  _partnerGrid   = null;  // grid extracted from the CQ; written to ADIF
    private int      _retryCount    = 0;
    private bool     _skipNextRetry = false; // A-01: true after entering WaitReport/WaitRr73 — skip the first empty cycle (our own TX window)
    private DateTime _qsoStartUtc   = DateTime.MinValue;

    // gridtracker-udp-reporting: the most recently observed decode batch while Idle, consulted
    // by TryEngageExternal to validate that an external Reply's callsign is a currently-decoded,
    // non-filtered-out CQ. Volatile: written on the background loop thread, read from whichever
    // thread the inbound UDP listener dispatches TryEngageExternal on.
    private volatile DecodeBatch? _lastIdleDecodeBatch;

    // Phase-aware pending-target for AnswerCqAsync (TX-D01).
    // All four fields are read/written under _stateLock; volatile _state is checked inside
    // the lock but may also be read outside (HTTP thread) without a lock as before.
    private readonly object _stateLock             = new();
    private string?         _pendingTargetCallsign;
    private double          _pendingTargetFrequencyHz;
    private bool            _pendingTargetIsAPhase;   // true = wait for A-phase (:00/:30); false = B-phase (:15/:45)
    private DateTimeOffset  _pendingTargetSetAt;

    // ── Jump-in state (D-CALLER-012 EngageAtAsync) ────────────────────────────
    // Set by EngageAtAsync; consumed by HandleIdleAsync before the pending-target block.
    // Protected by _stateLock. Cleared by SafeAbortToIdleAsync.
    private EngagePoint    _jumpPoint;          // only meaningful when _jumpPartner != null
    private string?        _jumpPartner;
    private double         _jumpFreqHz;
    private bool           _jumpIsAPhase;       // false = B-phase, i.e. opposite of their decode
    private DateTimeOffset _jumpSetAt;

    // Cancellation for the active TX session; cancelled on watchdog expiry or operator abort.
    // Volatile reference so AbortAsync (HTTP thread) can safely read and cancel the current CTS.
    // Never Disposed to avoid ObjectDisposedException race in AbortAsync; let GC handle old instances.
    private volatile CancellationTokenSource _txCts = new();

    // Set in AbortAsync to distinguish an operator-requested abort from a watchdog timeout.
    // Cleared by SafeAbortToIdleAsync immediately after reading (FR-UX-002).
    private volatile bool _operatorAbortRequested;

    // Non-null only in unit tests; overrides the watchdog duration so tests don't wait 60+ seconds.
    private readonly TimeSpan? _watchdogDurationOverride;

    // TimeProvider used for the late-start guard (D-CALLER-013).
    // Defaults to TimeProvider.System in production; overridable in unit tests via the internal
    // test constructor so the guard can be exercised without sleeping through real FT8 windows.
    private readonly TimeProvider _timeProvider;

    // ── Timing constants ──────────────────────────────────────────────────────

    /// <summary>
    /// Written by <see cref="AnswerCqAsync"/> immediately after setting the pending target,
    /// so the background loop wakes up and can fire TX within the current FT8 cycle window
    /// without waiting for the next regular <see cref="_decodeChannel"/> batch (D-TX-UI-007).
    /// Exposed as <c>internal</c> so unit tests can drain it to avoid phase-dependent races.
    /// </summary>
    internal readonly Channel<DecodeBatch> _wakeupChannel =
        Channel.CreateUnbounded<DecodeBatch>(
            new UnboundedChannelOptions { SingleWriter = true, SingleReader = true });

    // ── Constructors ──────────────────────────────────────────────────────────

    /// <summary>Production constructor — all dependencies from DI.</summary>
    /// <param name="decoder">
    /// AP constraint sink for H6 directed AP decode (D-001).  Pass <see langword="null"/>
    /// (or omit) to leave AP decode disabled — the decoder behaves as pre-20260020.
    /// </param>
    public QsoAnswererService(
        ChannelReader<DecodeBatch>   decodeChannel,
        IConfigStore                 configStore,
        IPttController               pttController,
        ITxEventBus                  txEventBus,
        IAdifLogWriter               adifLog,
        AudioOffsetEventBus          audioOffsetEventBus,
        ILogger<QsoAnswererService>  logger,
        IApConstraintSink?           decoder = null,
        ICatState?                   catState = null,
        IDecodeFilterStore?          decodeFilterStore = null,
        IEngagementTargetValidator?  engagementValidator = null)
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
        _engagementValidator = engagementValidator;
        _timeProvider        = TimeProvider.System;
    }

    /// <summary>
    /// Test constructor — allows watchdog duration override to avoid 1-minute waits in unit tests,
    /// an optional <see cref="TimeProvider"/> override to exercise the late-start guard
    /// (D-CALLER-013) without sleeping through real FT8 window boundaries, and an optional
    /// <see cref="ICatState"/> (D-013) so tests can exercise the live-CAT dial-frequency
    /// resolution path without waiting through the real watchdog duration.
    /// </summary>
    internal QsoAnswererService(
        ChannelReader<DecodeBatch>   decodeChannel,
        IConfigStore                 configStore,
        IPttController               pttController,
        ITxEventBus                  txEventBus,
        IAdifLogWriter               adifLog,
        AudioOffsetEventBus          audioOffsetEventBus,
        ILogger<QsoAnswererService>  logger,
        TimeSpan                     watchdogDurationOverride,
        TimeProvider?                timeProvider = null,
        ICatState?                   catState = null,
        IDecodeFilterStore?          decodeFilterStore = null,
        IEngagementTargetValidator?  engagementValidator = null)
        : this(decodeChannel, configStore, pttController, txEventBus, adifLog, audioOffsetEventBus, logger,
               catState: catState, decodeFilterStore: decodeFilterStore, engagementValidator: engagementValidator)
    {
        _watchdogDurationOverride = watchdogDurationOverride;
        _timeProvider             = timeProvider ?? TimeProvider.System;
    }

    // ── IQsoController ───────────────────────────────────────────────────────

    /// <inheritdoc/>
    public QsoState State   => _state;

    /// <inheritdoc/>
    public string?  Partner => _partner;

    /// <inheritdoc/>
    public QsoRole Role => QsoRole.Answerer;

    /// <inheritdoc/>
    public bool Keying => _keying;

    /// <inheritdoc/>
    public Task SelectResponderAsync(
        string callsign, double frequencyHz, DateTimeOffset responseCycleStart, CancellationToken ct)
        => Task.CompletedTask; // No-op: answerer does not support operator-driven responder selection.

    /// <inheritdoc/>
    public Task EngageAtAsync(
        string         partnerCallsign,
        double         frequencyHz,
        DateTimeOffset theirCycleStart,
        EngagePoint    point,
        CancellationToken ct)
    {
        lock (_stateLock)
        {
            // Safety guard: caller (HTTP layer) must have brought us to Idle first.
            if (_state != QsoState.Idle)
                return Task.CompletedTask;

            _jumpPoint    = point;
            _jumpPartner  = partnerCallsign;
            _jumpFreqHz   = frequencyHz;
            _jumpIsAPhase = !IsAPhase(theirCycleStart);  // TX in the opposite slot
            _jumpSetAt    = DateTimeOffset.UtcNow;
        }

        // Push a wakeup so the background loop fires within the current cycle window,
        // matching the pattern used by AnswerCqAsync (_wakeupChannel push).
        var wakeupCycleStart = RoundDownTo15s(DateTimeOffset.UtcNow) - TimeSpan.FromSeconds(15);
        _wakeupChannel.Writer.TryWrite(new DecodeBatch(wakeupCycleStart, []));
        return Task.CompletedTask;
    }

    /// <inheritdoc/>
    public async Task AbortAsync(CancellationToken ct = default)
    {
        // D-CALLER-018: unconditionally clear any armed-but-not-yet-fired pending target or
        // jump-in, regardless of current _state. A target armed by AnswerCqAsync / EngageAtAsync /
        // TryEngageExternal fires independently of _state (it is specifically checked while Idle —
        // see HandleIdleAsync). Previously this method returned immediately whenever _state was
        // already Idle, which meant an armed target could NOT be cancelled by the operator once the
        // service returned to Idle — it fired regardless, up to ~30 s later, no matter how many times
        // Abort was clicked. Abort must be an unconditional hard stop: nothing may re-engage after it
        // until the operator explicitly requests it again. See
        // dev-tasks/2026-07-12-answerer-abort-hard-stop-and-reengage-timing.md.
        lock (_stateLock)
        {
            _pendingTargetCallsign    = null;
            _pendingTargetFrequencyHz = 0.0;
            _pendingTargetIsAPhase    = false;
            _pendingTargetSetAt       = default;
            _jumpPartner              = null;
        }

        if (_state == QsoState.Idle) return;

        _logger.LogInformation(
            "TX abort requested (HTTP) — cancelling active session (partner: {Partner}, state: {State}).",
            _partner, _state);

        // Flag operator abort intent before cancelling so SafeAbortToIdleAsync can distinguish
        // an operator-requested abort from a watchdog timeout (FR-UX-002).
        _operatorAbortRequested = true;
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

    /// <inheritdoc/>
    public async Task AnswerCqAsync(
        string callsign, double frequencyHz, DateTimeOffset cqCycleStart, CancellationToken ct)
    {
        if (!ArmPendingTarget(callsign, frequencyHz, cqCycleStart))
            return;   // HTTP layer already returned 409; this is a safety guard

        // Arm the system — set AutoAnswer so the guard in HandleIdleAsync passes.
        try
        {
            var current = _configStore.Current;
            var tx      = current.Tx ?? new TxConfig();
            await _configStore.SaveAsync(
                current with { Tx = tx with { AutoAnswer = true } }, ct)
                .ConfigureAwait(false);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "AnswerCqAsync: failed to save autoAnswer=true — ignoring.");
        }
    }

    /// <summary>
    /// External reply engages a specific decoded CQ (<c>external-reporting</c> capability's
    /// inbound Reply command, gridtracker-udp-reporting change). Reuses the same
    /// CQ-matching/<see cref="DecodeFilterState"/>/empty-callsign guards as the automatic
    /// auto-answer path, but targets <paramref name="callsign"/> specifically instead of "first
    /// CQ in the batch," and is <strong>not</strong> gated by <c>tx.autoAnswer</c> — an explicit
    /// external reply is a one-shot manual instruction, not automatic behaviour.
    /// </summary>
    /// <remarks>Implements <c>specs/qso-answerer/spec.md</c>'s "External reply engages a specific decoded CQ".</remarks>
    public Task<bool> TryEngageExternal(string callsign, CancellationToken ct = default)
    {
        if (_state != QsoState.Idle)
        {
            _logger.LogInformation(
                "TryEngageExternal: ignoring external reply for '{Callsign}' — not Idle (state={State}).",
                callsign, _state);
            return Task.FromResult(false);
        }

        var tx = _configStore.Current.Tx ?? new TxConfig();
        if (string.IsNullOrWhiteSpace(tx.Callsign) || string.IsNullOrWhiteSpace(tx.Grid))
        {
            _logger.LogInformation(
                "TryEngageExternal: ignoring external reply for '{Callsign}' — operator callsign/grid not configured.",
                callsign);
            return Task.FromResult(false);
        }

        var batch = _lastIdleDecodeBatch;
        if (batch is null)
        {
            _logger.LogInformation(
                "TryEngageExternal: ignoring external reply for '{Callsign}' — no decode batch received yet.",
                callsign);
            return Task.FromResult(false);
        }

        var filterState = _decodeFilterStore?.Current ?? DecodeFilterState.Unfiltered;

        foreach (var r in batch.Results)
        {
            if (!TryParseCq(r.Message, out var parsedCallsign, out _))
                continue;
            if (!string.Equals(parsedCallsign, callsign, StringComparison.OrdinalIgnoreCase))
                continue;

            if (!DecodeFilterEvaluator.IsVisible(r, filterState))
            {
                _logger.LogInformation(
                    "TryEngageExternal: ignoring external reply for '{Callsign}' — filtered out under the active decode filter.",
                    callsign);
                return Task.FromResult(false);
            }

            if (!ArmPendingTarget(parsedCallsign, r.FreqHz, batch.CycleStart))
            {
                _logger.LogInformation(
                    "TryEngageExternal: ignoring external reply for '{Callsign}' — state changed concurrently.",
                    callsign);
                return Task.FromResult(false);
            }

            _logger.LogInformation(
                "TryEngageExternal: engaging '{Callsign}' at {FreqHz} Hz via external reply.",
                callsign, r.FreqHz);
            return Task.FromResult(true);
        }

        _logger.LogInformation(
            "TryEngageExternal: ignoring external reply — '{Callsign}' is not present as a CQ in the most recent decode batch.",
            callsign);
        return Task.FromResult(false);
    }

    /// <summary>
    /// Arms the phase-aware pending TX target shared by <see cref="AnswerCqAsync"/> and
    /// <see cref="TryEngageExternal"/>: computes the opposite phase to
    /// <paramref name="cqCycleStart"/>, stores it under <see cref="_stateLock"/> (only while
    /// still <see cref="QsoState.Idle"/>), and pushes a wakeup batch so the background loop can
    /// fire TX within the current cycle if the call arrives while the correct phase is already
    /// active (D-TX-UI-007). Returns <c>false</c> without arming anything if the service is not
    /// <see cref="QsoState.Idle"/>.
    /// </summary>
    private bool ArmPendingTarget(string callsign, double frequencyHz, DateTimeOffset cqCycleStart)
    {
        lock (_stateLock)
        {
            if (_state != QsoState.Idle)
                return false;

            // CQ was on phase P → answer on the opposite phase
            bool cqIsAPhase           = IsAPhase(cqCycleStart);
            _pendingTargetCallsign    = callsign;
            _pendingTargetFrequencyHz = frequencyHz;
            _pendingTargetIsAPhase    = !cqIsAPhase;   // opposite phase
            _pendingTargetSetAt       = DateTimeOffset.UtcNow;
        }

        // Push a wakeup batch so the background loop can fire TX in the CURRENT cycle window
        // if the click arrives while the correct phase is active (D-TX-UI-007).
        //
        // The wakeup batch's CycleStart is set to (currentCycleStart − 15 s) so that the
        // phase check IsAPhase(batch.CycleStart + 15 s) evaluates to the phase of the
        // cycle that is STARTING NOW — consistent with how regular decode batches are
        // evaluated (see HandleIdleAsync phase check below).
        var wakeupCycleStart = RoundDownTo15s(DateTimeOffset.UtcNow) - TimeSpan.FromSeconds(15);
        _wakeupChannel.Writer.TryWrite(new DecodeBatch(wakeupCycleStart, []));
        return true;
    }

    /// <summary>
    /// Test-only: arms the pending-target fields directly under <see cref="_stateLock"/> without
    /// going through <see cref="AnswerCqAsync"/>'s <c>ArmPendingTarget</c> path — in particular,
    /// without pushing a wakeup batch. <c>ArmPendingTarget</c>'s wakeup is computed from real
    /// <see cref="DateTimeOffset.UtcNow"/> (not the injectable <see cref="_timeProvider"/>), so it
    /// races the background loop's own concurrent read of <see cref="_wakeupChannel"/>; tests that
    /// need fully deterministic phase-controlled arming (no such race) should use this instead.
    /// Mirrors <c>QsoCallerService.TestSetPendingResponder</c>.
    /// </summary>
    internal void TestSetPendingTarget(
        string callsign, double frequencyHz, bool isAPhase, DateTimeOffset? setAt = null)
    {
        lock (_stateLock)
        {
            _pendingTargetCallsign    = callsign;
            _pendingTargetFrequencyHz = frequencyHz;
            _pendingTargetIsAPhase    = isAPhase;
            _pendingTargetSetAt       = setAt ?? DateTimeOffset.UtcNow;
        }
    }

    /// <summary>
    /// Test-only: arms the jump-in target fields directly under <see cref="_stateLock"/> without
    /// going through <see cref="EngageAtAsync"/> — see <see cref="TestSetPendingTarget"/> for why.
    /// </summary>
    internal void TestSetJumpTarget(
        string callsign, double freqHz, EngagePoint point, bool isAPhase, DateTimeOffset? setAt = null)
    {
        lock (_stateLock)
        {
            _jumpPoint    = point;
            _jumpPartner  = callsign;
            _jumpFreqHz   = freqHz;
            _jumpIsAPhase = isAPhase;
            _jumpSetAt    = setAt ?? DateTimeOffset.UtcNow;
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
                    // Derive the reason before the async call so we don't race with a concurrent AbortAsync.
                    var reason1 = _operatorAbortRequested ? "Operator abort" : "Watchdog timeout";
                    _operatorAbortRequested = false;
                    await SafeAbortToIdleAsync(stoppingToken, reason1).ConfigureAwait(false);
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
                // Derive the reason before the async call so we don't race with a concurrent AbortAsync.
                var reason2 = _operatorAbortRequested ? "Operator abort" : "Watchdog timeout";
                _operatorAbortRequested = false;
                await SafeAbortToIdleAsync(stoppingToken, reason2).ConfigureAwait(false);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex,
                    "QsoAnswererService: unexpected error in state {State}; resetting to Idle.",
                    _state);
                await SafeAbortToIdleAsync(stoppingToken, $"Internal error: {ex.GetType().Name}").ConfigureAwait(false);
            }
        }

        _logger.LogInformation("QsoAnswererService stopped.");
    }

    // ── Batch read helper ─────────────────────────────────────────────────────

    /// <summary>
    /// Awaits the next <see cref="DecodeBatch"/> from either the main decode channel or
    /// the internal wakeup channel.  When in <see cref="QsoState.Idle"/>, both channels
    /// are raced so that a wakeup posted by <see cref="AnswerCqAsync"/> can fire TX in the
    /// current cycle without waiting for the next regular batch (D-TX-UI-007).
    /// In all other states only the decode channel is read, with the TX CTS also linked.
    /// </summary>
    private async ValueTask<DecodeBatch?> ReadNextBatchAsync(
        CancellationToken stoppingToken)
    {
        if (_state != QsoState.Idle)
        {
            // Non-Idle: only the decode channel is needed; TX CTS also cancels the wait.
            using var linked = CancellationTokenSource.CreateLinkedTokenSource(
                stoppingToken, _txCts.Token);
            try
            {
                return await _decodeChannel.ReadAsync(linked.Token).ConfigureAwait(false);
            }
            catch (OperationCanceledException) when (!stoppingToken.IsCancellationRequested)
            {
                return null; // TX CTS fired (watchdog or abort).
            }
        }

        // Idle: race _decodeChannel and _wakeupChannel.
        // Drain any already-queued wakeup first (avoids a Task.WhenAny allocation in the
        // common case where AnswerCqAsync has not yet been called this cycle).
        if (_wakeupChannel.Reader.TryRead(out var pending)) return pending;

        while (!stoppingToken.IsCancellationRequested)
        {
            if (_decodeChannel.TryRead(out var decode))          return decode;
            if (_wakeupChannel.Reader.TryRead(out var wakeup)) return wakeup;

            var decodeReady = _decodeChannel.WaitToReadAsync(stoppingToken).AsTask();
            var wakeupReady = _wakeupChannel.Reader.WaitToReadAsync(stoppingToken).AsTask();
            await Task.WhenAny(decodeReady, wakeupReady).ConfigureAwait(false);
            stoppingToken.ThrowIfCancellationRequested();
            // Loop back and TryRead from both channels.
        }

        stoppingToken.ThrowIfCancellationRequested();
        return null!; // Unreachable.
    }

    // ── State machine ─────────────────────────────────────────────────────────

    private async Task ProcessBatchAsync(
        DecodeBatch       batch,
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
        DecodeBatch       batch,
        TxConfig          tx,
        CancellationToken stoppingToken)
    {
        // gridtracker-udp-reporting: record this batch regardless of IsActive so an external
        // Reply arriving shortly after a role switch still has fresh data to validate against.
        _lastIdleDecodeBatch = batch;

        // Router guard: when the active role is Caller, the answerer must not initiate
        // any new QSO session (even if AutoAnswer or a pending target is set).
        if (!IsActive) return;

        // ── Jump-in handler (D-CALLER-012) ───────────────────────────────────────────
        // EngageAtAsync arms this block.  Fires before the pending-target block so
        // that a double-click engage takes effect even if a stale pending-target exists.
        {
            EngagePoint    jumpPoint;
            string?        jumpPartner;
            double         jumpFreqHz;
            bool           jumpIsAPhase;
            DateTimeOffset jumpSetAt;

            lock (_stateLock)
            {
                jumpPoint    = _jumpPoint;
                jumpPartner  = _jumpPartner;
                jumpFreqHz   = _jumpFreqHz;
                jumpIsAPhase = _jumpIsAPhase;
                jumpSetAt    = _jumpSetAt;
            }

            if (jumpPartner is not null)
            {
                // 60-second expiry guard (stale jump-in after a decode-loop stall).
                if (DateTimeOffset.UtcNow - jumpSetAt > TimeSpan.FromSeconds(60))
                {
                    _logger.LogWarning(
                        "QsoAnswererService: jump-in target '{Partner}' expired — discarding.",
                        jumpPartner);
                    lock (_stateLock) { _jumpPartner = null; }
                    return;
                }

                // Phase check: same semantics as the pending-target block.
                bool nextCycleIsAPhase = IsAPhase(batch.CycleStart + TimeSpan.FromSeconds(15));
                if (nextCycleIsAPhase != jumpIsAPhase)
                    return; // wrong phase — wait for next cycle

                // Correct phase — consume the jump-in and execute, regardless of how many
                // seconds into the window this cycle is (D-CALLER-021: no lateness rejection;
                // TransmitAsync truncates the audio buffer to fit the remaining window instead).
                lock (_stateLock) { _jumpPartner = null; }

                _logger.LogInformation(
                    "QsoAnswererService: jump-in to {Point} with partner {Partner} at {FreqHz} Hz.",
                    jumpPoint, jumpPartner, (int)Math.Round(jumpFreqHz));

                await ExecuteJumpInAsync(jumpPartner, jumpFreqHz, jumpPoint, tx, stoppingToken)
                    .ConfigureAwait(false);
                return;
            }
        }
        // ── End jump-in handler ───────────────────────────────────────────────────────

        // ── Phase-aware pending-target handling (TX-D01 / AnswerCqAsync) ─────────
        // Placed before all other guards so that a CQ-click armed target fires
        // independently of the general AutoAnswer flag (though AnswerCqAsync also
        // sets AutoAnswer=true, the AutoAnswer guard is NOT consulted for this path).
        string?        pendingCallsign;
        double         pendingFrequencyHz;
        bool           pendingIsAPhase;
        DateTimeOffset pendingSetAt;

        lock (_stateLock)
        {
            pendingCallsign    = _pendingTargetCallsign;
            pendingFrequencyHz = _pendingTargetFrequencyHz;
            pendingIsAPhase    = _pendingTargetIsAPhase;
            pendingSetAt       = _pendingTargetSetAt;
        }

        if (pendingCallsign is not null)
        {
            // NOTE: do NOT gate on tx.AutoAnswer here. The pending target is set synchronously
            // under _stateLock, but SaveAsync(AutoAnswer=true) in AnswerCqAsync is async. If
            // AutoAnswer is read before the save completes, the pending target is incorrectly
            // discarded (D-TX-UI-006). Abort detection uses _pendingTargetCallsign = null
            // (set by SafeAbortToIdleAsync under _stateLock), not the AutoAnswer flag.

            // Timeout guard: stale pending target (e.g. decode loop stalled).
            if (DateTimeOffset.UtcNow - pendingSetAt > TimeSpan.FromSeconds(60))
            {
                _logger.LogWarning(
                    "QsoAnswererService: pending target '{Callsign}' expired after 60 s — discarding.",
                    pendingCallsign);
                lock (_stateLock) { _pendingTargetCallsign = null; }
                return;
            }

            // Phase check: only fire on the correct answer phase.
            //
            // FRAMER SEMANTICS: the CycleFramer emits a cycle's batch at the END of that cycle —
            // i.e., at wall-clock time (batch.CycleStart + 15 s).  The cycle BEGINNING NOW is
            // therefore (batch.CycleStart + 15 s), not batch.CycleStart.
            //
            // Do NOT use UtcNow directly here: it includes sub-second jitter and is redundant
            // given that (batch.CycleStart + 15 s) already equals the authoritative cycle boundary.
            // Do NOT use batch.CycleStart alone: that is the COMPLETED cycle — one cycle too old —
            // causing TX to fire in the phase of the cycle AFTER the target (D-TX-UI-007).
            bool nextCycleIsAPhase = IsAPhase(batch.CycleStart + TimeSpan.FromSeconds(15));
            if (nextCycleIsAPhase != pendingIsAPhase)
            {
                // Wrong phase — skip this cycle; retain the pending target for next batch.
                return;
            }

            // Correct phase — clear the pending target and fire TX, regardless of how many
            // seconds into the window this cycle is (D-CALLER-021: no lateness rejection;
            // TransmitAsync truncates the audio buffer to fit the remaining window instead).
            _logger.LogInformation(
                "QsoAnswererService: pending CQ target '{Callsign}' at {FreqHz} Hz — answering at {Phase} phase.",
                pendingCallsign, (int)Math.Round(pendingFrequencyHz),
                pendingIsAPhase ? "A" : "B");
            lock (_stateLock) { _pendingTargetCallsign = null; }
            await ExecuteTxAnswerAsync(pendingCallsign, pendingFrequencyHz, null, tx, stoppingToken)
                .ConfigureAwait(false);
            return;
        }
        // ── End pending-target handling ───────────────────────────────────────────

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

        // Scan for the first non-filtered-out CQ in the batch (FR-050: auto-answer first
        // decoded CQ; decode-panel-filtering: skip any CQ whose callsign is currently
        // filtered out under the active DecodeFilterState — read once per decision, at the
        // moment of selecting which CQ to engage, not re-checked later in the QSO's lifecycle).
        var filterState = _decodeFilterStore?.Current ?? DecodeFilterState.Unfiltered;

        DecodeResult? cqResult = null;
        string        partner  = string.Empty;
        string?       cqGrid   = null;

        foreach (var r in batch.Results)
        {
            if (!TryParseCq(r.Message, out var callsign, out var grid))
                continue;

            if (!DecodeFilterEvaluator.IsVisible(r, filterState))
                continue; // filtered out — skip entirely, do not deprioritise

            // engagement-target-validation: hard-skip a candidate the region-anchored grammar
            // check rejects — no operator is looking at this specific decode, so there is no
            // override path (design.md Decision 4). Continue scanning the rest of the batch.
            var validation = _engagementValidator?.Validate(callsign) ?? EngagementValidationResult.Allowed;
            if (!validation.IsAllowed)
            {
                _logger.LogInformation(
                    "QsoAnswererService: skipping auto-answer CQ candidate {Callsign} — {Reason}",
                    callsign, validation.RejectionReason);
                continue;
            }

            cqResult = r;
            partner  = callsign;
            cqGrid   = grid;
            break;
        }

        if (cqResult is null) return; // no non-filtered-out CQ found — stay Idle

        _logger.LogInformation(
            "QsoAnswererService: CQ detected from {Partner} at {FreqHz} Hz — answering.",
            partner, cqResult.FreqHz);

        await ExecuteTxAnswerAsync(partner, cqResult.FreqHz, cqGrid, tx, stoppingToken)
            .ConfigureAwait(false);
    }

    // ── ExecuteTxAnswerAsync — shared TX answer logic ─────────────────────────

    /// <summary>
    /// Encodes and transmits an FT8 answer to <paramref name="partner"/> at
    /// <paramref name="frequencyHz"/>, then advances the state machine to
    /// <see cref="QsoState.WaitReport"/>.
    /// Called from both the automatic CQ scan path and the phase-aware pending-target path.
    /// </summary>
    private async Task ExecuteTxAnswerAsync(
        string            partner,
        double            frequencyHz,
        string?           partnerGrid,
        TxConfig          tx,
        CancellationToken stoppingToken)
    {
        // Guard: callsign and grid must be configured.
        // (Normally caught earlier but this serves as a safety net for the pending-target path.)
        if (string.IsNullOrWhiteSpace(tx.Callsign) || string.IsNullOrWhiteSpace(tx.Grid))
        {
            _logger.LogWarning(
                "QsoAnswererService: TX suppressed — callsign or grid is not configured.");
            return;
        }

        // Record session state.
        _partner     = partner;
        _partnerGrid = partnerGrid;
        _retryCount  = 0;
        _rstRcvd     = "+00";
        _qsoStartUtc = DateTime.UtcNow;

        // Task 4.1 / 4.2 — Determine TX frequency.
        // HoldTxFreq=false (default): use the caller's decoded frequency; auto-update
        //   TxAudioOffsetHz in config so the waterfall cursor reflects the actual TX position,
        //   and push an audioOffset WS event.
        // HoldTxFreq=true: use the operator-configured TxAudioOffsetHz; do not modify
        //   config or push an event so the cursor stays where the operator set it.
        int txFreqHz;
        if (tx.HoldTxFreq)
        {
            txFreqHz = tx.TxAudioOffsetHz;
            _logger.LogDebug(
                "QsoAnswererService: HoldTxFreq=true — transmitting at operator-set {Freq} Hz.",
                txFreqHz);
        }
        else
        {
            txFreqHz      = (int)Math.Round(frequencyHz);
            var currentTx = _configStore.Current.Tx ?? new TxConfig();
            await _configStore.SaveAsync(
                _configStore.Current with
                {
                    Tx = currentTx with { TxAudioOffsetHz = txFreqHz }
                },
                stoppingToken).ConfigureAwait(false);
            _audioOffsetEventBus.Publish(currentTx.RxAudioOffsetHz, txFreqHz, holdTxFreq: false);
        }

        // Task 4.3: store the session TX frequency; used consistently for all
        // subsequent transmissions (answer, report, Tx73, retries).
        _lastTxFreqHz = txFreqHz;

        // Start watchdog (fires after tx.WatchdogMinutes if no state advance).
        StartWatchdog(tx);

        // Compose and transmit the answer: PARTNER OURS GRID
        var answerMessage = $"{partner} {tx.Callsign} {tx.Grid}";
        _lastTxMessage = answerMessage;

        SetStateAndNotify(QsoState.TxAnswer);
        await TransmitAsync(answerMessage, _lastTxFreqHz, stoppingToken).ConfigureAwait(false);

        // Transmission completed — advance to WaitReport.
        ResetWatchdog(tx);
        _skipNextRetry = true; // A-01: next cycle is our own TX window; do not count as missed response

        // H6 AP decode (D-001): arm directed AP decode for the active QSO pair now that
        // we have both mycall and hiscall confirmed.  This allows the native shim to inject
        // ±40.0 LLR hard constraints for the 56 known callsign bits in subsequent decode
        // cycles, helping LDPC converge for co-channel messages from/to this partner.
        ApplyApConstraints(tx.Callsign, partner);

        SetStateAndNotify(QsoState.WaitReport);
    }

    // ── ExecuteJumpInAsync — mid-exchange jump-in (D-CALLER-012) ─────────────────

    /// <summary>
    /// Executes a mid-exchange jump-in requested by <see cref="EngageAtAsync"/>.
    /// Sets partner/frequency, transmits the correct response message for
    /// <paramref name="point"/>, and advances the state machine accordingly.
    /// </summary>
    private async Task ExecuteJumpInAsync(
        string        partner,
        double        freqHz,
        EngagePoint   point,
        TxConfig      tx,
        CancellationToken stoppingToken)
    {
        if (string.IsNullOrWhiteSpace(tx.Callsign) || string.IsNullOrWhiteSpace(tx.Grid))
        {
            _logger.LogWarning(
                "QsoAnswererService: jump-in suppressed — callsign or grid not configured.");
            return;
        }

        // Initialise per-session state (mirrors ExecuteTxAnswerAsync).
        _partner      = partner;
        _partnerGrid  = null;        // not available in mid-exchange jump-in
        _retryCount   = 0;
        _rstRcvd      = "+00";
        _qsoStartUtc  = DateTime.UtcNow;

        // Determine TX frequency (mirrors ExecuteTxAnswerAsync HoldTxFreq logic).
        int txFreqHz;
        if (tx.HoldTxFreq)
        {
            txFreqHz = tx.TxAudioOffsetHz;
        }
        else
        {
            txFreqHz = (int)Math.Round(freqHz);
            try
            {
                await _configStore.SaveAsync(
                    _configStore.Current with
                    {
                        Tx = (_configStore.Current.Tx ?? new TxConfig()) with
                        {
                            TxAudioOffsetHz = txFreqHz,
                        },
                    }, stoppingToken).ConfigureAwait(false);
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "QsoAnswererService: jump-in failed to update TxAudioOffsetHz.");
            }
            var currentTxForEvent = _configStore.Current.Tx ?? new TxConfig();
            _audioOffsetEventBus.Publish(currentTxForEvent.RxAudioOffsetHz, txFreqHz, holdTxFreq: false);
        }

        _lastTxFreqHz = txFreqHz;

        StartWatchdog(tx);
        ApplyApConstraints(tx.Callsign, partner);

        switch (point)
        {
            case EngagePoint.SendReport:
            {
                // They sent us a plain SNR → we reply R+00 → enter WaitRr73.
                var msg = $"{partner} {tx.Callsign} R+00";
                _lastTxMessage = msg;
                SetStateAndNotify(QsoState.TxReport);
                await TransmitAsync(msg, _lastTxFreqHz, stoppingToken).ConfigureAwait(false);
                ResetWatchdog(tx);
                _skipNextRetry = true;   // A-01: our TX window immediately follows
                SetStateAndNotify(QsoState.WaitRr73);
                break;
            }

            case EngagePoint.SendRr73:
            {
                // They sent RRR or R±NN → we reply RR73 → QsoComplete (no ADIF — partial QSO).
                var msg = $"{partner} {tx.Callsign} RR73";
                _lastTxMessage = msg;
                SetStateAndNotify(QsoState.Tx73);    // nearest proxy; UI shows as final TX
                await TransmitAsync(msg, _lastTxFreqHz, stoppingToken).ConfigureAwait(false);
                await SafeAbortToIdleAsync(stoppingToken).ConfigureAwait(false);
                break;
            }

            case EngagePoint.Send73:
            {
                // They sent RR73 → we reply 73 → QsoComplete (ADIF written via ExecuteTx73Async).
                await ExecuteTx73Async(tx, stoppingToken).ConfigureAwait(false);
                break;
            }
        }
    }

    // ── WaitReport handler ────────────────────────────────────────────────────

    private async Task HandleWaitReportAsync(
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
                    _skipNextRetry = false; // A-01: matching decode — clear skip guard
                    await ExecuteTx73Async(tx, stoppingToken).ConfigureAwait(false);
                    return;
                }

                // ── Signal report ──
                if (IsSignalReport(payload))
                {
                    _rstRcvd       = payload;
                    _retryCount    = 0;
                    _skipNextRetry = false; // A-01: matching decode — clear skip guard
                    _logger.LogInformation(
                        "QsoAnswererService: received report {Report} from {Partner}.",
                        payload, partner);

                    // TxReport: PARTNER OURS R+00
                    var reportMessage = $"{partner} {ours} R+00";
                    _lastTxMessage = reportMessage;

                    // D-007: ResetWatchdog moved to AFTER TransmitAsync so AbortAsync cannot
                    // cancel a pre-swap CTS that TransmitAsync never sees.
                    SetStateAndNotify(QsoState.TxReport);
                    await TransmitAsync(reportMessage, _lastTxFreqHz, stoppingToken).ConfigureAwait(false);

                    ResetWatchdog(tx);
                    _skipNextRetry = true; // A-01: next cycle is our own TX window in WaitRr73
                    SetStateAndNotify(QsoState.WaitRr73);
                    return;
                }
            }

            // ── Partner working another station — abort. Distinguish this from the partner simply
            // still calling CQ (dest == "CQ"), which is not evidence they've moved on — see D-CALLER-020. ──
            if (fromPartner && !toUs && !dest.Equals("CQ", StringComparison.OrdinalIgnoreCase))
            {
                _logger.LogInformation(
                    "QsoAnswererService: {Partner} is working {OtherDest} — aborting.",
                    partner, dest);
                await SafeAbortToIdleAsync(stoppingToken, $"Partner {partner} is working another station").ConfigureAwait(false);
                return;
            }
        }

        // No matching message — retry or abort.
        // A-01: The first empty cycle after entering WaitReport coincides with our own TX window;
        //       the silence guard fires because we were transmitting, not because the partner was
        //       silent.  Skip that cycle and give the partner time to respond.
        if (_skipNextRetry) { _skipNextRetry = false; return; }
        await RetryOrAbortAsync(tx, stoppingToken).ConfigureAwait(false);
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

            if (fromPartner && toUs &&
                (payload.Equals("RR73", StringComparison.OrdinalIgnoreCase) ||
                 payload.Equals("RRR",  StringComparison.OrdinalIgnoreCase)))
            {
                _logger.LogInformation(
                    "QsoAnswererService: {Payload} from {Partner} received.", payload, partner);
                _skipNextRetry = false; // A-01: matching decode — clear skip guard
                await ExecuteTx73Async(tx, stoppingToken).ConfigureAwait(false);
                return;
            }
        }

        // No RR73/RRR — retry or abort.
        // A-01: Same first-cycle guard as WaitReport — skip the cycle that covers our TX window.
        if (_skipNextRetry) { _skipNextRetry = false; return; }
        await RetryOrAbortAsync(tx, stoppingToken).ConfigureAwait(false);
    }

    // ── Tx73 helper ───────────────────────────────────────────────────────────

    private async Task ExecuteTx73Async(TxConfig tx, CancellationToken stoppingToken)
    {
        var ours    = tx.Callsign;
        var partner = _partner!;

        var msg73 = $"{partner} {ours} 73";
        _lastTxMessage = msg73;

        // D-007: ResetWatchdog moved to AFTER TransmitAsync for the same reason as
        // HandleWaitReportAsync — prevent AbortAsync from cancelling a stale CTS that
        // TransmitAsync never sees, which would silently write a spurious ADIF record.
        // Note: no ResetWatchdog call here — SafeAbortToIdleAsync (below) unconditionally
        // replaces _txCts with a fresh CTS, so any timeout-armed CTS would be immediately
        // discarded. Resetting the watchdog at QSO completion serves no purpose.
        // Build the QSO record (used for both qsoReview event and ADIF write).
        var record = new QsoRecord
        {
            PartnerCallsign  = partner,
            PartnerGrid      = _partnerGrid,       // captured from the CQ decode
            RstSent          = "R+00",
            RstRcvd          = _rstRcvd,
            QsoStartUtc      = _qsoStartUtc,
            QsoEndUtc        = Ft8TimeHelper.DeriveFt8CycleStartUtc(DateTime.UtcNow),
            OperatorCallsign = tx.Callsign,
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

        SetStateAndNotify(QsoState.Tx73);
        await TransmitAsync(msg73, _lastTxFreqHz, stoppingToken).ConfigureAwait(false);

        // QSO complete.
        SetStateAndNotify(QsoState.QsoComplete);
        _logger.LogInformation(
            "QsoAnswererService: QSO with {Partner} complete!", partner);

        // Write ADIF log entry (task 7.6 — failures are logged as Warning; never throw).
        // When qsoConfirmation is enabled the browser sends the record via POST /api/v1/tx/log-qso;
        // the daemon must NOT also write it here (double-entry prevention — qso-log-dialog D3).
        if (!tx.QsoConfirmation)
        {
            await _adifLog.AppendQsoAsync(record).ConfigureAwait(false);
        }

        // Return to Idle.
        await SafeAbortToIdleAsync(stoppingToken).ConfigureAwait(false);
    }

    // ── Retry / abort ─────────────────────────────────────────────────────────

    private async Task RetryOrAbortAsync(TxConfig tx, CancellationToken stoppingToken)
    {
        // RetryCount = 0 means unlimited; the watchdog timer acts as the backstop.
        _retryCount++;
        var maxRetries = tx.RetryCount; // 0 = unlimited; watchdog is the backstop
        if (maxRetries > 0 && _retryCount > maxRetries)
        {
            _logger.LogInformation(
                "QsoAnswererService: retry count {Count} exceeded {Max} — aborting QSO with {Partner}.",
                _retryCount - 1, maxRetries, _partner);
            await SafeAbortToIdleAsync(stoppingToken, $"No response from {_partner} after {maxRetries} retries").ConfigureAwait(false);
            return;
        }

        _logger.LogInformation(
            "QsoAnswererService: no response from {Partner} (retry {Retry}/{Max}) — retransmitting.",
            _partner, _retryCount, maxRetries);

        // Bracket the retransmission with a Tx*/Wait* broadcast pair so #tx-enable-btn shows
        // bright red for the duration of the retry, mirroring QsoCallerService.RetryOrAbortAsync.
        // SetStateAndNotify only sets _state and publishes to the event bus — it does NOT call
        // ResetWatchdog, so this does not reintroduce the watchdog-reset-on-retry problem D-008
        // guards against (see below); it only fixes what gets broadcast.
        var waitState = _state; // WaitReport or WaitRr73 — the only states this is called from
        var txState   = waitState == QsoState.WaitRr73 ? QsoState.TxReport : QsoState.TxAnswer;
        SetStateAndNotify(txState);

        // Retransmit the last TX message.
        await TransmitAsync(_lastTxMessage, _lastTxFreqHz, stoppingToken).ConfigureAwait(false);
        _skipNextRetry = true; // A-01: retry TX window also needs its silence cycle skipped
        // D-008: watchdog is NOT reset here — retries are not state transitions.
        // The timer runs uninterrupted across retry cycles; genuine forward transitions
        // (HandleIdleAsync, HandleWaitReportAsync, ExecuteTx73Async) still call ResetWatchdog.
        SetStateAndNotify(waitState); // back to WaitReport or WaitRr73
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

        // D-CALLER-021: a manual engage now fires unconditionally once the phase check passes,
        // however late into its window that happens — so the transmission itself must never key
        // past the current window's boundary. Truncate the buffer to whatever fits.
        var sampleCount = Ft8TimeHelper.ClampSampleCountToWindowBoundary(
            _timeProvider.GetUtcNow(), samples.Length, Ft8AudioSynthesiser.SampleRateHz);
        if (sampleCount == 0)
        {
            _logger.LogDebug(
                "QsoAnswererService: window already closed — skipping transmission of \"{Message}\".",
                message);
            return;
        }
        if (sampleCount < samples.Length)
            samples = samples[..sampleCount];

        _pttController.LoadAudio(samples);

        // Link stoppingToken + _txCts so both watchdog and operator abort interrupt TX.
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
            // dev-task 2026-07-12-cat-tx-ptt-missing-keyup-after-transmit.md: KeyUpAsync
            // MUST run here, not only from the abort path (SafeAbortToIdleAsync) — that path
            // is for operator/watchdog-initiated abort of an in-progress *session*, this is
            // the ordinary, successful (or cancelled) end of a single transmission. Every
            // KeyDownAsync must be paired with a KeyUpAsync in the normal-completion path or
            // PTT relies on the 20 s PttWatchdog failsafe to ever release, which breaks FT8
            // slot timing on every single transmission. Use CancellationToken.None so release
            // still happens even if linked.Token is already cancelled — both controllers'
            // KeyUpAsync bodies already tolerate being called when nothing is asserted (a
            // safe no-op).
            try
            {
                await _pttController.KeyUpAsync(CancellationToken.None).ConfigureAwait(false);
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "QsoAnswererService: KeyUpAsync threw after TransmitAsync — ignoring.");
            }
            _keying = false;
            PublishKeyingTransition();
        }
        // D-007: KeyDownAsync may return normally even when cancelled (audio stops but no exception).
        // Throw here so the abort propagates up through the state machine instead of advancing state.
        linked.Token.ThrowIfCancellationRequested();

        _logger.LogDebug("QsoAnswererService: TX complete for \"{Message}\".", message);
    }

    /// <summary>
    /// Broadcasts the current <see cref="_state"/>/<see cref="_partner"/> together with the
    /// just-updated <see cref="_keying"/> value, without advancing <see cref="_state"/> itself.
    /// Called from <see cref="TransmitAsync"/> immediately before and after the bracketed
    /// <c>KeyDownAsync</c> call (dev-task 2026-07-10-tx-btn-live-verify-and-settings-tab-wrap.md
    /// item A).
    /// </summary>
    private void PublishKeyingTransition()
    {
        _txEventBus.Publish(
            state:             _state.ToString(),
            role:              "answerer",
            partner:           _partner,
            autoAnswerEnabled: true,
            keying:            _keying);
    }

    // ── State transitions ─────────────────────────────────────────────────────

    private void SetStateAndNotify(QsoState newState)
    {
        var partner = _partner;
        _state = newState;
        _logger.LogDebug("QsoAnswererService: state → {State} (partner: {Partner}).",
            newState, partner ?? "(none)");
        _txEventBus.Publish(
            state:             newState.ToString(),
            role:              "answerer",
            partner:           partner,
            autoAnswerEnabled: true,
            keying:            _keying);
    }

    /// <summary>
    /// Aborts to <see cref="QsoState.Idle"/>, calls <see cref="IPttController.KeyUpAsync"/>,
    /// resets session state, and replaces <see cref="_txCts"/> with a fresh CTS.
    /// Safe to call from any state, including Idle.
    /// </summary>
    /// <param name="abortReason">
    /// Optional human-readable abort reason for the TX history log (FR-UX-002).
    /// Null means normal QSO completion or a routine Idle push — no abort entry is emitted.
    /// When null, the method falls back to <see cref="_operatorAbortRequested"/> to detect
    /// operator-abort intent (covers callers that do not derive the reason inline).
    /// </param>
    private async Task SafeAbortToIdleAsync(CancellationToken stoppingToken, string? abortReason = null)
    {
        // Resolve the effective abort reason.
        // An explicit caller reason takes precedence; otherwise check the operator-abort flag.
        // Normal QSO completion callers pass null and clear the flag cleanly.
        var effectiveReason = abortReason
            ?? (_operatorAbortRequested ? "Operator abort" : (string?)null);
        _operatorAbortRequested = false;
        // Clear phase-aware pending target so no delayed TX fires after abort.
        lock (_stateLock)
        {
            _pendingTargetCallsign    = null;
            _pendingTargetFrequencyHz = 0.0;
            _pendingTargetIsAPhase    = false;
            _pendingTargetSetAt       = default;
            _jumpPartner              = null;   // D-CALLER-012: clear any pending jump-in
        }

        var wasPartner = _partner;
        _partner        = null;
        _partnerGrid    = null;
        _skipNextRetry  = false; // A-01: clear skip guard on every return to Idle

        // H6 AP decode (D-001): clear AP constraints on return to Idle so the next
        // session starts without stale callsign constraints from the previous partner.
        _decoder?.SetApConstraints(null);

        // Replace the TX CTS with a fresh no-timeout CTS so the next session starts clean.
        // Do NOT dispose the old CTS here — AbortAsync may be holding a reference to it.
        //
        // RACE NOTE: AbortAsync (HTTP thread) reads _txCts and _state without a lock.
        // Between this CTS replacement and the subsequent _state = QsoState.Idle write,
        // an AbortAsync call could read the new CTS and cancel it, wrongly aborting the
        // next session before it starts.  The service loop self-heals: ReadNextBatchAsync
        // observes the cancelled token, re-enters SafeAbortToIdleAsync, and produces a
        // third fresh CTS.  The operator sees one spurious abort log line.  Accepted risk:
        // the window spans one KeyUpAsync call and requires a concurrent HTTP abort at
        // precisely that moment during an already-aborting session.
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

        // D-TX-UI-001 / D-TX-UI-003: supervised single-QSO model — disarm on every return
        // to Idle (abort, QSO completion, retry exhaustion, partner working another station).
        // The write is idempotent with the /tx/abort HTTP endpoint save (both write the same value).
        try
        {
            var currentTx = _configStore.Current.Tx ?? new TxConfig();
            await _configStore.SaveAsync(
                _configStore.Current with { Tx = currentTx with { AutoAnswer = false } },
                stoppingToken).ConfigureAwait(false);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "QsoAnswererService: failed to save autoAnswer=false on disarm — ignoring.");
        }

        if (_state != QsoState.Idle)
        {
            _logger.LogInformation(
                "QsoAnswererService: aborted to Idle (was: {State}, partner: {Partner}).",
                _state, wasPartner ?? "(none)");
        }

        _state      = QsoState.Idle;
        _retryCount = 0;
        _txEventBus.Publish(
            state:             QsoState.Idle.ToString(),
            role:              "answerer",
            partner:           null,
            autoAnswerEnabled: false,
            abortReason:       effectiveReason,
            keying:            _keying);
    }

    // ── H6 AP decode helper ───────────────────────────────────────────────────

    /// <summary>
    /// Packs <paramref name="mycall"/> and <paramref name="hiscall"/> and arms the
    /// AP constraint sink for directed AP decode (H6, D-001).  If either callsign
    /// fails packing (non-standard format) a warning is logged and AP is disabled.
    /// </summary>
    private void ApplyApConstraints(string mycall, string hiscall)
    {
        if (_decoder is null) return;

        byte[] mc = Ft8CallsignPacker.Pack28(mycall);
        byte[] hc = Ft8CallsignPacker.Pack28(hiscall);

        if (mc.Length == 0 || hc.Length == 0)
        {
            _logger.LogWarning(
                "QsoAnswererService H6: callsign packing failed — AP decode disabled " +
                "(mycall='{Mycall}' {McOk}, hiscall='{Hiscall}' {HcOk}). " +
                "Non-standard callsigns are not supported by the AP packer.",
                mycall, mc.Length > 0 ? "OK" : "FAILED",
                hiscall, hc.Length > 0 ? "OK" : "FAILED");
            _decoder.SetApConstraints(null);
            return;
        }

        _decoder.SetApConstraints(new Ft8ApConstraints(mc, hc));
        _logger.LogDebug(
            "QsoAnswererService H6: AP constraints armed (mycall={Mycall}, hiscall={Hiscall}).",
            mycall, hiscall);
    }

    // ── Watchdog ──────────────────────────────────────────────────────────────

    /// <summary>
    /// Starts the watchdog by scheduling a cancellation on <see cref="_txCts"/> after
    /// <c>tx.WatchdogMinutes</c>.  Call when leaving <see cref="QsoState.Idle"/>.
    /// </summary>
    private void StartWatchdog(TxConfig tx)
    {
        // Clamp defensively to [1, 60]: WatchdogMinutes < 1 would cause CancelAfter(TimeSpan.Zero)
        // which cancels the CTS immediately, aborting TX before it starts; > 60 exceeds the agreed
        // maximum and could produce a TimeSpan that overflows CancellationTokenSource.CancelAfter.
        var minutes = Math.Clamp(tx.WatchdogMinutes, 1, 60);
        // _watchdogDurationOverride is non-null only in unit tests; avoids 60-second waits.
        var timeout = _watchdogDurationOverride ?? TimeSpan.FromMinutes(minutes);
        _txCts.CancelAfter(timeout);
        _logger.LogInformation("QsoAnswererService: watchdog armed for {Minutes} minutes.", minutes);
    }

    /// <summary>
    /// Resets the watchdog to <c>tx.WatchdogMinutes</c> from now by creating a fresh
    /// <see cref="_txCts"/> with the new timeout.
    /// </summary>
    private void ResetWatchdog(TxConfig tx)
    {
        // Clamp defensively to [1, 60] — same rationale as StartWatchdog.
        var minutes = Math.Clamp(tx.WatchdogMinutes, 1, 60);
        // _watchdogDurationOverride is non-null only in unit tests; avoids 60-second waits.
        var timeout = _watchdogDurationOverride ?? TimeSpan.FromMinutes(minutes);
        // Create a fresh CTS with the new timeout; the old one is dropped (GC will collect it).
        _txCts = new CancellationTokenSource(timeout);
        _logger.LogInformation("QsoAnswererService: watchdog reset for {Minutes} minutes.", minutes);
    }

    // ── Phase helpers ─────────────────────────────────────────────────────────

    /// <summary>
    /// Returns <c>true</c> if the cycle starting at <paramref name="cycleStart"/> is
    /// A-phase (:00 or :30 seconds within the minute); <c>false</c> for B-phase (:15/:45).
    /// </summary>
    private static bool IsAPhase(DateTimeOffset cycleStart)
        => cycleStart.Second % 30 == 0;

    /// <summary>
    /// Rounds <paramref name="t"/> down to the nearest 15-second FT8 cycle boundary (UTC).
    /// Used to construct the wakeup batch's <c>CycleStart</c> in <see cref="AnswerCqAsync"/>.
    /// </summary>
    private static DateTimeOffset RoundDownTo15s(DateTimeOffset t) =>
        new DateTimeOffset(t.Year, t.Month, t.Day,
            t.Hour, t.Minute, (t.Second / 15) * 15, 0, TimeSpan.Zero);

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
