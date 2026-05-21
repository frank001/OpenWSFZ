using System.Runtime.CompilerServices;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Audio;

/// <summary>
/// Selects the correct <see cref="IAudioSource"/> implementation for the current
/// OS at runtime and delegates to it. Mirrors <see cref="PlatformAudioDeviceProvider"/>.
/// </summary>
public sealed class PlatformAudioSource : IAudioSource
{
    private readonly IAudioSource _inner;

    public PlatformAudioSource()
    {
        _inner = ResolveForCurrentPlatform();
    }

    public int SampleRate   => _inner.SampleRate;
    public int ChannelCount => _inner.ChannelCount;

    public IAsyncEnumerable<float[]> CaptureAsync(string deviceId, CancellationToken ct)
        => _inner.CaptureAsync(deviceId, ct);

    public ValueTask DisposeAsync() => _inner.DisposeAsync();

    private static IAudioSource ResolveForCurrentPlatform()
    {
#if WASAPI_SUPPORTED
        if (OperatingSystem.IsWindows())
            return new WasapiAudioSource();
#endif
        if (OperatingSystem.IsLinux())
            return new ArecordAudioSource();

        if (OperatingSystem.IsMacOS())
            return new SoxAudioSource();

        return new NullAudioSource();
    }
}

/// <summary>
/// Fallback for unsupported platforms — every capture attempt throws
/// <see cref="AudioCaptureException"/> with a clear platform-unsupported message.
/// </summary>
internal sealed class NullAudioSource : IAudioSource
{
    public int SampleRate   => 12_000;
    public int ChannelCount => 1;

    public async IAsyncEnumerable<float[]> CaptureAsync(
        string deviceId,
        [EnumeratorCancellation] CancellationToken ct)
    {
        // Throw via an awaitable so the compiler cannot statically determine that
        // yield break below is unreachable (avoids CS0162 with TreatWarningsAsErrors).
        await Task.FromException(new AudioCaptureException(
            deviceId,
            $"audio capture is not supported on this platform ({Environment.OSVersion.Platform})"));

        yield break;
    }

    public ValueTask DisposeAsync() => ValueTask.CompletedTask;
}
