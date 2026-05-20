namespace OpenWSFZ.Abstractions;

/// <summary>
/// Delivers a continuous stream of 32-bit float mono PCM samples from a
/// named audio capture device. Implemented by platform-specific sources
/// (<c>WasapiAudioSource</c> on Windows, <c>ArecordAudioSource</c> on Linux,
/// <c>SoxAudioSource</c> on macOS).
/// </summary>
public interface IAudioSource : IAsyncDisposable
{
    /// <summary>Sample rate delivered by this source (Hz). Fixed at 12 000 in Phase 4.</summary>
    int SampleRate { get; }

    /// <summary>Channel count. Fixed at 1 (mono) in Phase 4.</summary>
    int ChannelCount { get; }

    /// <summary>
    /// Opens <paramref name="deviceId"/> and yields PCM chunks until
    /// <paramref name="ct"/> is cancelled. Each chunk is a <c>float[]</c>
    /// containing normalised samples in the range [-1.0, +1.0].
    /// Throws <see cref="AudioCaptureException"/> if the device cannot be opened.
    /// </summary>
    IAsyncEnumerable<float[]> CaptureAsync(string deviceId, CancellationToken ct);
}
