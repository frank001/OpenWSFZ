using System;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.InteropServices;
using FluentAssertions;
using OpenWSFZ.Ft8.Interop;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// COH-MULTISET Stage 1 (shim 20260071), the B2 tests of the native core: the four further coherent bit-metric sets C1, J2, J3, N1 and the
/// diagnostic export <c>ft8_coherent_fallback_sets_at</c> that returns each set's 174 raw values and BP-only outcome. Written before the
/// code, each able to fail: the grouping of J2 and J3, the codeword signs on a noiseless synthetic signal, and the identity-Gray mutation
/// (the same signal with the Gray map replaced by the identity must make J2 and J3 fail). Port fidelity against QA's Python reference is
/// QA's B1, not this file. Synthetic content only (NFR-021): the message is <c>CQ Q1ABC FN20</c>.
/// </summary>
public sealed class CoherentMultisetNativeTests
{
    private const int PcmSamples = 180_000;
    private const int SamplesPerSymbol = 1920;
    private const double ToneSpacingHz = 6.25;
    private const double SymbolPeriodS = 0.16;
    private const int DataSymbols = 58;
    private const int HalfSymbols = 29;
    private const int RawVectorLength = 174;
    private static readonly int[] GrayMap = { 0, 1, 3, 2, 5, 6, 4, 7 };      // the public FT8 protocol constant

    private const int SetC1 = 1, SetJ2 = 2, SetJ3 = 3, SetN1 = 4;             // index into CohSetsResult.Raw (0 is V3)

    /// <summary>The raw symbol (0..78) of data symbol k (0..57): the halves sit after the first and second Costas blocks.</summary>
    private static int RawSymbol(int k) => k + (k < HalfSymbols ? 7 : 14);

    private static float[] Synthesise(byte[] tones, double freqHz, double startS, double noiseSigma, int seed)
    {
        var pcm = new float[PcmSamples];
        double phase = 0.0;
        long n0 = (long)Math.Round(startS * 12000.0);
        for (int s = 0; s < tones.Length; s++)
        {
            double f = freqHz + ToneSpacingHz * tones[s];
            for (int i = 0; i < SamplesPerSymbol; i++)
            {
                long idx = n0 + (long)s * SamplesPerSymbol + i;
                if (idx >= 0 && idx < PcmSamples) pcm[idx] += (float)(0.3 * Math.Sin(phase));
                phase += 2.0 * Math.PI * f / 12000.0;
            }
        }
        if (noiseSigma > 0.0)
        {
            var rng = new Random(seed);
            for (int i = 0; i < PcmSamples; i++)
            {
                double u1 = 1.0 - rng.NextDouble(), u2 = rng.NextDouble();
                pcm[i] += (float)(noiseSigma * Math.Sqrt(-2.0 * Math.Log(u1)) * Math.Cos(2.0 * Math.PI * u2));
            }
        }
        return pcm;
    }

    /// <summary>The 174 codeword bits in the extractor's order: data symbol k, then Gray-index bit 2, 1, 0.</summary>
    private static int[] CodewordBits(byte[] tones)
    {
        var bits = new int[RawVectorLength];
        for (int k = 0; k < DataSymbols; k++)
        {
            int j = Array.IndexOf(GrayMap, (int)tones[RawSymbol(k)]);
            bits[3 * k] = (j >> 2) & 1;
            bits[3 * k + 1] = (j >> 1) & 1;
            bits[3 * k + 2] = j & 1;
        }
        return bits;
    }

    private static int SignMismatches(double[] raw, int[] bits)
    {
        int n = 0;
        for (int i = 0; i < RawVectorLength; i++)
            if ((raw[i] > 0.0 ? 1 : 0) != bits[i] || raw[i] == 0.0) n++;        // positive = bit 1; an exact zero decides nothing, so it counts as wrong
        return n;
    }

    /// <summary>A clean signal at 1500 Hz, symbol 0 at 0.55 s, the anchor on the true position (candidate convention: one symbol period later).</summary>
    private static (byte[] Tones, float[] Pcm, double F0, double T0) CleanSignal(double noiseSigma = 0.0, int seed = 1)
    {
        var tones = new byte[79];
        Ft8LibInterop.EncodeMessage("CQ Q1ABC FN20", tones);
        const double f = 1500.0, start = 0.55;
        return (tones, Synthesise(tones, f, start, noiseSigma, seed), f, start + SymbolPeriodS);
    }

    [Fact(DisplayName = "COH-MULTISET B2: the new structs have the documented sizes and offsets (ABI pin)")]
    public void StructSizes_MatchTheHeader()
    {
        Marshal.SizeOf<CohSetOutcomeNative>().Should().Be(CohSetOutcomeNative.ExpectedNativeSizeBytes).And.Be(32);
        Marshal.SizeOf<CohSetsResultNative>().Should().Be(CohSetsResultNative.ExpectedNativeSizeBytes).And.Be(216);
        Marshal.OffsetOf<CohSetsResultNative>(nameof(CohSetsResultNative.DtStep)).ToInt32().Should().Be(24);
        Marshal.OffsetOf<CohSetsResultNative>(nameof(CohSetsResultNative.WalkA910)).ToInt32().Should().Be(40);
        Marshal.OffsetOf<CohSetsResultNative>(nameof(CohSetsResultNative.V3)).ToInt32().Should().Be(56);
        Marshal.OffsetOf<CohSetsResultNative>(nameof(CohSetsResultNative.N1)).ToInt32().Should().Be(56 + 4 * 32);
    }

    [Fact(DisplayName = "COH-MULTISET B2: J2 makes 15 groups per half (14 pairs + 1 single), J3 makes 10 (9 triples + 1 pair), no group touches a Costas block")]
    public void Grouping_IsAsSpecified()
    {
        foreach (var (size, perHalf, fullGroups, tailLen) in new[] { (2, 15, 14, 1), (3, 10, 9, 2) })
        {
            var groups = Ft8LibInterop.CohFallbackSetGroups(size);
            groups.Count.Should().Be(2 * perHalf, $"J{size}: {perHalf} groups per half");

            var covered = new List<int>();
            foreach (var (first, len) in groups)
            {
                len.Should().BeInRange(1, size);
                for (int p = 0; p < len; p++) covered.Add(first + p);
                // a group never straddles the halves, so never a Costas block
                (first / HalfSymbols).Should().Be((first + len - 1) / HalfSymbols, "the group stays inside one half of 29");
                for (int p = 0; p < len; p++)
                {
                    int raw = RawSymbol(first + p);
                    (raw is >= 0 and <= 6).Should().BeFalse("no group touches symbols 0-6");
                    (raw is >= 36 and <= 42).Should().BeFalse("no group touches symbols 36-42");
                    (raw is >= 72 and <= 78).Should().BeFalse("no group touches symbols 72-78");
                }
            }
            covered.Should().Equal(Enumerable.Range(0, DataSymbols), "consecutive, non-overlapping, every data symbol exactly once");

            for (int half = 0; half < 2; half++)
            {
                var inHalf = groups.Where(g => g.FirstK / HalfSymbols == half).ToList();
                inHalf.Count.Should().Be(perHalf);
                inHalf.Count(g => g.Length == size).Should().Be(fullGroups, "full-size groups first");
                inHalf.Last().Length.Should().Be(tailLen, "the last group of a half is the remainder");
            }
        }
        FluentActions.Invoking(() => Ft8LibInterop.CohFallbackSetGroups(4)).Should().Throw<ArgumentOutOfRangeException>();
        FluentActions.Invoking(() => Ft8LibInterop.CohFallbackSetGroups(1)).Should().Throw<ArgumentOutOfRangeException>();
    }

    [Fact(DisplayName = "COH-MULTISET B2: on a noiseless synthetic signal every set's 174 signs equal the codeword's bits, and each decodes through BP only")]
    public void NoiselessSignal_EverySetCarriesTheCodeword()
    {
        var (tones, pcm, f0, t0) = CleanSignal();
        var bits = CodewordBits(tones);
        var res = Ft8LibInterop.CohFallbackSetsAt(pcm, f0, t0);

        res.Raw.Length.Should().Be(5);
        foreach (var (name, v) in new[] { ("V3", 0), ("C1", SetC1), ("J2", SetJ2), ("J3", SetJ3), ("N1", SetN1) })
            SignMismatches(res.Raw[v], bits).Should().Be(0, $"{name}: positive = bit 1, every sign equals the codeword's bit");

        res.V3.CrcValid.Should().BeTrue();
        res.Sets.Count.Should().Be(4);
        res.Sets.Should().OnlyContain(o => o.CrcValid && o.BpPath == 0, "every set decodes through BP only (path 0, never OSD)");
        res.Sets.Select(o => Convert.ToHexString(o.A91, 0, 10)).Distinct().Should().ContainSingle("all four sets recover the same payload")
            .Which.Should().Be(Convert.ToHexString(res.V3.A91, 0, 10));

        // the walk is not entered where V3 has a CRC-valid output
        res.WalkEntered.Should().BeFalse();
        res.WalkSet.Should().Be(0);
        Convert.ToHexString(res.WalkPayload, 0, 10).Should().Be(Convert.ToHexString(res.V3.A91, 0, 10));
    }

    [Fact(DisplayName = "COH-MULTISET B2: with the Gray map replaced by the identity, J2, J3 and N1 fail on that same signal (the mutation check)")]
    public void IdentityGrayMap_BreaksJ2AndJ3()
    {
        var (tones, pcm, f0, t0) = CleanSignal();
        var bits = CodewordBits(tones);
        var res = Ft8LibInterop.CohFallbackSetsAt(pcm, f0, t0, Ft8LibInterop.CohSetsIdentityGray);

        SignMismatches(res.Raw[SetJ2], bits).Should().BeGreaterThan(20, "the identity map must break J2");
        SignMismatches(res.Raw[SetJ3], bits).Should().BeGreaterThan(20, "the identity map must break J3");
        SignMismatches(res.Raw[SetN1], bits).Should().BeGreaterThan(20, "the identity map must break N1");
        SignMismatches(res.Raw[SetC1], bits).Should().Be(0, "C1 is the V3 extractor's own order-1 term and does not take the test hook");
        SignMismatches(res.Raw[0], bits).Should().Be(0, "V3 does not take the test hook");
        res.Sets[SetJ2 - 1].CrcValid.Should().BeFalse();
        res.Sets[SetJ3 - 1].CrcValid.Should().BeFalse();
    }

    [Fact(DisplayName = "COH-MULTISET B2: noise only: nothing is CRC-valid, the walk is entered and returns no set; a bad flag or length is refused")]
    public void NoiseOnly_WalkFindsNothing_AndBadArgumentsAreRefused()
    {
        var pcm = Synthesise(new byte[0], 1500.0, 0.55, noiseSigma: 0.1, seed: 99);
        var res = Ft8LibInterop.CohFallbackSetsAt(pcm, 1500.0, 0.71);
        res.V3.CrcValid.Should().BeFalse();
        res.Sets.Should().OnlyContain(o => !o.CrcValid);
        res.WalkEntered.Should().BeTrue();
        res.WalkSet.Should().Be(-1);
        res.WalkPayload.Should().OnlyContain(b => b == 0);

        FluentActions.Invoking(() => Ft8LibInterop.CohFallbackSetsAt(pcm, 1500.0, 0.71, flags: 2)).Should().Throw<InvalidOperationException>();
        FluentActions.Invoking(() => Ft8LibInterop.CohFallbackSetsAt(new float[PcmSamples - 1], 1500.0, 0.71)).Should().Throw<InvalidOperationException>();
    }
}
