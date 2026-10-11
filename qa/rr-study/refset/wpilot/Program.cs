// REFERENCE-SET W-pilot harness (QA-owned, no src/ change).
// Spec: REFERENCE-SET 2c item 3 + 2f item 4 (arch/reference-set). Protocol: qa/rr-study/refset/wpilot/PROTOCOL.md (frozen before any decode).
//
// ONE PROCESS = ONE (block, W) cell. A fresh process per cell, so the callsign hash table (process-global) starts empty:
//   decode W warm-up cycles in order (output discarded), then L scored cycles in order, through the live DLL
//   (Ft8Decoder.DecodeTwoStageAsync, the STRONG-MISS call), and compare the scored cycles with the LIVE OpenWSFZ rows of the
//   same cycles (owsfz/ALL.TXT, produced with the full-history live process).
// HK-037: message text exists only in memory inside this process; the output is AGGREGATE counters only. The log sink prints only
//   allow-listed aggregate templates. Nothing per message is written, not even a temp file.
// JIT warm-up: one discarded decode of the committed SYNTHETIC fixture synth-qso-01.wav (Q-prefix calls only), so no real
//   history from any other cycle can enter the hash table.
//
// Modes:   (default)          one cell
//          --selftest true    pure-logic checks (no files, no decoder); exit 0 = pass

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
    private const int CycleSeconds = 15;

    private static readonly Regex HashRe = new(@"<[^>]*>", RegexOptions.Compiled);
    private static readonly Regex WsRe = new(@"\s+", RegexOptions.Compiled);

    private static string Norm(string s) => string.Join(" ", WsRe.Split(s.Trim()).Where(x => x.Length > 0));
    private static string KeyOf(string text) => HashRe.Replace(Norm(text), "<HASH>");
    private static bool IsHashed(string text) => text.Contains('<');          // any bracketed call (resolved <CALL> or <...>)
    private static bool HasDots(string text) => text.Contains("<...>", StringComparison.Ordinal);

    // ------------------------------------------------------------ scoring (pure functions, unit-checked by --selftest)
    internal sealed class Counts
    {
        public int LiveRows, LiveNonHashed, LiveHashed;
        public int ReproAll, ReproNonHashed, ReproHashedKey, ReproHashedExact;
        public int OwnRows, ExtraAll, ExtraNonHashed, ExtraHashedKey;
        // hashed rows whose key matched but the rendering differs
        public int RenderLiveResolvedOwnDots, RenderLiveDotsOwnResolved, RenderBothResolvedDifferent;
        public int LiveHashedDots;                                             // live hashed rows rendered <...>
    }

    private static Dictionary<string, List<string>> ByKey(IEnumerable<string> texts)
    {
        var d = new Dictionary<string, List<string>>(StringComparer.Ordinal);
        foreach (var t in texts)
        {
            string n = Norm(t);
            string k = KeyOf(n);
            if (!d.TryGetValue(k, out var l)) d[k] = l = new();
            l.Add(n);
        }
        return d;
    }

    internal static void ScoreCycle(IReadOnlyList<string> live, IReadOnlyList<string> own, Counts c)
    {
        var L = ByKey(live); var O = ByKey(own);
        foreach (var t in live) { c.LiveRows++; if (IsHashed(t)) { c.LiveHashed++; if (HasDots(t)) c.LiveHashedDots++; } else c.LiveNonHashed++; }
        c.OwnRows += own.Count;
        foreach (var (key, lt) in L)
        {
            O.TryGetValue(key, out var ot);
            int n = Math.Min(lt.Count, ot?.Count ?? 0);
            bool hashed = key.Contains("<HASH>", StringComparison.Ordinal);
            c.ReproAll += n;
            if (hashed) c.ReproHashedKey += n; else c.ReproNonHashed += n;
            if (hashed && n > 0)
            {
                // exact rendering: multiset intersection of the normalised texts inside the key group
                var pool = new Dictionary<string, int>(StringComparer.Ordinal);
                foreach (var t in ot!) { pool.TryGetValue(t, out int x); pool[t] = x + 1; }
                var leftLive = new List<string>();
                int exact = 0;
                foreach (var t in lt)
                {
                    if (pool.TryGetValue(t, out int x) && x > 0) { pool[t] = x - 1; exact++; } else leftLive.Add(t);
                }
                var leftOwn = pool.SelectMany(kv => Enumerable.Repeat(kv.Key, kv.Value)).ToList();
                c.ReproHashedExact += exact;
                int pairs = Math.Min(leftLive.Count, leftOwn.Count);
                for (int i = 0; i < pairs; i++)
                {
                    bool ld = HasDots(leftLive[i]), od = HasDots(leftOwn[i]);
                    if (!ld && od) c.RenderLiveResolvedOwnDots++;
                    else if (ld && !od) c.RenderLiveDotsOwnResolved++;
                    else c.RenderBothResolvedDifferent++;
                }
            }
        }
        foreach (var (key, ot) in O)
        {
            L.TryGetValue(key, out var lt);
            int extra = ot.Count - Math.Min(ot.Count, lt?.Count ?? 0);
            bool hashed = key.Contains("<HASH>", StringComparison.Ordinal);
            c.ExtraAll += extra;
            if (hashed) c.ExtraHashedKey += extra; else c.ExtraNonHashed += extra;
        }
    }

    private static int SelfTest()
    {
        int fails = 0;
        void Check(bool ok, string what) { if (!ok) { fails++; Console.WriteLine("FAIL " + what); } }
        Check(KeyOf("CQ <...> JO33") == "CQ <HASH> JO33" && KeyOf("CQ  <Q1AW>  JO33") == "CQ <HASH> JO33", "key collapses brackets and whitespace");
        Check(IsHashed("Q1ABC <Q9XYZ> R-08") && IsHashed("<...> Q1ABC RR73") && !IsHashed("CQ Q1ABC FN42"), "hashed detection");

        var c = new Counts();
        ScoreCycle(new[] { "CQ Q1ABC FN42", "<Q9XYZ> Q1AW -10", "<...> Q1ABC RR73", "Q1ABC Q1AW R-05" },
                   new[] { "CQ Q1ABC FN42", "<...> Q1AW -10", "<...> Q1ABC RR73", "Q1ZZZ Q1AW 73" }, c);
        Check(c.LiveRows == 4 && c.LiveNonHashed == 2 && c.LiveHashed == 2 && c.LiveHashedDots == 1, "live counts");
        Check(c.ReproAll == 3 && c.ReproNonHashed == 1 && c.ReproHashedKey == 2, "reproduced by key: all 3, non-hashed 1, hashed 2");
        Check(c.ReproHashedExact == 1 && c.RenderLiveResolvedOwnDots == 1 && c.RenderLiveDotsOwnResolved == 0, "exact hashed 1; one live-resolved/own-dots");
        Check(c.OwnRows == 4 && c.ExtraAll == 1 && c.ExtraNonHashed == 1 && c.ExtraHashedKey == 0, "extra rows");

        // duplicates are not double counted
        var d = new Counts();
        ScoreCycle(new[] { "CQ Q1ABC FN42", "CQ Q1ABC FN42" }, new[] { "CQ Q1ABC FN42" }, d);
        Check(d.ReproAll == 1 && d.ExtraAll == 0 && d.LiveRows == 2, "duplicate key counted once per own row");
        var e = new Counts();
        ScoreCycle(new[] { "<Q9XYZ> Q1AW -10" }, new[] { "<...> Q1AW -10" , "<Q9XYZ> Q1AW -10" }, e);
        Check(e.ReproHashedKey == 1 && e.ReproHashedExact == 1 && e.ExtraHashedKey == 1, "own has both renderings: exact one wins, the other is extra");
        var f = new Counts();
        ScoreCycle(new[] { "<...> Q1AW -10" }, new[] { "<Q9XYZ> Q1AW -10" }, f);
        Check(f.ReproHashedKey == 1 && f.ReproHashedExact == 0 && f.RenderLiveDotsOwnResolved == 1, "live dots, own resolved");
        Console.WriteLine(fails == 0 ? "SELFTEST OK" : $"SELFTEST {fails} FAILED");
        return fails == 0 ? 0 : 1;
    }

    // ------------------------------------------------------------ main
    private static int Main(string[] args)
    {
        try { return RunAsync(args).GetAwaiter().GetResult(); }
        catch (Exception ex) { Console.Error.WriteLine("FATAL " + ex.GetType().Name + " " + (ex is InvalidOperationException || ex is ArgumentException ? ex.Message : "")); return 3; }
    }

    private static int _ran, _abandoned, _contained;

    private static async Task<int> RunAsync(string[] args)
    {
        var a = ParseArgs(args);
        if (a.ContainsKey("selftest")) return SelfTest();
        string owsTxt = Req(a, "ows-alltxt"), wavDir = Req(a, "wav-dir"), firstStamp = Req(a, "first-stamp"), jit = Req(a, "jit-wav");
        string outJson = Req(a, "out-json"), logPath = Req(a, "log");
        int w = int.Parse(Req(a, "w"), CultureInfo.InvariantCulture), l = int.Parse(Req(a, "l"), CultureInfo.InvariantCulture);
        int spanCycles = int.Parse(Req(a, "span"), CultureInfo.InvariantCulture);          // cycles available from first-stamp (72)
        int scoredStart = int.Parse(Req(a, "scored-start"), CultureInfo.InvariantCulture); // index of the first scored cycle in the span (40)
        int nhard = int.Parse(Req(a, "nhard"), CultureInfo.InvariantCulture), signFix = int.Parse(Req(a, "osd-sign-fix"), CultureInfo.InvariantCulture);
        int threads = int.Parse(Req(a, "threads"), CultureInfo.InvariantCulture);
        string label = a.TryGetValue("label", out var lb) ? lb : "unlabelled";
        if (w < 0 || w > scoredStart || scoredStart + l > spanCycles) throw new ArgumentException("W / L do not fit in the span");

        var first = StampToUtc(firstStamp);
        string StampAt(int i) => first.AddSeconds(i * CycleSeconds).ToString("yyMMdd_HHmmss", CultureInfo.InvariantCulture);
        var warm = Enumerable.Range(scoredStart - w, w).Select(StampAt).ToList();
        var scored = Enumerable.Range(scoredStart, l).Select(StampAt).ToList();
        foreach (var s in warm.Concat(scored))
            if (!File.Exists(Path.Combine(wavDir, s + ".wav"))) throw new InvalidOperationException("missing WAV in the block");

        // live reference rows of the scored cycles (read here, held in memory only)
        var scoredSet = new HashSet<string>(scored);
        var liveBy = scored.ToDictionary(s => s, _ => new List<string>());
        foreach (var line in File.ReadLines(owsTxt, Encoding.ASCII))
        {
            var t = line.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries);
            if (t.Length < 8 || !scoredSet.Contains(t[0])) continue;
            liveBy[t[0]].Add(string.Join(" ", t.Skip(7)));
        }

        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outJson))!);
        using var log = new ReplayLog(logPath);
        var decoder = new Ft8Decoder(new WallClock(), new ReplayLogger<Ft8Decoder>(log));
        decoder.SetDecodeParams(KMinScorePass2, OsdCorrThreshold, nhard);
        decoder.SetOsdSignFix(signFix);
        decoder.SetSubtractionMaxThreads(threads);
        decoder.SetSubtractionEnabled(true);
        log.Raw($"# readback start subtractionEnabled={decoder.SubtractionEnabled} threadsConfigured={threads} cores={Environment.ProcessorCount} " +
                $"nhard={nhard} kMinScorePass2={KMinScorePass2} osdCorrThreshold={OsdCorrThreshold.ToString("F2", CultureInfo.InvariantCulture)} " +
                $"shim={Ft8Decoder.LoadedShimVersion} osdSignFixSet={signFix} osdSignFixRead={decoder.GetOsdSignFix()} label={label} w={w} l={l}");

        // JIT warm-up on the synthetic fixture (discarded; Q-prefix calls only)
        await decoder.DecodeTwoStageAsync(ReadWav(jit), StampToUtc(firstStamp), null, _ => Task.CompletedTask);
        int ranAfterJit = _ran, abAfterJit = _abandoned, coAfterJit = _contained;

        var sw = Stopwatch.StartNew();
        async Task<List<string>> DecodeAsync(string stamp)
        {
            var pcm = ReadWav(Path.Combine(wavDir, stamp + ".wav"));
            var all = new List<DecodeResult>();
            var b2 = await decoder.DecodeTwoStageAsync(pcm, StampToUtc(stamp), null, batch => { all.AddRange(batch); return Task.CompletedTask; });
            all.AddRange(b2);
            return all.Select(r => r.Message).ToList();
        }
        foreach (var s in warm) await DecodeAsync(s);                   // history only; output discarded
        double warmS = sw.Elapsed.TotalSeconds;
        var counts = new Counts();
        foreach (var s in scored)
        {
            var own = await DecodeAsync(s);
            ScoreCycle(liveBy[s], own, counts);
        }
        log.Raw("# readback end subtractionEnabled=" + decoder.SubtractionEnabled + " shim=" + Ft8Decoder.LoadedShimVersion);

        var result = new SortedDictionary<string, object>
        {
            ["label"] = label, ["generated_utc"] = DateTime.UtcNow.ToString("O"), ["first_stamp"] = firstStamp, ["W"] = w, ["L"] = l,
            ["warmup_cycles"] = warm.Count, ["scored_cycles"] = scored.Count,
            ["settings"] = new SortedDictionary<string, object> { ["nhard"] = nhard, ["osd_sign_fix"] = signFix, ["threads"] = threads, ["subtraction"] = "ON", ["shim"] = Ft8Decoder.LoadedShimVersion },
            ["counts"] = counts,
            ["residual_pass"] = new SortedDictionary<string, object> { ["ran"] = _ran - ranAfterJit, ["abandoned"] = _abandoned - abAfterJit, ["contained"] = _contained - coAfterJit },
            ["elapsed_s"] = sw.Elapsed.TotalSeconds, ["warmup_elapsed_s"] = warmS,
        };
        File.WriteAllText(outJson, JsonSerializer.Serialize(result, new JsonSerializerOptions { WriteIndented = true, IncludeFields = true }));
        Console.WriteLine("RESULT written " + outJson);
        return 0;
    }

    // ------------------------------------------------------------ helpers (as in StrongMiss / Replay81)
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
                Interlocked.Increment(ref _ran);
                if (t.Contains("deadlineAbandoned=True", StringComparison.OrdinalIgnoreCase)) Interlocked.Increment(ref _abandoned);
                if (t.Contains("containedException=True", StringComparison.OrdinalIgnoreCase)) Interlocked.Increment(ref _contained);
                _log.Line(level.ToString(), t);
                return;
            }
            if (level >= LogLevel.Warning)
                _log.Line(level.ToString(), "WARN-TEMPLATE " + template + (exception is null ? "" : " exc=" + exception.GetType().Name));
        }
    }
}
