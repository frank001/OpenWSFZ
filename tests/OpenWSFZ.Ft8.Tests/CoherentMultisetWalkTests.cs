using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Ft8.Interop;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// COH-MULTISET Stage 2 against the REAL native library: the walk in the product path (M1, A1.1, A1 and the runner's per-context rule).
/// The fixtures are synthetic cycles (NFR-021: the message is <c>CQ Q1ABC FN20</c>) at noise levels where V3 fails at the signal's position
/// and a further set (found by a scan, J3 in every case) recovers the payload. Which seeds do that is a numeric fact of the platform that
/// found them (macOS arm64 differs from x86-64 in the last bits), so each test takes the fixtures that win on THIS platform and requires at
/// least one; it never asserts a particular seed.
/// </summary>
public sealed class CoherentMultisetWalkTests
{
    private const int PcmSamples = 180_000;
    private const string Message = "CQ Q1ABC FN20";

    /// <summary>(noise sigma, seed) pairs at which V3 fails at the true position and a further set recovers the payload (found by a scan).</summary>
    private static readonly (double Sigma, int Seed)[] WalkCandidates = [(3.4, 6), (3.6, 18), (3.6, 23), (4.0, 22)];

    /// <summary>(noise sigma, seed) pairs at which V3 itself recovers the payload (a V3-CRC-valid candidate beside V3 failures).</summary>
    private static readonly (double Sigma, int Seed)[] V3Candidates = [(3.5, 1), (3.5, 3), (3.5, 4)];

    private static float[] Synthesise(double sigma, int seed)
    {
        var tones = new byte[79];
        Ft8LibInterop.EncodeMessage(Message, tones);
        var pcm = new float[PcmSamples];
        double phase = 0.0;
        long n0 = (long)Math.Round(0.55 * 12000.0);
        for (int s = 0; s < tones.Length; s++)
        {
            double f = 1500.0 + 6.25 * tones[s];
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
            pcm[i] += (float)(sigma * Math.Sqrt(-2.0 * Math.Log(u1)) * Math.Cos(2.0 * Math.PI * u2));
        }
        return pcm;
    }

    private sealed record Cycle(float[] Pcm, byte[] Snapshot);

    private static Cycle MakeCycle(double sigma, int seed)
    {
        var pcm = Synthesise(sigma, seed);
        Ft8LibInterop.DecodeAll(pcm);
        return new Cycle(pcm, Ft8LibInterop.CohFallbackSnapshot());      // same thread, nothing in between
    }

    /// <summary>The walk candidates that really win on this platform (V3 fails, a further set is CRC-valid at the signal's position).</summary>
    private static List<(double Sigma, int Seed)> WinningCandidates()
    {
        var win = new List<(double, int)>();
        foreach (var (sigma, seed) in WalkCandidates)
        {
            var r = Ft8LibInterop.CohFallbackSetsAt(Synthesise(sigma, seed), 1500.0, 0.55 + 0.16);
            if (!r.V3.CrcValid && r.Sets.Any(s => s.CrcValid)) win.Add((sigma, seed));
        }
        win.Should().NotBeEmpty("at least one fixture must be a position where V3 fails and a further set decodes, else these tests prove nothing");
        return win;
    }

    private static string Key(CohFallbackRow r, bool withProvenance = true)
        => $"{r.FreqHz:R}/{r.DtS:R}/{r.OutFreqHz:R}/{r.OutDtS:R}/{r.Pass}/{r.Edge}/{r.State}/{r.SnrDb}/{r.F1bDb:R}/{Convert.ToHexString(r.Payload)}"
           + (withProvenance ? $"/prov{r.Provenance}" : "");

    private static bool IsCrcValid(CohFallbackRow r) => r.State is CohFallbackState.Known or CohFallbackState.GatedOut or CohFallbackState.NewGated;

    // ── the walk takes the ordinary path ────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "COH-MULTISET: where V3 fails, ON recovers the payload through a further set and it takes the ordinary path (new payload, SNR, F1b gate -> NewGated); OFF publishes nothing there")]
    public void Walk_RecoversWhereV3Fails_AndTakesTheOrdinaryPath()
    {
        foreach (var (sigma, seed) in WinningCandidates())
        {
            var c = MakeCycle(sigma, seed);
            var off = Ft8LibInterop.CohFallbackRun(c.Pcm, c.Snapshot, -1, multiSet: false, CancellationToken.None);
            var on = Ft8LibInterop.CohFallbackRun(c.Pcm, c.Snapshot, -1, multiSet: true, CancellationToken.None);

            off.Rows.Should().NotContain(r => r.State == CohFallbackState.NewGated, "sigma {0} seed {1}: V3 alone finds nothing here", sigma, seed);
            var won = on.Rows.Where(r => r.Provenance is >= 1 and <= 4).ToList();
            won.Should().ContainSingle("sigma {0} seed {1}: exactly one position is recovered by a further set", sigma, seed);
            var row = won[0];
            row.State.Should().Be(CohFallbackState.NewGated, "a new payload with F1b <= T1 takes the existing gate path");
            row.F1bDb.Should().BeLessThanOrEqualTo(17.552446);
            row.SnrDb.Should().BeLessThan(0, "the coherent SNR is filled in by the existing path");
            Ft8LibInterop.CohFallbackUnpack(row.Payload).Should().Be(Message);
            on.Stats.CrcNew.Should().Be(off.Stats.CrcNew + 1);
            on.Stats.Gated.Should().Be(off.Stats.Gated + 1);
            on.CrcValidBySet(row.Provenance).Should().Be(1);
        }
    }

    // ── M1: the walk is entered where, and only where, V3 gave no CRC-valid output ───────────────────────────────

    [Fact(DisplayName = "M1: the walk-entry counter equals the number of NO_CRC candidates of the same call; a V3-CRC-valid candidate shows 0 entries and an unchanged row")]
    public void WalkEntries_EqualTheNoCrcCandidates_AndSkipV3Successes()
    {
        int v3ValidSeen = 0;
        var fixtures = WinningCandidates().Concat(V3Candidates).ToList();
        foreach (var (sigma, seed) in fixtures)
        {
            var c = MakeCycle(sigma, seed);
            var off = Ft8LibInterop.CohFallbackRun(c.Pcm, c.Snapshot, -1, multiSet: false, CancellationToken.None);
            var on = Ft8LibInterop.CohFallbackRun(c.Pcm, c.Snapshot, -1, multiSet: true, CancellationToken.None);

            off.Stats.WalkEntered.Should().Be(0, "OFF never enters the walk");
            off.Rows.Should().OnlyContain(r => r.Provenance == 0);
            int noCrc = off.Rows.Count(r => r.State == CohFallbackState.NoCrc);
            on.Stats.WalkEntered.Should().Be(noCrc, "sigma {0} seed {1}: the walk is entered by exactly the candidates V3 left without a CRC-valid output", sigma, seed);
            on.Stats.Attempted.Should().Be(off.Stats.Attempted);

            for (int i = 0; i < off.Rows.Count; i++)
            {
                if (IsCrcValid(off.Rows[i]))
                {
                    v3ValidSeen++;
                    Key(on.Rows[i]).Should().Be(Key(off.Rows[i]), "a V3-CRC-valid candidate (known, new, gated or gated out) never enters the walk: row {0} is unchanged and its provenance is 0", i);
                }
                else if (!IsCrcValid(on.Rows[i]))
                {
                    Key(on.Rows[i], withProvenance: false).Should().Be(Key(off.Rows[i], withProvenance: false), "a walk that found nothing leaves the row as OFF had it");
                    on.Rows[i].Provenance.Should().Be(-1, "the walk ran and found nothing");
                }
            }
        }
        v3ValidSeen.Should().BeGreaterThan(0, "at least one fixture carries a V3-CRC-valid candidate, else the 'never enters where V3 is valid' half of M1 is vacuous");
    }

    [Fact(DisplayName = "M1: a candidate the fallback did not attempt (deadline already passed) shows 0 walk entries and rows equal to OFF's")]
    public void NotAttempted_ShowsNoWalkEntries()
    {
        var (sigma, seed) = WinningCandidates()[0];
        var c = MakeCycle(sigma, seed);
        var off = Ft8LibInterop.CohFallbackRun(c.Pcm, c.Snapshot, 0.0, multiSet: false, CancellationToken.None);
        var on = Ft8LibInterop.CohFallbackRun(c.Pcm, c.Snapshot, 0.0, multiSet: true, CancellationToken.None);

        on.Stats.Attempted.Should().Be(0);
        on.Stats.WalkEntered.Should().Be(0);
        on.Rows.Select(r => Key(r)).Should().Equal(off.Rows.Select(r => Key(r)));
        on.Rows.Should().OnlyContain(r => r.State == CohFallbackState.Abandoned && r.Provenance == 0);
    }

    // ── A1.1: a long-lived context, a flag that changes between cycles ──────────────────────────────────────────

    private static List<CohFallbackRow> RunOn(ICohFallbackWorker worker, Cycle c, bool? setBit)
    {
        if (setBit is { } b) worker.SetMultiSet(b);
        var plan = Ft8LibInterop.CohFallbackMakePlan(c.Snapshot);
        return plan.CandidateIndex.Select(i => worker.Process(c.Pcm, c.Snapshot, i)).ToList();
    }

    private static List<CohFallbackRow> OnFresh(Cycle c, bool setBit)
    {
        using var fresh = CohFallbackLibBackend.Instance.CreateWorker();
        return RunOn(fresh, c, setBit);
    }

    [Theory(DisplayName = "A1.1: one context across two cycles - flag ON then OFF, and OFF then ON - gives each cycle the outputs of a fresh context with that cycle's flag")]
    [InlineData(true, false)]
    [InlineData(false, true)]
    public void LongLivedContext_FollowsTheFlagOfEachCycle(bool first, bool second)
    {
        var wins = WinningCandidates();
        var cycleA = MakeCycle(wins[0].Sigma, wins[0].Seed);
        var cycleB = MakeCycle(wins[^1].Sigma, wins[^1].Seed);
        var freshA = OnFresh(cycleA, first).Select(r => Key(r)).ToList();
        var freshB = OnFresh(cycleB, second).Select(r => Key(r)).ToList();
        (first ? freshA : freshB).Any(k => !k.EndsWith("/prov0") && !k.EndsWith("/prov-1")).Should().BeTrue("the ON cycle must show a further set's win, or the comparison cannot tell the flags apart");

        using var worker = CohFallbackLibBackend.Instance.CreateWorker();
        RunOn(worker, cycleA, first).Select(r => Key(r)).Should().Equal(freshA, "cycle 1, flag {0}", first);
        RunOn(worker, cycleB, second).Select(r => Key(r)).Should().Equal(freshB, "cycle 2, flag {0}, same context", second);
    }

    [Fact(DisplayName = "A1.1: a NEW context defaults to OFF natively - with no setter call it behaves exactly as the flag OFF")]
    public void NewContext_DefaultsToOff()
    {
        var (sigma, seed) = WinningCandidates()[0];
        var c = MakeCycle(sigma, seed);
        using var untouched = CohFallbackLibBackend.Instance.CreateWorker();
        var rows = RunOn(untouched, c, setBit: null);
        rows.Should().OnlyContain(r => r.Provenance == 0 && r.State != CohFallbackState.NewGated);
        rows.Select(r => Key(r)).Should().Equal(OnFresh(c, false).Select(r => Key(r)));
        untouched.Accumulated.WalkEntered.Should().Be(0);
    }

    // ── A1: flag false changes nothing, end to end ──────────────────────────────────────────────────────────────

    private sealed record Out(int Batch, string Message, int FreqHz, int Snr, int Path);

    private static async Task<List<Out>> Decode(float[] pcm, bool fallbackOn, bool? multiSet)
    {
        var start = new DateTime(2026, 10, 24, 12, 0, 0, DateTimeKind.Utc);
        var d = new Ft8Decoder(new FakeClock(start), null, interop: new Ft8NativeInteropAdapter());
        d.SetSubtractionEnabled(true);
        d.SetDecodingDepth(DecodingDepth.Deep);
        d.SetCoherentFallbackEnabled(fallbackOn);
        if (multiSet is { } m) d.SetCoherentFallbackMultiSet(m);
        var got = new List<Out>();
        await d.DecodeStagedAsync(pcm, start, null, (n, b) =>
        {
            got.AddRange(b.Select(x => new Out(n, x.Message, x.FreqHz, x.Snr, x.Path)));
            return Task.CompletedTask;
        });
        return got;
    }

    [Fact(DisplayName = "A1: with the flag false (default or explicit) the staged decode's batches are identical to the fallback without it, with the fallback ON and OFF; ON adds the further-set decode as batch 4")]
    public async Task FlagFalse_ChangesNothing_FlagTrueAddsTheDecode()
    {
        foreach (var (sigma, seed) in WinningCandidates().Take(2).Concat(V3Candidates.Take(1)))
        {
            var pcm = Synthesise(sigma, seed);
            foreach (bool fallbackOn in new[] { true, false })
            {
                var baseline = await Decode(pcm, fallbackOn, multiSet: null);          // the flag never touched: its default
                var explicitFalse = await Decode(pcm, fallbackOn, multiSet: false);
                explicitFalse.Should().Equal(baseline, "sigma {0} seed {1}, fallback {2}: the explicit false is the default", sigma, seed, fallbackOn);

                var on = await Decode(pcm, fallbackOn, multiSet: true);
                if (!fallbackOn) on.Should().Equal(baseline, "the multi-set flag acts only while the fallback itself is on");
            }

            var withFallback = await Decode(pcm, true, null);
            var withSets = await Decode(pcm, true, true);
            withSets.Where(o => o.Path != 2).Should().Equal(withFallback.Where(o => o.Path != 2), "the sets touch nothing but the fallback's own batch");
            withSets.Count(o => o.Path == 2).Should().BeGreaterThanOrEqualTo(withFallback.Count(o => o.Path == 2));
        }

        var (ws, wseed) = WinningCandidates()[0];
        var winPcm = Synthesise(ws, wseed);
        (await Decode(winPcm, true, false)).Should().NotContain(o => o.Message == Message && o.Path == 2, "flag false: V3 fails here, nothing is published");
        (await Decode(winPcm, true, true)).Should().Contain(o => o.Message == Message && o.Path == 2 && o.Batch == 4, "flag true: the further set's decode is the fallback's batch 4");
    }
}
