using OpenWSFZ.Abstractions;
using OpenWSFZ.Ft8.Interop;

namespace OpenWSFZ.Ft8.Subfeas;

/// <summary>
/// COH-FB-AUDIO: chooses which audio the coherent fallback reads (<c>decoder.coherentFallbackAudio</c>), and merges the two result sets of the
/// <see cref="CoherentFallbackAudio.Both"/> mode. Promoted from the replay-only probe <c>OPENWSFZ_COHFB_AUDIO</c> (the environment variable is gone).
///
/// <para>
/// The candidate snapshot is the same in every mode; only the PCM the fallback measures differs. The step-down is what the probe measured:
/// the third pass's own subtracted buffer when it ran, else the residual pass's buffer, else the original audio.
/// </para>
/// </summary>
internal static class CohFallbackAudioSelector
{
    /// <summary>Level: the original (normalised) audio, because the mode asked for it.</summary>
    internal const string LevelOriginal = "original";

    /// <summary>Level: the third pass's own subtracted buffer (third-pass outcome <c>ran</c>).</summary>
    internal const string LevelResidual3 = "residual3";

    /// <summary>Level: the residual pass's buffer (no third-pass buffer was usable).</summary>
    internal const string LevelResidual2 = "residual2";

    /// <summary>Level: a residual buffer was wanted but none was usable, so the original audio is read.</summary>
    internal const string LevelUnavailable = "unavailable";

    /// <summary>The audio the fallback reads and the level of the step-down it came from.</summary>
    /// <param name="Pcm">The decoder's own array (never a copy): read-only for the caller, not to be mutated or pooled while the fallback runs.</param>
    /// <param name="Level">One of the <c>Level*</c> constants.</param>
    /// <param name="CohSnapshot">COH-RES-CAND: the candidate snapshot taken from the decode of THIS buffer (<c>null</c> for the original audio, or when none was taken).
    /// Chosen by the same step-down as <paramref name="Pcm"/>, so the list and the audio cannot come from different buffers.</param>
    internal readonly record struct Choice(float[] Pcm, string Level, byte[]? CohSnapshot = null)
    {
        /// <summary>True when <see cref="Pcm"/> is a residual buffer.</summary>
        public bool IsResidual => Level is LevelResidual3 or LevelResidual2;
    }

    /// <summary>
    /// The step-down. <see cref="CoherentFallbackAudio.Original"/> always yields the original reference. Otherwise: not Deep, no report, residual pass
    /// abandoned or failed, buffer missing, or nothing fitted ⇒ <see cref="LevelUnavailable"/> (original audio); else the third pass's buffer when it
    /// <c>ran</c> and exposes one (<see cref="LevelResidual3"/>); else the residual pass's buffer (<see cref="LevelResidual2"/>).
    /// </summary>
    internal static Choice Select(
        CoherentFallbackAudio mode,
        float[] original,
        bool deep,
        SubtractionPass.ResidualPassReport? report,
        SubtractionPass.ThirdPassResult? third)
    {
        if (mode == CoherentFallbackAudio.Original) return new Choice(original, LevelOriginal);

        if (!deep
            || report is null
            || report.DeadlineAbandoned
            || report.ContainedException
            || report.Residual is null
            || report.FittedSignals == 0)
            return new Choice(original, LevelUnavailable);

        if (third is { Outcome: SubtractionPass.ThirdPassOutcome.Ran, Residual: { } thirdBuffer })
            return new Choice(thirdBuffer, LevelResidual3, third.CohSnapshot);

        return new Choice(report.Residual, LevelResidual2, report.CohSnapshot);
    }

    /// <summary>
    /// COH-RES-CAND v2 (R4, Amendment 2 A2.1): the highest published integer frequency, in Hz, at which a new-text row of the third (residual-candidates) fallback
    /// run is kept. Frozen from #272's arm-B data by QA's Stage 0 (record <c>qa/rr-study/2026-11-12-1352-qa-coh-res-cand-v2-stage0-record.md</c>, script
    /// <c>stage0.py</c>; kept_C 57 of 119, kept_TA 4 of 19, p_perm 0.0476) and written into the spec by the Architect's Amendment 2 (<c>538ecc29</c>). Never
    /// re-fitted: a pinned gate (HK-021(p)).
    /// </summary>
    internal const int ResidualRunMaxFreqHz = 1097;

    /// <summary>
    /// The integer frequency, in Hz, a fallback row is PUBLISHED with: the one place it is formed (the native result's <c>FreqHz</c>, which <c>MapNative</c> copies
    /// unchanged into <c>DecodeResult.FreqHz</c>, the value the replay harness writes as <c>freq</c>). Banker's rounding, as it has always been.
    /// </summary>
    internal static int PublishedFreqHz(CohFallbackRow row) => (int)Math.Round(row.OutFreqHz);

    /// <summary>COH-RES-CAND v2 (R4): whether a new-text row of the third run with this published integer frequency is kept (<c>&lt;=</c> <see cref="ResidualRunMaxFreqHz"/>).</summary>
    internal static bool PassesResidualRunGate(int publishedFreqHz) => publishedFreqHz <= ResidualRunMaxFreqHz;

    /// <summary>
    /// COH-RES-CAND v2 (R3, R-F4): the rows of the third run that may be considered for publication: those whose F1b gate PASSED
    /// (<see cref="CohFallbackState.NewGated"/>), one per payload by the selector's own rule (first non-edge, in candidate order). A
    /// <see cref="CohFallbackState.GatedOut"/> row is never taken, <b>whatever its <see cref="CohFallbackRow.Admitted"/> flag says</b>, so R-F4 (which sets that
    /// flag only inside <see cref="Merge"/>, on the first two runs' rows) can never ungate them. The third run's rows never enter <see cref="Merge"/>.
    /// </summary>
    internal static IReadOnlyList<CohFallbackRow> ThirdRunCandidates(IReadOnlyList<CohFallbackRow>? thirdRows)
    {
        if (thirdRows is null || thirdRows.Count == 0) return [];
        var f1bPassed = thirdRows.Where(static r => r.State == CohFallbackState.NewGated).ToList();
        return CoherentFallbackSelector.Select(f1bPassed);
    }

    /// <summary>The <c>audio=</c> log field for a mode and the level its step-down reached.</summary>
    internal static string Label(CoherentFallbackAudio mode, string level) => mode switch
    {
        CoherentFallbackAudio.Both => $"both({level})",
        _ when level == LevelUnavailable => "residual-unavailable",
        _ => level,
    };

    /// <summary>Bytes of the 77-bit payload that identify a message (the first 10 of the 12 the native side reports); as the selector's key.</summary>
    private const int PayloadKeyBytes = 10;

    /// <summary>The merge of the two runs of <see cref="CoherentFallbackAudio.Both"/>.</summary>
    /// <param name="Rows">The rows to hand to <see cref="CoherentFallbackSelector.Select"/>, in candidate order (residual before original on a tie).</param>
    /// <param name="FromOriginal">Distinct publishable payloads found only on the original audio.</param>
    /// <param name="FromResidual">Distinct publishable payloads found only on the residual audio.</param>
    /// <param name="InBoth">Distinct publishable payloads found by both runs (the residual rows are kept).</param>
    internal sealed record Merged(IReadOnlyList<CohFallbackRow> Rows, int FromOriginal, int FromResidual, int InBoth);

    /// <summary>
    /// Merges the rows of the two runs by payload, before <see cref="CoherentFallbackSelector.Select"/>. Only publishable rows
    /// (<see cref="CohFallbackState.NewGated"/>) take part in the payload match: a payload is "found" by a run when that run has a NewGated row for it
    /// (a run whose F1b gate rejected it did not find it). Where both runs found a payload, only the residual run's rows for it are kept (its SNR and
    /// DT are measured with the neighbours removed); an original-run row is added only for a payload the residual run did not find. Every residual-run
    /// row is kept (so the selector's one-row-per-payload and edge rules apply to the merged set exactly as to a single run). Either input may be
    /// <c>null</c> or empty (that run did not produce rows). Deterministic: sorted by candidate position, residual before original.
    /// <para>
    /// COH-GATE-G R-F4: with <paramref name="admitResidualGatedOut"/> a <see cref="CohFallbackState.GatedOut"/> row of <paramref name="residualRows"/> is
    /// admitted (flagged <see cref="CohFallbackRow.Admitted"/>, state unchanged) and from here on counts as a found, publishable payload exactly like a
    /// NewGated one: it joins the residual key set (an original-run NewGated row with the same payload is dropped), is counted in the three counters and
    /// goes to the selector. A GatedOut row of <paramref name="originalRows"/> is never admitted, and with no residual run (null) nothing is.
    /// </para>
    /// </summary>
    internal static Merged Merge(IReadOnlyList<CohFallbackRow>? originalRows, IReadOnlyList<CohFallbackRow>? residualRows, bool admitResidualGatedOut = false)
    {
        originalRows ??= [];
        residualRows ??= [];
        if (admitResidualGatedOut)
            residualRows = residualRows.Select(static r => r.State == CohFallbackState.GatedOut ? r with { Admitted = true } : r).ToList();

        static string Key(CohFallbackRow r) => Convert.ToHexString(r.Payload, 0, PayloadKeyBytes);

        var residualKeys = new HashSet<string>(StringComparer.Ordinal);
        foreach (var r in residualRows)
            if (r.IsPublishable) residualKeys.Add(Key(r));

        var originalKeys = new HashSet<string>(StringComparer.Ordinal);
        foreach (var r in originalRows)
            if (r.IsPublishable) originalKeys.Add(Key(r));

        int inBoth = originalKeys.Count(residualKeys.Contains);

        var combined = new List<(int Index, int Source, CohFallbackRow Row)>(residualRows.Count + originalRows.Count);
        for (int i = 0; i < residualRows.Count; i++) combined.Add((i, 0, residualRows[i]));
        for (int i = 0; i < originalRows.Count; i++)
        {
            var r = originalRows[i];
            if (r.IsPublishable && !residualKeys.Contains(Key(r))) combined.Add((i, 1, r));
        }
        combined.Sort(static (a, b) => a.Index != b.Index ? a.Index.CompareTo(b.Index) : a.Source.CompareTo(b.Source));

        return new Merged(
            combined.Select(c => c.Row).ToList(),
            FromOriginal: originalKeys.Count - inBoth,
            FromResidual: residualKeys.Count - inBoth,
            InBoth: inBoth);
    }

    /// <summary>
    /// The counters of the two runs of <see cref="CoherentFallbackAudio.Both"/> as one: the candidate counts of the (single) snapshot are taken once
    /// (<c>max</c>), the work counters and the times are summed (they describe the work done), so <c>abandoned</c> counts candidate-runs not started (a candidate abandoned in both runs counts twice).
    /// </summary>
    internal static CohFallbackStats CombineStats(CohFallbackStats a, CohFallbackStats b) => new(
        Math.Max(a.Candidates, b.Candidates), Math.Max(a.Decoded, b.Decoded), Math.Max(a.DupPosition, b.DupPosition), Math.Max(a.Eligible, b.Eligible),
        a.Attempted + b.Attempted, a.CrcOk + b.CrcOk, a.CrcNew + b.CrcNew, a.F1bComputed + b.F1bComputed, a.Gated + b.Gated,
        a.Abandoned + b.Abandoned, a.Edge + b.Edge, a.EstimateMs + b.EstimateMs, a.F1bMs + b.F1bMs, a.C3BpMs + b.C3BpMs, a.TotalMs + b.TotalMs)
    {
        WalkEntered = a.WalkEntered + b.WalkEntered,
    };

    /// <summary>The stats of a run that was not started because the shared budget was already spent: every eligible candidate counted abandoned.</summary>
    internal static CohFallbackStats NotRun(CohFallbackStats basis) => new(
        basis.Candidates, basis.Decoded, basis.DupPosition, basis.Eligible, 0, 0, 0, 0, 0, basis.Eligible, 0, 0, 0, 0, 0);
}
