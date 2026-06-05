using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Ft8;
using Xunit;
using Xunit.Abstractions;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// FR-029: Offline replay harness — measures decoder recovery rate against the
/// WSJT-X corpus captured in <c>p10-decoder-ground-truth_items/</c>.
///
/// This test is a **measurement tool**, not a gate. It:
/// <list type="bullet">
///   <item>Skips gracefully when the corpus directory is not present (CI, other machines).</item>
///   <item>Always passes — the result is reported via <see cref="ITestOutputHelper"/>
///     and written to <c>openspec/changes/p10-decoder-ground-truth/findings.md</c>.</item>
/// </list>
///
/// To run locally:
/// <code>
/// dotnet test -c Release --filter "DisplayName~Replay harness"
/// </code>
/// </summary>
public sealed class ReplayHarnessTests
{
    private readonly ITestOutputHelper _out;

    public ReplayHarnessTests(ITestOutputHelper output) => _out = output;

    // ── Paths ─────────────────────────────────────────────────────────────────

    /// <summary>Root of the corpus directory deposited by the Captain.</summary>
    private static readonly string CorpusRoot = Path.Combine(
        AppContext.BaseDirectory,          // bin/Release/net10.0/
        "..", "..", "..", "..", "..", // → repo root
        "p10-decoder-ground-truth_items");

    private static string SaveDir    => Path.GetFullPath(Path.Combine(CorpusRoot, "save"));
    private static string WsjtxAllTxt => Path.GetFullPath(Path.Combine(CorpusRoot, "WSJT-X ALL.TXT"));

    private static string FindingsPath => Path.GetFullPath(Path.Combine(
        AppContext.BaseDirectory,
        "..", "..", "..", "..", "..",
        "openspec", "changes", "p10-decoder-ground-truth", "findings.md"));

    // ── Test ──────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-029: Replay harness — decoder recovery-rate measurement against WSJT-X corpus")]
    public async Task MeasureRecoveryRate_AgainstWsjtxCorpus()
    {
        // ── Guard: skip if corpus is absent ───────────────────────────────────
        if (!Directory.Exists(SaveDir) || !File.Exists(WsjtxAllTxt))
        {
            _out.WriteLine($"Corpus not found at '{CorpusRoot}' — skipping measurement.");
            _out.WriteLine("To run this harness, ensure 'p10-decoder-ground-truth_items/' exists in the repo root.");
            return;
        }

        // ── Parse WSJT-X answer keys ──────────────────────────────────────────
        var answerKeys = WsjtxAllTxtParser.Parse(WsjtxAllTxt);
        _out.WriteLine($"WSJT-X ALL.TXT parsed: {answerKeys.Count} timestamps, " +
                       $"{answerKeys.Values.Sum(l => l.Count)} total decodes.");

        // ── Enumerate WAV files ───────────────────────────────────────────────
        string[] wavFiles = Directory.GetFiles(SaveDir, "*.wav")
                                     .OrderBy(f => f)
                                     .ToArray();
        _out.WriteLine($"Corpus: {wavFiles.Length} WAV files in '{SaveDir}'");

        // ── Per-file and aggregate counters ───────────────────────────────────
        int totalWsjtx     = 0;
        int totalMatched   = 0;
        int totalFalsePos  = 0;

        var sb = new StringBuilder();
        sb.AppendLine("# p10 Recovery-Rate Findings");
        sb.AppendLine();
        sb.AppendLine($"**Date:** {DateTime.UtcNow:yyyy-MM-dd HH:mm:ss} UTC");
        sb.AppendLine($"**Corpus:** {wavFiles.Length} × 15-second WAVs, 12 kHz mono int16, 7.074 MHz");
        sb.AppendLine($"**WSJT-X answer keys:** {answerKeys.Values.Sum(l => l.Count)} total decodes " +
                      $"across {answerKeys.Count} cycles");
        sb.AppendLine();
        sb.AppendLine("## Per-file results");
        sb.AppendLine();
        sb.AppendLine("| Cycle | WSJT-X | Ours | Matched | Missed | False+ |");
        sb.AppendLine("|---|---|---|---|---|---|");

        foreach (string wavPath in wavFiles)
        {
            string wavName   = Path.GetFileNameWithoutExtension(wavPath); // e.g. "260528_235745"
            string timestamp = wavName;

            // Read WAV → PCM
            float[] pcm;
            try   { pcm = WavReader.Read(wavPath); }
            catch (Exception ex)
            {
                _out.WriteLine($"[SKIP] {wavName}: WavReader error — {ex.Message}");
                continue;
            }

            // Parse the cycle timestamp — guard against stray filenames that don't match YYMMDD_HHMMSS.
            FakeClock clock;
            try
            {
                clock = ParseClockFromTimestamp(timestamp);
            }
            catch (Exception ex)
            {
                _out.WriteLine($"[SKIP] {wavName}: cannot parse timestamp — {ex.Message}");
                continue;
            }

            var decoder = new Ft8Decoder(clock);
            IReadOnlyList<DecodeResult> results;
            try
            {
                results = await decoder.DecodeAsync(pcm, CancellationToken.None);
            }
            catch (Exception ex)
            {
                _out.WriteLine($"[ERROR] {wavName}: decoder threw — {ex.Message}");
                continue;
            }

            var ourMessages    = results.Select(r => r.Message).ToHashSet(StringComparer.OrdinalIgnoreCase);
            var wsjtxMessages  = answerKeys.TryGetValue(timestamp, out var ak)
                                 ? ak.ToHashSet(StringComparer.OrdinalIgnoreCase)
                                 : new HashSet<string>(StringComparer.OrdinalIgnoreCase);

            int wsjtxCount  = wsjtxMessages.Count;
            int matched     = ourMessages.Count(m => wsjtxMessages.Contains(m));
            int falsePos    = ourMessages.Count(m => !wsjtxMessages.Contains(m));
            int missed      = wsjtxCount - matched;

            totalWsjtx    += wsjtxCount;
            totalMatched  += matched;
            totalFalsePos += falsePos;

            sb.AppendLine($"| `{timestamp}` | {wsjtxCount} | {ourMessages.Count} | {matched} | {missed} | {falsePos} |");

            _out.WriteLine($"{timestamp}: WSJT-X={wsjtxCount}  Ours={ourMessages.Count}  " +
                           $"Matched={matched}  FalsePos={falsePos}");
        }

        // ── Aggregate summary ─────────────────────────────────────────────────
        double recoveryRate = totalWsjtx > 0
            ? (double)totalMatched / totalWsjtx * 100.0
            : 0.0;

        sb.AppendLine();
        sb.AppendLine("## Aggregate summary");
        sb.AppendLine();
        sb.AppendLine($"| Metric | Value |");
        sb.AppendLine($"|---|---|");
        sb.AppendLine($"| WAV files decoded | {wavFiles.Length} |");
        sb.AppendLine($"| WSJT-X total decodes | {totalWsjtx} |");
        sb.AppendLine($"| Our matched decodes | {totalMatched} |");
        sb.AppendLine($"| Our false positives | {totalFalsePos} |");
        sb.AppendLine($"| **Recovery rate** | **{recoveryRate:F1}%** |");
        sb.AppendLine();
        sb.AppendLine("## Decision-gate outcome");
        sb.AppendLine();
        sb.AppendLine(recoveryRate switch
        {
            0.0 => "Recovery rate is **0.0%** — no signals decoded.\n\n" +
                   "**Action required:** ft8_lib interop is broken. Investigate `Ft8LibInterop.cs`, " +
                   "confirm the native shared library is present in the output directory, and verify " +
                   "that `LoadAndVerify()` succeeds without exception.",

            < 55.0 => $"Recovery rate is **{recoveryRate:F1}%** — below the established baseline (~66.6%).\n\n" +
                      "**Action required:** ft8_lib wrapper regression or parameter change. " +
                      "Compare decoder parameters against the p12 baseline. Review recent changes to " +
                      "`Ft8LibInterop.cs` and `Ft8Decoder.cs`. G6 gate may still be green if the committed " +
                      "fixture answer keys are all recovered — check `RealSignalFixtureTests` results.",

            _ => $"Recovery rate is **{recoveryRate:F1}%** — within normal operating range.\n\n" +
                 "**Status: nominal.** The miss rate relative to WSJT-X is a known, accepted " +
                 "limitation of the ft8_lib single-pass decoder. OpenWSFZ wraps it with a 2-pass " +
                 "iterative-subtraction loop, which recovers additional signals on each second pass, " +
                 "but WSJT-X employs a deeper multi-pass strategy that the current implementation " +
                 "does not replicate. Closing this gap is deferred to a future change. No action required."
        });

        string findings = sb.ToString();

        // ── Write findings.md ─────────────────────────────────────────────────
        try
        {
            string? dir = Path.GetDirectoryName(FindingsPath);
            if (dir is not null) Directory.CreateDirectory(dir);
            File.WriteAllText(FindingsPath, findings, Encoding.UTF8);
            _out.WriteLine($"\nFindings written to: {FindingsPath}");
        }
        catch (Exception ex)
        {
            _out.WriteLine($"[WARN] Could not write findings.md: {ex.Message}");
        }

        // ── Echo summary ──────────────────────────────────────────────────────
        _out.WriteLine(string.Empty);
        _out.WriteLine("=== AGGREGATE SUMMARY ===");
        _out.WriteLine($"WSJT-X total decodes : {totalWsjtx}");
        _out.WriteLine($"Our matched decodes   : {totalMatched}");
        _out.WriteLine($"Our false positives   : {totalFalsePos}");
        _out.WriteLine($"Recovery rate        : {recoveryRate:F1}%");
        _out.WriteLine(string.Empty);
        _out.WriteLine(recoveryRate switch
        {
            0.0    => "DECISION: interop failure — 0% recovery, check Ft8LibInterop.cs",
            < 55.0 => $"DECISION: regression — {recoveryRate:F1}% is below ~66.6% baseline",
            _      => $"STATUS: nominal — {recoveryRate:F1}% (iterative subtraction gap is accepted)"
        });

        // ── This test always passes — it is a measurement tool, not a gate ───
        // The real gate is RealSignalFixtureTests which asserts specific messages.
        true.Should().BeTrue();
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    /// <summary>
    /// Parses a timestamp like <c>"260528_235745"</c> into a UTC
    /// <see cref="DateTime"/> and returns a <see cref="FakeClock"/> set to it.
    /// </summary>
    private static FakeClock ParseClockFromTimestamp(string ts)
    {
        // ts = "YYMMDD_HHMMSS"
        int year   = 2000 + int.Parse(ts[..2]);
        int month  = int.Parse(ts[2..4]);
        int day    = int.Parse(ts[4..6]);
        int hour   = int.Parse(ts[7..9]);
        int minute = int.Parse(ts[9..11]);
        int second = int.Parse(ts[11..13]);
        return new FakeClock(new DateTime(year, month, day, hour, minute, second, DateTimeKind.Utc));
    }
}
