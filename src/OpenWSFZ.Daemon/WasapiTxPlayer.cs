#if WASAPI_SUPPORTED
using System.Runtime.Versioning;
using Microsoft.Extensions.Logging;
using NAudio.CoreAudioApi;
using NAudio.Wave;

namespace OpenWSFZ.Daemon;

/// <summary>
/// Shared WASAPI device-open/play/stop/dispose helper (cat-tx-ptt, design.md Decision 3),
/// extracted from <see cref="AudioOnlyPttController"/> so <c>CatPttController</c> and
/// <c>SerialRtsDtrPttController</c> can play TX audio without each duplicating this
/// ~150-line surface — and its finally/dispose bug surface — a second and third time.
///
/// <para>
/// <see cref="AudioOnlyPttController"/>'s public behaviour, timing, and requirements are
/// unchanged by this extraction: every existing scenario in the <c>ft8-tx</c> spec for
/// <c>AudioOnlyPttController</c> continues to hold verbatim.
/// </para>
/// </summary>
[SupportedOSPlatform("windows")]
internal sealed class WasapiTxPlayer : IAsyncDisposable
{
    private readonly ILogger        _logger;
    private readonly SemaphoreSlim  _playerLock = new(1, 1);
    private          WasapiOut?     _activePlayer;

    // Atomically taken by DisposeAsync so a second call sees a non-zero value and
    // exits immediately, rather than re-entering a disposed _playerLock and throwing
    // ObjectDisposedException — same double-dispose guard pattern as CatPollingService
    // (see its own DisposeAsync remarks). Fixes a genuine pre-existing defect (task 7.3):
    // AudioOnlyPttControllerTests.DisposeAsync_CalledTwice_SecondCallIsNoOp had never
    // actually executed before this change (the test project was missing the
    // WASAPI_SUPPORTED conditional-compilation symbol its host class requires — fixed
    // alongside this) and would have failed the moment it finally ran.
    private int _disposed;

    public WasapiTxPlayer(ILogger logger) => _logger = logger;

    /// <summary>
    /// Opens the given (or default) render device and plays <paramref name="samples"/>,
    /// returning when playback completes. Throws <see cref="OperationCanceledException"/>
    /// (carrying <paramref name="ct"/>) if <paramref name="ct"/> is cancelled before
    /// playback finishes, having first stopped and released the device.
    /// </summary>
    public async Task PlayAsync(float[] samples, string? deviceId, CancellationToken ct)
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

        // Wait outside the lock so StopAsync can acquire it to stop playback.
        // Register callback is synchronous — await is not available, so the stop here is
        // fire-and-forget. Observe the task to prevent an unhandled exception on the
        // finaliser thread; StopAndReleasePlayerCore already catches and logs internally
        // so a fault here indicates a genuinely unexpected failure.
        using var reg = ct.Register(() =>
        {
            StopAsync(CancellationToken.None).ContinueWith(
                t => _logger.LogWarning(t.Exception, "StopAsync threw during cancellation — ignoring."),
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

    /// <summary>
    /// Stops any in-progress playback and releases the device handle. Safe to call when
    /// no transmission is in progress — treated as a no-op.
    /// </summary>
    public async Task StopAsync(CancellationToken ct = default)
    {
        await _playerLock.WaitAsync(ct).ConfigureAwait(false);
        try
        {
            StopAndReleasePlayerCore();
        }
        finally
        {
            _playerLock.Release();
        }
    }

    /// <summary>
    /// Stops any in-progress playback, releases the device handle, and disposes the
    /// internal synchronisation primitive. Idempotent — a second call is a no-op.
    /// </summary>
    public async ValueTask DisposeAsync()
    {
        if (Interlocked.Exchange(ref _disposed, 1) != 0) return; // already disposed

        await _playerLock.WaitAsync().ConfigureAwait(false);
        try
        {
            StopAndReleasePlayerCore();
        }
        finally
        {
            _playerLock.Release();
            _playerLock.Dispose();
        }
    }

    private void StopAndReleasePlayerCore()
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
