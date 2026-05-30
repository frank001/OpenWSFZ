/*
 * SnrAnalyser — QA Task 9.7 — R5 SNR Calibration Re-Check
 *
 * Runs the R5 decoder against all UAT-01 WAV files and compares the
 * reported SNR values against WSJT-X ALL.TXT reference values.
 *
 * Pass criteria (r5-snr-calibration.md):
 *   Overall  |mean| ≤ 5 dB
 *   ≤ −20 dB bucket         ±6 dB
 *   −20 to −12 dB bucket    ±5 dB
 *   −12 to −4 dB bucket     ±5 dB
 *   −4 to +5 dB bucket      ±7 dB
 *   > +5 dB bucket          ±10 dB (saturation tolerance)
 *
 * Usage:
 *   dotnet run --project tools/SnrAnalyser [<saveDir> [<wsjtxAllTxt>]]
 */

using System.Text;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Ft8;

// ── Configuration ─────────────────────────────────────────────────────────────

string repoRoot  = FindRepoRoot();
string saveDir   = args.Length > 0 ? args[0]
                 : Path.Combine(repoRoot, "p12-ft8lib-port_UAT-01_items", "save");
string wsjtxPath = args.Length > 1 ? args[1]
                 : Path.Combine(repoRoot, "p12-ft8lib-port_UAT-01_items", "WSJT-X ALL.TXT");

Console.WriteLine("╔════════════════════════════════════════════╗");
Console.WriteLine("║  SnrAnalyser — QA Task 9.7 / R5 Re-check  ║");
Console.WriteLine("╚════════════════════════════════════════════╝");
Console.WriteLine();
Console.WriteLine($"Save dir:        {saveDir}");
Console.WriteLine($"WSJT-X ALL.TXT:  {wsjtxPath}");
Console.WriteLine();

if (!Directory.Exists(saveDir))
{
    Console.Error.WriteLine($"ERROR: save directory not found: {saveDir}");
    return 1;
}
if (!File.Exists(wsjtxPath))
{
    Console.Error.WriteLine($"ERROR: WSJT-X ALL.TXT not found: {wsjtxPath}");
    return 1;
}

// ── Parse WSJT-X ALL.TXT ──────────────────────────────────────────────────────

var wsjtxRef = ParseWsjtxAllTxt(wsjtxPath);
int totalRef = wsjtxRef.Values.SelectMany(v => v).Count();
Console.WriteLine($"WSJT-X decodes:  {totalRef} across {wsjtxRef.Count} timestamps");

// ── Enumerate WAV files ───────────────────────────────────────────────────────

var wavFiles = Directory.GetFiles(saveDir, "*.wav")
    .Select(f => (path: f, ts: Path.GetFileNameWithoutExtension(f)))
    .Where(x => TryParseTimestamp(x.ts, out _))
    .OrderBy(x => x.ts)
    .ToList();

Console.WriteLine($"WAV files:       {wavFiles.Count}");
Console.WriteLine();
Console.WriteLine("Decoding WAV files...");

// ── Decode each WAV and collect matched pairs ─────────────────────────────────

var pairs        = new List<(int WsjtxSnr, int OurSnr, string Msg, string Ts, int FreqHz)>();
int processed    = 0;
int readErrors   = 0;
int decodeErrors = 0;
int ourTotal     = 0;
int noRefMatch   = 0;

foreach (var (wavPath, ts) in wavFiles)
{
    if (!TryParseTimestamp(ts, out DateTime cycleStart))
    {
        Console.Error.WriteLine($"  [SKIP] Bad timestamp: {ts}");
        continue;
    }

    // Read WAV (16-bit PCM 12 kHz mono)
    float[] pcm;
    try   { pcm = ReadWav16(wavPath); }
    catch (Exception ex)
    {
        Console.Error.WriteLine($"  [ERR]  WAV read error {ts}: {ex.Message}");
        readErrors++;
        continue;
    }

    // Pad or trim to the exact 180 000 samples the decoder requires.
    if (pcm.Length != 180_000)
    {
        var buf = new float[180_000];
        Array.Copy(pcm, buf, Math.Min(pcm.Length, 180_000));
        pcm = buf;
    }

    // Decode with the R5 DLL
    IReadOnlyList<DecodeResult> results;
    try
    {
        var decoder = new Ft8Decoder(new FixedClock(cycleStart));
        results = await decoder.DecodeAsync(pcm, cycleStart);
    }
    catch (Exception ex)
    {
        Console.Error.WriteLine($"  [ERR]  Decode error {ts}: {ex.Message}");
        decodeErrors++;
        continue;
    }

    ourTotal += results.Count;

    // Match against WSJT-X reference for this timestamp
    if (!wsjtxRef.TryGetValue(ts, out var refs))
    {
        if (results.Count > 0) noRefMatch += results.Count;
        processed++;
        continue;
    }

    foreach (var our in results)
    {
        string ourNorm = NormaliseHash(our.Message);

        WsjtxEntry? best         = null;
        int         bestFreqDiff = int.MaxValue;

        foreach (var w in refs)
        {
            if (!string.Equals(NormaliseHash(w.Message), ourNorm, StringComparison.Ordinal))
                continue;

            int diff = Math.Abs(w.FreqHz - our.FreqHz);
            if (diff <= 20 && diff < bestFreqDiff)
            {
                best        = w;
                bestFreqDiff = diff;
            }
        }

        if (best is not null)
            pairs.Add((best.Snr, our.Snr, our.Message, ts, our.FreqHz));
    }

    processed++;
    if (processed % 50 == 0)
        Console.WriteLine($"  {processed}/{wavFiles.Count} WAVs,  {pairs.Count} matched pairs");
}

Console.WriteLine($"  Done. {processed} WAVs,  {readErrors} read errors,  {decodeErrors} decode errors");
Console.WriteLine();

if (pairs.Count == 0)
{
    Console.Error.WriteLine("ERROR: No matched pairs. Verify save directory and WSJT-X ALL.TXT path.");
    return 1;
}

// ── Compute overall statistics ────────────────────────────────────────────────

Console.WriteLine("═══════════════════════════════════════════════════════════");
Console.WriteLine("  SNR DELTA ANALYSIS  (R5 noise-floor calibration)");
Console.WriteLine("═══════════════════════════════════════════════════════════");
Console.WriteLine();
Console.WriteLine($"  Matched pairs analysed:  {pairs.Count}");
Console.WriteLine($"  Our total decodes:        {ourTotal}");
Console.WriteLine($"  Decodes with no ref:      {noRefMatch}");
Console.WriteLine();

var allDeltas  = pairs.Select(p => p.OurSnr - p.WsjtxSnr).OrderBy(d => d).ToList();
double ovMean  = allDeltas.Average();
double p25all  = Percentile(allDeltas, 25);
double p75all  = Percentile(allDeltas, 75);
int    minDelta= allDeltas[0];
int    maxDelta= allDeltas[^1];

Console.WriteLine($"  Overall mean (ours − WSJT-X):  {ovMean:+0.0;-0.0} dB   (threshold: |mean| ≤ 5 dB)");
Console.WriteLine($"  P25 / P75:                      {p25all:+0.0;-0.0} / {p75all:+0.0;-0.0} dB");
Console.WriteLine($"  Min / Max:                      {minDelta:+0;-0} / {maxDelta:+0;-0} dB");
Console.WriteLine();

bool overallPass = Math.Abs(ovMean) <= 5.0;
Console.WriteLine($"  Overall:  {Verdict(overallPass)}");
Console.WriteLine();

// ── Per-bucket detail (9 buckets matching UAT-01 uat-01-findings.md) ──────────

Console.WriteLine("── Detailed 9-bucket breakdown ─────────────────────────────");
Console.WriteLine();
Console.WriteLine($"  {"WSJT-X SNR bucket",-18}  {"N",5}  {"Mean Δ",8}  {"P25",5}  {"P75",5}");
Console.WriteLine($"  {new string('─', 18)}  {"─────",5}  {"────────",8}  {"─────",5}  {"─────",5}");

(string label, int lo, int hi)[] detailBuckets =
[
    ("≤ −20 dB",       int.MinValue, -20),
    ("−20 to −16 dB",        -20,   -16),
    ("−16 to −12 dB",        -16,   -12),
    ("−12 to −8 dB",         -12,    -8),
    ("−8 to −4 dB",           -8,    -4),
    ("−4 to 0 dB",            -4,     0),
    ("0 to +5 dB",             0,     5),
    ("+5 to +15 dB",           5,    15),
    ("> +15 dB",              15, int.MaxValue),
];

foreach (var (label, lo, hi) in detailBuckets)
{
    var bd = pairs
        .Where(p => p.WsjtxSnr >= lo && p.WsjtxSnr < hi)
        .Select(p => p.OurSnr - p.WsjtxSnr)
        .OrderBy(d => d)
        .ToList();

    if (bd.Count == 0) continue;

    double mean = bd.Average();
    double p25  = Percentile(bd, 25);
    double p75  = Percentile(bd, 75);

    Console.WriteLine($"  {label,-18}  {bd.Count,5}  {mean,8:+0.0;-0.0}  {p25,5:+0;-0}  {p75,5:+0;-0}");
}

Console.WriteLine();

// ── Acceptance criteria (5 consolidated buckets from r5-snr-calibration.md) ──

Console.WriteLine("── Acceptance criteria (r5-snr-calibration.md) ─────────────");
Console.WriteLine();
Console.WriteLine($"  {"WSJT-X SNR bucket",-22}  {"N",5}  {"Mean Δ",8}  {"Tolerance",10}  Verdict");
Console.WriteLine($"  {new string('─', 22)}  {"─────",5}  {"────────",8}  {"──────────",10}  ───────");

(string label, int lo, int hi, double tol)[] criterionBuckets =
[
    ("≤ −20 dB",             int.MinValue, -20,  6.0),
    ("−20 to −12 dB",              -20,   -12,   5.0),
    ("−12 to −4 dB",               -12,    -4,   5.0),
    ("−4 to +5 dB",                 -4,     5,   7.0),
    ("> +5 dB",                      5, int.MaxValue, 10.0),
];

bool allCriteriaPass = true;
foreach (var (label, lo, hi, tol) in criterionBuckets)
{
    var bd = pairs
        .Where(p => p.WsjtxSnr >= lo && p.WsjtxSnr < hi)
        .Select(p => p.OurSnr - p.WsjtxSnr)
        .OrderBy(d => d)
        .ToList();

    if (bd.Count == 0)
    {
        Console.WriteLine($"  {label,-22}  {"(no data)",16}");
        continue;
    }

    double mean = bd.Average();
    bool   pass = Math.Abs(mean) <= tol;
    if (!pass) allCriteriaPass = false;

    Console.WriteLine($"  {label,-22}  {bd.Count,5}  {mean,8:+0.0;-0.0}  ±{tol,4:0.0} dB     {Verdict(pass)}");
}

Console.WriteLine();

// ── G6 gate reminder ──────────────────────────────────────────────────────────

Console.WriteLine("── G6 gate reminder ─────────────────────────────────────────");
Console.WriteLine("  Run separately:");
Console.WriteLine("  dotnet test tests/OpenWSFZ.Ft8.Tests -c Release --filter RealSignal");
Console.WriteLine();

// ── Final verdict ─────────────────────────────────────────────────────────────

bool finalPass = overallPass && allCriteriaPass;
Console.WriteLine("═══════════════════════════════════════════════════════════");
Console.WriteLine($"  FINAL VERDICT:  {(finalPass
    ? "✅  PASS — R5 SNR calibration meets all acceptance criteria"
    : "❌  FAIL — R5 SNR calibration does not meet acceptance criteria")}");
Console.WriteLine("═══════════════════════════════════════════════════════════");
Console.WriteLine();

return finalPass ? 0 : 1;

// ═════════════════════════════════════════════════════════════════════════════
// Local functions  (must precede type declarations in top-level programs)
// ═════════════════════════════════════════════════════════════════════════════

static string FindRepoRoot()
{
    var dir = new DirectoryInfo(AppContext.BaseDirectory);
    while (dir != null)
    {
        if (Directory.Exists(Path.Combine(dir.FullName, ".git"))) return dir.FullName;
        dir = dir.Parent;
    }
    throw new InvalidOperationException("Repository root (.git) not found.");
}

static bool TryParseTimestamp(string ts, out DateTime dt)
{
    // Format: YYMMDD_HHMMSS  (e.g. "260530_154500")
    dt = default;
    if (ts.Length != 13 || ts[6] != '_') return false;

    if (!int.TryParse(ts.AsSpan(0, 2),  out int yy) ||
        !int.TryParse(ts.AsSpan(2, 2),  out int mo) ||
        !int.TryParse(ts.AsSpan(4, 2),  out int dd) ||
        !int.TryParse(ts.AsSpan(7, 2),  out int hh) ||
        !int.TryParse(ts.AsSpan(9, 2),  out int mi) ||
        !int.TryParse(ts.AsSpan(11, 2), out int ss))
        return false;

    try
    {
        dt = new DateTime(2000 + yy, mo, dd, hh, mi, ss, DateTimeKind.Utc);
        return true;
    }
    catch { return false; }
}

static float[] ReadWav16(string path)
{
    using var fs = File.OpenRead(path);
    using var r  = new BinaryReader(fs);

    static void Expect32(BinaryReader reader, int expected, string what)
    {
        int got = reader.ReadInt32();
        if (got != expected)
            throw new InvalidDataException(
                $"Expected {what} (0x{expected:X8}) but got 0x{got:X8}.");
    }

    Expect32(r, 0x46464952, "'RIFF'");  // 'RIFF'
    r.ReadInt32();                        // file size
    Expect32(r, 0x45564157, "'WAVE'");  // 'WAVE'

    short  channels = 0, bitsPerSample = 0, audioFormat = 0;
    int    sampleRate = 0;
    byte[]? audioData = null;

    while (fs.Position + 8 <= fs.Length)
    {
        int chunkId   = r.ReadInt32();
        int chunkSize = r.ReadInt32();

        if (chunkId == 0x20746d66)        // 'fmt '
        {
            audioFormat   = r.ReadInt16();
            channels      = r.ReadInt16();
            sampleRate    = r.ReadInt32();
            r.ReadInt32();                 // byte rate
            r.ReadInt16();                 // block align
            bitsPerSample = r.ReadInt16();
            int extra = chunkSize - 16;
            if (extra > 0) r.ReadBytes(extra);
        }
        else if (chunkId == 0x61746164)   // 'data'
        {
            audioData = r.ReadBytes(chunkSize);
        }
        else
        {
            r.ReadBytes(chunkSize);
        }

        if (chunkSize % 2 != 0 && fs.Position < fs.Length)
            r.ReadByte();
    }

    if (audioFormat   != 1     ) throw new InvalidDataException($"Not linear PCM (fmt={audioFormat})");
    if (channels      != 1     ) throw new InvalidDataException($"Not mono (ch={channels})");
    if (sampleRate    != 12_000) throw new InvalidDataException($"Not 12 kHz (sr={sampleRate})");
    if (bitsPerSample != 16    ) throw new InvalidDataException($"Not 16-bit (bps={bitsPerSample})");
    if (audioData is null || audioData.Length == 0)
        throw new InvalidDataException("WAV data chunk missing or empty.");

    int    count = audioData.Length / 2;
    float[] pcm  = new float[count];
    for (int i = 0; i < count; i++)
    {
        short s = (short)(audioData[i * 2] | (audioData[i * 2 + 1] << 8));
        pcm[i]  = s / 32768.0f;
    }
    return pcm;
}

static Dictionary<string, List<WsjtxEntry>> ParseWsjtxAllTxt(string path)
{
    var result = new Dictionary<string, List<WsjtxEntry>>(StringComparer.Ordinal);

    foreach (string line in File.ReadLines(path))
    {
        string trimmed = line.Trim();
        if (trimmed.Length == 0 || trimmed[0] == '#') continue;

        var parts = trimmed.Split(
            new[] { ' ', '\t' },
            StringSplitOptions.RemoveEmptyEntries);

        // timestamp freq_mhz Rx FT8 snr dt audioHz message…
        if (parts.Length < 8) continue;

        string ts = parts[0];
        if (!TryParseTimestamp(ts, out _)) continue;
        if (parts[3] != "FT8") continue;

        if (!int.TryParse(parts[4], out int snr))    continue;
        if (!int.TryParse(parts[6], out int freqHz)) continue;

        string message = string.Join(" ", parts, 7, parts.Length - 7);

        if (!result.TryGetValue(ts, out var list))
        {
            list = [];
            result[ts] = list;
        }
        list.Add(new WsjtxEntry(ts, freqHz, snr, message));
    }

    return result;
}

static string NormaliseHash(string msg)
{
    // Replace <…> callsign-hash tokens with <HASH> sentinel so that our
    // "<...>" can match WSJT-X's expanded "<II9MESC>" (and vice versa).
    if (!msg.Contains('<')) return msg;

    var sb        = new StringBuilder(msg.Length);
    bool inBracket = false;

    foreach (char c in msg)
    {
        if (c == '<')
        {
            inBracket = true;
            sb.Append("<HASH>");
        }
        else if (c == '>')
        {
            inBracket = false;
        }
        else if (!inBracket)
        {
            sb.Append(c);
        }
    }
    return sb.ToString();
}

static double Percentile(List<int> sorted, int p)
{
    if (sorted.Count == 0) return 0.0;
    double rank = p / 100.0 * (sorted.Count - 1);
    int    lo   = (int)rank;
    int    hi   = Math.Min(lo + 1, sorted.Count - 1);
    return sorted[lo] + (rank - lo) * (sorted[hi] - sorted[lo]);
}

static string Verdict(bool pass) => pass ? "✅ PASS" : "❌ FAIL";

// ═════════════════════════════════════════════════════════════════════════════
// Type declarations  (must follow all top-level code and local functions)
// ═════════════════════════════════════════════════════════════════════════════

/// <summary>One decoded entry parsed from WSJT-X ALL.TXT.</summary>
record WsjtxEntry(string Timestamp, int FreqHz, int Snr, string Message);

/// <summary>IClock implementation that returns a fixed UTC instant.</summary>
sealed class FixedClock(DateTime utc) : IClock
{
    public DateTime UtcNow => utc;
}
