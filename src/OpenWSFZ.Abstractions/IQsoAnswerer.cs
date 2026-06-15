namespace OpenWSFZ.Abstractions;

/// <summary>
/// Abstraction over the FT8 QSO answerer state machine (FR-047).
/// Consumed by the web layer for status reporting and abort control.
/// </summary>
public interface IQsoAnswerer
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
