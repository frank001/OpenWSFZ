using FluentAssertions;
using OpenWSFZ.Ft8.Dsp;
using System;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Ft8Decoder: CostasSynchroniserTests
/// </summary>
public sealed class CostasSynchroniserTests
{
    /// <summary>
    /// Pinning test: the Costas pattern must match the FT8 spec exactly (Franke & Taylor 2019, Table 1).
    /// The existing grid-based tests are self-referential (they read the pattern from the code under
    /// test), so they cannot catch a wrong value here. This test is the spec anchor.
    /// </summary>
    [Fact(DisplayName = "FR-001: CostasPattern matches FT8 specification [3,1,4,0,6,5,2]")]
    public void CostasPattern_MatchesFt8Specification()
    {
        int[] expected = [3, 1, 4, 0, 6, 5, 2];
        CostasSynchroniser.CostasPattern.ToArray().Should().Equal(expected,
            "the FT8 Costas array is [3,1,4,0,6,5,2] per Franke & Taylor 2019 — wrong value = zero decodes");
    }

    [Fact]
    public void FindCandidates_PerfectCostasGrid_ReturnsHighScoringCandidate()
    {
        // Build a 79×8 grid where the Costas tone positions have maximum energy
        // and all other tones have zero energy.
        var grid = BuildPerfectCostasGrid(freqShift: 0);

        var candidates = CostasSynchroniser.FindCandidates(grid, threshold: 0.9f);

        candidates.Should().NotBeEmpty("a perfect Costas pattern should score above threshold");
        candidates[0].Score.Should().BeApproximately(1.0f, 0.01f,
            "all 21 Costas tone positions match perfectly");
        candidates[0].FreqBinOffset.Should().Be(0,
            "the sync pattern was placed at freq shift 0");
    }

    [Fact]
    public void FindCandidates_CostasShiftedByTwoBins_DetectsAtCorrectOffset()
    {
        // Place the Costas pattern shifted by 2 tone bins.
        const int shift = 2;
        var grid = BuildPerfectCostasGrid(freqShift: shift);

        var candidates = CostasSynchroniser.FindCandidates(grid, threshold: 0.9f);

        candidates.Should().NotBeEmpty();
        candidates[0].FreqBinOffset.Should().Be(shift,
            "the sync pattern was placed at freq shift 2");
    }

    [Fact]
    public void FindCandidates_NoisyGrid_ReturnsNoCandidatesAboveThreshold()
    {
        // Random log-energy values — no meaningful Costas pattern.
        // Grid is GridWidth = 15 columns wide, matching the D4 convention. (D4)
        var rng  = new Random(42);
        var grid = new float[79, SymbolExtractor.GridWidth];
        for (int s = 0; s < 79; s++)
            for (int t = 0; t < SymbolExtractor.GridWidth; t++)
                grid[s, t] = (float)(rng.NextDouble() * 2.0 - 1.0);

        var candidates = CostasSynchroniser.FindCandidates(grid, threshold: 0.9f);

        candidates.Should().BeEmpty("random noise should not match the Costas pattern at high threshold");
    }

    /// <summary>
    /// Task 4.2-bis: verifies that the time-domain sweep path works end-to-end.
    /// The caller (Ft8Decoder) extracts the grid with a non-zero startSample;
    /// CostasSynchroniser must still return the correct frequency-bin candidate.
    /// </summary>
    [Fact(DisplayName = "FR-001: CostasSynchroniser detects Costas pattern when SymbolExtractor.Extract is called with a non-zero startSample (4.2-bis)")]
    public void FindCandidates_GridExtractedAtNonZeroStartSample_DetectsCorrectFreqBin()
    {
        // The FT8 signal starts 5 symbols into the buffer (as if the operator started
        // the daemon 5 × 0.16 s ≈ 0.8 s into the UTC cycle).
        const int    symbolOffset = 5;
        const int    freqShift    = 3;
        const double baseFreqHz   = 500.0;

        int   startSample = symbolOffset * SymbolExtractor.SamplesPerSymbol;
        float[] pcm       = BuildSyntheticFt8Pcm(symbolOffset, freqShift, baseFreqHz);

        // Let the caller (simulated here) extract the grid with the correct startSample.
        var grid       = SymbolExtractor.Extract(pcm, startSample, baseFreqHz);
        var candidates = CostasSynchroniser.FindCandidates(grid, threshold: 0.5f);

        candidates.Should().NotBeEmpty(
            "Costas tones are embedded at the expected symbol + frequency offset");
        candidates[0].FreqBinOffset.Should().Be(freqShift,
            $"the signal was placed {freqShift} tone-bins above the base frequency");
    }

    // ── Helpers ──────────────────────────────────────────────────────────────

    /// <summary>
    /// Generates a PCM buffer that contains FT8 Costas tones (and silence for data symbols)
    /// starting at the given symbol offset.
    /// </summary>
    private static float[] BuildSyntheticFt8Pcm(int symbolOffset, int freqShift, double baseFreqHz)
    {
        const int SampleRate = 12_000;

        int startSample  = symbolOffset * SymbolExtractor.SamplesPerSymbol;
        int totalSamples = startSample + SymbolExtractor.SymbolCount * SymbolExtractor.SamplesPerSymbol;
        var pcm          = new float[totalSamples];

        ReadOnlySpan<int> costasPositions = [0, 36, 72];
        ReadOnlySpan<int> pattern         = CostasSynchroniser.CostasPattern;

        foreach (int pos in costasPositions)
        {
            for (int i = 0; i < pattern.Length; i++)
            {
                int    sym         = pos + i;
                // No % 8: the tone column is pattern[i] + freqShift (range 0–13 for freqShift
                // 0–7), matching the GridWidth = 15 convention in ExtractFromSpectrogram. (D4)
                int    toneCol     = pattern[i] + freqShift;
                double toneHz      = baseFreqHz + toneCol * SymbolExtractor.ToneSpacingHz;
                int    sampleStart = startSample + sym * SymbolExtractor.SamplesPerSymbol;

                for (int s = 0; s < SymbolExtractor.SamplesPerSymbol; s++)
                    pcm[sampleStart + s] = (float)Math.Sin(2.0 * Math.PI * toneHz * s / SampleRate);
            }
        }

        return pcm;
    }

    private static float[,] BuildPerfectCostasGrid(int freqShift)
    {
        // Grid is GridWidth = 15 columns wide so any freqShift 0–7 keeps all
        // 8 signal tones within bounds without % 8 wrapping. (D4)
        var grid = new float[79, SymbolExtractor.GridWidth];

        // Fill with very low energy.
        for (int s = 0; s < 79; s++)
            for (int t = 0; t < SymbolExtractor.GridWidth; t++)
                grid[s, t] = -10f;

        // Place high energy at the three Costas array positions using real
        // FT8-spec tone placement — no modulo wrapping. (D4)
        ReadOnlySpan<int> positions = [0, 36, 72];
        ReadOnlySpan<int> pattern   = CostasSynchroniser.CostasPattern;

        foreach (int pos in positions)
        {
            for (int i = 0; i < pattern.Length; i++)
            {
                int sym  = pos + i;
                int tone = pattern[i] + freqShift; // no % wrapping (D4)
                grid[sym, tone] = 10f;
            }
        }

        return grid;
    }
}
