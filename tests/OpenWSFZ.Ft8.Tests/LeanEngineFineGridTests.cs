using System.Reflection;
using FluentAssertions;
using OpenWSFZ.Ft8.Interop;
using Xunit;
using Xunit.Abstractions;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// FINE-GRID (shim 20260083): the lean candidate search can be thinned (THIN) and run on a 4 x 4 grid (FINE), both runtime parameters, both off by default, against the REAL native
/// library. (a) the defaults change nothing (explicit thin 0 and 2 x 2 equal the plain call, rows and results, on every committed synth-qso WAV and a mix; the build before the parameters
/// is covered by every existing golden test passing unchanged); (b) zero-padding is right (the 4 x 4 waterfall's even frequency sub-positions equal the 2 x 2 waterfall's cells within one
/// stored step, and a tone half-way between two old bins peaks at the new odd sub-position); (c) THIN keeps one candidate per place, keeps two signals 20 Hz apart, keeps both ends of a chain,
/// never leaves two survivors inside the window, and does not depend on the thread count; (d) a signal half a bin and half a hop off today's grid decodes under FINE on an odd sub-position;
/// (e) an invalid parameter returns the parameter error. Synthetic Q-prefix content only (NFR-021). No delay anywhere, and every random draw is seeded (TESTING_STRATEGY section 11).
/// </summary>
[Trait("Category", "RequiresNativeBinary")]
public sealed class LeanEngineFineGridTests(ITestOutputHelper output) : IDisposable
{
    private const int PcmSamples = 180_000;
    private const double SymbolPeriodS = 0.16;
    private const double WindowHz = 6.25, WindowS = 0.16, Epsilon = 1e-3;
    private const int MinBin = 22;                       // int(140 Hz x 0.16 s): the first stored bin of the lean waterfall
    private const string Message = "CQ Q1ABC JO22";

    public void Dispose()
    {
        Ft8LibInterop.SetDecodeParams(10, 0.10f, 60);
        Ft8LibInterop.SetCqApEnabled(false);
        Ft8LibInterop.LeanShutdown();
    }

    // ── helpers ──────────────────────────────────────────────────────────────────────────────────────────────────

    private static float[] LoadFixtureWav(string wavFileName)
    {
        Assembly asm = Assembly.GetExecutingAssembly();
        string name = asm.GetManifestResourceNames().Single(n => n.EndsWith(wavFileName, StringComparison.OrdinalIgnoreCase));
        using Stream stream = asm.GetManifestResourceStream(name)!;
        return WavReader.Read(stream);
    }

    private static float[] Mix(params string[] fixtures)
    {
        var sum = new float[PcmSamples];
        foreach (string f in fixtures)
        {
            float[] x = LoadFixtureWav(f);
            for (int i = 0; i < sum.Length; i++) sum[i] += x[i] / fixtures.Length;
        }
        return sum;
    }

    private static byte[] SaveHashState()
    {
        var image = new byte[Ft8LibInterop.HashStateSize()];
        Ft8LibInterop.HashStateSave(image);
        return image;
    }

    private static float[] Tone(double hz, float amplitude)
    {
        var pcm = new float[PcmSamples];
        for (int i = 0; i < pcm.Length; i++) pcm[i] = amplitude * (float)Math.Sin(2.0 * Math.PI * hz * i / 12_000.0);
        return pcm;
    }

    /// <summary>One synthetic FT8 signal (tone 0 at <paramref name="baseHz"/>, starting at <paramref name="startSample"/>) over seeded Gaussian noise, normalised as the daemon does.</summary>
    private static float[] Signal(double baseHz, int startSample, float amplitude = 0.10f, double extraHz = double.NaN, int extraStart = 0, float extraAmplitude = 0f)
    {
        var tones = new byte[79];
        Ft8LibInterop.EncodeMessage(Message, tones);
        float[] a = TestFt8Encoder.SymbolsToPcm(tones.Select(t => (int)t).ToArray(), baseHz, startSample, amplitude);
        float[]? b = null;
        if (!double.IsNaN(extraHz))
        {
            var t2 = new byte[79];
            Ft8LibInterop.EncodeMessage("Q2DEF Q3GHI -07", t2);
            b = TestFt8Encoder.SymbolsToPcm(t2.Select(t => (int)t).ToArray(), extraHz, extraStart, extraAmplitude);
        }
        var rng = new Random(7);
        var pcm = new float[PcmSamples];
        for (int i = 0; i < PcmSamples; i++)
        {
            double u1 = 1.0 - rng.NextDouble(), u2 = 1.0 - rng.NextDouble();
            pcm[i] = a[i] + (b is null ? 0f : b[i]) + (float)(0.02 * Math.Sqrt(-2.0 * Math.Log(u1)) * Math.Cos(2.0 * Math.PI * u2));
        }
        return Ft8Decoder.NormalisePcm(pcm, 0.20f);
    }

    private static LeanCycleOutcome Lean(float[] pcm, int threads = 2, bool thin = false, int timeOsr = 0, int freqOsr = 0, bool probe = true)
        => Ft8LibInterop.DecodeLeanCycle(pcm, new LeanCycleParams(threads, Rounds: true, Probe: probe, Thin: thin, TimeOsr: timeOsr, FreqOsr: freqOsr));

    private static string Serialise(LeanCycleOutcome o)
        => string.Join("\n", o.Results.Select((r, i) => $"{r.FreqHz}|{BitConverter.SingleToInt32Bits(r.Dt):X8}|{r.Snr}|{r.Message}|{o.Tiers[i]}|{o.Rounds[i]}"))
         + "\n--\n" + string.Join("\n", o.ProbeRows.Select(r => $"{r.Kind}|{r.Round}|{r.FreqHz:R}|{r.TimeS:R}|{r.Score}|{r.Kept}|{r.Outcome}|{r.TimeSub}|{r.FreqSub}"));

    private static IEnumerable<LeanProbeRow> Cands(LeanCycleOutcome o, int round) => o.ProbeRows.Where(r => r.Kind == LeanProbe.Cand && r.Round == round);

    private static bool InWindow(LeanProbeRow a, LeanProbeRow b)
        => Math.Abs(a.FreqHz - b.FreqHz) <= WindowHz + Epsilon && Math.Abs(a.TimeS - b.TimeS) <= WindowS + Epsilon;

    // ── test (a): the defaults change nothing ────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FINE-GRID test (a): thin 0 with an explicit 2 x 2 grid equals the plain call (results, tiers, rounds and probe rows) on every synth-qso WAV and a mix, and the probe rows carry sub-positions below 2")]
    public void Defaults_ChangeNothing()
    {
        var inputs = new List<float[]>
        {
            LoadFixtureWav("synth-qso-01.wav"), LoadFixtureWav("synth-qso-02.wav"), LoadFixtureWav("synth-qso-03.wav"),
            Mix("synth-qso-01.wav", "synth-qso-02.wav", "synth-qso-03.wav"),
        };
        byte[] start = SaveHashState();
        foreach (float[] pcm in inputs)
        {
            Ft8LibInterop.HashStateRestore(start);
            var plain = Lean(pcm);
            Ft8LibInterop.HashStateRestore(start);
            var explicitDefaults = Lean(pcm, thin: false, timeOsr: 2, freqOsr: 2);
            Ft8LibInterop.HashStateRestore(start);
            Serialise(explicitDefaults).Should().Be(Serialise(plain), "thin 0 and 2 x 2 is the call before the parameters");
            plain.Stats.Error.Should().Be(LeanCycleStats.Ok);
            plain.ProbeRows.Where(r => r.Kind == LeanProbe.Cand || r.Kind == LeanProbe.Low).Should().OnlyContain(r => r.TimeSub >= 0 && r.TimeSub < 2 && r.FreqSub >= 0 && r.FreqSub < 2);
        }
    }

    // ── test (b): zero-padding is right ──────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FINE-GRID test (b): on a tone, the 4 x 4 waterfall's EVEN frequency sub-positions equal the 2 x 2 waterfall's cells within one stored step, and a tone half-way between two old bins peaks at the new ODD sub-position")]
    public void ZeroPadding_EvenSubPositionsEqualTheOldGrid_AndAHalfBinToneLandsOnAnOddOne()
    {
        const int WindowLen = 3_840;                    // today's two-symbol window, what the 4 x 4 grid keeps
        foreach (double hz in new[] { 1500.0, 1501.5625 })
        {
            float[] pcm = Tone(hz, 0.1f);
            var (old, oldDims) = Ft8LibInterop.FtzTestWaterfall(pcm, 2, 2, 0);
            var (fine, fineDims) = Ft8LibInterop.FtzTestWaterfall(pcm, 2, 4, WindowLen);
            oldDims.Should().Equal(new[] { fineDims[0], 2, 2, fineDims[3] }, "same blocks and bins; osr 2 x 2 against 2 x 4");
            int blocks = oldDims[0], bins = oldDims[3];
            blocks.Should().BeGreaterThan(79, "a whole capture");
            int oldStride = 2 * 2 * bins, fineStride = 2 * 4 * bins;

            int maxDiff = 0;
            for (int block = 0; block < blocks; block++)
                for (int ts = 0; ts < 2; ts++)
                    for (int fs = 0; fs < 2; fs++)
                        for (int bin = 0; bin < bins; bin++)
                        {
                            int o = old[block * oldStride + (ts * 2 + fs) * bins + bin];
                            int f = fine[block * fineStride + (ts * 4 + fs * 2) * bins + bin];
                            maxDiff = Math.Max(maxDiff, Math.Abs(o - f));
                        }
            output.WriteLine($"tone {hz} Hz: largest |old - fine(even)| over {blocks} blocks = {maxDiff} stored steps (0.5 dB each)");
            maxDiff.Should().BeLessThanOrEqualTo(1, "every second bin of the zero-padded FFT is today's bin");

            // Where the tone peaks in a mid-capture block (time_sub 0).
            int mid = blocks / 2, best = -1, bestAt = -1;
            for (int fs = 0; fs < 4; fs++)
                for (int bin = 0; bin < bins; bin++)
                {
                    int v = fine[mid * fineStride + fs * bins + bin];
                    if (v > best) { best = v; bestAt = bin * 4 + fs; }
                }
            double peakHz = (MinBin + bestAt / 4.0) / SymbolPeriodS;
            output.WriteLine($"tone {hz} Hz peaks at {peakHz:F4} Hz (unit {bestAt}, sub-position {bestAt % 4})");
            peakHz.Should().BeApproximately(hz, 0.01);
            (bestAt % 2 == 1).Should().Be(hz > 1501.0, "the half-bin tone sits on an odd sub-position, the on-grid tone on an even one");
        }
    }

    // ── test (c): thinning ───────────────────────────────────────────────────────────────────────────────────────

    /// <summary>An independent statement of THIN's rule (sort by score, lower frequency, earlier time; keep unless a KEPT one is inside the window; stop at the cap).</summary>
    private static List<int[]> ReferenceThin(IEnumerable<int[]> cands, int cap, int timeOsr, int freqOsr)
    {
        int F(int[] c) => c[3] * freqOsr + c[4];
        int T(int[] c) => c[1] * timeOsr + c[2];
        var sorted = cands.OrderByDescending(c => c[0]).ThenBy(F).ThenBy(T).ToList();
        var kept = new List<int[]>();
        foreach (var c in sorted)
        {
            if (kept.Count >= cap) break;
            if (!kept.Any(k => Math.Abs(F(c) - F(k)) <= freqOsr && Math.Abs(T(c) - T(k)) <= timeOsr)) kept.Add(c);
        }
        return kept;
    }

    [Theory(DisplayName = "FINE-GRID test (c): THIN equals the rule on thousands of random candidate sets (clustered, with exactly tied scores) and no two survivors lie inside 6.25 Hz and 0.16 s")]
    [InlineData(2, 2)]
    [InlineData(4, 4)]
    [InlineData(2, 4)]
    public void Thin_EqualsTheRule_AndLeavesNoTwoSurvivorsInsideTheWindow(int timeOsr, int freqOsr)
    {
        var rng = new Random(20261127 + timeOsr * 10 + freqOsr);
        for (int round = 0; round < 3_000; round++)
        {
            int n = rng.Next(1, 70), spanF = rng.Next(2, 14), spanT = rng.Next(2, 8), scoreRange = rng.Next(1, 6) == 1 ? 3 : 40;
            var seen = new HashSet<(int, int, int, int)>();
            var list = new List<int[]>();
            for (int i = 0; i < n; i++)
            {
                var c = new[] { rng.Next(0, scoreRange), rng.Next(-3, spanT), rng.Next(0, timeOsr), rng.Next(0, spanF), rng.Next(0, freqOsr) };
                if (seen.Add((c[1], c[2], c[3], c[4]))) list.Add(c);       // a grid position holds one candidate
            }
            int cap = rng.Next(1, 5) == 1 ? rng.Next(1, 8) : 1_000;
            var got = Ft8LibInterop.FtzTestThin(list, cap, timeOsr, freqOsr);
            var want = ReferenceThin(list, cap, timeOsr, freqOsr);
            got.Select(c => string.Join(",", c)).Should().Equal(want.Select(c => string.Join(",", c)), $"round {round}: the rule");
            for (int i = 0; i < got.Length; i++)
                for (int j = i + 1; j < got.Length; j++)
                    (Math.Abs((got[i][3] * freqOsr + got[i][4]) - (got[j][3] * freqOsr + got[j][4])) <= freqOsr
                        && Math.Abs((got[i][1] * timeOsr + got[i][2]) - (got[j][1] * timeOsr + got[j][2])) <= timeOsr)
                        .Should().BeFalse($"round {round}: survivors {i} and {j} are inside the window");
        }
    }

    [Theory(DisplayName = "FINE-GRID test (c): the chain A > B > C (A-B and B-C inside the window, A-C outside it) keeps A and C and drops B, on the 2 x 2 and on the 4 x 4 grid; the cap then takes the best survivors")]
    [InlineData(2, 2)]
    [InlineData(4, 4)]
    public void Chain_KeepsBothEnds(int timeOsr, int freqOsr)
    {
        // frequency units: A at 1, B one window (freqOsr units) above it, C one more above that: A-B and B-C are exactly on the window's edge, A-C is two windows.
        var a = new[] { 30, 5, 0, 1, 1 };
        var b = new[] { 20, 5, 0, 1 + 1, 1 };            // freq unit + freqOsr
        var c = new[] { 10, 5, 0, 1 + 2, 1 };
        var got = Ft8LibInterop.FtzTestThin([c, b, a], 10, timeOsr, freqOsr);   // handed over in the wrong order on purpose
        got.Select(x => x[0]).Should().Equal([30, 10], "A and C survive, B is dropped because of A");
        Ft8LibInterop.FtzTestThin([c, b, a], 1, timeOsr, freqOsr).Select(x => x[0]).Should().Equal([30], "the cap takes the best survivor");

        // the finer grid also gives chains made of sub-positions only (one window = freqOsr units)
        var s0 = new[] { 9, 2, 0, 3, 0 };
        var s1 = new[] { 8, 2, 0, 3, freqOsr - 1 };                       // inside the window of s0
        var s2 = new[] { 7, 2, 0, 4, freqOsr - 1 };                       // one window above s1, two above s0
        Ft8LibInterop.FtzTestThin([s1, s2, s0], 10, timeOsr, freqOsr).Select(x => x[0]).Should().Equal([9, 7]);
    }

    [Fact(DisplayName = "FINE-GRID test (c): a strong synthetic signal leaves ONE surviving candidate beside it with THIN on (several without it), two signals 20 Hz apart both survive, and the rows are the same at 1, 2, 4, 8 and 16 threads")]
    public void Thin_OneSurvivorPerSignal_TwoSignalsBothSurvive_ThreadCountsAgree()
    {
        const double strongHz = 1500.0, otherHz = 1520.0;
        float[] pcm = Signal(strongHz, 6_000, 0.10f, otherHz, 6_000, 0.10f);
        byte[] start = SaveHashState();

        var off = Lean(pcm, thin: false);
        Ft8LibInterop.HashStateRestore(start);
        var on = Lean(pcm, thin: true);
        Ft8LibInterop.HashStateRestore(start);

        // The place a signal is searched at = its best-scoring round-0 candidate within 3.2 Hz of its carrier; the candidates inside one tone spacing and one symbol of that place are its copies.
        (int Copies, int Score) Place(LeanCycleOutcome o, double hz)
        {
            var rows = Cands(o, 0).Where(r => Math.Abs(r.FreqHz - hz) <= 3.2).ToArray();
            if (rows.Length == 0) return (0, 0);
            var best = rows.OrderByDescending(r => r.Score).First();
            return (Cands(o, 0).Count(r => InWindow(r, best)), best.Score);
        }
        output.WriteLine($"candidates in the window of the strong signal's best: off {Place(off, strongHz)}, on {Place(on, strongHz)}; of the other's: off {Place(off, otherHz)}, on {Place(on, otherHz)}");
        Place(off, strongHz).Copies.Should().BeGreaterThan(1, "precondition: without THIN a strong signal fills several slots");
        Place(on, strongHz).Copies.Should().Be(1, "one survivor beside the strong signal");
        Place(on, otherHz).Copies.Should().Be(1, "the signal 20 Hz away has a candidate of its own, and one only");
        Place(on, otherHz).Score.Should().BeGreaterThan(0);

        var rows = Cands(on, 0).ToArray();
        for (int i = 0; i < rows.Length; i++)
            for (int j = i + 1; j < rows.Length; j++)
                InWindow(rows[i], rows[j]).Should().BeFalse($"round-0 survivors {i} and {j} are inside the window");
        foreach (int round in on.ProbeRows.Where(r => r.Kind == LeanProbe.Cand).Select(r => r.Round).Distinct())
        {
            var rr = Cands(on, round).ToArray();
            for (int i = 0; i < rr.Length; i++)
                for (int j = i + 1; j < rr.Length; j++)
                    InWindow(rr[i], rr[j]).Should().BeFalse($"round {round}: survivors {i} and {j} are inside the window");
        }

        string reference = Serialise(on);
        foreach (int threads in new[] { 1, 2, 4, 8, 16 })
        {
            Ft8LibInterop.HashStateRestore(start);
            Serialise(Lean(pcm, threads, thin: true)).Should().Be(reference, $"THIN at {threads} threads");
        }
        Ft8LibInterop.HashStateRestore(start);
    }

    // ── test (d): FINE decodes ───────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FINE-GRID test (d): a signal half a bin (1.5625 Hz) and half a hop (0.04 s) off today's grid decodes under FINE (thin 1, 4 x 4), and its published candidate sits on an odd sub-position")]
    public void Fine_DecodesASignalOffTheOldGrid_OnAnOddSubPosition()
    {
        const double halfBinHz = 1501.5625;
        float[] pcm = Signal(halfBinHz, 6_240);          // 0.52 s: an odd multiple of the 4 x 4 grid's 0.04 s hop, half a hop off the old 0.08 s one
        byte[] start = SaveHashState();

        var fine = Lean(pcm, thin: true, timeOsr: 4, freqOsr: 4);
        Ft8LibInterop.HashStateRestore(start);
        fine.Stats.Error.Should().Be(LeanCycleStats.Ok);
        fine.Results.Should().Contain(r => r.Message.TrimEnd() == Message, "the signal decodes on the 4 x 4 grid");

        var published = fine.ProbeRows.Where(r => r.Kind == LeanProbe.Cand && r.Round == 0 && r.Outcome is 1 or 5 or 8 && Math.Abs(r.FreqHz - halfBinHz) <= 3.2).ToArray();
        output.WriteLine("published round-0 candidates near the signal: " + string.Join("; ", published.Select(r => $"{r.FreqHz:F4} Hz {r.TimeS:F3} s time_sub {r.TimeSub} freq_sub {r.FreqSub}")));
        published.Should().NotBeEmpty();
        published.Should().Contain(r => r.TimeSub % 2 == 1 || r.FreqSub % 2 == 1, "the decode came from a position the 2 x 2 grid does not have");
        fine.ProbeRows.Where(r => r.Kind == LeanProbe.Cand).Should().OnlyContain(r => r.TimeSub >= 0 && r.TimeSub < 4 && r.FreqSub >= 0 && r.FreqSub < 4);
    }

    // ── test (e): parameters ─────────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FINE-GRID test (e): an invalid thin or oversampling value returns the parameter error before anything runs, and the valid values 0, 2 and 4 are accepted")]
    public void InvalidValues_ReturnTheParameterError()
    {
        float[] pcm = Signal(1500.0, 6_000);
        byte[] start = SaveHashState();
        foreach (var (thin, t, f) in new[] { (true, 3, 0), (false, 0, 3), (true, 1, 0), (false, 0, 8), (true, -2, 0), (false, 0, 16) })
        {
            var o = Lean(pcm, thin: thin, timeOsr: t, freqOsr: f, probe: false);
            o.Stats.Error.Should().Be(LeanCycleStats.ErrParam, $"time_osr {t}, freq_osr {f}");
            o.Results.Should().BeEmpty();
            Ft8LibInterop.HashStateRestore(start);
        }
        foreach (int osr in new[] { 0, 2, 4 })
        {
            Lean(pcm, thin: true, timeOsr: osr, freqOsr: osr, probe: false).Stats.Error.Should().Be(LeanCycleStats.Ok, $"osr {osr}");
            Ft8LibInterop.HashStateRestore(start);
        }
    }
}
