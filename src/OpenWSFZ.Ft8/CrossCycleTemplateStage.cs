using OpenWSFZ.Ft8.Dsp;

namespace OpenWSFZ.Ft8;

/// <summary>
/// XC-BUILD R3/R5/R6/R8/R14/R15: turns a cycle's prior candidates into 79-tone templates (counting what is excluded) and runs the detector over them in parallel, nearest prior first, stopping to START templates when
/// the cycle budget says so. A template is DETECTED when S_E* clears T_E (R6), its second-data-block statistic S_P clears T_P (R15) and no decode of batches 1 to 5 of the cycle with a different text sits
/// next to the argmax (R14). Pure with respect to the decoder: it takes the buffer, the thresholds, the cycle's decodes, the worker count and a "budget expired" predicate, so the tests drive it with no clock and no sleeps.
/// </summary>
internal static class CrossCycleTemplateStage
{
    /// <summary>
    /// The product's published dt minus WSJT-X's dt, seconds (GAP-RELOCATE's DELTA_P, the offset the forced legs use; measured on the TRAIN night as the median of our dt minus WSJT-X's dt over the matched rows).
    /// The detector and its 0.48 s calibration are in WSJT-X's dt convention, so a prior's published dt is converted with this on the way in and the argmax is converted back on the way out.
    /// </summary>
    internal const double PublishedMinusWsjtxDtS = 0.6;

    /// <summary>XC-BUILD R14: the co-location window's half-width in frequency, Hz (the 3.125 Hz gate: half of one 6.25 Hz tone spacing).</summary>
    internal const double ColocationHalfWidthHz = 3.125;

    /// <summary>XC-BUILD R14: the co-location window's half-width in dt, seconds, in OUR OWN dt convention (the one batches 1 to 5 publish).</summary>
    internal const double ColocationHalfWidthS = 0.2;

    /// <summary>
    /// A comparison tolerance so a decode exactly on the window's edge counts as inside (the argmax dt is a grid value plus 0.6 s, which can differ from the exact decimal by a few ulps). Far below the 0.01 s
    /// search step and the 0.1 s the published dt is rounded to, so it moves no real boundary.
    /// </summary>
    internal const double ColocationEdgeToleranceUnits = 1e-9;

    /// <summary>A prior that survived the exclusions: its text, its 79 tones (from the encoder), its position (our own dt convention), its age and the batch (1 to 5) it was published in.</summary>
    internal sealed record Template(string Text, byte[] Tones, double FreqHz, double Dt, int AgeCycles, int Batch = 0);

    /// <summary>The counts of what <see cref="BuildTemplates"/> left out: texts already published in batches 1 to 5 of the cycle, hashed (<c>&lt;...&gt;</c>) texts, and texts the encoder refused.</summary>
    internal readonly record struct Exclusions(int AlreadyDecoded, int Hashed, int Refused);

    /// <summary>
    /// The outcome of one template: whether it was started, S_E*, S_P at the argmax, the argmax (our own dt convention), whether it is a (published) detection and, for a detection only, the SNR of the position.
    /// <see cref="Vetoed"/> is R14's verdict on the position (true when a decode of batches 1 to 5 with a different text is co-located), computed for every tested template whether or not the veto is applied;
    /// <see cref="ParityRejected"/> is true when S_E* cleared T_E and S_P did not clear T_P; <see cref="VetoRejected"/> is true when the template cleared T_E and T_P and the veto APPLIED removed it.
    /// The three of <see cref="Detected"/>, <see cref="ParityRejected"/> and <see cref="VetoRejected"/> are mutually exclusive, and exactly the templates that cleared T_E are in one of them.
    /// </summary>
    internal readonly record struct Outcome(bool Tested, double SStar, double FreqHz, double Dt, bool Detected, int Snr,
                                            double SP = 0.0, bool ParityRejected = false, bool Vetoed = false, bool VetoRejected = false);

    /// <summary>The outcome of one parallel run, in template (nearest-first) order. <see cref="ParityRejected"/> and <see cref="VetoRejected"/> are the counts of the like-named outcomes.</summary>
    internal sealed record RunResult(IReadOnlyList<Template> Templates, Outcome[] Outcomes, int Tested, int Detected, int Abandoned, int ParityRejected = 0, int VetoRejected = 0);

    /// <summary>
    /// R3: the priors for the cycle as templates. A text already published in batches 1 to 5 of the cycle is excluded first; then a text with a <c>&lt;...&gt;</c> hashed field (it cannot be re-encoded); then
    /// a text the encoder refuses (an <see cref="InvalidOperationException"/>, or any other failure of the call). Order is the candidates' order (nearest first). <paramref name="encode"/> is called on the
    /// calling thread, one text at a time: the native encoder is never entered from the workers.
    /// </summary>
    internal static List<Template> BuildTemplates(IReadOnlyList<CrossCyclePriorStore.Candidate> candidates, ISet<string> publishedThisCycle, Func<string, byte[]> encode, out Exclusions excluded)
    {
        int decoded = 0, hashed = 0, refused = 0;
        var templates = new List<Template>(candidates.Count);
        foreach (var c in candidates)
        {
            string text = c.Prior.Text;
            if (publishedThisCycle.Contains(text)) { decoded++; continue; }
            if (text.Contains('<')) { hashed++; continue; }
            byte[] tones;
            try { tones = encode(text); }
            catch (Exception) { refused++; continue; }
            if (tones.Length != CrossCycleTemplateDetector.SymbolCount) { refused++; continue; }
            templates.Add(new Template(text, tones, c.Prior.FreqHz, c.Prior.Dt, c.AgeCycles, c.Prior.Batch));
        }
        excluded = new Exclusions(decoded, hashed, refused);
        return templates;
    }

    /// <summary>
    /// R14: whether a decode of batches 1 to 5 of the cycle, at (<paramref name="decodeFreqHz"/>, <paramref name="decodeDt"/>), is co-located with a detection's argmax: |Δf| &lt;= 3.125 Hz and |Δdt| &lt;= 0.2 s.
    /// <b>Both dts must be in OUR OWN convention</b> (the argmax is converted back with <see cref="PublishedMinusWsjtxDtS"/> in <see cref="Run"/>, before this is called): a convention slip is a 0.6 s error that would make
    /// the veto never fire.
    /// </summary>
    internal static bool IsColocated(double argmaxFreqHz, double argmaxDt, double decodeFreqHz, double decodeDt)
        => Math.Abs(decodeFreqHz - argmaxFreqHz) <= ColocationHalfWidthHz + ColocationEdgeToleranceUnits
        && Math.Abs(decodeDt - argmaxDt) <= ColocationHalfWidthS + ColocationEdgeToleranceUnits;

    /// <summary>
    /// R14: true when any of <paramref name="cycleDecodes"/> (the cycle's batch 1 to 5 publishes: text, frequency, dt in our own convention) has a text different from <paramref name="text"/> and is co-located with the argmax.
    /// </summary>
    internal static bool IsVetoed(string text, double argmaxFreqHz, double argmaxDt, IReadOnlyList<CrossCyclePriorStore.Prior>? cycleDecodes)
    {
        if (cycleDecodes is null) return false;
        for (int i = 0; i < cycleDecodes.Count; i++)
        {
            var d = cycleDecodes[i];
            if (string.Equals(d.Text, text, StringComparison.Ordinal)) continue;     // the same text is not a different station: the "already decoded" exclusion applies first
            if (IsColocated(argmaxFreqHz, argmaxDt, d.FreqHz, d.Dt)) return true;
        }
        return false;
    }

    /// <summary>
    /// R5/R6/R8/R14/R15: run the detector on every template, in parallel over <paramref name="workers"/> workers that claim templates in index order (so the nearest priors start first). A worker stops
    /// claiming when <paramref name="budgetExpired"/> says so; the templates never started are counted as abandoned, and the started ones always finish (their detections count). A template is detected
    /// when S_E* &gt;= <paramref name="threshold"/> AND S_P &gt;= <paramref name="parityThreshold"/> AND (when <paramref name="applyVeto"/>) no co-located decode of another text exists; only a detection pays for the SNR estimate.
    /// </summary>
    /// <param name="templates">The templates, nearest prior first.</param>
    /// <param name="pcm">The cycle's residual buffer (read only).</param>
    /// <param name="threshold">T_E. <see cref="double.PositiveInfinity"/> detects nothing.</param>
    /// <param name="workers">Parallelism (the decoder passes <c>EffectiveSubtractionThreads</c>).</param>
    /// <param name="budgetExpired">True once no further template may START.</param>
    /// <param name="ct">Cancellation.</param>
    /// <param name="parityThreshold">T_P (R15). 0.0 gates nothing (S_P is never negative); the shipped value is a placeholder until QA's TRAIN arm measures it.</param>
    /// <param name="cycleDecodes">The cycle's batch 1 to 5 publishes (R14), in our own dt convention; null means none (nothing is vetoed).</param>
    /// <param name="applyVeto">Whether R14's veto removes a detection. The veto flag on each outcome is computed either way.</param>
    internal static RunResult Run(IReadOnlyList<Template> templates, float[] pcm, double threshold, int workers, Func<bool> budgetExpired, CancellationToken ct,
                                  double parityThreshold = 0.0, IReadOnlyList<CrossCyclePriorStore.Prior>? cycleDecodes = null, bool applyVeto = false)
    {
        int n = templates.Count;
        var outcomes = new Outcome[n];
        int next = -1;

        void Worker()
        {
            while (true)
            {
                ct.ThrowIfCancellationRequested();
                if (budgetExpired()) return;
                int i = Interlocked.Increment(ref next);
                if (i >= n) return;
                var t = templates[i];
                // The detector works in WSJT-X's dt convention: convert the prior's published dt in, and the argmax back out (so Outcome.Dt, the published dt, the veto's comparison and the probe offsets are all in
                // our own convention).
                var r = CrossCycleTemplateDetector.Search(pcm, t.FreqHz, t.Dt - PublishedMinusWsjtxDtS, t.Tones);
                double argmaxDt = r.Dt + PublishedMinusWsjtxDtS;
                bool clearsE = r.SStar >= threshold;
                bool parityRejected = clearsE && !(r.SP >= parityThreshold);
                bool vetoed = IsVetoed(t.Text, r.FreqHz, argmaxDt, cycleDecodes);
                bool vetoRejected = clearsE && !parityRejected && applyVeto && vetoed;
                bool detected = clearsE && !parityRejected && !vetoRejected;
                int snr = detected ? CrossCycleTemplateDetector.CoherentSnrDb(pcm, r.FreqHz, r.Dt, t.Tones) : 0;
                outcomes[i] = new Outcome(true, r.SStar, r.FreqHz, argmaxDt, detected, snr, r.SP, parityRejected, vetoed, vetoRejected);
            }
        }

        if (n > 0)
        {
            int w = Math.Max(1, Math.Min(workers, n));
            if (w == 1) Worker();
            else Parallel.For(0, w, new ParallelOptions { MaxDegreeOfParallelism = w, CancellationToken = ct }, _ => Worker());
        }

        int tested = 0, detectedCount = 0, parityCount = 0, vetoCount = 0;
        foreach (var o in outcomes)
        {
            if (!o.Tested) continue;
            tested++;
            if (o.Detected) detectedCount++;
            if (o.ParityRejected) parityCount++;
            if (o.VetoRejected) vetoCount++;
        }
        return new RunResult(templates, outcomes, tested, detectedCount, n - tested, parityCount, vetoCount);
    }
}
