#if WASAPI_SUPPORTED
using System.Runtime.Versioning;
using Microsoft.Extensions.Logging;
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

    // Shared WASAPI device-open/play/stop/dispose helper (cat-tx-ptt, design.md
    // Decision 3). Only ever touched via the real (non-override) KeyDownAsync path;
    // unit tests always supply _playerOverride, so this instance's WasapiOut is never
    // opened during tests — KeyUpAsync/DisposeAsync remain graceful no-ops for them.
    private readonly WasapiTxPlayer _player;

    // ── Constructors ─────────────────────────────────────────────────────────

    /// <summary>Production constructor — uses real WASAPI output.</summary>
    public AudioOnlyPttController(
        IConfigStore                    configStore,
        ILogger<AudioOnlyPttController> logger)
    {
        _configStore    = configStore;
        _logger         = logger;
        _playerOverride = null;
        _player         = new WasapiTxPlayer(logger);
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
        _player         = new WasapiTxPlayer(logger);
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

        await _player.PlayAsync(samples, deviceId, ct).ConfigureAwait(false);

        _logger.LogInformation("TX KeyDown — playback completed.");
    }

    /// <summary>
    /// Ends transmission — stops WASAPI playback immediately and releases the device handle.
    /// Safe to call when no transmission is in progress.
    /// </summary>
    public async Task KeyUpAsync(CancellationToken ct = default)
    {
        _logger.LogInformation("TX KeyUp — stopping playback.");
        await _player.StopAsync(ct).ConfigureAwait(false);
    }

    /// <inheritdoc/>
    public async ValueTask DisposeAsync() => await _player.DisposeAsync().ConfigureAwait(false);
}
#endif
