namespace OpenWSFZ.Abstractions;

/// <summary>
/// Common contract implemented by all QSO role services (FR-047).
/// Implemented by <c>QsoAnswererService</c> and <c>QsoCallerService</c>.
/// Consumed by the web layer for status reporting and abort control.
/// </summary>
/// <remarks>
/// QSO roles are exclusive: at any given time only one <see cref="IQsoController"/>
/// implementation SHALL be active. No two role services SHALL transmit concurrently.
/// </remarks>
public interface IQsoController
{
    /// <summary>Current state machine state.</summary>
    QsoState State { get; }

    /// <summary>
    /// Active partner callsign, or <c>null</c> when in <see cref="QsoState.Idle"/>.
    /// </summary>
    string? Partner { get; }

    /// <summary>
    /// The exact text of the most recently transmitted message this session (e.g. the
    /// composed CQ, signal-report, or RR73/73 line actually passed to <c>TransmitAsync</c>),
    /// or <c>null</c> if nothing has been transmitted yet.
    /// <para>
    /// Surfaces the real over-the-air content so the frontend can replace its static
    /// per-state message template (<c>renderMessageRows</c>) with what was actually sent
    /// once a message has gone out (fix-tx-transcript-real-message, TX-D05) — previously
    /// this value existed only as an internal field (<c>QsoAnswererService._lastTxMessage</c>)
    /// with no external accessor, and <c>QsoCallerService</c> had no equivalent field at all.
    /// </para>
    /// <para>
    /// Defaults to <see langword="null"/> via this default interface implementation, the same
    /// pattern used by <see cref="Keying"/>, so <see cref="IQsoController"/> test doubles that
    /// never transmit require no change; <c>QsoAnswererService</c> and <c>QsoCallerService</c>
    /// override it with the real tracked value, and <c>QsoControllerRouter</c> delegates to
    /// whichever is active.
    /// </para>
    /// </summary>
    string? LastTxMessage => null;

    /// <summary>
    /// The role this controller implements.
    /// </summary>
    QsoRole Role { get; }

    /// <summary>
    /// True from the moment this controller's <c>TransmitAsync</c> helper enters
    /// <c>IPttController.KeyDownAsync</c> until that call returns — normally, via
    /// cancellation, or via a concurrent <c>KeyUpAsync</c> interrupting it. False at all
    /// other times, including before the first ever transmission in a session (the
    /// "armed but idle" default).
    /// <para>
    /// Drives <c>#tx-enable-btn</c>'s bright-red/dark-red colour directly (dev-task
    /// 2026-07-10-tx-btn-live-verify-and-settings-tab-wrap.md item A), superseding the
    /// prior <c>state</c>-string-prefix derivation described by Decision 2 in
    /// <c>tx-state-indicators/spec.md</c>. Unlike <see cref="State"/>, this signal is
    /// instrumented at a single choke point per role service (the one call site of
    /// <c>KeyDownAsync</c> inside <c>TransmitAsync</c>), so it cannot be "forgotten" at a
    /// future TX call site the way a <c>SetStateAndNotify</c> bracket can.
    /// </para>
    /// <para>
    /// Defaults to <see langword="false"/> via this default interface implementation so
    /// <see cref="IQsoController"/> stubs that never transmit (test doubles) require no
    /// change; <c>QsoAnswererService</c> and <c>QsoCallerService</c> override it with the
    /// real signal, and <c>QsoControllerRouter</c> delegates to whichever is active.
    /// </para>
    /// </summary>
    bool Keying => false;

    /// <summary>
    /// Requests an immediate abort of any in-progress QSO.
    /// Calls <c>IPttController.KeyUpAsync</c> to stop any active TX and resets to
    /// <see cref="QsoState.Idle"/>.  If the service is already in Idle, this is a no-op.
    /// </summary>
    Task AbortAsync(CancellationToken ct = default);

    /// <summary>
    /// Requests a graceful stop of the current CQ caller session
    /// (f-004-operator-visibility-improvements, design.md Decision 2b).
    /// Distinct from <see cref="AbortAsync"/>: this SHALL NOT invoke
    /// <c>IPttController.KeyUpAsync</c> or otherwise interrupt any TX sample already in
    /// progress — the active controller returns to <see cref="QsoState.Idle"/> only once it
    /// reaches its next natural wait point. Defaults to a no-op so role services with no
    /// graceful-stop concept (currently <c>QsoAnswererService</c>) require no change;
    /// <c>QsoCallerService</c> overrides it with the behaviour specified by the
    /// <c>qso-caller</c> capability.
    /// </summary>
    Task GracefulStopAsync(CancellationToken ct = default) => Task.CompletedTask;

    /// <summary>
    /// Arms a phase-aware pending TX target to answer a specific CQ call (TX-D01).
    /// The service will fire TX at the next FT8 cycle boundary of the <em>opposite</em>
    /// phase to <paramref name="cqCycleStart"/>, so that the operator's reply does not
    /// collide with the CQ station's next transmission.
    /// </summary>
    /// <param name="callsign">Callsign of the CQ station to answer.</param>
    /// <param name="frequencyHz">Audio frequency of the CQ decode, in Hz.</param>
    /// <param name="cqCycleStart">UTC cycle-start timestamp of the CQ batch.</param>
    /// <param name="ct">Cancellation token.</param>
    /// <remarks>
    /// If the service is not in <see cref="QsoState.Idle"/> the call is silently ignored.
    /// The pending target is cleared automatically on abort, QSO completion, or 60 s timeout.
    /// </remarks>
    Task AnswerCqAsync(string callsign, double frequencyHz, DateTimeOffset cqCycleStart, CancellationToken ct);

    /// <summary>
    /// Arms a phase-aware pending TX target to reply to a station that responded to our CQ
    /// (<c>CallerPartnerSelect = None</c> mode). Called from
    /// <c>POST /api/v1/tx/select-responder</c> when the operator clicks a highlighted decode row.
    /// </summary>
    /// <param name="callsign">Callsign of the responding station.</param>
    /// <param name="frequencyHz">Audio frequency of the response, in Hz.</param>
    /// <param name="responseCycleStart">UTC cycle-start of the response batch.</param>
    /// <param name="ct">Cancellation token.</param>
    /// <remarks>
    /// <c>QsoAnswererService.SelectResponderAsync</c> is a no-op (returns immediately).
    /// <c>QsoCallerService</c> implements it fully.
    /// If the caller service is not in <c>WaitAnswer</c> the call is silently ignored.
    /// </remarks>
    Task SelectResponderAsync(
        string callsign, double frequencyHz, DateTimeOffset responseCycleStart, CancellationToken ct);

    /// <summary>
    /// Arms a mid-exchange jump-in: the service will TX the correct response message
    /// at the next FT8 cycle boundary of the <em>opposite</em> phase to
    /// <paramref name="theirCycleStart"/> and advance the state machine accordingly.
    /// </summary>
    /// <param name="partnerCallsign">Callsign of the partner.</param>
    /// <param name="frequencyHz">Audio frequency of the decoded message, in Hz.</param>
    /// <param name="theirCycleStart">UTC cycle-start of the decode batch.</param>
    /// <param name="point">Which exchange message to transmit next.</param>
    /// <param name="rawPayload">
    /// The exact decoded payload text that triggered this jump-in (e.g. <c>"R-05"</c> or
    /// <c>"RRR"</c>), as matched at the <c>POST /api/v1/tx/engage-decode</c> call site.
    /// Used by the <see cref="EngagePoint.SendRr73"/> jump-in case to derive a real
    /// <c>RstRcvd</c> for the ADIF record instead of a fabricated placeholder
    /// (fix-jump-in-rr73-adif-capture). Not consumed by the other two jump-in cases.
    /// </param>
    /// <param name="snr">
    /// The real measured <c>DecodeResult.Snr</c> of the decode that triggered this jump-in, as
    /// forwarded by the browser from the same decode-row data used to compute
    /// <paramref name="frequencyHz"/>. Used by the <see cref="EngagePoint.SendReport"/> jump-in
    /// case to compose a real signal report for the ADIF <c>RstSent</c> field instead of a fixed
    /// placeholder (TX-D04). Not consumed by the other two jump-in cases.
    /// </param>
    /// <param name="ct">Cancellation token.</param>
    /// <remarks>
    /// The service MUST already be in <see cref="QsoState.Idle"/> when this is called.
    /// The caller (HTTP layer) is responsible for aborting and waiting for Idle first.
    /// <c>QsoCallerService</c> does not implement this — it returns a no-op.
    /// </remarks>
    Task EngageAtAsync(
        string partnerCallsign,
        double frequencyHz,
        DateTimeOffset theirCycleStart,
        EngagePoint point,
        string rawPayload,
        int snr,
        CancellationToken ct);
}
