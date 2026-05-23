#if WASAPI_SUPPORTED
using System.Runtime.CompilerServices;
using System.Runtime.Versioning;
using System.Threading.Channels;
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
            WasapiCapture? capture = null;

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

                // DataAvailable fires on the WASAPI capture thread.
                capture.DataAvailable += (_, e) =>
                {
                    // B13: Wrap the entire handler so any exception (corrupt buffer,
                    // unexpected resampler state, etc.) is surfaced through the channel
                    // rather than propagating into NAudio's internal capture loop where
                    // it may silently terminate the thread without firing RecordingStopped.
                    try
                    {
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
                AudioSessionControl? sessionControl = null;
                try
                {
                    sessionControl = device.AudioSessionManager.AudioSessionControl;
                    sessionControl.RegisterEventClient(
                        new WasapiSessionEventClient(innerChannel, staCts));
                }
                catch
                {
                    sessionControl = null; // registration failed; proceed without it
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

        // All other session events are irrelevant for capture monitoring.
        public void OnVolumeChanged(float volume, bool isMuted)                                      { }
        public void OnDisplayNameChanged(string displayName)                                         { }
        public void OnIconPathChanged(string iconPath)                                               { }
        public void OnChannelVolumeChanged(uint channelCount, IntPtr newVolumes, uint channelIndex)  { }
        public void OnGroupingParamChanged(ref Guid groupingId)                                      { }
        public void OnStateChanged(AudioSessionState state)                                          { }
    }
}
#endif
