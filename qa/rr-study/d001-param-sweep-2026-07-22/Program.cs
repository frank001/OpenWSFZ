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
}

var decoder = new Ft8Decoder(new SystemClock(), logger: null); // grammarStore null → BuiltInDefault (shipped D-009 calibration)

int decoded = 0, skipped = 0;
long totalDecodeMs = 0;
var swall = System.Diagnostics.Stopwatch.StartNew();

for (int wi = 0; wi < wavPaths.Count; wi++)
{
    var path = wavPaths[wi];
    var stem = Path.GetFileNameWithoutExtension(path);

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

    public static CliOptions? Parse(string[] args)
    {
        string? wavDir = null, outDir = null, allTxtName = null, manifest = null;
        double dial = 14.074;
        int? limit = null;
        int progress = 100;
        HashSet<string>? points = null;
        int? indexStart = null, indexEnd = null, shardIndex = null, shardCount = null;

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
        };
    }

    static CliOptions? Usage()
    {
        Console.Error.WriteLine(
            "Usage: D001ParamSweep --wav-dir <dir> --out-dir <dir> --all-txt-name <name>\n" +
            "                      [--manifest <csv>] [--dial-mhz <d>] [--limit <n>]\n" +
            "                      [--points k10_c0.10_n60,...] [--progress-every <n>]");
        return null;
    }
}
