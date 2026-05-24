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

                // DataAvailable fires on the WASAPI capture thread.
                var dataAvailableFired  = false; // D1 (DIAG)
                var dataAvailableCount  = 0;     // L-3 (DIAG): periodic heartbeat counter
                var zeroOutputCount     = 0;     // D1 (DIAG): consecutive zero-output resampler drain runs
                capture.DataAvailable += (_, e) =>
                {
                    // B13: Wrap the entire handler so any exception (corrupt buffer,
                    // unexpected resampler state, etc.) is surfaced through the channel
                    // rather than propagating into NAudio's internal capture loop where
                    // it may silently terminate the thread without firing RecordingStopped.
                    try
                    {
                        // D1 (DIAG): log the first buffer to confirm WASAPI is actually delivering data.
                        if (!dataAvailableFired)
                        {
                            dataAvailableFired = true;
                            _logger?.LogInformation(
                                "DIAG DataAvailable: first buffer on '{DeviceId}' — " +
                                "BytesRecorded={Bytes}, WaveFormat={Format}",
                                deviceId, e.BytesRecorded, capture.WaveFormat);
                        }

                        // L-3 (DIAG): periodic heartbeat every 100 DataAvailable callbacks.
                        // Must be LogInformation (not LogDebug) — the daemon runs at
                        // Information level, so Debug entries are filtered out entirely.
                        dataAvailableCount++;
                        if (dataAvailableCount % 100 == 0)
                        {
                            _logger?.LogInformation(
                                "DIAG DataAvailable: {Count} buffers on '{DeviceId}' — " +
                                "BytesRecorded={Bytes}, BufferedMs={BufferedMs:F0}",
                                dataAvailableCount,
                                deviceId,
                                e.BytesRecorded,
                                buffer.BufferedDuration.TotalMilliseconds);
                        }

                        // DIAG: check whether WASAPI is delivering non-zero bytes.
                        // If rawHasData=False the device itself is returning silence — OS/hardware cause.
                        // If rawHasData=True but resampler output is zero, the pipeline is the cause.
                        // Short-circuits on first non-zero byte so the scan is inexpensive.
                        var rawHasData = false;
                        for (var i = 0; i < e.BytesRecorded && !rawHasData; i++)
                            rawHasData = e.Buffer[i] != 0;

                        if (dataAvailableCount <= 5 || dataAvailableCount % 100 == 0)
                        {
                            _logger?.LogInformation(
                                "DIAG raw bytes on '{DeviceId}': BytesRecorded={Bytes}, rawHasData={HasData}",
                                deviceId, e.BytesRecorded, rawHasData);
                        }

                        // DIAG: interpret first sample as IEEE 754 float to confirm signal is present.
                        // A non-zero firstSample with rawHasData=True confirms valid audio in the raw bytes.
                        if (e.BytesRecorded >= 4 && (dataAvailableCount <= 5 || dataAvailableCount % 100 == 0))
                        {
                            var firstSample = BitConverter.ToSingle(e.Buffer, 0);
                            _logger?.LogInformation(
                                "DIAG first sample on '{DeviceId}': {FirstSample:G6} (rawHasData={HasData})",
                                deviceId, firstSample, rawHasData);
                        }

                        // DIAG: direct float cast bypassing NAudio pipeline.
                        // maxAbs > 0 confirms valid signal in raw bytes; zeros introduced downstream.
                        // Only run when rawHasData is True to avoid noise from zero-filled buffers.
                        if (rawHasData && (dataAvailableCount <= 5 || dataAvailableCount % 100 == 0))
                        {
                            var span   = e.Buffer.AsSpan(0, e.BytesRecorded);
                            var floats = System.Runtime.InteropServices.MemoryMarshal.Cast<byte, float>(span);
                            var maxAbs = 0f;
                            foreach (var s in floats)
                                if (MathF.Abs(s) > maxAbs) maxAbs = MathF.Abs(s);
                            _logger?.LogInformation(
                                "DIAG direct cast on '{DeviceId}': {FloatCount} floats, maxAbs={MaxAbs:G6}",
                                deviceId, floats.Length, maxAbs);
                        }

                        buffer.AddSamples(e.Buffer, 0, e.BytesRecorded);

                        // L-4 (DIAG): warn when BufferedWaveProvider is near-full (>80% of 5 s).
                        var bufferedMs = buffer.BufferedDuration.TotalMilliseconds;
                        if (bufferedMs > 4000)
                        {
                            _logger?.LogWarning(
                                "DIAG BufferedWaveProvider near full on '{DeviceId}': " +
                                "{BufferedMs:F0} ms buffered — resampler may not be draining fast enough.",
                                deviceId,
                                bufferedMs);
                        }

                        // Drain the resampler in 2 048-sample chunks.
                        var outBuf = new float[2048];
                        int read;
                        while ((read = resampler.Read(outBuf, 0, outBuf.Length)) > 0)
                        {
                            var chunk = new float[read];
                            outBuf.AsSpan(0, read).CopyTo(chunk);

                            // L-6 (DIAG): log when the inner channel is full and a chunk is dropped.
                            if (!innerChannel.Writer.TryWrite(chunk))
                            {
                                _logger?.LogWarning(
                                    "DIAG innerChannel full on '{DeviceId}' — chunk dropped " +
                                    "({Samples} samples). Consumer may be stalled.",
                                    deviceId,
                                    chunk.Length);
                            }
                            // D1 (DIAG): rate-limited zero-output warning. Fires on the first
                            // occurrence and every 100 thereafter. Includes rawHasData so the
                            // operator can immediately distinguish the two root causes:
                            //   rawHasData=false → WASAPI is delivering silence (device/OS issue)
                            //   rawHasData=true  → NAudio pipeline is zeroing good data (format issue)
                            else if (chunk.All(sample => sample == 0))
                            {
                                zeroOutputCount++;
                                if (zeroOutputCount == 1)
                                {
                                    _logger?.LogWarning(
                                        "DIAG Resampler output all zeros on '{DeviceId}' " +
                                        "(run #1, rawHasData={RawHasData}) — {Diagnosis}",
                                        deviceId,
                                        rawHasData,
                                        rawHasData
                                            ? "NAudio pipeline is zeroing good data — check encoding type, channel count, and format negotiation."
                                            : "WASAPI is delivering silence — check device selection, mute state, signal source, and OS audio policy.");

                                    // D5 (DIAG): if rawHasData=True and the device is stereo, log the
                                    // first two interleaved L/R float pairs from the raw buffer.
                                    // If L0 ≈ −R0 and L1 ≈ −R1, the device delivers a differential
                                    // (balanced) signal and the stereo-to-mono conversion is cancelling it.
                                    if (rawHasData && capture.WaveFormat.Channels == 2 && e.BytesRecorded >= 16)
                                    {
                                        var span = e.Buffer.AsSpan(0, 16); // 4 floats × 4 bytes = 2 stereo frames
                                        var f    = System.Runtime.InteropServices.MemoryMarshal.Cast<byte, float>(span);
                                        _logger?.LogWarning(
                                            "DIAG Phase-cancellation check on '{DeviceId}': " +
                                            "L0={L0:G4}, R0={R0:G4}, L1={L1:G4}, R1={R1:G4} — " +
                                            "if L ≈ −R the device delivers a differential signal; stereo averaging cancels it.",
                                            deviceId, f[0], f[1], f[2], f[3]);
                                    }
                                }
                            }
                            else
                            {
                                // Non-zero audio is flowing — reset the consecutive-zero run counter
                                // so the next zero-output event is always logged as run #1.
                                zeroOutputCount = 0;
                            }
                            // Advisory: outBuf is reused each iteration; the meaningful allocation
                            // is the fresh float[read] chunk copy above. No re-allocation needed here.
                        }

                        // L-5 (DIAG): warn if a non-empty buffer produced no resampler output.
                        // D2: rate-limited to once every 100 callbacks to prevent log flooding.
                        if (e.BytesRecorded > 0 && dataAvailableCount > 1)
                        {
                            var samplesInBuffer = buffer.BufferedBytes /
                                (capture.WaveFormat.BitsPerSample / 8 * capture.WaveFormat.Channels);
                            if (samplesInBuffer > 0 && dataAvailableCount % 100 == 1)
                            {
                                _logger?.LogWarning(
                                    "DIAG Resampler produced 0 output on '{DeviceId}' " +
                                    "despite {SamplesInBuffer} samples in buffer (at callback #{Count}).",
                                    deviceId,
                                    samplesInBuffer,
                                    dataAvailableCount);
                            }
                        }
                    }
                    catch (Exception ex)
                    {
                        // Complete the channel so CaptureAsync exits and CaptureManager
                        // surfaces the error via CaptureFailed.
                        innerChannel.Writer.TryComplete(ex);
                        try { staCts.Cancel(); } catch (ObjectDisposedException) { }
                    }
                };

                capture.RecordingStopped += (_, e) =>
                {
                    // DIAG: this is the one log entry that has never existed in this codebase.
                    // null exception = graceful stop (doStop was set) → Case 2 in CaptureManager.
                    // non-null exception = WASAPI error → Case 3.  The exception type and message
                    // tell us exactly why WASAPI stopped.
                    if (e.Exception is not null)
                    {
                        _logger?.LogError(e.Exception,
                            "DIAG RecordingStopped — WASAPI error on '{DeviceId}': {ExType} — {ExMessage}",
                            deviceId, e.Exception.GetType().Name, e.Exception.Message);
                        innerChannel.Writer.TryComplete(e.Exception);
                    }
                    else
                    {
                        _logger?.LogWarning(
                            "DIAG RecordingStopped — null exception on '{DeviceId}' " +
                            "(graceful/unexpected stop; doStop was set internally by NAudio).",
                            deviceId);
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

                // L-7 (DIAG): confirm the StartRecording call was accepted by NAudio.
                _logger?.LogInformation(
                    "Calling capture.StartRecording() on '{DeviceId}'.", deviceId);
                capture.StartRecording();
                _logger?.LogInformation(
                    "capture.StartRecording() returned on '{DeviceId}'.", deviceId);

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

                // L-8 (DIAG): the most informative log in the entire STA thread.
                // Distinguishes operator-stop (ct cancelled) from unexpected stop (staCts only).
                _logger?.LogInformation(
                    "DIAG STA WaitOne unblocked on '{DeviceId}' — " +
                    "ct.IsCancellationRequested={CtCancelled}, " +
                    "staCts.IsCancellationRequested={StaCancelled}",
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
                // L-9 (DIAG): trace every cleanup step so we can tell exactly how far
                // the finally block progressed if something throws.
                _logger?.LogInformation(
                    "DIAG STA finally: beginning cleanup on '{DeviceId}'.", deviceId);

                // Dispose sessionControl before capture: cleanly unregisters the
                // WASAPI session event client before tearing down the capture session.
                if (sessionControl is not null)
                {
                    _logger?.LogInformation(
                        "DIAG STA finally: disposing sessionControl on '{DeviceId}'.", deviceId);
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
                    _logger?.LogInformation(
                        "DIAG STA finally: calling capture.StopRecording() on '{DeviceId}' (3 s timeout).",
                        deviceId);
                    var stopTask = Task.Run(() => { try { capture.StopRecording(); } catch { } });
                    if (stopTask.Wait(TimeSpan.FromSeconds(3)))
                    {
                        _logger?.LogInformation(
                            "DIAG STA finally: capture.StopRecording() completed on '{DeviceId}'.", deviceId);
                        _logger?.LogInformation(
                            "DIAG STA finally: calling capture.Dispose() on '{DeviceId}'.", deviceId);
                        try { capture.Dispose(); } catch { }
                    }
                    else
                    {
                        // StopRecording timed out — skip Dispose (it would also hang).
                        // The device handle is abandoned; the OS reclaims it on process exit.
                        _logger?.LogWarning(
                            "DIAG STA finally: capture.StopRecording() timed out after 3 s on '{DeviceId}' " +
                            "— abandoning device handle; OS will reclaim on process exit.", deviceId);
                    }
                }

                _logger?.LogInformation(
                    "DIAG STA finally: cleanup complete on '{DeviceId}'.", deviceId);
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
            // DIAG
            _logger?.LogError(
                "DIAG OnSessionDisconnected on '{DeviceId}': reason = {Reason}",
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
            // L-10 (DIAG): log all state transitions, not just Expired, so the full
            // session lifecycle is visible (Active → Inactive → Expired sequence).
            _logger?.LogInformation(
                "DIAG OnStateChanged on '{DeviceId}': state = {State}",
                _deviceId, state);

            if (state == AudioSessionState.AudioSessionStateExpired)
            {
                var ex = new AudioCaptureException(
                    _deviceId,
                    "WASAPI audio session expired (OnStateChanged: Expired).");

                _channel.Writer.TryComplete(ex);
                try { _staCts.Cancel(); } catch (ObjectDisposedException) { }
            }
            // AudioSessionStateInactive: session paused but not destroyed — do not
            // complete the channel; audio may resume (e.g. brief device re-negotiation).
        }

        // L-11 (DIAG): log volume/mute — a muted session explains silent audio without
        // terminating the session, so it would trip the watchdog without this log.
        public void OnVolumeChanged(float volume, bool isMuted)
        {
            _logger?.LogInformation(
                "DIAG OnVolumeChanged on '{DeviceId}': volume={Volume:F2}, isMuted={IsMuted}",
                _deviceId, volume, isMuted);
        }
        public void OnDisplayNameChanged(string displayName)                                         { }
        public void OnIconPathChanged(string iconPath)                                               { }
        public void OnChannelVolumeChanged(uint channelCount, IntPtr newVolumes, uint channelIndex)  { }
        public void OnGroupingParamChanged(ref Guid groupingId)                                      { }
    }
}
#endif
