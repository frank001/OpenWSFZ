using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using OpenWSFZ.Ft8;
using OpenWSFZ.Ft8.Interop;
using Xunit;
using Xunit.Abstractions;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// ONE-OFF VERIFICATION (not a permanent gate, pending Captain's decision on whether to keep
/// it) — F-005 hash-table-saturation-diagnostic. Replays the full real off-air corpus at
/// <c>artefacts/20260615_live_run/save</c> (2,291 WAVs, ~9.5h of genuine captured FT8 traffic,
/// predates F-001) through the current decoder build in a single process, so the native
/// process-global hash table accumulates exactly as it would in a real daemon session, then
/// reads <see cref="Ft8LibInterop.GetHashTableRejectCount"/> once at the end — the same
/// session-end read the daemon performs at graceful shutdown (design.md D2).
///
/// <para>
/// Purpose: get a genuine answer, from real recorded RF (not synthetic fictional callsigns),
/// to the question F-005 exists to answer — does the 256-slot table's capacity assumption
/// (F-001 design D3) actually get exceeded in practice — without needing 9.5 hours of
/// real-time audio replay. Runtime is bounded by decode compute, not wall-clock: a 30-file
/// timing pilot measured ~448ms/file, i.e. ~17 minutes for the full corpus.
/// </para>
///
/// <para>
/// Follows the same "measurement tool, not a gate" philosophy and graceful-skip-when-absent
/// convention as <see cref="ReplayHarnessTests"/> (FR-029) — <c>artefacts/</c> is gitignored
/// (NFR-021/GDPR — may contain real third-party callsigns), so this always skips cleanly in CI
/// and on any machine without the corpus.
/// </para>
/// </summary>
public sealed class F005RealCorpusSaturationCheck
{
    private readonly ITestOutputHelper _out;
    public F005RealCorpusSaturationCheck(ITestOutputHelper output) => _out = output;

    private static readonly string CorpusDir = Path.GetFullPath(Path.Combine(
        AppContext.BaseDirectory, "..", "..", "..", "..", "..",
        "artefacts", "20260615_live_run", "save"));

    [Fact(DisplayName = "f-005 VERIFY: full 20260615 real corpus replay — genuine hash-table reject count")]
    public async Task ReplayFullCorpus_ReportsGenuineRejectCount()
    {
        if (!Directory.Exists(CorpusDir))
        {
            _out.WriteLine($"Corpus not found at {CorpusDir} — skipping (expected on CI/other machines; artefacts/ is gitignored).");
            return;
        }

        string[] wavFiles = Directory.GetFiles(CorpusDir, "*.wav").OrderBy(f => f).ToArray();
        _out.WriteLine($"Corpus: {wavFiles.Length} WAV files at {CorpusDir}");

        int rejectsBefore = Ft8LibInterop.GetHashTableRejectCount();
        _out.WriteLine($"Reject count before replay (whatever this process already accumulated): {rejectsBefore}");

        int totalDecodes = 0;
        int hashPlaceholderDecodes = 0; // messages containing the '<...>' unresolved-hash placeholder
        int filesFailed = 0;
        var sw = Stopwatch.StartNew();

        foreach (string path in wavFiles)
        {
            float[] pcm;
            try { pcm = WavReader.Read(path); }
            catch (Exception ex)
            {
                filesFailed++;
                _out.WriteLine($"[SKIP] {Path.GetFileName(path)}: WavReader error — {ex.Message}");
                continue;
            }

            var decoder = new Ft8Decoder(new FakeClock(DateTime.UtcNow));
            try
            {
                var results = await decoder.DecodeAsync(pcm, CancellationToken.None);
                totalDecodes += results.Count;
                hashPlaceholderDecodes += results.Count(r => r.Message.Contains('<'));
            }
            catch (Exception ex)
            {
                filesFailed++;
                _out.WriteLine($"[ERROR] {Path.GetFileName(path)}: decoder threw — {ex.Message}");
            }
        }

        sw.Stop();
        int rejectsAfter = Ft8LibInterop.GetHashTableRejectCount();
        int delta = rejectsAfter - rejectsBefore;

        var sb = new StringBuilder();
        sb.AppendLine("=== F-005 REAL-CORPUS SATURATION CHECK ===");
        sb.AppendLine($"Corpus                         : {CorpusDir}");
        sb.AppendLine($"WAV files processed            : {wavFiles.Length} ({filesFailed} failed/skipped)");
        sb.AppendLine($"Elapsed                        : {sw.Elapsed.TotalMinutes:F1} min ({sw.Elapsed.TotalMilliseconds / wavFiles.Length:F1} ms/file)");
        sb.AppendLine($"Total decodes                  : {totalDecodes}");
        sb.AppendLine($"Decodes with '<' hash placeholder: {hashPlaceholderDecodes}");
        sb.AppendLine($"Reject count before             : {rejectsBefore}");
        sb.AppendLine($"Reject count after              : {rejectsAfter}");
        sb.AppendLine($"Reject count DELTA (this run)   : {delta}");
        sb.AppendLine();
        sb.AppendLine(delta > 0
            ? $"RESULT: table saturation OBSERVED against real off-air traffic — {delta} Type 4 " +
              "announcements were discarded because the 256-slot table was already full."
            : "RESULT: no saturation observed against this corpus — the 256-slot table was " +
              "never exceeded across this session's real traffic.");

        _out.WriteLine(sb.ToString());

        // Measurement tool, not a gate — always passes regardless of outcome.
        Assert.True(true);
    }
}
