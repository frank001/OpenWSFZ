using FluentAssertions;
using OpenWSFZ.Ft8.Interop;
using OpenWSFZ.Ft8.Subfeas;
using Xunit;
using Xunit.Abstractions;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// DR-2 step 2c (FR-108), the subtract-and-retry loop inside <c>ftz_decode_cycle</c>, against the REAL native library: a masked signal found in round 1
/// (test 1), the same payload as classic's residual pass (test 2), the patch window (test 3), the accept rules (test 4), the stop rules (test 5),
/// order and determinism (test 6) and the budget (test 7). The ASan/UBSan fuzz of the loop is <c>native/ftz_decoder/tests/ftz_fuzz.c</c> (CI job
/// <c>native-asan</c>). Synthetic Q-prefix content only (NFR-021). The masked-signal fixture is a strong CQ and a much weaker message 125 ms later, 0 Hz
/// apart, in seeded noise; the margins were measured over seeds and amplitudes (the weak signal is missed by round 0 and found by round 1 from 0.030 up
/// to 0.050 against 0.100). No delay anywhere (TESTING_STRATEGY section 11).
/// </summary>
[Trait("Category", "RequiresNativeBinary")]
public sealed class LeanEngineRoundsTests(ITestOutputHelper output) : IDisposable
{
    private const int PcmSamples = 180_000;
    private const string StrongMessage = "CQ Q1ABC JO22";
    private const string WeakMessage = "Q2DEF Q3GHI -07";
    private const float StrongAmp = 0.10f;
    internal const float WeakAmp = 0.04f;
    private const double CarrierHz = 1500.0;
    private const int StrongStart = 6_000;
    private const int WeakStart = 7_500;
    private const double NoiseSigma = 0.02;
    private const int NoiseSeed = 7;
    private const float PcmTargetRms = 0.20f;

    public void Dispose()
    {
        Ft8LibInterop.SetDecodeParams(10, 0.10f, 60);
        Ft8LibInterop.SetCqApEnabled(false);
        Ft8LibInterop.LeanShutdown();
    }

    // ── fixtures and helpers ─────────────────────────────────────────────────────────────────────────────────────

    internal static float[] Synth(float weakAmp, int seed = NoiseSeed, double weakHz = CarrierHz)
    {
        var t1 = new byte[79]; Ft8LibInterop.EncodeMessage(StrongMessage, t1);
        var a = TestFt8Encoder.SymbolsToPcm(t1.Select(t => (int)t).ToArray(), CarrierHz, StrongStart, StrongAmp);
        float[]? b = null;
        if (weakAmp > 0f)
        {
            var t2 = new byte[79]; Ft8LibInterop.EncodeMessage(WeakMessage, t2);
            b = TestFt8Encoder.SymbolsToPcm(t2.Select(t => (int)t).ToArray(), weakHz, WeakStart, weakAmp);
        }
        var rng = new Random(seed);
        var pcm = new float[PcmSamples];
        for (int i = 0; i < PcmSamples; i++)
        {
            double u1 = 1.0 - rng.NextDouble(), u2 = 1.0 - rng.NextDouble();
            pcm[i] = a[i] + (b is null ? 0f : b[i]) + (float)(NoiseSigma * Math.Sqrt(-2.0 * Math.Log(u1)) * Math.Cos(2.0 * Math.PI * u2));
        }
        return Ft8Decoder.NormalisePcm(pcm, PcmTargetRms);
    }

    private static LeanCycleOutcome Lean(float[] pcm, int threads = 2, bool rounds = true, int maxRounds = 0, int expireRound = 0, int? budgetMs = null,
        bool ungated = false, bool rescand = false)
        => Ft8LibInterop.DecodeLeanCycle(pcm, new LeanCycleParams(threads, false, budgetMs, 0, rounds, maxRounds, ungated, rescand, expireRound));

    private static byte[] SaveHashState()
    {
        var image = new byte[Ft8LibInterop.HashStateSize()];
        Ft8LibInterop.HashStateSave(image);
        return image;
    }

    private static bool Has(LeanCycleOutcome o, string message) => o.Results.Any(r => r.Message.TrimEnd() == message);

    private static string Serialise(LeanCycleOutcome o)
        => string.Join("\n", o.Results.Select((r, i) => $"{r.FreqHz}|{BitConverter.SingleToInt32Bits(r.Dt):X8}|{r.Snr}|{r.Message}|{o.Tiers[i]}|{o.Rounds[i]}"));

    private static bool[] Payload77(string message)
    {
        var tones = new byte[79];
        Ft8LibInterop.EncodeMessage(message, tones);
        return SubfeasPayload.ExtractPayload77(tones);
    }

    // ── test 1: round 1 finds a masked signal ────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-108: DR-2 2c test 1: a signal masked by a strong one is missed by round 0 and found by round 1 once the strong one is subtracted; with the loop off only the strong one is published")]
    public void Round1_FindsTheMaskedSignal()
    {
        float[] pcm = Synth(WeakAmp);
        byte[] start = SaveHashState();

        var off = Lean(pcm, rounds: false);
        Ft8LibInterop.HashStateRestore(start);
        var on = Lean(pcm);
        Ft8LibInterop.HashStateRestore(start);

        Has(off, StrongMessage).Should().BeTrue("the fixture's strong signal must decode in round 0");
        Has(off, WeakMessage).Should().BeFalse("precondition: the weak signal is masked in round 0 (a fixture that does not mask proves nothing)");
        off.Stats.RoundsRun.Should().Be(0, "with the loop off the call is the step-2b call");
        off.Rounds.Should().OnlyContain(r => r == 0);

        on.Stats.Error.Should().Be(LeanCycleStats.Ok);
        Has(on, StrongMessage).Should().BeTrue();
        Has(on, WeakMessage).Should().BeTrue("round 1 finds the masked signal");
        int weakAt = Array.FindIndex(on.Results, r => r.Message.TrimEnd() == WeakMessage);
        on.Rounds[weakAt].Should().Be(1);
        on.Rounds[Array.FindIndex(on.Results, r => r.Message.TrimEnd() == StrongMessage)].Should().Be(0);
        on.Stats.RoundsRun.Should().BeGreaterThanOrEqualTo(1);
        on.Stats.Rounds[1].Fits.Should().Be(1, "one re-encodable result to subtract");
        on.Stats.Rounds[1].Subtracted.Should().Be(1);
        on.Stats.Rounds[1].FitNone.Should().Be(0);
        on.Stats.Rounds[1].Results.Should().Be(1);
        on.Stats.Rounds[1].FitCpuUs.Should().BeGreaterThan(0, "the fit CPU is reported on its own");
        on.Stats.Rounds[1].SearchCpuUs.Should().BeGreaterThanOrEqualTo(0);
        on.Stats.Results.Should().Be(on.Results.Length);
        output.WriteLine($"S3 split (this fixture, CPU ms): fit={on.Stats.S3FitCpuUs / 1000.0:F1} search={on.Stats.S3SearchCpuUs / 1000.0:F1} decode={on.Stats.S3DecodeCpuUs / 1000.0:F1} other={on.Stats.S3OtherCpuUs / 1000.0:F1} rounds={on.Stats.RoundsRun}");
    }

    // ── test 2: equivalence with classic's residual pass ─────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-108: DR-2 2c test 2: round 1 finds the payload classic's residual pass finds on the same fixture")]
    public async Task Round1_FindsTheSamePayloadAsClassicsResidualPass()
    {
        float[] pcm = Synth(WeakAmp);
        byte[] start = SaveHashState();

        // classic: the ordinary decode (OSD refused, CQ-AP off), then the residual pass on the same buffer
        Ft8LibInterop.SetDecodeParams(10, 0.10f, -1);
        Ft8LibInterop.SetCqApEnabled(false);
        var pass0 = Ft8LibInterop.DecodeAll(pcm);
        var residual = await SubtractionPass.RunAsync(new Ft8NativeInteropAdapter(), pcm, pass0, 2, null);
        Ft8LibInterop.HashStateRestore(start);

        var lean = Lean(pcm);
        Ft8LibInterop.HashStateRestore(start);

        residual.Should().NotBeEmpty("precondition: classic's residual pass finds the masked message on this fixture");
        var classicPayloads = residual.Select(r => string.Concat(Payload77(r.Message.TrimEnd()).Select(b => b ? '1' : '0'))).ToHashSet();
        var leanRound1 = lean.Results.Where((_, i) => lean.Rounds[i] == 1).Select(r => string.Concat(Payload77(r.Message.TrimEnd()).Select(b => b ? '1' : '0'))).ToHashSet();
        leanRound1.Should().BeEquivalentTo(classicPayloads, "the same payload set, compared as payloads and never as rendered text");
    }

    // ── test 3: the patch window ─────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-108: DR-2 2c test 3: the patch rule keeps a base frequency in [f - 50, f + 100] Hz of a signal subtracted in the round, and only those")]
    public void PatchWindow_IsMinus50ToPlus100()
    {
        float[] subs = [1000f, 2000f];
        Ft8LibInterop.LeanPatchKeep(1000f, subs).Should().BeTrue();
        Ft8LibInterop.LeanPatchKeep(950f, subs).Should().BeTrue("50 Hz below is inside");
        Ft8LibInterop.LeanPatchKeep(949.9f, subs).Should().BeFalse();
        Ft8LibInterop.LeanPatchKeep(1100f, subs).Should().BeTrue("100 Hz above is inside");
        Ft8LibInterop.LeanPatchKeep(1100.1f, subs).Should().BeFalse();
        Ft8LibInterop.LeanPatchKeep(1500f, subs).Should().BeFalse("between the two windows");
        Ft8LibInterop.LeanPatchKeep(2100f, subs).Should().BeTrue("the second signal has its own window");
        Ft8LibInterop.LeanPatchKeep(1000f, []).Should().BeFalse("nothing subtracted, nothing attempted");
    }

    [Fact(DisplayName = "FR-108: DR-2 2c test 3: end to end, the residual search finds many candidates and only those near the subtracted signal are attempted")]
    public void PatchWindow_EndToEnd_ThroughTheStats()
    {
        byte[] start = SaveHashState();
        var on = Lean(Synth(WeakAmp));
        Ft8LibInterop.HashStateRestore(start);

        var r1 = on.Stats.Rounds[1];
        r1.Found.Should().BeGreaterThan(r1.Kept, "the residual spectrogram has candidates outside the patch (noise); they are not attempted");
        r1.Kept.Should().BeGreaterThanOrEqualTo(1, "the weak signal sits inside the strong one's patch");
        r1.Kept.Should().BeLessThanOrEqualTo(r1.Found);
    }

    // ── test 4: the accept rules ─────────────────────────────────────────────────────────────────────────────────

    private static byte[] StdPayload(uint call1, uint call2, bool ir, uint igrid4, uint i3)
    {
        var p = new byte[10];
        void Put(int lo, int bits, uint v) { for (int i = 0; i < bits; i++) if (((v >> (bits - 1 - i)) & 1u) != 0) p[(lo + i) >> 3] |= (byte)(0x80 >> ((lo + i) & 7)); }
        Put(0, 29, call1); Put(29, 29, call2); Put(58, 1, ir ? 1u : 0u); Put(59, 15, igrid4); Put(74, 3, i3);
        return p;
    }

    [Fact(DisplayName = "FR-108: DR-2 2c test 4a: a payload already known is the same QSO, also in the RR73-aware case (standard sentinel known, on-air sentinel found)")]
    public void AcceptRule_PayloadKnown_IncludingTheRr73AwareCase()
    {
        var known = StdPayload(0x12345, 0x6789A, false, 5000, 1);
        Ft8LibInterop.LeanPayloadSameQso(known, (byte[])known.Clone()).Should().BeTrue("bit-identical");
        var other = StdPayload(0x12345, 0x6789A, false, 5001, 1);
        Ft8LibInterop.LeanPayloadSameQso(known, other).Should().BeFalse("a different report is a different message");

        var rr73Std = StdPayload(0x12345, 0x6789A, false, 32403, 1);
        var rr73Air = StdPayload(0x12345, 0x6789A, false, 32373, 1);
        var rr73OtherCalls = StdPayload(0x12345, 0x6789B, false, 32373, 1);
        Ft8LibInterop.LeanPayloadSameQso(rr73Std, rr73Air).Should().BeTrue("the standard RR73 already known covers the on-air one with the same two calls");
        Ft8LibInterop.LeanPayloadSameQso(rr73Std, rr73OtherCalls).Should().BeFalse();
        Ft8LibInterop.LeanPayloadSameQso(rr73Air, rr73Std).Should().BeFalse("the rule is one-way, as classic's");

        // and the C# rule it mirrors agrees on the same bit patterns
        bool[] Bits(byte[] b) => Enumerable.Range(0, 77).Select(i => ((b[i >> 3] >> (7 - (i & 7))) & 1) != 0).ToArray();
        SubfeasPayload.SameQso(Bits(rr73Std), Bits(rr73Air)).Should().BeTrue();
        SubfeasPayload.SameQso(Bits(rr73Air), Bits(rr73Std)).Should().BeFalse();
    }

    [Fact(DisplayName = "FR-108: DR-2 2c test 4b: end to end, no text and no payload is published twice in a cycle, however many rounds run")]
    public void AcceptRule_NothingIsPublishedTwice_AcrossRounds()
    {
        byte[] start = SaveHashState();
        var on = Lean(Synth(WeakAmp));
        Ft8LibInterop.HashStateRestore(start);

        on.Results.Select(r => r.Message.TrimEnd()).Should().OnlyHaveUniqueItems("a text published earlier in the cycle is not published again");
        on.Results.Select(r => string.Concat(Payload77(r.Message.TrimEnd()).Select(b => b ? '1' : '0'))).Should().OnlyHaveUniqueItems();
    }

    [Fact(DisplayName = "FR-108: DR-2 2c test 4c: a residual tier-B row with F1b above T1 is published iff the ungating is on, and is counted as ungated")]
    public void AcceptRule_UngatedRows()
    {
        Ft8LibInterop.LeanResidualBAccept(false, 1500, ungatedOn: false, rescandOn: false, out bool u0).Should().BeFalse();
        u0.Should().BeFalse();
        Ft8LibInterop.LeanResidualBAccept(false, 1500, ungatedOn: true, rescandOn: false, out bool u1).Should().BeTrue();
        u1.Should().BeTrue("published only because of the ungating");
        Ft8LibInterop.LeanResidualBAccept(true, 1500, ungatedOn: true, rescandOn: false, out bool u2).Should().BeTrue();
        u2.Should().BeFalse("an F1b-passed row is not an ungated row");
    }

    [Fact(DisplayName = "FR-108: DR-2 2e D4: the residual-candidates flag no longer restricts a residual tier-B row: an F1b-failed row is published as ungated at any frequency when the ungating is on, an F1b-passed row always, and with the ungating off a failed row is dropped whatever the flag says")]
    public void AcceptRule_ResidualCandidatesFlag_HasNoEffect()
    {
        foreach (bool rescand in new[] { false, true })
        {
            foreach (int hz in new[] { 500, 1097, 1098, 2400 })
            {
                Ft8LibInterop.LeanResidualBAccept(true, hz, true, rescand, out bool passedUngated).Should().BeTrue($"an F1b-passed row at {hz} Hz, rescand {rescand}");
                passedUngated.Should().BeFalse("an F1b-passed row is not an ungated row");
                Ft8LibInterop.LeanResidualBAccept(false, hz, true, rescand, out bool failedUngated).Should().BeTrue($"an F1b-failed row at {hz} Hz is published with the ungating on, rescand {rescand}");
                failedUngated.Should().BeTrue("and counted as ungated");
                Ft8LibInterop.LeanResidualBAccept(false, hz, false, rescand, out _).Should().BeFalse($"with the ungating off an F1b-failed row at {hz} Hz is dropped, rescand {rescand}");
            }
        }
    }

    // ── test 5: stop rules ───────────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-108: DR-2 2c test 5: a cycle with nothing more to find stops after round 1, and the round cap is honoured")]
    public void StopRules()
    {
        byte[] start = SaveHashState();
        var nothing = Lean(Synth(0f));
        Ft8LibInterop.HashStateRestore(start);
        nothing.Stats.RoundsRun.Should().Be(1, "round 1 subtracts the one signal, finds nothing new and stops");
        nothing.Results.Should().ContainSingle();

        var capped = Lean(Synth(WeakAmp), maxRounds: 1);
        Ft8LibInterop.HashStateRestore(start);
        capped.Stats.RoundsRun.Should().Be(1, "capped at one round");
        Has(capped, WeakMessage).Should().BeTrue();

        var uncapped = Lean(Synth(WeakAmp));
        Ft8LibInterop.HashStateRestore(start);
        uncapped.Stats.RoundsRun.Should().BeInRange(1, 3, "never beyond round 3");
    }

    // ── test 6: order and determinism ────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-108: DR-2 2c test 6: the same audio and starting hash state give byte-identical results, tiers and rounds, twice and at 1, 2 and 4 threads")]
    public void Deterministic_AcrossRunsAndThreadCounts()
    {
        float[] pcm = Synth(WeakAmp);
        byte[] start = SaveHashState();
        var runs = new List<string>();
        foreach (int threads in new[] { 1, 2, 4, 8, 16, 2, 1 })
        {
            Ft8LibInterop.HashStateRestore(start);
            var o = Lean(pcm, threads);
            o.Stats.Error.Should().Be(LeanCycleStats.Ok);
            runs.Add(Serialise(o));
        }
        Ft8LibInterop.HashStateRestore(start);
        runs[0].Should().Contain(WeakMessage, "the loop must have contributed for this test to cover it");
        runs.Distinct().Should().ContainSingle("byte-identical at every thread count");
    }

    // ── test 7: budget ───────────────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-108: DR-2 2c test 7: a budget that is gone at round 2 returns rounds 0 and 1 only, flagged abandoned; a round-1 budget returns round 0 only; a zero budget starts no round")]
    public void Budget_IsAllOrNothingPerRound()
    {
        float[] pcm = Synth(WeakAmp);
        byte[] start = SaveHashState();

        var at2 = Lean(pcm, expireRound: 2);
        Ft8LibInterop.HashStateRestore(start);
        at2.Stats.Abandoned.Should().BeTrue();
        Has(at2, WeakMessage).Should().BeTrue("round 1 stands");
        at2.Rounds.Should().OnlyContain(r => r <= 1);

        var at1 = Lean(pcm, expireRound: 1);
        Ft8LibInterop.HashStateRestore(start);
        at1.Stats.Abandoned.Should().BeTrue();
        Has(at1, StrongMessage).Should().BeTrue("round 0 stands");
        Has(at1, WeakMessage).Should().BeFalse("round 1 publishes nothing when the budget stops it");
        at1.Rounds.Should().OnlyContain(r => r == 0);

        var zero = Lean(pcm, budgetMs: 0);
        Ft8LibInterop.HashStateRestore(start);
        zero.Stats.Error.Should().Be(LeanCycleStats.Ok);
        zero.Stats.RoundsRun.Should().Be(0, "no round starts with less than the reserve left");
        zero.Rounds.Should().OnlyContain(r => r == 0);
        zero.Stats.Abandoned.Should().BeTrue();
    }
}
