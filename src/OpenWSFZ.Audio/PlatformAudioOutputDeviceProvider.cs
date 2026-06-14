using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Logging.Abstractions;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Audio;

/// <summary>
/// Selects the correct <see cref="IAudioOutputDeviceProvider"/> implementation for the
/// current OS at runtime and delegates to it.
/// On Windows, uses <see cref="WasapiAudioOutputDeviceProvider"/> (DataFlow.Render).
/// On Linux and macOS, uses <see cref="SubprocessAudioOutputDeviceProvider"/> (stub — empty list).
/// </summary>
public sealed class PlatformAudioOutputDeviceProvider : IAudioOutputDeviceProvider
{
    private readonly IAudioOutputDeviceProvider _inner;

    public PlatformAudioOutputDeviceProvider(ILoggerFactory? loggerFactory = null)
    {
        _inner = ResolveForCurrentPlatform(loggerFactory);
    }

    public Task<IReadOnlyList<AudioDeviceInfo>> GetDevicesAsync(CancellationToken ct = default)
        => _inner.GetDevicesAsync(ct);

    private static IAudioOutputDeviceProvider ResolveForCurrentPlatform(ILoggerFactory? loggerFactory)
    {
#if WASAPI_SUPPORTED
        if (OperatingSystem.IsWindows())
        {
            var log = loggerFactory?.CreateLogger<WasapiAudioOutputDeviceProvider>()
                      ?? NullLogger<WasapiAudioOutputDeviceProvider>.Instance;
            return new WasapiAudioOutputDeviceProvider(log);
        }
#endif

        // Linux, macOS, and any other platform: stub returns empty list.
        var stubLog = loggerFactory?.CreateLogger<SubprocessAudioOutputDeviceProvider>()
                      ?? NullLogger<SubprocessAudioOutputDeviceProvider>.Instance;
        return new SubprocessAudioOutputDeviceProvider(stubLog);
    }
}
