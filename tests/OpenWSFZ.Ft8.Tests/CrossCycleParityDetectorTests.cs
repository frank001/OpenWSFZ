using System.Text.Json;
using FluentAssertions;
using OpenWSFZ.Ft8.Dsp;
using OpenWSFZ.Ft8.Interop;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// XC-BUILD R15 (FR-105, Amendment 6): S_P, the template statistic restricted to frame symbols 43 to 71 (the second data block: the CRC's tail and the LDPC parity), against QA's remedy fixtures
/// (<c>dev-tasks/2026-11-14-xc-remedy-fixtures.json</c>, from the desk detector <c>xt_lib</c>): six cases with S_E* and S_P at the argmax within 1e-3 relative, plus the frame-index assertions against the real
/// encoder (QA's P0 as a unit test). Every test must be able to fail: QA mutates the detector.
/// </summary>
public sealed class CrossCycleParityDetectorTests
{
    private sealed record Case(string Name, string Buffer, string Tones, double CentreFreqHz, double CentreDt, double ExpectedSE, double ExpectedSP, double ExpectedFreq, double ExpectedDt);

    private sealed class Fixtures
    {
        public required List<Case> Cases { get; init; }
        public required double ToleranceE { get; init; }
        public required double ToleranceP { get; init; }
        public required byte[] MessageTones { get; init; }
        public required byte[] WrongTones { get; init; }
        public required byte[] StaleTones { get; init; }
        public required float[] Signal { get; init; }
        public required float[] StaleSignal { get; init; }
        public required float[] NoiseOnly { get; init; }
        public required int[] Sync { get; init; }
        public required int[] Block1 { get; init; }
        public required int[] Block2 { get; init; }
    }

    private static readonly Lazy<Fixtures> Loaded = new(Load);

    private static JsonDocument Resource(string name)
    {
        using var stream = typeof(CrossCycleParityDetectorTests).Assembly.GetManifestResourceStream(name) ?? throw new InvalidOperationException("The fixtures resource is missing: " + name);
        return JsonDocument.Parse(stream);
    }

    private static Fixtures Load()
    {
        using var baseDoc = Resource("xc-template-fixtures.json");      // the recipe the remedy file refers to ("same buffer recipe, noise, taps and grid")
        using var remedy = Resource("xc-remedy-fixtures.json");
        var b = baseDoc.RootElement;
        var r = remedy.RootElement;
        static byte[] Bytes(JsonElement e) => e.EnumerateArray().Select(v => (byte)v.GetInt32()).ToArray();
        static int[] Ints(JsonElement e) => e.EnumerateArray().Select(v => v.GetInt32()).ToArray();

        var signalJson = b.GetProperty("signal");
        var msg = Bytes(signalJson.GetProperty("message_tones"));
        var wrong = Bytes(signalJson.GetProperty("wrong_message_tones"));
        var stale = Bytes(r.GetProperty("stale_message_tones"));
        double f0 = signalJson.GetProperty("base_freq_hz").GetDouble(), dt = signalJson.GetProperty("dt_wsjtx_s").GetDouble(), amp = signalJson.GetProperty("amplitude").GetDouble();

        var noise = XcSynth.Noise((uint)b.GetProperty("noise").GetProperty("seed").GetInt32(), 1.0);
        var sig = (double[])noise.Clone();
        XcSynth.AddMessage(sig, msg, f0, dt, amp);
        var staleSig = (double[])noise.Clone();
        XcSynth.AddMessage(staleSig, stale, f0, dt, amp);

        var fi = r.GetProperty("frame_indices");
        var cases = r.GetProperty("cases").EnumerateArray().Select(c => new Case(
            c.GetProperty("name").GetString()!, c.GetProperty("buffer").GetString()!, c.GetProperty("tones").GetString()!,
            c.GetProperty("centre_freq_hz").GetDouble(), c.GetProperty("centre_dt_s").GetDouble(),
            c.GetProperty("expected_S_E_star").GetDouble(), c.GetProperty("expected_S_P_at_argmax").GetDouble(),
            c.GetProperty("expected_argmax_freq_hz").GetDouble(), c.GetProperty("expected_argmax_dt_s").GetDouble())).ToList();

        return new Fixtures
        {
            Cases = cases,
            ToleranceE = r.GetProperty("tolerance").GetProperty("S_E_star_relative").GetDouble(),
            ToleranceP = r.GetProperty("tolerance").GetProperty("S_P_relative").GetDouble(),
            MessageTones = msg, WrongTones = wrong, StaleTones = stale,
            Signal = XcSynth.ToFloat(sig), StaleSignal = XcSynth.ToFloat(staleSig), NoiseOnly = XcSynth.ToFloat(noise),
            Sync = Ints(fi.GetProperty("sync")), Block1 = Ints(fi.GetProperty("data_block_1")), Block2 = Ints(fi.GetProperty("data_block_2")),
        };
    }

    public static IEnumerable<object[]> CaseIndexes() => Enumerable.Range(0, 6).Select(i => new object[] { i });

    [Theory(DisplayName = "FR-105: XC-BUILD R15: remedy fixture case (S_E* and S_P at the argmax within 1e-3 relative, argmax equal)")]
    [MemberData(nameof(CaseIndexes))]
    public void Case_MatchesFixture(int index)
    {
        var fx = Loaded.Value;
        var c = fx.Cases[index];
        var buffer = c.Buffer switch { "signal" => fx.Signal, "signal_stale" => fx.StaleSignal, "noise_only" => fx.NoiseOnly, _ => throw new InvalidOperationException(c.Buffer) };
        var tones = c.Tones switch { "message" => fx.MessageTones, "wrong_message" => fx.WrongTones, "stale_message" => fx.StaleTones, _ => throw new InvalidOperationException(c.Tones) };

        var r = CrossCycleTemplateDetector.Search(buffer, c.CentreFreqHz, c.CentreDt, tones);

        (Math.Abs(r.SStar - c.ExpectedSE) / c.ExpectedSE).Should().BeLessThan(fx.ToleranceE, $"{c.Name}: S_E* {r.SStar:R} against {c.ExpectedSE:R}");
        (Math.Abs(r.SP - c.ExpectedSP) / c.ExpectedSP).Should().BeLessThan(fx.ToleranceP, $"{c.Name}: S_P {r.SP:R} against {c.ExpectedSP:R}");
        r.FreqHz.Should().BeApproximately(c.ExpectedFreq, 1e-9, $"{c.Name}: argmax frequency");
        r.Dt.Should().BeApproximately(c.ExpectedDt, 1e-9, $"{c.Name}: argmax dt");
    }

    [Fact(DisplayName = "FR-105: XC-BUILD R15: the stale case is the one the gate exists for: S_E* 5.08 clears any T_E near 3, S_P 0.84 fails a T_P near 1.9, and the found-at-centre case has S_P 7.59")]
    public void StaleCase_ClearsTheE_AndFailsTheP()
    {
        var fx = Loaded.Value;
        var stale = CrossCycleTemplateDetector.Search(fx.StaleSignal, 1000.0, 0.52, fx.MessageTones);
        var found = CrossCycleTemplateDetector.Search(fx.Signal, 1000.0, 0.52, fx.MessageTones);

        stale.SStar.Should().BeGreaterThan(3.076, "the stale template matches the sync and the callsigns, so S_E* alone calls it a detection");
        stale.SP.Should().BeLessThan(1.899, "the second data block was re-drawn: about 1/8 of its symbols match");
        found.SP.Should().BeGreaterThan(1.899).And.BeApproximately(found.SStar, 0.2, "a true repeat matches the second block as well as the rest");
    }

    [Fact(DisplayName = "FR-105: XC-BUILD R15: S_P is formed from the SAME correlations as S_E* (no second search): at the S_E* argmax it equals the direct mean over frame symbols 43 to 71 of the bin powers there, and the search never moves because of it")]
    public void SP_IsTheDirectBlockMean_AtTheArgmax()
    {
        var fx = Loaded.Value;
        foreach (var (buffer, tones) in new[] { (fx.Signal, fx.MessageTones), (fx.StaleSignal, fx.MessageTones), (fx.NoiseOnly, fx.MessageTones) })
        {
            var r = CrossCycleTemplateDetector.Search(buffer, 1001.5, 0.57, tones);
            var p = new double[79 * 8];
            CrossCycleTemplateDetector.BinPowersAt(buffer, r.FreqHz, r.Dt, p);
            CrossCycleTemplateDetector.ParityStatisticFromPowers(p, tones).Should().BeApproximately(r.SP, 1e-4, "S_P at the argmax, directly");
            CrossCycleTemplateDetector.StatisticFromPowers(p, tones).Should().BeApproximately(r.SStar, 1e-4, "and S_E* at the same place, so the argmax is S_E*'s");
        }
        // The 29 symbols alone: a template whose block 2 is all wrong and the rest right has S_P low and S_E* high (the two statistics are not the same number).
        var s = CrossCycleTemplateDetector.Search(fx.StaleSignal, 1000.0, 0.52, fx.MessageTones);
        s.SStar.Should().BeGreaterThan(3.0 * s.SP);
    }

    [Fact(DisplayName = "FR-105: XC-BUILD R15: a symbol without power counts 1 in S_P too (a silent buffer gives S_P exactly 1.0, as S_E* is exactly 1.0)")]
    public void SilentBuffer_GivesExactlyOne()
    {
        var fx = Loaded.Value;
        var r = CrossCycleTemplateDetector.Search(new float[XcSynth.N], 1000.0, 0.52, fx.MessageTones);
        r.SStar.Should().Be(1.0);
        r.SP.Should().Be(1.0);
    }

    // ── the frame indices against the real encoder (QA's P0 as a unit test) ─────────────────────────────────────────

    private static byte[] Encode(string message)
    {
        var tones = new byte[79];
        Ft8LibInterop.EncodeMessage(message, tones);
        return tones;
    }

    private static readonly byte[] Costas = [3, 1, 4, 0, 6, 5, 2];

    [Fact(DisplayName = "FR-105: XC-BUILD R15 (QA P0): the 29 symbols of the second data block are exactly frame symbols 43..71 (between the Costas arrays at 36-42 and 72-78), and the fixtures' index lists, the code's constants and the encoder's output agree")]
    public void BlockTwo_IsFrameSymbols43To71_AgainstTheEncoder()
    {
        var fx = Loaded.Value;
        CrossCycleTemplateDetector.ParityBlockFirstSymbol.Should().Be(43);
        CrossCycleTemplateDetector.ParityBlockLastSymbol.Should().Be(71);
        CrossCycleTemplateDetector.ParityBlockSymbols.Should().Be(29);
        fx.Block2.Should().Equal(Enumerable.Range(CrossCycleTemplateDetector.ParityBlockFirstSymbol, CrossCycleTemplateDetector.ParityBlockSymbols), "the fixtures' list of block 2 is the code's range");
        fx.Block1.Should().Equal(Enumerable.Range(7, 29));
        fx.Sync.Should().Equal(Enumerable.Range(0, 7).Concat(Enumerable.Range(36, 7)).Concat(Enumerable.Range(72, 7)));

        // The encoder puts the Costas array 3,1,4,0,6,5,2 at the three sync positions of every message, and data everywhere else: so block 2 lies between the 2nd and the 3rd array.
        foreach (var text in new[] { "Q1ABC Q1XYZ JO33", "Q1ABC Q1XYZ RR73", "CQ Q1ABC JO33", "Q1ABC Q1XYZ -12" })
        {
            var tones = Encode(text);
            tones.Should().HaveCount(79);
            foreach (int start in new[] { 0, 36, 72 })
                tones.Skip(start).Take(7).Should().Equal(Costas, $"'{text}': the Costas array starts at frame symbol {start}");
        }
    }

    [Fact(DisplayName = "FR-105: XC-BUILD R15 (QA P0): two different messages from the same station share all 21 sync symbols and most of data block 1 but almost none of block 2 (chance 3.6 of 29); the same message shares all 29")]
    public void DifferentMessages_ShareBlockOneButNotBlockTwo()
    {
        var a = Encode("Q1ABC Q1XYZ JO33");
        var sameAgain = Encode("Q1ABC Q1XYZ JO33");
        var nextReport = Encode("Q1ABC Q1XYZ -12");
        var nextRr73 = Encode("Q1ABC Q1XYZ RR73");

        int Equal(byte[] x, byte[] y, IEnumerable<int> idx) => idx.Count(i => x[i] == y[i]);
        var sync = Loaded.Value.Sync;
        var block1 = Loaded.Value.Block1;
        var block2 = Loaded.Value.Block2;

        Equal(a, sameAgain, block2).Should().Be(29, "a true repeat matches block 2 completely");
        foreach (var next in new[] { nextReport, nextRr73 })
        {
            Equal(a, next, sync).Should().Be(21, "the sync symbols never change");
            Equal(a, next, block1).Should().BeGreaterThanOrEqualTo(18, "the callsigns sit in data block 1; only the report/RR73 field and the CRC's head differ there");
            Equal(a, next, block2).Should().BeLessThanOrEqualTo(10, "the CRC tail and the LDPC parity are re-drawn almost at random: about 29/8 equal by chance");
        }
    }
}
