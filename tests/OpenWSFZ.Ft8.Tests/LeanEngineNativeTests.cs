using System.Reflection;
using FluentAssertions;
using OpenWSFZ.Ft8.Interop;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// DR-2 step 2a (FR-108), the native tests of the lean engine's one call, <c>ftz_decode_cycle</c> (spectrogram, candidates, tier A, unpack, sorted),
/// against the REAL native library: primary-pass equality on the committed synthetic fixtures (test 1), determinism and thread-count independence
/// (test 2), and the fuzz (test 3). The same fuzz runs under AddressSanitizer in the CI job <c>native-asan</c> (<c>native/ftz_decoder/tests/</c>).
/// Fictional Q-prefix calls only (NFR-021). No delay anywhere: every call is synchronous and awaited by returning.
/// </summary>
[Trait("Category", "RequiresNativeBinary")]
public sealed class LeanEngineNativeTests : IDisposable
{
    // The native state these tests touch (the OSD gate, the callsign table) is process-global; the assembly runs its tests one at a time
    // (AssemblyInfo.cs), and every test puts back what it changed.
    private const int DefaultKMinScorePass2 = 10;
    private const float DefaultOsdCorrThreshold = 0.10f;
    private const int DefaultOsdNhardMax = 60;

    public LeanEngineNativeTests()
    {
        Ft8LibInterop.SetApBits([], []);
        Ft8LibInterop.SetCqApEnabled(false);
    }

    public void Dispose()
    {
        Ft8LibInterop.SetDecodeParams(DefaultKMinScorePass2, DefaultOsdCorrThreshold, DefaultOsdNhardMax);
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

    private static byte[] SaveHashState()
    {
        var image = new byte[Ft8LibInterop.HashStateSize()];
        Ft8LibInterop.HashStateSave(image);
        return image;
    }

    /// <summary>One line per result with every field exact (the float as its bit pattern): two runs are "byte-identical" iff these strings are equal.</summary>
    private static string Serialise(IEnumerable<Ft8NativeResult> results)
        => string.Join("\n", results.Select(r => $"{r.FreqHz}|{BitConverter.SingleToInt32Bits(r.Dt):X8}|{r.Snr}|{r.Message}"));

    /// <summary>The classic PRIMARY pass's texts: the first <c>passCounts[0]</c> results of <c>ft8_decode_all</c> (the pass-1 results follow them), CQ-AP and OSD off.</summary>
    private static HashSet<string> ClassicPrimaryTexts(float[] pcm)
    {
        Ft8LibInterop.SetDecodeParams(DefaultKMinScorePass2, DefaultOsdCorrThreshold, osdNhardMax: -1);   // nhard > -1 always: every OSD accept is refused
        Ft8LibInterop.SetCqApEnabled(false);
        Ft8NativeResult[] all = Ft8LibInterop.DecodeAll(pcm);
        int primary = Ft8LibInterop.GetLastPassCounts(2)[0];
        return all.Take(primary).Select(r => r.Message.TrimEnd()).ToHashSet(StringComparer.Ordinal);
    }

    // ── test 1: primary-pass equality ────────────────────────────────────────────────────────────────────────────

    [Theory(DisplayName = "FR-108: DR-2 test 1: on the committed synthetic fixtures the lean engine's decoded texts equal the classic primary pass's (CQ-AP and OSD off)")]
    [InlineData("synth-qso-01.wav")]
    [InlineData("synth-qso-02.wav")]
    [InlineData("synth-qso-03.wav")]
    public void LeanTexts_EqualTheClassicPrimaryPassTexts(string fixture)
    {
        float[] pcm = LoadFixtureWav(fixture);
        pcm.Should().HaveCount(180_000);
        byte[] start = SaveHashState();

        Ft8LibInterop.HashStateRestore(start);
        HashSet<string> classic = ClassicPrimaryTexts(pcm);

        Ft8LibInterop.HashStateRestore(start);
        LeanCycleOutcome lean = Ft8LibInterop.DecodeLeanCycle(pcm, threads: 2);
        Ft8LibInterop.HashStateRestore(start);

        lean.Stats.Error.Should().Be(LeanCycleStats.Ok);
        classic.Should().NotBeEmpty("the fixture must decode something for the comparison to mean anything");
        lean.Results.Select(r => r.Message.TrimEnd()).ToHashSet(StringComparer.Ordinal).Should().BeEquivalentTo(classic);
        lean.Results.Length.Should().Be(classic.Count, "one result per text: the lean engine publishes a text once");
    }

    [Fact(DisplayName = "FR-108: DR-2 D1: the results come back sorted by frequency, then time, and the stats are consistent counts (no text)")]
    public void Results_AreSorted_AndStatsAreCounts()
    {
        float[] pcm = Mix("synth-qso-01.wav", "synth-qso-02.wav", "synth-qso-03.wav");
        byte[] start = SaveHashState();
        LeanCycleOutcome lean = Ft8LibInterop.DecodeLeanCycle(pcm, threads: 2);
        Ft8LibInterop.HashStateRestore(start);

        lean.Results.Length.Should().BeGreaterThan(1);
        lean.Results.Select(r => (r.FreqHz, r.Dt)).Should().BeInAscendingOrder(Comparer<(int FreqHz, float Dt)>.Create(
            (a, b) => a.FreqHz != b.FreqHz ? a.FreqHz.CompareTo(b.FreqHz) : a.Dt.CompareTo(b.Dt)));
        lean.Stats.Results.Should().Be(lean.Results.Length);
        lean.Stats.Candidates.Should().BeGreaterThanOrEqualTo(lean.Stats.TierADecodes);
        lean.Stats.TierADecodes.Should().BeGreaterThanOrEqualTo(lean.Stats.Results);
        lean.Stats.Abandoned.Should().BeFalse();
        lean.Stats.TotalWallUs.Should().BeGreaterThan(0);
        lean.Stats.TotalCpuUs.Should().BeGreaterThanOrEqualTo(0);
    }

    // ── test 2: determinism ──────────────────────────────────────────────────────────────────────────────────────

    /// <summary>The three fixtures added into one buffer: several signals at once, so the candidate list is long and the ordering and de-duplication are exercised.</summary>
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

    [Fact(DisplayName = "FR-108: DR-2 test 2: the same audio and the same starting hash state give byte-identical output twice, and at 1, 2 and 4 threads")]
    public void SameAudioSameState_ByteIdentical_AcrossRunsAndThreadCounts()
    {
        foreach (float[] pcm in new[]
        {
            LoadFixtureWav("synth-qso-01.wav"),
            Mix("synth-qso-01.wav", "synth-qso-02.wav", "synth-qso-03.wav"),
        })
        {
            byte[] start = SaveHashState();
            var outputs = new List<(string Label, string Text)>();
            foreach (int threads in new[] { 1, 2, 4, 2, 1, 4 })
            {
                Ft8LibInterop.HashStateRestore(start);
                LeanCycleOutcome o = Ft8LibInterop.DecodeLeanCycle(pcm, threads);
                o.Stats.Error.Should().Be(LeanCycleStats.Ok);
                outputs.Add(($"threads={threads}", Serialise(o.Results)));
            }
            Ft8LibInterop.HashStateRestore(start);

            outputs[0].Text.Should().NotBeEmpty("an empty output would make the comparison vacuous");
            foreach (var (label, text) in outputs.Skip(1))
                text.Should().Be(outputs[0].Text, $"{label} must be byte-identical to threads=1");
        }
    }

    // ── test 3: fuzz ─────────────────────────────────────────────────────────────────────────────────────────────

    /// <summary>Runs of the fuzz. The native harness behind the CI job <c>native-asan</c> runs the same number.</summary>
    internal const int FuzzRuns = 10_000;

    private static float[] FuzzBuffer(Random rng, int kind, int length)
    {
        var x = new float[length];
        switch (kind)
        {
            case 0: break;                                                                     // silence
            case 1: Array.Fill(x, (float)(rng.NextDouble() * 2 - 1)); break;                   // DC
            case 2: for (int i = 0; i < length; i++) x[i] = (float)(rng.NextDouble() * 2 - 1); break;   // white noise
            case 3: for (int i = 0; i < length; i++) x[i] = Math.Clamp((float)((rng.NextDouble() * 2 - 1) * 50.0), -1f, 1f); break;   // hard-clipped noise
            case 4:                                                                            // a tone, clipped
                double f = 100 + rng.NextDouble() * 3000;
                for (int i = 0; i < length; i++) x[i] = Math.Clamp((float)(3.0 * Math.Sin(2 * Math.PI * f * i / 12000.0)), -1f, 1f);
                break;
            case 5: for (int i = 0; i < length; i += 1 + rng.Next(600)) x[i] = rng.Next(2) == 0 ? 1f : -1f; break;     // impulses
            default:                                                                           // loud noise, far beyond full scale but finite
                for (int i = 0; i < length; i++) x[i] = (float)((rng.NextDouble() * 2 - 1) * 1.0e5);
                break;
        }
        return x;
    }

    [Fact(DisplayName = "FR-108: DR-2 test 3: 10,000 fuzz runs (random, clipped, silent and DC audio, truncated buffers, every thread count) end without a crash or an error code")]
    public void Fuzz_TenThousandRuns_NeverCrashesNorErrors()
    {
        var rng = new Random(20261124);
        int[] edgeLengths = [0, 1, 1919, 1920, 1921, 3840, 12_000, 179_999, 180_000, 200_000];
        int fullLength = 0;
        for (int run = 0; run < FuzzRuns; run++)
        {
            // Mostly short buffers (a truncated capture), with a steady trickle of full-length ones so the worker pool and the candidate list are exercised.
            int length = run % 50 == 0 ? 180_000
                       : run % 7 == 0 ? edgeLengths[rng.Next(edgeLengths.Length)]
                       : rng.Next(0, 30_000);
            if (length >= 180_000) fullLength++;
            int kind = rng.Next(7);
            int threads = new[] { 1, 2, 4, 8, 3 }[run % 5];

            LeanCycleOutcome o = Ft8LibInterop.DecodeLeanCycle(FuzzBuffer(rng, kind, length), threads);

            o.Stats.Error.Should().Be(LeanCycleStats.Ok, $"run {run}: kind {kind}, length {length}, threads {threads}");
            o.Results.Length.Should().Be(o.Stats.Results);
            o.Stats.Candidates.Should().BeInRange(0, 140);
        }
        fullLength.Should().BeGreaterThan(100, "the fuzz must include full-length runs");
    }

    [Theory(DisplayName = "FR-108: DR-2 D3: audio that is not decodable (NaN, infinity, a sample beyond 1e6) returns the bad-audio code and nothing else, and the next call works")]
    [InlineData(float.NaN)]
    [InlineData(float.PositiveInfinity)]
    [InlineData(float.NegativeInfinity)]
    [InlineData(1.0e30f)]
    public void NonFiniteAudio_ReturnsBadAudio_AndTheNextCallWorks(float poison)
    {
        float[] pcm = LoadFixtureWav("synth-qso-01.wav");
        pcm[90_000] = poison;

        LeanCycleOutcome bad = Ft8LibInterop.DecodeLeanCycle(pcm, threads: 2);
        bad.Stats.Error.Should().Be(LeanCycleStats.ErrBadAudio);
        bad.Results.Should().BeEmpty();

        byte[] start = SaveHashState();
        LeanCycleOutcome good = Ft8LibInterop.DecodeLeanCycle(LoadFixtureWav("synth-qso-01.wav"), threads: 2);
        Ft8LibInterop.HashStateRestore(start);
        good.Stats.Error.Should().Be(LeanCycleStats.Ok);
        good.Results.Should().NotBeEmpty();
    }

    [Fact(DisplayName = "FR-108: DR-2 D2: the worker pool is created once and follows a thread-count change between cycles (1, 8, 2, 1) with unchanged output")]
    public void ThreadCountChangesBetweenCycles_DoNotChangeTheOutput()
    {
        float[] pcm = Mix("synth-qso-01.wav", "synth-qso-02.wav");
        byte[] start = SaveHashState();
        string? first = null;
        foreach (int threads in new[] { 1, 8, 2, 1, 8 })
        {
            Ft8LibInterop.HashStateRestore(start);
            string text = Serialise(Ft8LibInterop.DecodeLeanCycle(pcm, threads).Results);
            first ??= text;
            text.Should().Be(first, $"threads={threads}");
        }
        Ft8LibInterop.HashStateRestore(start);
    }
}
