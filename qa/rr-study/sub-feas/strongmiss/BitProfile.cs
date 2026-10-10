// STRONG-MISS follow-up B: bit-error profile of the P-WEAK targets against the known codeword (QA-owned, no src/ change).
// Spec: qa/rr-study/2026-10-10-1400-architect-to-qa-spec-strong-miss-followups-a-b.md section B (arch/strong-miss 0625c6fd).
//
// Runs inside RunProbe (same process, same thread): the groups TW (the P-WEAK targets), CW (the pilot controls that decoded) and
// NW (the pilot empty points) are scored the same way: the hard bits (sign of the pass-0 LLR, positive = bit 1) at the BEST of the
// 25 window points are compared with the 174-bit codeword of the message WSJT-X decoded. HK-037: aggregates only.
//
// The codeword comes from the DLL's own encoder (tones, Gray-inverted). For texts ending in RR73 the grid-RR73 alternative is
// built by a C# port of ft8_lib's CRC-14 + encode174 (generator table in LdpcGenerator.cs); that port is checked against the DLL's
// encoder on every primary codeword before anything is scored.

using System.Text;

internal static partial class Program
{
    private const int DataSymbols = 58, BurstSymbols = 15, EdgeSymbols = 10, Crc14Poly = 0x2757, Crc14Width = 14, LdpcM = 83, LdpcKBytes = 12;
    private const float SaturatedLlr = 8f;
    private const double BV2MedianMax = 87, BV3NullMedianMin = 60;
    private const int BurstMinErrors = 10;          // Bst, edge and confident-wrong shares are computed for E >= 10
    private const int NullCodewordSeed = 20261012;

    private static int Crc14(byte[] msg, int numBits)
    {
        int rem = 0, idx = 0;
        for (int b = 0; b < numBits; b++)
        {
            if (b % 8 == 0) { rem ^= msg[idx] << (Crc14Width - 8); idx++; }
            rem = (rem & (1 << (Crc14Width - 1))) != 0 ? (rem << 1) ^ Crc14Poly : rem << 1;
        }
        return rem & ((1 << Crc14Width) - 1);
    }

    private static int Parity8(int x) { x ^= x >> 4; x ^= x >> 2; x ^= x >> 1; return x & 1; }

    // 77 payload bits (as bit array) -> 174-bit codeword, port of ftx_add_crc + encode174
    private static int[] CodewordFromPayload(int[] payload77)
    {
        var a91 = new byte[LdpcKBytes];
        for (int i = 0; i < PayloadBits; i++) if (payload77[i] == 1) a91[i / 8] |= (byte)(0x80 >> (i % 8));
        a91[9] &= 0xF8; a91[10] = 0;
        int crc = Crc14(a91, 96 - Crc14Width);
        a91[9] |= (byte)(crc >> 11); a91[10] = (byte)(crc >> 3); a91[11] = (byte)(crc << 5);
        var cw = new int[CodewordBits];
        for (int i = 0; i < A91Bits; i++) cw[i] = (a91[i / 8] >> (7 - i % 8)) & 1;
        for (int i = 0; i < LdpcM; i++)
        {
            int nsum = 0;
            for (int j = 0; j < LdpcKBytes; j++) nsum ^= Parity8(a91[j] & LdpcGenerator[i][j]);
            cw[A91Bits + i] = nsum;
        }
        return cw;
    }

    // codewords the message may have been sent as; null when the text cannot be packed (unresolved <...>, encoder refusal).
    // [0] = the DLL encoder's (token) codeword; [1] = the grid-RR73 alternative for texts ending in RR73.
    private static List<int[]>? ExpectedCodewords(string text, out bool unresolvedHash)
    {
        unresolvedHash = text.Contains("<...>");
        if (unresolvedHash) return null;
        var tones = new byte[Tones];
        if (Native.ft8_encode_message(text, tones, Tones) != Tones) return null;
        var bits = new int[CodewordBits];
        int bi = 0;
        foreach (int sym in Enumerable.Range(7, 29).Concat(Enumerable.Range(43, 29)))
        {
            int v = GrayInverse[tones[sym] & 7];
            bits[bi++] = (v >> 2) & 1; bits[bi++] = (v >> 1) & 1; bits[bi++] = v & 1;
        }
        var list = new List<int[]> { bits };
        if (text.Split(' ', StringSplitOptions.RemoveEmptyEntries)[^1] == "RR73")
        {
            var pay = bits.Take(PayloadBits).ToArray();
            for (int i = 0; i < 15; i++) pay[59 + i] = (GridRR73 >> (14 - i)) & 1;
            list.Add(CodewordFromPayload(pay));
        }
        return list;
    }

    private sealed class BitProf
    {
        public int E = int.MaxValue, Df, Dt, Alt;
        public double Bst = double.NaN, Edge = double.NaN, ConfWrong = double.NaN;
        public bool Scored;
        // metadata for the splits (never text)
        public string Form = "", SnrBin = "", DtBin = "", SyncCls = "";
    }

    // fewest hard-bit errors over the window points (and, for RR73, over the two encodings); ties keep the first (nearest the centre)
    private static BitProf ProfileWindow(float[] pcm, double f0, double t0, List<int[]> cws)
    {
        var best = new BitProf(); float[]? bestLlr = null; int[]? bestCw = null;
        var llr = new float[CodewordBits];
        foreach (var p in WindowPoints())
        {
            if (Native.ft8_extract_llrs_at(pcm, pcm.Length, (float)(f0 + p.Df * FreqStepHz), (float)(t0 + p.Dt * TimeStepS), llr) != 0) continue;
            for (int k = 0; k < cws.Count; k++)
            {
                int e = 0;
                for (int i = 0; i < CodewordBits; i++) if ((llr[i] > 0 ? 1 : 0) != cws[k][i]) e++;
                if (e < best.E) { best.E = e; best.Df = p.Df; best.Dt = p.Dt; best.Alt = k; bestLlr = (float[])llr.Clone(); bestCw = cws[k]; best.Scored = true; }
            }
        }
        if (!best.Scored) return best;
        // damage measures at the best point
        var perSym = new int[DataSymbols];
        var wrongAbs = new List<float>(); var rightAbs = new List<float>();
        for (int i = 0; i < CodewordBits; i++)
        {
            bool wrong = (bestLlr![i] > 0 ? 1 : 0) != bestCw![i];
            if (wrong) { perSym[i / 3]++; wrongAbs.Add(Math.Abs(bestLlr[i])); } else rightAbs.Add(Math.Abs(bestLlr[i]));
        }
        if (best.E >= BurstMinErrors)
        {
            int maxWin = 0;
            for (int s0 = 0; s0 + BurstSymbols <= DataSymbols; s0++) maxWin = Math.Max(maxWin, perSym.Skip(s0).Take(BurstSymbols).Sum());
            best.Bst = (double)maxWin / best.E;
            best.Edge = (double)(perSym.Take(EdgeSymbols).Sum() + perSym.Skip(DataSymbols - EdgeSymbols).Sum()) / best.E;
            double med = Median(rightAbs.Select(x => (double)x).ToList());
            best.ConfWrong = (double)wrongAbs.Count(x => x > med) / best.E;
        }
        return best;
    }

    private static bool SaturatedRoundTrip(int[] cw)
    {
        var llr = new float[CodewordBits];
        for (int i = 0; i < CodewordBits; i++) llr[i] = cw[i] == 1 ? SaturatedLlr : -SaturatedLlr;
        var a91 = new byte[12];
        return Native.ft8_ldpc_decode_llrs(llr, BpIterations, BpOnly, a91, out int errs, out _, out int crc) == 0 && errs == 0 && crc == 1;
    }

    private static double Pctl(List<double> sorted, double p) => sorted.Count == 0 ? double.NaN : sorted[(int)(p * (sorted.Count - 1))];

    private static SortedDictionary<string, object> Summ(IEnumerable<double> x)
    {
        var s = x.Where(v => !double.IsNaN(v)).OrderBy(v => v).ToList();
        return new SortedDictionary<string, object> { ["n"] = s.Count, ["min"] = s.Count > 0 ? s[0] : double.NaN, ["p5"] = Pctl(s, 0.05), ["p25"] = Pctl(s, 0.25), ["median"] = Pctl(s, 0.5),
            ["p75"] = Pctl(s, 0.75), ["p95"] = Pctl(s, 0.95), ["max"] = s.Count > 0 ? s[^1] : double.NaN, ["mean"] = s.Count > 0 ? s.Average() : double.NaN };
    }

    private static SortedDictionary<string, int> OffsetHist(IEnumerable<BitProf> g)
    {
        var h = new SortedDictionary<string, int>(StringComparer.Ordinal);
        foreach (var r in g) { string k = $"df{r.Df:+0;-0;0},dt{r.Dt:+0;-0;0}"; h[k] = h.GetValueOrDefault(k) + 1; }
        return h;
    }

    private static string WsjDtBin(double dt) => dt < 0 ? "1: dt < 0" : dt < 0.2 ? "2: 0 <= dt < 0.2" : dt < 0.4 ? "3: 0.2 <= dt < 0.4" : "4: dt >= 0.4";

    // validity first, then (only if all three hold) the classes
    private static SortedDictionary<string, object> BReport(List<BitProf> cw, List<BitProf> nw, List<BitProf> tw, SortedDictionary<string, object> counters)
    {
        var r = new SortedDictionary<string, object>();
        var cwE = cw.Select(x => (double)x.E).OrderBy(v => v).ToList(); var nwE = nw.Select(x => (double)x.E).OrderBy(v => v).ToList();
        double cwP95 = Pctl(cwE, 0.95), nwP5 = Pctl(nwE, 0.05), cwMed = Pctl(cwE, 0.5), nwMed = Pctl(nwE, 0.5);
        bool v1 = cwP95 < nwP5, v2 = (int)counters["bv2_roundtrip_fail"] == 0 && (int)counters["bv2_port_mismatch"] == 0 && cwMed < BV2MedianMax, v3 = nwMed >= BV3NullMedianMin;
        r["B0_validity"] = new SortedDictionary<string, object> {
            ["B-V1_CW_P95_lt_NW_P5"] = new SortedDictionary<string, object> { ["CW_P95"] = cwP95, ["NW_P5"] = nwP5, ["pass"] = v1 },
            ["B-V2_convention"] = new SortedDictionary<string, object> { ["saturated_roundtrip_fail_of_CW_codewords"] = counters["bv2_roundtrip_fail"], ["csharp_encoder_port_mismatch_vs_DLL"] = counters["bv2_port_mismatch"],
                ["CW_median_E"] = cwMed, ["bar_median_lt"] = BV2MedianMax, ["pass"] = v2 },
            ["B-V3_NW_median_ge_60"] = new SortedDictionary<string, object> { ["NW_median"] = nwMed, ["pass"] = v3 },
            ["all_pass"] = v1 && v2 && v3 };
        r["counters"] = counters;
        r["E_summary"] = new SortedDictionary<string, object> { ["CW"] = Summ(cwE), ["NW"] = Summ(nwE), ["TW"] = Summ(tw.Select(x => (double)x.E)) };
        r["best_point_offsets"] = new SortedDictionary<string, object> { ["CW"] = OffsetHist(cw), ["NW"] = OffsetHist(nw), ["TW"] = OffsetHist(tw) };
        r["damage_measures"] = new SortedDictionary<string, object> {
            ["CW_burst_share"] = Summ(cw.Select(x => x.Bst)), ["CW_edge_share"] = Summ(cw.Select(x => x.Edge)), ["CW_confident_wrong"] = Summ(cw.Select(x => x.ConfWrong)),
            ["NW_burst_share"] = Summ(nw.Select(x => x.Bst)), ["NW_edge_share"] = Summ(nw.Select(x => x.Edge)), ["NW_confident_wrong"] = Summ(nw.Select(x => x.ConfWrong)),
            ["TW_burst_share"] = Summ(tw.Select(x => x.Bst)), ["TW_edge_share"] = Summ(tw.Select(x => x.Edge)), ["TW_confident_wrong"] = Summ(tw.Select(x => x.ConfWrong)) };
        if (!(v1 && v2 && v3)) { r["classes"] = "NOT SCORED: a validity row failed; B is descriptive only"; return r; }

        string Cls(BitProf x) => x.E >= nwP5 ? "W-NOSIGNAL" : x.E <= cwP95 ? "W-NEAR" : "W-DEGRADED";
        var names = new[] { "W-NOSIGNAL", "W-NEAR", "W-DEGRADED" };
        var cls = new SortedDictionary<string, object>();
        foreach (var n in names) cls[n] = Share(tw.Count(x => Cls(x) == n), tw.Count);
        r["classes"] = cls;
        SortedDictionary<string, object> Split(Func<BitProf, string> key)
        {
            var d = new SortedDictionary<string, object>(StringComparer.Ordinal);
            foreach (var g in tw.GroupBy(key).OrderBy(g => g.Key, StringComparer.Ordinal))
            {
                var row = new SortedDictionary<string, object> { ["n"] = g.Count() };
                foreach (var n in names) row[n] = g.Count(x => Cls(x) == n);
                d[g.Key] = row;
            }
            return d;
        }
        r["classes_by_form"] = Split(x => x.Form);
        r["classes_by_wsjt_snr"] = Split(x => x.SnrBin);
        r["classes_by_refined_sync"] = Split(x => x.SyncCls);
        r["classes_by_wsjt_dt"] = Split(x => x.DtBin);
        var deg = tw.Where(x => Cls(x) == "W-DEGRADED").ToList();
        r["W-DEGRADED_damage"] = new SortedDictionary<string, object> { ["burst_share"] = Summ(deg.Select(x => x.Bst)), ["edge_share"] = Summ(deg.Select(x => x.Edge)), ["confident_wrong"] = Summ(deg.Select(x => x.ConfWrong)),
            ["E"] = Summ(deg.Select(x => (double)x.E)), ["note"] = "against CW's distributions in damage_measures; computed for E >= 10 only" };
        return r;
    }

    // smoke of the machinery (NOT the run): C# encoder port vs the DLL on every control and target text, saturated round trip on 60 codewords,
    // and the E reading on 20 controls OUTSIDE the seeded pilot sample and 20 empty points on another seed (fixed rough offsets)
    private static SortedDictionary<string, object> BSmoke(Derived d, string owsWavDir)
    {
        BindProduct();
        var r = new SortedDictionary<string, object>();
        int n = 0, mism = 0, nullCw = 0, hashN = 0, rt = 0, rtFail = 0, rr73 = 0;
        foreach (var row in d.Controls.Concat(d.Targets))
        {
            var l = ExpectedCodewords(row.Text, out bool h);
            if (l == null) { nullCw++; if (h) hashN++; continue; }
            n++;
            if (!CodewordFromPayload(l[0].Take(PayloadBits).ToArray()).SequenceEqual(l[0])) mism++;
            if (l.Count == 2) rr73++;
            if (rt < 60 && n % 30 == 0) { rt++; if (l.Any(x => !SaturatedRoundTrip(x))) rtFail++; }
        }
        r["texts_packable"] = n; r["texts_unpackable"] = nullCw; r["texts_unresolved_hash"] = hashN; r["port_vs_DLL_mismatch"] = mism; r["texts_ending_RR73"] = rr73;
        r["saturated_roundtrips"] = rt; r["saturated_roundtrip_fail"] = rtFail;
        var ctl = d.Controls.OrderBy(c => c.Ts, StringComparer.Ordinal).ThenBy(c => c.Key, StringComparer.Ordinal).ThenBy(c => c.KeyRank).ToList();
        var rng = new Random(PilotSeed);
        for (int i = ctl.Count - 1; i > 0; i--) { int j = rng.Next(i + 1); (ctl[i], ctl[j]) = (ctl[j], ctl[i]); }
        var outside = ctl.Skip(PilotControls).Take(20).ToList();
        var cE = new List<double>(); var nE = new List<double>(); var cws = new List<List<int[]>>();
        foreach (var c in outside)
        {
            var l = ExpectedCodewords(c.Text, out _); if (l == null) continue;
            cws.Add(l);
            var pcm = _normalise!(ReadWav(Path.Combine(owsWavDir, c.Ts + ".wav")));
            var bp = ProfileWindow(pcm, c.F, c.Dt + 0.6, l); if (bp.Scored) cE.Add(bp.E);
        }
        var rng2 = new Random(PilotSeed + 77);
        for (int i = 0; i < 20; i++)
        {
            string ts = d.Cycles[rng2.Next(d.Cycles.Count)];
            var pcm = _normalise!(ReadWav(Path.Combine(owsWavDir, ts + ".wav")));
            var bp = ProfileWindow(pcm, 200 + rng2.NextDouble() * 2600, 0.6 + rng2.NextDouble() * 0.6, cws[i % cws.Count]); if (bp.Scored) nE.Add(bp.E);
        }
        r["smoke_controls_scored"] = cE.Count; r["smoke_control_E"] = Summ(cE); r["smoke_nulls_scored"] = nE.Count; r["smoke_null_E"] = Summ(nE);
        return r;
    }
}
