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
/// Each emitted item is a <c>(float[] Pcm, DateTime CycleStart)</c> tuple where
/// <c>CycleStart</c> is the UTC instant at which the 15-second window began.  The
/// decode pump passes this value directly to <see cref="IModeDecoder.DecodeAsync"/>
/// so that timestamps in <see cref="DecodeResult"/> records reflect when the audio
/// was <em>captured</em>, not when the decoder was invoked.
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
    /// and writes each completed window (along with its cycle-start timestamp) to
    /// <paramref name="output"/>.
    /// Returns when the source channel completes or <paramref name="ct"/> is cancelled.
    /// </summary>
    public async Task RunAsync(ChannelWriter<(float[] Pcm, DateTime CycleStart)> output, CancellationToken ct)
    {
        try
        {
            var startUtc = _clock.UtcNow;

            // Determine how many samples into the current cycle we are at start-up.
            int leadingSilence = ComputeLeadingSamples(startUtc);
            var window         = new float[SamplesPerCycle];
            int filled         = leadingSilence; // leading zeros already in place (array is zero-initialised)

            // The current cycle started at the most recent 15-second UTC boundary.
            // Computed once here and advanced by CycleDurationSecs after each emission
            // so the framer — not the decoder — is the authoritative source of cycle
            // timestamps (R3: avoids the wall-clock race in Ft8Decoder).
            DateTime cycleStart = AlignToCycleStart(startUtc);

            _logger?.LogInformation(
                "CycleFramer started; leading silence = {Samples} samples ({Seconds:F3} s), cycle start = {CycleStart:HH:mm:ss}.",
                leadingSilence, leadingSilence / (double)SampleRate, cycleStart);

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
                        // Window complete — emit it with its cycle-start timestamp.
                        output.TryWrite((window, cycleStart));
                        _logger?.LogDebug("Window emitted ({Samples} samples, cycle {CycleStart:HH:mm:ss}).",
                            SamplesPerCycle, cycleStart);

                        // Advance to the next cycle.
                        window     = new float[SamplesPerCycle];
                        filled     = 0;
                        cycleStart = cycleStart.AddSeconds(CycleDurationSecs);
                    }
                }
            }

            // Source channel ended naturally (device failure or CaptureManager disposed).
            // Do NOT complete the output channel — Program.cs owns the channel lifetime
            // and calls TryComplete() on ApplicationStopping. The decode pump must
            // survive device-failure restarts.
            _logger?.LogInformation(
                "CycleFramer source ended (device failure or natural completion) — " +
                "exiting without completing output channel.");
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

        // Note: no early return for offsetSecs == 0 — when the daemon starts exactly
        // at a 15-second UTC boundary but Millisecond > 0, elapsedSamples must still
        // include the sub-second offset to keep the window aligned correctly.
        int elapsedSamples = offsetSecs * SampleRate
                           + (int)(utcNow.Millisecond / 1000.0 * SampleRate);

        return Math.Min(elapsedSamples, SamplesPerCycle);
    }

    /// <summary>
    /// Returns the UTC instant of the most recent 15-second cycle boundary at or before
    /// <paramref name="utc"/>.  Used to initialise <c>cycleStart</c> in
    /// <see cref="RunAsync"/>.
    /// </summary>
    private static DateTime AlignToCycleStart(DateTime utc)
    {
        int totalSecs  = utc.Second + utc.Minute * 60;
        int offsetSecs = totalSecs % CycleDurationSecs;
        return utc.AddSeconds(-offsetSecs).AddMilliseconds(-utc.Millisecond);
    }
}
