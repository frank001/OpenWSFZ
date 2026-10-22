// REFERENCE-SET replay harness: ONE PROCESS = ONE BLOCK (QA-owned, no src/ or native/ change).
// Spec: REFERENCE-SET 2c (blocks: fresh process, W warm-up cycles then L scored), 2i, 2k, 2l (platform-neutral; legs A and D first).
//
// The process decodes the W warm-up cycles of one manifest block in order (output discarded: they only fill the process-global callsign
// hash table), then the L scored cycles, through Ft8Decoder.DecodeTwoStageAsync (the live call, as the W pilot and STRONG-MISS). Scoring is
// NOT done here: the process writes a per-block WORKING file (stamp, snr, dt, freq, text; HK-037 amended 2026-10-10: working files with
// message text are allowed only in D:\Projects\claude\_qa-scratch\<job>\ or its sol equivalent, outside git, read by code only, deleted at
// job close) and a per-block AGGREGATE summary json. Message text never reaches the console, the log or any committed file.
//
// Per block the summary records: pins (native library SHA-256, shim, settings readback at start and end), residual-pass counts per cycle
// (ran / abandoned / contained: 2l item 2 reports abandonments first), wall time and CPU time per block, per-cycle decode time.
//
// Modes:   (default)          one block
//          --selftest true    pure-logic checks; exit 0 = pass

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
    private const int CycleSeconds = 15;
    private const int ExpectedWarmupCycles = 8;      // corpus constant W (manifest.warmup_cycles)
    private const int ExpectedScoredCycles = 32;     // corpus constant L (manifest.scored_cycles)

    private static int _ran, _abandoned, _contained;
    // residual-pass wall time of the most recent call, and the budget field of its log line (spec 2m: recorded per cycle)
    private static long _lastResidualMs = -1;
    private static long _lastFitted = -1;                // fittedSignals of the most recent residual pass (old-CPU profile, 2026-10-13: signals fitted per cycle)
    private static string _lastBudget = "";
    private const string BudgetEnvVar = "OPENWSFZ_SUBTRACTION_BUDGET";   // the QA-proposed name; the Developer may rename (dev-task 2026-10-11): record whatever the build reads

    private static int Main(string[] args)
    {
        try { return RunAsync(args).GetAwaiter().GetResult(); }
        catch (Exception ex)
        {
            // exception type only: never a message, which could carry a path or text
            Console.Error.WriteLine("FATAL " + ex.GetType().Name + " " + (ex is InvalidOperationException || ex is ArgumentException || ex is InvalidDataException ? ex.Message : ""));
            return 3;
        }
    }

    // ------------------------------------------------------------ pure helpers (unit-checked by --selftest)
    internal static string StampAt(string firstStamp, int index) =>
        StampToUtc(firstStamp).AddSeconds(index * CycleSeconds).ToString("yyMMdd_HHmmss", CultureInfo.InvariantCulture);

    internal static string Sanitise(string text) => text.Replace('\t', ' ').Replace('\r', ' ').Replace('\n', ' ');

    private static int SelfTest()
    {
        int fails = 0;
        void Check(bool ok, string what) { if (!ok) { fails++; Console.WriteLine("FAIL " + what); } }
        Check(StampAt("260808_170545", 1) == "260808_170600", "stamp +1 cycle");
        Check(StampAt("260808_235945", 2) == "260809_000015", "stamp rolls over midnight");
        Check(Sanitise("A\tB\nC") == "A B C", "working-file field is one line, one tab-free field");
        Check(Path.GetFileName("x/y/z.wav") == "z.wav", "path helper");
        Console.WriteLine(fails == 0 ? "SELFTEST OK" : $"SELFTEST {fails} FAILED");
        return fails == 0 ? 0 : 1;
    }

    // ------------------------------------------------------------ main
    private static async Task<int> RunAsync(string[] args)
    {
        var a = ParseArgs(args);
        if (a.ContainsKey("selftest")) return SelfTest();
        if (a.ContainsKey("wavlist")) return await RunListAsync(a);

        string manifestPath = Req(a, "manifest"), corpus = Req(a, "corpus"), blockId = Req(a, "block"), leg = Req(a, "leg");
        string outDir = Req(a, "out-dir"), jit = Req(a, "jit-wav"), pass = Req(a, "pass");
        string label = a.TryGetValue("label", out var lb) ? lb : "unlabelled";
        int nhard = int.Parse(Req(a, "nhard"), CultureInfo.InvariantCulture), signFix = int.Parse(Req(a, "osd-sign-fix"), CultureInfo.InvariantCulture);
        int threads = int.Parse(Req(a, "threads"), CultureInfo.InvariantCulture);
        // optional "start:count" (old-CPU profile 4b): decode only those cycle indices of the block, all of them scored, with no warm-up cycles
        int rangeStart = 0, rangeCount = -1;
        if (a.TryGetValue("cycle-range", out var cr))
        {
            var parts = cr.Split(':');
            if (parts.Length != 2) throw new ArgumentException("--cycle-range is start:count");
            rangeStart = int.Parse(parts[0], CultureInfo.InvariantCulture);
            rangeCount = int.Parse(parts[1], CultureInfo.InvariantCulture);
        }
        if (leg != "A" && leg != "B") throw new ArgumentException("--leg must be A (OpenWSFZ recording) or B (WSJT-X recording)");
        string audioSide = leg == "A" ? "owsfz" : "wsjt-x";

        // block from the manifest (an excluded block is refused: skipped, never replaced - 2l item 4)
        using var mdoc = JsonDocument.Parse(File.ReadAllText(manifestPath));
        JsonElement? block = null;
        foreach (var b in mdoc.RootElement.GetProperty("blocks").EnumerateArray())
            if (b.GetProperty("id").GetString() == blockId) { block = b; break; }
        if (block is null) throw new ArgumentException("block id not in the manifest");
        var blk = block.Value;
        if (blk.GetProperty("excluded").GetBoolean()) throw new InvalidOperationException("block is excluded by the corpus scan");
        string run = blk.GetProperty("run").GetString()!;
        int w = blk.GetProperty("warmup_cycles").GetInt32(), l = blk.GetProperty("scored_cycles").GetInt32();
        if (w != ExpectedWarmupCycles || l != ExpectedScoredCycles) throw new InvalidOperationException("manifest W/L differ from the frozen 8/32");
        var cycles = blk.GetProperty("cycles").EnumerateArray().Select(e => e.GetString()!).ToList();
        if (cycles.Count != w + l) throw new InvalidOperationException("cycle list is not W+L");
        string first = cycles[0];
        for (int i = 0; i < cycles.Count; i++)
            if (cycles[i] != StampAt(first, i)) throw new InvalidOperationException("cycles are not contiguous 15 s steps");
        string wavDir = Path.Combine(corpus, audioSide, run);
        foreach (var s in cycles)
            if (!File.Exists(Path.Combine(wavDir, s + ".wav"))) throw new InvalidOperationException("missing WAV in the block");

        string legDir = Path.Combine(outDir, pass, leg);
        Directory.CreateDirectory(legDir);
        string workPath = Path.Combine(legDir, blockId + ".decodes.tsv");
        string sumPath = Path.Combine(legDir, blockId + ".json");

        // pins: the native library actually loaded from beside this executable
        string nativeSha = NativeLibSha(out string nativeName);

        var decoder = new Ft8Decoder(new WallClock(), new CountingLogger<Ft8Decoder>());
        decoder.SetDecodeParams(KMinScorePass2, OsdCorrThreshold, nhard);
        decoder.SetOsdSignFix(signFix);
        decoder.SetSubtractionMaxThreads(threads);
        decoder.SetSubtractionEnabled(true);
        var readbackStart = new SortedDictionary<string, object>
        {
            ["subtractionEnabled"] = decoder.SubtractionEnabled, ["threadsConfigured"] = threads, ["cores"] = Environment.ProcessorCount,
            ["nhard"] = nhard, ["kMinScorePass2"] = KMinScorePass2, ["osdCorrThreshold"] = OsdCorrThreshold, ["shim"] = Ft8Decoder.LoadedShimVersion,
            ["osdSignFixSet"] = signFix, ["osdSignFixRead"] = decoder.GetOsdSignFix(),
        };

        // JIT warm-up on the committed SYNTHETIC fixture (Q-prefix calls only), discarded; the hash table gets no real history from it.
        await decoder.DecodeTwoStageAsync(ReadWav(jit), StampToUtc(first), null, _ => Task.CompletedTask);
        int ran0 = _ran, ab0 = _abandoned, co0 = _contained;

        async Task<List<DecodeResult>> DecodeAsync(string stamp)
        {
            var pcm = ReadWav(Path.Combine(wavDir, stamp + ".wav"));
            var all = new List<DecodeResult>();
            var b2 = await decoder.DecodeTwoStageAsync(pcm, StampToUtc(stamp), null, batch => { all.AddRange(batch); return Task.CompletedTask; });
            all.AddRange(b2);
            return all;
        }

        var proc = Process.GetCurrentProcess();
        var cpu0 = proc.TotalProcessorTime;
        var swAll = Stopwatch.StartNew();
        var cycleInfo = new List<SortedDictionary<string, object>>();
        using (var work = new StreamWriter(workPath + ".part", false, new UTF8Encoding(false)))
        {
            work.WriteLine("stamp\tsnr\tdt\tfreq_hz\ttext");
            for (int i = 0; i < cycles.Count; i++)
            {
                if (rangeCount >= 0 && (i < rangeStart || i >= rangeStart + rangeCount)) continue;
                string s = cycles[i];
                bool scored = rangeCount >= 0 || i >= w;
                int r1 = _ran, a1 = _abandoned, c1 = _contained;
                _lastResidualMs = -1;
                _lastFitted = -1;
                var sw = Stopwatch.StartNew();
                var rows = await DecodeAsync(s);
                double ms = sw.Elapsed.TotalMilliseconds;
                cycleInfo.Add(new SortedDictionary<string, object>
                {
                    ["stamp"] = s, ["scored"] = scored, ["rows"] = rows.Count, ["ms"] = Math.Round(ms, 1),
                    ["ran"] = _ran - r1, ["abandoned"] = _abandoned - a1, ["contained"] = _contained - c1,
                    ["residual_ms"] = _lastResidualMs, ["budget"] = _lastBudget, ["fitted"] = _lastFitted,
                });
                if (!scored) continue;                                          // warm-up: output discarded
                foreach (var r in rows.OrderBy(x => x.FreqHz).ThenBy(x => x.Message, StringComparer.Ordinal))
                    work.WriteLine(string.Join("\t", s, r.Snr.ToString(CultureInfo.InvariantCulture), r.Dt.ToString("F2", CultureInfo.InvariantCulture),
                        r.FreqHz.ToString("F0", CultureInfo.InvariantCulture), Sanitise(r.Message)));
            }
        }
        double wall = swAll.Elapsed.TotalSeconds;
        double cpu = (proc.TotalProcessorTime - cpu0).TotalSeconds;
        File.Move(workPath + ".part", workPath, true);

        var readbackEnd = new SortedDictionary<string, object> { ["subtractionEnabled"] = decoder.SubtractionEnabled, ["shim"] = Ft8Decoder.LoadedShimVersion };
        string nativeShaEnd = NativeLibSha(out _);
        var summary = new SortedDictionary<string, object>
        {
            ["pass"] = pass, ["leg"] = leg, ["label"] = label, ["block"] = blockId, ["run"] = run, ["generated_utc"] = DateTime.UtcNow.ToString("O"),
            ["os"] = System.Runtime.InteropServices.RuntimeInformation.OSDescription, ["os_arch"] = System.Runtime.InteropServices.RuntimeInformation.OSArchitecture.ToString(),
            ["budget_override_env"] = Environment.GetEnvironmentVariable(BudgetEnvVar) ?? "(unset: 13 s default)",
            ["native_lib"] = nativeName, ["native_sha256_start"] = nativeSha, ["native_sha256_end"] = nativeShaEnd,
            ["readback_start"] = readbackStart, ["readback_end"] = readbackEnd,
            ["warmup_cycles"] = w, ["scored_cycles"] = l, ["cycle_range"] = rangeCount >= 0 ? $"{rangeStart}:{rangeCount}" : "all",
            ["residual_pass"] = new SortedDictionary<string, object> { ["ran"] = _ran - ran0, ["abandoned"] = _abandoned - ab0, ["contained"] = _contained - co0 },
            ["wall_s"] = Math.Round(wall, 2), ["cpu_s"] = Math.Round(cpu, 2), ["cycles"] = cycleInfo,
        };
        File.WriteAllText(sumPath + ".part", JsonSerializer.Serialize(summary, new JsonSerializerOptions { WriteIndented = true }));
        File.Move(sumPath + ".part", sumPath, true);
        Console.WriteLine($"BLOCK {blockId} leg {leg} pass {pass}: wall {wall:F1}s cpu {cpu:F1}s abandoned {_abandoned - ab0} of {_ran - ran0} residual passes");
        return 0;
    }

    // ------------------------------------------------------------ OWS-REPLAY-CONSISTENCY list mode (Architect spec 2026-10-16-1635 + amendment 1)
    // ONE PROCESS = ONE RUN-REPEAT: decodes the WAVs named in --wavlist, in list order, through the live call, and tags every decode with its batch
    // (1 = pass 0, handed to the callback; 2 = the residual pass, returned). List file: one line per item, "index<TAB>wav path<TAB>cycle stamp".
    // Working file (message text, scratch only, HK-037): index, batch, snr, dt, freq, text. Summary json: pins, readback, per-item rows / ms / residual-pass flags.
    private static async Task<int> RunListAsync(Dictionary<string, string> a)
    {
        string listPath = Req(a, "wavlist"), outDir = Req(a, "out-dir"), runId = Req(a, "run-id"), jit = Req(a, "jit-wav");
        string label = a.TryGetValue("label", out var lb) ? lb : "unlabelled";
        int nhard = int.Parse(Req(a, "nhard"), CultureInfo.InvariantCulture), signFix = int.Parse(Req(a, "osd-sign-fix"), CultureInfo.InvariantCulture);
        int threads = int.Parse(Req(a, "threads"), CultureInfo.InvariantCulture);
        var items = new List<(int Index, string Path, string Stamp)>();
        foreach (var line in File.ReadAllLines(listPath))
        {
            if (line.Length == 0) continue;
            var f = line.Split('\t');
            if (f.Length != 3) throw new InvalidDataException("wavlist line is not index<TAB>path<TAB>stamp");
            items.Add((int.Parse(f[0], CultureInfo.InvariantCulture), f[1], f[2]));
        }
        if (items.Count == 0) throw new InvalidDataException("empty wavlist");
        foreach (var it in items) if (!File.Exists(it.Path)) throw new InvalidOperationException("missing WAV in the list");
        Directory.CreateDirectory(outDir);
        string workPath = Path.Combine(outDir, runId + ".decodes.tsv"), sumPath = Path.Combine(outDir, runId + ".json");

        string nativeSha = NativeLibSha(out string nativeName);
        var decoder = new Ft8Decoder(new WallClock(), new CountingLogger<Ft8Decoder>());
        decoder.SetDecodeParams(KMinScorePass2, OsdCorrThreshold, nhard);
        decoder.SetOsdSignFix(signFix);
        decoder.SetSubtractionMaxThreads(threads);
        decoder.SetSubtractionEnabled(true);
        var readbackStart = new SortedDictionary<string, object>
        {
            ["subtractionEnabled"] = decoder.SubtractionEnabled, ["threadsConfigured"] = threads, ["cores"] = Environment.ProcessorCount,
            ["nhard"] = nhard, ["kMinScorePass2"] = KMinScorePass2, ["osdCorrThreshold"] = OsdCorrThreshold, ["shim"] = Ft8Decoder.LoadedShimVersion,
            ["osdSignFixSet"] = signFix, ["osdSignFixRead"] = decoder.GetOsdSignFix(),
        };
        await decoder.DecodeTwoStageAsync(ReadWav(jit), StampToUtc(items[0].Stamp), null, _ => Task.CompletedTask);   // JIT warm-up on the synthetic fixture, discarded
        int ran0 = _ran, ab0 = _abandoned, co0 = _contained;

        var proc = Process.GetCurrentProcess();
        var cpu0 = proc.TotalProcessorTime;
        var swAll = Stopwatch.StartNew();
        var itemInfo = new List<SortedDictionary<string, object>>();
        int nUntagged = 0;
        using (var work = new StreamWriter(workPath + ".part", false, new UTF8Encoding(false)))
        {
            work.WriteLine("index\tbatch\tsnr\tdt\tfreq_hz\ttext");
            foreach (var it in items)
            {
                var pcm = ReadWav(it.Path);
                int r1 = _ran, a1 = _abandoned, c1 = _contained;
                _lastResidualMs = -1;
                _lastFitted = -1;
                var batch1 = new List<DecodeResult>();
                var sw = Stopwatch.StartNew();
                var batch2 = await decoder.DecodeTwoStageAsync(pcm, StampToUtc(it.Stamp), null, b => { batch1.AddRange(b); return Task.CompletedTask; });
                double ms = sw.Elapsed.TotalMilliseconds;
                itemInfo.Add(new SortedDictionary<string, object>
                {
                    ["index"] = it.Index, ["stamp"] = it.Stamp, ["rows_b1"] = batch1.Count, ["rows_b2"] = batch2.Count, ["ms"] = Math.Round(ms, 1),
                    ["ran"] = _ran - r1, ["abandoned"] = _abandoned - a1, ["contained"] = _contained - c1, ["residual_ms"] = _lastResidualMs, ["fitted"] = _lastFitted,
                });
                foreach (var (rows, batch) in new[] { (batch1, 1), (batch2.ToList(), 2) })
                    foreach (var r in rows.OrderBy(x => x.FreqHz).ThenBy(x => x.Message, StringComparer.Ordinal))
                        work.WriteLine(string.Join("\t", it.Index.ToString(CultureInfo.InvariantCulture), batch.ToString(CultureInfo.InvariantCulture),
                            r.Snr.ToString(CultureInfo.InvariantCulture), r.Dt.ToString("F2", CultureInfo.InvariantCulture),
                            r.FreqHz.ToString("F0", CultureInfo.InvariantCulture), Sanitise(r.Message)));
            }
        }
        double wall = swAll.Elapsed.TotalSeconds, cpu = (proc.TotalProcessorTime - cpu0).TotalSeconds;
        File.Move(workPath + ".part", workPath, true);
        var summary = new SortedDictionary<string, object>
        {
            ["mode"] = "wavlist", ["run_id"] = runId, ["label"] = label, ["generated_utc"] = DateTime.UtcNow.ToString("O"),
            ["os"] = System.Runtime.InteropServices.RuntimeInformation.OSDescription, ["budget_override_env"] = Environment.GetEnvironmentVariable(BudgetEnvVar) ?? "(unset: 13 s default)",
            ["native_lib"] = nativeName, ["native_sha256_start"] = nativeSha, ["native_sha256_end"] = NativeLibSha(out _),
            ["readback_start"] = readbackStart,
            ["readback_end"] = new SortedDictionary<string, object> { ["subtractionEnabled"] = decoder.SubtractionEnabled, ["shim"] = Ft8Decoder.LoadedShimVersion },
            ["items"] = items.Count, ["untagged_decodes"] = nUntagged,
            ["residual_pass"] = new SortedDictionary<string, object> { ["ran"] = _ran - ran0, ["abandoned"] = _abandoned - ab0, ["contained"] = _contained - co0 },
            ["wall_s"] = Math.Round(wall, 2), ["cpu_s"] = Math.Round(cpu, 2), ["item_info"] = itemInfo,
        };
        File.WriteAllText(sumPath + ".part", JsonSerializer.Serialize(summary, new JsonSerializerOptions { WriteIndented = true }));
        File.Move(sumPath + ".part", sumPath, true);
        Console.WriteLine($"RUN {runId}: {items.Count} items, wall {wall:F1}s cpu {cpu:F1}s abandoned {_abandoned - ab0} of {_ran - ran0} residual passes");
        return 0;
    }

    // ------------------------------------------------------------ helpers
    private static string NativeLibSha(out string name)
    {
        // the build output carries all three platforms' libraries; the pin is the one this OS loads
        name = OperatingSystem.IsWindows() ? "libft8.dll" : OperatingSystem.IsMacOS() ? "libft8.dylib" : "libft8.so";
        string path = Path.Combine(AppContext.BaseDirectory, name);
        if (!File.Exists(path)) throw new InvalidOperationException("native library " + name + " is not beside the executable");
        using var fs = File.OpenRead(path);
        return Convert.ToHexString(SHA256.HashData(fs)).ToLowerInvariant();
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

    // Counts the residual-pass summary lines; every other log record is dropped (HK-037: nothing else is rendered anywhere).
    private sealed class CountingLogger<T> : ILogger<T>
    {
        private const string SubfeasPrefix = "Sub-feas residual pass: residualDecodes=";
        public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;
        public bool IsEnabled(LogLevel logLevel) => logLevel >= LogLevel.Information;

        public void Log<TState>(LogLevel level, EventId eventId, TState state, Exception? exception, Func<TState, Exception?, string> formatter)
        {
            if (level != LogLevel.Information) return;
            string template = "";
            if (state is IReadOnlyList<KeyValuePair<string, object?>> kv)
                foreach (var p in kv) if (p.Key == "{OriginalFormat}") template = p.Value?.ToString() ?? "";
            if (!template.StartsWith(SubfeasPrefix, StringComparison.Ordinal)) return;
            string t = formatter(state, exception);
            var em = System.Text.RegularExpressions.Regex.Match(t, @"elapsedMs=(\d+)");
            if (em.Success) Interlocked.Exchange(ref _lastResidualMs, long.Parse(em.Groups[1].Value, CultureInfo.InvariantCulture));
            var fm = System.Text.RegularExpressions.Regex.Match(t, @"fittedSignals=(\d+)");
            if (fm.Success) Interlocked.Exchange(ref _lastFitted, long.Parse(fm.Groups[1].Value, CultureInfo.InvariantCulture));
            var bm = System.Text.RegularExpressions.Regex.Match(t, @"budgetMs=(\S+)");
            _lastBudget = bm.Success ? bm.Groups[1].Value : "";          // empty on a build without the override field
            Interlocked.Increment(ref _ran);
            if (t.Contains("deadlineAbandoned=True", StringComparison.OrdinalIgnoreCase)) Interlocked.Increment(ref _abandoned);
            if (t.Contains("containedException=True", StringComparison.OrdinalIgnoreCase)) Interlocked.Increment(ref _contained);
        }
    }
}
