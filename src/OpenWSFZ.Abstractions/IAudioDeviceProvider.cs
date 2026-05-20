namespace OpenWSFZ.Abstractions;

/// <summary>
/// Enumerates audio capture devices available on the host OS.
/// Implementations are platform-specific; see <c>OpenWSFZ.Audio</c>.
/// Implementations MUST return an empty list — never throw — when no devices
/// are found or the underlying OS mechanism is unavailable.
/// </summary>
public interface IAudioDeviceProvider
{
    /// <summary>
    /// Returns all available audio capture devices.
    /// Never throws; returns an empty list on any enumeration failure.
    /// </summary>
    Task<IReadOnlyList<AudioDeviceInfo>> GetDevicesAsync(CancellationToken ct = default);
}
