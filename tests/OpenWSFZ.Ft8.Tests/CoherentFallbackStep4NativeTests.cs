using FluentAssertions;
using OpenWSFZ.Ft8.Interop;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// COH-FALLBACK step 4 (shim 20260069) against the REAL native library: the per-candidate exports (<c>ft8_coherent_fallback_plan</c>,
/// <c>_ctx_new</c>, <c>_process</c>) driven by the parallel runner give, for 1, 2 and 8 workers, exactly the rows and counts that the
/// single-thread <c>ft8_coherent_fallback_run</c> gives on the same snapshot. The thread counts are the test's own parameters, so the result
/// does not depend on how many cores the machine has. Synthetic content only (NFR-021).
/// </summary>
public sealed class CoherentFallbackStep4NativeTests
{
    private const int PcmSamples = 180_000;
    private const double WeakNoiseSigma = 3.5;
    private static readonly int[] Seeds = [1, 3, 4];

    private static float[] Synthesise(int seed)
    {
        var tones = new byte[79];
        Ft8LibInterop.EncodeMessage("CQ Q1ABC FN20", tones);
        var pcm = new float[PcmSamples];
        double phase = 0.0;
        long n0 = (long)Math.Round(0.55 * 12000.0);
        for (int s = 0; s < tones.Length; s++)
        {
            double f = 1500.0 + 6.25 * tones[s];
            for (int i = 0; i < 1920; i++)
            {
                long idx = n0 + (long)s * 1920 + i;
                if (idx >= 0 && idx < PcmSamples) pcm[idx] += (float)(0.3 * Math.Sin(phase));
                phase += 2.0 * Math.PI * f / 12000.0;
            }
        }
        var rng = new Random(seed);
        for (int i = 0; i < PcmSamples; i++)
        {
            double u1 = 1.0 - rng.NextDouble(), u2 = rng.NextDouble();
            pcm[i] += (float)(WeakNoiseSigma * Math.Sqrt(-2.0 * Math.Log(u1)) * Math.Cos(2.0 * Math.PI * u2));
        }
        return pcm;
    }

    private static byte[] DecodeAndSnapshot(float[] pcm)
    {
        Ft8LibInterop.DecodeAll(pcm);
        return Ft8LibInterop.CohFallbackSnapshot();   // same thread, nothing in between
    }

    private static string Key(CohFallbackRow r)
        => $"{r.FreqHz:R}/{r.DtS:R}/{r.OutFreqHz:R}/{r.OutDtS:R}/{r.Pass}/{r.Edge}/{r.State}/{r.SnrDb}/{r.F1bDb:R}/{Convert.ToHexString(r.Payload)}";

    [Theory(DisplayName = "R15: with the real library, 1, 2 and 8 workers give the single-thread run's rows (every field) and counts, in candidate order")]
    [InlineData(1)]
    [InlineData(2)]
    [InlineData(8)]
    public void ParallelRows_EqualTheSingleThreadRun(int workers)
    {
        foreach (int seed in Seeds)
        {
            var pcm = Synthesise(seed);
            var snap = DecodeAndSnapshot(pcm);

            var reference = Ft8LibInterop.CohFallbackRun(pcm, snap, -1, CancellationToken.None);
            var parallel = CohFallbackParallelRunner.Run(CohFallbackLibBackend.Instance, pcm, snap, -1, workers, CancellationToken.None)!;

            reference.Stats.Eligible.Should().BeGreaterThan(8, "seed {0}: enough candidates to share between workers", seed);
            parallel.Rows.Select(Key).Should().Equal(reference.Rows.Select(Key), "seed {0}, {1} workers", seed, workers);
            parallel.Workers.Should().Be(workers);

            var (p, r) = (parallel.Stats, reference.Stats);
            (p.Candidates, p.Decoded, p.DupPosition, p.Eligible, p.Attempted, p.CrcOk, p.CrcNew, p.F1bComputed, p.Gated, p.Abandoned, p.Edge)
                .Should().Be((r.Candidates, r.Decoded, r.DupPosition, r.Eligible, r.Attempted, r.CrcOk, r.CrcNew, r.F1bComputed, r.Gated, r.Abandoned, r.Edge),
                              "seed {0}, {1} workers", seed, workers);
        }
    }

    [Fact(DisplayName = "R15: the plan is the single-thread run's candidate list - the same eligible count, ordinals in increasing snapshot order, every row pre-filled as abandoned")]
    public void Plan_MatchesTheRun()
    {
        var pcm = Synthesise(3);
        var snap = DecodeAndSnapshot(pcm);
        var reference = Ft8LibInterop.CohFallbackRun(pcm, snap, 0, CancellationToken.None);   // budget 0: every eligible row, none attempted

        var plan = Ft8LibInterop.CohFallbackMakePlan(snap);

        plan.Stats.Eligible.Should().Be(reference.Stats.Eligible);
        (plan.Stats.Candidates, plan.Stats.Decoded, plan.Stats.DupPosition).Should().Be((reference.Stats.Candidates, reference.Stats.Decoded, reference.Stats.DupPosition));
        plan.CandidateIndex.Should().BeInAscendingOrder().And.OnlyHaveUniqueItems();
        plan.Rows.Select(Key).Should().Equal(reference.Rows.Select(Key));
        plan.Rows.Should().OnlyContain(r => r.State == CohFallbackState.Abandoned);
    }

    [Fact(DisplayName = "R7: through the real library an already-passed deadline abandons every candidate - none attempted, none published, all counted")]
    public void Parallel_ZeroBudget_AbandonsAll()
    {
        var pcm = Synthesise(3);
        var snap = DecodeAndSnapshot(pcm);

        var result = CohFallbackParallelRunner.Run(CohFallbackLibBackend.Instance, pcm, snap, 0.0, 8, CancellationToken.None)!;

        result.Stats.Eligible.Should().BeGreaterThan(0);
        (result.Stats.Attempted, result.Stats.Abandoned).Should().Be((0, result.Stats.Eligible));
        result.Rows.Should().OnlyContain(r => r.State == CohFallbackState.Abandoned);
        CoherentFallbackSelector.Select(result.Rows).Should().BeEmpty();
    }

    [Fact(DisplayName = "R7: through the real library a stop mid-run leaves a prefix of finished rows and an abandoned tail that equals the plan's rows")]
    public void Parallel_Stop_LeavesAPrefix()
    {
        var pcm = Synthesise(3);
        var snap = DecodeAndSnapshot(pcm);
        var full = CohFallbackParallelRunner.Run(CohFallbackLibBackend.Instance, pcm, snap, -1, 1, CancellationToken.None)!;
        var plan = Ft8LibInterop.CohFallbackMakePlan(snap);

        // a stop from a worker's own progress: the backend wrapper cancels after the fifth candidate, so the cut point is deterministic with one worker
        using var cts = new CancellationTokenSource();
        var cutting = new CancelAfter(CohFallbackLibBackend.Instance, cts, after: 5);
        var cut = CohFallbackParallelRunner.Run(cutting, pcm, snap, -1, 1, cts.Token)!;

        cut.Stats.Attempted.Should().Be(5);
        cut.Stats.Abandoned.Should().Be(full.Stats.Eligible - 5);
        cut.Rows.Take(5).Select(Key).Should().Equal(full.Rows.Take(5).Select(Key), "the finished prefix is what the uninterrupted run produced");
        cut.Rows.Skip(5).Select(Key).Should().Equal(plan.Rows.Skip(5).Select(Key), "the tail is untouched: abandoned, never started");
    }

    private sealed class CancelAfter(ICohFallbackBackend inner, CancellationTokenSource cts, int after) : ICohFallbackBackend
    {
        private int _count;
        public CohFallbackPlan? Plan(byte[] snapshot) => inner.Plan(snapshot);
        public ICohFallbackWorker CreateWorker() => new W(inner.CreateWorker(), this);

        private sealed class W(ICohFallbackWorker real, CancelAfter owner) : ICohFallbackWorker
        {
            public CohFallbackRow Process(float[] pcm, byte[] snapshot, int candidateIndex)
            {
                var row = real.Process(pcm, snapshot, candidateIndex);
                if (Interlocked.Increment(ref owner._count) == owner._after) owner._cts.Cancel();
                return row;
            }
            public CohFallbackStats Accumulated => real.Accumulated;
            public void Dispose() => real.Dispose();
        }

        private int _after => after;
        private CancellationTokenSource _cts => cts;
    }
}
