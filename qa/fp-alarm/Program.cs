// FP-ALARM (#279) tool, QA-owned (spec arch/fp-alarm-nhard section 1 + Amendment 1; QA (k) review 501a3c83).
// The product's OWN functions are called, never reimplemented: Ft8Decoder.ExtractPrimaryCallsignToken and Ft8Decoder.IsPlausibleMessage (internal, reached through the
// friend assembly name Ft8.FitProbe), Ft8LibInterop.CohFallbackUnpack (the native unpack), CallsignRegionStore.TryMatchPrefix and CallsignGrammarStore (public, Daemon).
//
//   pin       T-PIN       the SHA-256 of the region and grammar files equal the frozen ones; the region store's IsSeedData property is false
//   tclass    T-CLASS     hand-classified synthetic vectors (expected classes are fixed in this file BEFORE the tool ever ran), 100 %
//   sens      s           ghost sensitivity: G-ANY (gates) and G-CQ (descriptive), >= 10,000 kept ghosts each, seed 20261112, Wilson 95 %
//   fa        FA          the false-alarm rate over WSJT-X's decodes of the night (literal, and plausibility-filtered as a descriptive variant), plus P_R (descriptive)
//   pos       T-POS       ARITHMETIC CONTROL: inject plausible G-ANY ghosts at 1x = 1 % and 2x = 2 % of the base's N into our live ALL.TXT (seed 20261113)
//   armcounts           per-cycle counts (E, N, I) of an arm's published rows, and T-X: the alarm over the not-corroborated rows (matched = 0), numbers only
//   prod      T-PROD      the live daemon's published Region against the tool's class, >= 40 cycles, over the daemon's WebSocket
//   verdict               TOOL-OK / TOOL-WEAK / TOOL-FAIL from the rows' JSON files
//
// HK-037: message text exists only in this process's memory; what leaves it is counts. Ghost texts are random and never written anywhere (NFR-021).
// It runs in its OWN process: ghost unpacks feed the process-global hash table.
using System.Globalization;
using System.Net.WebSockets;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon;
using OpenWSFZ.Ft8;
using OpenWSFZ.Ft8.Interop;

namespace FpAlarm;

internal enum Cls { Excluded, Implausible, Resolved }

internal static class Program
{
    // ---- FROZEN DECISION VALUES (each with its source) ---------------------------------------------------------------------------------------------------
    private const int SeedSens = 20261112;          // spec 1.2
    private const int SeedPos = 20261113;           // spec 1.5 (T-POS), disjoint from 1.2
    private const int GhostMinN = 10000;            // spec 1.2: N >= 10,000 kept ghosts for G-ANY
    private const double SepMin = 0.20;             // spec 1.5 T-SEP: Wilson_lo(s) - Wilson_hi(FA) >= 0.20 (the Architect's choice, no data to derive it from)
    private const double PosLo = 0.5, PosHi = 1.5;  // spec 1.5 T-POS: each step's F-hat increase within [0.5, 1.5] x the number injected (the Architect's choice)
    private const double PosStep = 0.01;            // spec 1.5 T-POS: 1x = 1 % of the base's N, 2x = 2 %
    private const double Z95 = 1.959964;            // Wilson 95 %
    private const int ProdMinCycles = 40;           // spec 1.5 T-PROD
    private const long GhostCap = 50_000_000;       // a safety cap on generated ghosts, never reached in practice

    private static readonly JsonSerializerOptions Pretty = new() { WriteIndented = true, NumberHandling = System.Text.Json.Serialization.JsonNumberHandling.AllowNamedFloatingPointLiterals };

    private static async Task<int> Main(string[] argv)
    {
        if (argv.Length == 0) { Console.Error.WriteLine("usage: Ft8.FitProbe pin|tclass|sens|fa|pos|armcounts|prod|verdict --key value ..."); return 2; }
        var a = ParseArgs(argv[1..]);
        try
        {
            return argv[0] switch
            {
                "pin" => await Pin(a),
                "tclass" => await TClass(a),
                "sens" => await Sens(a),
                "fa" => await Fa(a),
                "pos" => await Pos(a),
                "armcounts" => await ArmCounts(a),
                "prod" => await Prod(a),
                "verdict" => Verdict(a),
                "drift" => await Drift(a),
                _ => 2,
            };
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"ERROR {ex.GetType().Name}: {ex.Message}");
            return 3;
        }
    }

    // ---- plumbing ----------------------------------------------------------------------------------------------------------------------------------------
    private static Dictionary<string, string> ParseArgs(string[] v)
    {
        var d = new Dictionary<string, string>(StringComparer.Ordinal);
        for (int i = 0; i + 1 < v.Length; i += 2) d[v[i].TrimStart('-')] = v[i + 1];
        return d;
    }

    private static string Req(Dictionary<string, string> a, string k) => a.TryGetValue(k, out var s) ? s : throw new ArgumentException($"--{k} is required");

    private static string Sha256(string path)
    {
        using var fs = File.OpenRead(path);
        return Convert.ToHexString(SHA256.HashData(fs)).ToLowerInvariant();
    }

    private static int Emit(Dictionary<string, string> a, object result, bool pass)
    {
        string json = JsonSerializer.Serialize(result, Pretty);
        Console.WriteLine(json);
        if (a.TryGetValue("out", out var o)) File.WriteAllText(o, json);
        return pass ? 0 : 1;
    }

    private static async Task<(CallsignRegionStore regions, CallsignGrammarStore grammar)> LoadStores(Dictionary<string, string> a)
    {
        var regions = new CallsignRegionStore(Req(a, "regions"));
        await regions.LoadAsync();
        var grammar = new CallsignGrammarStore(Req(a, "grammar"));
        await grammar.LoadAsync();
        return (regions, grammar);
    }

    private static (double lo, double hi) Wilson(long k, long n)
    {
        if (n == 0) return (double.NaN, double.NaN);
        double p = (double)k / n, z2 = Z95 * Z95, d = 1.0 + z2 / n;
        double centre = (p + z2 / (2.0 * n)) / d;
        double half = Z95 * Math.Sqrt(p * (1.0 - p) / n + z2 / (4.0 * n * n)) / d;
        return (centre - half, centre + half);
    }

    // ---- the classification (spec 1.1): the product's functions ------------------------------------------------------------------------------------------
    internal static Cls Classify(string text, ICallsignRegionStore regions)
    {
        string? token = Ft8Decoder.ExtractPrimaryCallsignToken(text);
        if (token is null || token.StartsWith('<')) return Cls.Excluded;
        return regions.TryMatchPrefix(token) is null ? Cls.Implausible : Cls.Resolved;
    }

    private sealed class Tally
    {
        public long Excluded, Implausible, Resolved;
        public long N => Implausible + Resolved;
        public void Add(Cls c) { if (c == Cls.Excluded) Excluded++; else if (c == Cls.Implausible) Implausible++; else Resolved++; }
    }

    // ---- real-data readers (text stays in memory) --------------------------------------------------------------------------------------------------------
    private static string NormText(string t)
    {
        var tok = t.Split(' ', StringSplitOptions.RemoveEmptyEntries).ToList();
        if (tok.Count > 0 && tok[^1] == "?") tok.RemoveAt(tok.Count - 1);          // WSJT-X marks a low-confidence decode with a trailing "?"
        return string.Join(' ', tok);
    }

    /// <summary>ALL.TXT (WSJT-X and OpenWSFZ share the layout): stamp dial Rx FT8 snr dt freq text.</summary>
    private static IEnumerable<(string stamp, int freq, string text)> ReadAllTxt(string path)
    {
        foreach (var line in File.ReadLines(path))
        {
            var p = line.Split(' ', 8, StringSplitOptions.RemoveEmptyEntries);
            if (p.Length < 8 || p[2] != "Rx" || p[3] != "FT8") continue;
            if (!int.TryParse(p[6], NumberStyles.Integer, CultureInfo.InvariantCulture, out int f)) continue;
            yield return (p[0], f, NormText(p[7]));
        }
    }

    // ---- ghosts (spec 1.2) -------------------------------------------------------------------------------------------------------------------------------
    private static byte[] Payload(Random r, bool cq)
    {
        var bits = new bool[80];
        for (int i = 0; i < 77; i++) bits[i] = r.Next(2) == 1;
        if (cq)
        {   // G-CQ: bits 0-28 = CQ (n28 = 2, ip = 0), i3 = 1 at bits 74-76, bits 29-73 random (spec 1.2)
            for (int i = 0; i < 28; i++) bits[i] = ((2 >> (27 - i)) & 1) == 1;
            bits[28] = false;
            bits[74] = false; bits[75] = false; bits[76] = true;
        }
        var b = new byte[10];
        for (int i = 0; i < 80; i++) if (bits[i]) b[i / 8] |= (byte)(0x80 >> (i % 8));
        return b;
    }

    /// <summary>An endless stream of KEPT ghosts: unpacked by the product's own native unpack, kept only if IsPlausibleMessage (with the station's grammar), classified as in 1.1.</summary>
    private static IEnumerable<Cls> GhostStream(bool cq, Random r, ICallsignRegionStore regions, ICallsignGrammarStore grammar, long cap, Action<long>? generated = null)
    {
        for (long g = 1; g <= cap; g++)
        {
            string? text = Ft8LibInterop.CohFallbackUnpack(Payload(r, cq))?.TrimEnd();
            generated?.Invoke(g);
            if (string.IsNullOrWhiteSpace(text) || !Ft8Decoder.IsPlausibleMessage(text, grammar)) continue;
            yield return Classify(text, regions);
        }
    }

    // ---- T-PIN -------------------------------------------------------------------------------------------------------------------------------------------
    private static async Task<int> Pin(Dictionary<string, string> a)
    {
        var (regions, grammar) = await LoadStores(a);
        string rs = Sha256(Req(a, "regions")), gs = Sha256(Req(a, "grammar"));
        bool rOk = !a.TryGetValue("regions-sha", out var rw) || rs.Equals(rw, StringComparison.OrdinalIgnoreCase);
        bool gOk = !a.TryGetValue("grammar-sha", out var gw) || gs.Equals(gw, StringComparison.OrdinalIgnoreCase);
        bool seedFalse = !regions.IsSeedData;
        bool pass = rOk && gOk && seedFalse && regions.Entries.Count > 0;
        return Emit(a, new { row = "T-PIN", regionsSha256 = rs, grammarSha256 = gs, regionEntries = regions.Entries.Count, regionsIsSeedData = regions.IsSeedData,
                             regionsShaMatches = rOk, grammarShaMatches = gOk, PASS = pass }, pass);
    }

    // ---- T-CLASS: the expected class of every vector is fixed HERE by hand, from the documented forms of ExtractPrimaryCallsignToken -----------------------------------
    // (CQ forms: token 1 for 2/3 tokens, token 2 for 4+; QSO form: token 1, falling back to token 0 when token 1 is hashed or RRR/73/RR73; <...> is EXCLUDED.)
    // 🔒 NFR-021: the committed vectors use Q-prefix calls and PD2FZ (the documented exception). The station's region table has an explicit entry, prefix "Q" ->
    // "Synthetic (R&R Study)" (the NFR-021 carve-out), so a Q-prefix call is RESOLVED, and so is PD2FZ. IMPLAUSIBLE (shape-valid, no region) vectors use the placeholders
    // {U1} and {U2}: tokens built IN PROCESS at run time from letter-letter-digit-AAA shapes whose TryMatchPrefix is null, never printed and never committed.
    // (First version of this table, committed 34eaad5e, expected Q-calls to be IMPLAUSIBLE: wrong, found by this very row; the corrected expectation comes from the
    // table entry above, a fact on the pinned file, not from the tool's answers. The tool's logic did not change.)
    private static readonly (string text, Cls expected, string why)[] Vectors =
    [
        ("CQ", Cls.Excluded, "CQ alone: no candidate token"),
        ("CQ DX <...> JO22", Cls.Excluded, "4 tokens, token 2 hashed"),
        ("CQ <...> JO22", Cls.Excluded, "3 tokens, token 1 hashed"),
        ("<...> <...> -07", Cls.Excluded, "both calls hashed"),
        ("RRR 73", Cls.Excluded, "two terminal keywords"),
        ("CQ {U1}", Cls.Implausible, "2 tokens: token 1, no region"),
        ("CQ {U1} JO22", Cls.Implausible, "3 tokens: token 1, no region"),
        ("CQ DX {U1} JO22", Cls.Implausible, "4 tokens: token 2, no region"),
        ("<...> {U1} -07", Cls.Implausible, "QSO form: token 1, no region"),
        ("{U1} <...> RR73", Cls.Implausible, "token 1 hashed: falls back to token 0, no region"),
        ("{U1} RRR", Cls.Implausible, "token 1 is RRR: falls back to token 0, no region"),
        ("{U1} RR73", Cls.Implausible, "token 1 is RR73: falls back to token 0, no region"),
        ("{U1} {U2} R-10", Cls.Implausible, "QSO form: token 1, no region"),
        ("{U1}/P {U2}/P -05", Cls.Implausible, "portable suffix stripped, still no region"),
        ("PD2FZ {U1} -10", Cls.Implausible, "QSO form: token 1 is the sender, no region"),
        ("CQ PD2FZ JO22", Cls.Resolved, "CQ 3 tokens, region found"),
        ("CQ POTA PD2FZ JO22", Cls.Resolved, "CQ with a modifier, region found"),
        ("{U1} PD2FZ R-12", Cls.Resolved, "QSO form: token 1 is the resolved call"),
        ("PD2FZ <...> RR73", Cls.Resolved, "token 1 hashed: token 0 resolves"),
        ("<...> PD2FZ 73", Cls.Resolved, "QSO form: token 1 resolves"),
        ("CQ PD2FZ/P JO22", Cls.Resolved, "portable suffix stripped, region found"),
        ("CQ Q1ABC JO22", Cls.Resolved, "Q-prefix: the synthetic region entry (NFR-021 carve-out)"),
        ("Q1ABC Q2DEF R-10", Cls.Resolved, "Q-prefix, QSO form: token 1, the synthetic region entry"),
        ("Q1ABC RRR", Cls.Resolved, "Q-prefix: token 1 is RRR, falls back to token 0, the synthetic region entry"),
    ];

    /// <summary>Shape-valid tokens (letter, letter, digit, "AAA") that the pinned table does NOT match; built in process, never printed (NFR-021).</summary>
    private static List<string> FindUnmatched(ICallsignRegionStore regions, int n)
    {
        var found = new List<string>();
        const string L = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
        foreach (char c1 in L)
            foreach (char c2 in L)
                foreach (char d in "0123456789")
                {
                    if (c1 == 'Q') continue;
                    string tok = $"{c1}{c2}{d}AAA";
                    if (regions.TryMatchPrefix(tok) is null) { found.Add(tok); if (found.Count >= n) return found; }
                }
        return found;
    }

    private static async Task<int> TClass(Dictionary<string, string> a)
    {
        var (regions, _) = await LoadStores(a);
        var u = FindUnmatched(regions, 2);
        int agree = 0; var bad = new List<string>();
        if (u.Count < 2) bad.Add($"fewer than 2 unmatched shape-valid tokens exist ({u.Count}): the IMPLAUSIBLE class cannot be constructed from the pinned table");
        else
            for (int i = 0; i < Vectors.Length; i++)
            {
                string text = Vectors[i].text.Replace("{U1}", u[0]).Replace("{U2}", u[1]);
                var got = Classify(text, regions);
                if (got == Vectors[i].expected) agree++; else bad.Add($"#{i + 1} expected {Vectors[i].expected} got {got} ({Vectors[i].why})");
            }
        bool pass = agree == Vectors.Length;
        return Emit(a, new { row = "T-CLASS", vectors = Vectors.Length, agree, unmatchedTokensFound = u.Count, disagreements = bad, PASS = pass }, pass);
    }

    // ---- s: ghost sensitivity ------------------------------------------------------------------------------------------------------------------------------
    private static object GhostResult(string name, bool cq, int seed, ICallsignRegionStore regions, ICallsignGrammarStore grammar, out double s, out double sLo)
    {
        var t = new Tally(); long gen = 0;
        var rng = new Random(seed);
        foreach (var c in GhostStream(cq, rng, regions, grammar, GhostCap, g => gen = g))
        {
            t.Add(c);
            if (t.N >= GhostMinN) break;
        }
        long kept = t.Excluded + t.Implausible + t.Resolved;
        s = t.N == 0 ? double.NaN : (double)t.Implausible / t.N;
        var w = Wilson(t.Implausible, t.N);
        sLo = w.lo;
        return new { model = name, seed, generated = gen, keptPlausible = kept, excluded = t.Excluded, N = t.N, I = t.Implausible, s, wilsonLo = w.lo, wilsonHi = w.hi };
    }

    private static async Task<int> Sens(Dictionary<string, string> a)
    {
        var (regions, grammar) = await LoadStores(a);
        var any = GhostResult("G-ANY", false, SeedSens, regions, grammar, out double sAny, out double sLoAny);
        var cq = GhostResult("G-CQ", true, SeedSens, regions, grammar, out double sCq, out double sLoCq);
        return Emit(a, new { row = "s", gates = any, descriptive = cq, sGAny = sAny, sGAnyWilsonLo = sLoAny, sGCq = sCq }, !double.IsNaN(sAny));
    }

    // ---- FA ------------------------------------------------------------------------------------------------------------------------------------------------
    private static async Task<int> Fa(Dictionary<string, string> a)
    {
        var (regions, grammar) = await LoadStores(a);
        var lit = new Tally(); var plausible = new Tally(); long rows = 0, plausRows = 0;
        foreach (var (_, _, text) in ReadAllTxt(Req(a, "wsjtx")))
        {
            rows++;
            lit.Add(Classify(text, regions));
            if (Ft8Decoder.IsPlausibleMessage(text, grammar)) { plausRows++; plausible.Add(Classify(text, regions)); }
        }
        var w = Wilson(lit.Implausible, lit.N); var wp = Wilson(plausible.Implausible, plausible.N);
        object? own = null;
        if (a.TryGetValue("own", out var ownPath)) own = OwnStats(ownPath, regions, grammar);
        bool pass = lit.N > 0;
        return Emit(a, new
        {
            row = "FA",
            literalAllWsjtxDecodes_gates = new { rows, excluded = lit.Excluded, N = lit.N, I = lit.Implausible, fa = (double)lit.Implausible / lit.N, wilsonLo = w.lo, wilsonHi = w.hi },
            plausibleOnly_descriptive = new { rows = plausRows, excluded = plausible.Excluded, N = plausible.N, I = plausible.Implausible, fa = (double)plausible.Implausible / plausible.N, wilsonLo = wp.lo, wilsonHi = wp.hi },
            faGates = (double)lit.Implausible / lit.N, faWilsonHi = w.hi, own,
        }, pass);
    }

    private static readonly CultureInfo Inv = CultureInfo.InvariantCulture;

    /// <summary>Our own live ALL.TXT: class shares, and P_R (descriptive; the sender rule is the product's primary token, an approximation of CQ-AP-PSK's sender extractor).</summary>
    private static object OwnStats(string path, ICallsignRegionStore regions, ICallsignGrammarStore grammar)
    {
        var all = new Tally(); var rows = new List<(double t, int f, string? sender, Cls c)>();
        foreach (var (stamp, f, text) in ReadAllTxt(path))
        {
            var c = Classify(text, regions); all.Add(c);
            var t = DateTime.ParseExact(stamp, "yyMMdd_HHmmss", Inv, DateTimeStyles.AssumeUniversal | DateTimeStyles.AdjustToUniversal);
            string? tok = Ft8Decoder.ExtractPrimaryCallsignToken(text);
            rows.Add(((t - DateTime.UnixEpoch).TotalSeconds, f, tok is null || tok.StartsWith('<') ? null : tok, c));
        }
        var bySender = rows.Where(r => r.sender is not null).GroupBy(r => r.sender!).ToDictionary(g => g.Key, g => g.ToList());
        var pr = new Tally();
        foreach (var r in rows)
        {
            if (r.sender is null) continue;
            int others = bySender[r.sender].Count(o => !ReferenceEquals(o, r) && o.t != r.t && Math.Abs(o.t - r.t) <= 600 && Math.Abs(o.f - r.f) <= 10);
            if (others >= 2) pr.Add(r.c);
        }
        var w = Wilson(all.Implausible, all.N); var wp = Wilson(pr.Implausible, pr.N);
        return new { rows = rows.Count, excluded = all.Excluded, N = all.N, I = all.Implausible, iOverN = (double)all.Implausible / all.N, wilsonLo = w.lo, wilsonHi = w.hi,
                     P_R_descriptive = new { N = pr.N, I = pr.Implausible, iOverN = pr.N == 0 ? double.NaN : (double)pr.Implausible / pr.N, wilsonLo = wp.lo, wilsonHi = wp.hi } };
    }

    // ---- T-POS: ARITHMETIC CONTROL ---------------------------------------------------------------------------------------------------------------------------
    private static double FHat(double i, double n, double fa, double s) => (i - fa * n) / (s - fa);

    private static async Task<int> Pos(Dictionary<string, string> a)
    {
        var (regions, grammar) = await LoadStores(a);
        double s = ReadNumber(Req(a, "sens"), "sGAny"), fa = ReadNumber(Req(a, "fa"), "faGates");
        var b = new Tally();
        foreach (var (_, _, text) in ReadAllTxt(Req(a, "own"))) b.Add(Classify(text, regions));
        int step = (int)Math.Round(PosStep * b.N);
        // "the number injected" is read as the ghosts that enter N (RESOLVED or IMPLAUSIBLE): F-hat is defined on N, and an EXCLUDED ghost never enters it.
        double i0 = b.Implausible, n0 = b.N;
        var rng = new Random(SeedPos);
        long injN = 0, injI = 0, generated = 0;
        var stream = GhostStream(false, rng, regions, grammar, GhostCap, g => generated = g).GetEnumerator();
        void Inject(int target)
        {
            int added = 0;
            while (added < target && stream.MoveNext())
            {
                if (stream.Current == Cls.Excluded) continue;
                added++; injN++; if (stream.Current == Cls.Implausible) injI++;
            }
        }
        double f0 = FHat(i0, n0, fa, s);
        Inject(step); double f1 = FHat(i0 + injI, n0 + injN, fa, s); long iAfter1 = injI, nAfter1 = injN;
        Inject(step); double f2 = FHat(i0 + injI, n0 + injN, fa, s);
        double d1 = f1 - f0, d2 = f2 - f1;
        bool ok1 = d1 >= PosLo * step && d1 <= PosHi * step, ok2 = d2 >= PosLo * step && d2 <= PosHi * step;
        bool pass = ok1 && ok2 && step > 0;
        return Emit(a, new { row = "T-POS (arithmetic control: s comes from the same G-ANY model it injects; passes whether or not OSD false accepts look like G-ANY)",
                             baseN = b.N, baseI = b.Implausible, baseExcluded = b.Excluded, s, fa, stepGhostsEnteringN = step, ghostsGenerated = generated,
                             fHat0 = f0, fHat1 = f1, fHat2 = f2, increase1 = d1, increase2 = d2, ratio1 = d1 / step, ratio2 = d2 / step, step1InBand = ok1, step2InBand = ok2, PASS = pass }, pass);
    }

    private static double ReadNumber(string jsonPath, string prop)
    {
        using var d = JsonDocument.Parse(File.ReadAllText(jsonPath));
        return d.RootElement.GetProperty(prop).GetDouble();
    }

    // ---- per-cycle counts of an arm's rows (nc.tsv), and T-X -------------------------------------------------------------------------------------------------
    private static async Task<int> ArmCounts(Dictionary<string, string> a)
    {
        var (regions, _) = await LoadStores(a);
        var per = new SortedDictionary<string, Tally>(StringComparer.Ordinal); var all = new Tally(); var unm = new Tally(); long rows = 0, unmatchedRows = 0;
        foreach (var line in File.ReadLines(Req(a, "nc")))
        {
            var p = line.Split('\t');
            if (p.Length < 11) continue;
            string text = string.Join(' ', p[10].Split(' ', StringSplitOptions.RemoveEmptyEntries));
            var c = Classify(text, regions);
            rows++; all.Add(c);
            if (!per.TryGetValue(p[0], out var t)) per[p[0]] = t = new Tally();
            t.Add(c);
            if (p[2] == "0") { unmatchedRows++; unm.Add(c); }
        }
        if (a.TryGetValue("csv", out var csv))
            File.WriteAllLines(csv, new[] { "stamp,excluded,N,I" }.Concat(per.Select(kv => $"{kv.Key},{kv.Value.Excluded},{kv.Value.N},{kv.Value.Implausible}")));
        object? tx = null;
        if (a.TryGetValue("sens", out var sp) && a.TryGetValue("fa", out var fp))
        {
            double s = ReadNumber(sp, "sGAny"), fa = ReadNumber(fp, "faGates");
            tx = new { row = "T-X (descriptive, no bar: no data exists to set one)", notCorroboratedRows = unmatchedRows, excluded = unm.Excluded, N = unm.N, I = unm.Implausible,
                       fHatFloor = FHat(unm.Implausible, unm.N, fa, s), testedAbsentOnFile = a.TryGetValue("ta", out var ta) ? ta : null };
        }
        return Emit(a, new { row = "armcounts", cycles = per.Count, rows, excluded = all.Excluded, N = all.N, I = all.Implausible, tX = tx }, true);
    }

    // ---- T-PROD: the live daemon's published Region against the tool's class ------------------------------------------------------------------------------
    private static JsonElement? Prop(JsonElement e, string camel)
    {
        if (e.ValueKind != JsonValueKind.Object) return null;
        foreach (var p in e.EnumerateObject())
            if (p.Name.Equals(camel, StringComparison.OrdinalIgnoreCase)) return p.Value;
        return null;
    }

    private static async Task<int> Prod(Dictionary<string, string> a)
    {
        var (regions, _) = await LoadStores(a);
        string pinned = Sha256(Req(a, "regions")), live = Sha256(Req(a, "live-regions"));
        if (!pinned.Equals(live, StringComparison.OrdinalIgnoreCase)) throw new InvalidOperationException("the live daemon's region file differs from the pinned copy: T-PROD would compare two tables");
        int port = a.TryGetValue("port", out var ps) ? int.Parse(ps, Inv) : 8080;
        int minutes = a.TryGetValue("max-minutes", out var ms) ? int.Parse(ms, Inv) : 20;
        using var ws = new ClientWebSocket();
        using var cts = new CancellationTokenSource(TimeSpan.FromMinutes(minutes));
        await ws.ConnectAsync(new Uri($"ws://127.0.0.1:{port}/api/v1/ws"), cts.Token);
        var cycles = new HashSet<string>(StringComparer.Ordinal); var tally = new Tally(); long rows = 0, disagree = 0, productResolved = 0;
        var buf = new byte[1 << 16];
        while (cycles.Count < ProdMinCycles && !cts.IsCancellationRequested && ws.State == WebSocketState.Open)
        {
            using var ms2 = new MemoryStream();
            WebSocketReceiveResult r;
            do { r = await ws.ReceiveAsync(buf, cts.Token); ms2.Write(buf, 0, r.Count); } while (!r.EndOfMessage);
            if (r.MessageType == WebSocketMessageType.Close) break;
            using var doc = JsonDocument.Parse(ms2.ToArray());
            if (Prop(doc.RootElement, "type")?.GetString() != "decode") continue;
            var payload = Prop(doc.RootElement, "payload");
            if (payload is null || payload.Value.ValueKind != JsonValueKind.Array) continue;
            foreach (var item in payload.Value.EnumerateArray())
            {
                string? text = Prop(item, "message")?.GetString(); string? time = Prop(item, "time")?.GetString();
                if (text is null || time is null) continue;
                cycles.Add(time); rows++;
                var cls = Classify(string.Join(' ', text.Split(' ', StringSplitOptions.RemoveEmptyEntries)), regions);
                tally.Add(cls);
                var region = Prop(item, "region");
                bool productHas = region is not null && region.Value.ValueKind != JsonValueKind.Null;
                if (productHas) productResolved++;
                if (productHas != (cls == Cls.Resolved)) disagree++;
            }
        }
        bool pass = cycles.Count >= ProdMinCycles && rows > 0 && disagree == 0;
        return Emit(a, new { row = "T-PROD (live daemon route; the replay does not expose Region)", distinctCyclesSeen = cycles.Count, publishedRows = rows, productResolved, toolExcluded = tally.Excluded,
                             toolImplausible = tally.Implausible, toolResolved = tally.Resolved, disagreements = disagree, regionFilesEqual = true, PASS = pass }, pass);
    }

    // ---- drift: DIAGNOSTIC ONLY (not a registered row; added after the registered rows ran, in a separate commit and a separate build folder) ----------------------------------
    // Does the sensitivity s change as ghosts are unpacked in one process (the native call-hash table fills)? Reports kept / N / I per window of generated ghosts.
    private static async Task<int> Drift(Dictionary<string, string> a)
    {
        var (regions, grammar) = await LoadStores(a);
        int seed = a.TryGetValue("seed", out var sd) ? int.Parse(sd, Inv) : SeedPos;
        int window = a.TryGetValue("window", out var ws) ? int.Parse(ws, Inv) : 1000;
        int windows = a.TryGetValue("windows", out var wn) ? int.Parse(wn, Inv) : 20;
        var rng = new Random(seed); var rows = new List<object>();
        long gen = 0;
        for (int w = 0; w < windows; w++)
        {
            var t = new Tally(); long inWindow = 0;
            for (int k = 0; k < window; k++)
            {
                gen++; inWindow++;
                string? text = Ft8LibInterop.CohFallbackUnpack(Payload(rng, false))?.TrimEnd();
                if (string.IsNullOrWhiteSpace(text) || !Ft8Decoder.IsPlausibleMessage(text, grammar)) continue;
                t.Add(Classify(text, regions));
            }
            rows.Add(new { window = w + 1, generatedFrom = gen - inWindow + 1, generatedTo = gen, N = t.N, I = t.Implausible, excluded = t.Excluded, s = t.N == 0 ? double.NaN : (double)t.Implausible / t.N });
        }
        return Emit(a, new { row = "drift (diagnostic)", seed, window, windows = rows }, true);
    }

    // ---- verdict -----------------------------------------------------------------------------------------------------------------------------------------
    private static bool Pass(string path) { using var d = JsonDocument.Parse(File.ReadAllText(path)); return d.RootElement.GetProperty("PASS").GetBoolean(); }

    private static int Verdict(Dictionary<string, string> a)
    {
        bool pin = Pass(Req(a, "pin")), prod = Pass(Req(a, "prod")), cls = Pass(Req(a, "class")), pos = Pass(Req(a, "pos"));
        double sLo = ReadNumber(Req(a, "sens"), "sGAnyWilsonLo"), faHi = ReadNumber(Req(a, "fa"), "faWilsonHi");
        double margin = sLo - faHi; bool sep = margin >= SepMin;
        string verdict = pin && prod && cls && pos && sep ? "TOOL-OK" : pin && prod && cls && pos && !sep ? "TOOL-WEAK" : "TOOL-FAIL";
        return Emit(a, new { row = "verdict", tPin = pin, tProd = prod, tClass = cls, tPosArithmeticControl = pos, tSepMargin = margin, tSepBar = SepMin, tSep = sep, verdict }, true);
    }
}
