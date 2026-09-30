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
        if (newFile) csv.WriteLine("run,stratum,stamp,seq,flag,elapsed_ms,decodes,exception");

        // ---- warm-up: one discarded cycle per process start, through the full path ----
        string warm = root.GetProperty("runs").GetProperty(run).GetProperty("warmup").GetString()!;
        var warmPcm = ReadWav(Path.Combine(WavDirFor(run), warm + ".wav"));
        SetFlag(decoder, mode == "alt");
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
            // alt: OFF then ON on even index, ON then OFF on odd index (spreads drift)
            string[] order = idx % 2 == 0 ? ["OFF", "ON"] : ["ON", "OFF"];
            foreach (var flag in order)
            {
                if (done.Contains(stamp + "|" + flag)) continue;
                SetFlag(decoder, flag == "ON");
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
        }
        catch (Exception ex) { exc = ex.GetType().Name; }
        sw.Stop();
        csv.WriteLine(string.Join(",", run, stratum, stamp, seq.ToString(CultureInfo.InvariantCulture), flag,
            sw.Elapsed.TotalMilliseconds.ToString("F1", CultureInfo.InvariantCulture),
            n.ToString(CultureInfo.InvariantCulture), exc));
    }

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
