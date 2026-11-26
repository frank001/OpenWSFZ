using FluentAssertions;
using OpenWSFZ.Ft8.Interop;
using Xunit;
using Xunit.Abstractions;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// DR-3 (FR-109), the lean engine's duplicate rule, against the REAL native library: of two or more hits of ONE round with the same payload (round 0) or the same
/// transmission (a residual round), the one with the HIGHEST candidate sync score (<c>ftx_candidate_t.score</c>, the field the candidate search ranks by) is
/// published, at its own frequency; equal scores keep today's order (the lower frequency first). Selection-level tests call the pure native functions the cycle
/// itself calls (<c>ftz_dedup_select</c>, <c>ftz_text_replace_wins</c>); one end-to-end test decodes the same message twice in one buffer, the stronger copy at the
/// HIGHER frequency. Synthetic Q-prefix content only (NFR-021). No delay anywhere (TESTING_STRATEGY section 11).
/// </summary>
[Trait("Category", "RequiresNativeBinary")]
public sealed class LeanEngineDuplicateRuleTests(ITestOutputHelper output) : IDisposable
{
    private const int PcmSamples = 180_000;
    private const string Message = "CQ Q1ABC JO22";
    private const double LowHz = 1000.0;
    private const double HighHz = 1400.0;
    private const int StartSample = 6_000;
    private const double NoiseSigma = 0.02;
    private const int NoiseSeed = 11;
    private const float PcmTargetRms = 0.20f;

    public void Dispose()
    {
        Ft8LibInterop.SetDecodeParams(10, 0.10f, 60);
        Ft8LibInterop.SetCqApEnabled(false);
        Ft8LibInterop.LeanShutdown();
    }

    private static byte[] Pl(byte first, byte last = 0)
    {
        var p = new byte[10];
        p[0] = first; p[9] = last;
        return p;
    }

    // ── selection level ──────────────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-109: DR-3: two hits with the same payload, the higher score at the HIGHER frequency: the higher-score hit survives (today's code kept the lower frequency)")]
    public void SamePayload_HigherScoreAtHigherFrequency_Survives()
    {
        // published order is ascending frequency: hit 0 = the lower frequency, hit 1 = the higher
        var drop = Ft8LibInterop.LeanDedupSelect(0, [Pl(1), Pl(1)], [20, 35]);
        drop.Should().Equal(true, false);
    }

    [Fact(DisplayName = "FR-109: DR-3: two hits with the same payload, the higher score at the LOWER frequency: the lower one survives, as before")]
    public void SamePayload_HigherScoreAtLowerFrequency_Survives()
    {
        Ft8LibInterop.LeanDedupSelect(0, [Pl(1), Pl(1)], [35, 20]).Should().Equal(false, true);
    }

    [Fact(DisplayName = "FR-109: DR-3: equal scores keep today's order (the earlier, lower-frequency hit)")]
    public void SamePayload_EqualScores_KeepTheEarlierHit()
    {
        Ft8LibInterop.LeanDedupSelect(0, [Pl(1), Pl(1)], [28, 28]).Should().Equal(false, true);
        Ft8LibInterop.LeanDedupSelect(0, [Pl(1), Pl(1), Pl(1)], [28, 28, 28]).Should().Equal(false, true, true);
    }

    [Fact(DisplayName = "FR-109: DR-3: three copies: the highest score survives wherever it sits; different payloads are untouched")]
    public void SamePayload_ThreeCopies_HighestSurvives_OtherPayloadsUntouched()
    {
        Ft8LibInterop.LeanDedupSelect(0, [Pl(1), Pl(2), Pl(1), Pl(1)], [10, 40, 50, 30])
            .Should().Equal(true, false, false, true);
        Ft8LibInterop.LeanDedupSelect(0, [Pl(1), Pl(2), Pl(3)], [10, 40, 50]).Should().Equal(false, false, false);
    }

    [Fact(DisplayName = "FR-109: DR-3: in a residual round the same transmission counts as the same payload (the RR73-aware rule), and the higher score survives")]
    public void ResidualRound_SameTransmission_HigherScoreSurvives()
    {
        // Same 77 bits (the last three bits of byte 9 are padding, ignored): the same transmission in a residual round, a different payload in round 0.
        var a = Pl(7, 0x00);
        var b = Pl(7, 0x07);
        Ft8LibInterop.LeanDedupSelect(1, [a, b], [20, 35]).Should().Equal(true, false);
        Ft8LibInterop.LeanDedupSelect(0, [a, b], [20, 35]).Should().Equal(false, false);   // round 0 compares the whole payload bit for bit
    }

    [Fact(DisplayName = "FR-109: DR-3: the same rendered text from two payloads in one round: only a strictly higher score replaces the earlier result")]
    public void SameText_OnlyStrictlyHigherScoreReplaces()
    {
        Ft8LibInterop.LeanTextReplaceWins(35, 20).Should().BeTrue();
        Ft8LibInterop.LeanTextReplaceWins(20, 35).Should().BeFalse();
        Ft8LibInterop.LeanTextReplaceWins(28, 28).Should().BeFalse("equal scores keep the earlier result");
    }

    // ── end to end ───────────────────────────────────────────────────────────────────────────────────────────────

    // The sync score saturates for a strong signal (33 on this fixture at amplitude 0.10 and at 0.05), so the weaker copy must be near the decode floor to score lower
    // (0.004 scores 26 and still decodes; measured over 0.006, 0.004 and 0.003).
    private static float[] TwoCopies(double lowAmp, double highAmp)
    {
        var tones = new byte[79];
        Ft8LibInterop.EncodeMessage(Message, tones);
        var symbols = tones.Select(t => (int)t).ToArray();
        var a = TestFt8Encoder.SymbolsToPcm(symbols, LowHz, StartSample, (float)lowAmp);
        var b = TestFt8Encoder.SymbolsToPcm(symbols, HighHz, StartSample, (float)highAmp);
        var rng = new Random(NoiseSeed);
        var pcm = new float[PcmSamples];
        for (int i = 0; i < PcmSamples; i++)
        {
            double u1 = 1.0 - rng.NextDouble(), u2 = 1.0 - rng.NextDouble();
            pcm[i] = a[i] + b[i] + (float)(NoiseSigma * Math.Sqrt(-2.0 * Math.Log(u1)) * Math.Cos(2.0 * Math.PI * u2));
        }
        return Ft8Decoder.NormalisePcm(pcm, PcmTargetRms);
    }

    private static LeanCycleOutcome Lean(float[] pcm)
        => Ft8LibInterop.DecodeLeanCycle(pcm, new LeanCycleParams(2, false, null, 0, false, 0, false, false, 0));

    [Fact(DisplayName = "FR-109: DR-3: the same message twice in one buffer, the stronger copy at the HIGHER frequency: one result, at the higher frequency")]
    public void EndToEnd_StrongerCopyAtHigherFrequency_IsPublished()
    {
        var pcm = TwoCopies(lowAmp: 0.004, highAmp: 0.10);
        var o = Lean(pcm);
        o.Stats.Error.Should().Be(LeanCycleStats.Ok);
        var rows = o.Results.Where(r => r.Message.TrimEnd() == Message).ToArray();
        rows.Should().HaveCount(1, "one payload is one decode");
        output.WriteLine($"published at {rows[0].FreqHz} Hz (copies at {LowHz} and {HighHz} Hz)");
        rows[0].FreqHz.Should().BeInRange((int)HighHz - 10, (int)HighHz + 10, "the higher-score copy is the one published, at its own frequency (the old rule kept the lowest frequency)");
    }

    [Fact(DisplayName = "FR-109: DR-3: the same message twice, the stronger copy at the LOWER frequency: one result, at the lower frequency (unchanged from before)")]
    public void EndToEnd_StrongerCopyAtLowerFrequency_IsPublished()
    {
        var pcm = TwoCopies(lowAmp: 0.10, highAmp: 0.004);
        var o = Lean(pcm);
        var rows = o.Results.Where(r => r.Message.TrimEnd() == Message).ToArray();
        rows.Should().HaveCount(1);
        rows[0].FreqHz.Should().BeInRange((int)LowHz - 10, (int)LowHz + 10);
    }

    [Fact(DisplayName = "FR-109: DR-3: the selection does not depend on the thread count (byte-identical at 1, 2, 4, 8 and 16 threads)")]
    public void EndToEnd_SameAtEveryThreadCount()
    {
        var pcm = TwoCopies(lowAmp: 0.004, highAmp: 0.10);
        string Ser(LeanCycleOutcome o) => string.Join("\n", o.Results.Select((r, i) => $"{r.FreqHz}|{BitConverter.SingleToInt32Bits(r.Dt):X8}|{r.Snr}|{r.Message}|{o.Tiers[i]}|{o.Rounds[i]}"));
        var image = new byte[Ft8LibInterop.HashStateSize()];
        Ft8LibInterop.HashStateSave(image);
        string? first = null;
        foreach (int threads in new[] { 1, 2, 4, 8, 16 })
        {
            Ft8LibInterop.HashStateRestore(image);
            var o = Ft8LibInterop.DecodeLeanCycle(pcm, new LeanCycleParams(threads, false, null, 0, true, 0, false, false, 0));
            string s = Ser(o);
            first ??= s;
            s.Should().Be(first, $"{threads} threads");
        }
    }
}
