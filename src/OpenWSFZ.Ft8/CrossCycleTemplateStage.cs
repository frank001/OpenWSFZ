using OpenWSFZ.Ft8.Dsp;

namespace OpenWSFZ.Ft8;

/// <summary>
/// XC-BUILD R3/R5/R6/R8: turns a cycle's prior candidates into 79-tone templates (counting what is excluded) and runs the detector over them in parallel, nearest prior first, stopping to START templates when
/// the cycle budget says so. Pure with respect to the decoder: it takes the buffer, the threshold, the worker count and a "budget expired" predicate, so the tests drive it with no clock and no sleeps.
/// </summary>
internal static class CrossCycleTemplateStage
{
    /// <summary>A prior that survived the exclusions: its text, its 79 tones (from the encoder) and its position and age.</summary>
    internal sealed record Template(string Text, byte[] Tones, double FreqHz, double Dt, int AgeCycles);

    /// <summary>The counts of what <see cref="BuildTemplates"/> left out: texts already published in batches 1 to 5 of the cycle, hashed (<c>&lt;...&gt;</c>) texts, and texts the encoder refused.</summary>
    internal readonly record struct Exclusions(int AlreadyDecoded, int Hashed, int Refused);

    /// <summary>The outcome of one template: whether it was started, S_E*, the argmax, and (for a detection only) the SNR of the position.</summary>
    internal readonly record struct Outcome(bool Tested, double SStar, double FreqHz, double Dt, bool Detected, int Snr);

    /// <summary>The outcome of one parallel run, in template (nearest-first) order.</summary>
    internal sealed record RunResult(IReadOnlyList<Template> Templates, Outcome[] Outcomes, int Tested, int Detected, int Abandoned);

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
            templates.Add(new Template(text, tones, c.Prior.FreqHz, c.Prior.Dt, c.AgeCycles));
        }
        excluded = new Exclusions(decoded, hashed, refused);
        return templates;
    }

    /// <summary>
    /// R5/R6/R8: run the detector on every template, in parallel over <paramref name="workers"/> workers that claim templates in index order (so the nearest priors start first). A worker stops
    /// claiming when <paramref name="budgetExpired"/> says so; the templates never started are counted as abandoned, and the started ones always finish (their detections count). A template is detected
    /// when S_E* &gt;= <paramref name="threshold"/>; only a detection pays for the SNR estimate.
    /// </summary>
    /// <param name="templates">The templates, nearest prior first.</param>
    /// <param name="pcm">The cycle's residual buffer (read only).</param>
    /// <param name="threshold">T_E. <see cref="double.PositiveInfinity"/> detects nothing.</param>
    /// <param name="workers">Parallelism (the decoder passes <c>EffectiveSubtractionThreads</c>).</param>
    /// <param name="budgetExpired">True once no further template may START.</param>
    /// <param name="ct">Cancellation.</param>
    internal static RunResult Run(IReadOnlyList<Template> templates, float[] pcm, double threshold, int workers, Func<bool> budgetExpired, CancellationToken ct)
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
                var r = CrossCycleTemplateDetector.Search(pcm, t.FreqHz, t.Dt, t.Tones);
                bool detected = r.SStar >= threshold;
                int snr = detected ? CrossCycleTemplateDetector.CoherentSnrDb(pcm, r.FreqHz, r.Dt, t.Tones) : 0;
                outcomes[i] = new Outcome(true, r.SStar, r.FreqHz, r.Dt, detected, snr);
            }
        }

        if (n > 0)
        {
            int w = Math.Max(1, Math.Min(workers, n));
            if (w == 1) Worker();
            else Parallel.For(0, w, new ParallelOptions { MaxDegreeOfParallelism = w, CancellationToken = ct }, _ => Worker());
        }

        int tested = 0, detectedCount = 0;
        foreach (var o in outcomes)
        {
            if (!o.Tested) continue;
            tested++;
            if (o.Detected) detectedCount++;
        }
        return new RunResult(templates, outcomes, tested, detectedCount, n - tested);
    }
}
