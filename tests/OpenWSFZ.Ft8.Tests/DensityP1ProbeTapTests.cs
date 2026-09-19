using System.Reflection;
using System.Runtime.InteropServices;
using FluentAssertions;
using OpenWSFZ.Ft8.Interop;
using Xunit;
using Xunit.Abstractions;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Tests for the DENSITY-P1 Stage 1 pass-1 probe TAP (density-p1-stage1-pass1-probe,
/// shim 20260053): four DIAGNOSTIC-ONLY native exports —
/// <c>ft8_set_probe</c>, <c>ft8_clear_probe</c>, <c>ft8_get_probe_llrs</c>,
/// <c>ft8_get_last_suppression</c> — over a read-only tap inside <c>ft8_decode_all</c>.
/// <para>
/// <b>Test-local P/Invoke, on purpose.</b> The four exports have NO managed binding: no
/// <c>DllImport</c> in <c>src/OpenWSFZ.Ft8</c>, no <c>IFt8NativeInterop</c> member (dev-task
/// §1.3). They are declared in <see cref="ProbeNative"/> below, in the TEST assembly only.
/// </para>
/// <para>
/// Deterministic synthetic scenes only; <c>Q</c>-prefix synthetic callsigns only (NFR-021).
/// Everything is thread-local in the native shim, and xUnit runs each test method on one
/// thread with test parallelisation disabled for this assembly (<c>AssemblyInfo.cs</c>), so
/// arm → decode → read sequences here are on one thread by construction. Nothing in this
/// class is <c>async</c>, deliberately: an <c>await</c> could hop threads.
/// </para>
/// <para>
/// All float comparisons are on <b>bit patterns</b> (<see cref="BitConverter.SingleToInt32Bits"/>),
/// never <c>==</c> on floats, per the dev-task's T2 wording.
/// </para>
/// </summary>
[Trait("Category", "RequiresNativeBinary")]
public sealed class DensityP1ProbeTapTests
{
    private readonly ITestOutputHelper _out;
    public DensityP1ProbeTapTests(ITestOutputHelper output) => _out = output;

    // ── Test-local P/Invoke (NOT in src/) ────────────────────────────────────

    /// <summary>Mirror of the native <c>FT8Result</c> (48 bytes).</summary>
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Ansi)]
    private struct NativeResult
    {
        public int   FreqHz;
        public float Dt;
        public int   Snr;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 36)]
        public string Message;
    }

    /// <summary>Mirror of the native <c>Ft8SuppressionRecord</c> (24 bytes, no padding).</summary>
    [StructLayout(LayoutKind.Sequential)]
    private struct SuppressionRecord
    {
        public int   FreqOffset;
        public int   TimeOffset;
        public int   FreqSub;
        public int   TimeSub;
        public float SnrDb;
        public float Factor;
    }

    private static class ProbeNative
    {
        private const string Lib = "libft8.dll";

        // The test assembly needs its own resolver: Ft8LibInterop's is registered on the
        // OpenWSFZ.Ft8 assembly and does not apply to this one. It loads the SAME file
        // from the SAME directory, so both bind the one module (and its thread-locals).
        static ProbeNative()
        {
            try { NativeLibrary.SetDllImportResolver(typeof(ProbeNative).Assembly, Resolve); }
            catch (InvalidOperationException) { /* already registered for this assembly */ }
        }

        private static IntPtr Resolve(string name, Assembly asm, DllImportSearchPath? path)
        {
            if (name != Lib) return IntPtr.Zero;
            string file = RuntimeInformation.IsOSPlatform(OSPlatform.Windows) ? "libft8.dll"
                        : RuntimeInformation.IsOSPlatform(OSPlatform.OSX)     ? "libft8.dylib"
                        : "libft8.so";
            return NativeLibrary.Load(Path.Combine(AppContext.BaseDirectory, file));
        }

        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
        public static extern int ft8_lib_version_check();

        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
        public static extern int ft8_decode_all([In] float[] pcm, int pcmLen, [Out] NativeResult[] results, int maxResults);

        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
        public static extern int ft8_get_max_passes();

        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
        public static extern int ft8_get_last_pass_counts([Out] int[] counts, int capacity);

        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
        public static extern int ft8_get_last_candidate_counts([Out] int[] counts, int capacity);

        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
        public static extern int ft8_get_last_llr_stats([Out] float[] meanAbs, [Out] float[] prenormVar, [Out] int[] failCount, int capacity);

        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
        public static extern int ft8_get_last_snr_terms([Out] float[] signalDb, [Out] float[] localNoiseDb, int capacity);

        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
        public static extern float ft8_get_last_noise_floor_db();

        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
        public static extern int ft8_extract_llrs_at([In] float[] pcm, int pcmLen, float freqHz, float timeOffsetS, [Out] float[] outLlr174);

        // ── the four DENSITY-P1 Stage 1 exports ──
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
        public static extern void ft8_set_probe(float freqHz, float timeOffsetS);

        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
        public static extern void ft8_clear_probe();

        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
        public static extern int ft8_get_probe_llrs(int pass, [In, Out] float[]? out174);

        // [In, Out] (not [Out] alone) so the runtime's copy-back can never disturb elements the
        // native side did not write — the "untouched" assertions below must test the NATIVE code,
        // not the marshaller.
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
        public static extern int ft8_get_last_suppression([In, Out] SuppressionRecord[]? buf, int capacity);
    }

    // ── Return codes (ft8_shim.h) — literals asserted on purpose, not imported ──

    private const int ProbeOk         = 0;
    private const int ProbeBadArg     = -1;
    private const int ProbeOutOfBand  = -3;
    private const int ProbeNotArmed   = -4;
    private const int ProbePassNotRun = -5;

    private const int PcmLen     = 180_000;
    private const int LlrCount   = 174;
    private const int MaxResults = 340;

    /// <summary>A NaN with a recognisable payload — the "untouched" sentinel.</summary>
    private static readonly int SentinelBits = BitConverter.SingleToInt32Bits(BitConverter.Int32BitsToSingle(0x7FC01234));

    // ── Scene: three deterministic synthetic signals in seeded white noise ───

    private const int    NoiseSeed   = 20260919;
    private const double NoiseSigma  = 0.08;

    /// <summary>tone-0 Hz (all on the 3.125 Hz lattice), start sample, peak amplitude, text.</summary>
    private static readonly (double FreqHz, int StartSample, float Amplitude, string Text)[] SceneSignals =
    [
        (  800.0, 6_000, 0.30f, "Q1OFZ Q9XYZ JO33"),   // strong
        ( 1400.0, 6_400, 0.15f, "Q9XYZ Q1OFZ RR73"),   // mid
        ( 2000.0, 6_800, 0.09f, "CQ Q1ABC AA00"),      // weak
    ];

    private static float[] BuildScene()
    {
        var pcm = new float[PcmLen];
        foreach (var (freq, start, amp, text) in SceneSignals)
        {
            var tones = new byte[Ft8LibInterop.EncodedToneCount];
            Ft8LibInterop.EncodeMessage(text, tones);
            float[] one = TestFt8Encoder.SymbolsToPcm(Array.ConvertAll(tones, static t => (int)t), freq, start, amp);
            for (int i = 0; i < PcmLen; i++) pcm[i] += one[i];
        }

        // Seeded Box–Muller white noise. new Random(seed) is a stable, documented sequence.
        var rng = new Random(NoiseSeed);
        for (int i = 0; i < PcmLen; i++)
        {
            double u1 = 1.0 - rng.NextDouble();
            double u2 = rng.NextDouble();
            pcm[i] += (float)(NoiseSigma * Math.Sqrt(-2.0 * Math.Log(u1)) * Math.Cos(2.0 * Math.PI * u2));
        }
        return pcm;
    }

    // ── One decode call + every existing ft8_get_last_* diagnostic ───────────

    private sealed record Snapshot(
        int      Count,
        string[] Messages,
        int[]    FreqHz,
        int[]    DtBits,
        int[]    Snr,
        int[]    PassCounts,
        int[]    CandidateCounts,
        int[]    LlrMeanAbsBits,
        int[]    LlrPrenormVarBits,
        int[]    LlrFailCounts,
        int      NoiseFloorBits,
        int[]    SignalDbBits,
        int[]    LocalNoiseDbBits);

    private static (Snapshot Snap, NativeResult[] Raw) DecodeAndSnapshot(float[] pcm, int maxResults = MaxResults)
    {
        var results = new NativeResult[Math.Max(maxResults, 1)];
        int n = ProbeNative.ft8_decode_all(pcm, pcm.Length, results, maxResults);
        n.Should().BeGreaterThanOrEqualTo(0, "the decode call itself must not fail (-1 bad length, -2 SEH fault)");

        int passes = ProbeNative.ft8_get_max_passes();
        var passCounts = new int[passes];        int npc = ProbeNative.ft8_get_last_pass_counts(passCounts, passes);
        var candCounts = new int[passes];        int ncc = ProbeNative.ft8_get_last_candidate_counts(candCounts, passes);
        var meanAbs    = new float[passes];
        var prenormVar = new float[passes];
        var failCount  = new int[passes];        int nls = ProbeNative.ft8_get_last_llr_stats(meanAbs, prenormVar, failCount, passes);
        var sig        = new float[MaxResults];
        var loc        = new float[MaxResults];  int nst = ProbeNative.ft8_get_last_snr_terms(sig, loc, MaxResults);

        npc.Should().Be(passes); ncc.Should().Be(passes); nls.Should().Be(passes);
        nst.Should().Be(n, "ft8_get_last_snr_terms's count contract: one entry per returned decode");

        var raw = results.Take(n).ToArray();
        return (new Snapshot(
            n,
            raw.Select(r => r.Message).ToArray(),
            raw.Select(r => r.FreqHz).ToArray(),
            raw.Select(r => BitConverter.SingleToInt32Bits(r.Dt)).ToArray(),
            raw.Select(r => r.Snr).ToArray(),
            passCounts,
            candCounts,
            meanAbs.Select(BitConverter.SingleToInt32Bits).ToArray(),
            prenormVar.Select(BitConverter.SingleToInt32Bits).ToArray(),
            failCount,
            BitConverter.SingleToInt32Bits(ProbeNative.ft8_get_last_noise_floor_db()),
            sig.Take(nst).Select(BitConverter.SingleToInt32Bits).ToArray(),
            loc.Take(nst).Select(BitConverter.SingleToInt32Bits).ToArray()), raw);
    }

    private static float[] SentinelBuffer(int n = LlrCount)
    {
        var b = new float[n];
        Array.Fill(b, BitConverter.Int32BitsToSingle(0x7FC01234));
        return b;
    }

    private static bool IsUntouched(float[] buf) => buf.All(f => BitConverter.SingleToInt32Bits(f) == SentinelBits);

    private static float[] Llrs(int pass, out int rc)
    {
        var buf = new float[LlrCount];
        rc = ProbeNative.ft8_get_probe_llrs(pass, buf);
        return buf;
    }

    /// <summary>The scene's strong signal's position, as the shim itself reports it.</summary>
    private static (float FreqHz, float TimeOffsetS) StrongSignalPosition(NativeResult[] raw)
    {
        NativeResult strong = raw.First(r => r.Message.Contains("Q1OFZ Q9XYZ JO33", StringComparison.Ordinal));
        // 800.0 Hz is on the 3.125 Hz lattice; dt is the shim's own (time_offset + sub/osr) * symbol_period,
        // which is exactly the forward mapping ft8_extract_llrs_at inverts.
        return (800.0f, strong.Dt);
    }

    // ── Sanity: the DLL under test is the new one, and the layout is what QA reads ──

    [Fact(DisplayName = "T0a: the loaded native binary is shim 20260053 and Ft8SuppressionRecord is 24 bytes")]
    public void LoadedBinary_IsShim20260053_AndRecordLayoutIs24Bytes()
    {
        ProbeNative.ft8_lib_version_check().Should().Be(20260053,
            "these tests are for the density-p1-stage1-pass1-probe build (20260052 is reserved, not used)");
        Marshal.SizeOf<SuppressionRecord>().Should().Be(24, "six 4-byte members, no padding");
        Marshal.SizeOf<NativeResult>().Should().Be(48, "FT8Result must stay 48 bytes — nothing that exists changes layout");
    }

    [Fact(DisplayName = "T0b: the scene decodes all three signals (else the other tests are vacuous)")]
    public void Scene_DecodesAllThreeSignals()
    {
        ProbeNative.ft8_clear_probe();
        var (snap, _) = DecodeAndSnapshot(BuildScene());
        foreach (var (_, _, _, text) in SceneSignals)
            snap.Messages.Should().Contain(text);
        _out.WriteLine($"scene decodes: {string.Join(" | ", snap.Messages.Zip(snap.Snr, (m, s) => $"{m} @ {s} dB"))}");
        _out.WriteLine($"pass counts: {string.Join(",", snap.PassCounts)}  candidates: {string.Join(",", snap.CandidateCounts)}");
    }

    // ── T1: NON-PERTURBATION ─────────────────────────────────────────────────

    /// <summary>Armed positions: on the strong signal, on empty spectrum, deep out-of-band both sides.</summary>
    public static TheoryData<float, float> ArmedPositions => new()
    {
        { 800.0f,  0.5f  },   // on the strong signal's frequency
        { 1234.5f, 3.3f  },   // arbitrary in-band position
        { 2900.0f, 14.0f },   // near the top edge, late in the window
        { 50.0f,   1.0f  },   // below the passband      -> out of band
        { 5000.0f, 1.0f  },   // above the passband      -> out of band
    };

    [Theory(DisplayName = "T1: decode results AND every ft8_get_last_* diagnostic are identical armed vs disarmed")]
    [MemberData(nameof(ArmedPositions))]
    public void Armed_IsIdentical_ToDisarmed(float freqHz, float timeOffsetS)
    {
        float[] pcm = BuildScene();

        ProbeNative.ft8_clear_probe();
        var (baseline, _)  = DecodeAndSnapshot(pcm);
        var (baseline2, _) = DecodeAndSnapshot(pcm);
        baseline2.Should().BeEquivalentTo(baseline, o => o.WithStrictOrdering(),
            "precondition: two DISARMED decodes of the same PCM must already be identical, or this test proves nothing");

        ProbeNative.ft8_set_probe(freqHz, timeOffsetS);
        var (armed, _) = DecodeAndSnapshot(pcm);

        armed.Should().BeEquivalentTo(baseline, o => o.WithStrictOrdering(),
            "the tap is READ-ONLY: it must not change any result, counter, candidate, SNR or TLS diagnostic");
    }

    // ── T2: PASS-0 EQUIVALENCE with ft8_extract_llrs_at ──────────────────────

    [Theory(DisplayName = "T2: pass-0 tap LLRs equal ft8_extract_llrs_at at the same PCM/position, bit-for-bit")]
    [InlineData(-1f, -1f)]      // sentinel: use the strong signal's own position
    [InlineData(1234.5f, 3.3f)]
    [InlineData(803.0f, 0.55f)] // a near-neighbour position, off the signal's lattice point
    [InlineData(2900.0f, 1.0f)] // near the top edge; t=1 s is inside the data window (a late t would zero-fill both sides and be vacuous)
    public void Pass0Tap_Equals_ExtractLlrsAt_BitForBit(float freqHz, float timeOffsetS)
    {
        float[] pcm = BuildScene();

        if (freqHz < 0)
        {
            ProbeNative.ft8_clear_probe();
            var (_, raw) = DecodeAndSnapshot(pcm);
            (freqHz, timeOffsetS) = StrongSignalPosition(raw);
        }

        ProbeNative.ft8_set_probe(freqHz, timeOffsetS);
        DecodeAndSnapshot(pcm);
        float[] tap = Llrs(0, out int rcTap);

        var reference = new float[LlrCount];
        int rcRef = ProbeNative.ft8_extract_llrs_at(pcm, pcm.Length, freqHz, timeOffsetS, reference);

        rcRef.Should().Be(0);
        rcTap.Should().Be(ProbeOk);
        tap.Select(BitConverter.SingleToInt32Bits).Should().Equal(reference.Select(BitConverter.SingleToInt32Bits),
            "the tap's snapping arithmetic is an independent copy of ft8_extract_llrs_at's; they must agree exactly");
        tap.Any(f => f != 0f).Should().BeTrue("all-zero LLRs on both sides would make this comparison vacuous");
    }

    [Fact(DisplayName = "T2b: the pass-1 tap sees the SUPPRESSED waterfall (differs from pass 0 at a suppressed signal)")]
    public void Pass1Tap_DiffersFromPass0_AtASuppressedSignal()
    {
        float[] pcm = BuildScene();
        ProbeNative.ft8_clear_probe();
        var (_, raw) = DecodeAndSnapshot(pcm);
        var (f, t) = StrongSignalPosition(raw);

        ProbeNative.ft8_set_probe(f, t);
        DecodeAndSnapshot(pcm);
        float[] p0 = Llrs(0, out int rc0);
        float[] p1 = Llrs(1, out int rc1);
        int nSupp = ProbeNative.ft8_get_last_suppression(null, 0);

        rc0.Should().Be(ProbeOk);
        rc1.Should().Be(ProbeOk);
        nSupp.Should().BeGreaterThanOrEqualTo(1, "the strong signal is decoded in pass 0 and therefore suppressed before pass 1");
        p1.Select(BitConverter.SingleToInt32Bits).Should().NotEqual(p0.Select(BitConverter.SingleToInt32Bits),
            "the tap runs AFTER pass 1's suppression: at the suppressed signal's own position the LLRs must have changed. " +
            "Identical LLRs would mean the tap sits before the suppression block (a placement defect).");
        _out.WriteLine($"mean|LLR| pass0={p0.Average(Math.Abs):F3}  pass1={p1.Average(Math.Abs):F3}");
    }

    // ── T3: SELF-DISARM, NEVER STALE ─────────────────────────────────────────

    [Fact(DisplayName = "T3: a second decode with no re-arm reads back 'not armed' — never the earlier armed call's data")]
    public void SecondDecode_WithoutRearm_ReadsNotArmed()
    {
        float[] pcm = BuildScene();

        ProbeNative.ft8_set_probe(800.0f, 0.5f);
        DecodeAndSnapshot(pcm);
        Llrs(0, out int armedRc);
        armedRc.Should().Be(ProbeOk, "precondition: the armed call captured pass 0");
        ProbeNative.ft8_get_last_suppression(null, 0).Should().BeGreaterThanOrEqualTo(1, "precondition: the armed call recorded suppressions");

        DecodeAndSnapshot(pcm);   // NOT re-armed

        foreach (int pass in new[] { 0, 1 })
        {
            float[] buf = SentinelBuffer();
            ProbeNative.ft8_get_probe_llrs(pass, buf).Should().Be(ProbeNotArmed, $"pass {pass}: the arm was consumed by the first call");
            IsUntouched(buf).Should().BeTrue("out174 must be left untouched on every non-zero return");
        }
        ProbeNative.ft8_get_last_suppression(new SuppressionRecord[4], 4).Should().Be(0, "no stale suppression records from the earlier armed call");
    }

    [Fact(DisplayName = "T3b: ft8_clear_probe disarms a pending arm AND invalidates captured data")]
    public void ClearProbe_DisarmsAndInvalidates()
    {
        float[] pcm = BuildScene();

        // (i) clear after capture -> reads invalid
        ProbeNative.ft8_set_probe(800.0f, 0.5f);
        DecodeAndSnapshot(pcm);
        Llrs(0, out int rcBefore);
        rcBefore.Should().Be(ProbeOk);
        ProbeNative.ft8_clear_probe();
        Llrs(0, out int rcAfter);
        rcAfter.Should().Be(ProbeNotArmed);
        ProbeNative.ft8_get_last_suppression(null, 0).Should().Be(0);

        // (ii) arm then clear then decode -> the decode is NOT armed
        ProbeNative.ft8_set_probe(800.0f, 0.5f);
        ProbeNative.ft8_clear_probe();
        DecodeAndSnapshot(pcm);
        Llrs(0, out int rcCleared);
        rcCleared.Should().Be(ProbeNotArmed, "a cleared arm must not capture");
    }

    [Fact(DisplayName = "T3c: bad arguments return -1 and leave out174 untouched")]
    public void GetProbeLlrs_BadArguments_ReturnBadArg()
    {
        float[] pcm = BuildScene();
        ProbeNative.ft8_set_probe(800.0f, 0.5f);
        DecodeAndSnapshot(pcm);

        foreach (int badPass in new[] { -1, 2, 99 })
        {
            float[] buf = SentinelBuffer();
            ProbeNative.ft8_get_probe_llrs(badPass, buf).Should().Be(ProbeBadArg, $"pass {badPass} is out of range");
            IsUntouched(buf).Should().BeTrue();
        }
        ProbeNative.ft8_get_probe_llrs(0, null).Should().Be(ProbeBadArg, "NULL out174");
    }

    // ── T4: OUT-OF-BAND POSITION ─────────────────────────────────────────────

    [Theory(DisplayName = "T4: an out-of-band position returns -3 for BOTH passes; decode results unchanged")]
    [InlineData(50.0f)]
    [InlineData(5000.0f)]
    public void OutOfBandPosition_ReturnsMinus3_AndDecodeUnchanged(float freqHz)
    {
        float[] pcm = BuildScene();

        ProbeNative.ft8_clear_probe();
        var (baseline, _) = DecodeAndSnapshot(pcm);

        ProbeNative.ft8_set_probe(freqHz, 1.0f);
        var (armed, _) = DecodeAndSnapshot(pcm);

        foreach (int pass in new[] { 0, 1 })
        {
            float[] buf = SentinelBuffer();
            ProbeNative.ft8_get_probe_llrs(pass, buf).Should().Be(ProbeOutOfBand, $"pass {pass}");
            IsUntouched(buf).Should().BeTrue("out174 untouched on -3");
        }

        // ft8_extract_llrs_at rejects the same position with the same code — the tap agrees.
        ProbeNative.ft8_extract_llrs_at(pcm, pcm.Length, freqHz, 1.0f, new float[LlrCount]).Should().Be(ProbeOutOfBand);

        armed.Should().BeEquivalentTo(baseline, o => o.WithStrictOrdering());
    }

    // ── T5: SUPPRESSION RECORDS ──────────────────────────────────────────────

    [Fact(DisplayName = "T5: suppression records — count >= 1, factor == 1 - clamp((snr-(-5))/20, 0, 1) within 1e-6, factor in [0,1]")]
    public void SuppressionRecords_FactorMatchesTheRamp_AndIsInUnitRange()
    {
        float[] pcm = BuildScene();
        ProbeNative.ft8_set_probe(800.0f, 0.5f);
        var (snap, _) = DecodeAndSnapshot(pcm);

        int total = ProbeNative.ft8_get_last_suppression(null, 0);
        total.Should().BeGreaterThanOrEqualTo(1, "the scene has a strong pass-0 decode");
        total.Should().Be(snap.PassCounts[0], "one record per pass-0 decode that entered the suppression accumulator");

        var recs = new SuppressionRecord[total];
        ProbeNative.ft8_get_last_suppression(recs, total).Should().Be(total);

        bool sawInterior = false;
        foreach (SuppressionRecord r in recs)
        {
            // Literals on purpose (dev-task T5): K_SOFT_SUPP_SNR_MIN_DB = -5, K_SOFT_SUPP_SNR_MAX_DB = +15.
            float expected = 1.0f - Math.Clamp((r.SnrDb - (-5.0f)) / (15.0f - (-5.0f)), 0.0f, 1.0f);
            r.Factor.Should().BeApproximately(expected, 1e-6f, $"snr_db={r.SnrDb}: factor must be what the ramp gives");
            r.Factor.Should().BeInRange(0.0f, 1.0f);
            float.IsFinite(r.SnrDb).Should().BeTrue();

            sawInterior |= r.SnrDb > -5.0f && r.SnrDb < 15.0f;
            _out.WriteLine($"record: f_off={r.FreqOffset} t_off={r.TimeOffset} f_sub={r.FreqSub} t_sub={r.TimeSub} snr_db={r.SnrDb:F4} factor={r.Factor:F6}");
        }

        // A clamp-only check would also pass an implementation that always returned 0 or 1.
        sawInterior.Should().BeTrue("at least one record must sit strictly inside the ramp, so the linear part is exercised, not just its clamped ends");

        // snr_db is the UNROUNDED float: it must agree with FT8Result.snr only after rounding.
        // (MidpointRounding.AwayFromZero matches the C side's roundf.)
        var snrs = recs.Select(r => (int)MathF.Round(r.SnrDb, MidpointRounding.AwayFromZero)).OrderBy(x => x).ToArray();
        snrs.Should().Equal(snap.Snr.Take(total).OrderBy(x => x),
            "records carry the unrounded SNR; rounded, they must equal the pass-0 decodes' reported SNRs");
    }

    [Fact(DisplayName = "T5b: ft8_get_last_suppression capacity convention — returns the TOTAL, writes at most `capacity`")]
    public void GetLastSuppression_CapacityConvention()
    {
        float[] pcm = BuildScene();
        ProbeNative.ft8_set_probe(800.0f, 0.5f);
        DecodeAndSnapshot(pcm);

        int total = ProbeNative.ft8_get_last_suppression(null, 0);
        total.Should().BeGreaterThanOrEqualTo(2, "need >=2 records to test truncation");

        var one = new SuppressionRecord[2];
        one[1] = new SuppressionRecord { FreqOffset = 0x5A5A5A5A };
        ProbeNative.ft8_get_last_suppression(one, 1).Should().Be(total, "returns the TOTAL even when capacity is smaller");
        one[1].FreqOffset.Should().Be(0x5A5A5A5A, "only `capacity` (=1) records may be written");

        ProbeNative.ft8_get_last_suppression(new SuppressionRecord[4], 0).Should().Be(total, "capacity 0 just sizes the buffer");
        ProbeNative.ft8_get_last_suppression(new SuppressionRecord[4], -3).Should().Be(total, "negative capacity writes nothing");
    }

    // ── T6: EARLY EXIT ───────────────────────────────────────────────────────

    [Fact(DisplayName = "T6: with max_results small enough to skip pass 1, pass 1 reads 'pass did not run' (-5); pass 0 still captured")]
    public void EarlyExit_PassOneSkipped_ReadsPassDidNotRun()
    {
        float[] pcm = BuildScene();

        ProbeNative.ft8_set_probe(800.0f, 0.5f);
        var (snap, _) = DecodeAndSnapshot(pcm, maxResults: 1);

        snap.Count.Should().Be(1, "max_results = 1 fills the buffer in pass 0");
        snap.PassCounts.Should().Equal([1, 0], "pass 1 took the `num_decoded >= max_results` early-exit `continue`");

        Llrs(0, out int rc0);
        rc0.Should().Be(ProbeOk, "pass 0 ran and was captured");

        float[] buf = SentinelBuffer();
        ProbeNative.ft8_get_probe_llrs(1, buf).Should().Be(ProbePassNotRun);
        IsUntouched(buf).Should().BeTrue("out174 untouched on -5");

        ProbeNative.ft8_get_last_suppression(new SuppressionRecord[4], 4).Should().Be(0,
            "pass 1 did not run, so there were no suppressions to record");
    }

    [Fact(DisplayName = "T6b: with max_results = 0 NEITHER pass runs — both read -5")]
    public void EarlyExit_BothPassesSkipped_BothReadPassDidNotRun()
    {
        float[] pcm = BuildScene();
        ProbeNative.ft8_set_probe(800.0f, 0.5f);
        DecodeAndSnapshot(pcm, maxResults: 0);

        foreach (int pass in new[] { 0, 1 })
        {
            float[] buf = SentinelBuffer();
            ProbeNative.ft8_get_probe_llrs(pass, buf).Should().Be(ProbePassNotRun, $"pass {pass}");
            IsUntouched(buf).Should().BeTrue();
        }
    }
}
