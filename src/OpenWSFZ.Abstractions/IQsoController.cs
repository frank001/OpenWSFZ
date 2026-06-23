namespace OpenWSFZ.Abstractions;

/// <summary>
/// Common contract implemented by all QSO role services (FR-047).
/// Currently implemented by <c>QsoAnswererService</c>; <c>QsoCallerService</c> will
/// implement it in future. Consumed by the web layer for status reporting and
/// abort control.
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
}
