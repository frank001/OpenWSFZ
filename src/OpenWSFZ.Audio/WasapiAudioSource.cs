#if WASAPI_SUPPORTED
using System.Runtime.CompilerServices;
using System.Runtime.Versioning;
using System.Threading.Channels;
using NAudio.CoreAudioApi;
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

        // The STA thread owns all COM objects for the entire capture session.
        // It blocks on ct until cancellation, then performs cleanup.
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
                };

                capture.RecordingStopped += (_, _) =>
                    innerChannel.Writer.TryComplete();

                capture.StartRecording();

                // Signal that setup succeeded so the async caller can start reading.
                setupTcs.SetResult();

                // Block the STA thread alive while the session is running.
                ct.WaitHandle.WaitOne();
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
}
#endif
