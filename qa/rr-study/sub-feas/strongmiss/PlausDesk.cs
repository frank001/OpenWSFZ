// STRONG-MISS follow-up A (desk, no decoding): what the product's plausibility filter rejects among real WSJT-X decodes.
// Spec: qa/rr-study/2026-10-10-1400-architect-to-qa-spec-strong-miss-followups-a-b.md section A (arch/strong-miss 0625c6fd).
//
// Applies the product's own Ft8Decoder.IsPlausibleMessage (reflection, no grammar store) to every non-';' WSJT-X row of the night.
// Message text exists only inside this function's loops (HK-037); only aggregate counters leave. Nothing per message on disk.
//
// Attribution (mechanical): the token-count rules are a port of the Architect's pf_01 token_rule(); a row rejected by the product
// but passing token_rule() is a "shape rule" row. For shape rows the failing POSITION is found by substituting one token at a
// time with a known-valid call (Q1ABC) and asking the product again: positions whose substitution alone makes the row plausible.
// Only positions are reported, never tokens.

using System.Text.Json;
using System.Text.RegularExpressions;

internal static partial class Program
{
    private const string SubstituteCall = "Q1ABC";
    private static readonly string[] SnrBins = { "1: <= -20", "2: (-20,-15]", "3: (-15,-10]", "4: (-10,-5]", "5: (-5,0]", "6: > 0" };

    private static string SnrBin(double s) => s <= -20 ? SnrBins[0] : s <= -15 ? SnrBins[1] : s <= -10 ? SnrBins[2] : s <= -5 ? SnrBins[3] : s <= 0 ? SnrBins[4] : SnrBins[5];

    // Port of pf_01 token_rule(); returns the rule name or null.
    internal static string? TokenRule(string text)
    {
        var toks = text.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries);
        int n = toks.Length;
        if (n == 4 && toks[0] != "CQ") return "4-token non-CQ";
        if (n >= 5) return "5+ tokens";
        if (n == 2 && toks[0] == "CQ" && toks[1].StartsWith('<')) return "CQ <hash>";
        if (n == 3)
        {
            string last = toks[2];
            if (last == "RRR" || last == "73" || last == "RR73" || last.Contains('<') || Regex.IsMatch(last, @"^R?[+-][0-9]{2}$")) return null;
            if (last.Length == 4 && last.Substring(2).All(char.IsAsciiDigit))
            {
                if (last.Substring(0, 2).All(c => char.IsAsciiLetter(c)))
                    return (string.CompareOrdinal(last.Substring(0, 1), "R") <= 0 && string.CompareOrdinal(last.Substring(1, 1), "R") <= 0) ? null : "bad grid";
                return null;
            }
            if (last.Length > 0 && last.All(char.IsAsciiDigit)) return null;
            return "3-token unknown last field";
        }
        return null;
    }

    private static bool Substitutable(string tok) =>
        tok != "CQ" && tok != "DE" && tok != "QRZ" && tok != "RRR" && tok != "73" && tok != "RR73" && tok != "R" && !tok.Contains('<')
        && !GridRe.IsMatch(tok) && !ReportRe.IsMatch(tok);

    private static string ShapePosition(string text)
    {
        var toks = text.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries);
        var fix = new List<int>();
        for (int i = 0; i < toks.Length; i++)
        {
            if (!Substitutable(toks[i])) continue;
            var t2 = (string[])toks.Clone();
            t2[i] = SubstituteCall;
            if (_plausible!(string.Join(" ", t2))) fix.Add(i);
        }
        string pat = fix.Count == 0 ? "no single-token substitution fixes it" : "token index " + string.Join("+", fix);
        return $"{toks.Length}-token form: {pat}";
    }

    private static void Bump(Dictionary<string, int> d, string k) { d.TryGetValue(k, out int n); d[k] = n + 1; }

    private static int PlausDesk(Dictionary<string, string> a)
    {
        BindProduct();
        var d = Derive(Req(a, "ows-alltxt"), Req(a, "wsjt-alltxt"));

        // re-run the standing matching rule on the same Row objects Derive built (T membership is by reference)
        var byO = new Dictionary<(string, string), int>();
        foreach (var r in d.Ows) { var k = (r.Ts, r.Key); byO.TryGetValue(k, out int c); byO[k] = c + 1; }
        var byWRank = new Dictionary<(string, string), int>();
        var matched = new List<Row>(); var only = new List<Row>();
        foreach (var r in d.Wsj)
        {
            var k = (r.Ts, r.Key);
            byWRank.TryGetValue(k, out int rank); byWRank[k] = rank + 1;
            byO.TryGetValue(k, out int nOws);
            (rank < nOws ? matched : only).Add(r);      // duplicates paired in order
        }
        if (matched.Count != ExpectMatched || only.Count != ExpectWsjtOnly) throw new InvalidOperationException("matching drifted in desk A");
        var targets = new HashSet<Row>(d.Targets);

        var res = new SortedDictionary<string, object>();
        var counts = new SortedDictionary<string, Dictionary<string, int>>();
        Dictionary<string, int> C(string k) { if (!counts.TryGetValue(k, out var v)) counts[k] = v = new(); return v; }

        int tRejected = 0, tRejectedCapture = 0, tNonSemi = 0;
        foreach (var (label, rows) in new[] { ("matched", matched), ("wsjt_only", only) })
        {
            var c = C(label);
            foreach (var r in rows)
            {
                if (r.Text.Contains(';')) { Bump(c, "skipped ';' rows"); continue; }
                Bump(c, "non-';' rows");
                bool rej = !_plausible!(r.Text);
                if (label == "wsjt_only" && targets.Contains(r)) { tNonSemi++; if (rej) tRejected++; }
                string bin = SnrBin(r.Snr), form = Form(r.Text);
                string? tok = TokenRule(r.Text);
                if (tok is not null) Bump(c, "token rule fires (pf_01 port) | " + tok);
                if (!rej)
                {
                    if (tok is not null) Bump(c, "token rule fires but product ACCEPTS");
                    continue;
                }
                Bump(c, "rejected by product");
                Bump(c, "rejected | by form | " + form);
                Bump(c, "rejected | by SNR bin | " + bin);
                if (tok is not null)
                {
                    Bump(c, "rejected | token rule | " + tok);
                    Bump(c, "rejected | token rule | " + tok + " | form " + form);
                    Bump(c, "rejected | token rule | " + tok + " | SNR " + bin);
                    var tt = r.Text.Split(' ');
                    if (tok == "4-token non-CQ" && tt[2] == "R" && GridRe.IsMatch(tt[3])) Bump(c, "rejected | token rule | 4-token non-CQ | of which CALL CALL R GRID");
                }
                else
                {
                    Bump(c, "rejected | shape rules (product rejects, token_rule passes)");
                    Bump(c, "rejected | shape rules | form " + form);
                    Bump(c, "rejected | shape rules | SNR " + bin);
                    Bump(c, "rejected | shape rules | " + ShapePosition(r.Text));
                }
            }
        }
        // sanity: the product's own accepted rows
        int owsFail = 0, owsTok = 0, owsN = 0;
        foreach (var r in d.Ows) { if (r.Text.Contains(';')) continue; owsN++; if (!_plausible!(r.Text)) owsFail++; if (TokenRule(r.Text) is not null) owsTok++; }

        int mRej = counts["matched"].GetValueOrDefault("rejected by product"), mN = counts["matched"]["non-';' rows"];
        int oRej = counts["wsjt_only"].GetValueOrDefault("rejected by product"), oN = counts["wsjt_only"]["non-';' rows"];
        int tokOnly = counts["wsjt_only"].Where(kv => kv.Key.StartsWith("rejected | token rule | ") && kv.Key.Count(ch => ch == '|') == 2).Sum(kv => kv.Value);
        int shapeOnly = counts["wsjt_only"].GetValueOrDefault("rejected | shape rules (product rejects, token_rule passes)");

        res["counts"] = counts;
        res["matched_rejected"] = Share(mRej, mN);
        res["wsjt_only_rejected"] = Share(oRej, oN);
        res["wsjt_only_rejected_token_rule"] = tokOnly;
        res["wsjt_only_rejected_shape_rule"] = shapeOnly;
        res["T_non_semicolon"] = tNonSemi; res["T_rejected"] = tRejected;
        res["ows_rows_non_semicolon"] = owsN; res["ows_rows_rejected_by_product"] = owsFail; res["ows_rows_failing_token_rule"] = owsTok;
        res["A-V1_matched_rejected_le_0.1pct"] = new Dictionary<string, object> { ["value"] = mRej, ["bar_max"] = (int)Math.Floor(0.001 * ExpectMatched), ["pass"] = mRej <= (int)Math.Floor(0.001 * ExpectMatched) };
        res["A-V2_T_rejected_ge_70"] = new Dictionary<string, object> { ["value"] = tRejected, ["bar_min"] = 70, ["pass"] = tRejected >= 70 };
        Console.WriteLine("PLAUS-DESK " + JsonSerializer.Serialize(res, new JsonSerializerOptions { WriteIndented = true }));
        if (a.TryGetValue("out-json", out var o)) File.WriteAllText(o, JsonSerializer.Serialize(res, new JsonSerializerOptions { WriteIndented = true }));
        return 0;
    }
}
