namespace OpenWSFZ.Abstractions;

/// <summary>
/// Fire-and-forget rig-tuning capability exposed by the CAT subsystem (FR-045).
/// Implemented by <c>CatPollingService</c>; injected into the web layer via DI
/// so that <c>POST /api/v1/tune</c> can command the rig without depending on
/// the Daemon assembly.
/// </summary>
public interface ICatTuner
{
    /// <summary>
    /// Commands the active rig connection to tune VFO-A to
    /// <paramref name="frequencyMHz"/>. Updates <see cref="ICatState.DialFrequencyMHz"/>
    /// optimistically before the next poll cycle confirms the new value.
    /// </summary>
    /// <exception cref="InvalidOperationException">
    /// Thrown when no active rig connection is available (CAT not yet connected).
    /// </exception>
    /// <exception cref="Exception">
    /// Re-throws any exception raised by the underlying
    /// <see cref="IRadioConnection.SetDialFrequencyMhzAsync"/> implementation
    /// (e.g. serial port I/O errors, TCP send failures).
    /// </exception>
    Task SetDialFrequencyAsync(double frequencyMHz, CancellationToken cancellationToken = default);
}
