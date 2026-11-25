using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using FluentAssertions;
using OpenWSFZ.Ft8.Interop;
using Xunit;
using Xunit.Abstractions;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// DR-2 step 2e (FR-108), against the REAL native library: the exact speedups of the fit (D2: the fast path and the reference path give the same bytes), the fit-skip
/// rule (D3), the residual accept rule (D4) and the two tidies (D5). Synthetic Q-prefix content only (NFR-021). No delay anywhere (TESTING_STRATEGY section 11).
/// </summary>
[Trait("Category", "RequiresNativeBinary")]
public sealed class LeanEngineFitCostTests(ITestOutputHelper output) : IDisposable
{
    private const string StrongMessage = "CQ Q1ABC JO22";
    private const string WeakMessage = "Q2DEF Q3GHI -07";

    public void Dispose()
    {
        Ft8LibInterop.SubfeasSetReferenceMode(false);
        Ft8LibInterop.LeanShutdown();
    }

    private static byte[] SaveHashState()
    {
        var image = new byte[Ft8LibInterop.HashStateSize()];
        Ft8LibInterop.HashStateSave(image);
        return image;
    }

    // ── D2: the fast path is bit-identical to the reference path ────────────────────────────────────────────────

    private static double Gauss(Random rng)
    {
        double u1 = 1.0 - rng.NextDouble(), u2 = rng.NextDouble();
        return Math.Sqrt(-2.0 * Math.Log(u1)) * Math.Cos(2.0 * Math.PI * u2);
    }

    /// <summary>One 8-FSK message with a linear carrier drift at a known place, in seeded Gaussian noise.</summary>
    private static (float[] Pcm, byte[] Tones, float Dt, float FreqHz) Signal(int seed, double freqHz, int startSample, double amp, double sigma, double driftHz, string message)
    {
        var tones = new byte[79];
        Ft8LibInterop.EncodeMessage(message, tones);
        var pcm = new float[180_000];
        double phase = 0.0;
        for (int sym = 0; sym < 79; sym++)
            for (int i = 0; i < 1920; i++)
            {
                long idx = startSample + (long)sym * 1920 + i;
                double f = freqHz + 6.25 * tones[sym] + driftHz * ((sym * 1920.0 + i) / 151_680.0 - 0.5);
                if (idx < pcm.Length) pcm[idx] += (float)(amp * Math.Sin(phase));
                phase += 2.0 * Math.PI * f / 12000.0;
            }
        var rng = new Random(seed);
        for (int i = 0; i < pcm.Length; i++) pcm[i] += (float)(sigma * Gauss(rng));
        // the decoder's published dt convention is (start sample / 12000 - 0.1 s) at most; the fit searches +-100 ms around it, so a small offset is realistic
        return (pcm, tones, (float)(startSample / 12000.0 - 0.1 + ((seed % 7) - 3) * 0.004), (float)Math.Round(freqHz + ((seed % 5) - 2)));
    }

    [Fact(DisplayName = "FR-108: DR-2 2e D2: the fast fit and the reference fit give byte-identical out_shat (and the same return code) on 38 signals: seeded noise at several SNRs, offsets, drifts and frequencies, and the step 2c fixture")]
    public void FastFit_IsBitIdenticalToTheReferenceFit()
    {
        var cases = new List<(float[] Pcm, byte[] Tones, float Dt, float FreqHz, string Label)>();
        for (int n = 0; n < 36; n++)
        {
            double freq = 300.0 + (n * 61) % 2500;
            int start = 1_000 + (n * 997) % 9_000;
            double amp = 0.02 + 0.015 * (n % 7);
            double sigma = 0.01 + 0.012 * (n % 5);
            double drift = ((n % 9) - 4) * 0.08;
            string msg = n % 2 == 0 ? StrongMessage : WeakMessage;
            var s = Signal(100 + n, freq, start, amp, sigma, drift, msg);
            cases.Add((s.Pcm, s.Tones, s.Dt, s.FreqHz, $"seed {100 + n}: {freq:F0} Hz, start {start}, amp {amp:F3}, sigma {sigma:F3}, drift {drift:F2}"));
        }
        // the step 2c fixture (a strong signal and a masked weak one in noise): fit both published positions
        float[] fixture = LeanEngineRoundsTests.Synth(LeanEngineRoundsTests.WeakAmp);
        byte[] start0 = SaveHashState();
        var decoded = Ft8LibInterop.DecodeLeanCycle(fixture, new LeanCycleParams(2, Rounds: true));
        Ft8LibInterop.HashStateRestore(start0);
        decoded.Results.Length.Should().BeGreaterThanOrEqualTo(2, "precondition: the fixture decodes both messages");
        foreach (var r in decoded.Results)
        {
            var tones = new byte[79];
            Ft8LibInterop.EncodeMessage(r.Message.TrimEnd(), tones);
            cases.Add((fixture, tones, r.Dt, r.FreqHz, $"fixture {r.Message.TrimEnd()}"));
        }
        cases.Count.Should().BeGreaterThanOrEqualTo(30);

        Ft8LibInterop.SubfeasPoolConfigure(1);
        int identical = 0, fitted = 0;
        var cpuRef = new System.Diagnostics.Stopwatch();
        var cpuFast = new System.Diagnostics.Stopwatch();
        foreach (var c in cases)
        {
            var (re, im) = Ft8LibInterop.SubfeasComputeAnalytic(c.Pcm);
            Ft8LibInterop.SubfeasSetReferenceMode(true);
            cpuRef.Start();
            var reference = Ft8LibInterop.SubfeasFitSignal(re, im, c.Tones, c.Dt, c.FreqHz);
            cpuRef.Stop();
            Ft8LibInterop.SubfeasSetReferenceMode(false);
            cpuFast.Start();
            var fast = Ft8LibInterop.SubfeasFitSignal(re, im, c.Tones, c.Dt, c.FreqHz);
            cpuFast.Stop();

            fast.ReturnCode.Should().Be(reference.ReturnCode, c.Label);
            MemoryMarshal.AsBytes(fast.Shat.AsSpan()).SequenceEqual(MemoryMarshal.AsBytes(reference.Shat.AsSpan())).Should().BeTrue($"shat is byte-identical: {c.Label}");
            identical++;
            if (reference.ReturnCode == 0) fitted++;
        }
        fitted.Should().BeGreaterThanOrEqualTo(20, "most cases must actually fit, or the comparison is vacuous");
        output.WriteLine($"{identical} of {cases.Count} byte-identical ({fitted} fitted, the rest answered no valid fit); reference {cpuRef.ElapsedMilliseconds / (double)cases.Count:F0} ms, fast {cpuFast.ElapsedMilliseconds / (double)cases.Count:F0} ms per fit (wall)");
    }

    // ── D3: the fit-skip rule ───────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-108: DR-2 2e D3: the fit-skip rule needs a failed candidate in [f - 50, f + 100] Hz of the result: tested at the window edges, with none, one inside and one outside")]
    public void FitNeeded_Rule()
    {
        Ft8LibInterop.LeanFitNeeded(1000f, [1000f]).Should().BeTrue("a failed candidate at the result");
        Ft8LibInterop.LeanFitNeeded(1000f, [950f]).Should().BeTrue("50 Hz below is inside");
        Ft8LibInterop.LeanFitNeeded(1000f, [949.9f]).Should().BeFalse();
        Ft8LibInterop.LeanFitNeeded(1000f, [1100f]).Should().BeTrue("100 Hz above is inside");
        Ft8LibInterop.LeanFitNeeded(1000f, [1100.1f]).Should().BeFalse();
        Ft8LibInterop.LeanFitNeeded(1000f, [400f, 1500f, 1080f]).Should().BeTrue("one inside among others outside");
        Ft8LibInterop.LeanFitNeeded(1000f, [400f, 1500f, 2400f]).Should().BeFalse("all outside");
        Ft8LibInterop.LeanFitNeeded(1000f, []).Should().BeFalse("no failed candidate: nothing may be hiding there");
        Ft8LibInterop.LeanFitNeeded(float.NaN, [1000f]).Should().BeFalse();
    }

    [Fact(DisplayName = "FR-108: DR-2 2e D3 fixture A: a lone signal with no failed candidate near it is not fitted (the fit CPU is zero), and the published set is the same as with the rule off")]
    public void SkipRule_LoneSignal_SkipsTheFit_PublishedSetUnchanged()
    {
        float[] pcm = LeanEngineRoundsTests.Synth(0f);
        byte[] start = SaveHashState();
        // a round-0 candidate list of one: the strong signal itself, so no candidate failed anywhere
        var off = Ft8LibInterop.DecodeLeanCycle(pcm, new LeanCycleParams(2, Rounds: true, MaxCandidates: 1, SkipFits: false));
        Ft8LibInterop.HashStateRestore(start);
        var on = Ft8LibInterop.DecodeLeanCycle(pcm, new LeanCycleParams(2, Rounds: true, MaxCandidates: 1, SkipFits: true));
        Ft8LibInterop.HashStateRestore(start);

        off.Stats.Rounds[1].Fits.Should().Be(1, "the rule off: the one result is fitted");
        on.Stats.Rounds[1].Fits.Should().Be(0);
        on.Stats.Rounds[1].FitSkipped.Should().Be(1, "the rule on: skipped");
        on.Stats.S3FitCpuUs.Should().Be(0, "no fit ran");
        on.Stats.RoundsRun.Should().Be(0);
        on.Results.Select(r => r.Message.TrimEnd()).Should().Equal(off.Results.Select(r => r.Message.TrimEnd()), "the published set is unchanged");
    }

    [Fact(DisplayName = "FR-108: DR-2 2e D3 fixture B: when the masked signal was never a candidate of round 0 the skipped fit WOULD have unmasked it: the rule loses it, the rule off finds it (what is lost, stated)")]
    public void SkipRule_MaskedSignalNeverACandidate_IsLost()
    {
        float[] pcm = LeanEngineRoundsTests.Synth(LeanEngineRoundsTests.WeakAmp);
        byte[] start = SaveHashState();
        var off = Ft8LibInterop.DecodeLeanCycle(pcm, new LeanCycleParams(2, Rounds: true, MaxCandidates: 1, SkipFits: false));
        Ft8LibInterop.HashStateRestore(start);
        var on = Ft8LibInterop.DecodeLeanCycle(pcm, new LeanCycleParams(2, Rounds: true, MaxCandidates: 1, SkipFits: true));
        Ft8LibInterop.HashStateRestore(start);

        off.Results.Select(r => r.Message.TrimEnd()).Should().Contain(WeakMessage, "without the rule the subtraction unmasks the weak signal");
        on.Results.Select(r => r.Message.TrimEnd()).Should().NotContain(WeakMessage, "with the rule the strong signal is not subtracted (no failed candidate near it), so the weak one stays masked: this is what the rule can lose");
        on.Results.Select(r => r.Message.TrimEnd()).Should().Contain(StrongMessage);
        on.Stats.Rounds[1].FitSkipped.Should().Be(1);
    }

    [Fact(DisplayName = "FR-108: DR-2 2e D3: at the default candidate cap the rule skips nothing on the step 2c fixture (its round 0 has failed candidates all over the band), and the output is byte-identical to the rule off")]
    public void SkipRule_DefaultCap_SkipsNothing_OnThisFixture()
    {
        float[] pcm = LeanEngineRoundsTests.Synth(LeanEngineRoundsTests.WeakAmp);
        byte[] start = SaveHashState();
        var off = Ft8LibInterop.DecodeLeanCycle(pcm, new LeanCycleParams(2, Rounds: true, WantResidual: true, SkipFits: false));
        Ft8LibInterop.HashStateRestore(start);
        var on = Ft8LibInterop.DecodeLeanCycle(pcm, new LeanCycleParams(2, Rounds: true, WantResidual: true, SkipFits: true));
        Ft8LibInterop.HashStateRestore(start);

        on.Stats.S3FitSkipped.Should().Be(0, "the rule needs a failed candidate near NO result to skip anything; here there is always one");
        Digest(on).Should().Be(Digest(off));
        output.WriteLine($"round-0 candidates {on.Stats.Rounds[0].Found}, fits skipped {on.Stats.S3FitSkipped}");
    }

    // ── the rule off restores step 2d ───────────────────────────────────────────────────────────────────────────

    /// <summary>SHA-256 over every result (frequency, dt bits, snr, text, tier, round) and the residual bytes: two runs are "byte for byte" the same iff the digests are.</summary>
    internal static string Digest(LeanCycleOutcome o)
    {
        var sb = new StringBuilder();
        for (int i = 0; i < o.Results.Length; i++)
        {
            var r = o.Results[i];
            sb.Append(r.FreqHz).Append('|').Append(BitConverter.SingleToInt32Bits(r.Dt).ToString("X8")).Append('|').Append(r.Snr).Append('|').Append(r.Message.TrimEnd())
              .Append('|').Append(o.Tiers[i]).Append('|').Append(o.Rounds[i]).Append('\n');
        }
        using var sha = SHA256.Create();
        sha.TransformBlock(Encoding.UTF8.GetBytes(sb.ToString()), 0, Encoding.UTF8.GetByteCount(sb.ToString()), null, 0);
        byte[] resid = o.Residual is null ? [] : MemoryMarshal.AsBytes(o.Residual.AsSpan()).ToArray();
        sha.TransformFinalBlock(resid, 0, resid.Length);
        return Convert.ToHexString(sha.Hash!);
    }

    /// <summary>
    /// The digest of the step 2c fixture's lean cycle (results, tiers, rounds and residual bytes) as the step 2d build, commit 6c746029, produced it on Windows x64.
    /// It is recorded on that platform only (a numeric golden holds only where it was recorded: libm differs on arm64 and Linux), so it is asserted there only.
    /// </summary>
    private const string Digest2dWindowsX64 = "B66E5B0683BDBC56C0C7CEB45CD4B94271E2DC6E9FD98DF3598EC49B01CB5E3E";

    [Fact(DisplayName = "FR-108: DR-2 2e D3: with the fit-skip rule off, the results, tiers, rounds and residual bytes of the step 2c fixture equal what step 2d produced (recorded on Windows x64; elsewhere only the in-process comparison with the reference fit is asserted)")]
    public void RuleOff_RestoresStep2d_ByteForByte()
    {
        float[] pcm = LeanEngineRoundsTests.Synth(LeanEngineRoundsTests.WeakAmp);
        byte[] start = SaveHashState();
        var fast = Ft8LibInterop.DecodeLeanCycle(pcm, new LeanCycleParams(2, Rounds: true, WantResidual: true, SkipFits: false));
        Ft8LibInterop.HashStateRestore(start);

        // In process, everywhere: the whole cycle with the reference fit equals the whole cycle with the fast fit.
        Ft8LibInterop.SubfeasSetReferenceMode(true);
        var reference = Ft8LibInterop.DecodeLeanCycle(pcm, new LeanCycleParams(2, Rounds: true, WantResidual: true, SkipFits: false));
        Ft8LibInterop.HashStateRestore(start);
        Ft8LibInterop.SubfeasSetReferenceMode(false);
        Digest(fast).Should().Be(Digest(reference), "the fast fit changes nothing the cycle publishes or returns");

        output.WriteLine($"digest of this build: {Digest(fast)}");
        if (OperatingSystem.IsWindows() && RuntimeInformation.ProcessArchitecture == Architecture.X64)
            Digest(fast).Should().Be(Digest2dWindowsX64, "the same bytes the step 2d build produced");
    }

    // ── D5 (2): a non-fault error after partial chunks exports no half-subtracted residual ──────────────────────

    [Fact(DisplayName = "FR-108: DR-2 2e D5: a non-fault error after the first chunk of a round's fits returns the earlier rounds' results and NO residual buffer (it would be half-subtracted)")]
    public void ErrorAfterFirstChunk_ExportsNoResidual()
    {
        float[] pcm = LeanEngineRoundsTests.Synth(LeanEngineRoundsTests.WeakAmp);
        byte[] start = SaveHashState();
        var ok = Ft8LibInterop.DecodeLeanCycle(pcm, new LeanCycleParams(2, Rounds: true, WantResidual: true));
        Ft8LibInterop.HashStateRestore(start);
        var failed = Ft8LibInterop.DecodeLeanCycle(pcm, new LeanCycleParams(2, Rounds: true, WantResidual: true, InjectErrorRound: 2));
        Ft8LibInterop.HashStateRestore(start);

        ok.Residual.Should().NotBeNull("control: the cycle without the injected error returns a residual");
        failed.Stats.Error.Should().Be(LeanCycleStats.ErrNoMem);
        failed.Results.Select(r => r.Message.TrimEnd()).Should().Contain(StrongMessage).And.Contain(WeakMessage, "rounds 0 and 1 stand");
        failed.Residual.Should().BeNull("the buffer was being subtracted into when the error came: it is not a residual");
    }
}
