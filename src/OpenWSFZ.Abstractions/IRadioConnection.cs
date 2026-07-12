namespace OpenWSFZ.Abstractions;

/// <summary>
/// Abstraction over a rig CAT connection (FR-031, FR-032, FR-045, FR-056).
/// Implementations are in <c>OpenWSFZ.Rig</c>; consumers outside that assembly
/// depend only on this interface so the protocol details are hidden.
///
/// <para>
/// The p16 read-only restriction was first amended for frequency (FR-045):
/// <see cref="SetDialFrequencyMhzAsync"/> sends a frequency-set command to the rig.
/// It is <b>hereby further amended</b> for PTT (FR-056): <see cref="SetPttAsync"/>
/// sends a PTT-set command to key or unkey the transmitter. No mode-set or other
/// rig-altering command beyond frequency-set and PTT-set is defined here.
/// </para>
///
/// <para>
/// All access to a given <see cref="IRadioConnection"/> instance MUST be serialised
/// by its owner (see <c>CatPollingService</c>'s wire-serialisation gate, FR-056) —
/// the implementations in <c>OpenWSFZ.Rig</c> assume request/response calls never
/// overlap on the underlying transport.
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
    /// Commands the rig to key (<paramref name="transmitting"/> = <c>true</c>) or unkey
    /// (<paramref name="transmitting"/> = <c>false</c>) the transmitter (FR-056).
    /// This is a fire-and-forget set: the method sends the command — and, where the
    /// underlying protocol provides one, reads and validates its acknowledgement — but
    /// does not poll back to confirm the rig actually changed PTT state.
    /// <see cref="IRadioConnection"/> defines no PTT-state query.
    /// </summary>
    /// <param name="transmitting"><c>true</c> to key PTT; <c>false</c> to unkey it.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    Task SetPttAsync(bool transmitting, CancellationToken cancellationToken = default);

    /// <summary>
    /// <c>true</c> after a successful <see cref="ConnectAsync"/> and before
    /// <see cref="DisconnectAsync"/> is called.
    /// </summary>
    bool IsConnected { get; }
}
