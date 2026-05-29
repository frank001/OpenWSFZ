namespace OpenWSFZ.Ft8.Dsp;

/// <summary>
/// Locates FT8 transmissions within a 79-symbol log-energy grid by cross-correlating
/// the received grid against the known Costas array pattern.
///
/// FT8 transmissions carry three Costas arrays of 7 symbols each at positions
/// 0, 36, and 72 within the 79-symbol frame (Franke &amp; Taylor 2019).
/// </summary>
internal static class CostasSynchroniser
{
    /// <summary>
    /// The FT8 Costas array: tone index (0-7) for each of the 7 sync symbols.
    /// Source: Franke &amp; Taylor, "The FT4 and FT8 Communication Protocols", QEX Nov/Dec 2019, Table 1.
    /// </summary>
    public static ReadOnlySpan<int> CostasPattern => [3, 1, 4, 0, 6, 5, 2];

    /// <summary>Positions of the three Costas arrays within the 79-symbol frame.</summary>
    private static ReadOnlySpan<int> CostasPositions => [0, 36, 72];

    /// <summary>
    /// Searches the log-energy grid for FT8 synchronisation candidates using softmax
    /// Costas scoring (D18 fix).
    ///
    /// <para>
    /// Each Costas symbol contributes <c>exp(E_costas − logSumExp(E_0…E_7))</c> to the
    /// score — the softmax probability that the Costas tone is the unique dominant tone.
    /// This is 1/8 for uniform noise and approaches 1.0 for an isolated real signal,
    /// making the gate robust to crowded-band conditions (the old hard-max formula
    /// evaluated to ~0.74/position on a live 40 m FT8 band, causing 24 % false-alarm
    /// rate).
    /// </para>
    /// </summary>
    /// <param name="grid">
    /// A <c>float[79, GridWidth]</c> log-energy grid produced by
    /// <see cref="SymbolExtractor.Extract"/> or
    /// <see cref="SymbolExtractor.ExtractFromSpectrogram"/>.
    /// </param>
    /// <param name="threshold">
    /// Minimum normalised score (0–1) to report a candidate.
    /// The threshold of 0.45 is appropriate for the softmax formula.
    /// </param>
    /// <returns>
    /// Candidates sorted by score descending. Each candidate's <c>FreqBinOffset</c> is an
    /// integer number of 6.25 Hz tone bins from the grid's base frequency.
    /// </returns>
    public static IReadOnlyList<SyncCandidate> FindCandidates(float[,] grid, float threshold = 0.4f)
    {
        int symbols = grid.GetLength(0); // 79

        // Maximum correlation score: all three Costas arrays aligned perfectly.
        // Each array contributes 7 tone matches; each match contributes 1.0 normalised.
        float maxPossible = CostasPositions.Length * CostasPattern.Length; // 21

        var candidates = new List<SyncCandidate>();

        // Frequency sweep: slide by integer tone offsets 0–7. The grid has 15 columns
        // (GridWidth = ToneCount + 7) so that offset 7 still keeps all 8 signal tones
        // within bounds — no modulo-8 wrapping needed. (D4)
        // The caller (Ft8Decoder) performs the outer time-domain sweep.
        for (int freqShift = 0; freqShift < SymbolExtractor.ToneCount; freqShift++)
        {
            float score = ComputeCostasScore(grid, symbols, freqShift);
            float normScore = score / maxPossible;

            if (normScore >= threshold)
            {
                candidates.Add(new SyncCandidate(
                    SymbolOffset:  0,
                    FreqBinOffset: freqShift,
                    Score:         normScore));
            }
        }

        candidates.Sort((a, b) => b.Score.CompareTo(a.Score));
        return candidates;
    }

    private static float ComputeCostasScore(float[,] grid, int symbols, int freqShift)
    {
        // The 8 signal tones occupy columns [freqShift, freqShift + ToneCount).
        // The grid is GridWidth = 15 columns wide, so any freqShift 0–7 keeps the
        // signal tones within bounds without wrapping. (D4)
        const int tones = SymbolExtractor.ToneCount; // 8
        float score = 0f;

        foreach (int pos in CostasPositions)
        {
            for (int i = 0; i < CostasPattern.Length; i++)
            {
                int sym  = pos + i;
                int tone = CostasPattern[i] + freqShift; // no % wrapping (D4)

                if (sym >= symbols) break;

                // Softmax Costas scoring (D18 fix).
                //
                // The previous formula, exp(costas − maxE), computes energy at the Costas
                // tone relative to the MAXIMUM of the 8 tones.  On an isolated signal this
                // is fine (1.0 when Costas tone is dominant).  On a live crowded band, all
                // 8 tones are within 2–4 dB → maxE ≈ costas → exp(0) ≈ 1.0 everywhere
                // → false-positive rate of 24 %, flooding the decode pipeline.
                //
                // The softmax formula exp(costas − logSumExp(all 8)) = E_costas / Σ E_k
                // is the standard probability that the Costas tone is the unique dominant
                // tone.  Its properties:
                //   • Uniform noise (all 8 tones equal):        contribution = 1/8 = 0.125 ✓
                //   • Real isolated signal (one dominant tone):  contribution → 1.0         ✓
                //   • Crowded band (N tones elevated equally):   contribution ≈ 1/N < 0.45  ✓
                //
                // The noise-floor gate (maxE < −18) is retained so that silent-band frames
                // with FFT floor values ≈ −23 are skipped without corrupting the score.
                float costas = grid[sym, tone];
                float maxE   = costas;
                for (int t = freqShift; t < freqShift + tones; t++)
                    if (grid[sym, t] > maxE) maxE = grid[sym, t];

                if (maxE < -18f) continue;  // silent-band guard (D9, D10, D11)

                float logSumAll = LogSumExp8(
                    grid[sym, freqShift + 0], grid[sym, freqShift + 1],
                    grid[sym, freqShift + 2], grid[sym, freqShift + 3],
                    grid[sym, freqShift + 4], grid[sym, freqShift + 5],
                    grid[sym, freqShift + 6], grid[sym, freqShift + 7]);

                // Softmax Costas scoring (D18 fix).
                //
                // exp(costas − logSumAll) = E_costas / Σ_k E_k is the softmax probability
                // that the Costas tone is the unique dominant tone.
                //   • Uniform noise (all 8 tones equal):        contribution = 1/8 = 0.125
                //   • Real isolated signal (one dominant tone):  contribution → 1.0
                //   • Crowded band (N tones elevated equally):   contribution ≈ 1/N < threshold
                score += MathF.Exp(costas - logSumAll);
            }
        }

        return score;
    }

    /// <summary>
    /// Numerically stable log-sum-exp over 8 values:
    /// <c>log(exp(a) + exp(b) + … + exp(h)) = m + log(Σ exp(x − m))</c>
    /// where <c>m = max(a…h)</c>.
    /// </summary>
    private static float LogSumExp8(
        float a, float b, float c, float d,
        float e, float f, float g, float h)
    {
        float m = MathF.Max(MathF.Max(MathF.Max(a, b), MathF.Max(c, d)),
                            MathF.Max(MathF.Max(e, f), MathF.Max(g, h)));
        return m + MathF.Log(
            MathF.Exp(a - m) + MathF.Exp(b - m) + MathF.Exp(c - m) + MathF.Exp(d - m) +
            MathF.Exp(e - m) + MathF.Exp(f - m) + MathF.Exp(g - m) + MathF.Exp(h - m));
    }
}

/// <summary>A synchronisation candidate returned by <see cref="CostasSynchroniser"/>.</summary>
/// <param name="SymbolOffset">Symbol index offset of the transmission start within the buffer.</param>
/// <param name="FreqBinOffset">Tone-bin offset of the lowest tone from the grid base frequency.</param>
/// <param name="Score">Normalised correlation score in [0, 1].</param>
internal sealed record SyncCandidate(int SymbolOffset, int FreqBinOffset, float Score);
