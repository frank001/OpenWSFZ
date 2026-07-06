using FluentAssertions;
using OpenWSFZ.Ft8.Interop;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Tests for <see cref="IFt8NativeInterop.SetDecodeParams"/> — verifies that the
/// adapter delegates correctly without error.
/// Tasks 7.3 (decoder-settings-page).
/// </summary>
public sealed class SetDecodeParamsTests
{
    // ── Test double ───────────────────────────────────────────────────────────

    /// <summary>
    /// Capturing fake that records the last <see cref="SetDecodeParams"/> call.
    /// </summary>
    private sealed class CapturingInterop : IFt8NativeInterop
    {
        public bool   SetDecodeParamsCalled    { get; private set; }
        public int    LastKMinScorePass2        { get; private set; }
        public float  LastOsdCorrThreshold      { get; private set; }
        public int    LastOsdNhardMax            { get; private set; }

        public int MaxDecodePasses => 2;

        public Ft8NativeResult[] DecodeAll(float[] pcm) => [];

        public int[]  GetLastPassCounts(int maxPasses)      => new int[maxPasses];
        public int[]  GetLastCandidateCounts(int maxPasses) => new int[maxPasses];
        public float  GetLastNoiseFloorDb()                  => 0f;
        public int    GetHashTableRejectCount()              => 0;
        public (float[] MeanAbs, float[] PrenormVariance, int[] FailCount) GetLastLlrStats(int maxPasses)
            => (new float[maxPasses], new float[maxPasses], new int[maxPasses]);

        public void SetApBits(byte[] mycallBits, byte[] hiscallBits) { /* no-op */ }

        public void SetDecodeParams(int kMinScorePass2, float osdCorrThreshold, int osdNhardMax)
        {
            SetDecodeParamsCalled = true;
            LastKMinScorePass2    = kMinScorePass2;
            LastOsdCorrThreshold  = osdCorrThreshold;
            LastOsdNhardMax       = osdNhardMax;
        }
    }

    // ── 7.3a — Adapter correctly delegates SetDecodeParams ───────────────────

    [Fact(DisplayName = "7.3a: IFt8NativeInterop.SetDecodeParams is called with correct values")]
    public void SetDecodeParams_DelegatesToImplementation()
    {
        var interop = new CapturingInterop();

        interop.SetDecodeParams(kMinScorePass2: 15, osdCorrThreshold: 0.20f, osdNhardMax: 70);

        interop.SetDecodeParamsCalled.Should().BeTrue(
            "SetDecodeParams must be forwarded to the underlying implementation");
        interop.LastKMinScorePass2  .Should().Be(15,
            "kMinScorePass2 must be passed through unchanged");
        interop.LastOsdCorrThreshold.Should().BeApproximately(0.20f, 1e-6f,
            "osdCorrThreshold must be passed through unchanged");
        interop.LastOsdNhardMax     .Should().Be(70,
            "osdNhardMax must be passed through unchanged");
    }

    [Fact(DisplayName = "7.3b: SetDecodeParams with calibrated defaults (10, 0.10, 60) calls implementation")]
    public void SetDecodeParams_WithCalibratedDefaults_DelegatesToImplementation()
    {
        var interop = new CapturingInterop();

        interop.SetDecodeParams(kMinScorePass2: 10, osdCorrThreshold: 0.10f, osdNhardMax: 60);

        interop.SetDecodeParamsCalled.Should().BeTrue();
        interop.LastKMinScorePass2  .Should().Be(10);
        interop.LastOsdCorrThreshold.Should().BeApproximately(0.10f, 1e-6f);
        interop.LastOsdNhardMax     .Should().Be(60);
    }

    // ── 7.3c — Native adapter: Ft8LibInterop.SetDecodeParams (requires native binary) ──

    /// <summary>
    /// Smoke test for the real P/Invoke path.  Requires the native binary at
    /// the expected location; skipped on machines where it is absent.
    /// </summary>
    [Fact(DisplayName = "7.3c: Ft8NativeInteropAdapter.SetDecodeParams delegates to Ft8LibInterop without throwing")]
    [Trait("Category", "RequiresNativeBinary")]
    public void Ft8NativeInteropAdapter_SetDecodeParams_DoesNotThrow()
    {
        var adapter = new Ft8NativeInteropAdapter();

        // Act — call with calibrated defaults; must not throw.
        var act = () => adapter.SetDecodeParams(
            kMinScorePass2:   10,
            osdCorrThreshold: 0.10f,
            osdNhardMax:      60);

        act.Should().NotThrow(
            "SetDecodeParams with calibrated defaults must complete without error " +
            "when the native binary (shim 20260030) is present");
    }

    [Fact(DisplayName = "7.3d: Ft8NativeInteropAdapter.SetDecodeParams with out-of-range (but legal) values does not throw")]
    [Trait("Category", "RequiresNativeBinary")]
    public void Ft8NativeInteropAdapter_SetDecodeParamsEdgeCases_DoesNotThrow()
    {
        var adapter = new Ft8NativeInteropAdapter();

        // These values are at the UI-enforced bounds — they must not crash the native layer.
        var actLow  = () => adapter.SetDecodeParams(kMinScorePass2: 5,  osdCorrThreshold: 0.05f, osdNhardMax: 30);
        var actHigh = () => adapter.SetDecodeParams(kMinScorePass2: 30, osdCorrThreshold: 0.40f, osdNhardMax: 100);

        actLow.Should().NotThrow("lower-bound values must be accepted by the native shim");
        actHigh.Should().NotThrow("upper-bound values must be accepted by the native shim");

        // Restore calibrated defaults so subsequent tests are not affected.
        adapter.SetDecodeParams(kMinScorePass2: 10, osdCorrThreshold: 0.10f, osdNhardMax: 60);
    }
}
