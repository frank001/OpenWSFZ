using FluentAssertions;
using OpenWSFZ.Ft8.Dsp;
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
        var rng  = new Random(42);
        var grid = new float[79, 8];
        for (int s = 0; s < 79; s++)
            for (int t = 0; t < 8; t++)
                grid[s, t] = (float)(rng.NextDouble() * 2.0 - 1.0);

        var candidates = CostasSynchroniser.FindCandidates(grid, threshold: 0.9f);

        candidates.Should().BeEmpty("random noise should not match the Costas pattern at high threshold");
    }

    // ── Helpers ──────────────────────────────────────────────────────────────

    private static float[,] BuildPerfectCostasGrid(int freqShift)
    {
        var grid = new float[79, 8];

        // Fill base with very low energy.
        for (int s = 0; s < 79; s++)
            for (int t = 0; t < 8; t++)
                grid[s, t] = -10f;

        // Place high energy at the three Costas array positions.
        ReadOnlySpan<int> positions = [0, 36, 72];
        ReadOnlySpan<int> pattern   = CostasSynchroniser.CostasPattern;

        foreach (int pos in positions)
        {
            for (int i = 0; i < pattern.Length; i++)
            {
                int sym  = pos + i;
                int tone = (pattern[i] + freqShift) % 8;
                grid[sym, tone] = 10f;
            }
        }

        return grid;
    }
}
