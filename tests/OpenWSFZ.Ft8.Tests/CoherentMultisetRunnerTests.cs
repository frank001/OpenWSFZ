using System.Collections.Concurrent;
using FluentAssertions;
using OpenWSFZ.Ft8.Interop;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// COH-MULTISET Stage 2, Architect A1.1 at the seam: the managed runner sets the multi-set bit on EVERY worker context before that worker's
/// first candidate, for every cycle, whatever the flag says - because a native context can outlive a cycle while the flag changes at run time.
/// A fake backend that REUSES its worker objects across runs stands in for the long-lived context.
/// </summary>
public sealed class CoherentMultisetRunnerTests
{
    private static CohFallbackRow Row() => new(1000f, 0.3f, 1000.3f, 0.31f, 0, false, CohFallbackState.NoCrc, 0, double.NaN, new byte[12]);

    private sealed class RecordingBackend(int candidates) : ICohFallbackBackend
    {
        public ConcurrentQueue<string> Events { get; } = new();

        /// <summary>Each worker waits here at its first candidate, so every worker of the run really takes part (a fast one cannot do all the work first).</summary>
        public Barrier? Gate { get; set; }
        private readonly ConcurrentQueue<Worker> _pool = new();

        public CohFallbackPlan? Plan(byte[] snapshot)
        {
            var stats = new CohFallbackStats(candidates, 0, 0, candidates, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0);
            return new CohFallbackPlan(stats, Enumerable.Range(0, candidates).ToList(), Enumerable.Range(0, candidates).Select(_ => Row()).ToList());
        }

        // a long-lived worker: handed out again for the next run, as a context that outlives a cycle would be
        public ICohFallbackWorker CreateWorker() => _pool.TryDequeue(out var w) ? w : new Worker(this);

        public void Release(Worker w) => _pool.Enqueue(w);

        public sealed class Worker(RecordingBackend owner) : ICohFallbackWorker
        {
            private static int _next;
            private readonly int _id = Interlocked.Increment(ref _next);
            private bool _bit;
            private bool _first;

            public CohFallbackRow Process(float[] pcm, byte[] snapshot, int candidateIndex)
            {
                if (_first)
                {
                    _first = false;
                    owner.Gate?.SignalAndWait(TimeSpan.FromSeconds(30)).Should().BeTrue();
                }
                owner.Events.Enqueue($"W{_id}:process:bit={(_bit ? 1 : 0)}");
                return Row();
            }

            public CohFallbackStats Accumulated => default;

            public void SetMultiSet(bool on)
            {
                _bit = on;
                _first = true;
                owner.Events.Enqueue($"W{_id}:set:{(on ? 1 : 0)}");
            }

            public void Dispose() => owner.Release(this);     // returned to the pool, not destroyed
        }
    }

    [Theory(DisplayName = "A1.1: every worker gets the bit set before its first candidate, in every cycle, and every candidate is processed with the cycle's value (ON then OFF, OFF then ON)")]
    [InlineData(true, false, 1)]
    [InlineData(false, true, 1)]
    [InlineData(true, false, 3)]
    [InlineData(false, true, 3)]
    public void RunnerSetsTheBit_OnEveryWorker_EveryCycle(bool first, bool second, int workers)
    {
        var backend = new RecordingBackend(candidates: 12);
        foreach (bool flag in new[] { first, second })
        {
            while (backend.Events.TryDequeue(out _)) { }
            backend.Gate = new Barrier(workers);
            CohFallbackParallelRunner.Run(backend, new float[1], new byte[4], -1, workers, CancellationToken.None, flag)!.Rows.Should().HaveCount(12);

            var events = backend.Events.ToList();
            var byWorker = events.GroupBy(e => e.Split(':')[0]).ToList();
            byWorker.Should().HaveCount(workers);
            foreach (var w in byWorker)
            {
                var list = w.ToList();
                list[0].Should().Be($"{w.Key}:set:{(flag ? 1 : 0)}", "the bit is set before the worker's first candidate, even when the value is false");
                list.Skip(1).Should().OnlyContain(e => e.EndsWith($"process:bit={(flag ? 1 : 0)}"), "every candidate runs with this cycle's value, not the previous cycle's");
            }
            events.Count(e => e.Contains(":process:")).Should().Be(12);
        }
    }
}
