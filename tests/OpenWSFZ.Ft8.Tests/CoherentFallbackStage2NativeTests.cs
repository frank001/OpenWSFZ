using System.Reflection;
using System.Runtime.InteropServices;
using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Ft8.Interop;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// COH-FALLBACK Stage 2 (shim 20260068) against the REAL native library: the ABI of the three new exports, the snapshot-driven run, the
/// deadline and cancel behaviour (R7': abandon, never queue), the text unpack, the coherent SNR, and the end-to-end wiring through
/// <see cref="Ft8Decoder"/> (R6' slot, R11 tag). Also R13 on recorded cycles: with the flag OFF the staged batches are the pre-change ones,
/// and with it ON they are those plus the fallback's own decodes (which proves Stage 1's thread-local candidate retention, and the snapshot
/// that reads it, are outcome-neutral on those cycles).
///
/// <para>Synthetic content only (NFR-021): the message is <c>CQ Q1ABC FN20</c> at a seeded noise level where the ordinary decode finds
/// nothing and the fallback does. The generator is seeded and the assertions are conditional on the ordinary decode having found nothing, so
/// a different last bit on another platform cannot flip the test (TESTING_STRATEGY section 11: a numeric golden holds only where it was
/// recorded).</para>
/// </summary>
public sealed class CoherentFallbackStage2NativeTests
{
    private const int PcmSamples = 180_000;
    private const double WeakNoiseSigma = 3.5;   // amplitude 0.3, so about -20 dB in 2500 Hz: below the ordinary decode, inside the fallback's reach
    private static readonly int[] WeakSeeds = [1, 3, 4];
    private const string WeakMessage = "CQ Q1ABC FN20";
    private static readonly DateTime CycleStart = new(2026, 10, 20, 12, 0, 0, DateTimeKind.Utc);

    private static float[] Synthesise(string message, double freqHz, double startS, double noiseSigma, int seed)
    {
        var tones = new byte[79];
        Ft8LibInterop.EncodeMessage(message, tones);
        var pcm = new float[PcmSamples];
        double phase = 0.0;
        long n0 = (long)Math.Round(startS * 12000.0);
        for (int s = 0; s < tones.Length; s++)
        {
            double f = freqHz + 6.25 * tones[s];
            for (int i = 0; i < 1920; i++)
            {
                long idx = n0 + (long)s * 1920 + i;
                if (idx >= 0 && idx < PcmSamples) pcm[idx] += (float)(0.3 * Math.Sin(phase));
                phase += 2.0 * Math.PI * f / 12000.0;
            }
        }
        var rng = new Random(seed);
        for (int i = 0; i < PcmSamples; i++)
        {
            double u1 = 1.0 - rng.NextDouble(), u2 = rng.NextDouble();
            pcm[i] += (float)(noiseSigma * Math.Sqrt(-2.0 * Math.Log(u1)) * Math.Cos(2.0 * Math.PI * u2));
        }
        return pcm;
    }

    private static (Ft8NativeResult[] Ordinary, byte[] Snapshot) DecodeAndSnapshot(float[] pcm)
    {
        var ordinary = Ft8LibInterop.DecodeAll(pcm);
        return (ordinary, Ft8LibInterop.CohFallbackSnapshot());   // same thread, nothing in between
    }

    [Fact(DisplayName = "Stage 2: the new native structs have the documented sizes (ABI pin)")]
    public void StructSizes_MatchTheHeader()
    {
        Marshal.SizeOf<CohFallbackStatsNative>().Should().Be(CohFallbackStatsNative.ExpectedNativeSizeBytes).And.Be(96);
        Marshal.SizeOf<CohFallbackOutNative>().Should().Be(CohFallbackOutNative.ExpectedNativeSizeBytes).And.Be(56);
        Marshal.OffsetOf<CohFallbackOutNative>(nameof(CohFallbackOutNative.F1bDb)).ToInt32().Should().Be(32);
        Marshal.OffsetOf<CohFallbackOutNative>(nameof(CohFallbackOutNative.Payload0)).ToInt32().Should().Be(40);
        Marshal.OffsetOf<CohFallbackOutNative>(nameof(CohFallbackOutNative.Payload1)).ToInt32().Should().Be(48);
    }

    [Fact(DisplayName = "Stage 2: a weak synthetic CQ that the ordinary decode misses is recovered by the run - right text, a coherent SNR near the true one, position near the true one, not at the edge")]
    public void WeakSignal_RecoveredByTheFallback()
    {
        int exercised = 0;
        foreach (int seed in WeakSeeds)
        {
            var pcm = Synthesise(WeakMessage, 1500.0, 0.55, WeakNoiseSigma, seed);
            var (ordinary, snap) = DecodeAndSnapshot(pcm);
            if (ordinary.Any(r => r.Message.TrimEnd() == WeakMessage)) continue;   // the ordinary decode got it on this platform: nothing to recover
            exercised++;

            var run = Ft8LibInterop.CohFallbackRun(pcm, snap, budgetMs: -1, CancellationToken.None);
            var found = run.Rows.Where(r => r.State == CohFallbackState.NewGated).ToList();

            found.Should().NotBeEmpty($"seed {seed}: the fallback recovers the signal the ordinary decode missed");
            var row = CoherentFallbackSelector.Select(run.Rows).First();
            Ft8LibInterop.CohFallbackUnpack(row.Payload).Should().Be(WeakMessage);
            row.SnrDb.Should().BeInRange(-24, -17, "the true SNR is about -20.5 dB in 2500 Hz");
            row.OutFreqHz.Should().BeApproximately(1500f, 0.5f);
            row.OutDtS.Should().BeApproximately(0.71f, 0.03f, "candidate convention: the symbol-0 start plus one symbol period");
            row.Edge.Should().BeFalse();
            row.F1bDb.Should().BeLessThanOrEqualTo(17.552446, "published rows are gated at T1");
            run.Stats.Abandoned.Should().Be(0);
            run.Stats.Attempted.Should().Be(run.Stats.Eligible, "no deadline: every eligible candidate was attempted");
            run.Stats.CrcNew.Should().BeGreaterThan(0);
            run.Rows.Count.Should().Be(run.Stats.Eligible);
        }
        exercised.Should().BeGreaterThan(0, "at least one seeded cycle must have been missed by the ordinary decode, or the test proves nothing");
    }

    [Fact(DisplayName = "R7': a zero budget (and a cancelled token) abandons every eligible candidate - counted, none attempted, none published")]
    public void ZeroBudget_AbandonsEverything()
    {
        var pcm = Synthesise(WeakMessage, 1500.0, 0.55, WeakNoiseSigma, 3);
        var (_, snap) = DecodeAndSnapshot(pcm);

        var none = Ft8LibInterop.CohFallbackRun(pcm, snap, budgetMs: 0, CancellationToken.None);
        none.Stats.Eligible.Should().BeGreaterThan(0);
        (none.Stats.Attempted, none.Stats.Abandoned).Should().Be((0, none.Stats.Eligible));
        none.Rows.Should().OnlyContain(r => r.State == CohFallbackState.Abandoned);
        CoherentFallbackSelector.Select(none.Rows).Should().BeEmpty();

        using var cts = new CancellationTokenSource();
        cts.Cancel();
        var cancelled = Ft8LibInterop.CohFallbackRun(pcm, snap, budgetMs: -1, cts.Token);
        (cancelled.Stats.Attempted, cancelled.Stats.Abandoned).Should().Be((0, cancelled.Stats.Eligible));
    }

    [Fact(DisplayName = "R7': a deadline that arrives mid-run stops between candidates - some attempted, the rest abandoned, attempted + abandoned = eligible")]
    public void MidRunDeadline_StopsBetweenCandidates()
    {
        var pcm = Synthesise(WeakMessage, 1500.0, 0.55, WeakNoiseSigma, 3);
        var (_, snap) = DecodeAndSnapshot(pcm);
        var full = Ft8LibInterop.CohFallbackRun(pcm, snap, budgetMs: -1, CancellationToken.None);
        full.Stats.Eligible.Should().BeGreaterThan(3);

        // a budget of a tenth of the unconstrained run: not enough for all of them, with margin for a slow or fast machine
        var cut = Ft8LibInterop.CohFallbackRun(pcm, snap, budgetMs: Math.Max(1.0, full.Stats.TotalMs / 10.0), CancellationToken.None);
        cut.Stats.Eligible.Should().Be(full.Stats.Eligible);
        (cut.Stats.Attempted + cut.Stats.Abandoned).Should().Be(cut.Stats.Eligible);
        cut.Stats.Abandoned.Should().BeGreaterThan(0);
        cut.Rows.Count(r => r.State == CohFallbackState.Abandoned).Should().Be(cut.Stats.Abandoned);
    }

    [Fact(DisplayName = "Stage 2: the snapshot is thread-independent - taken on one thread, the run on another gives the same rows")]
    public async Task Snapshot_RunsOnAnotherThread()
    {
        var pcm = Synthesise(WeakMessage, 1500.0, 0.55, WeakNoiseSigma, 4);
        var (_, snap) = DecodeAndSnapshot(pcm);

        var here = Ft8LibInterop.CohFallbackRun(pcm, snap, -1, CancellationToken.None);
        var there = await Task.Run(() => Ft8LibInterop.CohFallbackRun(pcm, snap, -1, CancellationToken.None));

        there.Rows.Select(Key).Should().Equal(here.Rows.Select(Key));
        there.Stats.Eligible.Should().Be(here.Stats.Eligible);
        static string Key(CohFallbackRow r) => $"{r.FreqHz}/{r.DtS}/{r.State}/{r.SnrDb}/{Convert.ToHexString(r.Payload)}";
    }

    [Fact(DisplayName = "Stage 2: the run reads only the snapshot - a later ft8_decode_all on the same thread does not change it")]
    public void Snapshot_IsACopy()
    {
        var pcm = Synthesise(WeakMessage, 1500.0, 0.55, WeakNoiseSigma, 3);
        var (_, snap) = DecodeAndSnapshot(pcm);
        var before = Ft8LibInterop.CohFallbackRun(pcm, snap, -1, CancellationToken.None);

        Ft8LibInterop.DecodeAll(new float[PcmSamples]);   // resets the thread-local retention
        var after = Ft8LibInterop.CohFallbackRun(pcm, snap, -1, CancellationToken.None);

        after.Rows.Select(r => (r.FreqHz, r.DtS, r.State)).Should().Equal(before.Rows.Select(r => (r.FreqHz, r.DtS, r.State)));
    }

    [Fact(DisplayName = "Stage 2: bad arguments are refused across the managed boundary, an unpack of a payload that is not a message returns null")]
    public void BadArguments()
    {
        var pcm = new float[PcmSamples];
        Action shortPcm = () => Ft8LibInterop.CohFallbackRun(new float[10], [0], -1, CancellationToken.None);
        shortPcm.Should().Throw<ArgumentException>();
        Action badSnap = () => Ft8LibInterop.CohFallbackRun(pcm, new byte[8], -1, CancellationToken.None);
        badSnap.Should().Throw<InvalidOperationException>("a snapshot of the wrong size is refused by the native side");

        // i3 = 7 is not a defined FT8 message type: the ordinary message decode refuses it
        Ft8LibInterop.CohFallbackUnpack([0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0, 0]).Should().BeNull();
    }

    // ── end to end through Ft8Decoder with the real native library ───────────────────────────────────────

    private static async Task<List<(int Batch, DecodeResult[] Results)>> Staged(Ft8Decoder d, float[] pcm)
    {
        var got = new List<(int, DecodeResult[])>();
        await d.DecodeStagedAsync(pcm, CycleStart, null, (n, b) => { got.Add((n, b.ToArray())); return Task.CompletedTask; });
        return got;
    }

    private static Ft8Decoder Decoder(DecodingDepth depth, bool fallback)
    {
        var d = new Ft8Decoder(new FakeClock(CycleStart));
        d.SetSubtractionEnabled(true);
        d.SetDecodingDepth(depth);
        d.SetCoherentFallbackEnabled(fallback);
        return d;
    }

    [Theory(DisplayName = "step 4 R6/R11: end to end - the weak cycle's fallback decode appears in the fallback's OWN batch (4 on Deep, 3 on Normal) tagged path 2; flag OFF has it nowhere; batch 1 is identical")]
    [InlineData(DecodingDepth.Deep, 4)]
    [InlineData(DecodingDepth.Normal, 3)]
    public async Task EndToEnd_WeakSignal_PublishedInTheLastBatch(DecodingDepth depth, int expectedBatch)
    {
        int exercised = 0;
        foreach (int seed in WeakSeeds)
        {
            var pcm = Synthesise(WeakMessage, 1500.0, 0.55, WeakNoiseSigma, seed);
            var off = await Staged(Decoder(depth, false), pcm);
            if (off.SelectMany(b => b.Results).Any(r => r.Message == WeakMessage)) continue;
            var on = await Staged(Decoder(depth, true), pcm);

            on.SelectMany(b => b.Results).Where(r => r.Path == 2).Select(r => r.Message).Should().Contain(WeakMessage);
            var slot = on.Single(b => b.Results.Any(r => r.Path == 2));
            slot.Batch.Should().Be(expectedBatch);
            on.Select(b => b.Batch).Should().OnlyContain(n => n <= 4, "no batch number beyond the fallback's own");
            slot.Results.Should().OnlyContain(r => r.Path == 2, "the fallback's batch carries the fallback's decodes only");
            var fb = slot.Results.Single(r => r.Path == 2);
            fb.Snr.Should().BeInRange(-24, -17);
            fb.FreqHz.Should().BeInRange(1499, 1501);
            fb.Message.Should().Be(WeakMessage);

            // R13/A1 shape: flag ON = flag OFF + the fallback's own decodes, batch by batch
            on.Single(b => b.Batch == 1).Results.Should().Equal(off.Single(b => b.Batch == 1).Results, "batch 1 is untouched");
            foreach (var b in off)
                on.Where(x => x.Batch == b.Batch).SelectMany(x => x.Results).Where(r => r.Path != 2)
                  .Should().Equal(b.Results, $"batch {b.Batch} without the fallback's decodes equals flag OFF");
            exercised++;
        }
        exercised.Should().BeGreaterThan(0, "at least one seeded cycle must be missed by the ordinary decode");
    }

    public static IEnumerable<object[]> RecordedCycles()
    {
        foreach (var id in new[] { "synth-qso-01", "synth-qso-02", "synth-qso-03" })
            yield return new object[] { id };
    }

    [Theory(DisplayName = "R13/A1: recorded cycles - flag OFF is the pre-change staged decode (batch 1 = the single pass-0 decode), flag ON adds only path-2 decodes and changes nothing else")]
    [MemberData(nameof(RecordedCycles))]
    public async Task RecordedCycles_FlagOffIsThePreChangeDecode_FlagOnIsAdditive(string fixtureId)
    {
        float[] pcm;
        using (Stream s = OpenFixture($"Fixtures/{fixtureId}.wav")) pcm = WavReader.Read(s);

        // the reference for batch 1: pass 0 alone (residual pass off, no staged entry): the code path that never had the fallback
        var reference = new Ft8Decoder(new FakeClock(CycleStart));
        var pass0 = await reference.DecodeAsync(pcm, CycleStart, null);

        foreach (var depth in new[] { DecodingDepth.Deep, DecodingDepth.Normal })
        {
            var off = await Staged(Decoder(depth, false), pcm);
            var on  = await Staged(Decoder(depth, true), pcm);

            off.Single(b => b.Batch == 1).Results.Select(r => (r.Message, r.FreqHz, r.Snr, r.Dt))
               .Should().Equal(pass0.Select(r => (r.Message, r.FreqHz, r.Snr, r.Dt)), $"{depth}: flag OFF batch 1 is the pass-0 decode");
            off.SelectMany(b => b.Results).Should().OnlyContain(r => r.Path != 2, "flag OFF: nothing is tagged fallback");

            foreach (var b in off)
                on.Where(x => x.Batch == b.Batch).SelectMany(x => x.Results).Where(r => r.Path != 2)
                  .Should().Equal(b.Results, $"{depth}: batch {b.Batch} with the fallback's decodes removed equals flag OFF");
            on.Single(b => b.Batch == 1).Results.Should().Equal(off.Single(b => b.Batch == 1).Results, $"{depth}: batch 1 is untouched by the flag");
        }
    }

    private static Stream OpenFixture(string resourceSuffix)
    {
        Assembly asm = typeof(CoherentFallbackStage2NativeTests).Assembly;
        string name = asm.GetManifestResourceNames()
                         .First(n => n.EndsWith(resourceSuffix.Replace('/', '.'), StringComparison.OrdinalIgnoreCase));
        return asm.GetManifestResourceStream(name)!;
    }
}
