using System;
using System.IO;
using System.Reflection;
using FluentAssertions;
using OpenWSFZ.Ft8.Interop;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Tests for <see cref="IFt8NativeInterop.RefineCandidate"/> —
/// r1-sync-refiner-instrument-validation, tasks 2.1/2.2.
/// <para>
/// This diagnostic-only entry point has no production call site (task 2.2 confirmed this
/// by grep — see the change's QA report); these tests exercise only the interop seam
/// (delegation via a fake, and a real-binary smoke test) — accuracy against known truth
/// is the Python validation harness's job (AC-1..AC-6), not these unit tests.
/// </para>
/// </summary>
public sealed class RefineCandidateTests
{
    // ── Test double ───────────────────────────────────────────────────────────

    /// <summary>Capturing fake that records the last <see cref="RefineCandidate"/> call.</summary>
    private sealed class CapturingInterop : IFt8NativeInterop
    {
        public bool    RefineCandidateCalled     { get; private set; }
        public float[]? LastPcm                  { get; private set; }
        public int     LastCoarseFreqHz          { get; private set; }
        public float   LastCoarseTimeOffsetS     { get; private set; }

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

        public (float DeltaFreqHz, float DeltaTimeS, float SyncScore) RefineCandidate(
            float[] pcm, int coarseFreqHz, float coarseTimeOffsetS)
        {
            RefineCandidateCalled = true;
            LastPcm               = pcm;
            LastCoarseFreqHz      = coarseFreqHz;
            LastCoarseTimeOffsetS = coarseTimeOffsetS;
            return (0.1234f, -0.005f, 42.0f);
        }
    }

    // ── 2.1a — Fake delegation ────────────────────────────────────────────────

    [Fact(DisplayName = "2.1a: IFt8NativeInterop.RefineCandidate is callable on a fake implementation without loading the native DLL")]
    public void RefineCandidate_FakeImplementation_RecordsArgumentsWithoutNativeDll()
    {
        var interop = new CapturingInterop();
        var pcm     = new float[180_000];

        var (deltaFreqHz, deltaTimeS, syncScore) = interop.RefineCandidate(pcm, coarseFreqHz: 700, coarseTimeOffsetS: 0.2f);

        interop.RefineCandidateCalled.Should().BeTrue(
            "RefineCandidate must be forwarded to the underlying implementation");
        interop.LastPcm.Should().BeSameAs(pcm, "the PCM buffer must be passed through unchanged");
        interop.LastCoarseFreqHz.Should().Be(700, "coarseFreqHz must be passed through unchanged");
        interop.LastCoarseTimeOffsetS.Should().BeApproximately(0.2f, 1e-6f, "coarseTimeOffsetS must be passed through unchanged");
        deltaFreqHz.Should().BeApproximately(0.1234f, 1e-6f);
        deltaTimeS.Should().BeApproximately(-0.005f, 1e-6f);
        syncScore.Should().BeApproximately(42.0f, 1e-6f);
    }

    // ── 2.1b — Native adapter: Ft8NativeInteropAdapter.RefineCandidate (requires native binary) ──

    /// <summary>
    /// Smoke test for the real P/Invoke path. Uses the same committed synthetic fixture
    /// WAV as <see cref="RealSignalFixtureTests"/> (synth-qso-01: a CQ signal at 700 Hz,
    /// dt=0.2 s — see qa/rr-study/gen_decoder_fixtures.py). Requires the native binary at
    /// the expected location; skipped on machines where it is absent.
    /// </summary>
    [Fact(DisplayName = "2.1b: Ft8NativeInteropAdapter.RefineCandidate returns a refined offset without throwing")]
    [Trait("Category", "RequiresNativeBinary")]
    public void Ft8NativeInteropAdapter_RefineCandidate_ReturnsFiniteResultWithoutThrowing()
    {
        float[] pcm = LoadEmbeddedWav("Fixtures/synth-qso-01.wav");
        var adapter = new Ft8NativeInteropAdapter();

        // Coarse position matches the fixture's known injected (freq, dt) for the first
        // (CQ) signal — see _FIXTURES in gen_decoder_fixtures.py.
        var act = () => adapter.RefineCandidate(pcm, coarseFreqHz: 700, coarseTimeOffsetS: 0.2f);

        var result = act.Should().NotThrow(
            "RefineCandidate on a valid 180 000-sample PCM buffer must complete without error " +
            "when the native binary (shim 20260040) is present").Subject;

        float.IsFinite(result.DeltaFreqHz).Should().BeTrue("a diagnostic refiner must never return NaN/Inf");
        float.IsFinite(result.DeltaTimeS).Should().BeTrue("a diagnostic refiner must never return NaN/Inf");
        float.IsFinite(result.SyncScore).Should().BeTrue("a diagnostic refiner must never return NaN/Inf");
        result.SyncScore.Should().BeGreaterThan(0f, "a genuine signal at the supplied coarse position should score above zero");
    }

    [Fact(DisplayName = "2.1c: Ft8NativeInteropAdapter.RefineCandidate throws ArgumentException on a wrong-length PCM buffer")]
    [Trait("Category", "RequiresNativeBinary")]
    public void Ft8NativeInteropAdapter_RefineCandidate_WrongLengthPcm_Throws()
    {
        var adapter = new Ft8NativeInteropAdapter();
        var shortPcm = new float[1000];

        var act = () => adapter.RefineCandidate(shortPcm, coarseFreqHz: 700, coarseTimeOffsetS: 0.2f);

        act.Should().Throw<ArgumentException>(
            "the native shim requires exactly 180 000 samples (15 s x 12 kHz)");
    }

    // ── Helpers (mirrors RealSignalFixtureTests) ─────────────────────────────

    private static float[] LoadEmbeddedWav(string resourceSuffix)
    {
        using Stream stream = OpenEmbeddedResource(resourceSuffix);
        return WavReader.Read(stream);
    }

    private static Stream OpenEmbeddedResource(string resourceSuffix)
    {
        Assembly asm     = typeof(RefineCandidateTests).Assembly;
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
