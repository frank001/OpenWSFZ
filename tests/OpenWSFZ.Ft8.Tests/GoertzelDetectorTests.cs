using FluentAssertions;
using OpenWSFZ.Ft8.Dsp;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Ft8Decoder: GoertzelDetectorTests
/// </summary>
public sealed class GoertzelDetectorTests
{
    private const int SampleRate   = 12_000;
    private const int WindowSamples = SymbolExtractor.SamplesPerSymbol; // 1 920

    [Fact]
    public void ComputeEnergy_PureTone_PeaksAtCorrectBin()
    {
        // Generate a 1920-sample sine wave at 1025 Hz (just inside tone-1 bin for base = 1000 Hz,
        // spacing 6.25 Hz → tones at 1000, 1006.25, 1012.5, ...).
        double targetHz = 1012.5; // tone-2 exactly
        var samples = GenerateSine(targetHz, WindowSamples, SampleRate);

        // The energy at the target frequency should greatly exceed adjacent tones.
        float energyOn  = GoertzelDetector.ComputeEnergy(samples, targetHz,                SampleRate);
        float energyOff = GoertzelDetector.ComputeEnergy(samples, targetHz + 6.25, SampleRate);

        energyOn.Should().BeGreaterThan(energyOff * 100f,
            "energy at the pure tone frequency should dominate adjacent bins");
    }

    [Fact]
    public void Extract_PureToneSingleSymbol_PeaksAtCorrectTone()
    {
        // 15 s of silence, then embed a pure tone for the first symbol at base 1000 Hz + tone 3.
        double baseHz = 1000.0;
        int    targetTone = 3;
        double toneHz = baseHz + targetTone * SymbolExtractor.ToneSpacingHz;

        var pcm = new float[15 * SampleRate];
        var symbol = GenerateSine(toneHz, SymbolExtractor.SamplesPerSymbol, SampleRate);
        symbol.CopyTo(new Span<float>(pcm, 0, SymbolExtractor.SamplesPerSymbol));

        var grid = SymbolExtractor.Extract(pcm, startSample: 0, baseFrequencyHz: baseHz);

        // Find the peak tone for symbol 0.
        int peakTone  = 0;
        float peakVal = grid[0, 0];
        for (int t = 1; t < SymbolExtractor.ToneCount; t++)
        {
            if (grid[0, t] > peakVal)
            {
                peakVal  = grid[0, t];
                peakTone = t;
            }
        }

        peakTone.Should().Be(targetTone,
            "the tone carrying the pure sine should have the highest log-energy");
    }

    // ── Helpers ──────────────────────────────────────────────────────────────

    private static float[] GenerateSine(double frequencyHz, int samples, int sampleRate)
    {
        var buf = new float[samples];
        for (int i = 0; i < samples; i++)
            buf[i] = (float)Math.Sin(2.0 * Math.PI * frequencyHz * i / sampleRate);
        return buf;
    }
}
