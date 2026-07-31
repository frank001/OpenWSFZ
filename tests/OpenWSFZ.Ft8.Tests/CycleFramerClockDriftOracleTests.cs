using System.Threading.Channels;
using FluentAssertions;
using OpenWSFZ.Ft8;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Ft8Decoder: CycleFramer clock-drift regression oracle.
///
/// <para>
/// Regression oracle for <c>DEFECT-capture-clock-drift-silent-decode-loss.md</c> — dev-task
/// 1a of the drift fix, per
/// <c>qa/cycleframer-alignment-replay/2026-07-31-0910-architect-to-qa-consolidated-handoff-post-measurements-abc.md</c>
/// §3 task 1. Test-only: asserts a <c>src/</c> invariant, changes no <c>src/</c> behaviour.
/// </para>
///
/// <para>
/// <see cref="CycleFramer.RunAsync"/> reads <c>IClock.UtcNow</c> exactly once, at start-up,
/// then advances <c>cycleStart</c> purely by arithmetic (<c>cycleStart.AddSeconds(15)</c> per
/// completed window). It never re-consults the clock, so it has no notion of elapsed real
/// time other than the count of samples it has been handed. Two independent field conditions
/// silently defeat that assumption:
/// </para>
///
/// <list type="bullet">
/// <item>a capture-device crystal running at other than exactly 12 000 Hz — measured on the
/// affected device at 48.4 ppm slow (an effective 11 999.42 Hz) — see
/// <see cref="RunAsync_24hAt48ppmSlowClock_BoundaryDriftsWellBeyondTolerance"/>;</item>
/// <item>any single dropped/lost chunk upstream — <c>WasapiAudioSource</c>'s buffer-overrun
/// and channel-write-failure branches are both warn-only — see
/// <see cref="RunAsync_DroppedChunkMidStream_PermanentlyShiftsAllSubsequentBoundaries"/>.</item>
/// </list>
///
/// <para>
/// Both assert the invariant dev-task 1b's fix must establish: emitted <c>CycleStart</c> stays
/// within <see cref="ToleranceSeconds"/> of true UTC. <b>Both are expected to FAIL against
/// current `main`</b> — per the handoff, "the oracle lands first, and it must go red against
/// current `main` before the fix is written. A regression test that does not fail beforehand
/// proves nothing." Neither test touches real audio, a real clock, or a live session; both
/// run in-process against a <see cref="FakeClock"/> and an in-memory channel.
/// </para>
/// </summary>
public sealed class CycleFramerClockDriftOracleTests
{
    private const int SampleRate        = 12_000;
    private const int CycleDurationSecs = 15;
    private const int SamplesPerCycle   = SampleRate * CycleDurationSecs; // 180 000

    /// <summary>
    /// Acceptance tolerance for cycle-boundary error against true UTC. Derived, not guessed:
    /// per the 2026-07-31-0910 handoff §3, the DT cliff is bracketed at 2.34-2.48 s; holding
    /// boundary error under ~0.2 s is an order of magnitude inside that.
    /// </summary>
    private const double ToleranceSeconds = 0.2;

    // ── Case 1: sustained crystal drift over a 24 h session ───────────────────

    [Fact(DisplayName =
        "Oracle (1a): 24h simulated at the measured 48.4ppm-slow clock (11999.42Hz effective) " +
        "drifts the emitted cycle boundary far beyond tolerance — must be red against current main")]
    public async Task RunAsync_24hAt48ppmSlowClock_BoundaryDriftsWellBeyondTolerance()
    {
        // The measured effective sample rate of the affected capture device (defect report §7 /
        // 2026-07-31-0029 ruling §2): a crystal 48.4 ppm slow relative to the nominal 12 000 Hz
        // CycleFramer assumes.
        const double effectiveHz = 11_999.42;

        var startUtc = new DateTime(2026, 1, 1, 0, 0, 0, DateTimeKind.Utc); // exactly on a cycle boundary
        var clock    = new FakeClock(startUtc);

        var source = Channel.CreateUnbounded<float[]>();
        var output = Channel.CreateUnbounded<(float[], DateTime, double?)>();
        var framer = new CycleFramer(source.Reader, clock);

        using var cts  = new CancellationTokenSource(TimeSpan.FromSeconds(60));
        var framerTask = Task.Run(() => framer.RunAsync(output.Writer, cts.Token));

        // Simulate 24 true-UTC hours of continuous capture at the drifted rate.
        const double simulatedRealSeconds = 24 * 3600;
        long totalSamples = (long)Math.Round(effectiveHz * simulatedRealSeconds);

        long completeWindows = totalSamples / SamplesPerCycle;
        completeWindows.Should().BeGreaterThan(1000,
            "sanity check: 24h at ~12kHz must yield thousands of 15s windows — if this fails " +
            "the test's own arithmetic is broken, not CycleFramer");

        // Feed and drain one window at a time, advancing the FakeClock by the real seconds
        // this window's worth of samples actually took a device running at effectiveHz to
        // produce, BEFORE handing the samples over — and draining the corresponding emission
        // before moving to the next window. This keeps the (otherwise static) FakeClock
        // synchronized with CycleFramer's own consumption instead of racing ahead of or
        // behind it: the fix reads _clock.UtcNow lazily, the instant it starts accumulating
        // a fresh window, so the clock must actually reflect "now" at that instant for the
        // simulation to mean anything.
        double realSecondsPerWindow = SamplesPerCycle / effectiveHz;
        var emitted = new List<DateTime>();
        for (long i = 0; i < completeWindows; i++)
        {
            if (i > 0)
            {
                clock.Advance(TimeSpan.FromSeconds(realSecondsPerWindow));
            }

            await source.Writer.WriteAsync(new float[SamplesPerCycle], cts.Token);
            var (_, cycleStart, _) = await output.Reader.ReadAsync(cts.Token);
            emitted.Add(cycleStart);
        }
        source.Writer.Complete();

        cts.Cancel();
        try { await framerTask; } catch (OperationCanceledException) { /* expected teardown */ }

        emitted.Should().HaveCount((int)completeWindows,
            "every complete 180000-sample window fed must be emitted exactly once");

        // Ground truth: the true UTC instant at which the last window actually opened, given
        // the source really produces samples at effectiveHz (not the nominal 12000 Hz the
        // framer assumes). Computed from first principles, not hand-picked.
        int lastIdx         = emitted.Count - 1;
        double trueOpenSecs = (lastIdx * (double)SamplesPerCycle) / effectiveHz;
        DateTime trueOpen   = startUtc.AddSeconds(trueOpenSecs);

        double driftSeconds = (emitted[lastIdx] - trueOpen).TotalSeconds;

        Math.Abs(driftSeconds).Should().BeLessThan(ToleranceSeconds,
            $"CycleFramer must not let cycle boundaries drift more than {ToleranceSeconds}s " +
            "from true UTC over a 24h session; a 48.4ppm-slow clock currently drifts the " +
            $"boundary by ~{driftSeconds:F2}s because RunAsync only reads the clock once at " +
            "start-up and advances cycleStart by pure arithmetic thereafter, never re-syncing " +
            "— see DEFECT-capture-clock-drift-silent-decode-loss.md");
    }

    // ── Case 2: a single dropped chunk mid-stream, independent of any clock drift ─

    [Fact(DisplayName =
        "Oracle (1a): a single dropped chunk mid-stream permanently shifts every subsequent " +
        "cycle boundary, independent of clock drift, with no way for the framer to detect or " +
        "recover — must be red against current main")]
    public async Task RunAsync_DroppedChunkMidStream_PermanentlyShiftsAllSubsequentBoundaries()
    {
        var startUtc = new DateTime(2026, 1, 1, 0, 0, 0, DateTimeKind.Utc);
        var clock    = new FakeClock(startUtc);

        var source = Channel.CreateUnbounded<float[]>();
        var output = Channel.CreateUnbounded<(float[], DateTime, double?)>();
        var framer = new CycleFramer(source.Reader, clock);

        using var cts  = new CancellationTokenSource(TimeSpan.FromSeconds(10));
        var framerTask = Task.Run(() => framer.RunAsync(output.Writer, cts.Token));

        var emitted = new List<DateTime>();

        // Three clean windows at the exact nominal rate — no drift — so any error observed
        // later is attributable solely to the drop, not to a rate mismatch. Fed and drained
        // one window at a time (see test 1's comment for why: the FakeClock must be
        // synchronized with CycleFramer's own lazy resync, not raced ahead of it).
        const int cleanWindows = 3;
        for (int w = 0; w < cleanWindows; w++)
        {
            if (w > 0) clock.Advance(TimeSpan.FromSeconds(CycleDurationSecs));

            await source.Writer.WriteAsync(new float[SamplesPerCycle], cts.Token);
            var (_, cs, _) = await output.Reader.ReadAsync(cts.Token);
            emitted.Add(cs);
        }

        // Simulate a dropped chunk: per the handoff §4.3, WasapiAudioSource's buffer-overrun
        // and channel-write-failure branches are both warn-only — a chunk the real world
        // produced simply never reaches the channel. Two true-UTC seconds of audio (24000
        // samples) vanish here; CycleFramer is never told — but real wall-clock time still
        // genuinely elapses while it happens, so the FakeClock must advance for it too, on
        // top of the 15s the third clean window's own accumulation took.
        const int droppedSamples = 2 * SampleRate;
        double droppedSeconds = droppedSamples / (double)SampleRate;
        clock.Advance(TimeSpan.FromSeconds(CycleDurationSecs + droppedSeconds));

        // Capture drops mid-cycle in the field, not conveniently on a boundary. Three more
        // clean windows follow so the shift is observed across several subsequent cycles,
        // proving it is a permanent offset rather than a one-cycle blip that self-corrects.
        const int postDropWindows = 3;
        for (int i = 0; i < postDropWindows; i++)
        {
            if (i > 0) clock.Advance(TimeSpan.FromSeconds(CycleDurationSecs));

            await source.Writer.WriteAsync(new float[SamplesPerCycle], cts.Token);
            var (_, cs, _) = await output.Reader.ReadAsync(cts.Token);
            emitted.Add(cs);
        }
        source.Writer.Complete();

        cts.Cancel();
        try { await framerTask; } catch (OperationCanceledException) { /* expected teardown */ }

        emitted.Should().HaveCount(cleanWindows + postDropWindows);

        // Pre-drop windows must be exact — establishes the baseline is clean before the drop.
        for (int k = 0; k < cleanWindows; k++)
        {
            emitted[k].Should().Be(startUtc.AddSeconds(k * CycleDurationSecs),
                $"window {k} precedes the drop and must be exactly on the nominal boundary");
        }

        // Post-drop windows: the dropped audio genuinely took droppedSeconds of true UTC time
        // to (not) arrive, so every true window-open time from here on is shifted later by that
        // amount — but CycleFramer's arithmetic has no way to know that, and keeps counting as
        // if it had seen every sample the real device ever produced.
        for (int i = 0; i < postDropWindows; i++)
        {
            int windowIndex   = cleanWindows + i;
            DateTime trueOpen = startUtc.AddSeconds(windowIndex * CycleDurationSecs + droppedSeconds);
            DateTime claimed  = emitted[windowIndex];
            double driftSecs  = (claimed - trueOpen).TotalSeconds;

            Math.Abs(driftSecs).Should().BeLessThan(ToleranceSeconds,
                $"window {windowIndex} (the {i + 1}-th window after the drop) should recover to " +
                $"within {ToleranceSeconds}s of true UTC; instead it is permanently off by " +
                $"{-driftSecs:F2}s because CycleFramer has no mechanism to detect or absorb a " +
                "dropped chunk it was never re-told about — see DEFECT-capture-clock-drift-" +
                "silent-decode-loss.md and the handoff §4.3 (\"a single stalled consumer does it " +
                "instantly\")");
        }
    }
}
