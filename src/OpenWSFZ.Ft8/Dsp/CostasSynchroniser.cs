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
    /// Searches the log-energy grid for FT8 synchronisation candidates.
    /// </summary>
    /// <param name="grid">
    /// A <c>float[79, 8]</c> log-energy grid produced by <see cref="SymbolExtractor.Extract"/>.
    /// </param>
    /// <param name="threshold">
    /// Minimum correlation score (normalised, 0–1) to report a candidate.
    /// Values around 0.4–0.6 are typical starting points.
    /// </param>
    /// <returns>
    /// Candidates sorted by score descending. Each candidate's <c>FreqBinOffset</c> is an
    /// integer number of 6.25 Hz tone bins from the grid's base frequency.
    /// </returns>
    public static IReadOnlyList<SyncCandidate> FindCandidates(float[,] grid, float threshold = 0.4f)
    {
        int symbols = grid.GetLength(0); // 79
        int tones   = grid.GetLength(1); // 8

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

                // Score contribution: energy at the Costas tone relative to the peak
                // among all 8 signal tones for this symbol.
                float costas = grid[sym, tone];
                float maxE   = costas;
                for (int t = freqShift; t < freqShift + tones; t++)
                    if (grid[sym, t] > maxE) maxE = grid[sym, t];

                // Noise-floor gate: when all 8 tones have energy near log(ε) ≈ −23
                // (the FFT spectrogram floor = log(0 + 1e-10)), they are all within
                // 0.1 log-units of each other and every tone trivially satisfies the
                // soft-match criterion — producing a "perfect" Costas score in silent
                // frequency bands.  Require the maximum energy to be above −18 to
                // avoid counting noise symbols.  Any real signal of interest (even at
                // −60 dBFS) produces log-energy above −10.
                if (maxE < -18f) continue;

                // Normalised soft-match: 1 if energy at Costas position is the peak.
                score += costas >= maxE - 0.1f ? 1.0f : 0.0f;
            }
        }

        return score;
    }
}

/// <summary>A synchronisation candidate returned by <see cref="CostasSynchroniser"/>.</summary>
/// <param name="SymbolOffset">Symbol index offset of the transmission start within the buffer.</param>
/// <param name="FreqBinOffset">Tone-bin offset of the lowest tone from the grid base frequency.</param>
/// <param name="Score">Normalised correlation score in [0, 1].</param>
internal sealed record SyncCandidate(int SymbolOffset, int FreqBinOffset, float Score);
