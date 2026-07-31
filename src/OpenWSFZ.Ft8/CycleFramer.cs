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
/// Each emitted item is a <c>(float[] Pcm, DateTime CycleStart, double? DialFrequencyMHz)</c>
/// tuple where <c>CycleStart</c> is the UTC instant at which the 15-second window began
/// and <c>DialFrequencyMHz</c> is the dial frequency snapshot taken at that same instant
/// (by invoking <c>dialFreqProvider</c>, if supplied).  Snapshotting at window-open time
/// prevents band-change boundary mislabeling: if the operator changes bands mid-cycle the
/// decode pump can detect the discrepancy and discard the window rather than logging it
/// with wrong metadata.
/// </para>
///
/// <para>
/// The decode pump passes <c>CycleStart</c> directly to <see cref="IModeDecoder.DecodeAsync"/>
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
    private readonly Func<double?>?          _dialFreqProvider;

    public CycleFramer(
        ChannelReader<float[]>  source,
        IClock                  clock,
        ILogger<CycleFramer>?   logger           = null,
        Func<double?>?          dialFreqProvider = null)
    {
        _source           = source;
        _clock            = clock;
        _logger           = logger;
        _dialFreqProvider = dialFreqProvider;
    }

    /// <summary>
    /// Reads from the source channel, frames samples into 15-second UTC-aligned windows,
    /// and writes each completed window (along with its cycle-start timestamp and dial
    /// frequency snapshot) to <paramref name="output"/>.
    /// Returns when the source channel completes or <paramref name="ct"/> is cancelled.
    /// </summary>
    public async Task RunAsync(
        ChannelWriter<(float[] Pcm, DateTime CycleStart, double? DialFrequencyMHz)> output,
        CancellationToken ct)
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

            // Snapshot the dial frequency at window-open time (startup = open of first window).
            // This prevents band-change boundary mislabeling: the decode pump compares this
            // snapshot against the live frequency at decode time and discards the cycle if
            // they differ (audio spans two bands).
            double? windowDialFreq = _dialFreqProvider?.Invoke();

            // DEFECT-capture-clock-drift-silent-decode-loss.md: set the instant a window
            // closes, consumed (and cleared) the next time this loop is about to accumulate
            // a *fresh* window's first sample. The resync deliberately happens lazily —
            // right when new data actually starts arriving for the next window — rather
            // than eagerly the moment the previous one closes. That distinction is the
            // whole fix: any real wall-clock time that elapses *between* the two (a capture
            // device crystal that simply runs slow, measured at 48.4 ppm on the affected
            // hardware, and/or WasapiAudioSource silently dropping a chunk on its warn-only
            // overrun/write-failure branches) only shows up in _clock.UtcNow once that gap
            // has actually passed. Reading the clock at window-close instead would miss it
            // — the gap (if any) hasn't happened yet at that point in the code.
            bool needsResync = false;

            _logger?.LogInformation(
                "CycleFramer started; leading silence = {Samples} samples ({Seconds:F3} s), cycle start = {CycleStart:HH:mm:ss}.",
                leadingSilence, leadingSilence / (double)SampleRate, cycleStart);

            await foreach (var chunk in _source.ReadAllAsync(ct))
            {
                int remaining = chunk.Length;
                int chunkPos  = 0;

                while (remaining > 0)
                {
                    if (needsResync)
                    {
                        // Re-derive this window's start from the wall clock rather than
                        // trusting "previous cycleStart + 15s" arithmetic — see the
                        // comment on `needsResync` above and DEFECT-capture-clock-drift-
                        // silent-decode-loss.md. Deliberately NOT floored to the nearest
                        // 15-second UTC grid line the way AlignToCycleStart is at start-up:
                        // the sample buffer itself is untouched by this fix (still always
                        // exactly SamplesPerCycle samples — no padding, no truncation, no
                        // carry-over), so a window's audio may now genuinely span slightly
                        // more or less than 15.000s of real time when the capture device's
                        // rate isn't exactly nominal. That residual is fully absorbed by
                        // this timestamp (the gap between consecutive CycleStart values),
                        // not by resizing the buffer — resync-every-cycle keeps that
                        // residual bounded to a single cycle's worth of clock error, which
                        // per the 2026-07-31 handoff is ~3 orders of magnitude inside the
                        // measured decode-failure cliff, so no rate estimation/PLL is needed.
                        cycleStart = _clock.UtcNow;

                        // dev-tasks/2026-07-31-fix-cycleframer-dial-freq-lazy-resync-
                        // consistency.md: snapshotted here, at the same lazy resync point as
                        // cycleStart, rather than eagerly in the emission block below. Both
                        // must be captured at the identical instant — when the window
                        // actually begins accumulating its first real sample — so that a
                        // band change during the close-open gap (the same gap the clock-
                        // drift fix above exists to absorb) is attributed to the window that
                        // is actually open when it happens, not the one that just closed.
                        // Do not move this back to the emission block "for tidiness".
                        windowDialFreq = _dialFreqProvider?.Invoke();

                        needsResync = false;
                    }

                    int space = SamplesPerCycle - filled;
                    int copy  = Math.Min(space, remaining);

                    Array.Copy(chunk, chunkPos, window, filled, copy);
                    filled   += copy;
                    chunkPos += copy;
                    remaining -= copy;

                    if (filled == SamplesPerCycle)
                    {
                        // Window complete — emit it with its cycle-start timestamp and
                        // the dial frequency that was live when this window began accumulating.
                        output.TryWrite((window, cycleStart, windowDialFreq));
                        _logger?.LogDebug("Window emitted ({Samples} samples, cycle {CycleStart:HH:mm:ss}).",
                            SamplesPerCycle, cycleStart);

                        // Advance to the next cycle. Both cycleStart and windowDialFreq are
                        // resolved lazily at the top of the loop, not here — see
                        // `needsResync` and the dev-tasks/2026-07-31-fix-cycleframer-dial-
                        // freq-lazy-resync-consistency.md comment above.
                        window      = new float[SamplesPerCycle];
                        filled      = 0;
                        needsResync = true;
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
