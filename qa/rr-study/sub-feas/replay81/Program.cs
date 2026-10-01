// SUB-FEAS §8.1 real-band runtime replay harness (QA-owned, no src/ change).
//
// Replays captured endurance cycles through the SAME public decode entry the daemon uses
// (Ft8Decoder.DecodeAsync, so the deadline logic in Ft8Decoder/SubtractionPass is included), one
// cycle at a time, serially, and records wall-clock per decode call.
//
// 🔒 HK-037 / NFR-021: decoded message text exists in memory (it is real third-party traffic) but is
// never written anywhere. Only counts and timings are recorded. The logger writes ONLY:
//   - rendered lines whose template is on a fixed allow-list of aggregate-only templates, and
//   - for Warning/Error lines, the ORIGINAL TEMPLATE (never the rendered text) and the exception TYPE.
// Debug/Trace and any other Information line are dropped (counted only).
//
// Modes:
//   --stratum pilot|M|H   decode each selected cycle; --mode off  => flag not touched (R0 builds have no flag)
//                                                      --mode alt  => OFF and ON, order alternated by cycle index parity
//   --stratum R6          synthetic stress: sum each selected pair, assert peak, decode ON only
// Resume: rows already present in --out (stamp|flag) are skipped, so a crashed process can be restarted.

using System.Diagnostics;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Ft8;

internal static class Program
{
    private const int PcmSamples = 180_000;
    private const int SampleRateHz = 12_000;
    private const int KMinScorePass2 = 10;
    private const float OsdCorrThreshold = 0.10f;
    private const int OsdNhardMax = 40;
    private const float R6PeakCeiling = 0.99f;

    private static int Main(string[] args)
    {
        try { return RunAsync(args).GetAwaiter().GetResult(); }
        catch (Exception ex)
        {
            Console.Error.WriteLine("FATAL " + ex.GetType().Name);   // type only, never text
            return 3;
        }
    }

    private static async Task<int> RunAsync(string[] args)
    {
        var a = ParseArgs(args);
        string selectionPath = Req(a, "selection"), run = Req(a, "run"), stratum = Req(a, "stratum");
        string wavRoot = Req(a, "wav-root"), outCsv = Req(a, "out"), logPath = Req(a, "log");
        string mode = a.TryGetValue("mode", out var m) ? m : "off";
        string label = a.TryGetValue("label", out var l) ? l : "unlabelled";

        using var selDoc = JsonDocument.Parse(File.ReadAllBytes(selectionPath));
        var root = selDoc.RootElement;
        string WavDirFor(string r) => Path.Combine(wavRoot, $"{r}_endurance_run-gathered", "owsfz", "wav");

        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outCsv))!);
        using var log = new ReplayLog(logPath);
        var logger = new ReplayLogger<Ft8Decoder>(log);
        var decoder = new Ft8Decoder(new WallClock(), logger);
        decoder.SetDecodeParams(KMinScorePass2, OsdCorrThreshold, OsdNhardMax);
        // sub-feas-speed-redesign: the ONLY change to this harness for the speed acceptance is the new config key
        // decoder.subtractionMaxThreads (0 = auto). Absent --threads leaves the decoder at its default (auto).
        // Only the candidate build has the setter (-p:HasMaxThreads=true); the base build cannot be asked for it.
        string threadsNote = "default";
        if (a.TryGetValue("threads", out var thr))
        {
#if HAS_MAXTHREADS
            decoder.SetSubtractionMaxThreads(int.Parse(thr, CultureInfo.InvariantCulture));
            threadsNote = thr;
#else
            throw new InvalidOperationException("this build has no subtractionMaxThreads setter");
#endif
        }
        log.Raw($"# harness label={label} run={run} stratum={stratum} mode={mode} threads={threadsNote} shim={Ft8Decoder.LoadedShimVersion}");

        var done = LoadDone(outCsv);
        bool newFile = !File.Exists(outCsv);
        await using var csv = new StreamWriter(outCsv, append: true, new UTF8Encoding(false)) { AutoFlush = true };
        // sub-feas-speed-redesign two-stage acceptance: modes "two"/"two1" write an 11-column CSV (tb1_ms = time to
        // batch 1, b1_n, b2_n); every row in such a file is written 11 columns wide.
        _wide = mode is "two" or "two1";
        if (newFile)
            csv.WriteLine(_wide ? "run,stratum,stamp,seq,flag,elapsed_ms,decodes,exception,tb1_ms,b1_n,b2_n"
                                : "run,stratum,stamp,seq,flag,elapsed_ms,decodes,exception");
        // Optional outcome keys (S1): per decode only NUMERIC fields plus an 8-hex-digit hash of the message text; the
        // text itself never leaves the function that reads it (HK-037 / NFR-021). Written to a gitignored artefact.
        // HK-037 clarification (Architect, 2026-09-30): a text-DERIVED hash counts as message identity. So the per-decode
        // text hash is OFF by default and only written when the explicit flag --outcome-text-hash true is given, which no
        // standard run sets. Default outcome lines are numeric only: stamp,kind,idx,freqHz,dt,snr.
        _outcomeTextHash = a.TryGetValue("outcome-text-hash", out var oth) && oth == "true";
        // Test B (WSJT-X corroboration, Architect's HK-037 ruling): the match is done INSIDE this process, where the decoded
        // text lives in memory, against WSJT-X's ALL.TXT read here; only COUNTS and stamps are written. Needs mode two1.
        if (a.TryGetValue("wsjtx-alltxt", out var wsPath))
        {
            LoadWsjtx(wsPath);
            var tb = Req(a, "testb-out");
            Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(tb))!);
            bool fresh = !File.Exists(tb);
            _testB = new StreamWriter(tb, append: true, new UTF8Encoding(false)) { AutoFlush = true };
            if (fresh) _testB.WriteLine("run,stamp,kind,band,n,corroborated");
        }
        if (a.TryGetValue("outcomes", out var outcomesPath))
        {
            Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outcomesPath))!);
            _outcomes = new StreamWriter(outcomesPath, append: true, new UTF8Encoding(false)) { AutoFlush = true };
        }

        // ---- warm-up: one discarded cycle per process start, through the full path ----
        string warm = root.GetProperty("runs").GetProperty(run).GetProperty("warmup").GetString()!;
        var warmPcm = ReadWav(Path.Combine(WavDirFor(run), warm + ".wav"));
        SetFlag(decoder, mode is "alt" or "two" or "on" or "two1");
        await decoder.DecodeAsync(warmPcm, StampToUtc(warm));
        log.Raw("# warm-up cycle decoded and discarded");

        if (stratum == "R6")
        {
            SetFlag(decoder, true);
            int seq = 0;
            foreach (var pair in root.GetProperty("R6_pairs").EnumerateArray())
            {
                string sa = pair.GetProperty("a").GetString()!, sb = pair.GetProperty("b").GetString()!;
                string ra = pair.GetProperty("a_run").GetString()!, rb = pair.GetProperty("b_run").GetString()!;
                string id = sa + "+" + sb;
                if (done.Contains(id + "|ON")) { seq++; continue; }
                var pa = ReadWav(Path.Combine(WavDirFor(ra), sa + ".wav"));
                var pb = ReadWav(Path.Combine(WavDirFor(rb), sb + ".wav"));
                var sum = new float[PcmSamples];
                float peak = 0f;
                for (int i = 0; i < PcmSamples; i++) { sum[i] = pa[i] + pb[i]; peak = MathF.Max(peak, MathF.Abs(sum[i])); }
                if (peak > R6PeakCeiling)
                {
                    float scale = R6PeakCeiling / peak;
                    for (int i = 0; i < PcmSamples; i++) sum[i] *= scale;
                }
                float peakAfter = 0f;
                for (int i = 0; i < PcmSamples; i++) peakAfter = MathF.Max(peakAfter, MathF.Abs(sum[i]));
                if (peakAfter > R6PeakCeiling + 1e-6f) throw new InvalidOperationException("R6 peak assertion failed");
                await Decode1(decoder, sum, StampToUtc(sa), csv, run: "R6", stratum: "R6", id, seq++, "ON");
            }
            return 0;
        }

        var cycles = root.GetProperty("runs").GetProperty(run).GetProperty(stratum).EnumerateArray()
                         .Select(e => e.GetString()!).ToList();
        for (int idx = 0; idx < cycles.Count; idx++)
        {
            string stamp = cycles[idx];
            var pcm = ReadWav(Path.Combine(WavDirFor(run), stamp + ".wav"));
            var cyc = StampToUtc(stamp);
            if (mode == "off")
            {
                if (!done.Contains(stamp + "|NA"))
                    await Decode1(decoder, pcm, cyc, csv, run, stratum, stamp, idx, "NA");
                continue;
            }
            // "on": flag ON, single-batch DecodeAsync, ONE call per cycle (the S1 reference; same native call sequence
            // as "two1", so the process-global callsign hash table has the same history in both).
            if (mode == "on")
            {
                if (done.Contains(stamp + "|ON")) continue;
                SetFlag(decoder, true);
                await Decode1(decoder, pcm, cyc, csv, run, stratum, stamp, idx, "ON");
                continue;
            }
#if HAS_TWOSTAGE
            // "two1": flag ON, DecodeTwoStageAsync, ONE call per cycle.
            if (mode == "two1")
            {
                if (done.Contains(stamp + "|ON")) continue;
                SetFlag(decoder, true);
                await DecodeTwo(decoder, pcm, cyc, csv, run, stratum, stamp, idx);
                continue;
            }
#endif
            // alt / two: OFF then ON on even index, ON then OFF on odd index (spreads drift). "two" makes the ON call
            // the two-stage one and records the time to batch 1.
            string[] order = idx % 2 == 0 ? ["OFF", "ON"] : ["ON", "OFF"];
            foreach (var flag in order)
            {
                if (done.Contains(stamp + "|" + flag)) continue;
                SetFlag(decoder, flag == "ON");
#if HAS_TWOSTAGE
                if (mode == "two" && flag == "ON")
                {
                    await DecodeTwo(decoder, pcm, cyc, csv, run, stratum, stamp, idx);
                    continue;
                }
#endif
                await Decode1(decoder, pcm, cyc, csv, run, stratum, stamp, idx, flag);
            }
        }
        return 0;
    }

    private static async Task Decode1(Ft8Decoder d, float[] pcm, DateTime cycleStart, StreamWriter csv,
                                      string run, string stratum, string stamp, int seq, string flag)
    {
        string exc = "";
        int n = -1;
        var sw = Stopwatch.StartNew();
        try
        {
            var res = await d.DecodeAsync(pcm, cycleStart);
            n = res.Count;
            WriteOutcomes(stamp, flag == "ON" ? "single_on" : "single_off", res);
        }
        catch (Exception ex) { exc = ex.GetType().Name; }
        sw.Stop();
        csv.WriteLine(string.Join(",", run, stratum, stamp, seq.ToString(CultureInfo.InvariantCulture), flag,
            sw.Elapsed.TotalMilliseconds.ToString("F1", CultureInfo.InvariantCulture),
            n.ToString(CultureInfo.InvariantCulture), exc) + (_wide ? ",,," : ""));
    }

    private static bool _wide;
    private static StreamWriter? _outcomes;
    private static bool _outcomeTextHash;   // default OFF (HK-037: a text-derived hash is message identity)

    // ---- Test B: in-process WSJT-X corroboration (counts only) -----------------------------------------------
    private static StreamWriter? _testB;
    private static readonly Dictionary<string, List<(int Snr, int Freq, string Msg)>> _wsjtx = new();
    private const int CorroborationDeltaHz = 10;   // Amendment-1 / Stage 2 convention (|df| <= 10 Hz)

    /// <summary>
    /// Pre-registered SNR bands of the OpenWSFZ decode, for the per-band report (a pooled rate would hide whether
    /// uncorroborated decodes cluster at the weak end, where false positives live): A >= 0, B -10..-1, C -15..-11, D <= -16 dB.
    /// </summary>
    private static string BandOf(int snr) => snr >= 0 ? "A" : snr >= -10 ? "B" : snr >= -15 ? "C" : "D";

    private static void LoadWsjtx(string path)
    {
        // Same line convention as corpus.py _load_all_txt: field 3 "Rx", field 4 "FT8", snr, dt, freq, then the message.
        // The message text stays in this dictionary in memory; it is never written anywhere.
        foreach (var line in File.ReadLines(path))
        {
            var f = line.Split(' ', StringSplitOptions.RemoveEmptyEntries);
            if (f.Length < 8 || f[2] != "Rx" || f[3] != "FT8") continue;
            if (!int.TryParse(f[4], out int snr) || !int.TryParse(f[6], out int freq)) continue;
            if (!_wsjtx.TryGetValue(f[0], out var l)) _wsjtx[f[0]] = l = new();
            l.Add((snr, freq, string.Join(" ", f.Skip(7)).Trim()));
        }
    }

    /// <summary>
    /// Scores one cycle: each OpenWSFZ decode (batch 1 = pass-0, batch 2 = the residual decodes) is corroborated iff
    /// WSJT-X decoded the same message text in the same cycle within 10 Hz, paired ONE-TO-ONE nearest-first across both
    /// batches (a WSJT-X decode corroborates at most one OpenWSFZ decode). Emits COUNTS per (kind, SNR band); text never leaves.
    /// </summary>
    private static void ScoreTestB(string run, string stamp, IReadOnlyList<DecodeResult> b1, IReadOnlyList<DecodeResult> b2)
    {
        if (_testB is null) return;
        var w = _wsjtx.TryGetValue(stamp, out var l) ? l : new List<(int Snr, int Freq, string Msg)>();
        var ows = new List<(int Kind, int Snr, int Freq, string Msg)>();
        foreach (var r in b1) ows.Add((1, r.Snr, r.FreqHz, r.Message.TrimEnd()));
        foreach (var r in b2) ows.Add((2, r.Snr, r.FreqHz, r.Message.TrimEnd()));
        var cands = new List<(int Df, int Oi, int Wi)>();
        for (int i = 0; i < ows.Count; i++)
            for (int j = 0; j < w.Count; j++)
            {
                int df = Math.Abs(ows[i].Freq - w[j].Freq);
                if (df <= CorroborationDeltaHz && string.Equals(ows[i].Msg, w[j].Msg, StringComparison.Ordinal))
                    cands.Add((df, i, j));
            }
        cands.Sort((x, y) => x.Df != y.Df ? x.Df.CompareTo(y.Df) : x.Oi != y.Oi ? x.Oi.CompareTo(y.Oi) : x.Wi.CompareTo(y.Wi));
        var usedO = new bool[ows.Count];
        var usedW = new bool[w.Count];
        foreach (var (_, oi, wi) in cands)
        {
            if (usedO[oi] || usedW[wi]) continue;
            usedO[oi] = true;
            usedW[wi] = true;
        }
        foreach (int kind in new[] { 1, 2 })
            foreach (var band in new[] { "A", "B", "C", "D" })
            {
                int n = 0, c = 0;
                for (int i = 0; i < ows.Count; i++)
                    if (ows[i].Kind == kind && BandOf(ows[i].Snr) == band) { n++; if (usedO[i]) c++; }
                _testB.WriteLine(string.Join(",", run, stamp, kind == 1 ? "b1" : "b2", band,
                    n.ToString(CultureInfo.InvariantCulture), c.ToString(CultureInfo.InvariantCulture)));
            }
        _testB.WriteLine(string.Join(",", run, stamp, "ws", "ALL", w.Count.ToString(CultureInfo.InvariantCulture),
            usedW.Count(x => x).ToString(CultureInfo.InvariantCulture)));
    }

    /// <summary>
    /// One line per decode: <c>stamp,kind,idx,freqHz,dt,snr</c> (numeric only). The 7th field, an 8-hex-digit hash of the
    /// message text, is written ONLY when <c>--outcome-text-hash true</c> is given (default off, HK-037: a text-derived
    /// hash is message identity); the text itself is never written anywhere.
    /// </summary>
    private static void WriteOutcomes(string stamp, string kind, IReadOnlyList<DecodeResult> list)
    {
        if (_outcomes is null) return;
        for (int i = 0; i < list.Count; i++)
        {
            var r = list[i];
            var fields = new List<string> { stamp, kind, i.ToString(CultureInfo.InvariantCulture),
                r.FreqHz.ToString(CultureInfo.InvariantCulture), r.Dt.ToString("F1", CultureInfo.InvariantCulture),
                r.Snr.ToString(CultureInfo.InvariantCulture) };
            if (_outcomeTextHash)
                fields.Add(Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(r.Message.TrimEnd())))[..8]);
            _outcomes.WriteLine(string.Join(",", fields));
        }
    }

#if HAS_TWOSTAGE
    /// <summary>
    /// Two-stage decode (Ft8Decoder.DecodeTwoStageAsync): records the time to batch 1 (from just before the call to
    /// the moment the decoder hands batch 1 to the publish callback: the hand-off S2 measures), the whole-call time
    /// (batch 2 available), and both batches' counts.
    /// </summary>
    private static async Task DecodeTwo(Ft8Decoder d, float[] pcm, DateTime cycleStart, StreamWriter csv,
                                        string run, string stratum, string stamp, int seq)
    {
        string exc = "";
        int n1 = -1, n2 = -1;
        double tb1 = -1;
        var sw = Stopwatch.StartNew();
        try
        {
            IReadOnlyList<DecodeResult>? b1 = null;
            var b2 = await d.DecodeTwoStageAsync(pcm, cycleStart, null, batch =>
            {
                tb1 = sw.Elapsed.TotalMilliseconds;
                b1 = batch;
                return Task.CompletedTask;
            });
            n1 = b1?.Count ?? -1;
            n2 = b2.Count;
            if (b1 is not null) WriteOutcomes(stamp, "b1", b1);
            WriteOutcomes(stamp, "b2", b2);
            if (b1 is not null) ScoreTestB(run, stamp, b1, b2);
        }
        catch (Exception ex) { exc = ex.GetType().Name; }
        sw.Stop();
        csv.WriteLine(string.Join(",", run, stratum, stamp, seq.ToString(CultureInfo.InvariantCulture), "ON",
            sw.Elapsed.TotalMilliseconds.ToString("F1", CultureInfo.InvariantCulture),
            (n1 < 0 ? -1 : n1 + Math.Max(0, n2)).ToString(CultureInfo.InvariantCulture), exc,
            tb1.ToString("F1", CultureInfo.InvariantCulture),
            n1.ToString(CultureInfo.InvariantCulture), n2.ToString(CultureInfo.InvariantCulture)));
    }
#endif

    private static void SetFlag(Ft8Decoder d, bool on)
    {
#if HAS_SUBFEAS
        d.SetSubtractionEnabled(on);
#else
        if (on) throw new InvalidOperationException("this build has no subtraction flag");
#endif
    }

    private static HashSet<string> LoadDone(string csvPath)
    {
        var s = new HashSet<string>();
        if (!File.Exists(csvPath)) return s;
        foreach (var line in File.ReadLines(csvPath).Skip(1))
        {
            var p = line.Split(',');
            if (p.Length >= 5) s.Add(p[2] + "|" + p[4]);
        }
        return s;
    }

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
            if (id == "fmt ")
            {
                channels = BitConverter.ToInt16(b, pos + 10);
                rate = BitConverter.ToInt32(b, pos + 12);
                bits = BitConverter.ToInt16(b, pos + 22);
            }
            else if (id == "data") { dataOff = pos + 8; dataLen = len; break; }
            pos += 8 + len + (len & 1);
        }
        // per-file assertions (spec R0): 12 kHz mono 16-bit, exactly 180 000 samples
        if (channels != 1 || rate != SampleRateHz || bits != 16 || dataOff < 0 || dataLen / 2 != PcmSamples)
            throw new InvalidDataException($"WAV assertion failed (ch={channels} rate={rate} bits={bits} samples={dataLen / 2})");
        var pcm = new float[PcmSamples];
        for (int i = 0; i < PcmSamples; i++)
            pcm[i] = BitConverter.ToInt16(b, dataOff + 2 * i) / 32768f;
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

    private static string Req(Dictionary<string, string> a, string k) =>
        a.TryGetValue(k, out var v) ? v : throw new ArgumentException("missing --" + k);

    private sealed class WallClock : IClock { public DateTime UtcNow => DateTime.UtcNow; }

    // ---------------------------------------------------------------- text-safe log sink
    private sealed class ReplayLog : IDisposable
    {
        private readonly StreamWriter _w;
        private readonly object _lock = new();
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
        // Rendered text is only ever written for these two templates: both carry aggregates only.
        private const string SubfeasPrefix = "Sub-feas residual pass: residualDecodes=";
        private const string CyclePrefix = "Cycle {Time}: {Count} decode(s) found";
        private readonly ReplayLog _log;
        public ReplayLogger(ReplayLog log) { _log = log; }
        public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;
        public bool IsEnabled(LogLevel logLevel) => logLevel >= LogLevel.Information;

        public void Log<TState>(LogLevel level, EventId eventId, TState state, Exception? exception,
                                Func<TState, Exception?, string> formatter)
        {
            if (level < LogLevel.Information) return;
            string template = "";
            if (state is IReadOnlyList<KeyValuePair<string, object?>> kv)
                foreach (var p in kv) if (p.Key == "{OriginalFormat}") template = p.Value?.ToString() ?? "";

            if (template.StartsWith(SubfeasPrefix, StringComparison.Ordinal) && level == LogLevel.Information
                || template.StartsWith(CyclePrefix, StringComparison.Ordinal))
            {
                _log.Line(level.ToString(), formatter(state, exception));
                return;
            }
            if (level >= LogLevel.Warning)
            {
                // Template only (placeholders unfilled) + exception TYPE. Never the rendered text.
                _log.Line(level.ToString(), "WARN-TEMPLATE " + template + (exception is null ? "" : " exc=" + exception.GetType().Name));
            }
            // other Information lines: dropped
        }
    }
}
