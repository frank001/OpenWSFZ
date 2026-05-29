using System;
using FluentAssertions;
using OpenWSFZ.Ft8.Dsp;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// FR-029: Unit tests for <see cref="SymbolExtractor.FillSpectrogramExact"/>.
///
/// Verifies that the Bluestein 1 920-point exact-DFT spectrogram places energy
/// on the correct bin (no spectral leakage) for pure FT8-frequency sine tones.
/// </summary>
public sealed class SymbolExtractorTests
{
    private const int SampleRate      = 12_000;
    private const int SamplesPerSymbol = 1_920;
    private const double ToneSpacing  = 6.25;

    // ── Helpers ───────────────────────────────────────────────────────────────

    /// <summary>
    /// Generates a PCM buffer long enough for one symbol at the given frequency.
    /// Uses an exact FT8-grid frequency so the DFT should give near-perfect energy
    /// concentration on a single bin.
    /// </summary>
    private static float[] MakeToneBuffer(double freqHz, int startSample = 0)
    {
        int totalSamples = startSample + SamplesPerSymbol * SymbolExtractor.SymbolCount;
        var pcm = new float[totalSamples];
        for (int s = 0; s < SamplesPerSymbol * SymbolExtractor.SymbolCount; s++)
        {
            int idx = startSample + s;
            pcm[idx] = (float)Math.Sin(2.0 * Math.PI * freqHz * s / SampleRate);
        }
        return pcm;
    }

    // ── Tests ─────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-029: FillSpectrogramExact — 1000 Hz tone concentrates energy at bin 160")]
    public void FillSpectrogramExact_1000HzTone_EnergyAtBin160()
    {
        // 1000 Hz / 6.25 Hz = 160.0 exactly → bin 160
        double freqHz = 1000.0;
        int expectedBin = 160;

        var pcm = MakeToneBuffer(freqHz);
        var spectrogram = new float[SymbolExtractor.SymbolCount, SymbolExtractor.ExactSpecBins];

        SymbolExtractor.FillSpectrogramExact(pcm, startSample: 0, spectrogram);

        // Check the first symbol's bin energies.
        float peakEnergy  = spectrogram[0, expectedBin];
        float nearbyLeft  = spectrogram[0, expectedBin - 1];
        float nearbyRight = spectrogram[0, expectedBin + 1];

        peakEnergy.Should().BeGreaterThan(nearbyLeft * 10f,
            "1000 Hz maps exactly to bin 160; adjacent bins should be ≥10× weaker");
        peakEnergy.Should().BeGreaterThan(nearbyRight * 10f,
            "1000 Hz maps exactly to bin 160; adjacent bins should be ≥10× weaker");
    }

    [Fact(DisplayName = "FR-029: FillSpectrogramExact — 500 Hz tone concentrates energy at bin 80")]
    public void FillSpectrogramExact_500HzTone_EnergyAtBin80()
    {
        // 500 Hz / 6.25 Hz = 80.0 exactly → bin 80
        double freqHz = 500.0;
        int expectedBin = 80;

        var pcm = MakeToneBuffer(freqHz);
        var spectrogram = new float[SymbolExtractor.SymbolCount, SymbolExtractor.ExactSpecBins];

        SymbolExtractor.FillSpectrogramExact(pcm, startSample: 0, spectrogram);

        float peakEnergy = spectrogram[0, expectedBin];
        float nearbyLeft = spectrogram[0, expectedBin - 1];
        float nearbyRight = spectrogram[0, expectedBin + 1];

        peakEnergy.Should().BeGreaterThan(nearbyLeft * 10f,
            "500 Hz maps exactly to bin 80 with the 1920-point DFT");
        peakEnergy.Should().BeGreaterThan(nearbyRight * 10f,
            "500 Hz maps exactly to bin 80 with the 1920-point DFT");
    }

    [Fact(DisplayName = "FR-029: FillSpectrogramExact — ExactSpecBins is 960 (half of 1920)")]
    public void ExactSpecBins_Is960()
    {
        SymbolExtractor.ExactSpecBins.Should().Be(960,
            "ExactSpecBins = SamplesPerSymbol / 2 = 1920 / 2 = 960");
    }

    [Fact(DisplayName = "FR-029: FillSpectrogramExact — out-of-bounds symbol rows are zeroed (stale-data guard)")]
    public void FillSpectrogramExact_ShortPcm_ZeroesOutOfBoundsRows()
    {
        // Provide only 1 symbol's worth of PCM so all other rows fall outside the buffer.
        var pcm = new float[SamplesPerSymbol]; // exactly 1 symbol, startSample=0
        for (int s = 0; s < SamplesPerSymbol; s++)
            pcm[s] = (float)Math.Sin(2.0 * Math.PI * 1000.0 * s / SampleRate);

        // Pre-fill result with non-zero sentinel values.
        var spectrogram = new float[SymbolExtractor.SymbolCount, SymbolExtractor.ExactSpecBins];
        for (int s = 1; s < SymbolExtractor.SymbolCount; s++)
            for (int b = 0; b < SymbolExtractor.ExactSpecBins; b++)
                spectrogram[s, b] = 9999f;

        SymbolExtractor.FillSpectrogramExact(pcm, startSample: 0, spectrogram);

        // Row 0 should have real energy; rows 1..78 should all be zero.
        spectrogram[0, 160].Should().BeGreaterThan(0f,
            "first symbol row should contain energy for the 1000 Hz tone");

        for (int s = 1; s < SymbolExtractor.SymbolCount; s++)
            spectrogram[s, 0].Should().Be(0f,
                $"row {s} falls outside the PCM buffer and must be zeroed (D5 stale-data guard)");
    }

    [Fact(DisplayName = "FR-029: FillSpectrogramExact — multiple symbol rows are independent")]
    public void FillSpectrogramExact_MultipleSymbols_EachRowHasCorrectPeak()
    {
        // Two consecutive symbols at different FT8-grid frequencies.
        // Symbol 0: 750 Hz → bin 120.  Symbol 1: 1250 Hz → bin 200.
        double freq0 = 750.0;
        double freq1 = 1250.0;
        int bin0 = 120;
        int bin1 = 200;

        var pcm = new float[SamplesPerSymbol * SymbolExtractor.SymbolCount];
        // Symbol 0 window
        for (int s = 0; s < SamplesPerSymbol; s++)
            pcm[s] = (float)Math.Sin(2.0 * Math.PI * freq0 * s / SampleRate);
        // Symbol 1 window
        for (int s = 0; s < SamplesPerSymbol; s++)
            pcm[SamplesPerSymbol + s] = (float)Math.Sin(2.0 * Math.PI * freq1 * s / SampleRate);

        var spectrogram = new float[SymbolExtractor.SymbolCount, SymbolExtractor.ExactSpecBins];
        SymbolExtractor.FillSpectrogramExact(pcm, startSample: 0, spectrogram);

        spectrogram[0, bin0].Should().BeGreaterThan(spectrogram[0, bin0 - 1] * 10f,
            "symbol 0 at 750 Hz should peak at bin 120");
        spectrogram[0, bin0].Should().BeGreaterThan(spectrogram[0, bin0 + 1] * 10f,
            "symbol 0 at 750 Hz should peak at bin 120");

        spectrogram[1, bin1].Should().BeGreaterThan(spectrogram[1, bin1 - 1] * 10f,
            "symbol 1 at 1250 Hz should peak at bin 200");
        spectrogram[1, bin1].Should().BeGreaterThan(spectrogram[1, bin1 + 1] * 10f,
            "symbol 1 at 1250 Hz should peak at bin 200");
    }
}
