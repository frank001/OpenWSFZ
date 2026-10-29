#if HAS_INTERNALS
// LATE-SUB (spec 5c33391f + Amendment 1 section 7, e2f7c5b2). QA-owned instrument; NO change under src/ or native/.
// After the product's own decode of each cycle (batches 1-4, exactly as shipped), inside the same process and in cycle order, this runs:
//   V2 : the product's residual pass and third pass reproduced offline (RunAsync / RunThirdPassAsync) from the captured inputs and the hash state saved before each call;
//   V3 : the product's batch 4 reproduced from the captured fallback rows (Merge -> Select -> unpack -> MapNative emulation);
//   arm C : CohFallbackRun on B (R3 where the third pass ran, else R2) with snap(B), published after batch 4 against everything already published;
//   arm L : C, then RunThirdPassAsync(B, fit = batch 3 + batch 4 + batch C, alsoKnown = batch 1 + batch 2) -> R4 and L1, then CohFallbackRun(R4, snap(R4)) -> L2.
// Every extra call is bracketed by HashStateSave / HashStateRestore of the end-of-cycle state, so the next cycle's product decode is untouched (V1).
// Message text is written ONLY under --late-sub-dir (D:\Projects\claude\_qa-scratch, HK-037), read by code, deleted at job close.
using System.Diagnostics;
using System.Globalization;
using System.Text;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Ft8;
using OpenWSFZ.Ft8.Interop;
using OpenWSFZ.Ft8.Subfeas;

internal static class LateSub
{
    public static string? Dir;
    public static bool Ungated;
    public static int Workers = 8;
    private const double UnlimitedBudgetMs = 600_000.0;            // the extra runs are unlimited offline (spec section 2 step 5); 10 minutes is "unlimited" for one cycle
    private const int DiagCheckCycles = 5;                          // D1: the snapshot-vs-diagnostics-switch check runs on the first 5 cycles
    private static int _ordinal;
    private static StreamWriter? _rows, _cyc;

    private readonly record struct Pub(string Msg, int Freq, double Dt, int Snr, Ft8NativeResult Nr);

    private static List<Pub> Map(HashSet<string> seen, IEnumerable<Ft8NativeResult> src)
    {
        // MapNative's publication rules (Ft8Decoder.cs:754-770): per-cycle text set (the text is added BEFORE the plausibility filter), then IsPlausibleMessage.
        var o = new List<Pub>();
        foreach (var nr in src)
        {
            string msg = nr.Message.TrimEnd();
            if (!seen.Add(msg)) continue;
            if (!Ft8Decoder.IsPlausibleMessage(msg, null)) continue;
            o.Add(new Pub(msg, nr.FreqHz, Math.Round(nr.Dt, 1), nr.Snr, nr));
        }
        return o;
    }

    private static bool Same(List<Pub> mine, IReadOnlyList<DecodeResult>? prod)
    {
        prod ??= Array.Empty<DecodeResult>();
        if (mine.Count != prod.Count) return false;
        for (int i = 0; i < mine.Count; i++)
            if (mine[i].Msg != prod[i].Message || mine[i].Freq != prod[i].FreqHz || mine[i].Dt != prod[i].Dt || mine[i].Snr != prod[i].Snr) return false;
        return true;
    }

    /// <summary>Ft8Decoder.cs:1099-1117: picked rows -> unpack -> natives (unrounded OutDtS, rounded FreqHz).</summary>
    private static List<Ft8NativeResult> FbNatives(IReadOnlyList<CohFallbackRow> picked, IFt8NativeInterop inner)
    {
        var natives = new List<Ft8NativeResult>(picked.Count);
        foreach (var row in picked)
        {
            string? text;
            try { text = inner.CohFallbackUnpack(row.Payload); }
            catch (NativeAccessViolationException) { continue; }
            if (string.IsNullOrWhiteSpace(text)) continue;
            natives.Add(new Ft8NativeResult { FreqHz = (int)Math.Round(row.OutFreqHz), Dt = row.OutDtS, Snr = row.SnrDb, Message = text });
        }
        return natives;
    }

    private static bool SameFloats(float[] a, float[] b) => a.AsSpan().SequenceEqual(b);
    private static string F(double v) => v.ToString("R", CultureInfo.InvariantCulture);

    private static int Refused(IEnumerable<Ft8NativeResult> fit, IFt8NativeInterop inner)
    {
        // SubtractionPass.IsReencodable (no '<', at least 3 tokens) and the EncodeMessage guard in RunCore: the texts the fit list cannot use.
        int n = 0;
        foreach (var nr in fit)
        {
            string m = nr.Message.TrimEnd();
            bool ok = !m.Contains('<') && m.Split(' ', StringSplitOptions.RemoveEmptyEntries).Length >= 3;
            if (ok) { try { inner.EncodeMessage(m); } catch (InvalidOperationException) { ok = false; } }
            if (!ok) n++;
        }
        return n;
    }

    public static async Task RunCycle(string stamp, IReadOnlyList<DecodeResult>? b1, IReadOnlyList<DecodeResult>? b2, IReadOnlyList<DecodeResult>? b3, IReadOnlyList<DecodeResult>? b4)
    {
        if (Dir is null) return;
        _rows ??= new StreamWriter(Path.Combine(Dir, "ls_rows.tsv"), false, new UTF8Encoding(false)) { AutoFlush = true };
        _cyc ??= new StreamWriter(Path.Combine(Dir, "ls_cycle.tsv"), false, new UTF8Encoding(false)) { AutoFlush = true };
        if (_ordinal == 0)
            _cyc.WriteLine("stamp\tordinal\tlevel\tcalls\tv2_b1\tv2_b2\tv2_b3\tv2_r3_bytes\tv3_b4\tsnapB\tsnapR4\tdiag_check\tpubC\tpubL1\tpubL2\tfit_n\tfit_refused\tl_outcome\tms_C\tms_Lround\tms_L2\tms_total");
        int ordinal = _ordinal++;
        var self = StageProbeInterop.Self!;
        var inner = self.Inner;
        List<StageProbeInterop.CapCall> calls;
        List<StageProbeInterop.LsRun> runs;
        calls = StageProbeInterop.CapCalls.ToList(); runs = StageProbeInterop.LsRuns.ToList();      // cycle boundary: nothing else is decoding
        var total = Stopwatch.StartNew();
        if (calls.Count == 0 || runs.Count == 0)
        {
            _cyc.WriteLine(string.Join("\t", stamp, ordinal, "none", calls.Count, "-", "-", "-", "-", "-", "-", "-", "-", 0, 0, 0, 0, 0, "-", 0, 0, 0, 0));
            return;
        }
        var hashEnd = new byte[inner.HashStateSize()];
        inner.HashStateSave(hashEnd);                                       // the product's end-of-cycle state: every arm starts from it and every arm leaves it restored
        string level = "O";
        int kB = 0;
        if (calls.Count > 2 && SameFloats(runs[0].Pcm, calls[2].Pcm)) { level = "R3"; kB = 2; }
        else if (calls.Count > 1 && SameFloats(runs[0].Pcm, calls[1].Pcm)) { level = "R2"; kB = 1; }
        bool v2b1 = false, v2b2 = false, v2b3 = false, v2r3 = false, v3b4 = false, snapB = false, snapR4 = false;
        string diag = "-", lOutcome = "-";
        int pubC = 0, pubL1 = 0, pubL2 = 0, fitN = 0, fitRefused = 0;
        double msC = 0, msL = 0, msL2 = 0;
        try
        {
            // ── V2: the product's own passes, offline ───────────────────────────────────────────────────────────────────────────────────
            var n1 = calls[0].Res;
            var seen = new HashSet<string>(StringComparer.Ordinal);
            var pub1 = Map(seen, n1);
            v2b1 = Same(pub1, b1);
            Ft8NativeResult[] n2 = Array.Empty<Ft8NativeResult>(), n3 = Array.Empty<Ft8NativeResult>();
            List<Pub> pub2 = new(), pub3 = new();
            if (calls.Count > 1)
            {
                inner.HashStateRestore(calls[1].Hash);
                n2 = await SubtractionPass.RunAsync(inner, calls[0].Pcm, n1, Workers, null, null, null, CancellationToken.None, null);
                pub2 = n2.Length == 0 ? new() : Map(seen, n2);
            }
            v2b2 = Same(pub2, b2);
            SubtractionPass.ThirdPassResult? third = null;
            if (calls.Count > 1 && n2.Length > 0)
            {
                if (calls.Count > 2) inner.HashStateRestore(calls[2].Hash);
                third = await SubtractionPass.RunThirdPassAsync(inner, calls[1].Pcm, n2, n1, Workers, null, null, null, CancellationToken.None);
                if (third.Outcome == SubtractionPass.ThirdPassOutcome.Ran) { n3 = third.NewResults; pub3 = n3.Length == 0 ? new() : Map(seen, n3); }
            }
            v2b3 = Same(pub3, b3);
            v2r3 = calls.Count > 2 ? (third?.Residual is not null && SameFloats(third.Residual, calls[2].Pcm)) : true;
            // ── V3: batch 4 from the captured fallback rows ─────────────────────────────────────────────────────────────────────────────
            inner.HashStateRestore(runs[0].Hash);
            var residualRows = level == "O" ? null : runs[0].Result?.Rows;
            var originalRows = level == "O" ? runs[0].Result?.Rows : (runs.Count > 1 ? runs[1].Result?.Rows : null);
            var merged = CohFallbackAudioSelector.Merge(originalRows, residualRows, Ungated);
            var picked4 = CoherentFallbackSelector.Select(merged.Rows);
            var n4 = FbNatives(picked4, inner);
            var pub4 = Map(seen, n4);
            v3b4 = Same(pub4, b4);
            // ── arm work, from the product's end-of-cycle hash state ─────────────────────────────────────────────────────────────────────
            if (level == "O" || calls[kB].Snap is null)
            {
                snapB = false;
            }
            else
            {
                var B = calls[kB];
                // D1: the diagnostics switch does not change the snapshot (first cycles only), and the plan parses
                if (ordinal < DiagCheckCycles)
                {
                    inner.HashStateRestore(B.Hash);
                    byte[]? s1 = null, s0 = null;
                    await Task.Run(() =>
                    {
                        inner.SetDiagnosticsEnabled(true); inner.DecodeAll(B.Pcm); s1 = inner.CohFallbackSnapshot();
                        inner.HashStateRestore(B.Hash);
                        inner.SetDiagnosticsEnabled(false); inner.DecodeAll(B.Pcm); s0 = inner.CohFallbackSnapshot();
                        inner.SetDiagnosticsEnabled(true);
                    });
                    bool parses = false;
                    try { parses = s1 is not null && Ft8LibInterop.CohFallbackMakePlan(s1).Rows.Count >= 0 && Ft8LibInterop.CohFallbackMakePlan(s0!).Rows.Count >= 0; } catch { parses = false; }
                    diag = (s1 is not null && s0 is not null && s1.AsSpan().SequenceEqual(s0) && B.Snap!.AsSpan().SequenceEqual(s1) && parses) ? "1" : "0";
                }
                inner.HashStateRestore(hashEnd);
                snapB = true;
                try { Ft8LibInterop.CohFallbackMakePlan(B.Snap); } catch { snapB = false; }
                // arm C
                var sw = Stopwatch.StartNew();
                var resC = inner.CohFallbackRun(B.Pcm, B.Snap, UnlimitedBudgetMs, Workers, true, CancellationToken.None);
                var pickedC = CoherentFallbackSelector.Select(CohFallbackAudioSelector.Merge(null, resC?.Rows, Ungated).Rows);
                var nC = FbNatives(pickedC, inner);
                msC = sw.Elapsed.TotalMilliseconds;
                var pc = Map(seen, nC);
                pubC = pc.Count;
                foreach (var r in pc) _rows.WriteLine(string.Join("\t", stamp, "C", r.Freq, F(r.Nr.Dt), r.Snr, r.Msg));
                // arm L: fit = published batch 3 + batch 4 + batch C, built as the product builds natives (unrounded dt)
                var fit = pub3.Concat(pub4).Concat(pc).Select(p => p.Nr).ToArray();
                fitN = fit.Length;
                fitRefused = Refused(fit, inner);
                var alsoKnown = n1.Concat(n2).ToArray();
                sw.Restart();
                StageProbeInterop.LsArmSnaps.Clear();
                StageProbeInterop.LsMode = 1;
                SubtractionPass.ThirdPassResult t2;
                try { t2 = await SubtractionPass.RunThirdPassAsync(self, B.Pcm, fit, alsoKnown, Workers, null, null, null, CancellationToken.None); }
                finally { StageProbeInterop.LsMode = 0; }
                msL = sw.Elapsed.TotalMilliseconds;
                lOutcome = t2.Outcome;
                if (t2.Outcome == SubtractionPass.ThirdPassOutcome.Ran)
                {
                    var pl1 = t2.NewResults.Length == 0 ? new() : Map(seen, t2.NewResults);
                    pubL1 = pl1.Count;
                    foreach (var r in pl1) _rows.WriteLine(string.Join("\t", stamp, "L1", r.Freq, F(r.Nr.Dt), r.Snr, r.Msg));
                    byte[]? snR4 = StageProbeInterop.LsArmSnaps.Count > 0 ? StageProbeInterop.LsArmSnaps[^1] : null;
                    snapR4 = t2.Residual is not null && snR4 is not null;
                    if (snapR4)
                    {
                        try { Ft8LibInterop.CohFallbackMakePlan(snR4!); } catch { snapR4 = false; }
                        sw.Restart();
                        var res2 = inner.CohFallbackRun(t2.Residual!, snR4!, UnlimitedBudgetMs, Workers, true, CancellationToken.None);
                        var picked2 = CoherentFallbackSelector.Select(CohFallbackAudioSelector.Merge(null, res2?.Rows, Ungated).Rows);
                        var n2b = FbNatives(picked2, inner);
                        msL2 = sw.Elapsed.TotalMilliseconds;
                        var pl2 = Map(seen, n2b);
                        pubL2 = pl2.Count;
                        foreach (var r in pl2) _rows.WriteLine(string.Join("\t", stamp, "L2", r.Freq, F(r.Nr.Dt), r.Snr, r.Msg));
                    }
                }
            }
        }
        finally
        {
            StageProbeInterop.LsMode = 0;
            inner.HashStateRestore(hashEnd);                                // the next cycle's product decode sees exactly the state it would have seen
            inner.SetDiagnosticsEnabled(true);
            inner.SetApBits(Array.Empty<byte>(), Array.Empty<byte>());
        }
        string b(bool x) => x ? "1" : "0";
        _cyc.WriteLine(string.Join("\t", stamp, ordinal, level, calls.Count, b(v2b1), b(v2b2), b(v2b3), b(v2r3), b(v3b4), b(snapB), level == "O" ? "-" : (lOutcome == "-" ? "-" : b(snapR4)),
            diag, pubC, pubL1, pubL2, fitN, fitRefused, lOutcome,
            msC.ToString("F1", CultureInfo.InvariantCulture), msL.ToString("F1", CultureInfo.InvariantCulture), msL2.ToString("F1", CultureInfo.InvariantCulture),
            total.Elapsed.TotalMilliseconds.ToString("F1", CultureInfo.InvariantCulture)));
    }
}
#endif
