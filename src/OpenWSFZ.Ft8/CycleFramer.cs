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
/// <b>Every cycle re-anchors to the UTC grid at sample level.</b>  A capture device's crystal
/// is not the system clock: the affected hardware runs 48.4 ppm slow, so 180 000 samples take
/// 15.00072 s of wall clock and a framer that simply counts to 180 000 opens each window
/// 0.72 ms later than the last.  That per-cycle error is tiny; its running sum is not, and it
/// reached 4 s over a 24 h session — well past FT8's ~2.36 s guard interval, at which point
/// decoding collapses silently with every health signal still green.  <see cref="RunAsync"/>
/// therefore chooses <em>how many source samples to consume</em> each cycle so the window's
/// audio spans the wall-clock interval between grid lines, padding or trimming the tail (in
/// dead air) to keep the emitted buffer at exactly 180 000 samples.  Corrections are clamped
/// to <see cref="MaxCorrectionSamples"/> so a system-clock step converges over several cycles
/// instead of mutilating one.  See <c>DEFECT-capture-clock-drift-silent-decode-loss.md</c>.
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

    private const long CycleTicks = CycleDurationSecs * TimeSpan.TicksPerSecond;

    /// <summary>
    /// The largest grid realignment applied in a single cycle: 250 ms, or 3 000 samples at
    /// 12 kHz.  This is a safety valve, not an operating point.
    ///
    /// <para>
    /// A capture crystal running at the measured 48.4 ppm needs ~9 samples of correction per
    /// cycle and never approaches this cap.  What the cap exists for is a system-clock
    /// <em>step</em> — an NTP correction, a sleep/resume, a VM pause — which would otherwise
    /// have the framer discard or duplicate a large block of audio in one cycle.  Clamped, a
    /// genuine step converges over a handful of cycles instead, and no single window is
    /// mutilated on the way.
    /// </para>
    /// </summary>
    internal const int MaxCorrectionSamples = SampleRate / 4; // 3 000 = 250 ms

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

            // How many SOURCE samples this window will consume, and how many it has consumed so
            // far.  Deliberately tracked separately from `filled`:
            //
            //   * start-up leading silence occupies buffer space without consuming any source
            //     samples, and
            //   * grid realignment (see the needsResync block) makes `consume` differ from
            //     SamplesPerCycle on every cycle of a drifting device.
            //
            // `consume` is the fix.  Everything else here is bookkeeping that only becomes
            // *true* because `consume` moved the window.
            int consume = SamplesPerCycle - leadingSilence;
            int taken   = 0;

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
            // a *fresh* window's first sample. The realignment deliberately happens lazily —
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
                        // ── Re-anchor this window to the UTC 15-second grid ───────────────
                        //
                        // DEFECT-capture-clock-drift-silent-decode-loss.md, reopened
                        // 2026-08-02; design at qa/cycleframer-alignment-replay/2026-08-02-
                        // 1813-architect-design-cycleframer-grid-realignment.md §3.
                        //
                        // PR #118 re-read the clock here and assigned it straight to
                        // cycleStart. That made the *timestamp* honest — it truthfully
                        // reported a drifting window — but it did not move the window, and
                        // the window kept drifting at 48 ppm for 43.6 h of live capture with
                        // every health signal green. Re-reading the clock tells you where you
                        // are; it does not move you back. The per-cycle error is bounded at
                        // 0.72 ms; the offset from the grid is the running sum of those, and
                        // that is unbounded.
                        //
                        // FT8 is defined against UTC — transmissions start at
                        // `second % 15 == 0` — so the fix is to choose how many source
                        // samples to CONSUME such that this window's audio spans the
                        // wall-clock interval [G, G+15], then pad or trim the tail to the
                        // exactly 180 000 samples the decoder expects. Measured cost of
                        // getting this wrong: -3.8% decodes at 1 s of offset, -29.8% at 2 s.

                        // When was this window's FIRST sample actually captured? A capture
                        // buffer is handed over once its LAST sample has been captured, so
                        // the clock we can read now runs ahead of the sample we are about to
                        // place by however much of the current chunk is still unconsumed —
                        // up to 2048 samples (171 ms) on the real capture sources. Left
                        // uncorrected that is a systematic bias eating most of the 0.2 s
                        // acceptance budget, so subtract it rather than inherit it.
                        DateTime firstSampleUtc =
                            _clock.UtcNow.AddSeconds(-remaining / (double)SampleRate);

                        // NEAREST grid line, not floor: a window that opened 14.9 s late must
                        // converge forwards to the next line, not be thrown a full cycle
                        // backwards. Nearest converges from either side.
                        DateTime grid      = NearestCycleGridLine(firstSampleUtc);
                        double   errorSecs = (firstSampleUtc - grid).TotalSeconds;

                        int wanted     = (int)Math.Round(errorSecs * SampleRate);
                        int correction = Math.Clamp(wanted, -MaxCorrectionSamples, MaxCorrectionSamples);

                        if (correction != wanted)
                        {
                            // Only a genuine clock step gets here — a 48 ppm crystal asks for
                            // ~9 samples. Worth a WRN: this defect went unnoticed for weeks
                            // partly because the capture path had no signal that could ever
                            // go non-green (see the defect report §3).
                            _logger?.LogWarning(
                                "Cycle-grid realignment clamped: wanted {Wanted} samples ({WantedSecs:F3} s), " +
                                "applied {Applied} ({AppliedSecs:F3} s). A system-clock step (NTP, sleep/resume, " +
                                "VM pause) converges over several cycles; a capture-crystal drift never reaches " +
                                "this cap.",
                                wanted, wanted / (double)SampleRate,
                                correction, correction / (double)SampleRate);
                        }

                        // THIS is the fix. Consuming fewer samples closes the window earlier in
                        // wall-clock terms, which opens the next one earlier, which cancels the
                        // drift. If `consume` is not varying cycle-to-cycle on a drifting
                        // device then the fix is not implemented, whatever the timestamps say.
                        consume = SamplesPerCycle - correction;
                        taken   = 0;

                        // Now honestly ON the grid — true only *because* `consume` moved the
                        // window. Assigning this without the line above would put a false grid
                        // label on genuinely drifted audio, which is worse than the status quo.
                        cycleStart = grid;

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

                    if (taken < consume)
                    {
                        // Take up to `consume` source samples for this window, but only ever
                        // STORE SamplesPerCycle of them. The two differ by the realignment:
                        //
                        //   consume < 180 000 (device slow / window opened late)
                        //       → the tail of `window` keeps its zero-initialised padding;
                        //   consume > 180 000 (window opened early)
                        //       → the surplus tail samples are taken and discarded.
                        //
                        // Either way the correction lands in FT8's guard interval: a signal
                        // occupies 12.64 s of the 15 s window, leaving ~2.36 s of dead air at
                        // the tail, and the clamp caps the change at 250 ms of it. The decoder
                        // is handed exactly 180 000 samples, as it always was.
                        int want  = Math.Min(consume - taken, remaining);
                        int store = Math.Min(want, SamplesPerCycle - filled);

                        if (store > 0)
                        {
                            Array.Copy(chunk, chunkPos, window, filled, store);
                            filled += store;
                        }

                        chunkPos  += want;
                        remaining -= want;
                        taken     += want;
                    }

                    if (taken >= consume)
                    {
                        // Window complete — emit it with its cycle-start timestamp and
                        // the dial frequency that was live when this window began accumulating.
                        output.TryWrite((window, cycleStart, windowDialFreq));
                        _logger?.LogDebug(
                            "Window emitted ({Samples} samples, cycle {CycleStart:HH:mm:ss}); " +
                            "consumed {Consumed} source samples ({Realign:+0;-0;0} grid realignment).",
                            SamplesPerCycle, cycleStart, consume, SamplesPerCycle - consume);

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
    ///
    /// <para>
    /// Exact to the tick.  The grid is anchored on UTC minute boundaries and 15 s divides
    /// 60 s evenly, so flooring the raw tick count is equivalent and loses nothing — unlike
    /// the previous whole-millisecond arithmetic, which left up to 1 ms of sub-millisecond
    /// residue behind.
    /// </para>
    /// </summary>
    internal static DateTime AlignToCycleStart(DateTime utc)
        => new(utc.Ticks - (utc.Ticks % CycleTicks), utc.Kind);

    /// <summary>
    /// Returns the <em>nearest</em> UTC 15-second grid line to <paramref name="utc"/>, which may
    /// be ahead of it.
    ///
    /// <para>
    /// Nearest rather than floor is load-bearing for the grid realignment in
    /// <see cref="RunAsync"/>: flooring a window that opened 14.9 s late would throw it a full
    /// cycle backwards instead of nudging it 0.1 s forwards.  Nearest converges from either
    /// side, which is also what lets a signed clock step of either polarity be walked back.
    /// </para>
    /// </summary>
    internal static DateTime NearestCycleGridLine(DateTime utc)
    {
        long into   = utc.Ticks % CycleTicks;
        long anchor = utc.Ticks - into;
        return new DateTime(into * 2 >= CycleTicks ? anchor + CycleTicks : anchor, utc.Kind);
    }
}
