// #122 gate 4a: offline truncation replay (spec qa/rr-study/2026-10-03-1015-architect-to-qa-spec-122-gate4a-truncation-replay.md).
// Mode "trunc" (partial of Program, test-only, no src/ change).
//   --arm F : the full window only, one DecodeTwoStageAsync per cycle, flag OFF (the 10-01 "two0" call).
//   --arm T : per cycle, the cut windows largest-cut-first (4.0, 2.5, 2.0, 1.5, 1.0, 0.5), THEN the full window, one process.
//
// 🔒 HK-037 / NFR-021: decoded text lives only inside the matching functions below. The CSV written holds COUNTS and
// numeric fields (freq/dt/snr deltas, bands, DT bins); never message text, never a text-derived hash.
//
// Output CSV (one file per arm): stamp,x,row,key,n,m,ms,exc
//   row=call  : n = decodes of that call, m = matched to the final decode (T early) / corroborated by WSJT-X (F and T final), ms = call time
//   row=spur  : key=corr|unc, n = unmatched early decodes (corroborated by the live WSJT-X or not)
//   row=band  : key=A|B|C|D, n = FINAL decodes in that SNR band, m = how many of them the early decode matched
//   row=dt    : key=bin label, n = final decodes in that DT bin, m = matched
//   row=shift : key = early SNR - final SNR (matched pair), n = 1
//   row=v5    : key = OpenWSFZ DT - WSJT-X DT (corroborated pair, arm-F final only), n = 1
//   row=final : x=0, n = final decodes (the V2 numeric multiset goes to --outcomes: stamp,kind,idx,freqHz,dt,snr)
using System.Diagnostics;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Ft8;

internal static partial class Program
{
    /// <summary>Spec section 4: the 4.0 s positive control first, then the grid, largest cut first.</summary>
    private static readonly double[] TruncCutsSecondsDescending = [4.0, 2.5, 2.0, 1.5, 1.0, 0.5];

    /// <summary>The DLL the spec pins (section 2). V0 compares the loaded module's SHA-256 with it at start and end.</summary>
    private const string PinnedDllSha256 = "ee00d118523ee2160750736225c67d8a056193908d168ed9a6ec3375ff990e4c";

    private static readonly string[] DtBinLabels = ["<=0", "0.0-0.5", "0.5-1.0", "1.0-1.5", "1.5-2.0", "2.0-2.5", ">2.5"];

    private static string DtBinOf(double dt) =>
        dt <= 0 ? DtBinLabels[0] : dt <= 0.5 ? DtBinLabels[1] : dt <= 1.0 ? DtBinLabels[2] :
        dt <= 1.5 ? DtBinLabels[3] : dt <= 2.0 ? DtBinLabels[4] : dt <= 2.5 ? DtBinLabels[5] : DtBinLabels[6];

    private static readonly Dictionary<string, List<(int Snr, double Dt, int Freq, string Msg)>> _trWsjtx = new();

    /// <summary>Same line convention as <c>LoadWsjtx</c>, plus DT (field 5) for row V5.</summary>
    private static void LoadWsjtxWithDt(string path)
    {
        foreach (var line in File.ReadLines(path))
        {
            var f = line.Split(' ', StringSplitOptions.RemoveEmptyEntries);
            if (f.Length < 8 || f[2] != "Rx" || f[3] != "FT8") continue;
            if (!int.TryParse(f[4], out int snr) || !int.TryParse(f[6], out int freq)) continue;
            if (!double.TryParse(f[5], NumberStyles.Float, CultureInfo.InvariantCulture, out double dt)) continue;
            if (!_trWsjtx.TryGetValue(f[0], out var l)) _trWsjtx[f[0]] = l = new();
            l.Add((snr, dt, freq, string.Join(" ", f.Skip(7)).Trim()));
        }
    }

    /// <summary>
    /// One-to-one nearest-first pairing (the Test B rule): same message text and |df| &lt;= CorroborationDeltaHz.
    /// Returns, for each A index, the paired B index or -1. Ties break on A then B index, as ScoreTestB does.
    /// </summary>
    private static int[] PairOneToOne(IReadOnlyList<(int Freq, string Msg)> a, IReadOnlyList<(int Freq, string Msg)> b)
    {
        var cands = new List<(int Df, int Ai, int Bi)>();
        for (int i = 0; i < a.Count; i++)
            for (int j = 0; j < b.Count; j++)
            {
                int df = Math.Abs(a[i].Freq - b[j].Freq);
                if (df <= CorroborationDeltaHz && string.Equals(a[i].Msg, b[j].Msg, StringComparison.Ordinal)) cands.Add((df, i, j));
            }
        cands.Sort((x, y) => x.Df != y.Df ? x.Df.CompareTo(y.Df) : x.Ai != y.Ai ? x.Ai.CompareTo(y.Ai) : x.Bi.CompareTo(y.Bi));
        var pa = new int[a.Count]; Array.Fill(pa, -1);
        var usedB = new bool[b.Count];
        foreach (var (_, ai, bi) in cands)
        {
            if (pa[ai] >= 0 || usedB[bi]) continue;
            pa[ai] = bi; usedB[bi] = true;
        }
        return pa;
    }

    // ---- Gate 4a diagnostic D3 (post-registration; ruling qa/rr-study/2026-10-03-1420-architect-122-gate4a-v2-fail-ruling.md) ----
    // Booleans and counts only, computed INSIDE this function where the text lives; no text, no text-derived hash.
    internal static bool DiagCountImplausible;
    internal static int DiagImplausibleDrops;

    private static readonly System.Reflection.MethodInfo? IsPlausibleMethod =
        typeof(Ft8Decoder).GetMethod("IsPlausibleMessage", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Static);

    private static bool Plausible(string text) =>
        IsPlausibleMethod is not null && (bool)IsPlausibleMethod.Invoke(null, [text, null])!;

    /// <summary>
    /// One line per call of the diagnosed stamp: x, n decodes, n with an unresolved "&lt;...&gt;" placeholder, whether a decode
    /// within 10 Hz of <paramref name="diagFreq"/> is present in this call, whether its text equals the text of ANY decode of
    /// the FINAL call (a dedup collision seen from inside one process), whether it passes IsPlausibleMessage, and the number of
    /// "filtered implausible" events logged during the call (template counted, text never read).
    /// </summary>
    private static string DiagLine(string arm, string stamp, string xLabel, IReadOnlyList<DecodeResult> res,
                                   IReadOnlyList<DecodeResult> final, int diagFreq, int implausibleDrops)
    {
        int ph = res.Count(r => r.Message.Contains("<...>", StringComparison.Ordinal));
        var near = res.Where(r => Math.Abs(r.FreqHz - diagFreq) <= CorroborationDeltaHz).ToList();
        string present = near.Count > 0 ? "1" : "0", eqFinal = "na", plaus = "na";
        if (near.Count > 0)
        {
            string txt = near[0].Message.TrimEnd();
            // equality with a final decode OTHER than a decode at diagFreq itself, i.e. the text the final call kept under another frequency
            eqFinal = final.Any(f => Math.Abs(f.FreqHz - diagFreq) > CorroborationDeltaHz && string.Equals(f.Message.TrimEnd(), txt, StringComparison.Ordinal)) ? "1" : "0";
            plaus = Plausible(txt) ? "1" : "0";
        }
        return string.Join(",", arm, stamp, xLabel, res.Count, ph, present, eqFinal, plaus, implausibleDrops);
    }

    private static string Inv(double v, string f) => v.ToString(f, CultureInfo.InvariantCulture);

    /// <summary>V0: the SHA-256 of the libft8 module the process actually loaded.</summary>
    private static string LoadedDllSha256()
    {
        foreach (ProcessModule mod in Process.GetCurrentProcess().Modules)
            if (mod.ModuleName.StartsWith("libft8", StringComparison.OrdinalIgnoreCase))
                return Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(mod.FileName))).ToLowerInvariant();
        return "NOT-LOADED";
    }

    /// <summary>V1: samples [n, len) exactly 0 AND [0, n) bit-identical to the original. A failure is fatal (exit 3).</summary>
    private static void AssertCut(float[] original, float[] cut, int n)
    {
        if (cut.Length != PcmSamples) throw new InvalidOperationException("V1: cut length");
        for (int i = 0; i < n; i++)
            if (BitConverter.SingleToInt32Bits(cut[i]) != BitConverter.SingleToInt32Bits(original[i])) throw new InvalidOperationException("V1: head altered");
        for (int i = n; i < PcmSamples; i++)
            if (BitConverter.SingleToInt32Bits(cut[i]) != 0) throw new InvalidOperationException("V1: tail not zero");
    }

    private static async Task<int> RunTruncAsync(Dictionary<string, string> a, Ft8Decoder decoder, ReplayLog log, string run,
                                                 string stratum, string wavDir, IReadOnlyList<string> cycles, string outCsv)
    {
        string arm = Req(a, "arm");
        if (arm is not ("F" or "T")) throw new ArgumentException("--arm F|T");
        if (a.TryGetValue("ws-alltxt", out var ws)) LoadWsjtxWithDt(ws); else throw new ArgumentException("--ws-alltxt required");
        if (OsdNhardMax != 40) throw new InvalidOperationException("V0: nhard");
        // The flag is OFF and read back from the decoder object (V0); RunAsync already ran the discarded warm-up.
        SetFlag(decoder, false);
        string dllStart = LoadedDllSha256();
        log.Raw($"# readback start arm={arm} subtractionEnabled={decoder.SubtractionEnabled} nhard={OsdNhardMax} " +
                $"kMinScorePass2={KMinScorePass2} osdCorrThreshold={OsdCorrThreshold.ToString("F2", CultureInfo.InvariantCulture)} " +
                $"dllSha256={dllStart} dllPinned={PinnedDllSha256} dllMatch={dllStart == PinnedDllSha256} shim={Ft8Decoder.LoadedShimVersion}");
        if (decoder.SubtractionEnabled) throw new InvalidOperationException("V0: flag is not OFF");

        a.TryGetValue("diag-stamp", out var diagStamp);
        int diagFreq = a.TryGetValue("diag-freq", out var df) ? int.Parse(df, CultureInfo.InvariantCulture) : 0;
        StreamWriter? diagOut = null;
        if (diagStamp is not null)
        {
            DiagCountImplausible = true;
            Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(Req(a, "diag-out")))!);
            diagOut = new StreamWriter(Req(a, "diag-out"), append: true, new UTF8Encoding(false)) { AutoFlush = true };
            diagOut.WriteLine("arm,stamp,x,n,n_placeholder,present_near_freq,text_equals_other_final,plausible,implausible_events");
        }
        bool earlyOutcomes = a.TryGetValue("early-outcomes", out var eo) && eo == "true";
        var done = new HashSet<string>();
        bool fresh = !File.Exists(outCsv);
        if (!fresh)
            foreach (var line in File.ReadLines(outCsv).Skip(1))
            {
                var p = line.Split(',');
                if (p.Length >= 3 && p[2] == "final") done.Add(p[0]);   // a cycle is done only once its final row exists
            }
        await using var csv = new StreamWriter(outCsv, append: true, new UTF8Encoding(false)) { AutoFlush = true };
        if (fresh) csv.WriteLine("stamp,x,row,key,n,m,ms,exc");

        for (int idx = 0; idx < cycles.Count; idx++)
        {
            string stamp = cycles[idx];
            if (done.Contains(stamp)) continue;
            var pcm = ReadWav(Path.Combine(wavDir, stamp + ".wav"));
            var cyc = StampToUtc(stamp);
            var w = _trWsjtx.TryGetValue(stamp, out var wl) ? wl : new List<(int Snr, double Dt, int Freq, string Msg)>();
            var rows = new List<string>();   // buffered: a cycle is written whole, so a crash leaves no half cycle
            var wsKey = w.Select(r => (r.Freq, r.Msg)).ToList();

            // Early decodes first (arm T only), kept in memory so the final decode can be matched against each.
            var early = new List<(double X, List<DecodeResult> Res)>();
            var diagDrops = new List<int>();
            bool diagThis = diagStamp == stamp;
            if (arm == "T")
                foreach (double x in TruncCutsSecondsDescending)
                {
                    int n = PcmSamples - (int)Math.Round(12_000 * x);
                    var cut = (float[])pcm.Clone();
                    Array.Clear(cut, n, PcmSamples - n);
                    AssertCut(pcm, cut, n);                                  // V1, before the decode
                    Interlocked.Exchange(ref DiagImplausibleDrops, 0);
                    var (res, ms, exc) = await TimedDecode(decoder, cut, cyc);
                    diagDrops.Add(Volatile.Read(ref DiagImplausibleDrops));
                    early.Add((x, res));
                    if (earlyOutcomes) WriteOutcomes(stamp, "early_" + Inv(x, "F1"), res);
                    rows.Add(string.Join(",", stamp, Inv(x, "F1"), "call", "", res.Count, "", Inv(ms, "F1"), exc));
                }

            Interlocked.Exchange(ref DiagImplausibleDrops, 0);
            var (final, fms, fexc) = await TimedDecode(decoder, pcm, cyc);
            int finalDrops = Volatile.Read(ref DiagImplausibleDrops);
            if (diagThis && diagOut is not null)
            {
                for (int k = 0; k < early.Count; k++)
                    diagOut.WriteLine(DiagLine(arm, stamp, Inv(early[k].X, "F1"), early[k].Res, final, diagFreq, diagDrops[k]));
                diagOut.WriteLine(DiagLine(arm, stamp, "0.0", final, final, diagFreq, finalDrops));
            }
            var finalKey = final.Select(r => (r.FreqHz, r.Message.TrimEnd())).ToList();
            var finalVsWs = PairOneToOne(finalKey, wsKey);
            int fcorr = finalVsWs.Count(i => i >= 0);
            rows.Add(string.Join(",", stamp, "0.0", "call", "", final.Count, fcorr, Inv(fms, "F1"), fexc));
            if (arm == "F")
                for (int i = 0; i < final.Count; i++)
                    if (finalVsWs[i] >= 0) rows.Add(string.Join(",", stamp, "0.0", "v5", Inv(final[i].Dt - w[finalVsWs[i]].Dt, "F2"), 1, "", "", ""));

            foreach (var (x, res) in early)
            {
                var earlyKey = res.Select(r => (r.FreqHz, r.Message.TrimEnd())).ToList();
                var pair = PairOneToOne(finalKey, earlyKey);                 // index = final decode, value = its early partner
                var earlyMatched = new bool[res.Count];
                foreach (int ei in pair) if (ei >= 0) earlyMatched[ei] = true;
                var unmatchedIdx = Enumerable.Range(0, res.Count).Where(i => !earlyMatched[i]).ToList();
                var unKey = unmatchedIdx.Select(i => earlyKey[i]).ToList();
                var unVsWs = PairOneToOne(unKey, wsKey);
                int sc = unVsWs.Count(i => i >= 0), su = unmatchedIdx.Count - sc;
                string xs = Inv(x, "F1");
                rows.Add(string.Join(",", stamp, xs, "spur", "corr", sc, "", "", ""));
                rows.Add(string.Join(",", stamp, xs, "spur", "unc", su, "", "", ""));
                var bandN = new Dictionary<string, (int N, int M)>();
                var dtN = new Dictionary<string, (int N, int M)>();
                for (int i = 0; i < final.Count; i++)
                {
                    bool hit = pair[i] >= 0;
                    string b = BandOf(final[i].Snr), d = DtBinOf(final[i].Dt);
                    bandN[b] = (bandN.GetValueOrDefault(b).N + 1, bandN.GetValueOrDefault(b).M + (hit ? 1 : 0));
                    dtN[d] = (dtN.GetValueOrDefault(d).N + 1, dtN.GetValueOrDefault(d).M + (hit ? 1 : 0));
                    if (hit) rows.Add(string.Join(",", stamp, xs, "shift", res[pair[i]].Snr - final[i].Snr, 1, "", "", ""));
                }
                foreach (var kv in bandN) rows.Add(string.Join(",", stamp, xs, "band", kv.Key, kv.Value.N, kv.Value.M, "", ""));
                foreach (var kv in dtN) rows.Add(string.Join(",", stamp, xs, "dt", kv.Key, kv.Value.N, kv.Value.M, "", ""));
                int matched = pair.Count(i => i >= 0);
                // the 'call' row for this x already holds n_early; its 'matched' count is added as its own row to keep rows append-only
                rows.Add(string.Join(",", stamp, xs, "matched", "", matched, "", "", ""));
            }

            WriteOutcomes(stamp, arm == "F" ? "final_F" : "final_T", final);   // V2 numeric multiset (freq, dt, snr)
            rows.Add(string.Join(",", stamp, "0.0", "final", "", final.Count, "", "", fexc));   // completion marker, last
            foreach (var r in rows) csv.WriteLine(r);
        }
        string dllEnd = LoadedDllSha256();
        log.Raw($"# readback end arm={arm} subtractionEnabled={decoder.SubtractionEnabled} dllSha256={dllEnd} dllMatch={dllEnd == PinnedDllSha256}");
        return dllStart == PinnedDllSha256 && dllEnd == PinnedDllSha256 ? 0 : 4;
    }

    private static async Task<(List<DecodeResult> Res, double Ms, string Exc)> TimedDecode(Ft8Decoder d, float[] pcm, DateTime cyc)
    {
        var all = new List<DecodeResult>();
        string exc = "";
        var sw = Stopwatch.StartNew();
        try
        {
            var b2 = await d.DecodeTwoStageAsync(pcm, cyc, null, batch => { all.AddRange(batch); return Task.CompletedTask; });
            all.AddRange(b2);
        }
        catch (Exception ex) { exc = ex.GetType().Name; }
        sw.Stop();
        return (all, sw.Elapsed.TotalMilliseconds, exc);
    }
}
