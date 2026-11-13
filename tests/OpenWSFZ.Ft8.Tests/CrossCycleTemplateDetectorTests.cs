using System.Text.Json;
using FluentAssertions;
using OpenWSFZ.Ft8.Dsp;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// The deterministic buffers of the XC-BUILD tests: QA's fixture recipe (a xorshift32 uniform noise source and a phase-continuous 8-FSK message), so the same helper builds the fixtures' buffer and the
/// wiring tests' cycle audio. No randomness, no clock: every number is reproducible (TESTING_STRATEGY section 11).
/// </summary>
internal static class XcSynth
{
    internal const int Fs = 12_000, N = 180_000, SamplesPerSymbol = 1_920;

    internal static uint XorShift32(uint s)
    {
        s ^= s << 13;
        s ^= s >> 17;
        s ^= s << 5;
        return s;
    }

    /// <summary>The 79 tones the recipe derives from a seed: <c>s = xorshift32(s)</c>, <c>tone = s % 8</c>, 79 times.</summary>
    internal static byte[] RecipeTones(uint seed)
    {
        var tones = new byte[79];
        uint s = seed;
        for (int i = 0; i < tones.Length; i++) { s = XorShift32(s); tones[i] = (byte)(s % 8); }
        return tones;
    }

    /// <summary>Uniform noise with the stated standard deviation (the recipe's source; the state advances once per sample, sample 0 uses the first advance).</summary>
    internal static double[] Noise(uint seed, double std)
    {
        var x = new double[N];
        uint s = seed;
        double scale = 2.0 * Math.Sqrt(3.0) * std;
        for (int i = 0; i < N; i++)
        {
            s = XorShift32(s);
            double u = (s + 0.5) / 4294967296.0;
            x[i] = (u - 0.5) * scale;
        }
        return x;
    }

    /// <summary>Adds a phase-continuous 8-FSK message (tone k at <c>f0 + 6.25 k</c>) starting at <c>round((dt + 0.48) x 12000)</c>, the recipe's synthesis, in float64.</summary>
    internal static void AddMessage(double[] x, ReadOnlySpan<byte> tones, double f0Hz, double dtWsjtx, double amplitude)
    {
        int start = (int)Math.Round((dtWsjtx + CrossCycleTemplateDetector.CalibrationStartMinusDtS) * Fs);
        double phase = 0.0;
        for (int k = 0; k < tones.Length; k++)
        {
            double f = f0Hz + 6.25 * tones[k];
            for (int i = 0; i < SamplesPerSymbol; i++)
            {
                int idx = start + k * SamplesPerSymbol + i;
                if ((uint)idx < (uint)x.Length) x[idx] += amplitude * Math.Cos(phase + 2.0 * Math.PI * f * i / Fs);
            }
            phase = (phase + 2.0 * Math.PI * f * SamplesPerSymbol / Fs) % (2.0 * Math.PI);
        }
    }

    internal static float[] ToFloat(double[] x)
    {
        var f = new float[x.Length];
        for (int i = 0; i < x.Length; i++) f[i] = (float)x[i];
        return f;
    }
}

/// <summary>
/// XC-BUILD R5 (FR-105): the managed template detector against QA's numeric fixtures (<c>dev-tasks/2026-11-13-xc-template-fixtures.json</c>, from the desk detector <c>xt_lib.py</c>): the taps, the baseband
/// checkpoints, the per-symbol bin powers at the true position, and seven cases (S_E* within 1e-3 relative, the argmax equal). Every test must be able to fail: QA mutates the detector.
/// </summary>
public sealed class CrossCycleTemplateDetectorTests
{
    private sealed record Case(string Name, string Buffer, string Tones, double CentreFreqHz, double CentreDt, double ExpectedS, double ExpectedFreq, double ExpectedDt);

    private sealed class Fixtures
    {
        public required double[] Taps { get; init; }
        public required byte[] MessageTones { get; init; }
        public required byte[] WrongTones { get; init; }
        public required double[] BasebandIndices { get; init; }
        public required double[][] BasebandValues { get; init; }
        public required double[][] SymbolPowers { get; init; }
        public required List<Case> Cases { get; init; }
        public required double Tolerance { get; init; }
        public required float[] Signal { get; init; }
        public required float[] NoiseOnly { get; init; }
    }

    private static readonly Lazy<Fixtures> Loaded = new(Load);

    private static Fixtures Load()
    {
        using var stream = typeof(CrossCycleTemplateDetectorTests).Assembly.GetManifestResourceStream("xc-template-fixtures.json")
                           ?? throw new InvalidOperationException("The fixtures resource is missing.");
        using var doc = JsonDocument.Parse(stream);
        var r = doc.RootElement;
        static double[] Doubles(JsonElement e) => e.EnumerateArray().Select(v => v.GetDouble()).ToArray();
        static byte[] Bytes(JsonElement e) => e.EnumerateArray().Select(v => (byte)v.GetInt32()).ToArray();

        var signalJson = r.GetProperty("signal");
        var msg = Bytes(signalJson.GetProperty("message_tones"));
        var wrong = Bytes(signalJson.GetProperty("wrong_message_tones"));

        // The recipe reproduces the tones the file lists (a check of the helper itself, so the cases below cannot pass on a wrong buffer).
        XcSynth.RecipeTones((uint)signalJson.GetProperty("tone_seed_message").GetInt32()).Should().Equal(msg);
        XcSynth.RecipeTones((uint)signalJson.GetProperty("tone_seed_wrong_message").GetInt32()).Should().Equal(wrong);

        double std = 1.0;
        uint noiseSeed = (uint)r.GetProperty("noise").GetProperty("seed").GetInt32();
        var noise = XcSynth.Noise(noiseSeed, std);
        var sig = (double[])noise.Clone();
        XcSynth.AddMessage(sig, msg, signalJson.GetProperty("base_freq_hz").GetDouble(), signalJson.GetProperty("dt_wsjtx_s").GetDouble(), signalJson.GetProperty("amplitude").GetDouble());

        var cases = r.GetProperty("cases").EnumerateArray().Select(c => new Case(
            c.GetProperty("name").GetString()!, c.GetProperty("buffer").GetString()!, c.GetProperty("tones").GetString()!,
            c.GetProperty("centre_freq_hz").GetDouble(), c.GetProperty("centre_dt_s").GetDouble(),
            c.GetProperty("expected_S_E_star").GetDouble(), c.GetProperty("expected_argmax_freq_hz").GetDouble(), c.GetProperty("expected_argmax_dt_s").GetDouble())).ToList();

        var bb = r.GetProperty("baseband_checkpoints");
        return new Fixtures
        {
            Taps = Doubles(r.GetProperty("lowpass_taps_61")),
            MessageTones = msg,
            WrongTones = wrong,
            BasebandIndices = Doubles(bb.GetProperty("indices")),
            BasebandValues = bb.GetProperty("values_re_im").EnumerateArray().Select(Doubles).ToArray(),
            SymbolPowers = r.GetProperty("per_symbol_bin_powers_at_truth").GetProperty("P").EnumerateArray().Select(Doubles).ToArray(),
            Cases = cases,
            Tolerance = r.GetProperty("tolerance").GetProperty("S_E_star_relative").GetDouble(),
            Signal = XcSynth.ToFloat(sig),
            NoiseOnly = XcSynth.ToFloat(noise),
        };
    }

    public static IEnumerable<object[]> CaseIndexes() => Enumerable.Range(0, 7).Select(i => new object[] { i });

    [Fact(DisplayName = "FR-105: XC-BUILD R5: the 61 low-pass taps equal the fixtures' taps (Hann-windowed sinc, 900 Hz at 12 kHz, unit DC gain)")]
    public void Taps_MatchFixtures()
    {
        var taps = CrossCycleTemplateDetector.LowPassTapsCopy();
        taps.Should().HaveCount(61);
        for (int i = 0; i < taps.Length; i++) taps[i].Should().BeApproximately(Load2().Taps[i], 1e-12, "tap " + i);
        taps.Sum().Should().BeApproximately(1.0, 1e-12, "unit DC gain");
    }

    private static Fixtures Load2() => Loaded.Value;

    [Fact(DisplayName = "FR-105: XC-BUILD R5: the baseband (mix at 1000 Hz, low-pass, decimate by 6) equals the fixtures' checkpoints at four indices")]
    public void Baseband_MatchesCheckpoints()
    {
        var fx = Loaded.Value;
        int n2k = XcSynth.N / CrossCycleTemplateDetector.Decimation;
        var re = new double[n2k]; var im = new double[n2k];
        CrossCycleTemplateDetector.DownconvertDecimate(fx.Signal, 1000.0, re, im);
        for (int i = 0; i < fx.BasebandIndices.Length; i++)
        {
            int m = (int)fx.BasebandIndices[i];
            re[m].Should().BeApproximately(fx.BasebandValues[i][0], 1e-9, $"baseband[{m}].re");
            im[m].Should().BeApproximately(fx.BasebandValues[i][1], 1e-9, $"baseband[{m}].im");
        }
    }

    [Fact(DisplayName = "FR-105: XC-BUILD R5: the 79 x 8 bin powers at the true position equal the fixtures' per-symbol powers (relative to the largest, 1e-6)")]
    public void SymbolPowers_MatchFixtures_AtTruth()
    {
        var fx = Loaded.Value;
        var p = new double[79 * 8];
        CrossCycleTemplateDetector.BinPowersAt(fx.Signal, 1000.0, 0.52, p);
        double max = fx.SymbolPowers.SelectMany(r => r).Max();
        double worst = 0.0;
        for (int k = 0; k < 79; k++)
            for (int b = 0; b < 8; b++)
                worst = Math.Max(worst, Math.Abs(p[k * 8 + b] - fx.SymbolPowers[k][b]) / max);
        worst.Should().BeLessThan(1e-6, "the largest per-bin deviation, relative to the largest power");
    }

    [Theory(DisplayName = "FR-105: XC-BUILD R5: fixture case (S_E* within 1e-3 relative, argmax equal)")]
    [MemberData(nameof(CaseIndexes))]
    public void Case_MatchesFixture(int index)
    {
        var fx = Loaded.Value;
        var c = fx.Cases[index];
        var buffer = c.Buffer == "signal" ? fx.Signal : fx.NoiseOnly;
        var tones = c.Tones == "message" ? fx.MessageTones : fx.WrongTones;

        var r = CrossCycleTemplateDetector.Search(buffer, c.CentreFreqHz, c.CentreDt, tones);

        double rel = Math.Abs(r.SStar - c.ExpectedS) / c.ExpectedS;
        rel.Should().BeLessThan(fx.Tolerance, $"{c.Name}: S_E* {r.SStar:R} against {c.ExpectedS:R}");
        r.FreqHz.Should().BeApproximately(c.ExpectedFreq, 1e-9, $"{c.Name}: argmax frequency");
        r.Dt.Should().BeApproximately(c.ExpectedDt, 1e-9, $"{c.Name}: argmax dt");
    }

    [Fact(DisplayName = "FR-105: XC-BUILD R5: a known message is found inside the window and MISSED outside it (S_E* near 7.5 inside, near 1 outside, at the same buffer and tones)")]
    public void KnownMessage_FoundInside_MissedOutside()
    {
        var fx = Loaded.Value;
        var inside = CrossCycleTemplateDetector.Search(fx.Signal, 1002.5, 0.52 + 0.11, fx.MessageTones);        // 2.5 Hz and 0.11 s from the truth: inside +-3 Hz x +-0.12 s
        inside.SStar.Should().BeGreaterThan(7.0);
        inside.FreqHz.Should().BeApproximately(1000.0, 1e-9);
        inside.Dt.Should().BeApproximately(0.52, 1e-9);

        var outsideFreq = CrossCycleTemplateDetector.Search(fx.Signal, 1000.0 + 12.5, 0.52, fx.MessageTones);   // 12.5 Hz away: the grid ends 9.5 Hz short
        outsideFreq.SStar.Should().BeLessThan(2.0);
        var outsideTime = CrossCycleTemplateDetector.Search(fx.Signal, 1000.0, 0.52 + 0.40, fx.MessageTones);   // 0.40 s away: the grid ends 0.28 s short
        outsideTime.SStar.Should().BeLessThan(2.0);
    }

    [Fact(DisplayName = "FR-105: XC-BUILD R5: the rolled DFT equals a direct computation (the zero-offset frequency row, all 25 start times, 1e-9)")]
    public void RolledDft_EqualsDirect_OnTheZeroOffsetRow()
    {
        var fx = Loaded.Value;
        const double fc = 1000.0, dtc = 0.55;
        var grid = new double[CrossCycleTemplateDetector.FreqSteps * CrossCycleTemplateDetector.DtSteps];
        CrossCycleTemplateDetector.Grid(fx.Signal, fc, dtc, fx.MessageTones, grid);
        int zeroRow = CrossCycleTemplateDetector.FreqSteps / 2;
        CrossCycleTemplateDetector.FreqOffsetHz(zeroRow).Should().Be(0.0);
        for (int k = 0; k < CrossCycleTemplateDetector.DtSteps; k++)
        {
            double direct = CrossCycleTemplateDetector.StatisticAt(fx.Signal, fc, dtc + CrossCycleTemplateDetector.DtOffsetS(k), fx.MessageTones);
            grid[zeroRow * CrossCycleTemplateDetector.DtSteps + k].Should().BeApproximately(direct, 1e-9, "start time index " + k);
        }
    }

    [Fact(DisplayName = "FR-105: XC-BUILD R5: symbols outside the buffer are zero-padded (a window past the end of the buffer scores near 1 and never throws; a symbol with no power counts 1)")]
    public void OutOfBufferSymbols_AreZeroPadded()
    {
        var fx = Loaded.Value;
        var silent = new float[XcSynth.N];
        CrossCycleTemplateDetector.Search(silent, 1000.0, 0.52, fx.MessageTones).SStar.Should().Be(1.0, "every symbol has no power and counts 1");
        // dt so late that most of the 79 symbols fall past the end of the buffer, and so early that symbol 0 starts before it: both are search windows the decoder can be handed.
        CrossCycleTemplateDetector.Search(fx.NoiseOnly, 1000.0, 9.0, fx.MessageTones).SStar.Should().BeGreaterThan(0.9).And.BeLessThan(3.0);
        CrossCycleTemplateDetector.Search(fx.NoiseOnly, 1000.0, -1.5, fx.MessageTones).SStar.Should().BeGreaterThan(0.9).And.BeLessThan(3.0);
    }

    [Fact(DisplayName = "FR-105: XC-BUILD R7: the coherent SNR of a template (the managed cf_snr_db: (S - N)/N x 6.25/2500, floor -30, lround) is the expected value on the fixtures' signal, and the floor on noise")]
    public void CoherentSnr_OnSignalAndOnNoise()
    {
        var fx = Loaded.Value;
        // Signal amplitude 0.5 in a tone, noise uniform std 1.0. Per 6.25 Hz bin the 320-sample (2000 Hz) coherent sum: signal power (0.5/2)^2 x ... is not needed here; what is pinned is the formula, from the
        // powers the fixtures list: sel = mean P[tone], oth = mean of the other seven, snr = 10 log10((sel - oth)/oth) - 26.0206, rounded half away from zero.
        double sel = 0.0, oth = 0.0;
        for (int k = 0; k < 79; k++)
            for (int b = 0; b < 8; b++)
            {
                if (b == fx.MessageTones[k]) sel += fx.SymbolPowers[k][b]; else oth += fx.SymbolPowers[k][b];
            }
        sel /= 79; oth /= 79 * 7;
        int expected = (int)Math.Round(10.0 * Math.Log10((sel - oth) / oth) - 26.0206, MidpointRounding.AwayFromZero);

        CrossCycleTemplateDetector.CoherentSnrDb(fx.Signal, 1000.0, 0.52, fx.MessageTones).Should().Be(expected);
        // Noise alone: (sel - oth) is about 0 and often negative: the result is the floor or near it, never above a few dB below zero.
        CrossCycleTemplateDetector.CoherentSnrDb(fx.NoiseOnly, 1000.0, 0.52, fx.MessageTones).Should().BeLessThanOrEqualTo(-20);
        // The floor and the rounding are the native's: zero power gives the floor.
        CrossCycleTemplateDetector.CoherentSnrDb(new float[XcSynth.N], 1000.0, 0.52, fx.MessageTones).Should().Be(-30);
        CrossCycleTemplateDetector.CoherentSnrDbFromPowers(new double[79 * 8], fx.MessageTones).Should().Be(-30);
    }
}
