using System.Threading.Channels;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Ft8;

/// <summary>
/// Accumulates PCM chunks from <see cref="ICaptureSource"/> and emits exactly one
/// 180 000-sample buffer per 15-second FT8 cycle, aligned to UTC even-second boundaries.
///
/// <para>
/// FT8 transmissions occupy a 15-second window starting at UTC seconds 0 and 15
/// of every minute (i.e., <c>utc.Second % 15 == 0</c>).  <see cref="CycleFramer"/>
/// uses the supplied <see cref="IClock"/> to determine where in the current cycle
/// the daemon started capturing; it pre-fills the leading portion of the first
/// window with zeros so that the first emitted buffer is always exactly 180 000 samples.
/// </para>
///
/// <para>
/// When the caller's output channel is full, the new window is dropped with no exception —
/// the decode pipeline is expected to keep up on modern hardware.
/// </para>
/// </summary>
public sealed class CycleFramer
{
    private const int SampleRate        = 12_000;
    private const int CycleDurationSecs = 15;
    private const int SamplesPerCycle   = SampleRate * CycleDurationSecs; // 180 000

    private readonly ChannelReader<float[]>  _source;
    private readonly IClock                  _clock;
    private readonly ILogger<CycleFramer>?   _logger;

    public CycleFramer(ChannelReader<float[]> source, IClock clock, ILogger<CycleFramer>? logger = null)
    {
        _source = source;
        _clock  = clock;
        _logger = logger;
    }

    /// <summary>
    /// Reads from the source channel, frames samples into 15-second UTC-aligned windows,
    /// and writes each completed window to <paramref name="output"/>.
    /// Returns when the source channel completes or <paramref name="ct"/> is cancelled.
    /// </summary>
    public async Task RunAsync(ChannelWriter<float[]> output, CancellationToken ct)
    {
        try
        {
            // Determine how many samples into the current cycle we are at start-up.
            int leadingSilence = ComputeLeadingSamples(_clock.UtcNow);
            var window         = new float[SamplesPerCycle];
            int filled         = leadingSilence; // leading zeros already in place (array is zero-initialised)

            _logger?.LogInformation(
                "CycleFramer started; leading silence = {Samples} samples ({Seconds:F3} s).",
                leadingSilence, leadingSilence / (double)SampleRate);

            await foreach (var chunk in _source.ReadAllAsync(ct))
            {
                int remaining = chunk.Length;
                int chunkPos  = 0;

                while (remaining > 0)
                {
                    int space = SamplesPerCycle - filled;
                    int copy  = Math.Min(space, remaining);

                    Array.Copy(chunk, chunkPos, window, filled, copy);
                    filled   += copy;
                    chunkPos += copy;
                    remaining -= copy;

                    if (filled == SamplesPerCycle)
                    {
                        // Window complete — emit it (non-blocking; drop if consumer is slow).
                        output.TryWrite(window);
                        _logger?.LogDebug("Window emitted ({Samples} samples).", SamplesPerCycle);

                        // Start a fresh window.
                        window = new float[SamplesPerCycle];
                        filled = 0;
                    }
                }
            }

            // Source channel ended naturally (e.g. CaptureManager disposed on shutdown).
            // Signal downstream that no more windows will arrive.
            _logger?.LogInformation("CycleFramer source ended; completing output channel.");
            output.TryComplete();
        }
        catch (OperationCanceledException) when (ct.IsCancellationRequested)
        {
            // Cancelled for a device restart — do NOT complete the output channel.
            // Program.cs owns the channel lifetime and calls TryComplete() on
            // ApplicationStopping. The decode pump must survive the restart.
            _logger?.LogDebug("CycleFramer cancelled (device restart or shutdown).");
        }
    }

    /// <summary>
    /// Returns the number of leading silence samples needed to align the first
    /// window to the next 15-second UTC boundary.
    /// </summary>
    internal static int ComputeLeadingSamples(DateTime utcNow)
    {
        int totalSecs  = utcNow.Second + utcNow.Minute * 60;
        int offsetSecs = totalSecs % CycleDurationSecs;

        if (offsetSecs == 0) return 0; // already at a boundary

        // Samples elapsed in the current cycle at the moment we started.
        // Prepend silence for that period so the window aligns correctly.
        int elapsedSamples = offsetSecs * SampleRate
                           + (int)(utcNow.Millisecond / 1000.0 * SampleRate);

        return Math.Min(elapsedSamples, SamplesPerCycle);
    }
}
