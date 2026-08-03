using FluentAssertions;
using FluentAssertions.Execution;
using OpenWSFZ.Ft8;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Ft8Decoder: CycleFramer UTC-grid alignment regression oracle.
///
/// <para>
/// Regression oracle for <c>DEFECT-capture-clock-drift-silent-decode-loss.md</c>, reopened
/// 2026-08-02; implements the oracle specified in
/// <c>dev-tasks/2026-08-02-reopen-cycleframer-clock-drift-still-present-after-pr118.md</c> §4
/// and the design at
/// <c>qa/cycleframer-alignment-replay/2026-08-02-1813-architect-design-cycleframer-grid-realignment.md</c> §4.
/// </para>
///
/// <para>
/// <b>This file replaces an oracle that could not fail.</b> Its predecessor computed ground truth
/// as <c>startUtc + lastIdx * SamplesPerCycle / effectiveHz</c> — the <em>drift-inclusive</em>
/// instant the window actually opened — and asserted the emitted timestamp matched it. That is
/// label honesty, and PR #118 made it identically zero by construction by reading
/// <c>_clock.UtcNow</c> at window open. The window could walk arbitrarily far off the UTC
/// 15-second grid and the test stayed green. It did, for 43.6 h of live capture, at 48 ppm.
/// </para>
///
/// <para>
/// <b>Two assertions, and the second is the load-bearing one.</b>
/// </para>
/// <list type="number">
/// <item>
/// <b>Grid offset</b> — the emitted <c>CycleStart</c> must sit on the UTC 15-second grid, since
/// FT8 transmissions start at <c>second % 15 == 0</c> and a window labelled off-grid is by
/// definition a window opened off-grid. Necessary, and required by the design's §4 — but on its
/// own it is <b>defeatable</b>: the fix assigns <c>cycleStart = G_next</c>, so an implementation
/// that snaps the label and never touches sample consumption passes it with zero error while the
/// audio stays exactly as misaligned as it is today. That would be strictly worse than the status
/// quo, because the label would then lie.
/// </item>
/// <item>
/// <b>Sample consumption</b> — which source samples actually landed in the window. To hold a
/// 15 s wall-clock window on a device running at <c>effectiveHz</c>, the framer must consume
/// <c>effectiveHz x 15</c> source samples per cycle, not a fixed 180 000. Over N cycles a broken
/// framer sits at <c>N x 180 000</c> and a fixed one at <c>~effectiveHz x 15 x N</c> — a
/// divergence of ~8.7 samples per cycle at 48.4 ppm. Every sample carries its own source index
/// (see <see cref="SimulatedCaptureDevice"/>), so this is read directly out of the emitted PCM.
/// <b>Current <c>main</c>, a label-only fix, and a label-snap fix all fail it. Only a fix that
/// moves the window passes.</b>
/// </item>
/// </list>
///
/// <para>
/// <b>Expected red values against unfixed <c>main</c></b>, per the dev-task §4.3.1: ~4.1 s of
/// grid offset after 24 h at 48.4 ppm, against a 0.2 s tolerance; and ~50 000 samples of
/// consumption divergence, against a 3 000-sample clamp. Both were confirmed red before the fix
/// was written. The 0.2 s tolerance is unchanged from the predecessor oracle — the number was
/// always right, it was the reference it was compared against that was wrong.
/// </para>
///
/// <para>
/// No test here touches real audio, a real clock, or a live session. All four run in-process
/// against <see cref="SimulatedCaptureDevice"/> and <see cref="WindowRecorder"/>, single-threaded
/// and fully deterministic.
/// </para>
/// </summary>
public sealed class CycleFramerClockDriftOracleTests
{
    private const int SampleRate        = 12_000;
    private const int CycleDurationSecs = 15;
    private const int SamplesPerCycle   = SampleRate * CycleDurationSecs; // 180 000

    private const long CycleTicks = CycleDurationSecs * TimeSpan.TicksPerSecond;

    /// <summary>
    /// Sample rate measured on the affected capture device (FT-991A via USB Audio CODEC):
    /// 48.4 ppm slow against the nominal 12 000 Hz the framer assumes. Reproduces the
    /// +0.173 s/h observed in production across four independent uptime epochs.
    /// </summary>
    private const double DriftedHz = 11_999.42;

    /// <summary>
    /// Samples per delivered buffer, matching the real capture sources (<c>WasapiAudioSource</c>
    /// reads into a 2048-sample buffer; <c>ArecordAudioSource</c>/<c>SoxAudioSource</c> use
    /// <c>ChunkBytes = 2048 * sizeof(float)</c>). 2048 samples is ~171 ms at 12 kHz, so this is
    /// also the sub-chunk timing granularity the fix has to survive — deliberately not idealised.
    /// </summary>
    private const int ChunkSamples = 2048;

    /// <summary>
    /// Acceptance tolerance for window alignment against the UTC grid. Derived from measured
    /// decode loss, not taste (dev-task §5): &lt;0.2 s costs nothing measurable, ~1.0 s costs
    /// -3.8%, ~2.0 s costs -29.8%. Unchanged from the predecessor oracle.
    /// </summary>
    private const double ToleranceSeconds = 0.2;

    /// <summary>
    /// The largest realignment a single cycle may apply, in samples — 250 ms at 12 kHz, per the
    /// design's §3 property 4. Declared here independently of <c>src/</c> so this oracle carries
    /// its own ground truth: a 48 ppm crystal never approaches the cap (it needs ~9 samples per
    /// cycle), while a genuine clock step is spread over several cycles instead of discarding or
    /// duplicating a large block at once.
    /// </summary>
    private const int MaxCorrectionSamples = 3_000;

    // ── Case 1: sustained crystal drift over a 24 h session ───────────────────

    [Fact(DisplayName =
        "Oracle (grid alignment): 24h at the measured 48.4ppm-slow capture clock must hold the " +
        "capture window on the UTC 15s grid — both in the emitted label AND in which source " +
        "samples land in the window")]
    public async Task RunAsync_24hAt48ppmSlowClock_HoldsWindowOnTheUtcGrid()
    {
        var startUtc = new DateTime(2026, 1, 1, 0, 0, 0, DateTimeKind.Utc); // exactly on a grid line
        var clock    = new FakeClock(startUtc);

        const double simulatedRealSeconds = 24 * 3600;
        long totalSamples = (long)Math.Round(DriftedHz * simulatedRealSeconds);

        var device   = new SimulatedCaptureDevice(clock, startUtc, DriftedHz, ChunkSamples, totalSamples);
        var recorder = new WindowRecorder();
        var framer   = new CycleFramer(device, clock);

        await framer.RunAsync(recorder, CancellationToken.None);

        var windows = recorder.Windows;
        windows.Should().HaveCountGreaterThan(5_000,
            "sanity check: 24h of 15s windows must be thousands of emissions — if this fails the " +
            "harness is broken, not CycleFramer");
        windows.Should().AllSatisfy(w => w.Length.Should().Be(SamplesPerCycle,
            "every emitted buffer must still be exactly 180 000 samples — realignment pads or " +
            "trims the tail, it never changes what the decoder is handed"));

        // Both assertions are evaluated in one scope so a failing run reports BOTH numbers.
        // That is deliberate: the dev-task §4.3.1 requires each to be independently red against
        // unfixed main, and a short-circuiting first assertion would leave the second unproven.
        using var scope = new AssertionScope();

        // ── Assertion 1: the label must be on the grid ────────────────────────
        var (worstOffGridIdx, worstOffGrid) = WorstOffGrid(windows);

        Math.Abs(worstOffGrid).Should().BeLessThan(ToleranceSeconds,
            $"window {worstOffGridIdx} of {windows.Count} is {worstOffGrid:F3}s off the UTC " +
            "15-second grid. FT8 transmissions start at second % 15 == 0, so a window that opens " +
            "off-grid is decoding a time-shifted view of a protocol with a fixed time grid. " +
            "Against unfixed main this reads ~4.1s after 24h at 48.4ppm, because RunAsync frames " +
            "by counting to 180 000 samples and nothing ever re-anchors the boundary to UTC — " +
            "see DEFECT-capture-clock-drift-silent-decode-loss.md");

        // ── Assertion 2: the AUDIO must be on the grid, not merely the label ──
        var (worstDriftIdx, worstDriftSamples) = WorstSampleMisalignment(device, windows);

        Math.Abs(worstDriftSamples).Should().BeLessThan(MaxCorrectionSamples,
            $"window {worstDriftIdx} of {windows.Count} begins {worstDriftSamples} source samples " +
            $"({worstDriftSamples / (double)SampleRate:F3}s) away from where a window carrying its " +
            "own grid label must begin. This is the assertion a label-only or label-snapping fix " +
            "cannot satisfy: to hold a 15s wall-clock window on a device running at " +
            $"{DriftedHz}Hz the framer must consume ~{DriftedHz * CycleDurationSecs:F0} source " +
            $"samples per cycle, not {SamplesPerCycle}. Unfixed main diverges by ~8.7 samples per " +
            "cycle and reads ~50 000 samples here — see the dev-task §4.2");
    }

    // ── Case 2: a single dropped chunk mid-stream ─────────────────────────────

    [Fact(DisplayName =
        "Oracle (grid alignment): a silently dropped chunk knocks the window off-grid, and the " +
        "framer must walk it back — within the per-cycle clamp, never in one jump")]
    public async Task RunAsync_DroppedChunkMidStream_RealignsToTheGridWithinTheClamp()
    {
        // Nominal rate: any misalignment observed here is attributable solely to the drop.
        const double nominalHz    = SampleRate;
        const int    cleanCycles  = 4;
        const int    totalCycles  = 24;
        const long   droppedSamples = 2 * SampleRate; // 2 s of audio that never arrives

        var startUtc = new DateTime(2026, 1, 1, 0, 0, 0, DateTimeKind.Utc);
        var clock    = new FakeClock(startUtc);

        var device = new SimulatedCaptureDevice(
            clock, startUtc, nominalHz, ChunkSamples,
            totalSamples: (long)SamplesPerCycle * totalCycles + droppedSamples);
        device.ScheduleDrop(atSample: (long)SamplesPerCycle * cleanCycles, samples: droppedSamples);

        var recorder = new WindowRecorder();
        var framer   = new CycleFramer(device, clock);

        await framer.RunAsync(recorder, CancellationToken.None);

        var windows = recorder.Windows;
        windows.Should().HaveCountGreaterThan(cleanCycles + 12,
            "the run must be long enough to observe both the disturbance and the recovery");

        // Pre-drop windows are exact — establishes a clean baseline.
        for (int k = 1; k < cleanCycles; k++)
        {
            double offGrid = SignedOffGridSeconds(windows[k].CycleStart);
            Math.Abs(offGrid).Should().BeLessThan(ToleranceSeconds,
                $"window {k} precedes the drop and must sit on the grid");
        }

        // No single cycle may absorb the whole 2 s: that would discard or duplicate 24 000
        // samples at once. The clamp exists to spread it.
        AssertNoCycleExceedsTheClamp(device, windows);

        // 2 s at a 0.25 s clamp converges in ~8 cycles; allow 12 before requiring the bar.
        const int convergenceCycles = 12;
        int firstSettled = cleanCycles + convergenceCycles;
        firstSettled.Should().BeLessThan(windows.Count,
            "the harness must produce windows past the convergence budget");

        for (int k = firstSettled; k < windows.Count; k++)
        {
            double misalignSecs = SampleMisalignment(device, windows[k]) / (double)SampleRate;
            Math.Abs(misalignSecs).Should().BeLessThan(ToleranceSeconds,
                $"window {k} is {misalignSecs:F3}s off the grid, {k - cleanCycles} cycles after a " +
                "2 s chunk was silently dropped. A dropped chunk shifts the window off-grid " +
                "permanently on unfixed main — the framer keeps counting to 180 000 as if it had " +
                "seen every sample the device ever produced, and has no mechanism to notice. " +
                "Per-cycle re-anchoring against the UTC grid must walk it back");
        }
    }

    // ── Case 3: restart-punctuated multi-epoch operation ──────────────────────

    [Fact(DisplayName =
        "Oracle (grid alignment): drift stays bounded across restart-punctuated epochs — the " +
        "observed live failure shape, where a restart resets the accumulated offset and hides " +
        "unbounded growth")]
    public async Task RunAsync_RestartPunctuatedEpochs_StaysOnGridWithinEveryEpoch()
    {
        // The 43.6 h live corpus contained three restarts, producing three reset-and-reaccumulate
        // sawtooth cycles. A single-epoch design cannot distinguish "bounded forever" from
        // "bounded until the next restart happened to arrive first".
        const int    epochs           = 3;
        const double epochRealSeconds = 4 * 3600;

        var clock = new FakeClock(new DateTime(2026, 1, 1, 0, 0, 0, DateTimeKind.Utc));

        // Epoch 1 starts on a grid line; the restarts deliberately do not, so each subsequent
        // epoch also exercises the leading-silence start-up path from a mid-cycle position.
        var epochOrigin = clock.UtcNow;

        for (int epoch = 0; epoch < epochs; epoch++)
        {
            long totalSamples = (long)Math.Round(DriftedHz * epochRealSeconds);

            var device   = new SimulatedCaptureDevice(clock, epochOrigin, DriftedHz, ChunkSamples, totalSamples);
            var recorder = new WindowRecorder();
            var framer   = new CycleFramer(device, clock);

            await framer.RunAsync(recorder, CancellationToken.None);

            var windows = recorder.Windows;
            windows.Should().HaveCountGreaterThan(900, $"epoch {epoch} must run for ~4 simulated hours");

            // Window 0 carries start-up leading silence, so its first sample is padding rather
            // than a ramp marker — skip it and assert on every window thereafter.
            var settled = windows.Skip(1).ToList();

            var (worstOffGridIdx, worstOffGrid) = WorstOffGrid(settled);
            Math.Abs(worstOffGrid).Should().BeLessThan(ToleranceSeconds,
                $"epoch {epoch}, window {worstOffGridIdx + 1}: label is {worstOffGrid:F3}s off-grid");

            var (worstDriftIdx, worstDriftSamples) = WorstSampleMisalignment(device, settled);
            Math.Abs(worstDriftSamples).Should().BeLessThan(MaxCorrectionSamples,
                $"epoch {epoch}, window {worstDriftIdx + 1}: audio is {worstDriftSamples} samples " +
                $"({worstDriftSamples / (double)SampleRate:F3}s) off-grid. Drift must be bounded " +
                "*within* an epoch, not merely reset by the next restart — the live sawtooth is " +
                "what unbounded-until-restart looks like");

            // Restart: the process comes back up mid-cycle, some seconds later.
            epochOrigin = clock.UtcNow.AddSeconds(3.7);
            clock.UtcNow = epochOrigin;
        }
    }

    // ── Case 4: a system-clock step (NTP correction, sleep/resume, VM pause) ──

    [Theory(DisplayName =
        "Oracle (grid alignment): an NTP-sized clock step is absorbed within the per-cycle clamp " +
        "and the window reconverges — no single cycle may discard or duplicate a large block")]
    [InlineData(+1.5)]
    [InlineData(-1.5)]
    public async Task RunAsync_SystemClockStep_ConvergesWithoutExceedingTheClamp(double stepSeconds)
    {
        const double nominalHz     = SampleRate; // no crystal drift: the step is the only disturbance
        const int    cyclesBefore  = 4;
        const int    totalCycles   = 32;

        var startUtc = new DateTime(2026, 1, 1, 0, 0, 0, DateTimeKind.Utc);
        var clock    = new FakeClock(startUtc);

        var device = new SimulatedCaptureDevice(
            clock, startUtc, nominalHz, ChunkSamples,
            totalSamples: (long)SamplesPerCycle * totalCycles);
        device.ScheduleClockStep(
            atSample: (long)SamplesPerCycle * cyclesBefore,
            step:     TimeSpan.FromSeconds(stepSeconds));

        var recorder = new WindowRecorder();
        var framer   = new CycleFramer(device, clock);

        await framer.RunAsync(recorder, CancellationToken.None);

        var windows = recorder.Windows;
        windows.Should().HaveCountGreaterThan(totalCycles - 4,
            "the run must be long enough to observe the step and the recovery");

        // The safety valve: a 1.5 s step is 18 000 samples. Absorbing it in one cycle would
        // discard or duplicate a tenth of a window; the clamp must spread it over ~6 cycles.
        AssertNoCycleExceedsTheClamp(device, windows);

        // 1.5 s at a 0.25 s clamp converges in 6 cycles; allow 12.
        int firstSettled = cyclesBefore + 12;
        firstSettled.Should().BeLessThan(windows.Count);

        for (int k = firstSettled; k < windows.Count; k++)
        {
            double misalignSecs = SampleMisalignment(device, windows[k]) / (double)SampleRate;
            Math.Abs(misalignSecs).Should().BeLessThan(ToleranceSeconds,
                $"window {k} is {misalignSecs:F3}s off-grid, {k - cyclesBefore} cycles after a " +
                $"{stepSeconds:+0.0;-0.0}s system-clock step. The window must reconverge on the " +
                "corrected clock rather than staying permanently offset by the step");

            double offGrid = SignedOffGridSeconds(windows[k].CycleStart);
            Math.Abs(offGrid).Should().BeLessThan(ToleranceSeconds,
                $"window {k}'s label is {offGrid:F3}s off the UTC grid after the step");
        }
    }

    // ── Helpers: the oracle's own ground truth, independent of src/ ───────────

    /// <summary>
    /// Signed distance from <paramref name="utc"/> to the <em>nearest</em> UTC 15-second grid
    /// line, in seconds. Computed from ticks here rather than by calling into
    /// <see cref="CycleFramer"/> — an oracle that borrows the implementation's notion of "the
    /// grid" cannot detect the implementation getting the grid wrong.
    /// </summary>
    private static double SignedOffGridSeconds(DateTime utc)
    {
        long into = utc.Ticks % CycleTicks;
        if (into * 2 > CycleTicks)
        {
            into -= CycleTicks;
        }

        return into / (double)TimeSpan.TicksPerSecond;
    }

    /// <summary>
    /// The UTC 15-second grid line nearest <paramref name="utc"/>. Computed from ticks, like
    /// <see cref="SignedOffGridSeconds"/>, rather than by calling into <see cref="CycleFramer"/>.
    /// </summary>
    private static DateTime NearestGridLine(DateTime utc)
    {
        long into   = utc.Ticks % CycleTicks;
        long anchor = utc.Ticks - into;
        return new DateTime(into * 2 > CycleTicks ? anchor + CycleTicks : anchor, DateTimeKind.Utc);
    }

    /// <summary>
    /// How far, in source samples, a window's audio begins from where the <b>UTC grid line it
    /// belongs to</b> says it must begin. Positive means the window contains audio captured later
    /// than the grid demands.
    ///
    /// <para>
    /// <b>The snap to the grid line is what stops this being circular</b>, and it is the whole
    /// content of the dev-task's §4.2. Measured against the emitted label directly, this quantity
    /// is identically zero on unfixed <c>main</c> — PR #118 reads <c>_clock.UtcNow</c> at window
    /// open, so the label is a truthful report of wherever the window drifted to, and audio and
    /// label agree perfectly while both sit seconds away from the grid. Measured against the
    /// nearest grid line instead, all three broken shapes fail:
    /// </para>
    /// <list type="bullet">
    /// <item><b>unfixed main</b> — label is 4.3 s off-grid, so the nearest grid line is ~4.3 s
    /// away from where the audio actually starts: ~50 000 samples;</item>
    /// <item><b>a label-only fix</b> — same as above;</item>
    /// <item><b>a label-snapping fix</b> — label sits exactly on the grid line while the audio is
    /// still at <c>k x 180 000</c>: the same ~50 000 samples, and now the label lies about it.</item>
    /// </list>
    /// <para>
    /// Only moving the window closes it.
    /// </para>
    /// </summary>
    private static long SampleMisalignment(SimulatedCaptureDevice device, WindowRecorder.RecordedWindow window)
    {
        double expected = device.ExpectedFirstSampleIndex(NearestGridLine(window.CycleStart));
        long   actual   = GridAlignmentHarness.UnwrapSampleIndex((long)Math.Round(expected), window.FirstSample);
        return actual - (long)Math.Round(expected);
    }

    private static (int Index, double OffGridSeconds) WorstOffGrid(IReadOnlyList<WindowRecorder.RecordedWindow> windows)
    {
        int    worstIdx = 0;
        double worst    = 0;

        for (int k = 0; k < windows.Count; k++)
        {
            double offGrid = SignedOffGridSeconds(windows[k].CycleStart);
            if (Math.Abs(offGrid) > Math.Abs(worst))
            {
                worst    = offGrid;
                worstIdx = k;
            }
        }

        return (worstIdx, worst);
    }

    private static (int Index, long Samples) WorstSampleMisalignment(
        SimulatedCaptureDevice device,
        IReadOnlyList<WindowRecorder.RecordedWindow> windows)
    {
        int  worstIdx = 0;
        long worst    = 0;

        for (int k = 0; k < windows.Count; k++)
        {
            long misalign = SampleMisalignment(device, windows[k]);
            if (Math.Abs(misalign) > Math.Abs(worst))
            {
                worst    = misalign;
                worstIdx = k;
            }
        }

        return (worstIdx, worst);
    }

    /// <summary>
    /// Asserts that consecutive windows never differ in source consumption from
    /// <see cref="SamplesPerCycle"/> by more than <see cref="MaxCorrectionSamples"/> — the
    /// safety valve of the design's §3 property 4, measured from the audio itself.
    /// </summary>
    private static void AssertNoCycleExceedsTheClamp(
        SimulatedCaptureDevice device,
        IReadOnlyList<WindowRecorder.RecordedWindow> windows)
    {
        for (int k = 2; k < windows.Count; k++)
        {
            long prev = FirstSampleIndex(device, windows[k - 1]);
            long here = FirstSampleIndex(device, windows[k]);
            long consumed = here - prev;

            Math.Abs(consumed - SamplesPerCycle).Should().BeLessThanOrEqualTo(MaxCorrectionSamples,
                $"window {k} consumed {consumed} source samples, {consumed - SamplesPerCycle} away " +
                $"from the nominal {SamplesPerCycle}. No single cycle may realign by more than " +
                $"{MaxCorrectionSamples} samples ({MaxCorrectionSamples / (double)SampleRate:F3}s): " +
                "a clock step must converge over several cycles rather than discarding or " +
                "duplicating a large block of audio in one");
        }
    }

    private static long FirstSampleIndex(SimulatedCaptureDevice device, WindowRecorder.RecordedWindow window)
    {
        double expected = device.ExpectedFirstSampleIndex(NearestGridLine(window.CycleStart));
        return GridAlignmentHarness.UnwrapSampleIndex((long)Math.Round(expected), window.FirstSample);
    }
}
