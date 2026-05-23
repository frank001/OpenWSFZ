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

                capture = new WasapiCapture(device);

                // ── NAudio resampling pipeline ────────────────────────────────
                var buffer = new BufferedWaveProvider(capture.WaveFormat)
                {
                    BufferDuration          = TimeSpan.FromSeconds(5),
                    DiscardOnBufferOverflow = true,
                };

                ISampleProvider samples = buffer.ToSampleProvider();

                if (capture.WaveFormat.Channels == 2)
                    samples = new StereoToMonoSampleProvider(samples);

                var resampler = new WdlResamplingSampleProvider(samples, 12_000);

                // D1: latches true on the first DataAvailable callback.
                // Accessed only from the WASAPI capture thread (sequential); no lock needed.
                var dataAvailableFired = false;

                // DataAvailable fires on the WASAPI capture thread.
                capture.DataAvailable += (_, e) =>
                {
                    // B13: Wrap the entire handler so any exception (corrupt buffer,
                    // unexpected resampler state, etc.) is surfaced through the channel
                    // rather than propagating into NAudio's internal capture loop where
                    // it may silently terminate the thread without firing RecordingStopped.
                    try
                    {
                        // D1: Log the first buffer so we can distinguish Scenario A
                        // (DataAvailable fires) from Scenario B (DataAvailable never fires).
                        if (!dataAvailableFired)
                        {
                            dataAvailableFired = true;
                            _logger?.LogInformation(
                                "DIAG DataAvailable: first buffer received — " +
                                "BytesRecorded={BytesRecorded}, WaveFormat={WaveFormat}",
                                e.BytesRecorded, capture.WaveFormat);
                        }

                        buffer.AddSamples(e.Buffer, 0, e.BytesRecorded);

                        // Drain the resampler in 2 048-sample chunks.
                        var outBuf = new float[2048];
                        int read;
                        while ((read = resampler.Read(outBuf, 0, outBuf.Length)) > 0)
                        {
                            var chunk = new float[read];
                            outBuf.AsSpan(0, read).CopyTo(chunk);
                            innerChannel.Writer.TryWrite(chunk);
                            outBuf = new float[2048];
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
                    // Propagate any WASAPI error through the channel so CaptureManager
                    // surfaces it via CaptureFailed.  A null Exception means a graceful
                    // stop (e.g. capture.StopRecording() was called from the finally block).
                    if (e.Exception is not null)
                        innerChannel.Writer.TryComplete(e.Exception);
                    else
                        innerChannel.Writer.TryComplete();

                    // Wake the STA thread so staTask completes promptly.
                    // Without this, await staTask in the finally block below would
                    // hang until the caller's ct is cancelled (which may never happen).
                    // B12: Guard with catch(ObjectDisposedException) — WASAPI fires
                    // RecordingStopped a second time from capture.StopRecording() in the
                    // finally block, which races with staCts disposal at the end of
                    // CaptureAsync.  The second call is harmless; the STA is already
                    // unblocking.
                    try { staCts.Cancel(); }
                    catch (ObjectDisposedException) { /* staCts already disposed — STA is unblocking */ }
                };

                capture.StartRecording();

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
                        new WasapiSessionEventClient(innerChannel, staCts));
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
            }
            catch (Exception ex)
            {
                setupException = ex;
                setupTcs.TrySetResult();
                innerChannel.Writer.TryComplete(ex);
            }
            finally
            {
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
                    try { capture.StopRecording(); } catch { }
                    try { capture.Dispose();       } catch { }
                }
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

    // ── B11: WASAPI session event listener ────────────────────────────────────
    // Receives IAudioSessionEvents notifications from the Windows audio engine
    // on a COM event thread (Thread C in the thread-model reference).
    // When Windows terminates the session (device change, exclusive-mode takeover,
    // audio engine restart, format change), OnSessionDisconnected fires and we
    // complete the innerChannel so CaptureAsync exits and CaptureManager raises
    // CaptureFailed — even if NAudio's RecordingStopped never fires.
    private sealed class WasapiSessionEventClient : IAudioSessionEventsHandler
    {
        private readonly Channel<float[]>        _channel;
        private readonly CancellationTokenSource _staCts;

        public WasapiSessionEventClient(
            Channel<float[]>        channel,
            CancellationTokenSource staCts)
        {
            _channel = channel;
            _staCts  = staCts;
        }

        public void OnSessionDisconnected(AudioSessionDisconnectReason disconnectReason)
        {
            // Windows terminated the session: complete the channel with a descriptive
            // exception so CaptureManager surfaces the event via CaptureFailed, and
            // FR-021 logs it at Error level.
            var ex = new AudioCaptureException(
                "unknown",
                $"WASAPI audio session disconnected: {disconnectReason}");

            _channel.Writer.TryComplete(ex);
            try { _staCts.Cancel(); } catch (ObjectDisposedException) { }
        }

        // B17: Handle session expiry. AudioSessionStateExpired fires when the session
        // is being destroyed normally (e.g. device removed quietly, format change).
        // On some drivers this fires without a corresponding OnSessionDisconnected.
        public void OnStateChanged(AudioSessionState state)
        {
            if (state == AudioSessionState.AudioSessionStateExpired)
            {
                var ex = new AudioCaptureException(
                    "unknown",
                    "WASAPI audio session expired (OnStateChanged: Expired).");

                _channel.Writer.TryComplete(ex);
                try { _staCts.Cancel(); } catch (ObjectDisposedException) { }
            }
            // AudioSessionStateInactive: session paused but not destroyed — do not
            // complete the channel; audio may resume (e.g. brief device re-negotiation).
        }

        // All other session events are irrelevant for capture monitoring.
        public void OnVolumeChanged(float volume, bool isMuted)                                      { }
        public void OnDisplayNameChanged(string displayName)                                         { }
        public void OnIconPathChanged(string iconPath)                                               { }
        public void OnChannelVolumeChanged(uint channelCount, IntPtr newVolumes, uint channelIndex)  { }
        public void OnGroupingParamChanged(ref Guid groupingId)                                      { }
    }
}
#endif
