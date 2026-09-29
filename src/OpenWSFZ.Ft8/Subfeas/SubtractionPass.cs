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
    private const int PcmLength = 180_000;

    /// <summary>
    /// Runs the residual-decode pass. Never throws for a native access-violation on any
    /// individual signal's fit or on the residual decode itself — those are caught, logged,
    /// and treated as "no new decodes this cycle" (graceful fallback to pass-0-only),
    /// matching design.md Decision 4's contract. Other exceptions (bad arguments, a
    /// genuinely unexpected native return code) propagate.
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
        CancellationToken ct = default)
    {
        if (normalisedPcm.Length != PcmLength)
            throw new ArgumentException(
                $"normalisedPcm must be exactly {PcmLength} samples. Got {normalisedPcm.Length}.",
                nameof(normalisedPcm));

        return await Task.Run(() => RunCore(interop, normalisedPcm, pass0Results, maxDegreeOfParallelism, logger, ct), ct);
    }

    private static Ft8NativeResult[] RunCore(
        IFt8NativeInterop interop,
        float[] normalisedPcm,
        Ft8NativeResult[] pass0Results,
        int maxDegreeOfParallelism,
        ILogger? logger,
        CancellationToken ct)
    {
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
        bool accessViolation = false;

        var options = new ParallelOptions
        {
            MaxDegreeOfParallelism = Math.Max(1, maxDegreeOfParallelism),
            CancellationToken = ct,
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
        catch (AggregateException ex) when (ex.InnerExceptions.Any(e => e is NativeAccessViolationException))
        {
            accessViolation = true;
        }
        catch (NativeAccessViolationException)
        {
            accessViolation = true;
        }

        if (accessViolation)
        {
            // Decision 4's contract: ANY signal's AV abandons the WHOLE residual pass, not a
            // per-signal skip — do not silently keep other signals' successful fits.
            logger?.LogWarning(
                "Sub-feas residual pass: native access violation during a per-signal fit — " +
                "abandoning the whole residual pass for this cycle (fallback to pass-0-only), " +
                "per design.md Decision 4.");
            return [];
        }

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
        Ft8NativeResult[] pass2Results;
        try
        {
            pass2Results = interop.DecodeAll(residual);
        }
        catch (NativeAccessViolationException)
        {
            logger?.LogWarning(
                "Sub-feas residual pass: native access violation during the residual decode call " +
                "— treating as no new decodes for this cycle (fallback to pass-0-only).");
            return [];
        }

        if (pass2Results.Length == 0) return [];

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
