#if WASAPI_SUPPORTED
using System.Runtime.CompilerServices;
using System.Runtime.Versioning;
using System.Threading.Channels;
using Microsoft.Extensions.Logging;
using NAudio.CoreAudioApi;
using NAudio.CoreAudioApi.Interfaces;
using NAudio.Wave;
using NAudio.Wave.SampleProviders;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Audio;

/// <summary>
/// Windows WASAPI audio capture source. Opens a device on a dedicated COM STA
/// thread and pipes raw PCM through a NAudio resampling pipeline to produce
/// 12 000 Hz mono float samples.
/// </summary>
[SupportedOSPlatform("windows")]
internal sealed class WasapiAudioSource : IAudioSource
{
    private readonly ILogger<WasapiAudioSource>? _logger;

    public WasapiAudioSource(ILogger<WasapiAudioSource>? logger = null)
    {
        _logger = logger;
    }

    public int SampleRate   => 12_000;
    public int ChannelCount => 1;

    public async IAsyncEnumerable<float[]> CaptureAsync(
        string deviceId,
        [EnumeratorCancellation] CancellationToken ct)
    {
        // Inner channel bridges the WASAPI capture thread to the async enumerable.
        var innerChannel = Channel.CreateBounded<float[]>(
            new BoundedChannelOptions(32)
            {
                FullMode     = BoundedChannelFullMode.DropOldest,
                SingleWriter = true,
                SingleReader = true,
            });

        Exception?  setupException = null;
        var         setupTcs       = new TaskCompletionSource(
            TaskCreationOptions.RunContinuationsAsynchronously);

        // staCts is cancelled either when ct is cancelled (normal StopAsync path)
        // or when RecordingStopped fires for any reason (unexpected stop path).
        // The STA thread blocks on staCts.Token so both signals unblock it promptly.
        // Without this, an unexpected RecordingStopped leaves the STA thread blocked
        // on ct indefinitely, causing await staTask to hang forever (B10).
        using var staCts = CancellationTokenSource.CreateLinkedTokenSource(ct);

        // The STA thread owns all COM objects for the entire capture session.
        // It blocks on staCts until cancellation or an unexpected stop, then cleans up.
        var staTask = StaThread.Run<bool>(() =>
        {
            WasapiCapture?       capture        = null;
            AudioSessionControl? sessionControl = null;   // B15: outer scope keeps COM ref alive

            try
            {
                using var enumerator = new MMDeviceEnumerator();

                MMDevice device;
                try
                {
                    device = enumerator.GetDevice(deviceId);
                }
                catch (Exception ex)
                {
                    throw new AudioCaptureException(deviceId, ex.Message);
                }

                capture = new WasapiCapture(device, useEventSync: false);

                // L-1 (DIAG): log device identity and negotiated WaveFormat so any
                // format/channel mismatch is immediately visible.
                _logger?.LogInformation(
                    "WASAPI device opened: '{DeviceId}' ('{FriendlyName}') — " +
                    "WaveFormat={SampleRate} Hz, {BitsPerSample}-bit, {Channels} ch, Encoding={Encoding}",
                    deviceId,
                    device.FriendlyName,
                    capture.WaveFormat.SampleRate,
                    capture.WaveFormat.BitsPerSample,
                    capture.WaveFormat.Channels,
                    capture.WaveFormat.Encoding);

                // D3 (DIAG): log sub-format GUID for Extensible format.
                // {00000001-...} = PCM, {00000003-...} = IEEE float.
                // Any other GUID indicates a compressed format that the NAudio
                // pipeline may not handle correctly.
                if (capture.WaveFormat is WaveFormatExtensible ext)
                {
                    _logger?.LogInformation(
                        "WASAPI sub-format on '{DeviceId}': {SubFormat}",
                        deviceId, ext.SubFormat);
                }

                // ── NAudio resampling pipeline ────────────────────────────────
                var buffer = new BufferedWaveProvider(capture.WaveFormat)
                {
                    BufferDuration          = TimeSpan.FromSeconds(5),
                    DiscardOnBufferOverflow = true,
                };

                ISampleProvider samples = buffer.ToSampleProvider();

                // D6: LeftChannelSampleProvider replaces StereoToMonoSampleProvider.
                // StereoToMonoSampleProvider averages (L + R) / 2 — when the device
                // delivers a differential (balanced) signal (L = −R), every output
                // sample is zero regardless of signal amplitude. Extracting the left
                // channel alone carries the full signal without phase cancellation.
                if (capture.WaveFormat.Channels == 2)
                    samples = new LeftChannelSampleProvider(samples);

                var resampler = new WdlResamplingSampleProvider(samples, 12_000);

                // L-2 (DIAG): confirm which resampling path was taken and the target rate.
                _logger?.LogInformation(
                    "Resampling pipeline ready on '{DeviceId}': " +
                    "channelMode={ChannelMode}, inputRate={InputRate} Hz → 12000 Hz",
                    deviceId,
                    capture.WaveFormat.Channels == 2 ? "stereo→mono(left)" : "mono",
                    capture.WaveFormat.SampleRate);

                // DataAvailable fires on the WASAPI capture thread (~50 Hz).
                capture.DataAvailable += (_, e) =>
                {
                    try
                    {
                        buffer.AddSamples(e.Buffer, 0, e.BytesRecorded);

                        // Warn if the buffer is near-full (> 4 s). This indicates the consumer
                        // is stalling and new audio will be silently discarded.
                        if (buffer.BufferedDuration.TotalMilliseconds > 4000)
                        {
                            _logger?.LogWarning(
                                "BufferedWaveProvider near full on '{DeviceId}': " +
                                "{BufferedMs:F0} ms — consumer may be stalled.",
                                deviceId,
                                buffer.BufferedDuration.TotalMilliseconds);
                        }

                        // Drain the resampler in 2 048-sample chunks.
                        var outBuf = new float[2048];
                        int read;
                        while ((read = resampler.Read(outBuf, 0, outBuf.Length)) > 0)
                        {
                            var chunk = new float[read];
                            outBuf.AsSpan(0, read).CopyTo(chunk);

                            if (!innerChannel.Writer.TryWrite(chunk))
                            {
                                _logger?.LogWarning(
                                    "Audio chunk dropped on '{DeviceId}' ({Samples} samples) — " +
                                    "consumer is not keeping up.",
                                    deviceId,
                                    chunk.Length);
                            }
                        }
                    }
                    catch (Exception ex)
                    {
                        innerChannel.Writer.TryComplete(ex);
                        try { staCts.Cancel(); } catch (ObjectDisposedException) { }
                    }
                };

                capture.RecordingStopped += (_, e) =>
                {
                    if (e.Exception is not null)
                    {
                        _logger?.LogError(e.Exception,
                            "RecordingStopped with error on '{DeviceId}': {ExType} — {ExMessage}",
                            deviceId, e.Exception.GetType().Name, e.Exception.Message);
                        innerChannel.Writer.TryComplete(e.Exception);
                    }
                    else
                    {
                        _logger?.LogInformation(
                            "RecordingStopped (graceful) on '{DeviceId}'.", deviceId);
                        innerChannel.Writer.TryComplete();
                    }

                    // Wake the STA thread so staTask completes promptly.
                    // B12: Guard with catch(ObjectDisposedException) — WASAPI fires
                    // RecordingStopped a second time from capture.StopRecording() in the
                    // finally block, which races with staCts disposal at the end of
                    // CaptureAsync.  The second call is harmless; the STA is already
                    // unblocking.
                    try { staCts.Cancel(); }
                    catch (ObjectDisposedException) { /* staCts already disposed — STA is unblocking */ }
                };

                _logger?.LogDebug("Starting capture on '{DeviceId}'.", deviceId);
                capture.StartRecording();
                _logger?.LogDebug("Capture started on '{DeviceId}'.", deviceId);

                // B11: Subscribe to WASAPI audio session events so Windows-initiated
                // session termination is detected even if NAudio's RecordingStopped
                // does not fire.  Covers: default-device switches, exclusive-mode
                // takeover, audio engine restarts, driver-level format changes.
                // Best-effort: failure to register must not prevent capture.
                // sessionControl declared in outer scope (B15) so the GC cannot
                // collect it while the STA thread is blocked on WaitOne().
                try
                {
                    sessionControl = device.AudioSessionManager.AudioSessionControl;
                    sessionControl.RegisterEventClient(
                        new WasapiSessionEventClient(innerChannel, staCts, deviceId, _logger));
                }
                catch (Exception ex)
                {
                    // B16: Log so the operator can tell whether B11 is working.
                    // Do NOT prevent capture — registration is best-effort.
                    _logger?.LogWarning(ex,
                        "WASAPI session event registration failed on device '{DeviceId}'; " +
                        "session-disconnect events will not be detected. " +
                        "Capture continues without event-driven termination detection.",
                        deviceId);
                    sessionControl = null;
                }

                // Signal that setup succeeded so the async caller can start reading.
                setupTcs.SetResult();

                // Block the STA thread alive while the session is running.
                // Uses staCts.Token so RecordingStopped can also unblock it (B10).
                staCts.Token.WaitHandle.WaitOne();

                _logger?.LogInformation(
                    "Capture session unblocked on '{DeviceId}' " +
                    "(ct={CtCancelled}, staCts={StaCancelled}).",
                    deviceId,
                    ct.IsCancellationRequested,
                    staCts.IsCancellationRequested);
            }
            catch (Exception ex)
            {
                setupException = ex;
                setupTcs.TrySetResult();
                innerChannel.Writer.TryComplete(ex);
            }
            finally
            {
                _logger?.LogInformation(
                    "Audio capture cleanup starting on '{DeviceId}'.", deviceId);

                // Dispose sessionControl before capture: cleanly unregisters the
                // WASAPI session event client before tearing down the capture session.
                if (sessionControl is not null)
                {
                    try { sessionControl.Dispose(); } catch { }
                    sessionControl = null;
                }

                // Stop and dispose on the STA thread that owns the COM objects.
                if (capture is not null)
                {
                    // S2: some drivers (e.g. Jabra EVOLVE LINK USB) take 10+ seconds to
                    // acknowledge StopRecording().  Running it on a background thread with
                    // a 3-second timeout lets the STA finally block complete promptly.  If
                    // the thread-pool thread violates the STA COM apartment rule the resulting
                    // COMException is swallowed — acceptable during shutdown since the process
                    // is exiting and the device is being abandoned regardless.
                    _logger?.LogInformation("Stopping capture on '{DeviceId}'.", deviceId);
                    var stopTask = Task.Run(() => { try { capture.StopRecording(); } catch { } });
                    if (stopTask.Wait(TimeSpan.FromSeconds(3)))
                    {
                        // P2: same treatment as StopRecording — some drivers hang in Dispose() too.
                        var disposeTask = Task.Run(() => { try { capture.Dispose(); } catch { } });
                        if (!disposeTask.Wait(TimeSpan.FromSeconds(3)))
                            _logger?.LogWarning(
                                "capture.Dispose() timed out after 3 s on '{DeviceId}' " +
                                "— abandoning device handle; OS will reclaim on process exit.", deviceId);
                    }
                    else
                    {
                        // StopRecording timed out — skip Dispose (it would also hang).
                        // The device handle is abandoned; the OS reclaims it on process exit.
                        _logger?.LogWarning(
                            "capture.StopRecording() timed out after 3 s on '{DeviceId}' " +
                            "— abandoning device handle; OS will reclaim on process exit.", deviceId);
                    }
                }

                _logger?.LogInformation(
                    "Audio capture cleanup complete on '{DeviceId}'.", deviceId);
            }

            return true;
        });

        // Wait for setup to complete (device open + recording started).
        await setupTcs.Task;

        if (setupException is AudioCaptureException)
            throw setupException;

        if (setupException is not null)
            throw new AudioCaptureException(deviceId, setupException.Message);

        try
        {
            await foreach (var chunk in innerChannel.Reader.ReadAllAsync(ct))
                yield return chunk;
        }
        finally
        {
            // If the caller abandons the iterator without cancelling ct,
            // ensure the STA thread still terminates eventually.
            try { await staTask; } catch { }
        }
    }

    public ValueTask DisposeAsync() => ValueTask.CompletedTask;

    // ── D6: Left-channel stereo-to-mono extractor ────────────────────────────

    /// <summary>
    /// Extracts the left channel from a stereo IEEE float sample stream.
    /// Used instead of <see cref="StereoToMonoSampleProvider"/> when the audio device
    /// delivers a differential (balanced) signal where L = −R: averaging both channels
    /// produces silence, but either channel alone carries the full signal.
    /// </summary>
    private sealed class LeftChannelSampleProvider : ISampleProvider
    {
        private readonly ISampleProvider _source;
        private float[]                  _stereoBuffer = new float[4096];

        public LeftChannelSampleProvider(ISampleProvider source)
        {
            if (source.WaveFormat.Channels != 2)
                throw new ArgumentException("Source must be stereo.", nameof(source));
            _source    = source;
            WaveFormat = WaveFormat.CreateIeeeFloatWaveFormat(
                source.WaveFormat.SampleRate, channels: 1);
        }

        public WaveFormat WaveFormat { get; }

        public int Read(float[] buffer, int offset, int count)
        {
            int stereoCount = count * 2;
            if (_stereoBuffer.Length < stereoCount)
                _stereoBuffer = new float[stereoCount];

            int read = _source.Read(_stereoBuffer, 0, stereoCount);
            int mono = read / 2;
            for (int i = 0; i < mono; i++)
                buffer[offset + i] = _stereoBuffer[i * 2]; // left channel (index 0 of each interleaved pair)
            return mono;
        }
    }

    // ── B11: WASAPI session event listener ────────────────────────────────────
    // Receives IAudioSessionEvents notifications from the Windows audio engine
    // on a COM event thread (Thread C in the thread-model reference).
    // When Windows terminates the session (device change, exclusive-mode takeover,
    // audio engine restart, format change), OnSessionDisconnected fires and we
    // complete the innerChannel so CaptureAsync exits and CaptureManager raises
    // CaptureFailed — even if NAudio's RecordingStopped never fires.
    private sealed class WasapiSessionEventClient : IAudioSessionEventsHandler
    {
        private readonly Channel<float[]>             _channel;
        private readonly CancellationTokenSource      _staCts;
        private readonly string                       _deviceId;
        private readonly ILogger<WasapiAudioSource>?  _logger;

        public WasapiSessionEventClient(
            Channel<float[]>            channel,
            CancellationTokenSource     staCts,
            string                      deviceId,
            ILogger<WasapiAudioSource>? logger)
        {
            _channel  = channel;
            _staCts   = staCts;
            _deviceId = deviceId;
            _logger   = logger;
        }

        public void OnSessionDisconnected(AudioSessionDisconnectReason disconnectReason)
        {
            _logger?.LogError(
                "WASAPI session disconnected on '{DeviceId}': {Reason}",
                _deviceId, disconnectReason);

            // Windows terminated the session: complete the channel with a descriptive
            // exception so CaptureManager surfaces the event via CaptureFailed, and
            // FR-021 logs it at Error level.
            var ex = new AudioCaptureException(
                _deviceId,
                $"WASAPI audio session disconnected: {disconnectReason}");

            _channel.Writer.TryComplete(ex);
            try { _staCts.Cancel(); } catch (ObjectDisposedException) { }
        }

        // B17: Handle session expiry. AudioSessionStateExpired fires when the session
        // is being destroyed normally (e.g. device removed quietly, format change).
        // On some drivers this fires without a corresponding OnSessionDisconnected.
        public void OnStateChanged(AudioSessionState state)
        {
            if (state != AudioSessionState.AudioSessionStateExpired) return;

            _logger?.LogWarning(
                "WASAPI audio session expired on '{DeviceId}'.", _deviceId);

            var ex = new AudioCaptureException(
                _deviceId,
                "WASAPI audio session expired (OnStateChanged: Expired).");

            _channel.Writer.TryComplete(ex);
            try { _staCts.Cancel(); } catch (ObjectDisposedException) { }
        }

        public void OnVolumeChanged(float volume, bool isMuted) { }
        public void OnDisplayNameChanged(string displayName)                                         { }
        public void OnIconPathChanged(string iconPath)                                               { }
        public void OnChannelVolumeChanged(uint channelCount, IntPtr newVolumes, uint channelIndex)  { }
        public void OnGroupingParamChanged(ref Guid groupingId)                                      { }
    }
}
#endif
