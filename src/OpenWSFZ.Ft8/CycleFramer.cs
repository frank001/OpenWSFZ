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
///
/// <para>
/// Over a long-running session, a capture device's clock-rate error (even a small one) causes
/// each window's raw sample content to span slightly more or less than the nominal 15.000 true
/// UTC seconds, drifting the decode-cycle boundary from true UTC without bound. To prevent this,
/// <see cref="CycleFramer"/> periodically compares its arithmetic cycle-boundary sequence
/// against the injected <see cref="IClock"/>'s wall-clock reading and — only once the accumulated
/// deviation clears a threshold <em>and</em> that threshold-crossing persists across several
/// consecutive checks in the same direction without shrinking (see Decision 4 in design.md) —
/// corrects which raw samples land in the next window by the full confirmed deviation and
/// re-anchors the reported <c>CycleStart</c> to match (see Decision 5 in design.md — the
/// persistence gate itself is what confirms the deviation is genuine, so the correction is no
/// longer capped to a small fixed quantum; a much larger sanity ceiling remains only as a
/// backstop against a pathological <see cref="IClock"/> reading, not as a slow-slew mechanism for
/// ordinary confirmed drift). Every emitted window remains exactly 180 000 samples regardless;
/// only the raw-sample-to-window mapping is adjusted. See the drift-correction constants below
/// for details and rationale.
/// </para>
///
/// <para>
/// The persistence requirement exists because a live pipeline's own scheduling (capture
/// callback jitter, channel backpressure, thread-pool contention with concurrent native decode
/// work) can make a single <see cref="IClock"/> read look tens-to-hundreds of samples off from
/// nominal on any given cycle — far larger than genuine device clock-rate drift, but recurring
/// on effectively every cycle rather than accumulating. Reacting to any single such reading
/// caused the correction to engage every cycle in production instead of the rare, occasional
/// event it was designed to be; requiring several consecutive, same-sign, non-decreasing
/// readings before acting filters that noise out while still catching genuine sustained drift,
/// whose accumulated deviation grows monotonically once nothing is correcting it.
/// </para>
/// </summary>
public sealed class CycleFramer
{
    private const int SampleRate        = 12_000;
    private const int CycleDurationSecs = 15;
    private const int SamplesPerCycle   = SampleRate * CycleDurationSecs; // 180 000

    // ── Cycle-boundary clock-drift correction (fix-cycle-boundary-clock-drift) ──
    // A capture device with a clock-rate error (QA measured ~-42.41 ppm on one real
    // device — see qa/rr-study/results/2026-07-23-d001-live-path-root-cause/
    // phase3_clockrate_results_usbcodec.json) causes each 180 000-sample window to
    // span slightly more or less than the nominal 15.000 true UTC seconds. Left
    // uncorrected, both the reported cycleStart label and — more importantly — the
    // window's actual sample content drift away from the true UTC 15-second FT8
    // grid without bound over a long session (~2.6 s over a 17 h session at the
    // measured rate), eventually pushing a real signal's sync tone outside the
    // decoder's search range. See design.md Decisions 2 and 3 for full rationale.
    //
    // Constants are derived from that measured ~-42.41 ppm device error, which
    // works out to ~7.6 samples of drift per 15 s cycle at 12 000 Hz
    // (15 s x 42.41e-6 x 12 000 Hz):
    //   - DriftThresholdSamples is set to ~3 cycles' worth of that drift — clearly
    //     above ordinary DateTime.UtcNow/GC/scheduler jitter, yet small enough that
    //     no more than a handful of cycles pass between corrections at the measured
    //     rate (Decision 3: threshold-gated, not applied every cycle). Left
    //     unchanged by the live-evidence fix below (design.md Decision 4): raising
    //     it to sit above the observed pipeline-latency noise ceiling (roughly
    //     500-2400 samples per a live capture — see
    //     dev-tasks/2026-07-23-cycleframer-correction-fires-every-cycle-live-evidence.md)
    //     would make genuine drift take ~80+ minutes just to become a threshold
    //     candidate at all, without improving noise rejection — RequiredConsecutiveReadings
    //     below already does that job regardless of a single reading's magnitude.
    //   - CorrectionSanityCeilingSamples (design.md Decision 5, superseding the old
    //     "MaxCorrectionSamples = 48" quantum from Decision 4) is deliberately NOT
    //     sized to the ~7.6 samples/cycle device-drift rate at all. A live 7h54m
    //     endurance re-test (qa/endurance/2026-07-24-ce13e30/report.md) found the
    //     48-sample cap absorbing as little as 0.3% of the deviation already
    //     confirmed genuine by the persistence gate at fire time (observed
    //     deviation-at-fire ranged ~1,700-17,400 samples) — 20 corrections over the
    //     session removed only 960 of 16,155 samples of net growth, leaving a
    //     residual drift rate the same order of magnitude as the original, unfixed
    //     defect. Once RequiredConsecutiveReadings has already confirmed 3
    //     consecutive same-sign, non-decreasing readings, that confirmation IS the
    //     protection against a single spurious reading (that job was never this
    //     cap's to do) — so the correction now absorbs the full confirmed deviation.
    //     CorrectionSanityCeilingSamples remains only as a backstop against a truly
    //     pathological IClock reading (a DateTime overflow, a multi-day misconfigured
    //     system clock) stalling the pipeline for an absurd length of real time — set
    //     to one full cycle's worth of samples (180 000 = 15 s), roughly an order of
    //     magnitude above any deviation-at-fire observed in the endurance run
    //     (max 17,438 samples) and far below the ~3,600,000 samples a 5-minute host
    //     clock step would produce, so a genuine large step still slews over several
    //     corrections rather than landing as one 15-second jump — this ceiling is not
    //     expected to bind for any plausible device-drift or host-clock-step
    //     scenario, only for genuinely broken input.
    private const int DriftThresholdSamples          = 24;      // ~2.0 ms @ 12 kHz (~3 cycles at the measured rate)
    private const int CorrectionSanityCeilingSamples = SamplesPerCycle; // one full 15 s cycle — pathological-input backstop only

    // Number of consecutive drift-check readings that must clear DriftThresholdSamples,
    // share the same sign, and be non-decreasing in magnitude before a correction is
    // actually applied (design.md Decision 4). This is the fix for a live-evidence
    // defect (dev-tasks/2026-07-23-cycleframer-correction-fires-every-cycle-live-evidence.md):
    // a real capture pipeline's own recurring scheduling latency (WASAPI callback
    // jitter, Channel<float[]> backpressure, thread-pool contention with concurrent
    // native decode work) can make any single IClock read look far outside
    // DriftThresholdSamples without any genuine device drift being present. Ordinary
    // pipeline latency bounces around from cycle to cycle rather than growing
    // monotonically, so it essentially never sustains a same-sign, non-decreasing
    // streak this long; genuine device clock-rate drift, left uncorrected, does grow
    // monotonically every cycle and will always eventually satisfy this. Set to 3 to
    // mirror the "~3 cycles" vocabulary already used to derive DriftThresholdSamples.
    private const int RequiredConsecutiveReadings = 3;

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

            // Purely-arithmetic reference sequence, advanced by exactly
            // CycleDurationSecs every window and NEVER touched by drift
            // corrections. Comparing this against _clock.UtcNow at each boundary
            // is what accumulated deviation is measured against (design.md
            // Decision 3). Reset to match cycleStart whenever a correction fires,
            // so deviation starts accumulating fresh from that point.
            DateTime nominalCycleStart = cycleStart;

            // Raw source samples still to be discarded (never assigned to any
            // window) before accumulation may resume — set by a "lengthen"
            // drift correction (see below). Persists across chunk boundaries.
            int pendingSkipSamples = 0;

            // Persistence-gate state for the drift check (design.md Decision 4).
            // driftStreakCount tracks how many consecutive checks have cleared
            // DriftThresholdSamples with the same sign and a non-decreasing
            // magnitude; a correction only applies once it reaches
            // RequiredConsecutiveReadings. Reset to 0 whenever a reading falls
            // below threshold, reverses sign, or shrinks — none of those are
            // consistent with sustained one-directional drift.
            int    driftStreakCount     = 0;
            int    driftStreakSign      = 0;
            double driftStreakMagnitude = 0;

            // Snapshot the dial frequency at window-open time (startup = open of first window).
            // This prevents band-change boundary mislabeling: the decode pump compares this
            // snapshot against the live frequency at decode time and discards the cycle if
            // they differ (audio spans two bands).
            double? windowDialFreq = _dialFreqProvider?.Invoke();

            _logger?.LogInformation(
                "CycleFramer started; leading silence = {Samples} samples ({Seconds:F3} s), cycle start = {CycleStart:HH:mm:ss}.",
                leadingSilence, leadingSilence / (double)SampleRate, cycleStart);

            await foreach (var chunk in _source.ReadAllAsync(ct))
            {
                int remaining = chunk.Length;
                int chunkPos  = 0;

                while (remaining > 0)
                {
                    // Discard any samples still owed to a prior "lengthen" drift
                    // correction before they can reach the window buffer. Re-checked
                    // every iteration (not just once per chunk) because a correction
                    // can be set mid-chunk — the same chunk may contain both the tail
                    // of the window that just closed and the head of the next one.
                    // May span multiple chunks if pendingSkipSamples exceeds what is
                    // left in this one.
                    if (pendingSkipSamples > 0)
                    {
                        int discard = Math.Min(pendingSkipSamples, remaining);
                        chunkPos           += discard;
                        remaining          -= discard;
                        pendingSkipSamples -= discard;
                        if (remaining == 0) break;
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

                        // Advance to the next cycle and snapshot the frequency at the new
                        // window-open boundary — not at window-close — so that a band change
                        // that happens during the previous window is correctly attributed to
                        // the next window, not the one just emitted.
                        var previousWindow = window;
                        window         = new float[SamplesPerCycle];
                        filled         = 0;
                        cycleStart     = cycleStart.AddSeconds(CycleDurationSecs);
                        nominalCycleStart = nominalCycleStart.AddSeconds(CycleDurationSecs);

                        // ── Drift check (fix-cycle-boundary-clock-drift, design.md Decisions 3-4) ──
                        // Only act once accumulated deviation clears the threshold AND that
                        // threshold-crossing has persisted across RequiredConsecutiveReadings
                        // consecutive checks in the same direction without shrinking; below
                        // threshold, or on a non-persistent reading, behaviour is unchanged
                        // (spec: "Decode-cycle boundary tracks true UTC over long-running
                        // sessions", "no correction fires absent genuine, sustained drift").
                        double deviationSeconds = (_clock.UtcNow - nominalCycleStart).TotalSeconds;
                        double deviationSamples = deviationSeconds * SampleRate;

                        if (Math.Abs(deviationSamples) >= DriftThresholdSamples)
                        {
                            int sign = Math.Sign(deviationSamples);
                            if (driftStreakCount == 0
                                || sign != driftStreakSign
                                || Math.Abs(deviationSamples) < driftStreakMagnitude)
                            {
                                // First candidate reading, a sign reversal, or a reading smaller
                                // than the previous one in the current streak — none of these are
                                // consistent with sustained, one-directional drift, so this
                                // reading starts a brand-new candidate streak rather than
                                // continuing the old one.
                                driftStreakCount     = 1;
                                driftStreakSign      = sign;
                                driftStreakMagnitude = Math.Abs(deviationSamples);
                            }
                            else
                            {
                                driftStreakCount++;
                                driftStreakMagnitude = Math.Abs(deviationSamples);
                            }
                        }
                        else
                        {
                            driftStreakCount = 0;
                        }

                        _logger?.LogDebug(
                            "Cycle boundary drift check: deviation = {DeviationSamples:F1} samples " +
                            "({DeviationMs:F2} ms); persistence streak = {Streak}/{Required}.",
                            deviationSamples, deviationSeconds * 1000.0, driftStreakCount, RequiredConsecutiveReadings);

                        if (driftStreakCount >= RequiredConsecutiveReadings)
                        {
                            // Absorb the full confirmed deviation (design.md Decision 5) — the
                            // persistence gate above has already confirmed this is genuine,
                            // sustained drift, not a single spurious reading, so there is nothing
                            // left for a small fixed quantum to protect against. Clamp only
                            // guards against a pathological IClock reading; it is not expected to
                            // bind for any plausible drift or clock-step scenario.
                            int correction = (int)Math.Clamp(
                                Math.Round(deviationSamples),
                                -CorrectionSanityCeilingSamples, CorrectionSanityCeilingSamples);

                            if (correction > 0)
                            {
                                // Clock reads later than nominal expects (device running slow —
                                // 180 000 raw samples span MORE than 15.000 true seconds): the
                                // raw stream is ahead of true UTC. Discard `correction` incoming
                                // samples before the next window may accumulate, so the window's
                                // sample content — not just its label — catches back up to the
                                // true UTC grid (design.md: relabelling alone was rejected as
                                // insufficient).
                                pendingSkipSamples += correction;
                            }
                            else if (correction < 0)
                            {
                                // Clock reads earlier than nominal expects (device running fast):
                                // replay the last |correction| real samples already captured at
                                // the tail of the window just emitted as the lead-in of the next
                                // window — a brief, bounded overlap of real audio, never
                                // synthetic silence.
                                int replay = -correction;
                                Array.Copy(previousWindow, SamplesPerCycle - replay, window, 0, replay);
                                filled = replay;
                            }

                            // Re-anchor the reported boundary to reflect the correction actually
                            // applied above, and reset the nominal reference to match so deviation
                            // starts accumulating fresh from this point. In the ordinary case the
                            // applied correction equals the full confirmed deviation, so the
                            // residual is zero; only a pathological reading that hits the sanity
                            // ceiling leaves an excess, which carries forward to be chipped away
                            // at on subsequent cycles (a slew, not a step; design.md Risks). Also
                            // reset the persistence streak — the next reading starts a fresh
                            // candidate streak against the just-corrected baseline.
                            cycleStart        = cycleStart.AddSeconds(correction / (double)SampleRate);
                            nominalCycleStart = cycleStart;
                            driftStreakCount  = 0;

                            _logger?.LogInformation(
                                "Cycle boundary resync: accumulated deviation = {DeviationSamples:F1} samples " +
                                "({DeviationMs:F2} ms); applying {Correction} sample correction; " +
                                "cycleStart re-anchored to {CycleStart:HH:mm:ss.fff}.",
                                deviationSamples, deviationSeconds * 1000.0, correction, cycleStart);
                        }

                        windowDialFreq = _dialFreqProvider?.Invoke();
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
