using FluentAssertions;
using OpenWSFZ.Ft8.Interop;
using Xunit;
using Xunit.Abstractions;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// XC-ROUND (shim 20260082), the native entry <c>ftz_xc_round</c> against the REAL library: ONE more subtract-and-retry round for a signal the cycle never subtracted
/// (a cross-cycle detection). The fixture is the step-2c masked-signal one: a strong CQ and a much weaker message on the same carrier 125 ms later, which round 0 cannot
/// decode (the round-less path publishes only the strong one: that is the "red before" of this test, since the entry did not exist in shim 20260081). Called with the strong
/// signal's tones and position and the buffer the cycle left unsubtracted, the round fits and subtracts it and decodes the weak one; called with no detection it decodes
/// nothing; the result bytes do not depend on the thread count; the probe rows of the round carry round 4. Synthetic Q-prefix content only (NFR-021). No delay anywhere
/// (TESTING_STRATEGY section 11).
/// </summary>
[Trait("Category", "RequiresNativeBinary")]
public sealed class LeanEngineXcRoundNativeTests(ITestOutputHelper output) : IDisposable
{
    private const string StrongMessage = "CQ Q1ABC JO22";
    private const string WeakMessage = "Q2DEF Q3GHI -07";
    private const double StrongHz = 1500.0;
    private const double FreqToleranceHz = 3.2;

    public void Dispose()
    {
        Ft8LibInterop.SetDecodeParams(10, 0.10f, 60);
        Ft8LibInterop.SetCqApEnabled(false);
        Ft8LibInterop.LeanShutdown();
    }

    private static byte[] SaveHashState()
    {
        var image = new byte[Ft8LibInterop.HashStateSize()];
        Ft8LibInterop.HashStateSave(image);
        return image;
    }

    private static byte[] Tones(string message)
    {
        var t = new byte[79];
        Ft8LibInterop.EncodeMessage(message, t);
        return t;
    }

    private static string Serialise(LeanCycleOutcome o)
        => string.Join("\n", o.Results.Select((r, i) => $"{r.FreqHz}|{BitConverter.SingleToInt32Bits(r.Dt):X8}|{r.Snr}|{r.Message}|{o.Tiers[i]}|{o.Rounds[i]}"));

    /// <summary>The fixture, the round-less cycle's view of it (the strong signal found, the weak one not), and the strong signal's detection as the cross-cycle stage would hand it over.</summary>
    private (float[] Pcm, LeanXcDetection Strong) Fixture(byte[] start)
    {
        float[] pcm = LeanEngineRoundsTests.Synth(LeanEngineRoundsTests.WeakAmp);
        var cycle = Ft8LibInterop.DecodeLeanCycle(pcm, new LeanCycleParams(2, Rounds: false));
        Ft8LibInterop.HashStateRestore(start);
        int s = Array.FindIndex(cycle.Results, r => r.Message.TrimEnd() == StrongMessage);
        s.Should().BeGreaterThanOrEqualTo(0, "precondition: the strong signal decodes in round 0");
        cycle.Results.Should().NotContain(r => r.Message.TrimEnd() == WeakMessage, "precondition (red before): the round-less path leaves the masked signal undecoded");
        return (pcm, new LeanXcDetection(cycle.Results[s].FreqHz, cycle.Results[s].Dt, Tones(StrongMessage)));
    }

    private static LeanCycleOutcome XcRound(float[] pcm, float[] residual, IReadOnlyList<LeanXcDetection> detections, int threads = 2, bool probe = false)
        => Ft8LibInterop.DecodeLeanXcRound(pcm, new LeanCycleParams(threads, Probe: probe), residual, detections);

    [Fact(DisplayName = "FR-108: XC-ROUND test (a): called with the strong signal's tones and position, the round decodes the masked weak signal (round 4) and, with the probe on, writes a round-4 SUB row at the strong signal's position")]
    public void XcRound_DecodesTheMaskedSignal_AndWritesRound4Rows()
    {
        byte[] start = SaveHashState();
        var (pcm, strong) = Fixture(start);
        float[] residual = (float[])pcm.Clone();

        var r = XcRound(pcm, residual, [strong], probe: true);
        Ft8LibInterop.HashStateRestore(start);

        output.WriteLine($"stats: fits={r.Stats.Rounds[1].Fits} subtracted={r.Stats.Rounds[1].Subtracted} found={r.Stats.Rounds[1].Found} kept={r.Stats.Rounds[1].Kept} results={r.Stats.Rounds[1].Results}; rows {r.ProbeRows.Length}");
        var rs = r.Stats.Rounds[1];
        output.WriteLine($"cost (one detection, 2 threads, probe on): total wall {r.Stats.TotalWallUs / 1000.0:F1} ms, cpu {r.Stats.TotalCpuUs / 1000.0:F1} ms; fit cpu {rs.FitCpuUs / 1000.0:F1}, sum {rs.SumCpuUs / 1000.0:F1}, spec {rs.SpecCpuUs / 1000.0:F1}, search {rs.SearchCpuUs / 1000.0:F1}, decode {rs.DecodeCpuUs / 1000.0:F1} ms");
        r.Stats.Error.Should().Be(LeanCycleStats.Ok);
        r.Results.Should().Contain(x => x.Message.TrimEnd() == WeakMessage, "with the strong signal subtracted, the patch window around it yields the weak one");
        r.Rounds.Should().OnlyContain(x => x == LeanProbe.XcRound);
        r.Stats.RoundsRun.Should().Be(1);
        r.Stats.Rounds[1].Fits.Should().Be(1, "every detection is fitted");
        r.Stats.Rounds[1].Subtracted.Should().Be(1);
        r.Stats.Rounds[1].FitNone.Should().Be(0);

        r.ProbeRows.Should().Contain(x => x.Kind == LeanProbe.Sub && x.Round == LeanProbe.XcRound && Math.Abs(x.FreqHz - strong.FreqHz) <= FreqToleranceHz && x.Amp > 0f);
        r.ProbeRows.Should().Contain(x => x.Kind == LeanProbe.Cand && x.Round == LeanProbe.XcRound);
        r.ProbeRows.Should().OnlyContain(x => x.Round == LeanProbe.XcRound, "an XC call writes round-4 rows only");
        r.ProbeOverflow.Should().BeFalse();
    }

    [Fact(DisplayName = "FR-108: XC-ROUND test (a): called with no detection the round decodes nothing and leaves the residual unchanged")]
    public void XcRound_WithNoDetection_DecodesNothing_AndLeavesTheResidualUnchanged()
    {
        byte[] start = SaveHashState();
        var (pcm, _) = Fixture(start);
        float[] residual = (float[])pcm.Clone();
        float[] before = (float[])residual.Clone();

        var r = XcRound(pcm, residual, [], probe: true);

        r.Stats.Error.Should().Be(LeanCycleStats.Ok);
        r.Results.Should().BeEmpty();
        r.ProbeRows.Should().BeEmpty();
        residual.Should().Equal(before, "the residual is read only");
    }

    [Fact(DisplayName = "FR-108: XC-ROUND test (b): the round's output is the same bytes at 1, 2 and 16 threads")]
    public void XcRound_IsDeterministic_AcrossThreadCounts()
    {
        byte[] start = SaveHashState();
        var (pcm, strong) = Fixture(start);
        string? reference = null;
        foreach (int threads in new[] { 1, 2, 16 })
        {
            Ft8LibInterop.HashStateRestore(start);
            var r = XcRound(pcm, (float[])pcm.Clone(), [strong], threads, probe: true);
            Ft8LibInterop.HashStateRestore(start);
            string s = Serialise(r) + "\n" + string.Join(";", r.ProbeRows.Select(x => $"{x.Kind}|{x.Round}|{x.FreqHz}|{x.TimeS}|{x.Score}|{x.Outcome}"));
            reference ??= s;
            s.Should().Be(reference, $"{threads} threads");
        }
        reference.Should().Contain(WeakMessage);
    }

    [Fact(DisplayName = "FR-108: XC-ROUND: a budget with less than the residual reserve left starts nothing and publishes nothing (all or nothing)")]
    public void XcRound_WithNoBudgetLeft_PublishesNothing()
    {
        byte[] start = SaveHashState();
        var (pcm, strong) = Fixture(start);

        var r = Ft8LibInterop.DecodeLeanXcRound(pcm, new LeanCycleParams(2, BudgetMs: 0), (float[])pcm.Clone(), [strong]);
        Ft8LibInterop.HashStateRestore(start);

        r.Stats.Error.Should().Be(LeanCycleStats.Ok);
        r.Results.Should().BeEmpty();
        r.Stats.Abandoned.Should().BeTrue("the round did not start: the reserve is the cycle's");
        r.Stats.Rounds[1].Fits.Should().Be(0);
    }
}
