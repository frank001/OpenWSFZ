namespace OpenWSFZ.Abstractions;

/// <summary>
/// Identifies a single audio capture device available on the host OS.
/// </summary>
/// <param name="Id">OS-specific identifier (e.g. WASAPI device GUID, ALSA hw: string).</param>
/// <param name="Name">Human-readable display name shown in the UI.</param>
/// <param name="Available">
/// Whether capture can be opened on this device right now (FR-073, capture-device-reresolution
/// #187). On Windows, <c>true</c> exactly when the WASAPI endpoint state is Active — a disabled
/// endpoint is still listed, with this <c>false</c>. Providers that list only devices they can
/// currently see (Linux, macOS) report <c>true</c> for everything they return. Defaults to
/// <c>true</c> so every existing call site that doesn't set it explicitly (the Linux/macOS
/// providers, <c>InMemoryAudioDeviceProvider</c>, test fixtures) stays correct as-is.
/// </param>
public sealed record AudioDeviceInfo(string Id, string Name, bool Available = true);
