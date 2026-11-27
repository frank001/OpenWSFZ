using System.Reflection;
using FluentAssertions;
using OpenWSFZ.Ft8.Interop;
using Xunit;
using Xunit.Abstractions;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// SUB-PROBE (shim 20260080), the test-only diagnostic probe of the lean engine, against the REAL native library: with the flag off nothing is written and the call is the
/// one before it existed; with the flag on the published decodes are byte-identical (on every committed synth-qso WAV and a mix of all three, at 1, 2, 4, 8 and 16 threads);
/// a strong and a weak signal 10 Hz apart give a SUB row for the strong one with suppression above 0 dB and a CAND row near the weak one; the buffer is bounds-checked
/// (a deliberately small one sets the overflow flag and returns the rows that fit). Numbers only: no row carries text. Synthetic Q-prefix content only (NFR-021).
/// No delay anywhere (TESTING_STRATEGY section 11).
/// </summary>
[Trait("Category", "RequiresNativeBinary")]
public sealed class LeanEngineProbeTests(ITestOutputHelper output) : IDisposable
{
    public void Dispose()
    {
        Ft8LibInterop.SetDecodeParams(10, 0.10f, 60);
        Ft8LibInterop.SetCqApEnabled(false);
        Ft8LibInterop.LeanShutdown();
    }

    private static float[] LoadFixtureWav(string wavFileName)
    {
        Assembly asm = Assembly.GetExecutingAssembly();
        string name = asm.GetManifestResourceNames().Single(n => n.EndsWith(wavFileName, StringComparison.OrdinalIgnoreCase));
        using Stream stream = asm.GetManifestResourceStream(name)!;
        return WavReader.Read(stream);
    }

    private static float[] Mix(params string[] fixtures)
    {
        var sum = new float[180_000];
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

    private static LeanCycleOutcome Lean(float[] pcm, int threads, bool probe, int capacity = LeanProbe.MaxRows)
        => Ft8LibInterop.DecodeLeanCycle(pcm, new LeanCycleParams(threads, Rounds: true, Probe: probe, ProbeCapacity: capacity));

    private static string Serialise(LeanCycleOutcome o)
        => string.Join("\n", o.Results.Select((r, i) => $"{r.FreqHz}|{BitConverter.SingleToInt32Bits(r.Dt):X8}|{r.Snr}|{r.Message}|{o.Tiers[i]}|{o.Rounds[i]}"));

    // ── test 1: off against on is byte-identical ─────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "SUB-PROBE test 1: flag off writes no probe rows; flag on gives byte-identical published output on every synth-qso WAV and a mix of all three, at 1, 2, 4, 8 and 16 threads")]
    public void FlagOffAndOn_AreByteIdentical_AtEveryThreadCount()
    {
        var inputs = new List<(string Label, float[] Pcm)>
        {
            ("01", LoadFixtureWav("synth-qso-01.wav")),
            ("02", LoadFixtureWav("synth-qso-02.wav")),
            ("03", LoadFixtureWav("synth-qso-03.wav")),
            ("mix", Mix("synth-qso-01.wav", "synth-qso-02.wav", "synth-qso-03.wav")),
        };
        byte[] start = SaveHashState();
        foreach (var (label, pcm) in inputs)
        {
            string? reference = null;
            foreach (int threads in new[] { 1, 2, 4, 8, 16 })
            {
                Ft8LibInterop.HashStateRestore(start);
                var off = Lean(pcm, threads, probe: false);
                Ft8LibInterop.HashStateRestore(start);
                var on = Lean(pcm, threads, probe: true);

                off.Stats.Error.Should().Be(LeanCycleStats.Ok);
                on.Stats.Error.Should().Be(LeanCycleStats.Ok);
                off.ProbeRows.Should().BeEmpty("the flag is off: nothing is written");
                off.ProbeOverflow.Should().BeFalse();
                on.ProbeRows.Should().NotBeEmpty("the flag is on: every candidate of round 0 has a CAND row");
                on.ProbeOverflow.Should().BeFalse();

                string s = Serialise(on);
                Serialise(off).Should().Be(s, $"{label}, {threads} threads: the probe only reads");
                reference ??= s;
                s.Should().Be(reference, $"{label}: the output does not depend on the thread count");
            }
            reference.Should().NotBeNullOrEmpty($"{label} must decode something for the comparison to mean anything");
        }
        Ft8LibInterop.HashStateRestore(start);
    }

    [Fact(DisplayName = "SUB-PROBE: every CAND row of a finished cycle has an outcome, and the published results are exactly the rows with a published outcome; LOW and SUB rows only in rounds 1 to 3; no row carries text")]
    public void Rows_AreConsistentWithThePublishedResults()
    {
        float[] pcm = Mix("synth-qso-01.wav", "synth-qso-02.wav", "synth-qso-03.wav");
        byte[] start = SaveHashState();
        var o = Lean(pcm, 2, probe: true);
        Ft8LibInterop.HashStateRestore(start);

        var cands = o.ProbeRows.Where(r => r.Kind == LeanProbe.Cand).ToArray();
        cands.Should().NotBeEmpty();
        cands.Should().OnlyContain(r => r.Outcome != 0, "a finished cycle leaves no candidate undecided");
        cands.Where(r => r.Round == 0).Should().OnlyContain(r => r.Kept == 1, "round 0 keeps every candidate");
        cands.Count(r => r.Outcome is 1 or 5 or 8).Should().Be(o.Results.Length, "one published outcome (A_OK, B_OK, CQ_OK) per published result");
        o.ProbeRows.Where(r => r.Kind == LeanProbe.Low).Should().OnlyContain(r => r.Round >= 1);
        o.ProbeRows.Where(r => r.Kind == LeanProbe.Sub).Should().OnlyContain(r => r.Round >= 1);
        cands.Where(r => r.Outcome == 12).Should().OnlyContain(r => r.Round >= 1 && r.Kept == 0);
        output.WriteLine($"rows: {o.ProbeRows.Length} (SUB {o.ProbeRows.Count(r => r.Kind == LeanProbe.Sub)}, CAND {cands.Length}, LOW {o.ProbeRows.Count(r => r.Kind == LeanProbe.Low)}), results {o.Results.Length}");
    }

    // ── test 2: a strong and a weak signal 10 Hz apart ───────────────────────────────────────────────────────────

    [Fact(DisplayName = "SUB-PROBE test 2: a strong and a weak signal 10 Hz apart: one SUB row for the strong signal with suppression above 0 dB, and a CAND row near the weak one")]
    public void StrongAndWeakTenHertzApart_SubRowForTheStrong_CandRowNearTheWeak()
    {
        const double strongHz = 1500.0, weakHz = 1510.0;
        const double weakStartS = 7_500 / 12_000.0;
        float[] pcm = LeanEngineRoundsTests.Synth(LeanEngineRoundsTests.WeakAmp, weakHz: weakHz);
        byte[] start = SaveHashState();
        var on = Lean(pcm, 2, probe: true);
        Ft8LibInterop.HashStateRestore(start);
        var off = Lean(pcm, 2, probe: false);
        Ft8LibInterop.HashStateRestore(start);
        Serialise(on).Should().Be(Serialise(off));

        var subs = on.ProbeRows.Where(r => r.Kind == LeanProbe.Sub).ToArray();
        output.WriteLine("SUB rows: " + string.Join("; ", subs.Select(r => $"r{r.Round} {r.FreqHz:F1} Hz {r.TimeS:F3} s amp {r.Amp:F4} supp {r.SuppDb:F1} dB")));
        subs.Should().Contain(r => Math.Abs(r.FreqHz - strongHz) <= 3.2 && r.SuppDb > 0f && r.Amp > 0f,
            "the strong signal was subtracted and its footprint is quieter afterwards");
        subs.Count(r => Math.Abs(r.FreqHz - strongHz) <= 3.2).Should().Be(1, "one SUB row for the strong signal");

        var near = on.ProbeRows.Where(r => r.Kind == LeanProbe.Cand && Math.Abs(r.FreqHz - weakHz) <= 3.2 && Math.Abs(r.TimeS - weakStartS) <= 0.2).ToArray();
        output.WriteLine("CAND rows near the weak signal: " + string.Join("; ", near.Select(r => $"r{r.Round} {r.FreqHz:F1} Hz {r.TimeS:F3} s score {r.Score} kept {r.Kept} outcome {r.Outcome}")));
        near.Should().NotBeEmpty("a candidate near the weak signal is in the probe");
    }

    // ── test 3: the buffer is bounds-checked ─────────────────────────────────────────────────────────────────────

    [Theory(DisplayName = "SUB-PROBE test 3: a deliberately small probe buffer sets the overflow flag and returns the rows that fit, without a write past the end, and the published output is unchanged")]
    [InlineData(1)]
    [InlineData(5)]
    [InlineData(40)]
    public void SmallBuffer_SetsOverflow_ReturnsTheRowsThatFit(int capacity)
    {
        float[] pcm = Mix("synth-qso-01.wav", "synth-qso-02.wav", "synth-qso-03.wav");
        byte[] start = SaveHashState();
        var full = Lean(pcm, 2, probe: true);
        Ft8LibInterop.HashStateRestore(start);
        var small = Lean(pcm, 2, probe: true, capacity);
        Ft8LibInterop.HashStateRestore(start);

        full.ProbeOverflow.Should().BeFalse();
        full.ProbeRows.Length.Should().BeGreaterThan(capacity, "the fixture must produce more rows than the small buffer holds");
        small.ProbeOverflow.Should().BeTrue();
        small.ProbeRows.Length.Should().Be(capacity, "exactly the rows that fit");
        small.ProbeRows.Should().Equal(full.ProbeRows.Take(capacity), "the rows that fit are the first rows, unchanged");
        Serialise(small).Should().Be(Serialise(full), "an overflowing probe never changes the decode");
    }

    [Fact(DisplayName = "SUB-PROBE: the worst case the native side can write fits FTZ_PROBE_MAX_ROWS: 4 x 256 CAND + 3 x 400 LOW + 1024 SUB")]
    public void MaxRows_CoversTheStatedWorstCase()
    {
        LeanProbe.MaxRows.Should().BeGreaterThanOrEqualTo(4 * 256 + 3 * 400 + 1024);
    }
}
