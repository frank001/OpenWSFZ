using System.Runtime.InteropServices;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Audio;

/// <summary>
/// Selects the correct <see cref="IAudioDeviceProvider"/> implementation for the
/// current OS at runtime and delegates to it. Registered as the singleton
/// <see cref="IAudioDeviceProvider"/> in the DI container.
/// </summary>
public sealed class PlatformAudioDeviceProvider : IAudioDeviceProvider
{
    private readonly IAudioDeviceProvider _inner;

    public PlatformAudioDeviceProvider()
    {
        _inner = ResolveForCurrentPlatform();
    }

    public Task<IReadOnlyList<AudioDeviceInfo>> GetDevicesAsync(CancellationToken ct = default)
        => _inner.GetDevicesAsync(ct);

    private static IAudioDeviceProvider ResolveForCurrentPlatform()
    {
        if (OperatingSystem.IsWindows())
            return new WasapiAudioDeviceProvider();

        if (OperatingSystem.IsLinux())
            return SubprocessAudioDeviceProvider.ForLinux();

        if (OperatingSystem.IsMacOS())
            return SubprocessAudioDeviceProvider.ForMacOs();

        // Unknown platform → safe no-op.
        return new NullAudioDeviceProvider();
    }
}

/// <summary>Safe fallback for unsupported platforms — always returns an empty list.</summary>
internal sealed class NullAudioDeviceProvider : IAudioDeviceProvider
{
    public Task<IReadOnlyList<AudioDeviceInfo>> GetDevicesAsync(CancellationToken ct = default)
        => Task.FromResult<IReadOnlyList<AudioDeviceInfo>>([]);
}
