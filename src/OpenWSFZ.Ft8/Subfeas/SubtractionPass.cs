using System.Runtime.InteropServices;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Ft8.Interop;

namespace OpenWSFZ.Ft8.Subfeas;

/// <summary>
/// The additive residual-decode pass (design.md Decision 1 steps 2-5, tasks.md 2.4/2.5):
/// given a cycle's pass-0 decode results and the exact PCM buffer they were decoded from,
/// fits and subtracts every re-encodable pass-0 signal, decodes the residual, and returns
/// only the genuinely NEW decodes (payload-based dedup against pass-0, RR73-aware).
///
/// <para>
/// NOT WIRED IN YET: no caller in <see cref="Ft8Decoder"/> invokes this (tasks.md §5's config
/// flag does not exist yet — that is the next increment). This class is a standalone,
/// independently testable unit; <see cref="Ft8Decoder"/> will call it, concatenate its output
/// with pass-0's native results, and let the existing per-message mapping/plausibility-filter/
/// text-dedup loop in <c>DecodeAsync</c> process the combined set unchanged — no duplication
/// of that logic (design.md's own intent for the two-call shape).
/// </para>
///
/// <para>
/// Concurrency (design.md's Decision 2 addendum): the expensive per-signal fit runs via
/// <see cref="IFt8NativeInterop.SubfeasFitSignal"/>, called once per re-encodable signal,
/// concurrently, bounded by <c>maxDegreeOfParallelism</c>. Each call is independently
/// SEH-wrapped in the native shim — the SAME crash-containment mechanism
/// <c>ft8_decode_all</c> already uses, not a new one. Per Decision 4's existing
/// "any failure -&gt; whole cycle falls back to single-pass, no partial state" contract: an
/// access-violation on ANY one signal's fit call abandons the ENTIRE residual pass (returns
/// no new decodes), rather than silently keeping other signals' successful fits.
/// </para>
/// </summary>
internal static class SubtractionPass
{
    private const int PcmLength = Ft8LibInterop.PcmSampleCount;

    /// <summary>
    /// sub-feas-speed-redesign A5 (design.md D5, Architect's Amendment 1): time held back for the residual
    /// <see cref="IFt8NativeInterop.DecodeAll"/> and the merge that follows it. The native fits are cancelled at
    /// <c>budget - SubtractionResidualDecodeReserve</c>, and the residual decode is not started with less than this
    /// remaining. 1 500 ms leaves 670 ms over the largest flag-OFF whole call observed (830 ms).
    /// </summary>
    internal static readonly TimeSpan SubtractionResidualDecodeReserve = TimeSpan.FromMilliseconds(1500);

    /// <summary>
    /// The native workspace pool's hard cap (<c>SUBFEAS_POOL_MAX_BOUND</c> in <c>subfeas_fit.h</c>). The fit
    /// parallelism is clamped to it, so a machine with more logical processors cannot ask for more concurrent fits
    /// than the pool can lease (a lease beyond the bound is refused, see design.md D2).
    /// </summary>
    internal const int SubfeasPoolMaxBound = 64;

    /// <summary>
    /// Runs the residual-decode pass. Never throws for a native access-violation on any
    /// individual signal's fit or on the residual decode itself — those are caught, logged,
    /// and treated as "no new decodes this cycle" (graceful fallback to pass-0-only),
    /// matching design.md Decision 4's contract.
    ///
    /// <para>
    /// Failure containment (QA review R2): once past argument validation, ANY non-cancellation
    /// exception from the residual pass (compute-analytic AV or rc -1, per-signal rc -1 surfacing
    /// as an <see cref="AggregateException"/>, an encode failure, ...) is logged and swallowed;
    /// the caller keeps pass-0's results. Only caller cancellation propagates.
    /// </para>
    ///
    /// <para>
    /// Thread state (QA review R1): native AP bits, SNR terms and the H12 counters are
    /// <c>_Thread_local</c>. The residual <see cref="IFt8NativeInterop.DecodeAll"/> runs on this
    /// pass's own pool thread, so AP bits are set explicitly on that thread immediately before it
    /// (same discipline as pass-0) and cleared afterwards. The callsign hash table is NOT
    /// thread-local state: it is the process-global <c>g_session_hash_table</c>, re-attached
    /// at the top of every native decode call, so hashes learned in pass-0 resolve in the residual
    /// decode on any thread. Pass-0 and this pass run strictly sequentially (awaited), so there is
    /// no concurrent access to it.
    /// </para>
    ///
    /// <para>
    /// Wall-clock guard (QA review R3, hardened by sub-feas-speed-redesign A5): the per-signal fits are
    /// CANCELLABLE. A cancellation flag (an int in pinned managed memory that outlives every in-flight native call)
    /// is set at <c>deadline - SubtractionResidualDecodeReserve</c>; each native fit checks it at every search
    /// iteration and returns <c>-4</c> promptly, which is a deadline outcome (never an exception). The residual
    /// decode is not started with less than the reserve remaining. Exceeding the deadline abandons the pass
    /// (pass-0-only). Only <c>ft8_subfeas_compute_analytic</c> (about 10 ms) and the residual decode itself are
    /// not interruptible; the reserve covers the latter.
    /// </para>
    /// </summary>
    /// <param name="interop">Native interop abstraction (mockable for tests).</param>
    /// <param name="normalisedPcm">
    /// The EXACT PCM buffer pass-0 was decoded from (post D-002 RMS normalisation) — not the
    /// caller's raw, pre-normalisation buffer. Fits must match what the native decoder actually
    /// saw.
    /// </param>
    /// <param name="pass0Results">Pass-0's native decode results for this cycle.</param>
    /// <param name="maxDegreeOfParallelism">
    /// Bound on concurrent <see cref="IFt8NativeInterop.SubfeasFitSignal"/> calls (design.md's
    /// Decision 2 addendum / tasks.md 1.4 — no shared native buffer pool exists; this bound is
    /// the only concurrency cap).
    /// </param>
    /// <param name="logger">Optional structured logger.</param>
    /// <param name="ap">
    /// The AP constraints pass-0 was decoded with (null = none). Applied on the residual
    /// decode's own thread, because native AP state is thread-local.
    /// </param>
    /// <param name="deadline">
    /// Optional wall-clock budget for the whole residual pass; null = unbounded.
    /// </param>
    /// <param name="ct">Cancellation token.</param>
    /// <returns>
    /// Only the NEW residual-pass decodes (not already present, payload-wise, in
    /// <paramref name="pass0Results"/>) — empty if nothing new was found, the residual decode
    /// produced nothing, or the pass was abandoned after an access violation.
    /// </returns>
    public static async Task<Ft8NativeResult[]> RunAsync(
        IFt8NativeInterop interop,
        float[] normalisedPcm,
        Ft8NativeResult[] pass0Results,
        int maxDegreeOfParallelism,
        ILogger? logger,
        Ft8ApConstraints? ap = null,
        TimeSpan? deadline = null,
        CancellationToken ct = default)
    {
        if (normalisedPcm.Length != PcmLength)
            throw new ArgumentException(
                $"normalisedPcm must be exactly {PcmLength} samples. Got {normalisedPcm.Length}.",
                nameof(normalisedPcm));

        // tasks.md 4.2: one aggregate-only Information line per invocation (never on caller
        // cancellation -- that propagates out of Task.Run/RunCore before reaching the log call).
        // Observability only: RunCore's return value is passed through unchanged.
        var stats = new PassStats();
        var wall = System.Diagnostics.Stopwatch.StartNew();
        Ft8NativeResult[] result = await Task.Run(
            () => RunCore(interop, normalisedPcm, pass0Results, maxDegreeOfParallelism, logger, ap, deadline, stats, ct), ct);
        wall.Stop();

        // HK-037 / NFR-021: aggregates only -- no message text, callsigns or exception text.
        logger?.LogInformation(
            "Sub-feas residual pass: residualDecodes={ResidualDecodes} elapsedMs={ElapsedMs} " +
            "deadlineAbandoned={DeadlineAbandoned} containedException={ContainedException} " +
            "fittedSignals={FittedSignals}",
            result.Length, (long)wall.Elapsed.TotalMilliseconds,
            stats.DeadlineAbandoned, stats.ContainedException, stats.FittedSignals);

        return result;
    }

    /// <summary>Per-invocation observability counters for the tasks.md 4.2 log line; never affects control flow.</summary>
    private sealed class PassStats
    {
        public int FittedSignals;
        public bool DeadlineAbandoned;
        public bool ContainedException;
    }

    private static Ft8NativeResult[] RunCore(
        IFt8NativeInterop interop,
        float[] normalisedPcm,
        Ft8NativeResult[] pass0Results,
        int maxDegreeOfParallelism,
        ILogger? logger,
        Ft8ApConstraints? ap,
        TimeSpan? deadline,
        PassStats stats,
        CancellationToken ct)
    {
        try
        {
            return RunCoreUnguarded(interop, normalisedPcm, pass0Results, maxDegreeOfParallelism, logger, ap, deadline, stats, ct);
        }
        catch (OperationCanceledException) when (ct.IsCancellationRequested)
        {
            throw; // caller cancellation is not a residual-pass failure
        }
        catch (Exception ex)
        {
            stats.ContainedException = true;
            // Decision 4: ANY failure -> whole cycle falls back to pass-0-only, never lost.
            logger?.LogWarning(ex,
                "Sub-feas residual pass failed ({ExceptionType}) - abandoning the residual pass " +
                "for this cycle (fallback to pass-0-only), per design.md Decision 4.",
                ex is AggregateException agg && agg.InnerException is not null
                    ? agg.InnerException.GetType().Name : ex.GetType().Name);
            return [];
        }
    }

    private static Ft8NativeResult[] RunCoreUnguarded(
        IFt8NativeInterop interop,
        float[] normalisedPcm,
        Ft8NativeResult[] pass0Results,
        int maxDegreeOfParallelism,
        ILogger? logger,
        Ft8ApConstraints? ap,
        TimeSpan? deadline,
        PassStats stats,
        CancellationToken ct)
    {
        var clock = System.Diagnostics.Stopwatch.StartNew();
        bool Expired() => deadline is { } d && clock.Elapsed >= d;
        Ft8NativeResult[] DeadlineAbandon(string phase)
        {
            stats.DeadlineAbandoned = true;
            logger?.LogWarning(
                "Sub-feas residual pass: wall-clock budget {Budget:F1}s exceeded {Phase} - " +
                "abandoning the residual pass (fallback to pass-0-only).",
                deadline?.TotalSeconds ?? 0.0, phase); // null deadline: only reachable via a fit answering -4 unprompted
            return [];
        }

        // ── Step 2: fit each pass-0 re-encodable decode ─────────────────────
        var candidates = new List<(byte[] Tones, float Dt, float FreqHz, bool[] Payload77)>();
        foreach (ref readonly Ft8NativeResult nr in pass0Results.AsSpan())
        {
            string msg = nr.Message.TrimEnd();
            if (!IsReencodable(msg)) continue;

            byte[] tones;
            try
            {
                tones = interop.EncodeMessage(msg);
            }
            catch (InvalidOperationException)
            {
                continue; // not encodable despite passing the coarse token/placeholder check
            }

            bool[] payload77 = SubfeasPayload.ExtractPayload77(tones);
            candidates.Add((tones, nr.Dt, nr.FreqHz, payload77));
        }

        stats.FittedSignals = candidates.Count;
        if (candidates.Count == 0) return [];

        // ── Analytic signal: ONE call per cycle, shared read-only across every fit ──
        (float[] xaRe, float[] xaIm) = interop.SubfeasComputeAnalytic(normalisedPcm);

        // ── Step 2 (per-signal fits, concurrent) ────────────────────────────
        var shatBuffers = new float[candidates.Count][];
        var returnCodes = new int[candidates.Count];

        if (Expired()) return DeadlineAbandon("before the per-signal fits");

        // A5: the fits stop at budget - reserve, so the residual decode always has its reserve.
        TimeSpan? fitBudget = deadline is { } d0 ? d0 - SubtractionResidualDecodeReserve : null;
        if (fitBudget is { } fb && clock.Elapsed >= fb)
            return DeadlineAbandon("before the per-signal fits (less than the residual-decode reserve remains)");

        // A3: size the native workspace pool at the cycle boundary, with nothing in flight.
        int degree = Math.Clamp(maxDegreeOfParallelism, 1, SubfeasPoolMaxBound);
        interop.SubfeasPoolConfigure(degree);

        // A5: the cancellation flag. Pinned managed memory (no unsafe code needed) that must outlive every
        // in-flight native call: it is freed only in the finally below, after Parallel.For has returned (it does
        // not return, or throw, until every running iteration has finished).
        var cancelFlag = new int[1];
        GCHandle flagHandle = GCHandle.Alloc(cancelFlag, GCHandleType.Pinned);
        try
        {
            IntPtr flagPtr = flagHandle.AddrOfPinnedObject();

            // Any exception from a fit (AV, rc -1 alloc failure, ...) propagates to RunCore's guard:
            // ANY signal's failure abandons the WHOLE residual pass (Decision 4), never a per-signal skip.
            using var fitCts = CancellationTokenSource.CreateLinkedTokenSource(ct);
            using var flagRegistration = fitCts.Token.Register(() => Volatile.Write(ref cancelFlag[0], 1));
            if (fitBudget is { } budget)
                fitCts.CancelAfter(budget > clock.Elapsed ? budget - clock.Elapsed : TimeSpan.Zero);
            var options = new ParallelOptions
            {
                MaxDegreeOfParallelism = degree,
                CancellationToken = fitCts.Token,
            };

            try
            {
                Parallel.For(0, candidates.Count, options, i =>
                {
                    var c = candidates[i];
                    (int rc, float[] shat) = interop.SubfeasFitSignal(xaRe, xaIm, c.Tones, c.Dt, c.FreqHz, flagPtr);
                    returnCodes[i] = rc;
                    shatBuffers[i] = shat;
                });
            }
            catch (OperationCanceledException) when (!ct.IsCancellationRequested)
            {
                return DeadlineAbandon("during the per-signal fits");
            }
        }
        finally
        {
            flagHandle.Free();
        }

        // rc -4 (D4): a fit answered the deadline flag. A deadline outcome, not an error: it must not raise, and
        // it must not count as a contained exception. Checked explicitly because Parallel.For does not always
        // throw when the last iterations were the ones that observed the cancellation.
        if (Array.IndexOf(returnCodes, Ft8LibInterop.SubfeasRcCancelled) >= 0)
            return DeadlineAbandon("during the per-signal fits");

        if (Expired()) return DeadlineAbandon("after the per-signal fits");

        // A5: do not start the residual decode with less than the reserve left.
        if (deadline is { } d1 && d1 - clock.Elapsed < SubtractionResidualDecodeReserve)
            return DeadlineAbandon("before the residual decode (less than the reserve remains)");

        // ── Step 3: accumulate every fitted signal's subtraction into one residual ──
        // rc == -3 (no valid fit found for that signal) already has an all-zero shat buffer
        // (subfeas_fit.c's own contract) — including it in the sum is a harmless no-op.
        var residual = (float[])normalisedPcm.Clone();
        for (int i = 0; i < candidates.Count; i++)
        {
            if (returnCodes[i] != 0 && returnCodes[i] != -3) continue; // defensive; interop already throws on other codes
            float[] shat = shatBuffers[i];
            for (int s = 0; s < PcmLength; s++) residual[s] -= shat[s];
        }

        // ── Step 4: decode the residual, unmodified existing entry point ────
        // Native AP state is _Thread_local (QA R1): set it on THIS thread, right before DecodeAll,
        // exactly as pass-0 does, and clear it afterwards so no pool thread keeps stale bits.
        // (Parallel.For has completed; this is the same thread that calls DecodeAll below.)
        Ft8NativeResult[] pass2Results;
        interop.SetApBits(ap?.MycallBits ?? [], ap?.HiscallBits ?? []);
        // M2: nothing reads the pass-0 LDPC-failure statistics after this call, so do not compute them (the
        // native switch is thread-local too: same thread, restored in the finally). The noise floor is kept: it
        // feeds the local-noise SNR fallback. Decode output does not depend on this switch.
        interop.SetDiagnosticsEnabled(false);
        try
        {
            pass2Results = interop.DecodeAll(residual);
        }
        finally
        {
            interop.SetDiagnosticsEnabled(true);
            interop.SetApBits([], []);
        }

        if (pass2Results.Length == 0) return [];
        if (Expired()) return DeadlineAbandon("after the residual decode");

        // ── Step 5: payload-based merge/dedup, RR73-aware ───────────────────
        var originalPayloads = candidates.Select(c => c.Payload77).ToList();
        var newResults = new List<Ft8NativeResult>();

        foreach (ref readonly Ft8NativeResult nr in pass2Results.AsSpan())
        {
            string msg = nr.Message.TrimEnd();

            byte[] candTones;
            try
            {
                candTones = interop.EncodeMessage(msg);
            }
            catch (InvalidOperationException)
            {
                continue; // candidate text doesn't re-encode -- cannot payload-compare, skip
            }

            bool[] candPayload77 = SubfeasPayload.ExtractPayload77(candTones);
            if (originalPayloads.Any(refPayload => SubfeasPayload.SameQso(refPayload, candPayload77)))
                continue; // already known to pass-0 before subtraction

            newResults.Add(nr);
        }

        return newResults.ToArray();
    }

    /// <summary>
    /// stage2.py's <c>_is_reencodable</c>: not a hash placeholder, at least 3 space-separated
    /// tokens (Standard QSO / CQ forms only — matches this codebase's own re-encode precondition).
    /// </summary>
    private static bool IsReencodable(string msg)
    {
        if (msg.Contains('<')) return false;
        int tokenCount = 0;
        bool inToken = false;
        foreach (char c in msg)
        {
            if (c == ' ') { inToken = false; }
            else if (!inToken) { inToken = true; tokenCount++; }
        }
        return tokenCount >= 3;
    }
}
