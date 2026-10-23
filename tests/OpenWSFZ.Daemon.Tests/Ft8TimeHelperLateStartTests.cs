using FluentAssertions;
using OpenWSFZ.Ft8;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// #259: <see cref="Ft8TimeHelper.ApplyLateStart"/> / <see cref="Ft8TimeHelper.AlignLateStart"/> /
/// <see cref="Ft8TimeHelper.ClampToWindowBoundary"/>. A transmission that starts late in its
/// 15 s slot has the START of the clip skipped (time-aligned, as WSJT-X does), not its tail cut.
/// All counts below are checked arithmetic at 48 kHz: skip = round((t - 0.5 s) x 48 000).
/// </summary>
[Trait("Category", "Unit")]
public sealed class Ft8TimeHelperLateStartTests
{
    private const int Rate  = Ft8AudioSynthesiser.SampleRateHz;      // 48 000
    private const int Total = Ft8AudioSynthesiser.TotalSampleCount;  // 606 720 = 12.64 s
    private const int Ramp  = 240;

    private static readonly DateTimeOffset Slot = new(2026, 6, 27, 17, 30, 0, TimeSpan.Zero);

    /// <summary>A moment <paramref name="ms"/> milliseconds into the :30:00 slot (exact ticks).</summary>
    private static DateTimeOffset At(int ms) => Slot + TimeSpan.FromTicks(ms * TimeSpan.TicksPerMillisecond);

    /// <summary>A clip whose every sample identifies its own index (input[i] = i + 1, exact in float).</summary>
    private static float[] Clip()
    {
        var clip = new float[Total];
        for (var i = 0; i < clip.Length; i++) clip[i] = i + 1;
        return clip;
    }

    /// <summary>The raised cosine, written out independently of the production helper.</summary>
    private static double Gain(int i) => 0.5 * (1.0 - Math.Cos(Math.PI * i / 239.0));

    private static void AssertAligned(float[] input, DateTimeOffset now, int skip, int load)
    {
        var result = Ft8TimeHelper.ApplyLateStart(now, input, Rate);

        result.Alignment.ShouldKey.Should().BeTrue();
        result.Alignment.SkipSamples.Should().Be(skip);
        result.Alignment.LoadSamples.Should().Be(load);
        var loaded = result.Samples!;
        loaded.Length.Should().Be(load);

        // The START is cut, not the tail: from the 241st loaded sample on, input[skip + 240 ...].
        for (var i = Ramp; i < loaded.Length; i++)
            loaded[i].Should().Be(input[skip + i], $"loaded[{i}] is the input unchanged");

        // The first 240 rise from 0 along the raised cosine; the 240th is the input unchanged.
        loaded[0].Should().Be(0f);
        loaded[Ramp - 1].Should().Be(input[skip + Ramp - 1]);
        for (var i = 0; i < Ramp; i++)
            loaded[i].Should().BeApproximately((float)(input[skip + i] * Gain(i)), 1e-3f);
        for (var i = 1; i < Ramp; i++)
            (loaded[i] / input[skip + i]).Should().BeGreaterThan(loaded[i - 1] / input[skip + i - 1],
                "the fade-in rises monotonically");
    }

    [Theory(DisplayName = "#259 T1: start within 2.36 s loads the whole clip, byte-identical, no fade")]
    [InlineData(0)]
    [InlineData(620)]
    [InlineData(2360)] // exactly 15 s - 12.64 s: the last whole-clip start
    public void T1_WithinWholeClipThreshold_LoadsInputUnchanged(int ms)
    {
        var input    = Clip();
        var snapshot = (float[])input.Clone();

        var result = Ft8TimeHelper.ApplyLateStart(At(ms), input, Rate);

        result.Alignment.ShouldKey.Should().BeTrue();
        result.Alignment.SkipSamples.Should().Be(0);
        result.Alignment.LoadSamples.Should().Be(Total);
        result.Samples.Should().Equal(snapshot);

        // The safety-net clamp must not touch a whole clip that starts at 2.36 s either
        // (12.64 s x 48 kHz is exactly 606 720 samples, not 606 719).
        var clamped = Ft8TimeHelper.ClampToWindowBoundary(At(ms), result.Samples!, Rate, out var cut);
        cut.Should().Be(0);
        clamped.Should().Equal(snapshot);
    }

    [Fact(DisplayName = "#259 T2: t = 2.37 s skips 89,760 samples and loads 516,960; the start is cut, the tail is not")]
    public void T2_JustPastWhole_SkipsTheStart()
        => AssertAligned(Clip(), At(2370), skip: 89_760, load: 516_960);

    [Fact(DisplayName = "#259 T3: t = 4.9 s (the #257 L-2 case) skips 211,200 samples and loads 395,520")]
    public void T3_FourPointNineSeconds_SkipsTheStart()
        => AssertAligned(Clip(), At(4900), skip: 211_200, load: 395_520);

    [Fact(DisplayName = "#259 T4: t = 11.24 s (the last start) skips 515,520 samples and loads 91,200")]
    public void T4_LastStart_SkipsTheStart()
        => AssertAligned(Clip(), At(11_240), skip: 515_520, load: 91_200);

    [Fact(DisplayName = "#259 T4b: where the boundary clamp still cuts the tail the last 240 samples fall to 0; an uncut clip has no fade")]
    public void T4b_ClampCut_FadesTheNewTailOut()
    {
        var input = Clip();

        // 14.9 s into the slot: 0.1 s = 4,800 samples remain, so the clamp keeps 4,800 of 606,720.
        var clamped = Ft8TimeHelper.ClampToWindowBoundary(At(14_900), input, Rate, out var cut);

        clamped.Length.Should().Be(4_800);
        cut.Should().Be(Total - 4_800);
        for (var i = 0; i < clamped.Length - Ramp; i++)
            clamped[i].Should().Be(input[i], "samples before the fade are the input unchanged");
        clamped[^1].Should().Be(0f);
        clamped[^Ramp].Should().Be(input[clamped.Length - Ramp], "the first fade-out sample has gain 1");
        for (var j = 0; j < Ramp; j++)
            clamped[clamped.Length - Ramp + j].Should().BeApproximately(
                (float)(input[clamped.Length - Ramp + j] * Gain(Ramp - 1 - j)), 1e-3f);

        // A buffer that fits is returned untouched, the same array.
        var fits = Ft8TimeHelper.ClampToWindowBoundary(At(0), input, Rate, out var noCut);
        noCut.Should().Be(0);
        fits.Should().BeSameAs(input);
    }

    [Theory(DisplayName = "#259 T5: at or after 11.25 s nothing is loaded and the decision is 'do not key'")]
    [InlineData(11_250)]
    [InlineData(14_900)]
    public void T5_AtOrAfterCutoff_DoesNotKey(int ms)
    {
        var result = Ft8TimeHelper.ApplyLateStart(At(ms), Clip(), Rate);

        result.Alignment.ShouldKey.Should().BeFalse();
        result.Alignment.LoadSamples.Should().Be(0);
        result.Samples.Should().BeNull();
        Ft8TimeHelper.IsPastLastStart(At(ms)).Should().BeTrue();
    }

    [Fact(DisplayName = "#259: the 11.25 s cut-off and the 2.36 s whole-clip edge are exact")]
    public void Boundaries_AreExact()
    {
        Ft8TimeHelper.IsPastLastStart(At(11_249)).Should().BeFalse();
        Ft8TimeHelper.IsPastLastStart(At(11_250)).Should().BeTrue();

        Ft8TimeHelper.AlignLateStart(At(2360), Total, Rate).SkipSamples.Should().Be(0);
        var justPast = Slot + TimeSpan.FromTicks(23_600_001); // 100 ns past 2.36 s
        Ft8TimeHelper.AlignLateStart(justPast, Total, Rate).SkipSamples.Should().BeGreaterThan(0);

        // The offset is taken inside the 15 s slot that contains 'now', whichever slot it is.
        var slot2 = new DateTimeOffset(2026, 6, 27, 17, 30, 45, TimeSpan.Zero);
        Ft8TimeHelper.OffsetIntoSlot(slot2 + TimeSpan.FromSeconds(5)).Should().Be(TimeSpan.FromSeconds(5));
    }

    [Fact(DisplayName = "#259: the ramp is 0 at sample 0, 1 at sample 239, and the input array is never modified")]
    public void Ramp_Endpoints_AndInputIsNeverModified()
    {
        Ft8TimeHelper.RampGain(0).Should().Be(0.0);
        Ft8TimeHelper.RampGain(239).Should().Be(1.0);
        Ft8TimeHelper.RampGain(120).Should().BeApproximately(Gain(120), 1e-12);

        var input    = Clip();
        var snapshot = (float[])input.Clone();
        _ = Ft8TimeHelper.ApplyLateStart(At(4900), input, Rate);
        _ = Ft8TimeHelper.ClampToWindowBoundary(At(14_900), input, Rate, out _);
        input.Should().Equal(snapshot);
    }
}
