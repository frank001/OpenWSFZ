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
    /// The role this controller implements.
    /// </summary>
    QsoRole Role { get; }

    /// <summary>
    /// Requests an immediate abort of any in-progress QSO.
    /// Calls <c>IPttController.KeyUpAsync</c> to stop any active TX and resets to
    /// <see cref="QsoState.Idle"/>.  If the service is already in Idle, this is a no-op.
    /// </summary>
    Task AbortAsync(CancellationToken ct = default);

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
        CancellationToken ct);
}
