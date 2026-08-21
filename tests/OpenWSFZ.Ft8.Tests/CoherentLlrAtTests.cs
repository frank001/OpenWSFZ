using System;
using System.IO;
using System.Reflection;
using FluentAssertions;
using OpenWSFZ.Ft8.Interop;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Tests for <see cref="IFt8NativeInterop.CoherentLlrAt"/> —
/// r2-coherent-llr-instrument, Route B2 Phase 1, tasks 2.1/2.2.
/// <para>
/// This diagnostic-only entry point has no production call site (task 2.2 confirmed this
/// by grep — see the change's QA report); these tests exercise only the interop seam
/// (delegation via a fake, and a real-binary smoke test) — accuracy/BER measurement is
/// the Python validation harness's job (the Phase 1 gate, tasks.md §4.3), not these unit
/// tests. Mirrors R1's <c>RefineCandidateTests</c> 2.1a/b/c pattern exactly, per the
/// Developer handoff's own acceptance criteria.
/// </para>
/// </summary>
public sealed class CoherentLlrAtTests
{
    // ── Test double ───────────────────────────────────────────────────────────

    /// <summary>Capturing fake that records the last <see cref="CoherentLlrAt"/> call.</summary>
    private sealed class CapturingInterop : IFt8NativeInterop
    {
        public bool     CoherentLlrAtCalled { get; private set; }
        public float[]? LastPcm             { get; private set; }
        public float    LastFreqHz          { get; private set; }
        public float    LastTimeOffsetS     { get; private set; }
        public float[]  StubLog174          { get; set; } = BuildStubLog174();

        public int MaxDecodePasses => 2;

        public Ft8NativeResult[] DecodeAll(float[] pcm) => [];

        public int[]  GetLastPassCounts(int maxPasses)      => new int[maxPasses];
        public int[]  GetLastCandidateCounts(int maxPasses) => new int[maxPasses];
        public float  GetLastNoiseFloorDb()                  => 0f;
        public int    GetHashTableRejectCount()              => 0;
        public (float[] MeanAbs, float[] PrenormVariance, int[] FailCount) GetLastLlrStats(int maxPasses)
            => (new float[maxPasses], new float[maxPasses], new int[maxPasses]);

        public void SetApBits(byte[] mycallBits, byte[] hiscallBits) { /* no-op */ }
        public void SetDecodeParams(int kMinScorePass2, float osdCorrThreshold, int osdNhardMax) { /* no-op */ }

        public (float DeltaFreqHz, float DeltaTimeS, float SyncScore, int CoarseDtSamp, int FineDtSamp) RefineCandidate(
            float[] pcm, int coarseFreqHz, float coarseTimeOffsetS)
            => (0f, 0f, 0f, 0, 0);

        public float[] CoherentLlrAt(float[] pcm, float freqHz, float timeOffsetS)
        {
            CoherentLlrAtCalled = true;
            LastPcm             = pcm;
            LastFreqHz          = freqHz;
            LastTimeOffsetS     = timeOffsetS;
            return StubLog174;
        }

        private static float[] BuildStubLog174()
        {
            var log174 = new float[174];
            for (int i = 0; i < log174.Length; i++) log174[i] = (i % 2 == 0) ? 3.9f : -3.9f;
            return log174;
        }
    }

    // ── 2.1a — Fake delegation ────────────────────────────────────────────────

    [Fact(DisplayName = "2.1a: IFt8NativeInterop.CoherentLlrAt is callable on a fake implementation without loading the native DLL")]
    public void CoherentLlrAt_FakeImplementation_RecordsArgumentsWithoutNativeDll()
    {
        var interop = new CapturingInterop();
        var pcm     = new float[180_000];

        float[] log174 = interop.CoherentLlrAt(pcm, freqHz: 700f, timeOffsetS: 0.2f);

        interop.CoherentLlrAtCalled.Should().BeTrue(
            "CoherentLlrAt must be forwarded to the underlying implementation");
        interop.LastPcm.Should().BeSameAs(pcm, "the PCM buffer must be passed through unchanged");
        interop.LastFreqHz.Should().Be(700f, "freqHz must be passed through unchanged");
        interop.LastTimeOffsetS.Should().BeApproximately(0.2f, 1e-6f, "timeOffsetS must be passed through unchanged");
        log174.Should().HaveCount(174, "the FT8 LDPC(174,91) codeword length");
        log174.Should().BeEquivalentTo(interop.StubLog174, "the fake's stub value must be returned unchanged");
    }

    // ── 2.1b — Native adapter: Ft8NativeInteropAdapter.CoherentLlrAt (requires native binary) ──

    /// <summary>
    /// Smoke test for the real P/Invoke path. Uses the same committed synthetic fixture
    /// WAV as <see cref="RefineCandidateTests"/> (synth-qso-01: a CQ signal at 700 Hz,
    /// dt=0.2 s — see qa/rr-study/gen_decoder_fixtures.py). Requires the native binary at
    /// the expected location (shim 20260043 or later); skipped on machines where it is
    /// absent (<c>[Trait("Category", "RequiresNativeBinary")]</c>).
    /// <para>
    /// Only checks the interop seam (finite output, correct count, no throw) — NOT
    /// accuracy/BER, which is the Phase 1 gate harness's job, not this unit test's
    /// (this correlator is UNVALIDATED until that gate's own ROW 0c sign test passes —
    /// see coherent_llr.c's own header comment).
    /// </para>
    /// </summary>
    [Fact(DisplayName = "2.1b: Ft8NativeInteropAdapter.CoherentLlrAt returns 174 finite LLRs without throwing")]
    [Trait("Category", "RequiresNativeBinary")]
    public void Ft8NativeInteropAdapter_CoherentLlrAt_ReturnsFiniteResultWithoutThrowing()
    {
        float[] pcm = LoadEmbeddedWav("Fixtures/synth-qso-01.wav");
        var adapter = new Ft8NativeInteropAdapter();

        // Grid position matches the fixture's known injected (freq, dt) for the first
        // (CQ) signal — see _FIXTURES in gen_decoder_fixtures.py. This is the EXISTING,
        // UNREFINED position (design.md D1) -- no RefineCandidate call involved.
        var act = () => adapter.CoherentLlrAt(pcm, freqHz: 700f, timeOffsetS: 0.2f);

        float[] log174 = act.Should().NotThrow(
            "CoherentLlrAt on a valid 180 000-sample PCM buffer at an in-band position must " +
            "complete without error when the native binary (shim 20260043) is present").Subject;

        log174.Should().HaveCount(174, "the FT8 LDPC(174,91) codeword length (FTX_LDPC_N)");
        foreach (float llr in log174)
            float.IsFinite(llr).Should().BeTrue("a diagnostic LLR export must never return NaN/Inf");
    }

    [Fact(DisplayName = "2.1c: Ft8NativeInteropAdapter.CoherentLlrAt throws ArgumentException on a wrong-length PCM buffer")]
    [Trait("Category", "RequiresNativeBinary")]
    public void Ft8NativeInteropAdapter_CoherentLlrAt_WrongLengthPcm_Throws()
    {
        var adapter = new Ft8NativeInteropAdapter();
        var shortPcm = new float[1000];

        var act = () => adapter.CoherentLlrAt(shortPcm, freqHz: 700f, timeOffsetS: 0.2f);

        act.Should().Throw<ArgumentException>(
            "the native shim requires exactly 180 000 samples (15 s x 12 kHz)");
    }

    [Fact(DisplayName = "2.1d: Ft8NativeInteropAdapter.CoherentLlrAt throws InvalidOperationException on an out-of-band frequency")]
    [Trait("Category", "RequiresNativeBinary")]
    public void Ft8NativeInteropAdapter_CoherentLlrAt_OutOfBandFrequency_Throws()
    {
        float[] pcm = LoadEmbeddedWav("Fixtures/synth-qso-01.wav");
        var adapter = new Ft8NativeInteropAdapter();

        // Well outside the [200, 3000) Hz passband -- the native shim rejects this with
        // rc == -3 rather than silently clamping (same discipline ft8_extract_llrs_at
        // already uses for a caller-supplied position with no in-band guarantee).
        var act = () => adapter.CoherentLlrAt(pcm, freqHz: 5000f, timeOffsetS: 0.2f);

        act.Should().Throw<InvalidOperationException>(
            "a frequency outside the valid passband must be rejected (rc == -3), not silently clamped");
    }

    // ── Helpers (mirrors RefineCandidateTests) ───────────────────────────────

    private static float[] LoadEmbeddedWav(string resourceSuffix)
    {
        using Stream stream = OpenEmbeddedResource(resourceSuffix);
        return WavReader.Read(stream);
    }

    private static Stream OpenEmbeddedResource(string resourceSuffix)
    {
        Assembly asm     = typeof(CoherentLlrAtTests).Assembly;
        string   asmName = asm.GetName().Name!;
        string   resourceName = $"{asmName}.{resourceSuffix.Replace('/', '.')}";

        Stream? stream = asm.GetManifestResourceStream(resourceName);
        if (stream is null)
        {
            string[] allNames = asm.GetManifestResourceNames();
            stream = Array.FindAll(allNames, n => n.EndsWith(resourceSuffix.Replace('/', '.'), StringComparison.OrdinalIgnoreCase))
                          .Length > 0
                ? asm.GetManifestResourceStream(
                    Array.Find(allNames, n => n.EndsWith(resourceSuffix.Replace('/', '.'), StringComparison.OrdinalIgnoreCase))!)
                : null;
        }

        return stream
               ?? throw new InvalidOperationException(
                   $"Embedded resource '{resourceName}' not found. " +
                   $"Available: [{string.Join(", ", asm.GetManifestResourceNames())}]");
    }
}
