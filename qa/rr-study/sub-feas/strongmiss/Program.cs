// STRONG-MISS replay harness (QA-owned, no src/ change).
// Spec: qa/rr-study/2026-10-10-1015-architect-to-qa-spec-strong-miss-replay.md + amendment 1 (arch/strong-miss 22e46d8f).
//
// ONE PROCESS does everything (Architect, amendment 1, HK-037): it reads both ALL.TXT files, derives the target set T and
// the control set C (spec section 1) with the standing matching rule, decodes the T cycles on BOTH audio sets (R-OWN =
// owsfz/wav, R-WSJ = wsjt-x/wav) through the live DLL, scores the classes and the validity rows IN MEMORY, and writes
// AGGREGATE counters only. Nothing per message is written to disk, not even a temp file; message text exists only in the
// in-memory structures below. The log sink prints only allow-listed aggregate templates.
//
// Interleaving: for each cycle the harness decodes R-OWN then R-WSJ, so the process-global callsign hash table has the same
// history for both arms (a limit of the design, stated in the report: neither arm has the live process's 15 h history; the
// comparison key collapses <...>, so hashed text does not depend on it).
//
// Modes:   (default)          full replay
//          --derive-only true  derive T/C, assert the Architect's counts, print aggregates, decode nothing
//          --selftest true     pure-logic checks (no files, no decoder); exit 0 = pass

using System.Diagnostics;
using System.Globalization;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Ft8;

internal static partial class Program
{
    private const int PcmSamples = 180_000;
    private const int SampleRateHz = 12_000;
    private const int KMinScorePass2 = 10;
    private const float OsdCorrThreshold = 0.10f;
    private const double StrongSnrDb = 0.0;          // strong = WSJT-X SNR > 0 dB (spec section 1)
    private const double CrowdHz = 25.0;             // uncrowded = no other WSJT-X decode within 25 Hz in the cycle
    private const int ExpectT = 504, ExpectTCycles = 433, ExpectC = 1671;
    private const int ExpectMatched = 62340, ExpectWsjtOnly = 31271;
    private const double V2ReproducedMin = 0.99;     // SM-V2 frozen bar (amendment 1): >= 99 % of live rows reproduced ...
    private const double V2ExtraMax = 0.01;          // ... and R-OWN adds <= 1 % rows (of the live row count) not in the live output
    private const double Z95 = 1.959964;

    private static readonly Regex HashRe = new(@"<[^>]*>", RegexOptions.Compiled);
    private static readonly Regex WsRe = new(@"\s+", RegexOptions.Compiled);

    // ---------------------------------------------------------------- rows
    private sealed class Row
    {
        public string Ts = ""; public double Snr, Dt, F; public string Text = ""; public string Key = "";
        public int KeyRank;       // position of this row inside its (cycle, key) group, in file order
    }

    private static string Norm(string s) => string.Join(" ", WsRe.Split(s.Trim()).Where(x => x.Length > 0));
    private static string KeyOf(string text) => HashRe.Replace(Norm(text), "<HASH>");

    private static List<Row> ReadAllTxt(string path)
    {
        var rows = new List<Row>();
        foreach (var line in File.ReadLines(path, Encoding.ASCII))
        {
            var t = line.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries);
            if (t.Length < 8) continue;
            if (!double.TryParse(t[4], NumberStyles.Float, CultureInfo.InvariantCulture, out double snr)) continue;
            if (!double.TryParse(t[5], NumberStyles.Float, CultureInfo.InvariantCulture, out double dt)) continue;
            if (!double.TryParse(t[6], NumberStyles.Float, CultureInfo.InvariantCulture, out double f)) continue;
            string text = string.Join(" ", t.Skip(7));
            rows.Add(new Row { Ts = t[0], Snr = snr, Dt = dt, F = f, Text = text, Key = KeyOf(text) });
        }
        // rank inside the (cycle, key) group, in file order
        var seen = new Dictionary<(string, string), int>();
        foreach (var r in rows)
        {
            var k = (r.Ts, r.Key);
            seen.TryGetValue(k, out int n);
            r.KeyRank = n;
            seen[k] = n + 1;
        }
        return rows;
    }

    // ---------------------------------------------------------------- shape predicates (port of the Architect's sm_01 script)
    private static readonly Regex GridRe = new(@"^[A-R]{2}[0-9]{2}$", RegexOptions.Compiled);
    private static readonly Regex ReportRe = new(@"^R?[+-][0-9]{2}$", RegexOptions.Compiled);

    internal static HashSet<string> Calls(string s)
    {
        string t = HashRe.Replace(s, m => m.Value.Substring(1, m.Value.Length - 2)).ToUpperInvariant().Replace(';', ' ');
        var set = new HashSet<string>();
        foreach (var tok in t.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries))
        {
            if (tok.Length < 3) continue;
            if (!tok.Any(char.IsAsciiDigit) || !tok.Any(c => c >= 'A' && c <= 'Z')) continue;
            if (GridRe.IsMatch(tok) || ReportRe.IsMatch(tok)) continue;
            set.Add(tok);
        }
        return set;
    }

    internal static string Form(string s)
    {
        var toks = s.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries);
        if (s.Contains(';')) return "multi-call (';')";
        if (s.Contains('<')) return "hashed";
        if (toks.Any(x => x.Contains('/'))) return "compound call ('/')";
        if (toks.Length > 0 && (toks[0] == "CQ" || toks[0] == "QRZ" || toks[0] == "DE"))
            return toks.Length >= 2 && toks.Length <= 4 ? "CQ standard" : "CQ other";
        if (Calls(s).Count >= 2 && toks.Length <= 4) return "two-call standard";
        if (Calls(s).Count == 0) return "free text / telemetry";
        return "other";
    }

    private static string FormGroup(string s)
    {
        string f = Form(s);
        return f.StartsWith("CQ") ? "CQ" : f.StartsWith("two-call") ? "two-call" : f == "hashed" ? "hashed"
             : f.StartsWith("compound") ? "compound '/'" : "other";
    }

    private static bool IsTargetShape(Row row, List<Row> cycleRows)
    {
        if (row.Snr <= StrongSnrDb) return false;
        if (row.Text.Contains(';') || Calls(row.Text).Count == 0) return false;
        foreach (var o in cycleRows)
            if (!ReferenceEquals(o, row) && Math.Abs(o.F - row.F) <= CrowdHz) return false;
        return true;
    }

    // ---------------------------------------------------------------- statistics
    internal static (double Lo, double Hi) Wilson(int k, int n)
    {
        if (n == 0) return (double.NaN, double.NaN);
        double p = (double)k / n, d = 1 + Z95 * Z95 / n, c = (p + Z95 * Z95 / (2 * n)) / d;
        double h = Z95 * Math.Sqrt(p * (1 - p) / n + Z95 * Z95 / (4.0 * n * n)) / d;
        return (Math.Max(0, c - h), Math.Min(1, c + h));
    }

    private static Dictionary<string, object> Share(int k, int n)
    {
        var (lo, hi) = Wilson(k, n);
        return new Dictionary<string, object> { ["k"] = k, ["n"] = n, ["pct"] = n == 0 ? double.NaN : 100.0 * k / n,
            ["ci95_lo_pct"] = 100 * lo, ["ci95_hi_pct"] = 100 * hi };
    }

    // ---------------------------------------------------------------- classes (spec section 2)
    internal enum Cls { Live, Capture, Decoder }
    internal static Cls Classify(bool ownDecoded, bool wsjDecoded) => ownDecoded ? Cls.Live : wsjDecoded ? Cls.Capture : Cls.Decoder;

    // ---------------------------------------------------------------- derive T and C
    private sealed class Derived
    {
        public List<Row> Ows = new(), Wsj = new();
        public List<Row> Targets = new(), Controls = new();
        public List<string> Cycles = new();                       // distinct T cycles, ascending
        public int Matched, WsjOnly;
        public SortedDictionary<string, int> TargetsByGroup = new();
    }

    private static Derived Derive(string owsPath, string wsjPath)
    {
        var d = new Derived { Ows = ReadAllTxt(owsPath), Wsj = ReadAllTxt(wsjPath) };
        var byO = new Dictionary<(string, string), List<Row>>();
        var byW = new Dictionary<(string, string), List<Row>>();
        foreach (var r in d.Ows) { var k = (r.Ts, r.Key); if (!byO.TryGetValue(k, out var l)) byO[k] = l = new(); l.Add(r); }
        foreach (var r in d.Wsj) { var k = (r.Ts, r.Key); if (!byW.TryGetValue(k, out var l)) byW[k] = l = new(); l.Add(r); }
        var keys = byO.Keys.Union(byW.Keys).ToList();
        keys.Sort((x, y) => { int c = string.CompareOrdinal(x.Item1, y.Item1); return c != 0 ? c : string.CompareOrdinal(x.Item2, y.Item2); });
        var mW = new List<Row>(); var uW = new List<Row>();
        foreach (var k in keys)
        {
            byO.TryGetValue(k, out var a); byW.TryGetValue(k, out var b);
            a ??= new(); b ??= new();
            int n = Math.Min(a.Count, b.Count);
            mW.AddRange(b.Take(n)); uW.AddRange(b.Skip(n));
        }
        d.Matched = mW.Count; d.WsjOnly = uW.Count;
        if (d.Matched != ExpectMatched || d.WsjOnly != ExpectWsjtOnly)
            throw new InvalidOperationException($"matching drifted: matched={d.Matched} wsjt-only={d.WsjOnly}");
        var wsjCyc = d.Wsj.GroupBy(r => r.Ts).ToDictionary(g => g.Key, g => g.ToList());
        d.Targets = uW.Where(r => IsTargetShape(r, wsjCyc[r.Ts])).ToList();
        var tCyc = new HashSet<string>(d.Targets.Select(r => r.Ts));
        d.Controls = mW.Where(r => tCyc.Contains(r.Ts) && IsTargetShape(r, wsjCyc[r.Ts])).ToList();
        d.Cycles = tCyc.OrderBy(x => x, StringComparer.Ordinal).ToList();
        foreach (var g in d.Targets.GroupBy(r => FormGroup(r.Text))) d.TargetsByGroup[g.Key] = g.Count();
        if (d.Targets.Count != ExpectT || d.Cycles.Count != ExpectTCycles || d.Controls.Count != ExpectC)
            throw new InvalidOperationException($"T/C drifted: T={d.Targets.Count} cycles={d.Cycles.Count} C={d.Controls.Count}");
        return d;
    }

    // ---------------------------------------------------------------- self test
    private static int SelfTest()
    {
        int fail = 0;
        void Check(bool ok, string what) { if (!ok) { fail++; Console.Error.WriteLine("SELFTEST FAIL " + what); } }
        // shapes (synthetic Q-prefix callsigns only)
        Check(Calls("Q1ABC Q2XYZ -12").SetEquals(new[] { "Q1ABC", "Q2XYZ" }), "calls two-call");
        Check(Calls("CQ Q1ABC EN37").SetEquals(new[] { "Q1ABC" }), "calls CQ (grid excluded)");
        Check(Calls("Q1ABC <Q2XYZ> R-07").SetEquals(new[] { "Q1ABC", "Q2XYZ" }), "calls hashed (report excluded)");
        Check(Form("CQ Q1ABC EN37") == "CQ standard", "form CQ");
        Check(Form("Q1ABC Q2XYZ -12") == "two-call standard", "form two-call");
        Check(Form("<...> Q2XYZ RR73") == "hashed", "form hashed");
        Check(Form("Q1ABC/P Q2XYZ -12") == "compound call ('/')", "form compound");
        Check(Form("Q1ABC RR73; Q2XYZ <Q3DX> -12") == "multi-call (';')", "form multi");
        // target shape: strong, uncrowded
        Row R(double snr, double f, string text) => new Row { Ts = "261009_000000", Snr = snr, F = f, Text = text, Key = KeyOf(text) };
        var a = R(3, 1000, "Q1ABC Q2XYZ -12"); var b = R(-5, 1030, "CQ Q3DX EN37"); var c = R(-5, 1020, "CQ Q4AAA EN37");
        Check(IsTargetShape(a, new() { a, b }), "target: neighbour 30 Hz away is not crowding");
        Check(!IsTargetShape(a, new() { a, c }), "target: neighbour 20 Hz away is crowding");
        Check(!IsTargetShape(R(0, 1000, "Q1ABC Q2XYZ -12"), new()), "target: SNR must be > 0");
        Check(!IsTargetShape(R(5, 1000, "Q1ABC RR73; Q2XYZ -12"), new()), "target: ';' excluded");
        // classes
        Check(Classify(true, true) == Cls.Live && Classify(true, false) == Cls.Live, "class LIVE wins");
        Check(Classify(false, true) == Cls.Capture, "class CAPTURE");
        Check(Classify(false, false) == Cls.Decoder, "class DECODER");
        // wilson
        var (lo, hi) = Wilson(0, 10); Check(lo == 0 && hi > 0.25 && hi < 0.30, "wilson 0/10");
        var (lo2, hi2) = Wilson(5, 10); Check(Math.Abs((lo2 + hi2) / 2 - 0.5) < 1e-9, "wilson 5/10 symmetric");
        // key rank: second copy of the same text in a cycle ranks 1
        var rows = new List<Row> { R(1, 1, "Q1ABC Q2XYZ -12"), R(1, 2, "Q1ABC Q2XYZ -12") };
        var seen = new Dictionary<string, int>(); foreach (var r in rows) { seen.TryGetValue(r.Key, out int n); r.KeyRank = n; seen[r.Key] = n + 1; }
        Check(rows[0].KeyRank == 0 && rows[1].KeyRank == 1, "key rank");
        // V2 arithmetic
        var live = new Dictionary<string, int> { ["a"] = 3, ["b"] = 1 }; var own = new Dictionary<string, int> { ["a"] = 2, ["b"] = 1, ["c"] = 2 };
        Check(Reproduced(live, own) == 3 && Extra(live, own) == 2, "V2 reproduced/extra");
        Console.WriteLine(fail == 0 ? "SELFTEST PASS" : $"SELFTEST {fail} FAIL");
        return fail == 0 ? 0 : 1;
    }

    private static int Reproduced(Dictionary<string, int> live, Dictionary<string, int> own) =>
        live.Sum(kv => own.TryGetValue(kv.Key, out int n) ? Math.Min(kv.Value, n) : 0);
    private static int Extra(Dictionary<string, int> live, Dictionary<string, int> own) =>
        own.Sum(kv => Math.Max(0, kv.Value - (live.TryGetValue(kv.Key, out int n) ? n : 0)));

    // ---------------------------------------------------------------- main
    private static int Main(string[] args)
    {
        try { return RunAsync(args).GetAwaiter().GetResult(); }
        catch (Exception ex) { Console.Error.WriteLine("FATAL " + ex.GetType().Name + " " + (ex is InvalidOperationException || ex is ArgumentException ? ex.Message : "")); return 3; }
    }

    private static string? _arm;                       // "OWN" / "WSJ": which arm is decoding right now (for the abandon counters)
    private static readonly Dictionary<string, int> Abandoned = new() { ["OWN"] = 0, ["WSJ"] = 0 };
    private static readonly Dictionary<string, int> Contained = new() { ["OWN"] = 0, ["WSJ"] = 0 };
    private static readonly Dictionary<string, int> Ran = new() { ["OWN"] = 0, ["WSJ"] = 0 };

    private static async Task<int> RunAsync(string[] args)
    {
        var a = ParseArgs(args);
        if (a.ContainsKey("selftest")) return SelfTest();
        if (a.ContainsKey("probe-selftest"))
        {
            BindProduct();
            var sc = ProbeSelfChecks(null);
            Console.WriteLine("PROBE-SELFTEST " + JsonSerializer.Serialize(sc));
            return (bool)sc["gray_inversion_roundtrip"] && (bool)sc["implausible_10_all_false"] && (bool)sc["plausible_synthetic_reads_true"] ? 0 : 1;
        }
        string owsTxt = Req(a, "ows-alltxt"), wsjTxt = Req(a, "wsjt-alltxt");
        var d = Derive(owsTxt, wsjTxt);
        var report = new SortedDictionary<string, object>
        {
            ["T"] = d.Targets.Count, ["T_cycles"] = d.Cycles.Count, ["C"] = d.Controls.Count,
            ["T_by_form"] = d.TargetsByGroup, ["matched"] = d.Matched, ["wsjt_only"] = d.WsjOnly,
        };
        Console.WriteLine("DERIVED " + JsonSerializer.Serialize(report));
        if (a.ContainsKey("derive-only")) return 0;
        if (a.ContainsKey("probe-smoke"))
        {
            SortedDictionary<string, object>? sm = null; Exception? se = null;
            var ts = new Thread(() => { try { sm = ProbeSmoke(d, Req(a, "ows-wav-dir")); } catch (Exception ex) { se = ex; } }, 64 * 1024 * 1024);
            ts.Start(); ts.Join();
            if (se != null) { Console.Error.WriteLine("SMOKE FAIL " + se.GetType().Name + " " + se.Message); return 1; }
            Console.WriteLine("PROBE-SMOKE " + JsonSerializer.Serialize(sm));
            return 0;
        }

        string owsWav = Req(a, "ows-wav-dir"), wsjWav = Req(a, "wsjt-wav-dir"), outJson = Req(a, "out-json"), logPath = Req(a, "log");
        string statusPath = Req(a, "status");
        int nhard = int.Parse(Req(a, "nhard"), CultureInfo.InvariantCulture);
        int signFix = int.Parse(Req(a, "osd-sign-fix"), CultureInfo.InvariantCulture);
        int threads = int.Parse(Req(a, "threads"), CultureInfo.InvariantCulture);
        string label = a.TryGetValue("label", out var l) ? l : "unlabelled";

        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outJson))!);
        using var log = new ReplayLog(logPath);
        var logger = new ReplayLogger<Ft8Decoder>(log);
        var decoder = new Ft8Decoder(new WallClock(), logger);
        decoder.SetDecodeParams(KMinScorePass2, OsdCorrThreshold, nhard);
        decoder.SetOsdSignFix(signFix);
        decoder.SetSubtractionMaxThreads(threads);
        decoder.SetSubtractionEnabled(true);
        void Readback(string tag) => log.Raw($"# readback {tag} subtractionEnabled={decoder.SubtractionEnabled} threadsConfigured={threads} " +
            $"cores={Environment.ProcessorCount} nhard={nhard} kMinScorePass2={KMinScorePass2} osdCorrThreshold={OsdCorrThreshold.ToString("F2", CultureInfo.InvariantCulture)} " +
            $"shim={Ft8Decoder.LoadedShimVersion} osdSignFixSet={signFix} osdSignFixRead={decoder.GetOsdSignFix()} label={label}");
        Readback("start");
        // every WAV of both arms must exist before the first decode (a missing file would otherwise abort hours in)
        var missing = d.Cycles.Where(c => !File.Exists(Path.Combine(owsWav, c + ".wav")) || !File.Exists(Path.Combine(wsjWav, c + ".wav"))).ToList();
        if (missing.Count > 0) throw new InvalidOperationException($"{missing.Count} of {d.Cycles.Count} cycles lack a WAV in one arm");
        log.Raw($"# all {d.Cycles.Count} cycles have a WAV in both arms");

        // warm-up: one discarded decode through the full path (first T cycle, R-OWN audio)
        await decoder.DecodeTwoStageAsync(ReadWav(Path.Combine(owsWav, d.Cycles[0] + ".wav")), StampToUtc(d.Cycles[0]), null, _ => Task.CompletedTask);
        log.Raw("# warm-up cycle decoded and discarded");

        // live OpenWSFZ rows in the T cycles (SM-V2 reference), as per-cycle key multisets
        var tCycSet = new HashSet<string>(d.Cycles);
        var liveBy = new Dictionary<string, Dictionary<string, int>>();
        foreach (var r in d.Ows.Where(r => tCycSet.Contains(r.Ts)))
        {
            if (!liveBy.TryGetValue(r.Ts, out var m)) liveBy[r.Ts] = m = new();
            m.TryGetValue(r.Key, out int n); m[r.Key] = n + 1;
        }
        var own = new Dictionary<string, Dictionary<string, int>>();
        var wsj = new Dictionary<string, Dictionary<string, int>>();
        var sw = Stopwatch.StartNew();
        for (int i = 0; i < d.Cycles.Count; i++)
        {
            string ts = d.Cycles[i];
            foreach (var (arm, dir, store) in new[] { ("OWN", owsWav, own), ("WSJ", wsjWav, wsj) })
            {
                _arm = arm;
                var pcm = ReadWav(Path.Combine(dir, ts + ".wav"));
                var all = new List<DecodeResult>();
                var b2 = await decoder.DecodeTwoStageAsync(pcm, StampToUtc(ts), null, batch => { all.AddRange(batch); return Task.CompletedTask; });
                all.AddRange(b2);
                var m = new Dictionary<string, int>();
                foreach (var r in all) { string k = KeyOf(r.Message); m.TryGetValue(k, out int n); m[k] = n + 1; }
                store[ts] = m;
            }
            File.WriteAllText(statusPath, JsonSerializer.Serialize(new { utc = DateTime.UtcNow.ToString("O"), done = i + 1, of = d.Cycles.Count, elapsed_s = sw.Elapsed.TotalSeconds }));
        }
        _arm = null;
        Readback("end");

        // ---- scoring (all in memory) ----
        bool Decoded(Row r, Dictionary<string, Dictionary<string, int>> st) =>
            st.TryGetValue(r.Ts, out var m) && m.TryGetValue(r.Key, out int n) && r.KeyRank < n;

        var classOf = new List<(Row Row, Cls C)>();
        foreach (var t in d.Targets) classOf.Add((t, Classify(Decoded(t, own), Decoded(t, wsj))));
        int nLive = classOf.Count(x => x.C == Cls.Live), nCap = classOf.Count(x => x.C == Cls.Capture), nDec = classOf.Count(x => x.C == Cls.Decoder);
        var byForm = new SortedDictionary<string, object>();
        foreach (var g in classOf.GroupBy(x => FormGroup(x.Row.Text)).OrderBy(g => g.Key, StringComparer.Ordinal))
            byForm[g.Key] = new SortedDictionary<string, object> {
                ["n"] = g.Count(),
                ["SM-LIVE"] = Share(g.Count(x => x.C == Cls.Live), g.Count()),
                ["SM-CAPTURE"] = Share(g.Count(x => x.C == Cls.Capture), g.Count()),
                ["SM-DECODER"] = Share(g.Count(x => x.C == Cls.Decoder), g.Count()) };
        var decRows = classOf.Where(x => x.C == Cls.Decoder).Select(x => x.Row).ToList();
        var decBySnr = new SortedDictionary<string, int>(StringComparer.Ordinal);
        var decByDt = new SortedDictionary<string, int>(StringComparer.Ordinal);
        foreach (var r in decRows)
        {
            string sb = r.Snr <= 5 ? "1: (0,5] dB" : r.Snr <= 10 ? "2: (5,10] dB" : "3: >10 dB";
            string db = r.Dt <= 0 ? "1: <=0 s" : r.Dt <= 0.5 ? "2: (0,0.5] s" : r.Dt <= 1.0 ? "3: (0.5,1] s" : "4: >1 s";
            decBySnr[sb] = decBySnr.GetValueOrDefault(sb) + 1; decByDt[db] = decByDt.GetValueOrDefault(db) + 1;
        }

        // SM-V2 / SM-V3
        int liveRows = liveBy.Values.Sum(m => m.Values.Sum()), ownRows = own.Values.Sum(m => m.Values.Sum());
        int repro = d.Cycles.Sum(c => Reproduced(liveBy.GetValueOrDefault(c) ?? new(), own[c]));
        int extra = d.Cycles.Sum(c => Extra(liveBy.GetValueOrDefault(c) ?? new(), own[c]));
        int eqCycles = d.Cycles.Count(c => (liveBy.GetValueOrDefault(c)?.Values.Sum() ?? 0) == own[c].Values.Sum());
        int sumAbs = d.Cycles.Sum(c => Math.Abs((liveBy.GetValueOrDefault(c)?.Values.Sum() ?? 0) - own[c].Values.Sum()));
        int cRecovered = d.Controls.Count(c => Decoded(c, own));
        int ownWsjDiffer = d.Cycles.Count(c => !own[c].OrderBy(x => x.Key, StringComparer.Ordinal).SequenceEqual(wsj[c].OrderBy(x => x.Key, StringComparer.Ordinal)));
        double reproFrac = (double)repro / liveRows, extraFrac = (double)extra / liveRows;
        bool v2Pass = reproFrac >= V2ReproducedMin && extraFrac <= V2ExtraMax;

        var result = new SortedDictionary<string, object>
        {
            ["label"] = label, ["generated_utc"] = DateTime.UtcNow.ToString("O"),
            ["T"] = d.Targets.Count, ["T_cycles"] = d.Cycles.Count, ["C"] = d.Controls.Count, ["T_by_form"] = d.TargetsByGroup,
            ["settings"] = new SortedDictionary<string, object> { ["nhard"] = nhard, ["osd_sign_fix"] = signFix, ["threads"] = threads, ["subtraction"] = "ON", ["shim"] = Ft8Decoder.LoadedShimVersion },
            ["SM-V2"] = new SortedDictionary<string, object> {
                ["pass_as_frozen_99_1"] = v2Pass, ["live_rows_in_T_cycles"] = liveRows, ["R-OWN_rows"] = ownRows,
                ["live_rows_reproduced"] = Share(repro, liveRows), ["R-OWN_rows_not_in_live"] = Share(extra, liveRows),
                ["cycles_equal_row_count"] = eqCycles, ["cycles"] = d.Cycles.Count, ["sum_abs_row_count_diff"] = sumAbs,
                ["sum_abs_diff_pct_of_live_rows"] = 100.0 * sumAbs / liveRows, ["net_row_count_diff"] = ownRows - liveRows },
            ["SM-V3_controls_recovered_in_R-OWN"] = Share(cRecovered, d.Controls.Count),
            ["classes"] = new SortedDictionary<string, object> {
                ["SM-LIVE"] = Share(nLive, d.Targets.Count), ["SM-CAPTURE"] = Share(nCap, d.Targets.Count), ["SM-DECODER"] = Share(nDec, d.Targets.Count) },
            ["classes_by_form"] = byForm,
            ["SM-DECODER_by_wsjt_snr"] = decBySnr, ["SM-DECODER_by_wsjt_dt"] = decByDt,
            ["cycles_where_R-OWN_and_R-WSJ_outputs_differ"] = ownWsjDiffer,
            ["residual_pass"] = new SortedDictionary<string, object> { ["ran_OWN"] = Ran["OWN"], ["ran_WSJ"] = Ran["WSJ"],
                ["abandoned_OWN"] = Abandoned["OWN"], ["abandoned_WSJ"] = Abandoned["WSJ"], ["contained_OWN"] = Contained["OWN"], ["contained_WSJ"] = Contained["WSJ"] },
            ["elapsed_s"] = sw.Elapsed.TotalSeconds,
        };
        if (a.ContainsKey("probe"))
        {
            var inp = new ProbeInput { D = d, OwsWavDir = owsWav, Nhard = nhard, Targets = classOf.Where(x => x.C == Cls.Decoder).Select(x => x.Row).ToList() };
            SortedDictionary<string, object>? pres = null; Exception? perr = null;
            var th = new Thread(() => { try { pres = RunProbe(inp, log); } catch (Exception ex) { perr = ex; } }, 64 * 1024 * 1024);
            th.Start(); th.Join();
            if (perr != null) throw new InvalidOperationException("probe phase failed: " + perr.GetType().Name + " " + perr.Message);
            result["probe"] = pres!;
        }
        File.WriteAllText(outJson, JsonSerializer.Serialize(result, new JsonSerializerOptions { WriteIndented = true }));
        Console.WriteLine("RESULT written " + outJson);
        return 0;
    }

    // ---------------------------------------------------------------- helpers (as in Replay81)
    private static float[] ReadWav(string path)
    {
        byte[] b = File.ReadAllBytes(path);
        if (b.Length < 44 || Encoding.ASCII.GetString(b, 0, 4) != "RIFF" || Encoding.ASCII.GetString(b, 8, 4) != "WAVE")
            throw new InvalidDataException("not a RIFF/WAVE file");
        int pos = 12, channels = 0, rate = 0, bits = 0, dataOff = -1, dataLen = 0;
        while (pos + 8 <= b.Length)
        {
            string id = Encoding.ASCII.GetString(b, pos, 4);
            int len = BitConverter.ToInt32(b, pos + 4);
            if (id == "fmt ") { channels = BitConverter.ToInt16(b, pos + 10); rate = BitConverter.ToInt32(b, pos + 12); bits = BitConverter.ToInt16(b, pos + 22); }
            else if (id == "data") { dataOff = pos + 8; dataLen = len; break; }
            pos += 8 + len + (len & 1);
        }
        if (channels != 1 || rate != SampleRateHz || bits != 16 || dataOff < 0 || dataLen / 2 != PcmSamples)
            throw new InvalidDataException($"WAV assertion failed (ch={channels} rate={rate} bits={bits} samples={dataLen / 2})");
        var pcm = new float[PcmSamples];
        for (int i = 0; i < PcmSamples; i++) pcm[i] = BitConverter.ToInt16(b, dataOff + 2 * i) / 32768f;
        return pcm;
    }

    private static DateTime StampToUtc(string stamp) =>
        DateTime.SpecifyKind(DateTime.ParseExact(stamp, "yyMMdd_HHmmss", CultureInfo.InvariantCulture), DateTimeKind.Utc);

    private static Dictionary<string, string> ParseArgs(string[] args)
    {
        var d = new Dictionary<string, string>();
        for (int i = 0; i + 1 < args.Length; i += 2)
        {
            if (!args[i].StartsWith("--")) throw new ArgumentException("bad arg");
            d[args[i][2..]] = args[i + 1];
        }
        return d;
    }

    private static string Req(Dictionary<string, string> a, string k) => a.TryGetValue(k, out var v) ? v : throw new ArgumentException("missing --" + k);

    private sealed class WallClock : IClock { public DateTime UtcNow => DateTime.UtcNow; }

    private sealed class ReplayLog : IDisposable
    {
        private readonly StreamWriter _w; private readonly object _lock = new();
        public ReplayLog(string path)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(path))!);
            _w = new StreamWriter(path, append: true, new UTF8Encoding(false)) { AutoFlush = true };
        }
        public void Raw(string s) { lock (_lock) _w.WriteLine(s); }
        public void Line(string level, string s) { lock (_lock) _w.WriteLine(DateTime.UtcNow.ToString("O") + " [" + level + "] " + s); }
        public void Dispose() { lock (_lock) _w.Dispose(); }
    }

    private sealed class ReplayLogger<T> : ILogger<T>
    {
        // Rendered text is written only for aggregate-only templates; everything else is dropped (HK-037).
        private const string SubfeasPrefix = "Sub-feas residual pass: residualDecodes=";
        private readonly ReplayLog _log;
        public ReplayLogger(ReplayLog log) { _log = log; }
        public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;
        public bool IsEnabled(LogLevel logLevel) => logLevel >= LogLevel.Information;

        public void Log<TState>(LogLevel level, EventId eventId, TState state, Exception? exception, Func<TState, Exception?, string> formatter)
        {
            if (level < LogLevel.Information) return;
            string template = "";
            if (state is IReadOnlyList<KeyValuePair<string, object?>> kv)
                foreach (var p in kv) if (p.Key == "{OriginalFormat}") template = p.Value?.ToString() ?? "";
            if (template.StartsWith(SubfeasPrefix, StringComparison.Ordinal) && level == LogLevel.Information)
            {
                string t = formatter(state, exception);
                if (_arm is { } arm)
                {
                    Ran[arm]++;
                    if (t.Contains("deadlineAbandoned=True", StringComparison.OrdinalIgnoreCase)) Abandoned[arm]++;
                    if (t.Contains("containedException=True", StringComparison.OrdinalIgnoreCase)) Contained[arm]++;
                }
                _log.Line(level.ToString(), t);
                return;
            }
            if (level >= LogLevel.Warning)
                _log.Line(level.ToString(), "WARN-TEMPLATE " + template + (exception is null ? "" : " exc=" + exception.GetType().Name));
        }
    }
}
