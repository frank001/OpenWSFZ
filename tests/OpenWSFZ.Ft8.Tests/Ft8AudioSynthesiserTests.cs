using FluentAssertions;
using OpenWSFZ.Ft8;
using OpenWSFZ.Ft8.Interop;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Unit tests for <see cref="Ft8AudioSynthesiser"/>.
/// </summary>
public sealed class Ft8AudioSynthesiserTests
{
    private readonly Ft8AudioSynthesiser _sut = new();

    // ── Constants ─────────────────────────────────────────────────────────────

    [Fact(DisplayName = "TotalSampleCount is 606 720 (79 × 7680)")]
    public void TotalSampleCount_Is606720()
    {
        Ft8AudioSynthesiser.TotalSampleCount.Should().Be(606_720);
        (Ft8AudioSynthesiser.SymbolCount * Ft8AudioSynthesiser.SamplesPerSymbol)
            .Should().Be(606_720);
    }

    [Fact(DisplayName = "SampleRateHz is 48 000")]
    public void SampleRateHz_Is48000()
    {
        Ft8AudioSynthesiser.SampleRateHz.Should().Be(48_000);
    }

    [Fact(DisplayName = "SamplesPerSymbol is 7 680 (48000 / 6.25)")]
    public void SamplesPerSymbol_Is7680()
    {
        Ft8AudioSynthesiser.SamplesPerSymbol.Should().Be(7_680);
    }

    // ── Output length ─────────────────────────────────────────────────────────

    [Fact(DisplayName = "Synthesise: output length is exactly 606 720 samples (79 × 7680)")]
    public void Synthesise_OutputLength_Is606720()
    {
        var tones  = new byte[79]; // all zeros (baseFrequencyHz + 0)
        var output = _sut.Synthesise(tones, baseFrequencyHz: 897.0);

        output.Should().HaveCount(Ft8AudioSynthesiser.TotalSampleCount,
            "79 × 7680 = 606 720 samples at 48 kHz");
    }

    // ── Amplitude bounds ──────────────────────────────────────────────────────

    [Fact(DisplayName = "Synthesise: all samples are in [-0.5, 0.5]")]
    public void Synthesise_AllSamples_WithinAmplitudeBounds()
    {
        var tones  = new byte[79];
        // Mix tones 0–7 across 79 symbols
        for (int i = 0; i < 79; i++)
            tones[i] = (byte)(i % 8);

        var output = _sut.Synthesise(tones, baseFrequencyHz: 897.0);

        output.Should().OnlyContain(s => s >= -0.5f && s <= 0.5f,
            "amplitude is normalised to ±0.5 peak (−6 dBFS)");
    }

    [Fact(DisplayName = "Synthesise: peak amplitude approaches 0.5 (not silent)")]
    public void Synthesise_PeakAmplitude_ApproachesHalf()
    {
        var tones  = new byte[79]; // constant tone 0
        var output = _sut.Synthesise(tones, baseFrequencyHz: 897.0);

        float maxAbs = output.Max(Math.Abs);
        maxAbs.Should().BeApproximately(0.5f, 0.001f,
            "a pure sine at 0.5 amplitude should reach peak ≈ 0.5");
    }

    // ── Phase continuity ──────────────────────────────────────────────────────

    [Fact(DisplayName = "Synthesise: phase is continuous at symbol boundary (no step > 2 samples)")]
    public void Synthesise_PhaseContinuous_AtSymbolBoundary()
    {
        // Two adjacent symbols with different tone indices: boundary at sample 7680.
        var tones = new byte[79];
        tones[0] = 0; // tone 0 → baseFreq
        tones[1] = 7; // tone 7 → baseFreq + 43.75 Hz

        var output = _sut.Synthesise(tones, baseFrequencyHz: 897.0);

        // Sample at boundary: last of symbol 0 = [7679], first of symbol 1 = [7680].
        // For continuous-phase FM the waveform must not exhibit a discontinuity —
        // specifically, the gap between adjacent samples across the boundary must be
        // comparable to (not wildly larger than) the gap within either symbol.
        // A phase discontinuity would cause the boundary gap to be much larger.
        float lastOfSym0  = output[Ft8AudioSynthesiser.SamplesPerSymbol - 1];
        float firstOfSym1 = output[Ft8AudioSynthesiser.SamplesPerSymbol];

        // Typical within-symbol step at these frequencies (~897 Hz, 48 kHz) is ~0.117.
        // A phase discontinuity would inject a step many times larger.
        // We allow up to 0.5 (maximum possible amplitude change in one sample).
        float step = Math.Abs(firstOfSym1 - lastOfSym0);
        step.Should().BeLessOrEqualTo(0.5f,
            "continuous-phase FM must not produce a phase discontinuity at symbol boundaries; " +
            $"boundary step was {step:F4}");
    }

    // ── Argument validation ───────────────────────────────────────────────────

    [Fact(DisplayName = "Synthesise: null tones throws ArgumentNullException")]
    public void Synthesise_NullTones_ThrowsArgumentNullException()
    {
        var act = () => _sut.Synthesise(null!, 897.0);
        act.Should().ThrowExactly<ArgumentNullException>().WithParameterName("tones");
    }

    [Fact(DisplayName = "Synthesise: wrong tone count throws ArgumentException")]
    public void Synthesise_WrongToneCount_ThrowsArgumentException()
    {
        var act = () => _sut.Synthesise(new byte[78], 897.0);
        act.Should().ThrowExactly<ArgumentException>()
           .WithParameterName("tones")
           .WithMessage("*79*");
    }

    [Fact(DisplayName = "Synthesise: tone index > 7 throws ArgumentException")]
    public void Synthesise_ToneOutOfRange_ThrowsArgumentException()
    {
        var tones = new byte[79];
        tones[5] = 8; // invalid — FT8 is 8-tone (0–7)

        var act = () => _sut.Synthesise(tones, 897.0);
        act.Should().ThrowExactly<ArgumentException>()
           .WithParameterName("tones")
           .WithMessage("*[0, 7]*");
    }

    [Fact(DisplayName = "Synthesise: negative base frequency throws ArgumentOutOfRangeException")]
    public void Synthesise_NegativeFrequency_ThrowsArgumentOutOfRangeException()
    {
        var act = () => _sut.Synthesise(new byte[79], baseFrequencyHz: -1.0);
        act.Should().ThrowExactly<ArgumentOutOfRangeException>()
           .WithParameterName("baseFrequencyHz");
    }

    // ── End-to-end round-trip (native encode → synthesise) ───────────────────

    [Fact(DisplayName = "Synthesise: round-trip from EncodeMessage produces non-silent output")]
    public void Synthesise_RoundTripFromEncodeMessage_NonSilent()
    {
        // Arrange: encode a standard FT8 message via the native shim
        var tones = new byte[Ft8LibInterop.EncodedToneCount];
        Ft8LibInterop.EncodeMessage("Q1OFZ Q1TST JO33", tones);

        // Act: synthesise audio at 897 Hz base frequency
        var audio = _sut.Synthesise(tones, 897.0);

        // Assert: the output must not be silent (all-zero would mean the synthesiser is broken)
        float rms = MathF.Sqrt(audio.Average(s => s * s));
        rms.Should().BeGreaterThan(0.1f,
            "synthesised audio must have non-trivial RMS amplitude; " +
            $"got {rms:F4} — indicates a working synthesis at baseFreq=897 Hz");
    }
}
