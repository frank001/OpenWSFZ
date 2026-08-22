using System;
using System.IO;
using System.Linq;
using System.Reflection;
using FluentAssertions;
using OpenWSFZ.Ft8.Interop;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Tests for <see cref="IFt8NativeInterop.GetLastSnrTerms"/> /
/// <see cref="Ft8LibInterop.GetLastSnrTerms"/> — Amendment 2 (corrected by
/// Amendment 3), r2-coherent-llr-instrument, tasks 15.1/15.2.
/// <para>
/// Mirrors the fake-delegation + real-binary-call coverage pattern
/// <c>CoherentLlrAtTests</c> established for the previous diagnostic export
/// this same change added (task 2.1), applied here to the getter this
/// Amendment adds. Placed in its own file (Developer's choice, recorded per
/// HK-022) rather than folded into <c>Ft8LibInteropTests</c>, matching the
/// one-file-per-diagnostic-export convention <c>CoherentLlrAtTests</c> and
/// <c>RefineCandidateTests</c> already established.
/// </para>
/// <para>
/// AC-N2 (identifiability), AC-N3 (count contract), AC-N4 (capacity,
/// including the both-NULL and negative-capacity cases), and AC-N5 (the
/// DT-stratified measurement) are QA's own follow-on acceptance run
/// (<c>tasks.md</c> §17), not this Developer session's job — this smoke
/// test only proves the P/Invoke binding, the fake delegation path, and
/// basic real-binary sanity.
/// </para>
/// </summary>
public sealed class GetLastSnrTermsTests
{
    // ── Test double ──────────────────────────────────────────────────────────

    /// <summary>Minimal fake implementing every <see cref="IFt8NativeInterop"/> member,
    /// mirroring <c>CoherentLlrAtTests.CapturingInterop</c>'s own construction.</summary>
    private sealed class CapturingInterop : IFt8NativeInterop
    {
        public int MaxDecodePasses => 2;

        public Ft8NativeResult[] DecodeAll(float[] pcm) => [];
        public int[] GetLastPassCounts(int maxPasses) => new int[maxPasses];
        public int[] GetLastCandidateCounts(int maxPasses) => new int[maxPasses];
        public float GetLastNoiseFloorDb() => 0f;
        public int GetHashTableRejectCount() => 0;

        public (float[] MeanAbs, float[] PrenormVariance, int[] FailCount) GetLastLlrStats(int maxPasses)
            => (new float[maxPasses], new float[maxPasses], new int[maxPasses]);

        public void SetApBits(byte[] mycallBits, byte[] hiscallBits) { /* no-op */ }
        public void SetDecodeParams(int kMinScorePass2, float osdCorrThreshold, int osdNhardMax) { /* no-op */ }

        public (float DeltaFreqHz, float DeltaTimeS, float SyncScore, int CoarseDtSamp, int FineDtSamp) RefineCandidate(
            float[] pcm, int coarseFreqHz, float coarseTimeOffsetS)
            => (0f, 0f, 0f, 0, 0);

        public float[] CoherentLlrAt(float[] pcm, float freqHz, float timeOffsetS) => new float[174];

        public bool GetLastSnrTermsCalled { get; private set; }
        public int  LastMaxDecoded        { get; private set; }
        public (float[] SignalDb, float[] LocalNoiseDb) StubResult { get; set; } = ([1.1f, 2.2f], [3.3f, 4.4f]);

        public (float[] SignalDb, float[] LocalNoiseDb) GetLastSnrTerms(int maxDecoded)
        {
            GetLastSnrTermsCalled = true;
            LastMaxDecoded        = maxDecoded;
            return StubResult;
        }
    }

    // ── 15.2a — Fake delegation ─────────────────────────────────────────────

    [Fact(DisplayName = "15.2a: IFt8NativeInterop.GetLastSnrTerms is callable on a fake implementation without loading the native DLL")]
    public void GetLastSnrTerms_FakeImplementation_RecordsArgumentsWithoutNativeDll()
    {
        var interop = new CapturingInterop();

        var (signalDb, localNoiseDb) = interop.GetLastSnrTerms(maxDecoded: 340);

        interop.GetLastSnrTermsCalled.Should().BeTrue(
            "GetLastSnrTerms must be forwarded to the underlying implementation");
        interop.LastMaxDecoded.Should().Be(340, "maxDecoded must be passed through unchanged");
        signalDb.Should().Equal(interop.StubResult.SignalDb,
            "the fake's stub SignalDb must be returned unchanged");
        localNoiseDb.Should().Equal(interop.StubResult.LocalNoiseDb,
            "the fake's stub LocalNoiseDb must be returned unchanged");
    }

    // ── 15.2b/c — Native adapter: Ft8LibInterop.GetLastSnrTerms (requires native binary) ──

    /// <summary>
    /// Mirrors <c>Ft8LibInteropTests.GetLastCandidateCounts_AfterDecodeAllOnSilentBuffer_...</c>:
    /// a silent buffer decodes nothing, so the TLS SNR-terms count must be 0.
    /// </summary>
    [Fact(DisplayName = "15.2b: Ft8LibInterop.GetLastSnrTerms returns empty arrays after DecodeAll on a silent PCM buffer")]
    [Trait("Category", "RequiresNativeBinary")]
    public void GetLastSnrTerms_AfterDecodeAllOnSilentBuffer_ReturnsEmptyArrays()
    {
        var pcm = new float[180_000];

        _ = Ft8LibInterop.DecodeAll(pcm);
        var (signalDb, localNoiseDb) = Ft8LibInterop.GetLastSnrTerms(maxDecoded: 340);

        signalDb.Should().BeEmpty("a silent buffer decodes nothing, so no SNR terms are recorded");
        localNoiseDb.Should().BeEmpty("a silent buffer decodes nothing, so no SNR terms are recorded");
    }

    /// <summary>
    /// Mirrors <c>Ft8LibInteropTests.GetLastCandidateCounts_AfterDecodeAllOnRealSignal_...</c>:
    /// on a real-signal fixture, confirms the index-alignment contract (AC-N3's own subject,
    /// though the gating AC-N3 run itself is QA's tasks.md §17.2, not this smoke test) and a
    /// loose sanity bound on the reconstructed SNR (AC-N2's own subject, at a looser tolerance
    /// than AC-N2's ±0.5 dB gate).
    /// </summary>
    [Fact(DisplayName = "15.2c: Ft8LibInterop.GetLastSnrTerms is index-aligned with DecodeAll's own results on a real fixture")]
    [Trait("Category", "RequiresNativeBinary")]
    public void GetLastSnrTerms_AfterDecodeAllOnRealSignal_IndexAlignedWithResults()
    {
        float[] pcm = LoadFixtureWav("synth-qso-01.wav");
        pcm.Should().HaveCount(180_000);

        // AP bits cleared first — same TLS-contamination guard
        // Ft8LibInteropTests.GetLastCandidateCounts_AfterDecodeAllOnRealSignal... uses.
        Ft8LibInterop.SetApBits([], []);
        Ft8NativeResult[] results = Ft8LibInterop.DecodeAll(pcm);
        var (signalDb, localNoiseDb) = Ft8LibInterop.GetLastSnrTerms(maxDecoded: results.Length);

        results.Length.Should().BeGreaterThan(0,
            "the synthetic fixture must decode at least one signal for this test to be meaningful");

        signalDb.Should().HaveCount(results.Length,
            "GetLastSnrTerms must return one entry per DecodeAll result — the whole index-alignment contract");
        localNoiseDb.Should().HaveCount(results.Length,
            "GetLastSnrTerms must return one entry per DecodeAll result — the whole index-alignment contract");

        for (int i = 0; i < results.Length; i++)
        {
            float.IsFinite(signalDb[i]).Should().BeTrue($"signalDb[{i}] must be a finite dB value, never NaN/Inf");
            float.IsFinite(localNoiseDb[i]).Should().BeTrue($"localNoiseDb[{i}] must be a finite dB value, never NaN/Inf");

            float reconstructedSnr = signalDb[i] - localNoiseDb[i] - 26.5f;
            reconstructedSnr.Should().BeApproximately(results[i].Snr, 1.0f,
                $"result[{i}]: signal_db - local_noise_db - 26.5 must be close to the " +
                "reported (rounded) SNR — the whole reason this getter exists");
        }
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    /// <summary>Same embedded-resource loader as <c>Ft8LibInteropTests.LoadFixtureWav</c>.</summary>
    private static float[] LoadFixtureWav(string wavFileName)
    {
        Assembly asm      = Assembly.GetExecutingAssembly();
        string   asmName  = asm.GetName().Name!;
        string   fullName = $"{asmName}.Fixtures.{wavFileName}";

        Stream? stream = asm.GetManifestResourceStream(fullName);
        if (stream is null)
        {
            stream = asm.GetManifestResourceNames()
                .Where(n => n.EndsWith(wavFileName, StringComparison.OrdinalIgnoreCase))
                .Select(n => asm.GetManifestResourceStream(n))
                .FirstOrDefault(s => s is not null);
        }

        if (stream is null)
            throw new InvalidOperationException(
                $"Embedded WAV resource '{fullName}' not found. " +
                $"Available: [{string.Join(", ", asm.GetManifestResourceNames())}]");

        using (stream)
            return WavReader.Read(stream);
    }
}
