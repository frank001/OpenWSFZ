using FluentAssertions;
using OpenWSFZ.Ft8.Subfeas;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// coh-fb-residual (REPLAY ONLY): the switch parser and the pure audio selector. The decoder-level wiring is in
/// <see cref="CoherentFallbackWiringTests"/>. Deterministic: no timing, no I/O.
/// </summary>
public sealed class CohFallbackAudioTests
{
    [Theory(DisplayName = "coh-fb-residual: only the exact, case-sensitive value 'residual' activates the switch")]
    [InlineData(null, false)]
    [InlineData("", false)]
    [InlineData("1", false)]
    [InlineData("RESIDUAL", false)]
    [InlineData("Residual", false)]
    [InlineData(" residual", false)]
    [InlineData("residual ", false)]
    [InlineData("original", false)]
    [InlineData("residual", true)]
    public void IsActive_OnlyExactResidual(string? raw, bool expected)
        => CohFallbackAudio.IsActive(raw).Should().Be(expected);

    private static readonly float[] Original = new float[180_000];
    private static readonly float[] ResidualBuf = new float[180_000];
    private static readonly float[] ThirdBuf = new float[180_000];

    private static SubtractionPass.ResidualPassReport Report(
        float[]? residual = null, int fitted = 2, bool abandoned = false, bool contained = false)
        => new() { Residual = residual ?? ResidualBuf, FittedSignals = fitted, DeadlineAbandoned = abandoned, ContainedException = contained };

    private static SubtractionPass.ThirdPassResult Third(string outcome, float[]? buffer = null)
        => new([], outcome, 1, outcome == SubtractionPass.ThirdPassOutcome.Ran ? 1 : 0, buffer);

    [Fact(DisplayName = "coh-fb-residual: switch off - the SAME reference as the original audio, label original, whatever the report holds")]
    public void Off_ReturnsOriginalReference()
    {
        var (buf, label) = CohFallbackAudio.Select(false, Original, true, Report(), Third(SubtractionPass.ThirdPassOutcome.Ran, ThirdBuf));
        buf.Should().BeSameAs(Original);
        label.Should().Be("original");
    }

    [Fact(DisplayName = "coh-fb-residual: active, third pass ran - its own buffer")]
    public void Active_ThirdRan_ThirdBuffer()
    {
        var (buf, label) = CohFallbackAudio.Select(true, Original, true, Report(), Third(SubtractionPass.ThirdPassOutcome.Ran, ThirdBuf));
        buf.Should().BeSameAs(ThirdBuf);
        label.Should().Be("residual");
    }

    [Theory(DisplayName = "coh-fb-residual: active, third pass absent / skipped / abandoned / failed - the residual pass's buffer")]
    [InlineData(null)]
    [InlineData(SubtractionPass.ThirdPassOutcome.SkippedNoNew)]
    [InlineData(SubtractionPass.ThirdPassOutcome.SkippedAbandoned)]
    [InlineData(SubtractionPass.ThirdPassOutcome.Abandoned)]
    [InlineData(SubtractionPass.ThirdPassOutcome.Failed)]
    public void Active_ThirdDidNotSubtract_ResidualPassBuffer(string? thirdOutcome)
    {
        var third = thirdOutcome is null ? null : Third(thirdOutcome, ThirdBuf);
        var (buf, label) = CohFallbackAudio.Select(true, Original, true, Report(), third);
        buf.Should().BeSameAs(ResidualBuf);
        label.Should().Be("residual");
    }

    [Fact(DisplayName = "coh-fb-residual: active, third pass ran but exposes no buffer - falls back to the residual pass's buffer, never null")]
    public void Active_ThirdRanWithoutBuffer_ResidualPassBuffer()
    {
        var (buf, _) = CohFallbackAudio.Select(true, Original, true, Report(), Third(SubtractionPass.ThirdPassOutcome.Ran, null));
        buf.Should().BeSameAs(ResidualBuf);
    }

    [Fact(DisplayName = "coh-fb-residual: active but Normal depth - original audio, residual-unavailable")]
    public void Active_Normal_Unavailable()
        => AssertUnavailable(CohFallbackAudio.Select(true, Original, false, Report(), null));

    [Fact(DisplayName = "coh-fb-residual: active, Deep, no report (no residual pass ran) - original audio, residual-unavailable")]
    public void Active_NoReport_Unavailable()
        => AssertUnavailable(CohFallbackAudio.Select(true, Original, true, null, null));

    [Fact(DisplayName = "coh-fb-residual: active, residual pass abandoned on the deadline - unavailable although its buffer was assigned")]
    public void Active_Abandoned_Unavailable()
        => AssertUnavailable(CohFallbackAudio.Select(true, Original, true, Report(abandoned: true), null));

    [Fact(DisplayName = "coh-fb-residual: active, residual pass failed with a contained exception - unavailable")]
    public void Active_ContainedException_Unavailable()
        => AssertUnavailable(CohFallbackAudio.Select(true, Original, true, Report(contained: true), null));

    [Fact(DisplayName = "coh-fb-residual: active, residual buffer never built - unavailable")]
    public void Active_NoBuffer_Unavailable()
        => AssertUnavailable(CohFallbackAudio.Select(true, Original, true,
            new SubtractionPass.ResidualPassReport { FittedSignals = 2 }, null));

    [Fact(DisplayName = "coh-fb-residual: active, nothing subtracted (zero fitted signals) - unavailable even if a third result is present")]
    public void Active_ZeroFitted_Unavailable()
        => AssertUnavailable(CohFallbackAudio.Select(true, Original, true, Report(fitted: 0),
            Third(SubtractionPass.ThirdPassOutcome.Ran, ThirdBuf)));

    private static void AssertUnavailable((float[] Buffer, string Label) r)
    {
        r.Buffer.Should().BeSameAs(Original);
        r.Label.Should().Be("residual-unavailable");
    }
}
