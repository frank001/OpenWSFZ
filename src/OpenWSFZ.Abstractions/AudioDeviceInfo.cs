namespace OpenWSFZ.Abstractions;

/// <summary>
/// Identifies a single audio capture device available on the host OS.
/// </summary>
/// <param name="Id">OS-specific identifier (e.g. WASAPI device GUID, ALSA hw: string).</param>
/// <param name="Name">Human-readable display name shown in the UI.</param>
public sealed record AudioDeviceInfo(string Id, string Name);
