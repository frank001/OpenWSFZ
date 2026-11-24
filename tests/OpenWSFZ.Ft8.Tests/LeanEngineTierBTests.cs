using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Ft8.Interop;
using Xunit;
using Xunit.Abstractions;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// DR-2 step 2b (FR-108), tier B (the coherent fallback inside <c>ftz_decode_cycle</c>) and CQ-AP, against the REAL native library: equality with the
/// classic fallback's first run on the original audio (test 1), the publish gate (test 2), CQ-AP (test 3), order and determinism (test 4) and the
/// budget (test 5). Synthetic Q-prefix content only (NFR-021). Seeded noise; every assertion that depends on what the ordinary decode finds is
/// conditional on it, so a different last bit on another platform cannot flip a test (TESTING_STRATEGY section 11). No delay anywhere.
/// </summary>
[Trait("Category", "RequiresNativeBinary")]
public sealed class LeanEngineTierBTests(ITestOutputHelper output) : IDisposable
{
    private const int PcmSamples = 180_000;
    private const double WeakNoiseSigma = 3.5;                 // the Stage 2 fixture: below the ordinary decode, inside the fallback's reach
    private static readonly int[] WeakSeeds = [1, 3, 4];
    private const string WeakMessage = "CQ Q1ABC FN20";
    private const string CqMessage = "CQ Q1ABC JO22";
    private const double CqBaseHz = 1500.0;
    private const int CqStartSample = 6_000;
    private const float CqSignalAmp = 0.1f;
    private const float PcmTargetRms = 0.20f;

    public void Dispose()
    {
        Ft8LibInterop.SetDecodeParams(10, 0.10f, 60);
        Ft8LibInterop.SetCqApEnabled(false);
        Ft8LibInterop.LeanShutdown();
    }

    // ── fixtures ─────────────────────────────────────────────────────────────────────────────────────────────────

    /// <summary>The Stage 2 fixture (<c>CoherentFallbackStage2NativeTests.Synthesise</c>): a weak message in seeded Gaussian noise.</summary>
    private static float[] SynthesiseWeak(string message, double freqHz, double startS, double noiseSigma, int seed)
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

    /// <summary>The CQ-AP fixture (<c>CqApNativeTests.Synthesise</c>): a CQ at <paramref name="snrDb"/> (2500 Hz bandwidth) in seeded white noise, RMS-normalised like the decoder does.</summary>
    private static float[] SynthesiseCq(double snrDb, int seed)
    {
        var tones = new byte[Ft8LibInterop.EncodedToneCount];
        Ft8LibInterop.EncodeMessage(CqMessage, tones);
        var pcm = TestFt8Encoder.SymbolsToPcm(tones.Select(t => (int)t).ToArray(), CqBaseHz, CqStartSample, CqSignalAmp);
        double sigma = Math.Sqrt((CqSignalAmp * CqSignalAmp / 2.0) / Math.Pow(10.0, snrDb / 10.0) * (6000.0 / 2500.0));
        var rng = new Random(seed);
        for (int i = 0; i < PcmSamples; i++)
        {
            double u1 = 1.0 - rng.NextDouble(), u2 = 1.0 - rng.NextDouble();
            pcm[i] += (float)(sigma * Math.Sqrt(-2.0 * Math.Log(u1)) * Math.Cos(2.0 * Math.PI * u2));
        }
        return Ft8Decoder.NormalisePcm(pcm, PcmTargetRms);
    }

    private static LeanCycleOutcome Lean(float[] pcm, int threads, bool cqAp = false, int? budgetMs = null, int maxCandidates = 0)
        => Ft8LibInterop.DecodeLeanCycle(pcm, new LeanCycleParams(threads, cqAp, budgetMs, maxCandidates));

    private static byte[] SaveHashState()
    {
        var image = new byte[Ft8LibInterop.HashStateSize()];
        Ft8LibInterop.HashStateSave(image);
        return image;
    }

    private static string Serialise(LeanCycleOutcome o)
        => string.Join("\n", o.Results.Select((r, i) => $"{r.FreqHz}|{BitConverter.SingleToInt32Bits(r.Dt):X8}|{r.Snr}|{r.Message}|{r.ApKind}|{(i < o.Tiers.Length ? o.Tiers[i] : 0)}"));

    private static HashSet<string> Texts(IEnumerable<Ft8NativeResult> results)
        => results.Select(r => r.Message.TrimEnd()).ToHashSet(StringComparer.Ordinal);

    private static bool Has(IEnumerable<Ft8NativeResult> results, string message) => results.Any(r => r.Message.TrimEnd() == message);

    /// <summary>A CQ whose carrier drifts linearly by <paramref name="driftHz"/> over the message (a real transmitter's thermal drift), at <paramref name="snrDb"/> in seeded noise.</summary>
    private static float[] SynthesiseDrifting(double snrDb, int seed, double driftHz)
    {
        var tones = new byte[Ft8LibInterop.EncodedToneCount];
        Ft8LibInterop.EncodeMessage(CqMessage, tones);
        var pcm = new float[PcmSamples];
        double phase = 0.0, total = tones.Length * 1920.0;
        for (int sym = 0; sym < tones.Length; sym++)
            for (int i = 0; i < 1920; i++)
            {
                long idx = CqStartSample + (long)sym * 1920 + i;
                double f = CqBaseHz + 6.25 * tones[sym] + driftHz * ((sym * 1920.0 + i) / total);
                phase += 2.0 * Math.PI * f / 12000.0;
                if (idx < PcmSamples) pcm[idx] += (float)(CqSignalAmp * Math.Sin(phase));
            }
        double sigma = Math.Sqrt((CqSignalAmp * CqSignalAmp / 2.0) / Math.Pow(10.0, snrDb / 10.0) * (6000.0 / 2500.0));
        var rng = new Random(seed);
        for (int i = 0; i < PcmSamples; i++)
        {
            double u1 = 1.0 - rng.NextDouble(), u2 = 1.0 - rng.NextDouble();
            pcm[i] += (float)(sigma * Math.Sqrt(-2.0 * Math.Log(u1)) * Math.Cos(2.0 * Math.PI * u2));
        }
        return Ft8Decoder.NormalisePcm(pcm, PcmTargetRms);
    }

    // ── test 1: tier-B equality with the classic fallback's first run ───────────────────────────────────────────

    [Fact(DisplayName = "FR-108: DR-2 2b test 1: on the Stage 2 weak-signal fixture the lean engine publishes, as tier B, the payload the classic fallback's first run publishes after the primary pass (CQ-AP off)")]
    public void TierB_PublishesWhatTheClassicFallbackPublishes_OnTheOriginalAudio()
    {
        int exercised = 0;
        foreach (int seed in WeakSeeds)
        {
            float[] pcm = SynthesiseWeak(WeakMessage, 1500.0, 0.55, WeakNoiseSigma, seed);
            byte[] start = SaveHashState();

            // classic: the ordinary decode (OSD refused, CQ-AP off), then the fallback's run on the same snapshot, multi-set on, no deadline
            Ft8LibInterop.SetDecodeParams(10, 0.10f, -1);
            Ft8LibInterop.SetCqApEnabled(false);
            var ordinary = Ft8LibInterop.DecodeAll(pcm);
            var snapshot = Ft8LibInterop.CohFallbackSnapshot();
            var run = Ft8LibInterop.CohFallbackRun(pcm, snapshot, budgetMs: -1, multiSet: true, CancellationToken.None);
            var selected = CoherentFallbackSelector.Select(run.Rows);
            var classicFallbackTexts = selected.Select(r => Ft8LibInterop.CohFallbackUnpack(r.Payload)).OfType<string>().ToHashSet(StringComparer.Ordinal);
            Ft8LibInterop.HashStateRestore(start);

            if (Has(ordinary, WeakMessage)) continue;   // the ordinary decode got it on this platform: nothing for the fallback to recover
            exercised++;
            classicFallbackTexts.Should().Contain(WeakMessage, $"seed {seed}: the classic fallback recovers the message the ordinary decode missed");

            var lean = Lean(pcm, threads: 2);
            Ft8LibInterop.HashStateRestore(start);

            lean.Stats.Error.Should().Be(LeanCycleStats.Ok);
            var tierBTexts = lean.Results.Where((_, i) => lean.Tiers[i] == LeanTier.B).Select(r => r.Message.TrimEnd()).ToHashSet(StringComparer.Ordinal);
            output.WriteLine($"seed {seed}: classic fallback published {classicFallbackTexts.Count}, lean tier B published {tierBTexts.Count} (eligible {lean.Stats.TierBEligible}, crc {lean.Stats.TierBCrcValid}, gated {lean.Stats.TierBGated})");
            tierBTexts.Should().Contain(WeakMessage, $"seed {seed}: the lean engine's tier B recovers the same message");
            classicFallbackTexts.Should().BeSubsetOf(Texts(lean.Results), $"seed {seed}: everything the classic first run publishes, the lean engine publishes");
            lean.Stats.TierBPublished.Should().Be(tierBTexts.Count);
            lean.Stats.TierBPublished.Should().BeLessThanOrEqualTo(lean.Stats.TierBGated);
            lean.Results.Where((r, i) => lean.Tiers[i] == LeanTier.B).Should().OnlyContain(r => r.Snr <= 0 && r.Snr >= -30);
        }
        exercised.Should().BeGreaterThan(0, "at least one seeded cycle must have been missed by the ordinary decode, or the test proves nothing");
    }

    // ── test 2: the gate ─────────────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-108: DR-2 2b test 2: a payload tier A decoded is not published again by tier B, no text appears twice, and the stage counts are consistent (published <= gated <= F1b computed <= CRC-valid <= attempted <= eligible)")]
    public void TierB_NeverRepublishes_AndTheCountsAreMonotone()
    {
        var fixtures = new List<float[]>();
        foreach (string f in new[] { "synth-qso-01.wav", "synth-qso-02.wav", "synth-qso-03.wav" }) fixtures.Add(LoadFixtureWav(f));
        foreach (int seed in WeakSeeds) fixtures.Add(SynthesiseWeak(WeakMessage, 1500.0, 0.55, WeakNoiseSigma, seed));

        foreach (float[] pcm in fixtures)
        {
            byte[] start = SaveHashState();
            var lean = Lean(pcm, threads: 2);
            Ft8LibInterop.HashStateRestore(start);

            var texts = lean.Results.Select(r => r.Message.TrimEnd()).ToList();
            texts.Should().OnlyHaveUniqueItems("a text is published once per cycle");
            var s = lean.Stats;
            s.TierBPublished.Should().BeLessThanOrEqualTo(s.TierBGated);
            s.TierBGated.Should().BeLessThanOrEqualTo(s.TierBF1b);
            s.TierBF1b.Should().BeLessThanOrEqualTo(s.TierBCrcValid);
            s.TierBCrcValid.Should().BeLessThanOrEqualTo(s.TierBAttempted);
            s.TierBAttempted.Should().BeLessThanOrEqualTo(s.TierBEligible);
            (s.TierBAttempted + s.TierBSkipped).Should().Be(s.TierBEligible);
            s.TierBEligible.Should().BeLessThanOrEqualTo(s.Candidates - s.TierADecodes, "a candidate tier A decoded is never attempted by tier B");
            s.Results.Should().Be(lean.Results.Length);
            (lean.Results.Count(r => r.ApKind == ApKind.Cq)).Should().Be(0, "CQ-AP is off in this run");
        }
    }

    [Fact(DisplayName = "FR-108: DR-2 2b test 2: F1b gate - every row the classic fallback publishes the lean engine publishes, and any row it marks GatedOut (CRC-valid, new, F1b above T1) it does not, over a sweep of noise levels")]
    public void TierB_DoesNotPublish_WhatTheClassicGateRefuses()
    {
        int gatedOutSeen = 0, crcValidSeen = 0;
        foreach (double sigma in new[] { 3.5, 4.0, 4.5, 5.0 })
        {
            foreach (int seed in new[] { 1, 2, 3, 4, 5, 6 })
            {
                float[] pcm = SynthesiseWeak(WeakMessage, 1500.0, 0.55, sigma, seed);
                byte[] start = SaveHashState();

                Ft8LibInterop.SetDecodeParams(10, 0.10f, -1);
                Ft8LibInterop.SetCqApEnabled(false);
                Ft8LibInterop.DecodeAll(pcm);
                var run = Ft8LibInterop.CohFallbackRun(pcm, Ft8LibInterop.CohFallbackSnapshot(), budgetMs: -1, multiSet: true, CancellationToken.None);
                var refused = run.Rows.Where(r => r.State == CohFallbackState.GatedOut).Select(r => Ft8LibInterop.CohFallbackUnpack(r.Payload)).OfType<string>().ToHashSet(StringComparer.Ordinal);
                var published = CoherentFallbackSelector.Select(run.Rows).Select(r => Ft8LibInterop.CohFallbackUnpack(r.Payload)).OfType<string>().ToHashSet(StringComparer.Ordinal);
                Ft8LibInterop.HashStateRestore(start);

                var lean = Lean(pcm, threads: 2);
                Ft8LibInterop.HashStateRestore(start);

                crcValidSeen += lean.Stats.TierBCrcValid;
                gatedOutSeen += refused.Count;
                foreach (string text in refused.Except(published))
                    Has(lean.Results, text).Should().BeFalse($"sigma {sigma} seed {seed}: a row the classic gate refuses (F1b above T1) is not published by the lean engine");
                lean.Stats.TierBF1b.Should().BeGreaterThanOrEqualTo(lean.Stats.TierBGated);
            }
        }
        output.WriteLine($"sweep: classic GatedOut payloads seen {gatedOutSeen}, lean CRC-valid tier-B outputs {crcValidSeen}");
        crcValidSeen.Should().BeGreaterThan(0, "the sweep must produce CRC-valid tier-B outputs, or the gate is not exercised");
        // gatedOutSeen is 0 on every noise level and interferer layout tried (2.5 to 6.0 sigma, eight interferer layouts): the rejecting side of the F1b gate
        // is the same single comparison as the classic one and could not be reached with synthetic audio; the report says so.
    }

    [Fact(DisplayName = "FR-108: DR-2 2b test 2: one payload found at two lattice positions is published ONCE, from the first row whose estimate is not on a window edge")]
    public void SamePayloadAtTwoPositions_IsPublishedOnce_FromTheFirstNonEdgeRow()
    {
        int multi = 0, withEdgeRow = 0;
        foreach (double sigma in new[] { 3.0, 3.25, 3.5 })
        {
            for (int seed = 1; seed <= 60; seed++)
            {
                float[] pcm = SynthesiseWeak(WeakMessage, 1500.0, 0.55, sigma, seed);
                byte[] start = SaveHashState();
                var lean = Lean(pcm, threads: 2);
                Ft8LibInterop.HashStateRestore(start);

                if (lean.Stats.TierBGated < 2) continue;         // one position only: nothing to select between
                multi++;
                if (lean.Stats.TierBEdge > 0) withEdgeRow++;
                lean.Stats.TierBPublished.Should().Be(1, $"sigma {sigma} seed {seed}: two gated rows, one payload, one published row");
                var rows = lean.Results.Where((r, i) => lean.Tiers[i] == LeanTier.B).ToList();
                rows.Should().ContainSingle();
                rows[0].Message.TrimEnd().Should().Be(WeakMessage);
                // The signal is at 1500 Hz; an estimate on the window's frequency edge sits 2.0 Hz away, so a published row within 1 Hz is an interior one.
                rows[0].FreqHz.Should().BeInRange(1499, 1501, $"sigma {sigma} seed {seed}: the published row is not the edge row");
            }
        }
        output.WriteLine($"cycles with two gated rows: {multi}, of which with an edge row: {withEdgeRow}");
        multi.Should().BeGreaterThan(0, "the sweep must produce a payload at two positions, or the selection is not exercised");
        withEdgeRow.Should().BeGreaterThan(0, "and one of them must have an edge row, or the edge rule is not exercised");
    }

    // ── test 3: CQ-AP ────────────────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-108: DR-2 2b test 3: on a CQ whose carrier drifts (tier B cannot integrate it, CQ-AP can) the lean engine decodes more with cqAp on than off, every extra one tagged CQ-AP, and the counts follow")]
    public void CqAp_AddsDecodes_AndTagsThem()
    {
        int off = 0, on = 0, extra = 0, attempts = 0, tierBAlsoGotIt = 0;
        foreach (var (snr, drift) in new[] { (-20.0, 6.0), (-20.0, 4.0), (-18.0, 8.0), (-20.0, 0.0) })
        {
            int offAt = 0, onAt = 0, extraAt = 0;
            for (int seed = 1000; seed < 1040; seed++)
            {
                float[] pcm = SynthesiseDrifting(snr, seed, drift);
                byte[] start = SaveHashState();
                var r0 = Lean(pcm, threads: 2, cqAp: false);
                Ft8LibInterop.HashStateRestore(start);
                var r1 = Lean(pcm, threads: 2, cqAp: true);
                Ft8LibInterop.HashStateRestore(start);

                r0.Stats.CqApAttempts.Should().Be(0, "with cqAp off the attempt never runs");
                r0.Stats.CqApDecodes.Should().Be(0);
                r0.Results.All(r => r.ApKind == ApKind.None).Should().BeTrue();
                bool offGot = Has(r0.Results, CqMessage), onGot = Has(r1.Results, CqMessage);
                if (offGot) offAt++;
                if (onGot) onAt++;
                attempts += r1.Stats.CqApAttempts;
                if (offGot) onGot.Should().BeTrue($"{snr} dB drift {drift} Hz seed {seed}: the CQ attempt only adds, a decode with cqAp off is made with it on too");
                if (!offGot && onGot)
                {
                    extraAt++;
                    int at = Array.FindIndex(r1.Results, r => r.Message.TrimEnd() == CqMessage);
                    r1.Results[at].ApKind.Should().Be(ApKind.Cq, $"{snr} dB drift {drift} Hz seed {seed}: a decode only the CQ attempt made is tagged CQ-AP");
                    r1.Tiers[at].Should().Be(LeanTier.CqAp);
                    r1.Stats.CqApDecodes.Should().BeGreaterThan(0);
                }
                if (onGot && r1.Tiers[Array.FindIndex(r1.Results, r => r.Message.TrimEnd() == CqMessage)] == LeanTier.B) tierBAlsoGotIt++;
                r1.Stats.CqApDecodes.Should().Be(r1.Results.Count(r => r.ApKind == ApKind.Cq), "the counter counts the rows published, as the classic counter does");
                r1.Results.Where(r => r.ApKind == ApKind.Cq).All(r => r.Message.StartsWith("CQ ")).Should().BeTrue();
            }
            output.WriteLine($"{snr} dB, carrier drift {drift} Hz, 40 cycles: cqAp off {offAt}, on {onAt}, only-CQ-AP {extraAt}");
            off += offAt; on += onAt; extra += extraAt;
        }
        output.WriteLine($"all: off {off}, on {on}, only-CQ-AP {extra}, attempts {attempts}, rows that tier B made first {tierBAlsoGotIt}");
        extra.Should().BeGreaterThan(0, "at least one cycle where cqAp off fails and on decodes");
        on.Should().BeGreaterThan(off);
        attempts.Should().BeGreaterThan(0);
    }

    // ── the order difference of the task's section 3 ──────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-108: DR-2 2b section 3: the lean order (tier A, tier B, CQ-AP) against the classic order (CQ-AP before the fallback): on the drifting-CQ and weak-signal fixtures the lean engine loses nothing the classic path decodes, and the payloads agree")]
    public void LeanOrder_LosesNothingTheClassicOrderDecodes()
    {
        int cycles = 0, classicOnly = 0, leanOnly = 0, same = 0;
        var cases = new List<float[]>();
        for (int seed = 1000; seed < 1030; seed++) { cases.Add(SynthesiseDrifting(-20, seed, 6.0)); cases.Add(SynthesiseDrifting(-18, seed, 8.0)); }
        foreach (int seed in WeakSeeds) cases.Add(SynthesiseWeak(WeakMessage, 1500.0, 0.55, WeakNoiseSigma, seed));
        foreach (float[] pcm in cases)
        {
            byte[] start = SaveHashState();
            Ft8LibInterop.SetDecodeParams(10, 0.10f, -1);          // OSD refused: the lean engine has none
            Ft8LibInterop.SetCqApEnabled(true);
            var ordinary = Ft8LibInterop.DecodeAll(pcm);
            int primary = Ft8LibInterop.GetLastPassCounts(2)[0];
            var snapshot = Ft8LibInterop.CohFallbackSnapshot();
            var run = Ft8LibInterop.CohFallbackRun(pcm, snapshot, budgetMs: -1, multiSet: true, CancellationToken.None);
            var classic = ordinary.Take(primary).Select(r => r.Message.TrimEnd())
                .Concat(CoherentFallbackSelector.Select(run.Rows).Select(r => Ft8LibInterop.CohFallbackUnpack(r.Payload)).OfType<string>())
                .ToHashSet(StringComparer.Ordinal);
            Ft8LibInterop.SetCqApEnabled(false);
            Ft8LibInterop.HashStateRestore(start);

            var lean = Texts(Lean(pcm, threads: 2, cqAp: true).Results);
            Ft8LibInterop.HashStateRestore(start);

            cycles++;
            if (lean.SetEquals(classic)) same++;
            classicOnly += classic.Except(lean).Count();
            leanOnly += lean.Except(classic).Count();
        }
        output.WriteLine($"{cycles} cycles: identical text sets {same}; texts only the classic order decodes {classicOnly}; texts only the lean order decodes {leanOnly}");
        classicOnly.Should().Be(0, "the lean order loses nothing the classic order decodes on these fixtures");
    }

    // ── test 4: order and determinism ────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-108: DR-2 2b test 4: with tier B and CQ-AP on, the same audio and the same hash state give byte-identical output (tiers included) at 1, 2, 4 and 8 threads, twice")]
    public void AllTiers_AreByteIdentical_AcrossThreadCounts()
    {
        var fixtures = new List<float[]>
        {
            SynthesiseWeak(WeakMessage, 1500.0, 0.55, WeakNoiseSigma, 3),
            SynthesiseCq(-20, 1003),
            LoadFixtureWav("synth-qso-01.wav"),
        };
        foreach (float[] pcm in fixtures)
        {
            byte[] start = SaveHashState();
            var outputs = new List<(int Threads, string Text)>();
            foreach (int threads in new[] { 1, 2, 4, 8, 2, 1 })
            {
                Ft8LibInterop.HashStateRestore(start);
                var o = Lean(pcm, threads, cqAp: true);
                o.Stats.Error.Should().Be(LeanCycleStats.Ok);
                outputs.Add((threads, Serialise(o)));
            }
            Ft8LibInterop.HashStateRestore(start);

            outputs[0].Text.Should().NotBeEmpty();
            foreach (var (threads, text) in outputs.Skip(1)) text.Should().Be(outputs[0].Text, $"threads={threads} must equal threads=1");
        }
    }

    // ── test 5: the budget ───────────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-108: DR-2 2b test 5: a budget of 0 ms (or a few) stops tier B and CQ-AP, sets abandoned, loses nothing it had decoded in tier A, and what it returns is a subset of the full run")]
    public void Budget_StopsTierBAndCqAp_AndFlagsIt()
    {
        float[] pcm = SynthesiseWeak(WeakMessage, 1500.0, 0.55, WeakNoiseSigma, 3);
        byte[] start = SaveHashState();

        var full = Lean(pcm, threads: 2, cqAp: true);
        Ft8LibInterop.HashStateRestore(start);
        full.Stats.Abandoned.Should().BeFalse("with no budget nothing is abandoned");
        full.Stats.TierBEligible.Should().BeGreaterThan(0, "the fixture must leave candidates for tier B, or the budget has nothing to stop");

        foreach (int budget in new[] { 0, 1, 3 })
        {
            Ft8LibInterop.HashStateRestore(start);
            var cut = Lean(pcm, threads: 2, cqAp: true, budgetMs: budget);
            Ft8LibInterop.HashStateRestore(start);

            cut.Stats.Error.Should().Be(LeanCycleStats.Ok, $"budget {budget} ms: no crash, no error");
            if (budget == 0)
            {
                cut.Stats.Abandoned.Should().BeTrue();
                cut.Stats.TierBAttempted.Should().Be(0);
                cut.Stats.TierBSkipped.Should().Be(cut.Stats.TierBEligible);
                cut.Results.Where((_, i) => cut.Tiers[i] != LeanTier.A).Should().BeEmpty("nothing past tier A runs with no budget");
            }
            else if (cut.Stats.Abandoned)
            {
                cut.Stats.TierBSkipped.Should().BeGreaterThan(0);
            }
            Texts(cut.Results).Should().BeSubsetOf(Texts(full.Results), $"budget {budget} ms: what a cut run returns, the full run returns");
            (cut.Stats.TierBAttempted + cut.Stats.TierBSkipped).Should().Be(cut.Stats.TierBEligible);
            Texts(full.Results.Where((_, i) => full.Tiers[i] == LeanTier.A)).Should().BeSubsetOf(Texts(cut.Results), "tier A is not budgeted");
        }
    }

    // ── helpers ──────────────────────────────────────────────────────────────────────────────────────────────────

    private static float[] LoadFixtureWav(string wavFileName)
    {
        var asm = System.Reflection.Assembly.GetExecutingAssembly();
        string name = asm.GetManifestResourceNames().Single(n => n.EndsWith(wavFileName, StringComparison.OrdinalIgnoreCase));
        using Stream stream = asm.GetManifestResourceStream(name)!;
        return WavReader.Read(stream);
    }
}
