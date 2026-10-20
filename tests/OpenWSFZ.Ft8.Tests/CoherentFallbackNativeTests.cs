using System;
using System.IO;
using System.Runtime.InteropServices;
using FluentAssertions;
using OpenWSFZ.Ft8.Interop;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// COH-FALLBACK (A' step 3) Stage 1 (shim 20260066): a managed P/Invoke smoke test of the two new DIAGNOSTIC-ONLY exports
/// <c>ft8_coherent_fallback_at</c> and <c>ft8_coherent_fallback_cycle</c>. They have no managed binding in Stage 1 (Stage 2
/// wires the product), so the test binds them here, test-locally, the way <c>OsdSignFixTests</c> binds <c>ft8_ldpc_decode_llrs</c>.
/// The numerical work (estimator, F1b, gate, BP-only decode, the retained candidate list) is covered by
/// <c>tests/Ft8.FitProbe/native/coh_fallback_selftest.c</c>; this test pins the ABI (struct sizes and field offsets), the export
/// names, the BP-only decode path and the bad-argument returns across the managed boundary.
/// Synthetic content only (NFR-021): the message is <c>CQ Q1ABC FN20</c>; the noise generator is seeded.
/// </summary>
public sealed class CoherentFallbackNativeTests
{
    private const int PcmSamples = 180_000;
    private const int SamplesPerSymbol = 1920;
    private const double ToneSpacingHz = 6.25;
    private const double SymbolPeriodS = 0.16;
    private const int FlagForceC3 = 1;
    private const int FlagSkipF1b = 2;
    private const int FlagEstimateOnly = 4;
    private const int BpNotRun = 99;

    [StructLayout(LayoutKind.Sequential, Pack = 8)]
    private struct CohResult
    {
        public double EstDfHz, EstDtS, Peak, F1bDb, EstimateMs, F1bMs, C3BpMs, ElapsedMs;
        public int DtStep, Edge, NRefs, Gated, C3Ran, BpRc, BpPath, BpCrcOk, BpLdpcErrors;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 12)] public byte[] A91;
    }

    [StructLayout(LayoutKind.Sequential, Pack = 8)]
    private struct CohCycleStats
    {
        public int NCandidates, NDecoded, NDupPosition, NEligible, NGated, NAttempted, NCrcOk, NCrcNew, NEdge, NDecodedEstimated, NRows, Reserved;
        public double EstimateMs, F1bMs, C3BpMs, TotalMs;
    }

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate int FallbackAt(float[] pcm, int pcmLen, double freqHz, double timeOffsetS, int flags, ref CohResult res, float[]? outLlr174);

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate int FallbackCycle(float[] pcm, int pcmLen, int flags, ref CohCycleStats stats, IntPtr rows, int rowsCap);

    private static (FallbackAt At, FallbackCycle Cycle) LoadExports()
    {
        _ = Ft8LibInterop.GetOsdSignFix();               // forces the native library to load and verify its version
        string file = RuntimeInformation.IsOSPlatform(OSPlatform.Windows) ? "libft8.dll"
                    : RuntimeInformation.IsOSPlatform(OSPlatform.OSX)     ? "libft8.dylib" : "libft8.so";
        IntPtr lib = NativeLibrary.Load(Path.Combine(AppContext.BaseDirectory, file));
        return (Marshal.GetDelegateForFunctionPointer<FallbackAt>(NativeLibrary.GetExport(lib, "ft8_coherent_fallback_at")),
                Marshal.GetDelegateForFunctionPointer<FallbackCycle>(NativeLibrary.GetExport(lib, "ft8_coherent_fallback_cycle")));
    }

    /// <summary>A continuous-phase 8-FSK FT8 signal (amplitude 0.3) whose symbol 0 starts at <paramref name="startS"/>, plus seeded noise.</summary>
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
        var rng = new Random(seed);
        for (int i = 0; i < PcmSamples; i++)
        {
            double u1 = 1.0 - rng.NextDouble(), u2 = rng.NextDouble();
            pcm[i] += (float)(noiseSigma * Math.Sqrt(-2.0 * Math.Log(u1)) * Math.Cos(2.0 * Math.PI * u2));
        }
        return pcm;
    }

    [Fact(DisplayName = "COH-FALLBACK Stage 1: the result structs have the documented sizes (ABI pin)")]
    public void StructSizes_MatchTheHeader()
    {
        Marshal.SizeOf<CohResult>().Should().Be(112, "FT8CohFallbackResult is 112 bytes in ft8_shim.h");
        Marshal.SizeOf<CohCycleStats>().Should().Be(80, "FT8CohFallbackCycleStats is 80 bytes in ft8_shim.h");
        Marshal.OffsetOf<CohResult>(nameof(CohResult.DtStep)).ToInt32().Should().Be(64);
        Marshal.OffsetOf<CohResult>(nameof(CohResult.A91)).ToInt32().Should().Be(100);
    }

    [Fact(DisplayName = "COH-FALLBACK Stage 1: a strong synthetic CQ decodes through the BP-only path (path 0, never OSD) to the encoded message's payload")]
    public void StrongSignal_DecodesBpOnly()
    {
        var (at, _) = LoadExports();
        var tones = new byte[79];
        Ft8LibInterop.EncodeMessage("CQ Q1ABC FN20", tones);
        tones.Length.Should().Be(79);
        const double fTrue = 1500.0, startS = 0.55;
        var pcm = Synthesise(tones, fTrue, startS, noiseSigma: 0.15, seed: 20261020);

        var res = new CohResult { A91 = new byte[12] };
        var llr = new float[174];
        // anchor 0.8 Hz and 0.04 s off the true position (candidate convention: symbol 0 at anchor - one symbol period)
        int rc = at(pcm, PcmSamples, fTrue + 0.8, startS + SymbolPeriodS + 0.04, FlagForceC3, ref res, llr);

        rc.Should().Be(0);
        res.EstDfHz.Should().BeApproximately(-0.8, 0.151);
        res.EstDtS.Should().BeApproximately(-0.04, 0.0101);
        res.Edge.Should().Be(0);
        res.NRefs.Should().Be(24);
        res.C3Ran.Should().Be(1);
        res.BpRc.Should().Be(0);
        res.BpPath.Should().Be(0, "the fallback is BP only: path 1 would be the OSD fallback");
        res.BpCrcOk.Should().Be(1);
        res.ElapsedMs.Should().BeGreaterThan(0.0);
    }

    [Fact(DisplayName = "COH-FALLBACK Stage 1: the flags and the bad-argument returns work across the managed boundary")]
    public void Flags_And_BadArguments()
    {
        var (at, cycle) = LoadExports();
        var tones = new byte[79];
        Ft8LibInterop.EncodeMessage("CQ Q1ABC FN20", tones);
        var pcm = Synthesise(tones, 1500.0, 0.55, noiseSigma: 0.05, seed: 7);   // strong: F1b is well above the gate

        var r = new CohResult { A91 = new byte[12] };
        at(pcm, PcmSamples, 1500.0, 0.71, FlagEstimateOnly, ref r, null).Should().Be(0);
        (r.C3Ran, r.BpRc, r.NRefs).Should().Be((0, BpNotRun, 0));
        double.IsNaN(r.F1bDb).Should().BeTrue("ESTIMATE_ONLY does not compute F1b");

        r = new CohResult { A91 = new byte[12] };
        at(pcm, PcmSamples, 1500.0, 0.71, 0, ref r, null).Should().Be(0);
        r.Gated.Should().Be(0);
        r.F1bDb.Should().BeGreaterThan(17.552446, "a strong signal is above T1");
        (r.C3Ran, r.BpRc).Should().Be((0, BpNotRun), "the gate is closed, so C3 does not run");

        r = new CohResult { A91 = new byte[12] };
        at(pcm, PcmSamples, 1500.0, 0.71, FlagSkipF1b, ref r, null).Should().Be(0);
        (r.C3Ran, r.NRefs).Should().Be((1, 0));

        at(pcm, PcmSamples - 1, 1500.0, 0.71, 0, ref r, null).Should().Be(-1, "pcm_len must be 180000");
        at(null!, PcmSamples, 1500.0, 0.71, 0, ref r, null).Should().Be(-1);

        // no ft8_decode_all on this thread: the retained list is empty
        var st = new CohCycleStats();
        cycle(pcm, PcmSamples, 0, ref st, IntPtr.Zero, 0).Should().Be(0);
        (st.NCandidates, st.NEligible, st.NRows).Should().Be((0, 0, 0));
        cycle(pcm, PcmSamples - 1, 0, ref st, IntPtr.Zero, 0).Should().Be(-1);
    }
}
