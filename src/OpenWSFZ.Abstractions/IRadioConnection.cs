namespace OpenWSFZ.Abstractions;

/// <summary>
/// Abstraction over a rig CAT connection (FR-031, FR-032, FR-045).
/// Implementations are in <c>OpenWSFZ.Rig</c>; consumers outside that assembly
/// depend only on this interface so the protocol details are hidden.
///
/// <para>
/// The p16 read-only restriction is hereby amended for frequency only (FR-045):
/// <see cref="SetDialFrequencyMhzAsync"/> sends a frequency-set command to the rig.
/// No mode-set, PTT, or other rig-altering commands are defined here.
/// </para>
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
    /// Commands the rig to tune VFO-A to the specified frequency (FR-045).
    /// This is a fire-and-forget set: the method sends the command and returns
    /// without reading back confirmation. The next <see cref="GetDialFrequencyMhzAsync"/>
    /// poll will reflect the new frequency if the rig accepted the command.
    /// </summary>
    /// <param name="frequencyMHz">Target VFO-A frequency in megahertz.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    Task SetDialFrequencyMhzAsync(double frequencyMHz, CancellationToken cancellationToken = default);

    /// <summary>
    /// <c>true</c> after a successful <see cref="ConnectAsync"/> and before
    /// <see cref="DisconnectAsync"/> is called.
    /// </summary>
    bool IsConnected { get; }
}
