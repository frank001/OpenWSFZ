using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Logging.Abstractions;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Audio;

/// <summary>
/// Selects the correct <see cref="IAudioDeviceProvider"/> implementation for the
/// current OS at runtime and delegates to it.
/// </summary>
public sealed class PlatformAudioDeviceProvider : IAudioDeviceProvider
{
    private readonly IAudioDeviceProvider _inner;

    public PlatformAudioDeviceProvider(ILoggerFactory? loggerFactory = null)
    {
        _inner = ResolveForCurrentPlatform(loggerFactory);
    }

    public Task<IReadOnlyList<AudioDeviceInfo>> GetDevicesAsync(CancellationToken ct = default)
        => _inner.GetDevicesAsync(ct);

    private static IAudioDeviceProvider ResolveForCurrentPlatform(ILoggerFactory? loggerFactory)
    {
#if WASAPI_SUPPORTED
        if (OperatingSystem.IsWindows())
        {
            var log = loggerFactory?.CreateLogger<WasapiAudioDeviceProvider>()
                      ?? NullLogger<WasapiAudioDeviceProvider>.Instance;
            return new WasapiAudioDeviceProvider(log);
        }
#endif

        if (OperatingSystem.IsLinux())
            return SubprocessAudioDeviceProvider.ForLinux();

        if (OperatingSystem.IsMacOS())
            return SubprocessAudioDeviceProvider.ForMacOs();

        return new NullAudioDeviceProvider();
    }
}

/// <summary>Safe fallback for unsupported platforms — always returns an empty list.</summary>
internal sealed class NullAudioDeviceProvider : IAudioDeviceProvider
{
    public Task<IReadOnlyList<AudioDeviceInfo>> GetDevicesAsync(CancellationToken ct = default)
        => Task.FromResult<IReadOnlyList<AudioDeviceInfo>>([]);
}
