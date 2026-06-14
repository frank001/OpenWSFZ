using System.Runtime.InteropServices;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Audio;

/// <summary>
/// Stub <see cref="IAudioOutputDeviceProvider"/> for Linux and macOS.
/// Returns an empty list and logs a single Debug-level message indicating that
/// output device enumeration is not yet supported on the current platform.
/// TX audio routing is currently Windows-only; this stub satisfies the
/// platform-provider contract without throwing.
/// </summary>
internal sealed class SubprocessAudioOutputDeviceProvider : IAudioOutputDeviceProvider
{
    private readonly ILogger<SubprocessAudioOutputDeviceProvider> _log;

    public SubprocessAudioOutputDeviceProvider(ILogger<SubprocessAudioOutputDeviceProvider> log)
        => _log = log;

    public Task<IReadOnlyList<AudioDeviceInfo>> GetDevicesAsync(CancellationToken ct = default)
    {
        _log.LogDebug(
            "Output device enumeration is not yet implemented on this platform ({OS}). Returning empty list.",
            RuntimeInformation.OSDescription);
        return Task.FromResult<IReadOnlyList<AudioDeviceInfo>>([]);
    }
}
