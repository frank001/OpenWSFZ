// STRONG-MISS step 2: the probe (spec section 4c + amendment 3 / 4d). QA-owned, no src/ change.
//
// Runs INSIDE the same single process as the replay (the SM-DECODER set is re-derived there, because nothing per message may be
// written to disk, not even a temp file). Everything below runs synchronously on ONE dedicated thread: the probe tap, the armed
// decode and the reads are thread-local in the native library.
//
// Pilot FIRST (SM-P1, SM-P2 bars frozen before the pilot is read): 500 seeded controls fix the WSJT-X -> probe mapping and must be
// found in the window; 500 seeded empty points must not give BP-only CRC hits. If SM-P1 fails the targets are NOT probed.
//
// Positions: the probe's (freq_hz, time_offset_s) are the native result's own axes (FT8Result.dt is computed with the same formula the
// probe inverts; the managed layer only rounds it to 0.1 s), so the mapping is  probe = WSJT-X value + median(OpenWSFZ - WSJT-X)
// per axis over the pilot sample's matched pairs.
//
// HK-037 / NFR-021: aggregates only. Message text and keys exist only in memory. The product's own encoder (ft8_encode_message) is
// used to build the expected payload; encoding is not the stage under test.

using System.Globalization;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using OpenWSFZ.Ft8;

internal static partial class Program
{
    // ---- frozen constants (amendment 3) ----
    private const double FreqStepHz = 3.125;          // K_FREQ_OSR = 2 at the 6.25 Hz tone spacing
    private const double TimeStepS = 0.08;            // K_TIME_OSR = 2 at the 0.16 s symbol period
    private const int WindowFreqSteps = 2, WindowTimeSteps = 2;   // +-6.25 Hz x +-0.16 s = 25 points
    private const int BpIterations = 50;              // K_LDPC_ITERATIONS (production)
    private const int BpOnly = -1;                    // osd_depth < 0 disables the OSD fallback
    private const int PilotControls = 500, PilotNulls = 500, PilotSeed = 20261010;
    private const double P1Min = 0.95, P2Max = 0.01;
    private const int MaxRaw = 200;
    private const double NullFreqMin = 200, NullFreqMax = 2800, NullAvoidHz = 100, NullTimeMin = 0.6, NullTimeMax = 1.2;
    private const double PassbandMinHz = 140.0, ToneSpacingHz = 6.25;   // min_bin = floor(140 * 0.16) = 22
    private const int CodewordBits = 174, A91Bits = 91, PayloadBits = 77, Tones = 79, RawSelfCheck = 10;   // the decoder zeroes the 14 CRC bits after checking them, so payloads are compared on the 77 message bits (crc_ok carries the CRC)

    private static class Native
    {
        private const string Lib = "libft8.dll";
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] public static extern int ft8_extract_llrs_at(float[] pcm, int len, float freq, float toff, float[] out174);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] public static extern int ft8_ldpc_decode_llrs(float[] llr, int maxIters, int osdDepth, byte[]? outA91, out int errs, out int path, out int crcOk);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] public static extern void ft8_set_probe(float freq, float toff);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] public static extern void ft8_clear_probe();
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] public static extern int ft8_get_probe_llrs(int pass, float[] out174);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] public static extern int ft8_get_last_suppression(byte[]? outRecords, int capacity);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] public static extern int ft8_decode_all(float[] pcm, int len, byte[] results, int max);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] public static extern int ft8_encode_message([MarshalAs(UnmanagedType.LPStr)] string msg, byte[] tones, int cap);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] public static extern int ft8_refine_candidate(float[] pcm, int len, int coarseFreq, float coarseToff, out float dF, out float dT, out float sync, out int coarseDt, out int fineDt);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] public static extern int ft8_get_decoder_params(byte[]? outEntries, int capacity);
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)] public static extern unsafe int ft8_get_last_osd_diag(int cap, int* nhard, float* corr, int* depth, int* batch, int* total, int* rejNhard, int* rejCorr, int passCap);
    }

    private static readonly int[] GrayInverse = { 0, 1, 3, 2, 6, 4, 5, 7 };   // tone -> 3-bit value (inverse of kFT8_Gray_map {0,1,3,2,5,6,4,7})

    // ---- reflection into the product's internals (same normalisation and filter as the daemon) ----
    private static Func<float[], float[]>? _normalise;
    private static Func<string, bool>? _plausible;
    private static float _targetRms;

    private static void BindProduct()
    {
        var t = typeof(Ft8Decoder);
        const BindingFlags F = BindingFlags.Static | BindingFlags.NonPublic | BindingFlags.Public;
        var rmsField = t.GetField("PcmNormalisationTargetRms", F) ?? throw new InvalidOperationException("PcmNormalisationTargetRms not found");
        _targetRms = (float)rmsField.GetRawConstantValue()!;
        var norm = t.GetMethod("NormalisePcm", F) ?? throw new InvalidOperationException("NormalisePcm not found");
        _normalise = pcm => (float[])norm.Invoke(null, new object[] { pcm, _targetRms })!;
        var pl = t.GetMethod("IsPlausibleMessage", F) ?? throw new InvalidOperationException("IsPlausibleMessage not found");
        _plausible = s => (bool)pl.Invoke(null, new object?[] { s, null })!;
    }

    // ---- expected payload through the DLL's own encoder ----
    private const int GridRR73 = 32373;   // Maidenhead grid RR73 = (17*18+17)*100+73: prints the same as the RR73 token (32403)

    private static byte[][]? ExpectedA91(string text)
    {
        if (text.Contains("<...>")) return null;                      // unresolved hash: CRC-only
        var tones = new byte[Tones];
        int rc = Native.ft8_encode_message(text, tones, Tones);
        if (rc != Tones) return null;
        var bits = new int[CodewordBits];
        int bi = 0;
        foreach (int sym in Enumerable.Range(7, 29).Concat(Enumerable.Range(43, 29)))
        {
            int v = GrayInverse[tones[sym] & 7];
            bits[bi++] = (v >> 2) & 1; bits[bi++] = (v >> 1) & 1; bits[bi++] = v & 1;
        }
        var a91 = new byte[12];
        for (int i = 0; i < A91Bits; i++) if (bits[i] == 1) a91[i / 8] |= (byte)(0x80 >> (i % 8));
        var lastTok = text.Split(' ', StringSplitOptions.RemoveEmptyEntries)[^1];
        if (lastTok != "RR73") return new[] { a91 };
        // "RR73" is ambiguous in text: the special token (32403) and the grid RR73 (32373) print identically, and the encoder gives only the
        // token. Accept either payload for texts ending in RR73 (found in the smoke test on controls outside the pilot sample; disclosed in the report).
        var alt = (byte[])a91.Clone();
        for (int i = 0; i < 15; i++) { int bit = (GridRR73 >> (14 - i)) & 1; int pos = 59 + i; alt[pos / 8] = (byte)((alt[pos / 8] & ~(0x80 >> (pos % 8))) | (bit << (7 - pos % 8))); }
        return new[] { a91, alt };
    }

    private static int Bits(byte[] x, int from, int n) { int v = 0; for (int i = 0; i < n; i++) v = (v << 1) | ((x[(from + i) / 8] >> (7 - (from + i) % 8)) & 1); return v; }
    private static string FieldClass(byte[] x)
    {
        int g = Bits(x, 59, 15); string gc = g < 32400 ? "grid" : g == 32402 ? "RRR" : g == 32403 ? "RR73" : g == 32404 ? "73" : g >= 32435 ? "report" : $"special{g}";
        return $"R={Bits(x, 58, 1)} g15={gc} i3={Bits(x, 74, 3)} ipa={Bits(x, 28, 1)} ipb={Bits(x, 57, 1)}";
    }

    private static bool SameA91(byte[] x, byte[][] ys) => ys.Any(y => SameA91(x, y));

    private static bool SameA91(byte[] x, byte[] y)
    {
        for (int i = 0; i < PayloadBits; i++)
            if (((x[i / 8] >> (7 - i % 8)) & 1) != ((y[i / 8] >> (7 - i % 8)) & 1)) return false;
        return true;
    }

    // ---- one lattice point ----
    private readonly record struct Pt(int Df, int Dt);
    private static IEnumerable<Pt> WindowPoints()
    {
        var l = new List<Pt>();
        for (int i = -WindowFreqSteps; i <= WindowFreqSteps; i++)
            for (int j = -WindowTimeSteps; j <= WindowTimeSteps; j++) l.Add(new Pt(i, j));
        return l.OrderBy(p => Math.Abs(p.Df) + Math.Abs(p.Dt)).ThenBy(p => p.Df).ThenBy(p => p.Dt);
    }

    private sealed class WinResult
    {
        public int Valid, CrcHits, VerifiedHits, VerifiedPrimary;      // points with rc 0; BP-only crc_ok points; of those payload-equal (or counted as verified when not packable)
        public Pt? FirstHit; public int MinPayloadDiff = 999; public string DiffPositions = ""; public string FieldDbg = "";                           // the hit nearest the centre (verified where packable, else CRC)
        public bool Packable;
    }

    private static WinResult ScanWindow(float[] pcm, double f0, double t0, byte[][]? expected)
    {
        var res = new WinResult { Packable = expected != null };
        var llr = new float[CodewordBits];
        var a91 = new byte[12];
        foreach (var p in WindowPoints())
        {
            int rc = Native.ft8_extract_llrs_at(pcm, pcm.Length, (float)(f0 + p.Df * FreqStepHz), (float)(t0 + p.Dt * TimeStepS), llr);
            if (rc != 0) continue;
            res.Valid++;
            int dec = Native.ft8_ldpc_decode_llrs(llr, BpIterations, BpOnly, a91, out _, out _, out int crc);
            if (dec != 0 || crc != 1) continue;
            res.CrcHits++;
            if (expected != null) { foreach (var e in expected) { int dd = 0; for (int i = 0; i < PayloadBits; i++) if (((a91[i / 8] >> (7 - i % 8)) & 1) != ((e[i / 8] >> (7 - i % 8)) & 1)) dd++; if (dd < res.MinPayloadDiff) { res.FieldDbg = FieldClass(a91) + " vs expected " + FieldClass(e); res.MinPayloadDiff = dd; res.DiffPositions = string.Join(",", Enumerable.Range(0, PayloadBits).Where(i => ((a91[i / 8] >> (7 - i % 8)) & 1) != ((e[i / 8] >> (7 - i % 8)) & 1))); } } }
            bool ok = expected == null || SameA91(a91, expected);
            if (ok) { res.VerifiedHits++; res.FirstHit ??= p; if (expected == null || SameA91(a91, expected[0])) res.VerifiedPrimary++; }
        }
        return res;
    }

    // ---- armed native decode ----
    private sealed class Armed
    {
        public int RawCount = -99; public int ProbeErr0 = -99, ProbeErr1 = -99;
        public List<string> RawKeys = new(); public List<bool> RawPlausible = new(); public List<(int F, float Dt)> RawPos = new();
        public bool Pass0Decodes, Pass1Decodes;       // BP-only on the captured pass LLRs (payload-verified where packable)
        public int SuppNearPoint; public double MinFactorNear = 1.0;
        public int RejNhard0, RejNhard1, RejCorr0, RejCorr1;
    }

    private static unsafe Armed ArmedDecode(float[] pcm, double f, double t, byte[][]? expected)
    {
        var a = new Armed();
        Native.ft8_set_probe((float)f, (float)t);
        var buf = new byte[48 * MaxRaw];
        a.RawCount = Native.ft8_decode_all(pcm, pcm.Length, buf, MaxRaw);
        if (a.RawCount >= 0)
            for (int i = 0; i < a.RawCount; i++)
            {
                int o = i * 48 + 12;
                int len = 0; while (len < 36 && buf[o + len] != 0) len++;
                string msg = Encoding.ASCII.GetString(buf, o, len).TrimEnd();
                a.RawKeys.Add(KeyOf(msg)); a.RawPlausible.Add(_plausible!(msg)); a.RawPos.Add((BitConverter.ToInt32(buf, i * 48), BitConverter.ToSingle(buf, i * 48 + 4)));
            }
        var l0 = new float[CodewordBits]; var l1 = new float[CodewordBits];
        a.ProbeErr0 = Native.ft8_get_probe_llrs(0, l0); a.ProbeErr1 = Native.ft8_get_probe_llrs(1, l1);
        var a91 = new byte[12];
        bool Dec(float[] l) => Native.ft8_ldpc_decode_llrs(l, BpIterations, BpOnly, a91, out _, out _, out int crc) == 0 && crc == 1 && (expected == null || SameA91(a91, expected));
        if (a.ProbeErr0 == 0) a.Pass0Decodes = Dec(l0);
        if (a.ProbeErr1 == 0) a.Pass1Decodes = Dec(l1);
        int n = Native.ft8_get_last_suppression(null, 0);
        if (n > 0)
        {
            var rec = new byte[24 * Math.Min(n, 400)];
            int got = Math.Min(n, 400); Native.ft8_get_last_suppression(rec, got);
            for (int i = 0; i < got; i++)
            {
                int fo = BitConverter.ToInt32(rec, i * 24), fs = BitConverter.ToInt32(rec, i * 24 + 8);
                float factor = BitConverter.ToSingle(rec, i * 24 + 20);
                double hz = (Math.Floor(PassbandMinHz / ToneSpacingHz) + fo + fs / 2.0) * ToneSpacingHz;
                if (Math.Abs(hz - f) <= ToneSpacingHz) { a.SuppNearPoint++; a.MinFactorNear = Math.Min(a.MinFactorNear, factor); }
            }
        }
        var rn = new int[2]; var rc2 = new int[2]; int tot;
        int[] nh = new int[256]; float[] cr = new float[256]; int[] dp = new int[256]; int[] bt = new int[256];
        fixed (int* pn = nh) fixed (float* pc = cr) fixed (int* pd = dp) fixed (int* pb = bt) fixed (int* prn = rn) fixed (int* prc = rc2)
            Native.ft8_get_last_osd_diag(256, pn, pc, pd, pb, &tot, prn, prc, 2);
        a.RejNhard0 = rn[0]; a.RejNhard1 = rn[1]; a.RejCorr0 = rc2[0]; a.RejCorr1 = rc2[1];
        return a;
    }

    private static double Median(List<double> x) { var s = x.OrderBy(v => v).ToList(); return s.Count == 0 ? double.NaN : s.Count % 2 == 1 ? s[s.Count / 2] : 0.5 * (s[s.Count / 2 - 1] + s[s.Count / 2]); }

    private static readonly string[] ImplausibleCandidates = {
        "Q1ABC", "Q2XYZ", "Q1ABC Q2XYZ Q3AAA Q4BBB", "Q1ABC Q2XYZ -12 EXTRA", "Q1ABC Q2XYZ ZZ99", "Q1ABC Q2XYZ SS55", "Q1ABC Q2XYZ R-99",
        "Q1ABC Q2XYZ RR99", "CQ", "Q1ABC Q2XYZ Q5CCC", "QQQQ QQQQ QQQQ", "Q1ABC Q2XYZ XX00", "Q1ABC Q2XYZ -88", "Q1ABC Q2XYZ R+99", "Q9ZZZ Q8YYY Q7XXX" };

    // ---- self checks (run before the pilot; any failure aborts) ----
    internal static SortedDictionary<string, object> ProbeSelfChecks(StringBuilder? log)
    {
        var r = new SortedDictionary<string, object>();
        // Gray inversion: encode a synthetic message, rebuild the codeword, feed it back as strong LLRs, BP-only must return the same a91
        var exp = (ExpectedA91("CQ Q1ABC EN37") ?? throw new InvalidOperationException("encoder could not pack the synthetic CQ"))[0];
        // rebuild the codeword bits from the tones again to make LLRs
        var tones = new byte[Tones]; Native.ft8_encode_message("CQ Q1ABC EN37", tones, Tones);
        var llr = new float[CodewordBits]; int bi = 0;
        foreach (int sym in Enumerable.Range(7, 29).Concat(Enumerable.Range(43, 29)))
        {
            int v = GrayInverse[tones[sym] & 7];
            foreach (int sh in new[] { 2, 1, 0 }) llr[bi++] = ((v >> sh) & 1) == 1 ? 8f : -8f;       // positive LLR = bit 1 (extractor and BP convention)
        }
        var a91 = new byte[12];
        int rc = Native.ft8_ldpc_decode_llrs(llr, BpIterations, BpOnly, a91, out int dbgErrs, out int dbgPath, out int crc);
        r["dbg_bp_errs"] = dbgErrs; r["dbg_path"] = dbgPath; r["dbg_tones"] = string.Join("", tones.Select(t => (t & 7).ToString()));
        r["gray_inversion_roundtrip"] = rc == 0 && crc == 1 && SameA91(a91, exp);
        int diff = 0; for (int i = 0; i < PayloadBits; i++) if (((a91[i / 8] >> (7 - i % 8)) & 1) != ((exp[i / 8] >> (7 - i % 8)) & 1)) diff++;
        r["dbg_diff_idx"] = string.Join(",", Enumerable.Range(0, PayloadBits).Where(i => ((a91[i / 8] >> (7 - i % 8)) & 1) != ((exp[i / 8] >> (7 - i % 8)) & 1))); r["dbg_ldpc_rc"] = rc; r["dbg_crc_ok"] = crc; r["dbg_a91_diff_bits"] = diff;
        // implausible texts: choose the first 10 that read FALSE, report how many candidates read FALSE
        int falseCount = ImplausibleCandidates.Count(s => !_plausible!(s));
        r["implausible_candidates_reading_false"] = falseCount;
        r["implausible_10_all_false"] = falseCount >= RawSelfCheck;
        // a plausible synthetic message must read TRUE (the predicate is not constant FALSE)
        r["plausible_synthetic_reads_true"] = _plausible!("CQ Q1ABC EN37") && _plausible!("Q1ABC Q2XYZ -12");
        return r;
    }


    private static string LastTokClass(string t)
    {
        var tk = t.Split(' ', StringSplitOptions.RemoveEmptyEntries); string l = tk[^1];
        return l == "RR73" || l == "RRR" || l == "73" ? l : System.Text.RegularExpressions.Regex.IsMatch(l, "^R?[+-][0-9]{2}$") ? (l.StartsWith("R") ? "R-report" : "report") : System.Text.RegularExpressions.Regex.IsMatch(l, "^[A-R]{2}[0-9]{2}$") ? "grid" : "other";
    }

    // ---- smoke test of the machinery (NOT the pilot): controls OUTSIDE the seeded pilot sample, empty points on another seed ----
    private static SortedDictionary<string, object> ProbeSmoke(Derived d, string owsWavDir)
    {
        BindProduct();
        var res = new SortedDictionary<string, object>();
        var owsBy = new Dictionary<(string, string, int), Row>();
        foreach (var o in d.Ows) owsBy[(o.Ts, o.Key, o.KeyRank)] = o;
        var ctl = d.Controls.OrderBy(c => c.Ts, StringComparer.Ordinal).ThenBy(c => c.Key, StringComparer.Ordinal).ThenBy(c => c.KeyRank).ToList();
        var rng = new Random(PilotSeed);
        for (int i = ctl.Count - 1; i > 0; i--) { int j = rng.Next(i + 1); (ctl[i], ctl[j]) = (ctl[j], ctl[i]); }
        var outside = ctl.Skip(PilotControls).Take(5).ToList();
        double offF = 0.0, offT = 0.6;      // fixed smoke offsets (the real run derives them from the pilot sample)
        int hits = 0, armedOk = 0, rawIn = 0, refineOk = 0, enc = 0;
        foreach (var c in outside)
        {
            var pcm = _normalise!(ReadWav(Path.Combine(owsWavDir, c.Ts + ".wav")));
            var exp = ExpectedA91(c.Text); if (exp != null) enc++;
            var w = ScanWindow(pcm, c.F + offF, c.Dt + offT, exp); if (w.VerifiedHits > 0) hits++;
            var ow = owsBy[(c.Ts, c.Key, c.KeyRank)];
            res[$"dbg_ctl_{c.Ts}"] = $"valid={w.Valid} crc={w.CrcHits} ver={w.VerifiedHits} packable={w.Packable} minPayloadDiffBits={w.MinPayloadDiff} diffAt=[{w.DiffPositions}] fields={w.FieldDbg} lastTok={LastTokClass(c.Text)} snr={c.Snr} wsjF={c.F} wsjDt={c.Dt} owsF={ow.F} owsDt={ow.Dt} form={FormGroup(c.Text)}";
            var a = ArmedDecode(pcm, c.F + offF, c.Dt + offT, exp); if (a.RawCount >= 0 && a.ProbeErr0 == 0) armedOk++; if (a.RawKeys.Contains(c.Key)) rawIn++;
            { int ix = a.RawKeys.IndexOf(c.Key); res[$"dbg_raw_{c.Ts}"] = ix < 0 ? "none" : $"rawF={a.RawPos[ix].F} rawDt={a.RawPos[ix].Dt:F2} centreF={c.F + offF} centreDt={c.Dt + offT:F2} firstHit={(w.FirstHit is { } fh ? $"df{fh.Df},dt{fh.Dt}" : "none")}"; }
            if (Native.ft8_refine_candidate(pcm, pcm.Length, (int)Math.Round(c.F + offF), (float)(c.Dt + offT), out _, out _, out _, out _, out _) == 0) refineOk++;
        }
        var rng2 = new Random(PilotSeed + 99); int nullHits = 0;
        for (int i = 0; i < 5; i++)
        {
            string ts = d.Cycles[rng2.Next(d.Cycles.Count)];
            var pcm = _normalise!(ReadWav(Path.Combine(owsWavDir, ts + ".wav")));
            if (ScanWindow(pcm, 200 + rng2.NextDouble() * 2600, 0.6 + rng2.NextDouble() * 0.6, null).CrcHits > 0) nullHits++;
        }
        Native.ft8_clear_probe();
        res["smoke_controls"] = 5; res["smoke_window_hits"] = hits; res["smoke_armed_ok"] = armedOk; res["smoke_raw_contains_key"] = rawIn;
        res["smoke_refine_ok"] = refineOk; res["smoke_packable"] = enc; res["smoke_null_hits"] = nullHits;
        return res;
    }

    // ---- the probe ----
    private sealed class ProbeInput
    {
        public Derived D = null!;
        public List<Row> Targets = new();             // SM-DECODER set, in T order
        public string OwsWavDir = "";
        public int Nhard;
        public bool Profile;                          // follow-up B: bit-error profile of the P-WEAK targets (BitProfile.cs)
    }

    private static SortedDictionary<string, object> RunProbe(ProbeInput inp, ReplayLog log)
    {
        BindProduct();
        var d = inp.D;
        var res = new SortedDictionary<string, object>();
        res["self_checks"] = ProbeSelfChecks(null);
        var sc = (SortedDictionary<string, object>)res["self_checks"];
        if (!(bool)sc["gray_inversion_roundtrip"] || !(bool)sc["implausible_10_all_false"] || !(bool)sc["plausible_synthetic_reads_true"])
        { res["ABORT"] = "self-check failed"; return res; }

        // decoder parameter readback inside this process
        int nEntries = Native.ft8_get_decoder_params(null, 0);
        var pbuf = new byte[72 * nEntries];
        Native.ft8_get_decoder_params(pbuf, nEntries);
        double Param(string name)
        {
            for (int i = 0; i < nEntries; i++)
            {
                int len = 0; while (len < 48 && pbuf[i * 72 + len] != 0) len++;
                if (Encoding.ASCII.GetString(pbuf, i * 72, len) == name) return BitConverter.ToDouble(pbuf, i * 72 + 48);
            }
            return double.NaN;
        }
        var pr = new SortedDictionary<string, object>();
        for (int i = 0; i < nEntries; i++)
        {
            int len = 0; while (len < 48 && pbuf[i * 72 + len] != 0) len++;
            string nm = Encoding.ASCII.GetString(pbuf, i * 72, len);
            if (nm.Contains("supp", StringComparison.OrdinalIgnoreCase) || nm.Contains("osd", StringComparison.OrdinalIgnoreCase) || nm.Contains("score", StringComparison.OrdinalIgnoreCase))
                pr[nm] = BitConverter.ToDouble(pbuf, i * 72 + 48);
        }
        res["decoder_params_in_process"] = pr;
        if (Param("osd_nhard_max") != inp.Nhard) { res["ABORT"] = "osd_nhard_max readback mismatch"; return res; }

        string Wav(string ts) => Path.Combine(inp.OwsWavDir, ts + ".wav");
        float[] Pcm(string ts) => _normalise!(ReadWav(Wav(ts)));

        // ---- pilot: controls ----
        var owsBy = new Dictionary<(string, string, int), Row>();
        foreach (var o in d.Ows) owsBy[(o.Ts, o.Key, o.KeyRank)] = o;
        var ctl = d.Controls.OrderBy(c => c.Ts, StringComparer.Ordinal).ThenBy(c => c.Key, StringComparer.Ordinal).ThenBy(c => c.KeyRank).ToList();
        var rng = new Random(PilotSeed);
        for (int i = ctl.Count - 1; i > 0; i--) { int j = rng.Next(i + 1); (ctl[i], ctl[j]) = (ctl[j], ctl[i]); }
        var sample = ctl.Take(PilotControls).ToList();
        var dF = new List<double>(); var dT = new List<double>();
        foreach (var c in sample) { var o = owsBy[(c.Ts, c.Key, c.KeyRank)]; dF.Add(o.F - c.F); dT.Add(o.Dt - c.Dt); }
        double offF = Median(dF), offT = Median(dT);
        res["mapping_frozen"] = new SortedDictionary<string, object> { ["offset_freq_hz"] = offF, ["offset_time_s"] = offT, ["sample"] = sample.Count, ["seed"] = PilotSeed };

        // follow-up B bookkeeping
        var bcw = new List<BitProf>(); var bnw = new List<BitProf>(); var btw = new List<BitProf>();
        var bc = new SortedDictionary<string, object>();
        int cwDecoded = 0, cwHash = 0, cwUnpack = 0, cwNoPt = 0, portMismatch = 0, rtFail = 0, cwAltWins = 0, nwAltWins = 0, twAltWins = 0;
        int twHash = 0, twUnpack = 0, twNoPt = 0, nwNoPt = 0;
        var sampleCws = new List<int[]>?[sample.Count];
        List<int[]>? Ecw(string text, out bool hash)
        {
            var l = ExpectedCodewords(text, out hash);
            if (l != null && !CodewordFromPayload(l[0].Take(PayloadBits).ToArray()).SequenceEqual(l[0])) portMismatch++;
            return l;
        }
        var winHist = new SortedDictionary<string, int>(StringComparer.Ordinal);
        int p1Hit = 0, p1Crc = 0, p1AltOnly = 0; var ctlSync = new List<double>();
        for (int si = 0; si < sample.Count; si++) if (inp.Profile) sampleCws[si] = Ecw(sample[si].Text, out _);
        var sampleIdx = new Dictionary<Row, int>(); for (int si = 0; si < sample.Count; si++) sampleIdx[sample[si]] = si;
        foreach (var g in sample.GroupBy(c => c.Ts).OrderBy(g => g.Key, StringComparer.Ordinal))
        {
            var pcm = Pcm(g.Key);
            foreach (var c in g)
            {
                var w = ScanWindow(pcm, c.F + offF, c.Dt + offT, ExpectedA91(c.Text));
                if (inp.Profile && w.VerifiedHits > 0)
                {
                    cwDecoded++;
                    var cws = sampleCws[sampleIdx[c]];
                    if (cws == null) { if (c.Text.Contains("<...>")) cwHash++; else cwUnpack++; }
                    else
                    {
                        if (cws.Any(x => !SaturatedRoundTrip(x))) rtFail++;
                        var bp = ProfileWindow(pcm, c.F + offF, c.Dt + offT, cws);
                        if (!bp.Scored) cwNoPt++; else { if (bp.Alt == 1) cwAltWins++; bcw.Add(bp); }
                    }
                }
                if (w.CrcHits > 0) p1Crc++;
                if (w.VerifiedHits > 0 && w.VerifiedPrimary == 0) p1AltOnly++;
                if (w.VerifiedHits > 0) { p1Hit++; var p = w.FirstHit!.Value; string k = $"df{p.Df:+0;-0;0},dt{p.Dt:+0;-0;0}"; winHist[k] = winHist.GetValueOrDefault(k) + 1; }
                if (Native.ft8_refine_candidate(pcm, pcm.Length, (int)Math.Round(c.F + offF), (float)(c.Dt + offT), out _, out _, out float sync, out _, out _) == 0) ctlSync.Add(sync);
            }
        }
        res["SM-P1"] = new SortedDictionary<string, object> { ["controls_found_in_window"] = Share(p1Hit, sample.Count), ["crc_only_any_hit"] = Share(p1Crc, sample.Count), ["controls_found_only_via_grid_RR73_alternative"] = p1AltOnly,
            ["bar_min_pct"] = 100 * P1Min, ["pass"] = (double)p1Hit / sample.Count >= P1Min, ["winning_point_histogram"] = winHist };
        if ((double)p1Hit / sample.Count < P1Min) { res["STOPPED"] = "SM-P1 failed: the targets are not probed (HK-026)"; return res; }
        ctlSync.Sort();
        double sy5 = ctlSync[(int)(0.05 * (ctlSync.Count - 1))], sy95 = ctlSync[(int)(0.95 * (ctlSync.Count - 1))];

        // ---- pilot: empty points ----
        var occ = new Dictionary<string, List<double>>();
        foreach (var r in d.Ows.Concat(d.Wsj)) { if (!occ.TryGetValue(r.Ts, out var l)) occ[r.Ts] = l = new(); l.Add(r.F); }
        var rng2 = new Random(PilotSeed + 1);
        int nullHits = 0, nulls = 0;
        var nullPts = new List<(string Ts, double F, double T)>();
        while (nullPts.Count < PilotNulls)
        {
            string ts = d.Cycles[rng2.Next(d.Cycles.Count)];
            double f = NullFreqMin + rng2.NextDouble() * (NullFreqMax - NullFreqMin), t = NullTimeMin + rng2.NextDouble() * (NullTimeMax - NullTimeMin);
            if (occ[ts].Any(x => Math.Abs(x - f) < NullAvoidHz)) continue;
            nullPts.Add((ts, f, t));
        }
        foreach (var g in nullPts.GroupBy(n => n.Ts).OrderBy(g => g.Key, StringComparer.Ordinal))
        {
            var pcm = Pcm(g.Key);
            foreach (var n in g) { nulls++; if (ScanWindow(pcm, n.F, n.T, null).CrcHits > 0) nullHits++; }
        }
        if (inp.Profile)
        {
            var packList = Enumerable.Range(0, sample.Count).Where(i => sampleCws[i] != null).ToList();
            var rng3 = new Random(NullCodewordSeed);
            var assigned = nullPts.Select(_ => sampleCws[packList[rng3.Next(packList.Count)]]!).ToList();
            var idxOf = Enumerable.Range(0, nullPts.Count).GroupBy(i => nullPts[i].Ts).OrderBy(g => g.Key, StringComparer.Ordinal);
            foreach (var g in idxOf)
            {
                var pcm = Pcm(g.Key);
                foreach (int i in g)
                {
                    var bp = ProfileWindow(pcm, nullPts[i].F, nullPts[i].T, assigned[i]);
                    if (!bp.Scored) nwNoPt++; else { if (bp.Alt == 1) nwAltWins++; bnw.Add(bp); }
                }
            }
        }
        bool p2Pass = (double)nullHits / nulls <= P2Max;
        res["SM-P2"] = new SortedDictionary<string, object> { ["null_points_with_bp_only_crc_hit"] = Share(nullHits, nulls), ["bar_max_pct"] = 100 * P2Max, ["pass"] = p2Pass,
            ["note"] = p2Pass ? "" : "SM-P2 FIRED: P-CLEAN is not interpretable until the Architect rules; the targets are probed anyway and reported with this flag" };

        // ---- self-check: raw membership on 10 controls (they must be in the raw output of the native call) ----
        int rawFound = 0, rawTried = 0;
        foreach (var c in sample.Take(RawSelfCheck))
        {
            var pcm = Pcm(c.Ts); var a = ArmedDecode(pcm, c.F + offF, c.Dt + offT, null);
            rawTried++; if (a.RawKeys.Contains(c.Key)) rawFound++;
        }
        res["raw_membership_on_10_controls"] = Share(rawFound, rawTried);
        Native.ft8_clear_probe();

        // ---- targets ----
        int nInv = 0, nFilt = 0, nClean = 0, nCleanVer = 0, nCleanCrcOnly = 0, nWeak = 0, nFiltImplausible = 0, nFiltPlausible = 0;
        int cleanAltOnly = 0, cleanP1 = 0, cleanSupp = 0, weakOutside = 0, weakSyncInRange = 0, weakRefineOk = 0;
        int rej0n = 0, rej1n = 0, rej0c = 0, rej1c = 0;
        var byForm = new SortedDictionary<string, int[]>(StringComparer.Ordinal);   // [INV, FILTER, CLEAN, WEAK]
        var weakBySnr = new SortedDictionary<string, int>(StringComparer.Ordinal);
        foreach (var g in inp.Targets.GroupBy(t => t.Ts).OrderBy(g => g.Key, StringComparer.Ordinal))
        {
            var pcm = Pcm(g.Key);
            foreach (var t in g)
            {
                double f0 = t.F + offF, t0 = t.Dt + offT;
                var exp = ExpectedA91(t.Text);
                var w = ScanWindow(pcm, f0, t0, exp);
                var pt = w.FirstHit ?? new Pt(0, 0);
                var a = ArmedDecode(pcm, f0 + pt.Df * FreqStepHz, t0 + pt.Dt * TimeStepS, exp);
                rej0n += a.RejNhard0; rej1n += a.RejNhard1; rej0c += a.RejCorr0; rej1c += a.RejCorr1;
                int cls; // 0 INVALID, 1 FILTER, 2 CLEAN, 3 WEAK
                if (w.Valid == 0 || a.RawCount < 0) cls = 0;
                else if (a.RawKeys.Contains(t.Key)) cls = 1;
                else if (w.VerifiedHits > 0) cls = 2;
                else cls = 3;
                string fm = FormGroup(t.Text);
                if (!byForm.TryGetValue(fm, out var arr)) byForm[fm] = arr = new int[4];
                arr[cls]++;
                switch (cls)
                {
                    case 0: nInv++; break;
                    case 1:
                        nFilt++; int ix = a.RawKeys.IndexOf(t.Key);
                        if (a.RawPlausible[ix]) nFiltPlausible++; else nFiltImplausible++;
                        break;
                    case 2:
                        nClean++; if (exp != null) nCleanVer++; else nCleanCrcOnly++;
                        if (w.VerifiedPrimary == 0) cleanAltOnly++;
                        if (a.Pass1Decodes) cleanP1++;
                        if (a.SuppNearPoint > 0) cleanSupp++;
                        break;
                    case 3:
                        nWeak++;
                        if (inp.Profile)
                        {
                            var cws = Ecw(t.Text, out bool hh);
                            if (cws == null) { if (hh) twHash++; else twUnpack++; }
                            else
                            {
                                var bp = ProfileWindow(pcm, f0, t0, cws);
                                if (!bp.Scored) twNoPt++;
                                else
                                {
                                    if (bp.Alt == 1) twAltWins++;
                                    bp.Form = FormGroup(t.Text); bp.SnrBin = t.Snr <= 5 ? "1: (0,5] dB" : t.Snr <= 10 ? "2: (5,10] dB" : "3: >10 dB"; bp.DtBin = WsjDtBin(t.Dt);
                                    bool rok = Native.ft8_refine_candidate(pcm, pcm.Length, (int)Math.Round(f0), (float)t0, out _, out _, out float syn, out _, out _) == 0;
                                    bp.SyncCls = !rok ? "refine failed" : (syn >= sy5 && syn <= sy95) ? "sync inside controls P5-P95" : "sync outside controls P5-P95";
                                    btw.Add(bp);
                                }
                            }
                        }
                        string sb = t.Snr <= 5 ? "1: (0,5] dB" : t.Snr <= 10 ? "2: (5,10] dB" : "3: >10 dB"; weakBySnr[sb] = weakBySnr.GetValueOrDefault(sb) + 1;
                        if (Native.ft8_refine_candidate(pcm, pcm.Length, (int)Math.Round(f0), (float)t0, out float df, out float dt, out float sync, out _, out _) == 0)
                        {
                            weakRefineOk++;
                            if (Math.Abs(df) > WindowFreqSteps * FreqStepHz || Math.Abs(dt) > WindowTimeSteps * TimeStepS) weakOutside++;
                            if (sync >= sy5 && sync <= sy95) weakSyncInRange++;
                        }
                        break;
                }
            }
        }
        Native.ft8_clear_probe();
        int total = inp.Targets.Count;
        res["targets"] = total;
        res["classes"] = new SortedDictionary<string, object> {
            ["P-INVALID"] = Share(nInv, total), ["P-FILTER"] = Share(nFilt, total), ["P-CLEAN"] = Share(nClean, total), ["P-WEAK"] = Share(nWeak, total) };
        res["classes_by_form"] = byForm.ToDictionary(kv => kv.Key, kv => (object)new SortedDictionary<string, object> {
            ["n"] = kv.Value.Sum(), ["P-INVALID"] = kv.Value[0], ["P-FILTER"] = kv.Value[1], ["P-CLEAN"] = kv.Value[2], ["P-WEAK"] = kv.Value[3] });
        res["P-FILTER_detail"] = new SortedDictionary<string, object> { ["dropped_as_implausible"] = nFiltImplausible, ["plausible_but_absent_from_product_output"] = nFiltPlausible };
        res["P-CLEAN_detail"] = new SortedDictionary<string, object> { ["payload_verified"] = nCleanVer, ["crc_only"] = nCleanCrcOnly, ["accepted_only_via_grid_RR73_alternative"] = cleanAltOnly,
            ["pass1_llrs_also_decode_bp_only"] = cleanP1, ["pass1_suppression_record_within_1_bin"] = cleanSupp };
        res["P-WEAK_detail"] = new SortedDictionary<string, object> { ["refine_ok"] = weakRefineOk, ["refined_position_outside_window"] = weakOutside,
            ["refined_sync_within_controls_P5_P95"] = weakSyncInRange, ["controls_sync_P5"] = sy5, ["controls_sync_P95"] = sy95, ["by_wsjt_snr"] = weakBySnr };
        res["osd_rejects_summed_over_armed_calls"] = new SortedDictionary<string, object> { ["nhard_pass0"] = rej0n, ["nhard_pass1"] = rej1n, ["corr_pass0"] = rej0c, ["corr_pass1"] = rej1c };
        if (inp.Profile)
        {
            bc["cw_decoded_controls"] = cwDecoded; bc["cw_scored"] = bcw.Count; bc["cw_excluded_unresolved_hash"] = cwHash; bc["cw_excluded_unpackable"] = cwUnpack; bc["cw_no_extractable_point"] = cwNoPt;
            bc["nw_scored"] = bnw.Count; bc["nw_no_extractable_point"] = nwNoPt;
            bc["tw_p_weak_targets"] = nWeak; bc["tw_scored"] = btw.Count; bc["tw_excluded_unresolved_hash"] = twHash; bc["tw_excluded_unpackable"] = twUnpack; bc["tw_no_extractable_point"] = twNoPt;
            bc["grid_RR73_alternative_wins_CW"] = cwAltWins; bc["grid_RR73_alternative_wins_NW"] = nwAltWins; bc["grid_RR73_alternative_wins_TW"] = twAltWins;
            bc["bv2_roundtrip_fail"] = rtFail; bc["bv2_port_mismatch"] = portMismatch;
            res["B"] = BReport(bcw, bnw, btw, bc);
        }
        res["limit"] = "P-FILTER reads the native first-stage call on the original normalised audio only; a target only the managed residual pass could produce is outside every class. The payload check uses the product's own encoder.";
        return res;
    }
}
