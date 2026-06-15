#if WASAPI_SUPPORTED
using System.Runtime.Versioning;
using Microsoft.Extensions.Logging;
using NAudio.CoreAudioApi;
using NAudio.Wave;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Audio;

namespace OpenWSFZ.Daemon;

/// <summary>
/// Windows WASAPI implementation of <see cref="IPttController"/>.
///
/// <para>
/// PTT is implemented entirely via audio output: <see cref="KeyDownAsync"/> opens the
/// configured render (output) device via <c>WasapiOut</c>, loads the pre-synthesised
/// TX audio buffer, and starts playback.  <see cref="KeyUpAsync"/> stops playback and
/// releases the device handle.  No serial-port or CAT keying is used.
/// </para>
///
/// <para>
/// Call <see cref="LoadAudio"/> with the synthesised <c>float[]</c> buffer before calling
/// <see cref="KeyDownAsync"/>.  Calling <see cref="KeyDownAsync"/> without a prior
/// <see cref="LoadAudio"/> throws <see cref="InvalidOperationException"/>.
/// </para>
///
/// <para>Registered as a singleton in DI by <c>Program.cs</c>.</para>
/// </summary>
[SupportedOSPlatform("windows")]
public sealed class AudioOnlyPttController : IPttController
{
    private readonly IConfigStore                        _configStore;
    private readonly ILogger<AudioOnlyPttController>     _logger;

    // Internal seam — replaced in tests with a delegate that does not open WASAPI.
    // Production constructor leaves this null, triggering the real WASAPI path.
    private readonly Func<float[], string?, CancellationToken, Task>? _playerOverride;

    // The pre-loaded audio buffer.  Null until LoadAudio is called.
    private float[]? _audioSamples;

    // The active WasapiOut instance (non-null only while transmission is in progress).
    private WasapiOut? _activePlayer;
    private readonly SemaphoreSlim _playerLock = new(1, 1);

    // ── Constructors ─────────────────────────────────────────────────────────

    /// <summary>Production constructor — uses real WASAPI output.</summary>
    public AudioOnlyPttController(
        IConfigStore                    configStore,
        ILogger<AudioOnlyPttController> logger)
    {
        _configStore    = configStore;
        _logger         = logger;
        _playerOverride = null;
    }

    /// <summary>
    /// Internal test constructor — injects a delegate in place of the real WASAPI path.
    /// The delegate receives the audio samples and configured output device ID,
    /// returning a Task that completes when "playback" is done.
    /// </summary>
    internal AudioOnlyPttController(
        IConfigStore                                        configStore,
        ILogger<AudioOnlyPttController>                     logger,
        Func<float[], string?, CancellationToken, Task>     playerOverride)
    {
        _configStore    = configStore;
        _logger         = logger;
        _playerOverride = playerOverride;
    }

    // ── Public API ────────────────────────────────────────────────────────────

    /// <summary>
    /// Sets the TX audio buffer that will be played on the next <see cref="KeyDownAsync"/> call.
    /// Must be called before <see cref="KeyDownAsync"/>.
    /// </summary>
    /// <param name="samples">
    /// Mono float32 PCM at 48 000 Hz, amplitude in [−0.5, +0.5].
    /// </param>
    public void LoadAudio(float[] samples)
    {
        ArgumentNullException.ThrowIfNull(samples);
        _audioSamples = samples;
        _logger.LogDebug("TX audio loaded: {Samples} samples ({DurationMs:F0} ms).",
            samples.Length,
            samples.Length * 1000.0 / 48_000);
    }

    /// <summary>
    /// Begins transmission — starts playback of the pre-loaded audio buffer on the
    /// configured WASAPI output device.  Returns when playback completes (or is cancelled).
    /// </summary>
    /// <exception cref="InvalidOperationException">
    /// Thrown when <see cref="LoadAudio"/> has not been called before this method.
    /// </exception>
    public async Task KeyDownAsync(CancellationToken ct = default)
    {
        var samples = _audioSamples
            ?? throw new InvalidOperationException(
                "LoadAudio must be called before KeyDownAsync. " +
                "Call LoadAudio with the synthesised TX audio buffer first.");

        var deviceId = _configStore.Current.AudioOutputDeviceId;

        _logger.LogInformation("TX KeyDown — starting playback on device '{DeviceId}' " +
            "({Samples} samples).", deviceId ?? "(default)", samples.Length);

        // Test seam: use the override delegate if injected (unit tests).
        if (_playerOverride is not null)
        {
            await _playerOverride(samples, deviceId, ct).ConfigureAwait(false);
            return;
        }

        await PlayWasapiAsync(samples, deviceId, ct).ConfigureAwait(false);

        _logger.LogInformation("TX KeyDown — playback completed.");
    }

    /// <summary>
    /// Ends transmission — stops WASAPI playback immediately and releases the device handle.
    /// Safe to call when no transmission is in progress.
    /// </summary>
    public async Task KeyUpAsync(CancellationToken ct = default)
    {
        _logger.LogInformation("TX KeyUp — stopping playback.");

        await _playerLock.WaitAsync(ct).ConfigureAwait(false);
        try
        {
            StopAndReleasePlayer();
        }
        finally
        {
            _playerLock.Release();
        }
    }

    /// <inheritdoc/>
    public async ValueTask DisposeAsync()
    {
        await _playerLock.WaitAsync().ConfigureAwait(false);
        try
        {
            StopAndReleasePlayer();
        }
        finally
        {
            _playerLock.Release();
            _playerLock.Dispose();
        }
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private async Task PlayWasapiAsync(float[] samples, string? deviceId, CancellationToken ct)
    {
        var tcs = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);

        await _playerLock.WaitAsync(ct).ConfigureAwait(false);
        try
        {
            // Obtain the output device.
            using var enumerator = new MMDeviceEnumerator();
            MMDevice device;
            if (!string.IsNullOrEmpty(deviceId))
            {
                device = enumerator.GetDevice(deviceId);
                _logger.LogDebug("TX: opened output device '{DeviceId}'.", deviceId);
            }
            else
            {
                device = enumerator.GetDefaultAudioEndpoint(DataFlow.Render, Role.Multimedia);
                _logger.LogDebug("TX: using default output device.");
            }

            var waveFormat  = WaveFormat.CreateIeeeFloatWaveFormat(48_000, channels: 1);
            var provider    = new FloatArraySampleProvider(samples, waveFormat);

            _activePlayer = new WasapiOut(device, AudioClientShareMode.Shared,
                useEventSync: true, latency: 200);

            _activePlayer.PlaybackStopped += (_, e) =>
            {
                if (e.Exception is not null)
                    tcs.TrySetException(e.Exception);
                else
                    tcs.TrySetResult();
            };

            _activePlayer.Init(provider);
            _activePlayer.Play();
        }
        finally
        {
            _playerLock.Release();
        }

        // Wait outside the lock so KeyUpAsync can acquire it to stop playback.
        // Register callback is synchronous — await is not available, so KeyUpAsync is
        // fire-and-forget.  Observe the task to prevent an unhandled exception on the
        // finaliser thread; StopAndReleasePlayer already catches and logs internally so
        // a fault here indicates a genuinely unexpected failure.
        using var reg = ct.Register(() =>
        {
            KeyUpAsync(CancellationToken.None).ContinueWith(
                t => _logger.LogWarning(t.Exception, "KeyUpAsync threw during cancellation — ignoring."),
                CancellationToken.None,
                TaskContinuationOptions.OnlyOnFaulted,
                TaskScheduler.Default);
            tcs.TrySetCanceled();
        });

        try
        {
            await tcs.Task.ConfigureAwait(false);
        }
        catch (TaskCanceledException)
        {
            // Cancellation is expected; caller will handle it.
            throw new OperationCanceledException(ct);
        }
    }

    private void StopAndReleasePlayer()
    {
        if (_activePlayer is null) return;

        try
        {
            _activePlayer.Stop();
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "WasapiOut.Stop() threw during TX release — ignoring.");
        }

        try
        {
            _activePlayer.Dispose();
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "WasapiOut.Dispose() threw during TX release — ignoring.");
        }

        _activePlayer = null;
    }

    // ── Inner helper: ISampleProvider over float[] ────────────────────────────

    /// <summary>
    /// Thin <see cref="ISampleProvider"/> wrapper over a pre-filled <c>float[]</c> buffer.
    /// Used to feed the synthesised TX audio to <c>WasapiOut.Init</c>.
    /// </summary>
    private sealed class FloatArraySampleProvider : ISampleProvider
    {
        private readonly float[] _samples;
        private          int     _position;

        public FloatArraySampleProvider(float[] samples, WaveFormat waveFormat)
        {
            _samples   = samples;
            WaveFormat = waveFormat;
        }

        public WaveFormat WaveFormat { get; }

        public int Read(float[] buffer, int offset, int count)
        {
            int available = _samples.Length - _position;
            int toCopy    = Math.Min(available, count);
            if (toCopy <= 0) return 0;
            Buffer.BlockCopy(_samples, _position * sizeof(float), buffer, offset * sizeof(float), toCopy * sizeof(float));
            _position += toCopy;
            return toCopy;
        }
    }
}
#endif
