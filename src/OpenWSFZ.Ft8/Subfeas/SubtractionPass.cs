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
    /// Wall-clock guard (QA review R3): native calls are not cancellable, so the
    /// <c>deadline</c> is cooperative - checked before/after each native phase and
    /// used to stop scheduling further per-signal fits. Exceeding it abandons the pass
    /// (pass-0-only). A single native call already in flight still runs to completion.
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

        return await Task.Run(() => RunCore(interop, normalisedPcm, pass0Results, maxDegreeOfParallelism, logger, ap, deadline, ct), ct);
    }

    private static Ft8NativeResult[] RunCore(
        IFt8NativeInterop interop,
        float[] normalisedPcm,
        Ft8NativeResult[] pass0Results,
        int maxDegreeOfParallelism,
        ILogger? logger,
        Ft8ApConstraints? ap,
        TimeSpan? deadline,
        CancellationToken ct)
    {
        try
        {
            return RunCoreUnguarded(interop, normalisedPcm, pass0Results, maxDegreeOfParallelism, logger, ap, deadline, ct);
        }
        catch (OperationCanceledException) when (ct.IsCancellationRequested)
        {
            throw; // caller cancellation is not a residual-pass failure
        }
        catch (Exception ex)
        {
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
        CancellationToken ct)
    {
        var clock = System.Diagnostics.Stopwatch.StartNew();
        bool Expired() => deadline is { } d && clock.Elapsed >= d;
        Ft8NativeResult[] DeadlineAbandon(string phase)
        {
            logger?.LogWarning(
                "Sub-feas residual pass: wall-clock budget {Budget:F1}s exceeded {Phase} - " +
                "abandoning the residual pass (fallback to pass-0-only).",
                deadline!.Value.TotalSeconds, phase);
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

        if (candidates.Count == 0) return [];

        // ── Analytic signal: ONE call per cycle, shared read-only across every fit ──
        (float[] xaRe, float[] xaIm) = interop.SubfeasComputeAnalytic(normalisedPcm);

        // ── Step 2 (per-signal fits, concurrent) ────────────────────────────
        var shatBuffers = new float[candidates.Count][];
        var returnCodes = new int[candidates.Count];

        if (Expired()) return DeadlineAbandon("before the per-signal fits");

        // Any exception from a fit (AV, rc -1 alloc failure, ...) propagates to RunCore's guard:
        // ANY signal's failure abandons the WHOLE residual pass (Decision 4), never a per-signal skip.
        using var fitCts = CancellationTokenSource.CreateLinkedTokenSource(ct);
        if (deadline is { } budget)
            fitCts.CancelAfter(budget > clock.Elapsed ? budget - clock.Elapsed : TimeSpan.Zero);
        var options = new ParallelOptions
        {
            MaxDegreeOfParallelism = Math.Max(1, maxDegreeOfParallelism),
            CancellationToken = fitCts.Token,
        };

        try
        {
            Parallel.For(0, candidates.Count, options, i =>
            {
                var c = candidates[i];
                (int rc, float[] shat) = interop.SubfeasFitSignal(xaRe, xaIm, c.Tones, c.Dt, c.FreqHz);
                returnCodes[i] = rc;
                shatBuffers[i] = shat;
            });
        }
        catch (OperationCanceledException) when (!ct.IsCancellationRequested)
        {
            return DeadlineAbandon("during the per-signal fits");
        }

        if (Expired()) return DeadlineAbandon("after the per-signal fits");

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
        try
        {
            pass2Results = interop.DecodeAll(residual);
        }
        finally
        {
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
