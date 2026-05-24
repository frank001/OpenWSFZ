using FluentAssertions;
using OpenWSFZ.Ft8.Dsp;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

public sealed class SpectrumAnalyserTests
{
    /// <summary>
    /// T-1: A 1000 Hz sine wave fed to the analyser should produce an energy peak
    /// at bin 171 (= Round(1000 / (12000 / 2048))) within ±2 bins.
    /// </summary>
    [Fact(DisplayName = "FR-008: SpectrumAnalyser computes correct frequency bin for 1000 Hz sine wave (live spectrogram energy delivered to SpectrumReady)")]
    public void SpectrumAnalyser_SineWave_PeaksAtExpectedBin()
    {
        const int    SampleRate  = 12_000;
        const int    FftSize     = SpectrumAnalyser.FftSize;
        const double FrequencyHz = 1_000.0;
        const int    ExpectedBin = 171; // Round(1000 / 5.859375)
        const int    Tolerance   = 2;

        var analyser  = new SpectrumAnalyser();
        float[]? received = null;
        analyser.SpectrumReady += m => received = m;

        var samples = new float[FftSize];
        for (var i = 0; i < FftSize; i++)
            samples[i] = MathF.Sin(2f * MathF.PI * (float)FrequencyHz * i / SampleRate);

        analyser.Push(samples);

        received.Should().NotBeNull();
        var peak = Array.IndexOf(received!, received!.Max());
        peak.Should().BeInRange(ExpectedBin - Tolerance, ExpectedBin + Tolerance,
            "1000 Hz tone should peak at bin ~171");
    }

    /// <summary>
    /// T-2: Pushing 2048 zero samples should produce all-minimum (−120 dBFS) output.
    /// </summary>
    [Fact(DisplayName = "FR-008: SpectrumAnalyser maps silence to -120 dBFS noise floor across all bins")]
    public void SpectrumAnalyser_Silence_ProducesMinimumMagnitudes()
    {
        var analyser  = new SpectrumAnalyser();
        float[]? received = null;
        analyser.SpectrumReady += m => received = m;

        analyser.Push(new float[SpectrumAnalyser.FftSize]);

        received.Should().NotBeNull();
        received!.Should().AllSatisfy(v => v.Should().BeApproximately(-120f, 0.001f));
    }

    /// <summary>
    /// T-3: Pushing 3 × FftSize samples should fire SpectrumReady exactly 3 times.
    /// </summary>
    [Fact(DisplayName = "FR-008: SpectrumAnalyser fires SpectrumReady once per FftSize samples (live update cadence)")]
    public void SpectrumAnalyser_FiresOncePerFftSize()
    {
        var analyser = new SpectrumAnalyser();
        var count    = 0;
        analyser.SpectrumReady += _ => count++;

        analyser.Push(new float[SpectrumAnalyser.FftSize * 3]);

        count.Should().Be(3);
    }
}
