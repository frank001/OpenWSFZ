// PASSBAND-140 managed chain tool (spec section 3.1).
//
// Two modes:
//   row0c <ALL.TXT>  [dial-prefix]
//     ROW 0c: apply the chain to C2's live openwsfz/ALL.TXT, grouped per cycle,
//     and report the rejection rate. Must be <= 0.1% (<=57 of 57,969) or the
//     arm's replay legs cannot be trusted -- live is already post-chain, so a
//     correct re-application should reject ~nothing.
//
//   chain <in.jsonl> <out.jsonl>
//     Apply the chain to a decode_leg.py-style JSONL file (one line per cycle:
//     {"ts": "...", "results": [{"freq_hz":.., "dt":.., "snr":.., "message":".."}]})
//     and write the post-chain JSONL (same shape, filtered + deduped) plus a
//     summary line to stderr. Used by every replay leg in section 2.2.
//
// NFR-021: message text is read into memory to run the filter and is written
// only to gitignored artefacts/ paths the caller supplies -- never to qa/.
// This tool itself writes no output path; the caller (a shell/PowerShell
// invocation, or a wrapper script under artefacts/) controls where JSONL lands.

using System.Reflection;
using System.Security.Cryptography;
using System.Text.Json;
using OpenWSFZ.Config;
using OpenWSFZ.Daemon;
using OpenWSFZ.Ft8;

if (args.Length < 1)
{
    Console.Error.WriteLine("usage: PassbandChain row0c <ALL.TXT> [dial-prefix]");
    Console.Error.WriteLine("       PassbandChain chain <in.jsonl> <out.jsonl>");
    return 2;
}

// ── Build the same CallsignGrammarStore the daemon builds (Program.cs:115-123) ──
string configPath = ConfigPathResolver.ResolvePath();
string grammarPath = Path.Combine(
    Path.GetDirectoryName(configPath) ?? AppContext.BaseDirectory,
    "callsign-grammar.json");

var grammarStore = new CallsignGrammarStore(grammarPath);
await grammarStore.LoadAsync();

string grammarSha256 = Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(grammarPath)))
    .ToLowerInvariant();
Console.Error.WriteLine($"[PassbandChain] callsign-grammar.json = {grammarPath}");
Console.Error.WriteLine($"[PassbandChain] callsign-grammar.json sha256 = {grammarSha256}");

// ── Reflection handle onto the production filter (internal static, Ft8Decoder.cs:568) ──
MethodInfo isPlausibleMessage = typeof(Ft8Decoder).GetMethod(
        "IsPlausibleMessage", BindingFlags.NonPublic | BindingFlags.Static)
    ?? throw new InvalidOperationException(
        "Ft8Decoder.IsPlausibleMessage not found by reflection -- signature or " +
        "accessibility changed since the spec was written; stop and re-check " +
        "Ft8Decoder.cs before trusting any chain output.");

bool IsPlausible(string msg) =>
    (bool)(isPlausibleMessage.Invoke(null, new object?[] { msg, grammarStore }) ?? false);

string mode = args[0];

if (mode == "row0c")
{
    if (args.Length < 2)
    {
        Console.Error.WriteLine("usage: PassbandChain row0c <ALL.TXT> [dial-prefix] [ts-lo] [ts-hi]");
        return 2;
    }
    return RunRow0c(
        args[1],
        args.Length > 2 ? args[2] : "14.074",
        args.Length > 3 ? args[3] : null,
        args.Length > 4 ? args[4] : null);
}

if (mode == "chain")
{
    if (args.Length < 3)
    {
        Console.Error.WriteLine("usage: PassbandChain chain <in.jsonl> <out.jsonl>");
        return 2;
    }
    return RunChain(args[1], args[2]);
}

Console.Error.WriteLine($"unknown mode '{mode}'");
return 2;

// ── ROW 0c ───────────────────────────────────────────────────────────────────
int RunRow0c(string allTxtPath, string dialPrefix, string? tsLo, string? tsHi)
{
    var byCycle = new Dictionary<string, List<string>>();
    int totalRows = 0;

    foreach (string line in File.ReadLines(allTxtPath))
    {
        string[] f = line.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries);
        // ts dial Rx FT8 snr dt freq <message tokens...> -- matcher.py / h1_hash_token_contamination.load()'s own filter, mirrored.
        if (f.Length < 8 || f[2] != "Rx" || f[3] != "FT8") continue;
        if (!f[1].StartsWith(dialPrefix, StringComparison.Ordinal)) continue;

        string ts = f[0];
        if (tsLo is not null && string.CompareOrdinal(ts, tsLo) < 0) continue;
        if (tsHi is not null && string.CompareOrdinal(ts, tsHi) > 0) continue;
        string msg = string.Join(' ', f[7..]);
        if (!byCycle.TryGetValue(ts, out List<string>? list))
            byCycle[ts] = list = new List<string>();
        list.Add(msg);
        totalRows++;
    }

    int rejected = 0;
    var rejectedExamples = new List<(string ts, string msg)>();
    var seenInCycle = new HashSet<string>(StringComparer.Ordinal);

    foreach ((string ts, List<string> msgs) in byCycle)
    {
        seenInCycle.Clear();
        foreach (string raw in msgs)
        {
            string trimmed = raw.TrimEnd();
            if (!seenInCycle.Add(trimmed)) continue; // dedup -- should never fire on live ALL.TXT
            if (!IsPlausible(trimmed))
            {
                rejected++;
                if (rejectedExamples.Count < 10) rejectedExamples.Add((ts, trimmed));
            }
        }
    }

    double pct = totalRows > 0 ? 100.0 * rejected / totalRows : double.NaN;
    bool pass = totalRows > 0 && rejected <= Math.Ceiling(totalRows * 0.001);

    Console.WriteLine($"ROW 0c: total_rows={totalRows} cycles={byCycle.Count} " +
                       $"rejected={rejected} reject_pct={pct:F4}% " +
                       $"threshold_rows={Math.Ceiling(totalRows * 0.001)} pass={pass}");
    Console.WriteLine($"grammar_sha256={grammarSha256}");
    if (rejectedExamples.Count > 0)
    {
        Console.WriteLine("first rejected (ts only, NFR-021 -- no message text to stdout):");
        foreach ((string ts, string _) in rejectedExamples)
            Console.WriteLine($"  ts={ts}");
    }

    return pass ? 0 : 1;
}

// ── chain (replay legs, section 2.2) ────────────────────────────────────────
int RunChain(string inPath, string outPath)
{
    long totalIn = 0, totalOut = 0, totalRejected = 0, totalDupRemoved = 0;
    long cycles = 0;

    Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outPath))!);
    using var outFh = new StreamWriter(outPath, append: false);

    foreach (string line in File.ReadLines(inPath))
    {
        if (string.IsNullOrWhiteSpace(line)) continue;
        cycles++;

        using JsonDocument doc = JsonDocument.Parse(line);
        JsonElement root = doc.RootElement;
        string ts = root.GetProperty("ts").GetString() ?? "";

        var kept = new List<JsonElement>();
        var seen = new HashSet<string>(StringComparer.Ordinal);

        if (root.TryGetProperty("results", out JsonElement results) &&
            results.ValueKind == JsonValueKind.Array)
        {
            foreach (JsonElement r in results.EnumerateArray())
            {
                totalIn++;
                string msg = (r.TryGetProperty("message", out JsonElement m) ? m.GetString() : null)
                             ?? "";
                string trimmed = msg.TrimEnd();
                if (!seen.Add(trimmed)) { totalDupRemoved++; continue; }
                if (!IsPlausible(trimmed)) { totalRejected++; continue; }
                kept.Add(r);
                totalOut++;
            }
        }

        var outRec = new { ts, results = kept.Select(k => JsonSerializer.Deserialize<object>(k.GetRawText())) };
        outFh.WriteLine(JsonSerializer.Serialize(outRec));
    }

    outFh.Flush();
    Console.Error.WriteLine($"[PassbandChain chain] {inPath} -> {outPath}");
    Console.Error.WriteLine($"  cycles={cycles} in={totalIn} out={totalOut} " +
                             $"rejected={totalRejected} dup_removed={totalDupRemoved}");
    return 0;
}
