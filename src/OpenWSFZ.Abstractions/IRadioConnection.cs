namespace OpenWSFZ.Abstractions;

/// <summary>
/// Abstraction over a rig CAT connection (FR-031, FR-032).
/// Implementations are in <c>OpenWSFZ.Rig</c>; consumers outside that assembly
/// depend only on this interface so the protocol details are hidden.
///
/// <para>Only read-only commands (frequency query) are sent in the current version.
/// No frequency-set, mode-set, or PTT commands are defined here.</para>
/// </summary>
public interface IRadioConnection
{
    /// <summary>Opens the underlying transport (serial port or TCP socket).</summary>
    Task ConnectAsync(CancellationToken cancellationToken = default);

    /// <summary>Closes the underlying transport.</summary>
    Task DisconnectAsync(CancellationToken cancellationToken = default);

    /// <summary>
    /// Queries the rig for VFO-A dial frequency and returns the value in MHz.
    /// </summary>
    /// <exception cref="InvalidOperationException">
    /// Thrown when the rig returns a malformed or unexpected response.
    /// </exception>
    /// <exception cref="TimeoutException">
    /// Thrown when no response arrives within the implementation-defined timeout.
    /// </exception>
    Task<double> GetDialFrequencyMhzAsync(CancellationToken cancellationToken = default);

    /// <summary>
    /// <c>true</c> after a successful <see cref="ConnectAsync"/> and before
    /// <see cref="DisconnectAsync"/> is called.
    /// </summary>
    bool IsConnected { get; }
}
