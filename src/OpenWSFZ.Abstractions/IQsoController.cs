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
}
