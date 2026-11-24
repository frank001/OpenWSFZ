using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Ft8.Interop;
using OpenWSFZ.Ft8.Subfeas;
using Xunit;
using Xunit.Abstractions;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// CQ-AP (shim 20260072): the native CQ a-priori attempt, against the real DLL. Q-prefix calls only (NFR-021). The native flag, counters and
/// ap-kind getter are thread-local, so every test sets the flag and reads the results on one thread with nothing awaited in between, and restores
/// the flag in a <c>finally</c>.
/// <para>
/// TESTING_STRATEGY section 11: no delay anywhere; the synthetic audio is seeded and every statistical assertion is a margin over a seeded sample
/// (ON must beat OFF, never an exact count), because a marginal decode can flip on another platform.
/// </para>
/// </summary>
[Trait("Category", "Integration")]
public sealed class CqApNativeTests(ITestOutputHelper output)
{
    private const string CqMessage    = "CQ Q1ABC JO22";
    private const string NonCqMessage = "Q1ABC Q2DEF JO22";

    private const int    CycleSamples = 180_000;
    private const int    CodewordBits = 174;
    private const int    PayloadBits  = 77;
    private const int    ForcedBits   = 32;                 // payload bits 0-28 and 74-76
    private const double BaseHz       = 1500.0;
    private const int    StartSample  = 6_000;               // 0.5 s into the cycle: inside the candidate search window, far from the DT clamp's edge
    private const float  SignalAmp    = 0.1f;
    private const float  PcmTargetRms = 0.20f;                // the decoder's own D-002 normalisation level

    // ── helpers ──────────────────────────────────────────────────────────────────────────────────────────────────

    /// <summary>The encoder's own tones, payload bits (0/1 per element) and 174-bit codeword for a message.</summary>
    private static (byte[] Tones, byte[] Payload, byte[] Codeword) Encode(string message)
    {
        var tones = new byte[Ft8LibInterop.EncodedToneCount];
        Ft8LibInterop.EncodeMessage(message, tones);
        bool[] bits77 = SubfeasPayload.ExtractPayload77(tones);
        var payload = bits77.Select(b => (byte)(b ? 1 : 0)).ToArray();
        var codeword = TestFt8Encoder.LdpcEncode(TestFt8Encoder.AppendCrc14(payload));
        // The independent encoder and the native one must agree on the whole frame, or the codeword below is not this message's.
        TestFt8Encoder.BitsToSymbols(codeword).Select(s => (byte)s).Should().Equal(tones, "the test's own LDPC encoder reproduces the native frame");
        return (tones, payload, codeword);
    }

    /// <summary>One 15 s cycle: the message at <paramref name="snrDb"/> (2500 Hz noise bandwidth) in seeded white noise, RMS-normalised like the decoder does.</summary>
    private static float[] Synthesise(string? message, double snrDb, int seed, params double[] baseHz)
    {
        var pcm = new float[CycleSamples];
        if (message is not null)
        {
            var tones = new byte[Ft8LibInterop.EncodedToneCount];
            Ft8LibInterop.EncodeMessage(message, tones);
            foreach (double hz in baseHz)
            {
                var frame = TestFt8Encoder.SymbolsToPcm(tones.Select(t => (int)t).ToArray(), hz, StartSample, SignalAmp);
                for (int i = 0; i < CycleSamples; i++) pcm[i] += frame[i];
            }
        }
        double sigma = Math.Sqrt((SignalAmp * SignalAmp / 2.0) / Math.Pow(10.0, snrDb / 10.0) * (6000.0 / 2500.0));
        var rng = new Random(seed);
        for (int i = 0; i < CycleSamples; i++)
        {
            double u1 = 1.0 - rng.NextDouble(), u2 = 1.0 - rng.NextDouble();
            pcm[i] += (float)(sigma * Math.Sqrt(-2.0 * Math.Log(u1)) * Math.Cos(2.0 * Math.PI * u2));
        }
        return Ft8Decoder.NormalisePcm(pcm, PcmTargetRms);
    }

    private static bool Has(Ft8NativeResult[] results, string message)
        => results.Any(r => r.Message.TrimEnd() == message);

    /// <summary>One native decode with the flag as given, restoring it to off afterwards. Same thread throughout.</summary>
    private static (Ft8NativeResult[] Results, (int Attempts, int Decodes, int OsdEntries) Stats, byte[] Snapshot) Decode(float[] pcm, bool cqAp)
    {
        Ft8LibInterop.SetCqApEnabled(cqAp);
        try
        {
            var results = Ft8LibInterop.DecodeAll(pcm);
            var stats = Ft8LibInterop.GetLastCqApStats();
            return (results, stats, Ft8LibInterop.CohFallbackSnapshot());
        }
        finally
        {
            Ft8LibInterop.SetCqApEnabled(false);
        }
    }

    /// <summary>Resets the thread's native per-call counters (a decode of silence) so a following probe read starts from zero.</summary>
    private static void ResetCounters()
    {
        Ft8LibInterop.SetCqApEnabled(false);
        Ft8LibInterop.DecodeAll(new float[CycleSamples]);
    }

    private static string Describe(Ft8NativeResult[] r)
        => string.Join(" | ", r.Select(x => $"{x.Message.TrimEnd()}@{x.FreqHz}/{x.Dt:F2}/{x.Snr}/{x.ApKind}"));

    // ── D1: the bits ─────────────────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-103: CQ-AP D1: the forcing pattern overrides exactly 32 positions, each equal to the encoder's bit for 'CQ Q1ABC JO22' (bits 0-28 and 74-76)")]
    public void Pattern_ForcesExactly32Positions_EqualToTheEncodedBits()
    {
        var (_, payload, _) = Encode(CqMessage);
        byte[] force = Ft8LibInterop.CqApPattern();

        force.Should().HaveCount(CodewordBits);
        int forced = force.Count(f => f != 0);
        forced.Should().Be(ForcedBits, "bits 0-28 (29 positions) and 74-76 (3 positions), no others");

        for (int i = 0; i < CodewordBits; i++)
        {
            bool shouldForce = i < 29 || (i >= 74 && i < PayloadBits);
            if (shouldForce)
                force[i].Should().Be((byte)(payload[i] == 1 ? 2 : 1), $"position {i} must be forced to the encoded bit {payload[i]} (2 = bit 1, positive LLR; 1 = bit 0, negative)");
            else
                force[i].Should().Be(0, $"position {i} is outside bits 0-28 and 74-76 and must not be forced");
        }
    }

    [Fact(DisplayName = "FR-103: CQ-AP D1: the forced fields are c28('CQ') << 1 | ipa 0 and i3 = 1 (so the pattern is the CQ token, not some other call)")]
    public void Pattern_FieldValues_AreTheCqTokenAndI3EqualsOne()
    {
        var (_, payload, _) = Encode(CqMessage);
        ulong n29a = 0;
        for (int i = 0; i < 29; i++) n29a = (n29a << 1) | payload[i];
        ulong i3 = 0;
        for (int i = 74; i < PayloadBits; i++) i3 = (i3 << 1) | payload[i];

        n29a.Should().Be((2UL << 1) | 0UL, "ft8_lib's c28 of the token CQ is 2, shifted left once for the ipa flag (0)");
        i3.Should().Be(1UL, "a standard message");

        byte[] force = Ft8LibInterop.CqApPattern();
        ulong forcedN29a = 0;
        for (int i = 0; i < 29; i++) forcedN29a = (forcedN29a << 1) | (force[i] == 2 ? 1UL : 0UL);
        forcedN29a.Should().Be(n29a);
    }

    [Fact(DisplayName = "FR-103: CQ-AP D1: the forced LLRs are written AFTER normalisation, at 1.01 x the largest |LLR| of the normalised non-forced entries, with the right sign")]
    public void ForcedLlrs_AreAfterNormalisation_At1p01TimesTheMaxNonForced()
    {
        byte[] force = Ft8LibInterop.CqApPattern();

        // Raw LLRs with a known spread; the forced positions carry a huge raw value so that injecting BEFORE normalisation (inflating the variance
        // and shrinking every other entry) is a different, detectable array.
        var rng = new Random(20261110);
        var raw = new float[CodewordBits];
        for (int i = 0; i < CodewordBits; i++)
            raw[i] = force[i] != 0 ? (rng.Next(2) == 0 ? -40f : 40f) : (float)((rng.NextDouble() * 2.0 - 1.0) * 6.0);

        double sum = 0, sum2 = 0;
        foreach (float x in raw) { sum += x; sum2 += (double)x * x; }
        double mean = sum / CodewordBits;
        double variance = sum2 / CodewordBits - mean * mean;
        double norm = Math.Sqrt(24.0 / variance);                                  // ftx_normalize_logl's own constant and form

        var (_, finalLlr, _, _) = Ft8LibInterop.CqApProbeLlrs(raw, maxIters: 1, allowOsd: false, flipSign: false);

        double maxNonForced = 0;
        for (int i = 0; i < CodewordBits; i++)
            if (force[i] == 0) maxNonForced = Math.Max(maxNonForced, Math.Abs(raw[i] * norm));

        for (int i = 0; i < CodewordBits; i++)
        {
            if (force[i] == 0)
                finalLlr[i].Should().BeApproximately((float)(raw[i] * norm), 1e-3f, $"non-forced position {i} is the raw value scaled by the variance of ALL raw entries (normalised before any forcing)");
            else
            {
                Math.Abs(finalLlr[i]).Should().BeApproximately((float)(1.01 * maxNonForced), 1e-3f, $"forced position {i} has magnitude 1.01 x the largest normalised non-forced |LLR|");
                (finalLlr[i] > 0).Should().Be(force[i] == 2, $"forced position {i}: bit 1 is a positive LLR, bit 0 negative");
            }
        }
    }

    [Fact(DisplayName = "FR-103: CQ-AP D1b: on a clean encoded 'CQ Q1ABC JO22' the right-sign override decodes it and the opposite-sign override does not")]
    public void Sign_RightDecodes_OppositeDoesNot()
    {
        var (_, payload, codeword) = Encode(CqMessage);
        var raw = codeword.Select(b => b == 1 ? 4f : -4f).ToArray();               // noise-free, bit 1 = positive (bp_decode's convention)

        var right = Ft8LibInterop.CqApProbeLlrs(raw, maxIters: 40, allowOsd: false, flipSign: false);
        right.Decoded.Should().BeTrue("the correct-sign CQ bits agree with the clean channel");
        right.LdpcErrors.Should().Be(0);
        for (int i = 0; i < PayloadBits; i++)
            ((right.A91[i / 8] >> (7 - i % 8)) & 1).Should().Be(payload[i], $"decoded payload bit {i}");

        var opposite = Ft8LibInterop.CqApProbeLlrs(raw, maxIters: 40, allowOsd: false, flipSign: true);
        opposite.Decoded.Should().BeFalse("32 positions forced to the WRONG sign, stronger than every channel LLR, must not yield this codeword");
    }

    // ── D4: BP only, with a counter that can count ───────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-103: CQ-AP D4: across noise cycles in which the OSD would have been reachable (BP fails on every CQ-AP attempt) the CQ-AP OSD counter reads 0")]
    public void OsdCounter_ReadsZero_OnTheProductionPath()
    {
        int attempts = 0;
        for (int seed = 0; seed < 12; seed++)
        {
            var (_, stats, _) = Decode(Synthesise(null, -20, 7000 + seed), cqAp: true);
            attempts += stats.Attempts;
            stats.OsdEntries.Should().Be(0, $"seed {seed}: the CQ-AP attempt is belief propagation only");
        }
        attempts.Should().BeGreaterThan(100, "BP failed on a large number of CQ-AP attempts, so the OSD WAS reachable and was not taken");
    }

    [Fact(DisplayName = "FR-103: CQ-AP D4: the OSD counter can count - a test copy that does enter the OSD reads > 0, and the BP-only call leaves it at 0")]
    public void OsdCounter_CanCount()
    {
        var rng = new Random(99);
        var noiseLlr = new float[CodewordBits];
        for (int i = 0; i < CodewordBits; i++) noiseLlr[i] = (float)((rng.NextDouble() * 2.0 - 1.0) * 3.0);

        ResetCounters();
        var bpOnly = Ft8LibInterop.CqApProbeLlrs(noiseLlr, maxIters: 20, allowOsd: false, flipSign: false);
        bpOnly.Decoded.Should().BeFalse("noise does not decode");
        bpOnly.LdpcErrors.Should().BeGreaterThan(0, "BP failed, which is where the OSD would be entered");
        Ft8LibInterop.GetLastCqApStats().OsdEntries.Should().Be(0, "the BP-only call never enters the OSD");

        Ft8LibInterop.CqApProbeLlrs(noiseLlr, maxIters: 20, allowOsd: true, flipSign: false);
        Ft8LibInterop.GetLastCqApStats().OsdEntries.Should().BeGreaterThan(0, "the sensitivity hook that does enter the OSD is counted");
        ResetCounters();
    }

    // ── D3: extra, never instead; placement ──────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-103: CQ-AP D3: a candidate the normal attempt decodes is never counted as a CQ-AP attempt, and a decode the normal attempt makes is unchanged with the flag on")]
    public void NeverInstead_NormalDecodesAreUnchanged_AndNotCountedAsAttempts()
    {
        foreach (string message in new[] { NonCqMessage, CqMessage })
        {
            var pcm = Synthesise(message, -8, 31, BaseHz);

            var off = Decode(pcm, cqAp: false);
            var on = Decode(pcm, cqAp: true);

            Has(off.Results, message).Should().BeTrue($"a clean {message} decodes normally");
            Describe(on.Results).Should().Be(Describe(off.Results), "with the flag on every decode the normal attempt makes is identical (text, frequency, dt, SNR) and untagged");
            on.Results.Should().OnlyContain(r => r.ApKind == ApKind.None, "nothing here needed the CQ attempt");
            on.Stats.Decodes.Should().Be(0);

            // The candidate counts are thread-local to the most recent native call: read them straight after the ON call (nothing decoded in between).
            on = Decode(pcm, cqAp: true);
            int candidates = Ft8LibInterop.GetLastCandidateCounts(Ft8LibInterop.MaxDecodePasses).Sum();
            on.Stats.Attempts.Should().BeLessThan(candidates, "at least the candidate the normal attempt decoded was not attempted again");
            on.Stats.Attempts.Should().BeLessThanOrEqualTo(candidates - on.Results.Length, "every decode is a candidate the normal attempt succeeded on, and none of those is a CQ-AP attempt");
        }
    }

    [Fact(DisplayName = "FR-103: CQ-AP D3: a CQ-AP decode is a decode for the coherent fallback (its candidate is no longer eligible) and is published once even when two candidates decode to it")]
    public void Placement_CqApDecode_ClearsFallbackEligibility_AndGoesThroughDedup()
    {
        int exercised = 0, doubled = 0;
        for (int seed = 2000; seed < 2060; seed++)
        {
            // Two weak copies of the same CQ at different frequencies: the same payload can be decoded twice in one call.
            var pcm = Synthesise(CqMessage, -20, seed, 1000.0, 2000.0);
            var off = Decode(pcm, cqAp: false);
            var on = Decode(pcm, cqAp: true);

            // The cross-pass dedup keys on the payload: the same message decoded from two candidates (two frequencies) is published once.
            on.Results.Count(r => r.Message.TrimEnd() == CqMessage).Should().BeLessThanOrEqualTo(1, "the cross-pass dedup applies to a CQ-AP decode exactly as to any other");

            int cq = on.Results.Count(r => r.ApKind == ApKind.Cq);
            if (cq == 0) continue;
            exercised++;

            int eligibleOff = Ft8LibInterop.CohFallbackMakePlan(off.Snapshot).Rows.Count;
            int eligibleOn = Ft8LibInterop.CohFallbackMakePlan(on.Snapshot).Rows.Count;
            (eligibleOff - eligibleOn).Should().BeGreaterThanOrEqualTo(cq,
                $"seed {seed}: each CQ-AP decode marks its candidate decoded before the continue branch, so the coherent fallback does not retry it");
            if (eligibleOff - eligibleOn >= 2) doubled++;
        }
        exercised.Should().BeGreaterThan(0, "at least one seeded cycle must have been decoded by the CQ attempt, or the test proves nothing");
        output.WriteLine($"cycles decoded by CQ-AP: {exercised}; of those, with two candidates cleared (the dedup path): {doubled}");
    }

    // ── D2: OFF is today's decoder ───────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-103: CQ-AP D2: with the flag off nothing is counted, every decode is untagged, and a thread that ran with the flag on is back to the old behaviour once it is set off")]
    public void FlagOff_CountsNothing_TagsNothing()
    {
        var pcm = Synthesise(CqMessage, -20, 1003, BaseHz);

        var on = Decode(pcm, cqAp: true);
        on.Stats.Attempts.Should().BeGreaterThan(0);

        var off = Decode(pcm, cqAp: false);
        off.Stats.Should().Be((0, 0, 0), "flag off: no attempt, no decode, no OSD entry");
        off.Results.Should().NotContain(r => r.ApKind != ApKind.None);

        // The default, on a fresh decode with no setter call at all, is off.
        Ft8LibInterop.DecodeAll(pcm).Should().NotContain(r => r.ApKind != ApKind.None);
        Ft8LibInterop.GetLastCqApStats().Should().Be((0, 0, 0));
    }

    [Fact(DisplayName = "FR-103: CQ-AP D2: QSO-AP active: the flag changes nothing about a decode the QSO-AP attempt makes, and the QSO-AP path itself is not the CQ path")]
    public void QsoAp_IsUnchanged_ByTheFlag()
    {
        byte[] mycall = Ft8CallsignPacker.Pack28("Q1ABC");
        byte[] hiscall = Ft8CallsignPacker.Pack28("Q2DEF");
        var pcm = Synthesise(NonCqMessage, -8, 77, BaseHz);

        Ft8LibInterop.SetApBits(mycall, hiscall);
        try
        {
            var off = Decode(pcm, cqAp: false);
            var on = Decode(pcm, cqAp: true);
            Has(off.Results, NonCqMessage).Should().BeTrue();
            Describe(on.Results).Should().Be(Describe(off.Results), "QSO-AP active, flag on: the QSO-AP decode is identical");
            on.Results.Should().OnlyContain(r => r.ApKind == ApKind.None);
        }
        finally
        {
            Ft8LibInterop.SetApBits([], []);
        }
    }

    // ── D10: synthetic audio ─────────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-103: CQ-AP D10(a): near threshold, ON decodes more of a weak 'CQ Q1ABC JO22' than OFF, every extra one tagged cq (SNR chosen from a short sweep, -20 dB in 2500 Hz)")]
    public void WeakCq_ON_DecodesMoreThanOFF_AndTagsThem()
    {
        const int cycles = 60;
        int off = 0, on = 0, cqTagged = 0, offMissedOnGot = 0;
        for (int seed = 1000; seed < 1000 + cycles; seed++)
        {
            var pcm = Synthesise(CqMessage, -20, seed, BaseHz);
            var r0 = Decode(pcm, cqAp: false);
            var r1 = Decode(pcm, cqAp: true);
            bool offGot = Has(r0.Results, CqMessage), onGot = Has(r1.Results, CqMessage);
            if (offGot) off++;
            if (onGot) on++;
            if (!offGot && onGot)
            {
                offMissedOnGot++;
                r1.Results.Single(r => r.Message.TrimEnd() == CqMessage).ApKind.Should().Be(ApKind.Cq, $"seed {seed}: a decode the normal attempt missed is the CQ attempt's");
            }
            foreach (var r in r1.Results.Where(x => x.ApKind == ApKind.Cq))
            {
                cqTagged++;
                r.Message.TrimEnd().Should().StartWith("CQ ", "a CQ-AP decode is a CQ");
            }
            if (offGot) onGot.Should().BeTrue($"seed {seed}: the CQ attempt only adds, a decode OFF makes ON makes too");
        }
        output.WriteLine($"-20 dB, {cycles} cycles: OFF {off}  ON {on}  tagged {cqTagged}  OFF-missed-ON-got {offMissedOnGot}");
        offMissedOnGot.Should().BeGreaterThan(0, "at least one cycle OFF fails and ON decodes");
        on.Should().BeGreaterThan(off, "ON decodes more than OFF");
    }

    [Fact(DisplayName = "FR-103: CQ-AP D10(b): a non-CQ 'Q1ABC Q2DEF JO22' is never decoded with apKind cq (flag on, from just decodable to well below threshold)")]
    public void NonCq_IsNeverTaggedCq()
    {
        int decodedNormally = 0, cqTagged = 0;
        foreach (double snr in new[] { -18.0, -20.0, -22.0, -24.0 })
        {
            for (int seed = 3000; seed < 3020; seed++)
            {
                var (results, _, _) = Decode(Synthesise(NonCqMessage, snr, seed, BaseHz), cqAp: true);
                cqTagged += results.Count(r => r.ApKind == ApKind.Cq);
                if (Has(results, NonCqMessage)) decodedNormally++;
            }
        }
        output.WriteLine($"non-CQ: decoded normally in {decodedNormally} of 80 cycles; cq-tagged {cqTagged}");
        cqTagged.Should().Be(0, "with the CQ bits forced, a message that is not a CQ cannot come out of the CQ attempt");
        decodedNormally.Should().BeGreaterThan(0, "the fixture is decodable by the normal attempt in some cycles, so this is not a vacuous check");
    }

    [Fact(DisplayName = "FR-103: CQ-AP D10(c): noise-only audio gives 0 cq decodes over 240 cycles with the flag on (and the attempt really ran)")]
    public void NoiseOnly_GivesNoCqDecodes()
    {
        const int cycles = 240;
        int cqTagged = 0, attempts = 0;
        for (int seed = 0; seed < cycles; seed++)
        {
            var (results, stats, _) = Decode(Synthesise(null, -20, 5000 + seed), cqAp: true);
            cqTagged += results.Count(r => r.ApKind == ApKind.Cq);
            attempts += stats.Attempts;
        }
        output.WriteLine($"noise only, {cycles} cycles: attempts {attempts}, cq decodes {cqTagged}");
        attempts.Should().BeGreaterThan(cycles, "the CQ attempt was exercised on many failed candidates");
        cqTagged.Should().Be(0);
    }
}
