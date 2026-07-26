// D-001 runtime-parameter recall/false-positive Pareto sweep — offline decode harness.
//
// Drives the real production OpenWSFZ.Ft8.Ft8Decoder in-process through its PUBLIC API only
// (Ft8Decoder.SetDecodeParams + IModeDecoder.DecodeAsync). For each of the 45 grid points
// (k_min_score_pass2 × osd_corr_threshold × osd_nhard_max) it decodes a directory of 12 kHz
// mono WAVs and writes one WSJT-X-ALL.TXT-format file per point, byte-for-byte matching
// src/OpenWSFZ.Daemon/AllTxtWriter.cs:99 so the existing Python scorers ingest it unchanged.
//
// Scoring (recall via classify_cochannel.py, false-positive via matcher.py) and the sweep
// orchestration live in the Python driver (sweep_driver.py) — this binary only decodes.
//
// See dev-tasks/2026-07-22-d001-runtime-param-sweep-work-order.md and
// qa/rr-study/results/2026-07-22-<sha>-d001-param-sweep/report.md.
//
// Determinism (spec §3.2): DecodeAll is pure w.r.t. (PCM, current param values) — no live
// audio, no timing. SetDecodeParams writes module-level native globals read only at the start
// of each ft8_decode_all call (Ft8Decoder.cs:90-96). This harness therefore loads each WAV
// once and decodes it under every grid point in the same thread, calling SetDecodeParams
// before each decode; results are identical to the "SetDecodeParams once per point, then
// iterate all WAVs" ordering (work-order step 3) but each WAV is read from disk exactly once.
// Decodes are never parallelised across grid points (that would race the shared globals).

using System.Globalization;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Ft8;
using OpenWSFZ.Ft8.Tests; // WavReader (linked via <Compile Include> in the .csproj)

const int ExpectedSamples = 180_000; // 15 s × 12 000 Hz — Ft8Decoder's hard contract.

var opts = CliOptions.Parse(args);
if (opts is null) return 2;

// ── Build the grid: 5 × 3 × 3 = 45 points. Baseline (10, 0.10, 60) is an ORDINARY point
//    in this enumeration, never special-cased (acceptance criterion 3). ─────────────────
int[]   kValues     = { 5, 7, 10, 15, 20 };
float[] corrValues  = { 0.10f, 0.15f, 0.25f };
int[]   nhardValues = { 40, 60, 80 };

var grid = new List<GridPoint>();
foreach (var k in kValues)
    foreach (var c in corrValues)
        foreach (var n in nhardValues)
            grid.Add(new GridPoint(k, c, n));

// Optional restriction (validate arm decodes only baseline + the chosen candidate).
if (opts.Points is { Count: > 0 })
    grid = grid.Where(p => opts.Points.Contains(p.DirName)).ToList();

if (grid.Count == 0)
{
    Console.Error.WriteLine("No grid points selected — check --points.");
    return 2;
}

// ── Gather the WAV list (sorted by filename so tune/validate temporal splits upstream are
//    reproducible and the log order is stable). ─────────────────────────────────────────
var allWavPaths = Directory.EnumerateFiles(opts.WavDir, "*.wav")
    .OrderBy(p => Path.GetFileName(p), StringComparer.Ordinal)
    .ToList();

// Temporal tune/validate split (work-order step 7): the ordinal filename sort is
// chronological for zero-padded YYMMDD_HHMMSS names, so [start,end) selects a
// contiguous time span. Applied to the full sorted list before sharding.
int start = opts.IndexStart ?? 0;
int end = opts.IndexEnd ?? allWavPaths.Count;
start = Math.Clamp(start, 0, allWavPaths.Count);
end = Math.Clamp(end, start, allWavPaths.Count);
var wavPaths = allWavPaths.GetRange(start, end - start);

// Process-shard (work-order step 3 forbids parallel decode *within one process* — this
// runs disjoint WAV subsets in SEPARATE processes, each with its own native globals, so
// no shared-global race exists; per-point outputs are concatenated afterwards).
if (opts.ShardCount is int sc && sc > 1)
{
    int si = opts.ShardIndex ?? 0;
    wavPaths = wavPaths.Where((_, idx) => idx % sc == si).ToList();
}

if (opts.Limit is int lim && lim < wavPaths.Count)
    wavPaths = wavPaths.Take(lim).ToList();

// Timestamp source: recall arm derives the slot timestamp from the WAV filename stem
// (YYMMDD_HHMMSS.wav ↔ the raw ts field in ALL.TXT, exact string join); FP arm reads a
// manifest mapping each dumped WAV basename → a canonical per-slot cycle_utc.
Dictionary<string, DateTime>? manifest = opts.ManifestPath is null ? null : LoadManifest(opts.ManifestPath);

Console.WriteLine($"D001ParamSweep decode: {wavPaths.Count} WAV(s) × {grid.Count} grid point(s)");
Console.WriteLine($"  wav-dir : {opts.WavDir}");
Console.WriteLine($"  out-dir : {opts.OutDir}");
Console.WriteLine($"  ts-mode : {(manifest is null ? "filename" : "manifest")}");
Console.WriteLine($"  output  : <out-dir>/<point>/{opts.AllTxtName}");

// ── Open one writer per grid point. ──────────────────────────────────────────────────
var writers = new Dictionary<string, StreamWriter>();
// D-001 C.1 (2026-07-26) deviation from "harness unmodified" — see dev-tasks/
// 2026-07-26-d001-candidate-cap-sweep.md §3.5. With logger: null (the harness's
// original, unconditional behaviour), Ft8Decoder.cs:420's failCands/meanAbsLLR/
// prenormVar Debug line is never emitted anywhere, so the candidate-cap sweep could
// not report those fields as required. --debug-log (opt-in, default off, so every
// existing caller of this harness is byte-for-byte unaffected) now opens one
// <out-dir>/<point>/decode.log per grid point and routes a minimal ILogger<Ft8Decoder>
// there, formatted to match ldpc_stats.py's RE_LLR line shape exactly (see
// SwitchablePointLogger below) so the existing Python parsing methodology applies
// unchanged to an offline run's log instead of a live daemon's.
var debugLogWriters = new Dictionary<string, StreamWriter>();
foreach (var p in grid)
{
    var dir = Path.Combine(opts.OutDir, p.DirName);
    Directory.CreateDirectory(dir);
    var sw = new StreamWriter(Path.Combine(dir, opts.AllTxtName), append: false, System.Text.Encoding.ASCII)
    {
        NewLine = "\r\n",
        AutoFlush = false,
    };
    writers[p.DirName] = sw;

    if (opts.DebugLog)
    {
        var dlw = new StreamWriter(Path.Combine(dir, "decode.log"), append: false)
        {
            AutoFlush = true, // low volume (one line per pass per WAV) — flush cost is negligible
        };
        debugLogWriters[p.DirName] = dlw;
    }
}

// Single mutable-target logger instance, shared by every Ft8Decoder this process
// constructs (shared or fresh-per-wav) — its Target is repointed to the current grid
// point's writer immediately before each decode, so one decoder instance processing
// multiple grid points in sequence (the normal --points-restricted-to-one case, but
// also the general multi-point case) still routes each pass's debug line to the
// correct point's decode.log. Concrete only when --debug-log is set; otherwise decoders
// get logger: null exactly as before (zero behavioural change for existing callers).
var switchableLogger = opts.DebugLog ? new SwitchablePointLogger<Ft8Decoder>() : null;

// grammarStore null → BuiltInDefault (shipped D-009 calibration). Default: one shared
// instance for the whole run (original D-001 param-sweep behaviour, unchanged for
// existing callers of this harness). --fresh-decoder-per-wav (added for the
// cycleframer-alignment-replay study, SPEC.md section 7.4(b)) instead constructs a new
// decoder per WAV, so Ft8Decoder's process-lifetime cumulative state (hash-table
// callsign resolution, hashTableRejectCount) cannot leak across windows decoded in the
// same run — confirmed by that study's cross-input determinism control to otherwise
// make message TEXT order-dependent (e.g. "<...> DG0JW" vs "<PD00DOG> DG0JW" for
// identical audio) even though the underlying signal is found either way.
Ft8Decoder? sharedDecoder = opts.FreshDecoderPerWav
    ? null
    : new Ft8Decoder(new SystemClock(), logger: switchableLogger);

int decoded = 0, skipped = 0;
long totalDecodeMs = 0;
var swall = System.Diagnostics.Stopwatch.StartNew();

for (int wi = 0; wi < wavPaths.Count; wi++)
{
    var path = wavPaths[wi];
    var stem = Path.GetFileNameWithoutExtension(path);
    var decoder = sharedDecoder ?? new Ft8Decoder(new SystemClock(), logger: switchableLogger);

    // Resolve the slot timestamp.
    DateTime cycleStart;
    if (manifest is not null)
    {
        if (!manifest.TryGetValue(Path.GetFileName(path), out cycleStart))
        {
            Console.Error.WriteLine($"[SKIP] {stem}: no manifest entry");
            skipped++;
            continue;
        }
    }
    else if (!DateTime.TryParseExact(stem, "yyMMdd_HHmmss", CultureInfo.InvariantCulture,
                 DateTimeStyles.AssumeUniversal | DateTimeStyles.AdjustToUniversal, out cycleStart))
    {
        Console.Error.WriteLine($"[SKIP] {stem}: filename is not a YYMMDD_HHMMSS timestamp");
        skipped++;
        continue;
    }

    // Load + validate the WAV once.
    float[] pcm;
    try
    {
        pcm = WavReader.Read(path);
    }
    catch (Exception ex) when (ex is InvalidDataException or IOException)
    {
        Console.Error.WriteLine($"[SKIP] {stem}: {ex.Message}");
        skipped++;
        continue;
    }
    if (pcm.Length != ExpectedSamples)
    {
        Console.Error.WriteLine($"[SKIP] {stem}: {pcm.Length} samples (expected {ExpectedSamples})");
        skipped++;
        continue;
    }

    string tsField = cycleStart.ToString("yyMMdd_HHmmss", CultureInfo.InvariantCulture);

    // Decode under every grid point (SetDecodeParams before each — see determinism note above).
    foreach (var p in grid)
    {
        decoder.SetDecodeParams(p.K, p.Corr, p.NHard);
        if (switchableLogger is not null)
            switchableLogger.Target = debugLogWriters.TryGetValue(p.DirName, out var dlw)
                ? new StreamWriterLineLogger(dlw)
                : null;
        var t0 = System.Diagnostics.Stopwatch.GetTimestamp();
        IReadOnlyList<DecodeResult> results;
        try
        {
            results = decoder.DecodeAsync(pcm, cycleStart).GetAwaiter().GetResult();
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[ERR ] {stem} @ {p.DirName}: {ex.GetType().Name}: {ex.Message}");
            continue;
        }
        totalDecodeMs += (long)System.Diagnostics.Stopwatch.GetElapsedTime(t0).TotalMilliseconds;

        var w = writers[p.DirName];
        foreach (var r in results)
            w.WriteLine(FormatAllTxtLine(tsField, opts.DialMhz, r));
    }

    decoded++;
    if (decoded % opts.ProgressEvery == 0 || wi == wavPaths.Count - 1)
    {
        double rate = decoded / Math.Max(0.001, swall.Elapsed.TotalSeconds);
        Console.WriteLine($"  {decoded}/{wavPaths.Count} wavs  ({rate:F1} wav/s, " +
                          $"{totalDecodeMs / Math.Max(1, decoded * grid.Count)} ms/decode avg)");
    }
}

foreach (var w in writers.Values) { w.Flush(); w.Dispose(); }
foreach (var w in debugLogWriters.Values) { w.Flush(); w.Dispose(); }

// tasks.md 11.6(b) / SPEC.md section 7.4(b-ii) (cycleframer-alignment-replay): record
// Ft8Decoder.GetHashTableRejectCount() -- process-lifetime cumulative, so for one CLI
// invocation this is the total for THIS ARM's entire decode set (whether or not
// --fresh-decoder-per-wav is set: the count lives in native static memory, shared by
// every managed Ft8Decoder instance in this process, so any instance reads the same
// final value). Written per grid point so Phase 1b can compare reject counts across
// arms as a confound signature -- a hash-driven reject is a genuinely missing decode
// that normalize_hash_tokens() neither fixes nor reveals.
{
    int finalRejectCount = (sharedDecoder ?? new Ft8Decoder(new SystemClock(), logger: null))
        .GetHashTableRejectCount();
    foreach (var p in grid)
    {
        var dir = Path.Combine(opts.OutDir, p.DirName);
        File.WriteAllText(Path.Combine(dir, "hash_reject_count.txt"),
            $"hashTableRejectCount={finalRejectCount}\n");
    }
    Console.WriteLine($"hashTableRejectCount (process-lifetime cumulative) = {finalRejectCount}");
}

swall.Stop();
Console.WriteLine($"Done. decoded={decoded} skipped={skipped} points={grid.Count} " +
                  $"total-decodes={(long)decoded * grid.Count} wall={swall.Elapsed.TotalMinutes:F1} min");
return 0;

// ── Helpers ──────────────────────────────────────────────────────────────────────────

// Byte-for-byte AllTxtWriter.cs:99 —
//   {timestamp}     {dialMhz:F3} Rx FT8 {snr,6} {dt,4:F1} {freq,4} {message}
// (five spaces after the timestamp; classify_cochannel.py / common.py column parsers depend
// on this exact layout).
static string FormatAllTxtLine(string ts, double dialMhz, DecodeResult r)
    => string.Create(CultureInfo.InvariantCulture,
        $"{ts}     {dialMhz:F3} Rx FT8 {r.Snr,6} {r.Dt,4:F1} {r.FreqHz,4} {r.Message}");

static Dictionary<string, DateTime> LoadManifest(string path)
{
    var map = new Dictionary<string, DateTime>(StringComparer.Ordinal);
    using var reader = new StreamReader(path);
    string? header = reader.ReadLine(); // wav,cycle_utc
    int wavCol = 0, tsCol = 1;
    if (header is not null)
    {
        var cols = header.Split(',');
        for (int i = 0; i < cols.Length; i++)
        {
            var c = cols[i].Trim().ToLowerInvariant();
            if (c == "wav") wavCol = i;
            else if (c is "cycle_utc" or "cycle") tsCol = i;
        }
    }
    string? line;
    while ((line = reader.ReadLine()) is not null)
    {
        if (line.Length == 0) continue;
        var f = line.Split(',');
        if (f.Length <= Math.Max(wavCol, tsCol)) continue;
        var wav = f[wavCol].Trim();
        var ts = DateTime.Parse(f[tsCol].Trim(), CultureInfo.InvariantCulture,
            DateTimeStyles.AssumeUniversal | DateTimeStyles.AdjustToUniversal);
        map[wav] = ts;
    }
    return map;
}

readonly record struct GridPoint(int K, float Corr, int NHard)
{
    // Filesystem-safe, uniquely parseable per-point directory name, e.g. "k10_c0.10_n60".
    public string DirName => string.Create(CultureInfo.InvariantCulture, $"k{K}_c{Corr:0.00}_n{NHard}");
}

sealed class CliOptions
{
    public required string WavDir { get; init; }
    public required string OutDir { get; init; }
    public required string AllTxtName { get; init; }
    public string? ManifestPath { get; init; }
    public double DialMhz { get; init; } = 14.074;
    public int? Limit { get; init; }
    public int ProgressEvery { get; init; } = 100;
    public HashSet<string>? Points { get; init; }
    public int? IndexStart { get; init; }
    public int? IndexEnd { get; init; }
    public int? ShardIndex { get; init; }
    public int? ShardCount { get; init; }
    public bool FreshDecoderPerWav { get; init; }
    public bool DebugLog { get; init; }

    public static CliOptions? Parse(string[] args)
    {
        string? wavDir = null, outDir = null, allTxtName = null, manifest = null;
        double dial = 14.074;
        int? limit = null;
        int progress = 100;
        HashSet<string>? points = null;
        int? indexStart = null, indexEnd = null, shardIndex = null, shardCount = null;
        bool freshDecoderPerWav = false;
        bool debugLog = false;

        for (int i = 0; i < args.Length; i++)
        {
            string a = args[i];
            string Next() => ++i < args.Length ? args[i] : throw new ArgumentException($"missing value for {a}");
            switch (a)
            {
                case "--wav-dir": wavDir = Next(); break;
                case "--out-dir": outDir = Next(); break;
                case "--all-txt-name": allTxtName = Next(); break;
                case "--manifest": manifest = Next(); break;
                case "--dial-mhz": dial = double.Parse(Next(), CultureInfo.InvariantCulture); break;
                case "--limit": limit = int.Parse(Next(), CultureInfo.InvariantCulture); break;
                case "--progress-every": progress = int.Parse(Next(), CultureInfo.InvariantCulture); break;
                case "--points":
                    points = new HashSet<string>(Next().Split(',', StringSplitOptions.RemoveEmptyEntries
                                                                     | StringSplitOptions.TrimEntries));
                    break;
                case "--index-start": indexStart = int.Parse(Next(), CultureInfo.InvariantCulture); break;
                case "--index-end": indexEnd = int.Parse(Next(), CultureInfo.InvariantCulture); break;
                case "--shard-index": shardIndex = int.Parse(Next(), CultureInfo.InvariantCulture); break;
                case "--shard-count": shardCount = int.Parse(Next(), CultureInfo.InvariantCulture); break;
                case "--fresh-decoder-per-wav": freshDecoderPerWav = true; break;
                case "--debug-log": debugLog = true; break;
                default:
                    Console.Error.WriteLine($"Unknown argument: {a}");
                    return Usage();
            }
        }

        if (wavDir is null || outDir is null || allTxtName is null)
        {
            Console.Error.WriteLine("Required: --wav-dir <dir> --out-dir <dir> --all-txt-name <name>");
            return Usage();
        }
        if (!Directory.Exists(wavDir))
        {
            Console.Error.WriteLine($"--wav-dir does not exist: {wavDir}");
            return null;
        }

        return new CliOptions
        {
            WavDir = wavDir, OutDir = outDir, AllTxtName = allTxtName,
            ManifestPath = manifest, DialMhz = dial, Limit = limit,
            ProgressEvery = progress, Points = points,
            IndexStart = indexStart, IndexEnd = indexEnd,
            ShardIndex = shardIndex, ShardCount = shardCount,
            FreshDecoderPerWav = freshDecoderPerWav,
            DebugLog = debugLog,
        };
    }

    static CliOptions? Usage()
    {
        Console.Error.WriteLine(
            "Usage: D001ParamSweep --wav-dir <dir> --out-dir <dir> --all-txt-name <name>\n" +
            "                      [--manifest <csv>] [--dial-mhz <d>] [--limit <n>]\n" +
            "                      [--points k10_c0.10_n60,...] [--progress-every <n>]\n" +
            "                      [--fresh-decoder-per-wav] [--debug-log]");
        return null;
    }
}

// ── D-001 C.1 debug-log support (--debug-log, §3.5 of the candidate-cap-sweep dev-task) ──

/// <summary>
/// Retargetable <c>ILogger&lt;T&gt;</c> — every <see cref="Ft8Decoder"/> instance this process
/// constructs shares ONE instance of this wrapper (assigned once, at startup); <see cref="Target"/>
/// is repointed to the current grid point's <see cref="StreamWriterLineLogger"/> immediately
/// before each decode call. This lets a single long-lived <c>sharedDecoder</c> (the harness's
/// default mode) route each grid point's debug lines to that point's own <c>decode.log</c>, even
/// though Ft8Decoder's constructor only accepts a logger once. When null (the default -- no
/// point's decode.log open, e.g. --fresh-decoder-per-wav churns decoders faster than points),
/// logging is a no-op, matching the harness's original logger: null behaviour exactly.
/// </summary>
sealed class SwitchablePointLogger<T> : ILogger<T>
{
    public ILogger? Target { get; set; }

    public IDisposable? BeginScope<TState>(TState state) where TState : notnull => Target?.BeginScope(state);
    public bool IsEnabled(LogLevel logLevel) => Target?.IsEnabled(logLevel) ?? false;

    public void Log<TState>(LogLevel logLevel, EventId eventId, TState state, Exception? exception,
        Func<TState, Exception?, string> formatter)
        => Target?.Log(logLevel, eventId, state, exception, formatter);
}

/// <summary>
/// Minimal file-backed <c>ILogger</c> that formats lines to match
/// <c>qa/cycleframer-alignment-replay/ldpc_stats.py</c>'s <c>RE_LLR</c>/<c>RE_PASS</c>/<c>RE_DEC</c>
/// regexes byte-for-byte: <c>{yyyy-MM-dd HH:mm:ss.fff} +00:00 [LVL] {message}</c> — the same shape
/// Serilog's default <c>{Timestamp:yyyy-MM-dd HH:mm:ss.fff zzz} [{Level:u3}] {Message}</c> template
/// produces in the daemon's own log files (<see cref="OpenWSFZ.Daemon.Logging.LoggingPipeline"/>),
/// so the existing Python parsing methodology applies unchanged to this offline harness's log.
/// </summary>
sealed class StreamWriterLineLogger(StreamWriter writer) : ILogger
{
    public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;
    public bool IsEnabled(LogLevel logLevel) => true;

    public void Log<TState>(LogLevel logLevel, EventId eventId, TState state, Exception? exception,
        Func<TState, Exception?, string> formatter)
    {
        string lvl = logLevel switch
        {
            LogLevel.Trace       => "VRB",
            LogLevel.Debug       => "DBG",
            LogLevel.Information => "INF",
            LogLevel.Warning     => "WRN",
            LogLevel.Error       => "ERR",
            LogLevel.Critical    => "FTL",
            _                    => "INF",
        };
        string ts = DateTime.UtcNow.ToString("yyyy-MM-dd HH:mm:ss.fff", CultureInfo.InvariantCulture);
        writer.WriteLine($"{ts} +00:00 [{lvl}] {formatter(state, exception)}");
    }
}
