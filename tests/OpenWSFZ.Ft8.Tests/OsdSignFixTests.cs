using System.Runtime.InteropServices;
using System.Text.RegularExpressions;
using FluentAssertions;
using OpenWSFZ.Ft8.Interop;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// osd-sign-fix (#215, shim 20260060, FR-084). <c>osd_decode</c> reads positive = bit 0 while the extractor and
/// belief propagation produce positive = bit 1; the OSD acceptance gate (<c>nhard</c>, corr/norm) read the SAME array as
/// OSD. The fix negates <c>llr_for_osd</c> in place once, so OSD and its gate read one corrected array.
/// These tests drive the real native <c>ft8_ldpc_decode_llrs</c> (production's own normalise → BP → OSD → gate → CRC
/// sequence) with a vector built from a known codeword.
/// </summary>
[Collection("OsdSignSwitch")]
public sealed class OsdSignFixTests : IDisposable
{
    private const int    N                 = 174;
    private const int    PayloadBitCount   = 77;
    private const int    StrongBitCount    = 60;   // well inside the 83 pivot columns
    private const int    StrongWrongBits   = 8;    // confidently wrong, well inside OsdNhardMax = 40
    private const float  StrongMagnitude   = 2.0f;
    private const int    BpIterations      = 50;
    private const int    OsdDepth          = 2;
    private const int    FirstDataSymbol   = 7;    // data symbols 7..35 and 43..71, 3 bits each
    private const int    SecondDataSymbol  = 43;
    private const int    DataSymbolsPerHalf = 29;
    private const float  OsdCorrThreshold  = 0.10f;
    private const int    OsdNhardMax       = 40;
    private static readonly int[] ToneToBits = BuildToneToBits();

    // ft8_ldpc_decode_llrs(llr174, max_iters, osd_depth, out_a91, out_ldpc_errors, out_path, out_crc_ok)
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
    private delegate int LdpcDecodeLlrs([In] float[] llr, int maxIters, int osdDepth, [Out] byte[] a91,
                                        out int ldpcErrors, out int path, out int crcOk);

    private readonly int _savedSwitch;

    public OsdSignFixTests()
    {
        _savedSwitch = Ft8LibInterop.GetOsdSignFix();
        Ft8LibInterop.SetDecodeParams(10, OsdCorrThreshold, OsdNhardMax);
    }

    public void Dispose()
    {
        Ft8LibInterop.SetOsdSignFix(_savedSwitch);
        Ft8LibInterop.SetDecodeParams(10, 0.10f, 60);   // production defaults, shim 20260030
    }

    // ── helpers ──────────────────────────────────────────────────────────────

    private static int[] BuildToneToBits()
    {
        int[] gray = [0, 1, 3, 2, 5, 6, 4, 7];          // bits value -> tone (ft8_lib kFT8_Gray_map)
        var inverse = new int[8];
        for (int bits = 0; bits < 8; bits++) inverse[gray[bits]] = bits;
        return inverse;
    }

    /// <summary>The 174 codeword bits of an encoded message, read back from its 79 tones.</summary>
    private static byte[] CodewordBits(string message)
    {
        var tones = new byte[Ft8LibInterop.EncodedToneCount];
        Ft8LibInterop.EncodeMessage(message, tones);
        var bits = new byte[N];
        int k = 0;
        for (int half = 0; half < 2; half++)
        {
            int start = half == 0 ? FirstDataSymbol : SecondDataSymbol;
            for (int s = 0; s < DataSymbolsPerHalf; s++)
            {
                int v = ToneToBits[tones[start + s]];
                bits[k++] = (byte)((v >> 2) & 1);
                bits[k++] = (byte)((v >> 1) & 1);
                bits[k++] = (byte)(v & 1);
            }
        }
        return bits;
    }

    private static float Gauss(Random rng)
    {
        double u1 = 1.0 - rng.NextDouble(), u2 = rng.NextDouble();
        return (float)(Math.Sqrt(-2.0 * Math.Log(u1)) * Math.Cos(2.0 * Math.PI * u2));
    }

    private static LdpcDecodeLlrs LoadExport()
    {
        _ = Ft8LibInterop.GetOsdSignFix();               // forces the native library to load and verify
        string file = RuntimeInformation.IsOSPlatform(OSPlatform.Windows) ? "libft8.dll"
                    : RuntimeInformation.IsOSPlatform(OSPlatform.OSX)     ? "libft8.dylib" : "libft8.so";
        IntPtr lib = NativeLibrary.Load(Path.Combine(AppContext.BaseDirectory, file));
        return Marshal.GetDelegateForFunctionPointer<LdpcDecodeLlrs>(NativeLibrary.GetExport(lib, "ft8_ldpc_decode_llrs"));
    }

    private sealed record Outcome(int Rc, byte[] A91, int LdpcErrors, int Path, int CrcOk);

    private static Outcome Decode(LdpcDecodeLlrs fn, float[] llr)
    {
        var a91 = new byte[12];
        int rc = fn(llr, BpIterations, OsdDepth, a91, out int errs, out int path, out int crc);
        return new Outcome(rc, a91, errs, path, crc);
    }

    /// <summary>
    /// BP-convention LLRs (positive = bit 1) for the codeword, shaped for this decoder's OSD: it takes the 83 MOST
    /// reliable independent columns as parity pivots (their values are recomputed, never read) and enumerates the
    /// LEAST reliable 91 bits as the free set. So <see cref="StrongWrongBits"/> of the <see cref="StrongBitCount"/> strongest
    /// bits are given the WRONG sign (confidently wrong: belief propagation fails), while the weak remainder is correct.
    /// OSD then recovers the codeword from the weak bits alone, and the gate sees <c>nhard</c> = the number of wrong strong bits.
    /// </summary>
    private static float[] NoisyLlrs(byte[] bits, int seed, float weakMagnitude)
    {
        var rng = new Random(seed);
        var order = Enumerable.Range(0, N).OrderBy(_ => rng.Next()).ToArray();
        var llr = new float[N];
        for (int r = 0; r < N; r++)
        {
            int i = order[r];
            float truthSign = bits[i] == 1 ? 1f : -1f;
            if (r < StrongBitCount)
            {
                float mag = StrongMagnitude * (1f + 0.25f * (float)rng.NextDouble());
                llr[i] = (r < StrongWrongBits ? -truthSign : truthSign) * mag;
            }
            else llr[i] = truthSign * weakMagnitude * (0.5f + (float)rng.NextDouble());
        }
        return llr;
    }

    private static int ChannelHardErrors(byte[] bits, float[] llr)
    {
        int e = 0;
        for (int i = 0; i < N; i++) if ((llr[i] > 0f ? 1 : 0) != bits[i]) e++;
        return e;
    }

    /// <summary>Vectors on which BP fails but OSD, on the corrected path, finds the codeword.</summary>
    private static List<(int Seed, float[] Llr, int Flips)> FindOsdOnlyVectors(LdpcDecodeLlrs fn, byte[] bits)
    {
        var found = new List<(int, float[], int)>();
        Ft8LibInterop.SetOsdSignFix(1);
        foreach (float sigma in new[] { 0.3f, 0.5f })
            for (int seed = 1; seed <= 300 && found.Count < 5; seed++)
            {
                var llr = NoisyLlrs(bits, seed, sigma);
                var r = Decode(fn, llr);
                // OSD can also land on a DIFFERENT CRC-valid codeword (a chance hit the weak gate lets through);
                // the test wants the vectors where the corrected path recovers the TRUE one.
                if (r.Rc == 0 && r.Path == 1 && r.CrcOk == 1 && MessageBits(r.A91).SequenceEqual(MessageBits(PayloadBytes(bits))))
                    found.Add((seed, llr, ChannelHardErrors(bits, llr)));
            }
        return found;
    }

    /// <summary>The 77 message bits of an a91 buffer (bytes 0-8 and the top 5 bits of byte 9); the CRC area is not compared.</summary>
    private static byte[] MessageBits(byte[] a91)
    {
        var m = new byte[10];
        Array.Copy(a91, m, 10);
        m[9] &= 0xF8;
        return m;
    }

    private static byte[] PayloadBytes(byte[] bits)
    {
        var a91 = new byte[12];
        for (int i = 0; i < PayloadBitCount; i++) if (bits[i] == 1) a91[i / 8] |= (byte)(0x80 >> (i % 8));
        return a91;   // the native a91 carries the 77 message bits only; its CRC bits are zeroed
    }

    // ── 3.1 sign test, including the gate ───────────────────────────────────

    [Fact(DisplayName = "FR-084: OSD with the sign fix on accepts the known codeword through its gate; switch off gives no decode")]
    public void SignFix_KnownCodeword_AcceptedWithSwitchOn_NotWithSwitchOff()
    {
        byte[] bits = CodewordBits("Q1OFZ Q9XYZ JO33");
        var fn = LoadExport();

        var vectors = FindOsdOnlyVectors(fn, bits);
        vectors.Should().NotBeEmpty("a noisy vector on which BP fails and corrected OSD succeeds must exist for this test to bite");

        byte[] truth = PayloadBytes(bits);
        foreach (var (seed, llr, flips) in vectors)
        {
            Ft8LibInterop.SetOsdSignFix(1);
            var on = Decode(fn, llr);
            // path 1 = the OSD fallback produced the accepted codeword, i.e. it also passed the gate
            // (nhard <= OsdNhardMax and corr/norm >= OsdCorrThreshold, both read from the SAME corrected array).
            // A gate left on the un-negated array measures agreement with the inverted decisions and rejects this.
            on.Path.Should().Be(1, $"seed {seed}: BP fails here, OSD must carry it, and the gate must accept it");
            on.CrcOk.Should().Be(1);
            on.LdpcErrors.Should().Be(0, "the fallback resets the BP error count when it succeeds");
            MessageBits(on.A91).Should().Equal(MessageBits(truth), $"seed {seed}: the payload must be the known one");
            flips.Should().BeLessThanOrEqualTo(OsdNhardMax,
                $"seed {seed}: the injected channel errors bound the accepted nhard, and nhard_max is {OsdNhardMax}");

            Ft8LibInterop.SetOsdSignFix(0);
            var off = Decode(fn, llr);
            // At 0, OSD reads the inverted array: it finds nothing, or (rarely) a chance CRC hit, never the TRUE payload.
            (off.Path == 1 && MessageBits(off.A91).SequenceEqual(MessageBits(truth))).Should().BeFalse(
                $"seed {seed}: with the switch at 0 the true payload must not be recovered");
        }
    }

    [Fact(DisplayName = "FR-084: the gate rejects a corrected OSD decode when its threshold exceeds the true agreement")]
    public void SignFix_GateReadsTheCorrectedArray_ThresholdOfOneRejects()
    {
        // corr/norm of a correct codeword on its own channel LLRs is < 1 when the channel is noisy, so a
        // threshold of 1.0 must reject. If the gate read the un-negated array corr would be NEGATIVE and the
        // accept test above would already have failed; this pins the other side: the gate is live, not bypassed.
        byte[] bits = CodewordBits("Q1OFZ Q9XYZ JO33");
        var fn = LoadExport();
        var vectors = FindOsdOnlyVectors(fn, bits);
        vectors.Should().NotBeEmpty();

        Ft8LibInterop.SetOsdSignFix(1);
        Ft8LibInterop.SetDecodeParams(10, 1.0f, OsdNhardMax);
        foreach (var (seed, llr, _) in vectors)
            Decode(fn, llr).Path.Should().NotBe(1, $"seed {seed}: corr/norm is below 1.0, the gate must reject");
    }

    // ── 3.3 the all-ones word ───────────────────────────────────────────────

    [Fact(DisplayName = "FR-084: an all-ones channel is not accepted as a codeword (switch on)")]
    public void AllOnesWord_IsNotAccepted()
    {
        const int switchValue = 1;   // at 0 the inverted OSD+gate accept a chance CRC hit: that is the defect itself
        var fn = LoadExport();
        Ft8LibInterop.SetOsdSignFix(switchValue);
        var llr = new float[N];
        var rng = new Random(7);
        for (int i = 0; i < N; i++) llr[i] = 1.0f + 0.2f * (float)rng.NextDouble();   // every bit says 1, nonzero variance
        var r = Decode(fn, llr);
        r.Rc.Should().Be(0);
        r.CrcOk.Should().Be(0);
        r.Path.Should().Be(-1);
    }

    // ── R6 diagnostics ──────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-084: OSD gate diagnostics are numbers in range, reset per call, and fill with no message text")]
    public void OsdDiagnostics_AreWellFormedAndResetPerCall()
    {
        _ = Ft8LibInterop.GetOsdSignFix();
        var rng = new Random(99);
        var noise = new float[180_000];
        for (int i = 0; i < noise.Length; i++) noise[i] = (float)(rng.NextDouble() * 2 - 1);
        float[] pcm = Ft8Decoder.NormalisePcm(noise, 0.20f);

        Ft8LibInterop.SetOsdSignFix(1);
        _ = Ft8LibInterop.DecodeAll(pcm);
        var d = Ft8LibInterop.GetLastOsdDiag(2);
        d.Nhard.Length.Should().Be(Math.Min(d.TotalAccepts, Ft8LibInterop.OsdDiagCapacity));
        d.CorrNorm.Length.Should().Be(d.Nhard.Length);
        d.Nhard.All(v => v >= 0 && v <= N).Should().BeTrue();
        d.CorrNorm.All(v => v >= -1.0001f && v <= 1.0001f).Should().BeTrue();
        d.Depth.All(v => v == OsdDepth).Should().BeTrue();
        d.Batch.All(v => v == 0 || v == 1).Should().BeTrue();
        d.RejectNhard.Concat(d.RejectCorr).All(v => v >= 0).Should().BeTrue();

        // The next call starts from zero, whatever the previous one recorded.
        _ = Ft8LibInterop.DecodeAll(new float[180_000]);
        var e = Ft8LibInterop.GetLastOsdDiag(2);
        e.TotalAccepts.Should().Be(0);
        e.RejectNhard.Concat(e.RejectCorr).All(v => v == 0).Should().BeTrue();
    }

    // ── 3.2 no bare callers ─────────────────────────────────────────────────

    [Fact(DisplayName = "FR-084: every osd_decode caller is preceded by osd_prepare_llr on the same array")]
    public void NoBareOsdDecodeCallers()
    {
        string text = File.ReadAllText(FindRepoFile("native/ft8_lib_build/patched/ft8/decode.c"));
        var lines = text.Split('\n');
        var call = new Regex(@"\bosd_decode\s*\(\s*(\w+)\s*,");
        var def  = new Regex(@"^\s*static\s+int\s+osd_decode\s*\(");
        int callers = 0;
        for (int i = 0; i < lines.Length; i++)
        {
            if (!lines[i].Contains("osd_decode(")) continue;
            string t = lines[i].TrimStart();
            if (def.IsMatch(lines[i]) || t.StartsWith("*") || t.StartsWith("//") || t.StartsWith("/*")) continue;
            var m = call.Match(lines[i]);
            m.Success.Should().BeTrue($"decode.c:{i + 1}: an osd_decode( call must pass a named array first");
            callers++;
            string arr = m.Groups[1].Value;
            string window = string.Join("\n", lines.Skip(Math.Max(0, i - 3)).Take(3));
            window.Should().MatchRegex($@"osd_prepare_llr\(\s*{arr}\s*\)",
                $"decode.c:{i + 1}: osd_decode({arr}, ...) must be preceded by osd_prepare_llr({arr}) so OSD and its gate read the SAME corrected array");
        }
        callers.Should().Be(3, "ftx_decode_candidate, ft8_ldpc_decode_llrs' implementation and the AP path are the three callers");
    }

    // ── 3.5 interop round trip ──────────────────────────────────────────────

    [Fact(DisplayName = "FR-084: Ft8LibInterop set/get round trip, default is 1")]
    public void Interop_RoundTrip()
    {
        Ft8LibInterop.SetOsdSignFix(0);
        Ft8LibInterop.GetOsdSignFix().Should().Be(0);
        Ft8LibInterop.SetOsdSignFix(1);
        Ft8LibInterop.GetOsdSignFix().Should().Be(1);
        Ft8LibInterop.SetOsdSignFix(5);
        Ft8LibInterop.GetOsdSignFix().Should().Be(1, "any non-zero value is stored as 1");
    }

    [Fact(DisplayName = "FR-084: Ft8Decoder forwards SetOsdSignFix / GetOsdSignFix to the interop")]
    public void Decoder_ForwardsToInterop()
    {
        var fake = new RecordingInterop();
        var decoder = new Ft8Decoder(new FakeClock(new DateTime(2026, 10, 8, 12, 0, 0, DateTimeKind.Utc)), null, fake);
        decoder.GetOsdSignFix().Should().Be(1);
        decoder.SetOsdSignFix(0);
        fake.Last.Should().Be(0);
        decoder.GetOsdSignFix().Should().Be(0);
    }

    private sealed class RecordingInterop : IFt8NativeInterop
    {
        public int Last { get; private set; } = 1;
        public int MaxDecodePasses => 2;
        public Ft8NativeResult[] DecodeAll(float[] pcm) => [];
        public int[] GetLastPassCounts(int maxPasses) => new int[maxPasses];
        public int[] GetLastCandidateCounts(int maxPasses) => new int[maxPasses];
        public float GetLastNoiseFloorDb() => 0f;
        public int GetHashTableRejectCount() => 0;
        public int GetH12DisplayingCount() => 0;
        public int GetH12AmbiguousCount() => 0;
        public int GetH12DivergentCount() => 0;
        public int GetH12SuppressedCount() => 0;
        public (float[] MeanAbs, float[] PrenormVariance, int[] FailCount) GetLastLlrStats(int maxPasses)
            => (new float[maxPasses], new float[maxPasses], new int[maxPasses]);
        public void SetApBits(byte[] mycallBits, byte[] hiscallBits) { }
        public void SetDecodeParams(int kMinScorePass2, float osdCorrThreshold, int osdNhardMax) { }
        public (float DeltaFreqHz, float DeltaTimeS, float SyncScore, int CoarseDtSamp, int FineDtSamp) RefineCandidate(
            float[] pcm, int coarseFreqHz, float coarseTimeOffsetS) => (0f, 0f, 0f, 0, 0);
        public float[] CoherentLlrAt(float[] pcm, float freqHz, float timeOffsetS) => new float[174];
        public (float[] SignalDb, float[] LocalNoiseDb) GetLastSnrTerms(int maxDecoded)
            => (Array.Empty<float>(), Array.Empty<float>());
        public byte[] EncodeMessage(string message) => new byte[79];
        public (float[] Re, float[] Im) SubfeasComputeAnalytic(float[] pcm) => (new float[180_000], new float[180_000]);
        public (int ReturnCode, float[] Shat) SubfeasFitSignal(
            float[] xARe, float[] xAIm, byte[] tones, float decodedDtS, float decodedFreqHz, IntPtr cancelFlag)
            => (0, new float[180_000]);
        public void SetOsdSignFix(int enabled) => Last = enabled != 0 ? 1 : 0;
        public int GetOsdSignFix() => Last;
    }

    // ── 3.6 not configurable ────────────────────────────────────────────────

    [Fact(DisplayName = "FR-084: no config record, settings page, API model or daemon code carries the OSD sign switch")]
    public void SwitchIsNotOperatorReachable()
    {
        string root = Path.GetDirectoryName(FindRepoFile("VERSION"))!;
        var needle = new Regex(@"osd[_-]?sign[_-]?fix", RegexOptions.IgnoreCase);
        var offenders = new List<string>();
        foreach (string dir in new[] { "src/OpenWSFZ.Abstractions", "src/OpenWSFZ.Daemon", "src/OpenWSFZ.Web", "web" })
        {
            string full = Path.Combine(root, dir);
            if (!Directory.Exists(full)) continue;
            foreach (string f in Directory.EnumerateFiles(full, "*.*", SearchOption.AllDirectories))
            {
                if (f.Contains($"{Path.DirectorySeparatorChar}bin{Path.DirectorySeparatorChar}") ||
                    f.Contains($"{Path.DirectorySeparatorChar}obj{Path.DirectorySeparatorChar}")) continue;
                string ext = Path.GetExtension(f).ToLowerInvariant();
                if (ext is not (".cs" or ".js" or ".html" or ".json")) continue;
                if (needle.IsMatch(File.ReadAllText(f))) offenders.Add(Path.GetRelativePath(root, f));
            }
        }
        offenders.Should().BeEmpty("the switch is harness-only: not a config key, a UI control or an API field");
    }

    private static string FindRepoFile(string relative)
    {
        string? dir = AppContext.BaseDirectory;
        while (dir != null)
        {
            string candidate = Path.Combine(dir, relative.Replace('/', Path.DirectorySeparatorChar));
            if (File.Exists(candidate)) return candidate;
            dir = Path.GetDirectoryName(dir);
        }
        throw new FileNotFoundException($"{relative} not found above {AppContext.BaseDirectory}");
    }
}

[CollectionDefinition("OsdSignSwitch", DisableParallelization = true)]
public sealed class OsdSignSwitchCollection { }
