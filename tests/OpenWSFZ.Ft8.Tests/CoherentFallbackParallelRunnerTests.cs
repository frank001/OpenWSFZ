using FluentAssertions;
using OpenWSFZ.Ft8.Interop;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// COH-FALLBACK step 4, R15 (spec section 14, A14.2): the parallel cycle's scheduling rules, against a FAKE native backend, so they do
/// not depend on the library, the speed of the machine or its core count. Rules under test (see <see cref="CohFallbackParallelRunner"/>):
/// every candidate is run exactly once; the rows are gathered in candidate order whatever the scheduling; the deadline / cancellation is
/// checked before a candidate is claimed, so the candidates run are a prefix of candidate order and the rest are abandoned, counted and
/// never started; a faulting worker stops the run and its exception reaches the caller.
///
/// <para>Scheduling is perturbed with a seeded spin/yield count and, in the order test, with a gate that holds candidate 0 until later
/// candidates have finished; nothing waits on a fixed delay (TESTING_STRATEGY section 11) and the thread count is the test's own
/// parameter, never <see cref="Environment.ProcessorCount"/>.</para>
/// </summary>
public sealed class CoherentFallbackParallelRunnerTests
{
    private static readonly float[] Pcm = new float[180_000];
    private static readonly byte[] Snapshot = [1, 2, 3, 4];

    private static CohFallbackRow Row(int idx, CohFallbackState state)
    {
        var payload = new byte[12];
        payload[0] = (byte)idx;
        payload[1] = (byte)(idx >> 8);
        return new CohFallbackRow(1000f + idx, 0.3f, 1000.3f + idx, 0.31f, 0, false, state, -21, state == CohFallbackState.NewGated ? 12.0 : double.NaN, payload);
    }

    private static int IdOf(CohFallbackRow r) => r.Payload[0] | (r.Payload[1] << 8);

    /// <summary>A scripted backend of <paramref name="n"/> eligible candidates whose snapshot index is 2 * e + 1 (so the index is never the ordinal).</summary>
    private sealed class FakeBackend(int n) : ICohFallbackBackend
    {
        private int _created, _disposed, _processCalls;
        private readonly object _gate = new();
        private readonly List<int> _processed = [];

        public int Created => Volatile.Read(ref _created);
        public int Disposed => Volatile.Read(ref _disposed);
        public int ProcessCalls => Volatile.Read(ref _processCalls);
        public List<int> Processed { get { lock (_gate) return [.. _processed]; } }

        /// <summary>Called inside <c>Process</c> with the eligible ordinal, before the row is returned.</summary>
        public Action<int>? OnProcess { get; set; }
        public bool PlanFails { get; init; }
        public int? ThrowAtOrdinal { get; init; }

        public CohFallbackPlan? Plan(byte[] snapshot)
        {
            if (PlanFails) return null;
            var idx = Enumerable.Range(0, n).Select(e => 2 * e + 1).ToList();
            var rows = Enumerable.Range(0, n).Select(e => Row(e, CohFallbackState.Abandoned)).ToList();
            return new CohFallbackPlan(new CohFallbackStats(n + 3, 3, 0, n, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0), idx, rows);
        }

        public ICohFallbackWorker CreateWorker()
        {
            Interlocked.Increment(ref _created);
            return new Worker(this);
        }

        private sealed class Worker(FakeBackend owner) : ICohFallbackWorker
        {
            private int _attempted, _gated;

            public CohFallbackRow Process(float[] pcm, byte[] snapshot, int candidateIndex)
            {
                int e = (candidateIndex - 1) / 2;
                Interlocked.Increment(ref owner._processCalls);
                lock (owner._gate) owner._processed.Add(e);
                owner.OnProcess?.Invoke(e);
                if (owner.ThrowAtOrdinal == e) throw new NativeAccessViolationException();
                _attempted++;
                bool gated = e % 3 == 0;
                if (gated) _gated++;
                return Row(e, gated ? CohFallbackState.NewGated : CohFallbackState.NoCrc);
            }

            public CohFallbackStats Accumulated => new(0, 0, 0, 0, _attempted, 0, 0, 0, _gated, 0, 0, _attempted, 0, 0, 0);

            public void Dispose() => Interlocked.Increment(ref owner._disposed);
        }
    }

    /// <summary>A seeded per-candidate spin, so the interleaving differs between runs without any wall-clock wait.</summary>
    private static Action<int> Perturb(int seed)
        => e =>
        {
            var rng = new Random(seed * 100_003 + e);
            Thread.SpinWait(rng.Next(0, 4000));
            if (rng.Next(0, 3) == 0) Thread.Yield();
        };

    [Theory(DisplayName = "R15: gathered in candidate order - 1, 2 and 8 workers give the same rows in the same order, each candidate run exactly once, whatever the interleaving")]
    [InlineData(1)]
    [InlineData(2)]
    [InlineData(8)]
    public void Gather_IsInCandidateOrder(int workers)
    {
        const int n = 60;
        for (int seed = 1; seed <= 5; seed++)
        {
            var backend = new FakeBackend(n) { OnProcess = Perturb(seed) };
            var result = CohFallbackParallelRunner.Run(backend, Pcm, Snapshot, -1, workers, CancellationToken.None)!;

            result.Rows.Select(IdOf).Should().Equal(Enumerable.Range(0, n), "seed {0}: the rows are in candidate order", seed);
            result.Rows.Select(r => r.State).Should().Equal(Enumerable.Range(0, n).Select(e => e % 3 == 0 ? CohFallbackState.NewGated : CohFallbackState.NoCrc));
            backend.Processed.OrderBy(e => e).Should().Equal(Enumerable.Range(0, n), "every candidate ran exactly once");
            result.Workers.Should().Be(workers);
            result.Stats.Attempted.Should().Be(n);
            result.Stats.Abandoned.Should().Be(0);
            result.Stats.Eligible.Should().Be(n);
            result.Stats.Gated.Should().Be(Enumerable.Range(0, n).Count(e => e % 3 == 0));
            backend.Created.Should().Be(workers);
            backend.Disposed.Should().Be(workers, "every worker context is released");
        }
    }

    [Fact(DisplayName = "R15: a candidate that finishes LAST does not move: candidate 0 is held until later candidates have finished, and still comes first (8 workers)")]
    public void Gather_SlowFirstCandidate_StaysFirst()
    {
        const int n = 40;
        using var laterDone = new ManualResetEventSlim(false);
        int finishedOthers = 0, othersFinishedWhenZeroReleased = -1;
        var backend = new FakeBackend(n);
        backend.OnProcess = e =>
        {
            if (e == 0)
            {
                laterDone.Wait(TimeSpan.FromSeconds(30)).Should().BeTrue("candidate 0 is released once later candidates have finished");
                othersFinishedWhenZeroReleased = Volatile.Read(ref finishedOthers);
            }
            else if (Interlocked.Increment(ref finishedOthers) >= 10)
                laterDone.Set();
        };

        var result = CohFallbackParallelRunner.Run(backend, Pcm, Snapshot, -1, 8, CancellationToken.None)!;

        result.Rows.Select(IdOf).Should().Equal(Enumerable.Range(0, n));
        othersFinishedWhenZeroReleased.Should().BeGreaterThanOrEqualTo(10, "candidate 0 completed AFTER ten later candidates: completion order differs from the result's order");
    }

    [Fact(DisplayName = "R15: the worker count is the caller's request, clamped to [1, candidates] - never read from the machine")]
    public void Workers_AreClamped()
    {
        var a = new FakeBackend(3);
        CohFallbackParallelRunner.Run(a, Pcm, Snapshot, 100, 100, CancellationToken.None)!.Workers.Should().Be(3);
        a.Created.Should().Be(3);

        var b = new FakeBackend(10);
        CohFallbackParallelRunner.Run(b, Pcm, Snapshot, -1, 0, CancellationToken.None)!.Workers.Should().Be(1);
        CohFallbackParallelRunner.Run(new FakeBackend(10), Pcm, Snapshot, -1, -5, CancellationToken.None)!.Workers.Should().Be(1);
    }

    [Fact(DisplayName = "R15: no eligible candidate - no worker is created, an empty result, the plan's counts")]
    public void NoCandidates_NoWorkers()
    {
        var backend = new FakeBackend(0);
        var result = CohFallbackParallelRunner.Run(backend, Pcm, Snapshot, -1, 8, CancellationToken.None)!;
        result.Rows.Should().BeEmpty();
        result.Workers.Should().Be(0);
        backend.Created.Should().Be(0);
        (result.Stats.Candidates, result.Stats.Decoded, result.Stats.Eligible).Should().Be((3, 3, 0));
    }

    [Fact(DisplayName = "R15: a plan that cannot be made gives null (the cycle has no fallback decodes), and no worker is created")]
    public void PlanFails_IsNull()
    {
        var backend = new FakeBackend(5) { PlanFails = true };
        CohFallbackParallelRunner.Run(backend, Pcm, Snapshot, -1, 4, CancellationToken.None).Should().BeNull();
        backend.Created.Should().Be(0);
    }

    // ── R7''' / R12': abandon, never queue ──────────────────────────────────────────────────────────────────────

    [Theory(DisplayName = "R7: a deadline that has already passed abandons every candidate - none started, all counted, rows keep the abandoned state")]
    [InlineData(1)]
    [InlineData(8)]
    public void ZeroBudget_AbandonsAll(int workers)
    {
        var backend = new FakeBackend(30);
        var result = CohFallbackParallelRunner.Run(backend, Pcm, Snapshot, 0.0, workers, CancellationToken.None)!;

        backend.ProcessCalls.Should().Be(0, "nothing is started after the deadline, and nothing is queued for later");
        result.Stats.Abandoned.Should().Be(30);
        result.Stats.Attempted.Should().Be(0);
        result.Rows.Should().OnlyContain(r => r.State == CohFallbackState.Abandoned);
        CoherentFallbackSelector.Select(result.Rows).Should().BeEmpty();
    }

    [Theory(DisplayName = "R7: a stop that arrives mid-run - the candidates run are a PREFIX of candidate order, the rest abandoned and counted, none started afterwards")]
    [InlineData(1, 7)]
    [InlineData(2, 7)]
    [InlineData(8, 7)]
    [InlineData(8, 0)]
    public void MidRunStop_RunsAPrefix(int workers, int stopAt)
    {
        const int n = 80;
        using var cts = new CancellationTokenSource();
        // The candidate at stopAt cancels; any later candidate that was already claimed waits (on a positive condition) until the
        // cancellation is visible, so how many were in flight is bounded by the worker count, not by the scheduling.
        var backend = new FakeBackend(n);
        backend.OnProcess = e =>
        {
            if (e == stopAt) cts.Cancel();
            else if (e > stopAt) cts.Token.WaitHandle.WaitOne(TimeSpan.FromSeconds(30)).Should().BeTrue();
        };

        var result = CohFallbackParallelRunner.Run(backend, Pcm, Snapshot, -1, workers, cts.Token)!;

        var processed = backend.Processed.OrderBy(e => e).ToList();
        int m = processed.Count;
        m.Should().BeGreaterThanOrEqualTo(stopAt + 1, "the stopping candidate itself was run");
        m.Should().BeLessThanOrEqualTo(stopAt + workers, "at most one candidate per worker was in flight when the stop arrived");
        m.Should().BeLessThan(n, "the stop left work undone");
        processed.Should().Equal(Enumerable.Range(0, m), "the candidates run are exactly 0..m-1: a prefix of candidate order");
        backend.ProcessCalls.Should().Be(m, "no candidate was started twice, or after the workers stopped");
        result.Stats.Attempted.Should().Be(m);
        result.Stats.Abandoned.Should().Be(n - m);
        result.Rows.Take(m).Should().OnlyContain(r => r.State != CohFallbackState.Abandoned);
        result.Rows.Skip(m).Should().OnlyContain(r => r.State == CohFallbackState.Abandoned);
        result.Rows.Select(IdOf).Should().Equal(Enumerable.Range(0, n), "abandoned rows keep their place");
    }

    [Fact(DisplayName = "R7: a finished row is published by the ordinary rules even when later candidates were abandoned (the selector sees the prefix)")]
    public void Abandonment_PublishesTheFinishedPrefix()
    {
        const int n = 30;
        using var cts = new CancellationTokenSource();
        var backend = new FakeBackend(n) { OnProcess = e => { if (e == 5) cts.Cancel(); } };
        var result = CohFallbackParallelRunner.Run(backend, Pcm, Snapshot, -1, 1, cts.Token)!;

        var picked = CoherentFallbackSelector.Select(result.Rows).Select(IdOf).ToList();
        picked.Should().Equal(new[] { 0, 3 }, "candidates 0 and 3 are the gated ones among 0..5; later gated ones (6, 9, ...) were abandoned");
    }

    // ── failure ──────────────────────────────────────────────────────────────────────────────────────────────────

    [Theory(DisplayName = "R15: a worker that throws (a contained native fault) stops the run - the exception reaches the caller, every worker context is released")]
    [InlineData(1)]
    [InlineData(8)]
    public void WorkerFault_PropagatesAndReleases(int workers)
    {
        var backend = new FakeBackend(50) { ThrowAtOrdinal = 3, OnProcess = Perturb(2) };

        Action act = () => CohFallbackParallelRunner.Run(backend, Pcm, Snapshot, -1, workers, CancellationToken.None);

        act.Should().Throw<NativeAccessViolationException>();
        backend.Created.Should().Be(workers);
        backend.Disposed.Should().Be(workers);
    }

    [Fact(DisplayName = "R15: after a fault no further candidate is claimed (one worker: candidates 0..3 ran, 4.. never started)")]
    public void WorkerFault_NothingClaimedAfterwards()
    {
        var backend = new FakeBackend(50) { ThrowAtOrdinal = 3 };
        Action act = () => CohFallbackParallelRunner.Run(backend, Pcm, Snapshot, -1, 1, CancellationToken.None);
        act.Should().Throw<NativeAccessViolationException>();
        backend.ProcessCalls.Should().Be(4);
    }

    // ── the default interface method ────────────────────────────────────────────────────────────────────────────

    private sealed class BackendOnlyInterop(ICohFallbackBackend? backend) : IFt8NativeInterop
    {
        public ICohFallbackBackend? CohFallbackBackend => backend;
        public Ft8NativeResult[] DecodeAll(float[] pcm) => [];
        public int MaxDecodePasses => 2;
        public int[] GetLastPassCounts(int maxPasses) => new int[maxPasses];
        public int[] GetLastCandidateCounts(int maxPasses) => new int[maxPasses];
        public float GetLastNoiseFloorDb() => 0f;
        public int GetHashTableRejectCount() => 0;
        public int GetH12DisplayingCount() => 0;
        public int GetH12AmbiguousCount() => 0;
        public int GetH12DivergentCount() => 0;
        public int GetH12SuppressedCount() => 0;
        public (float[] MeanAbs, float[] PrenormVariance, int[] FailCount) GetLastLlrStats(int maxPasses)
            => (new float[maxPasses], new float[maxPasses], new int[maxPasses]);
        public void SetApBits(byte[] mycallBits, byte[] hiscallBits) { }
        public void SetDecodeParams(int kMinScorePass2, float osdCorrThreshold, int osdNhardMax) { }
        public (float DeltaFreqHz, float DeltaTimeS, float SyncScore, int CoarseDtSamp, int FineDtSamp) RefineCandidate(
            float[] pcm, int coarseFreqHz, float coarseTimeOffsetS) => (0f, 0f, 0f, 0, 0);
        public float[] CoherentLlrAt(float[] pcm, float freqHz, float timeOffsetS) => new float[174];
        public (float[] SignalDb, float[] LocalNoiseDb) GetLastSnrTerms(int maxDecoded) => (Array.Empty<float>(), Array.Empty<float>());
        public byte[] EncodeMessage(string message) => new byte[79];
        public (float[] Re, float[] Im) SubfeasComputeAnalytic(float[] pcm) => (new float[pcm.Length], new float[pcm.Length]);
        public (int ReturnCode, float[] Shat) SubfeasFitSignal(float[] xARe, float[] xAIm, byte[] tones, float decodedDtS, float decodedFreqHz, IntPtr cancelFlag)
            => (0, new float[180_000]);
    }

    [Fact(DisplayName = "R15: the interop's default CohFallbackRun drives its backend through the parallel runner, and is null (no fallback) without one")]
    public void InteropDefault_UsesTheRunner()
    {
        IFt8NativeInterop with = new BackendOnlyInterop(new FakeBackend(12));
        var result = with.CohFallbackRun(Pcm, Snapshot, -1, 4, CancellationToken.None)!;
        result.Rows.Select(IdOf).Should().Equal(Enumerable.Range(0, 12));
        result.Workers.Should().Be(4);

        IFt8NativeInterop without = new BackendOnlyInterop(null);
        without.CohFallbackRun(Pcm, Snapshot, -1, 4, CancellationToken.None).Should().BeNull();
    }
}
