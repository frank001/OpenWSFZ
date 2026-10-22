using System.Diagnostics;
using OpenWSFZ.Ft8.Interop;

namespace OpenWSFZ.Ft8;

/// <summary>
/// COH-FALLBACK step 4, R15 (Architect spec §14 A14.2): the fallback cycle split across worker threads, with a result that does not
/// depend on how the threads were scheduled.
///
/// <para><b>Rules (stated here, tested in <c>CoherentFallbackParallelRunnerTests</c>):</b></para>
/// <list type="number">
///   <item><b>Split.</b> The eligible candidates (<see cref="CohFallbackPlan"/>, candidate order) are handed out one at a time from a
///   shared counter: a worker takes the next unclaimed candidate. Every candidate is run by exactly one worker, on that worker's own native
///   context.</item>
///   <item><b>Gather in candidate order.</b> Worker <c>w</c> writes only row <c>e</c> for the candidate <c>e</c> it ran. The result's rows
///   are the plan's rows, indexed by candidate, so the list the caller sees (and what F1b, the selector, the dedup and R6'' then do with it)
///   is the same for 1, 2 or 8 workers.</item>
///   <item><b>Abandon, never queue (R7', R12').</b> A worker checks the deadline and the cancellation token <i>before it claims</i> a
///   candidate; a candidate it has claimed it always finishes. Candidates are claimed in index order, so the candidates run are exactly
///   <c>0 .. k-1</c>: a prefix of candidate order. The rest keep their pre-filled <see cref="CohFallbackState.Abandoned"/> row, are
///   counted in <see cref="CohFallbackStats.Abandoned"/>, and are never started later. Every finished row, which is every row before the
///   first abandoned one, is published (or not) by the ordinary rules. The prefix is the only thing the clock decides.</item>
///   <item><b>Failure.</b> A worker that throws (a contained native access violation) stops all workers from claiming; the exception is
///   rethrown after every worker has stopped, and the caller treats the cycle as having no fallback decodes.</item>
/// </list>
/// The calling thread is worker 0; the others run on dedicated (long-running) threads, so no thread-pool injection delay is paid.
/// </summary>
internal static class CohFallbackParallelRunner
{
    /// <summary>Runs the fallback over <paramref name="snapshot"/>; see the class remarks for the rules.</summary>
    /// <param name="backend">The native side (the real library, or a fake in a test).</param>
    /// <param name="pcm">The cycle's normalised PCM (read only).</param>
    /// <param name="snapshot">The snapshot made on the decode thread (read only; the same array is handed to every worker).</param>
    /// <param name="budgetMs">&lt; 0: no deadline; otherwise no candidate is claimed once this many ms have passed since the call began.</param>
    /// <param name="workers">Worker threads wanted (at least 1; never more than there are candidates).</param>
    /// <param name="ct">Cancelling it has the same effect as the deadline.</param>
    /// <returns>The result, or <c>null</c> when the backend could not make a plan.</returns>
    public static CohFallbackRunResult? Run(
        ICohFallbackBackend backend, float[] pcm, byte[] snapshot, double budgetMs, int workers, CancellationToken ct)
    {
        ArgumentNullException.ThrowIfNull(backend);
        ArgumentNullException.ThrowIfNull(pcm);
        ArgumentNullException.ThrowIfNull(snapshot);

        var wall = Stopwatch.StartNew();
        var plan = backend.Plan(snapshot);
        if (plan is null) return null;

        int n = plan.CandidateIndex.Count;
        var rows = new CohFallbackRow[n];
        for (int i = 0; i < n; i++) rows[i] = plan.Rows[i];

        int nWorkers = n == 0 ? 0 : Math.Clamp(workers, 1, n);
        var accumulated = new CohFallbackStats[nWorkers];
        if (nWorkers > 0)
        {
            int next = -1;                  // last claimed candidate
            int faulted = 0;                // set once a worker has thrown
            Exception? firstFault = null;

            bool MayClaim() =>
                Volatile.Read(ref faulted) == 0
                && !ct.IsCancellationRequested
                && !(budgetMs >= 0.0 && wall.Elapsed.TotalMilliseconds >= budgetMs);

            void Work(int w)
            {
                try
                {
                    using var worker = backend.CreateWorker();
                    while (MayClaim())
                    {
                        int e = Interlocked.Increment(ref next);
                        if (e >= n) break;
                        rows[e] = worker.Process(pcm, snapshot, plan.CandidateIndex[e]);
                    }
                    accumulated[w] = worker.Accumulated;
                }
                catch (Exception ex)
                {
                    Interlocked.CompareExchange(ref firstFault, ex, null);
                    Volatile.Write(ref faulted, 1);
                }
            }

            var others = new Task[nWorkers - 1];
            for (int w = 1; w < nWorkers; w++)
            {
                int id = w;
                others[w - 1] = Task.Factory.StartNew(() => Work(id), CancellationToken.None, TaskCreationOptions.LongRunning, TaskScheduler.Default);
            }
            Work(0);
            Task.WaitAll(others);

            if (firstFault is not null)
                System.Runtime.ExceptionServices.ExceptionDispatchInfo.Capture(firstFault).Throw();
        }

        // Counters: the plan's population counts, the workers' sums for what was run, and abandoned = eligible - run.
        var p = plan.Stats;
        int attempted = 0, crcOk = 0, crcNew = 0, f1b = 0, gated = 0, edge = 0;
        double estMs = 0, f1bMs = 0, c3Ms = 0;
        foreach (var a in accumulated)
        {
            attempted += a.Attempted; crcOk += a.CrcOk; crcNew += a.CrcNew; f1b += a.F1bComputed; gated += a.Gated; edge += a.Edge;
            estMs += a.EstimateMs; f1bMs += a.F1bMs; c3Ms += a.C3BpMs;
        }
        var stats = new CohFallbackStats(
            p.Candidates, p.Decoded, p.DupPosition, p.Eligible, attempted, crcOk, crcNew, f1b, gated,
            Abandoned: p.Eligible - attempted, Edge: edge, EstimateMs: estMs, F1bMs: f1bMs, C3BpMs: c3Ms,
            TotalMs: wall.Elapsed.TotalMilliseconds);
        return new CohFallbackRunResult(stats, rows) { Workers = nWorkers };
    }
}
