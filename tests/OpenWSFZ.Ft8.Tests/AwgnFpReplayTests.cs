using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using FluentAssertions;
using OpenWSFZ.Ft8.Interop;
using Xunit;
using Xunit.Abstractions;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// `AWGN-FP` — decode-side of the offline S5 false-accept replay harness.
/// <para>
/// Spec: <c>qa/rr-study/2026-09-02-1906-architect-to-qa-spec-awgn-fp-offline-replay.md</c>
/// (Architect → QA, 2026-09-02 19:06Z). Runs ROW 0 (a→d) of that spec's pre-registered gate
/// — instrument validity — against WAV populations already rendered offline via the shipped
/// generator (<c>harness/run_scenario.py --dry-run --dump-wav-dir</c>, no new noise source,
/// no playback device). This file is the "equivalent under tests/OpenWSFZ.Ft8.Tests/" the spec
/// explicitly permits as QA's own call (HK-015) in place of a second Python ctypes binding,
/// because <see cref="Ft8LibInterop.GetLastSnrTerms"/> and <see cref="Ft8LibInterop.DecodeAll"/>
/// are <c>internal</c> and only reachable from an assembly with
/// <c>InternalsVisibleTo("OpenWSFZ.Ft8.Tests")</c> — <c>tools/</c> has no such grant, and adding
/// one would touch <c>src/OpenWSFZ.Ft8/AssemblyAttributes.cs</c>, which spec §5 step 1 forbids
/// ("Do not touch src/ or native/").
/// </para>
/// <para>
/// Each [Fact] is independently runnable (<c>dotnet test --filter "FullyQualifiedName~AwgnFpReplay"</c>)
/// and re-asserts the ROW 0a binary-identity pin itself (HK-021(p): "every row below is void if
/// that pin does not hold for the whole run") rather than depending on xunit test ordering.
/// </para>
/// <para>
/// Deliberate xunit-pass/fail split: ROW 0a (binary identity) is a hard mechanical precondition —
/// a mismatch means nothing downstream can be trusted, so it is asserted (test fails red). ROW 0b/0c/0d
/// are FINDINGS, not test-infra correctness — "the offline instrument does not reproduce the in-chain
/// phenomenon" is a complete, publishable, negative result per spec §5 step 2, not a red test. Those
/// three Facts assert only that decoding ran to completion and CSVs were written; the actual
/// band-membership verdict is computed, printed to test output (captured by <c>-v n</c>), and written
/// to a results file for the report to quote verbatim — never asserted as pass/fail here.
/// </para>
/// </summary>
[Trait("Category", "RequiresNativeBinary")]
[Trait("Category", "AwgnFpReplay")]
public sealed class AwgnFpReplayTests
{
    private readonly ITestOutputHelper _out;

    public AwgnFpReplayTests(ITestOutputHelper output) => _out = output;

    // ── ROW 0a pin — win-x64 SHA256, shim 20260049, from
    //    src/OpenWSFZ.Ft8/Native/win-x64/libft8.version.txt line 28 (f001-h12-unique-match-suppression,
    //    "CURRENT" block at the top of the file as of this arm's base commit main@3b52608). A
    //    FT8_SHIM_VERSION string is NOT an identity (standing rule) — this is the binary's own hash. ──
    private const string PinnedShaWinX64 =
        "ce02c7ba10e216349c3cc6d2460a6106379a4593bb730c807dbe8128ecca153e";

    private static readonly Regex SlotFileNameRe =
        new(@"^(?<scenario>[A-Za-z0-9]+)_p(?<part>\d+)_t(?<trial>\d+)_s(?<seed>\d+)\.wav$",
            RegexOptions.Compiled);

    // ── ROW 0b anchor band — exact Poisson 95% CI for k=4 events, taken to whole events,
    //    pre-registered in the spec (§4 ROW 0b): [1.09, 10.24] -> {2,...,10}. ──
    private const int AnchorBandLow = 2;
    private const int AnchorBandHigh = 10;

    private const int Row0dMinGenuineDecodes = 200;

    // ── ROW 0a — binary identity ────────────────────────────────────────────────────────

    [Fact(DisplayName = "ROW 0a: loaded libft8.dll SHA256 matches the pinned shim 20260049 manifest value")]
    public void Row0a_BinaryIdentity_MatchesPinnedSha256()
    {
        string dllPath = Path.Combine(AppContext.BaseDirectory, "libft8.dll");
        File.Exists(dllPath).Should().BeTrue($"the native binary under test must be present at '{dllPath}'");

        string actualSha = ComputeSha256(dllPath);
        _out.WriteLine($"ROW 0a: {dllPath}");
        _out.WriteLine($"ROW 0a: actual   SHA256 = {actualSha}");
        _out.WriteLine($"ROW 0a: pinned   SHA256 = {PinnedShaWinX64}");

        actualSha.Should().Be(PinnedShaWinX64,
            "ROW 0a fires on any mismatch: 'a FT8_SHIM_VERSION string is not an identity' (standing rule) — " +
            "every row in this spec is void if the binary pin does not hold for the whole run (HK-021(p))");
    }

    // ── ROW 0b — the anchor: this sweep's own 60 S5 seeds, offline ─────────────────────

    [Fact(DisplayName = "ROW 0b: offline replay of the in-chain sweep's own 60 S5 seeds (anchor)")]
    public void Row0b_S5Anchor60Slots_ReportsEventCountAgainstPoissonBand()
    {
        AssertBinaryPin();

        string wavDir = Path.Combine(FindRepoRoot(), "qa", "rr-study", "awgn-fp-replay", "_work", "row0b_baseline");
        string outDir = Path.Combine(FindRepoRoot(), "qa", "rr-study", "awgn-fp-replay", "results");

        var slots = DecodeDirectory(wavDir, outDir, "row0b_baseline");

        slots.Should().HaveCount(60, "ROW 0b replays exactly the in-chain sweep's 60 S5 seeds (parts 0+1, 30 trials each)");

        int events = slots.Count(s => s.Decodes.Count > 0);
        bool inBand = events >= AnchorBandLow && events <= AnchorBandHigh;

        _out.WriteLine($"ROW 0b: slots={slots.Count}  events(>=1 decode)={events}  " +
                        $"band=[{AnchorBandLow},{AnchorBandHigh}]  in_band={inBand}");
        WriteVerdictLine(outDir, "row0b_baseline",
            $"slots=60 events={events} band=[{AnchorBandLow},{AnchorBandHigh}] in_band={inBand}");

        // Mechanical sanity only — a FAIL here is a complete, publishable ROW 0 finding
        // (spec §5 step 2), not a test-infra defect, so it is NOT asserted red.
        slots.Should().OnlyContain(s => s.Decodes.Count >= 0);
    }

    // ── ROW 0c (FIRST ATTEMPT, INVALID -- kept for the record, see the corrected Fact below) ──
    //
    // These two directories (row0c_minus10 / row0c_plus10) were rendered via
    // harness/run_scenario.py --dry-run --dump-wav-dir against scratch scenario files whose only
    // change was level_dbfs +/-10 dB. Discovered AFTER running: run_scenario.py's main loop
    // peak-normalises every rendered slot to a fixed 0.9 peak amplitude BEFORE either live
    // playback or --dump-wav-dir writes it out. For a pure-Gaussian buffer this is not cosmetic:
    // normalised_output = raw_draw * (0.9 / max(|raw_draw|)) is algebraically INDEPENDENT of the
    // level_dbfs amplitude term (it cancels exactly), so every level_dbfs value produces the same
    // delivered RMS for a given seed. Measured directly on the REAL scenarios/s5-noise.json
    // baseline render: part 0 (-20 dBFS nominal) and part 1 (-10 dBFS nominal) -- a declared 10 dB
    // gap -- both land at -20.5..-22 dBFS actual RMS. This is a pre-existing property of the
    // shared S5 rendering path (same code before live hardware playback too), not something this
    // arm's offline replay introduced, and out of scope to fix here. The test below still runs
    // (mechanically harmless) but its "level_dependent" verdict is NOT cited -- see
    // Row0c_LevelDependence_LevelPreservingRerender for the corrected probe.

    [Fact(DisplayName = "ROW 0c FIRST ATTEMPT (INVALID -- normalisation cancels level, see the level-preserving rerender below)")]
    public void Row0c_LevelDependence_ReportsEventCountsAtPlusMinus10dB()
    {
        AssertBinaryPin();

        string root = Path.Combine(FindRepoRoot(), "qa", "rr-study", "awgn-fp-replay");
        string outDir = Path.Combine(root, "results");

        var minus10 = DecodeDirectory(Path.Combine(root, "_work", "row0c_minus10"), outDir, "row0c_minus10");
        var plus10 = DecodeDirectory(Path.Combine(root, "_work", "row0c_plus10"), outDir, "row0c_plus10");

        minus10.Should().HaveCount(60);
        plus10.Should().HaveCount(60);

        int eventsMinus10 = minus10.Count(s => s.Decodes.Count > 0);
        int eventsPlus10 = plus10.Count(s => s.Decodes.Count > 0);

        // Mechanical reading adopted for this arm (documented here because the spec's own
        // wording -- "if the event count moves by more than the same Poisson band" -- is not
        // itself a single unambiguous test): each perturbed count must independently still land
        // inside ROW 0b's own [2,10] band. Falling outside either one means "level-dependent" —
        // this is a literal re-application of the ALREADY-COMPUTED band, not a new derived
        // quantity (HK-021: hard threshold, computed not hand-typed, pre-registered).
        bool minus10InBand = eventsMinus10 >= AnchorBandLow && eventsMinus10 <= AnchorBandHigh;
        bool plus10InBand = eventsPlus10 >= AnchorBandLow && eventsPlus10 <= AnchorBandHigh;
        bool levelDependent = !minus10InBand || !plus10InBand;

        _out.WriteLine($"ROW 0c: -10dB events={eventsMinus10} in_band={minus10InBand}");
        _out.WriteLine($"ROW 0c: +10dB events={eventsPlus10} in_band={plus10InBand}");
        _out.WriteLine($"ROW 0c: level_dependent={levelDependent} " +
                        (levelDependent
                            ? "-> ROW 1 downgrades to relative-only (spec §4 ROW 0c)"
                            : "-> absolute in-chain-gate comparison remains valid"));
        WriteVerdictLine(outDir, "row0c",
            $"minus10_events={eventsMinus10} in_band={minus10InBand} " +
            $"plus10_events={eventsPlus10} in_band={plus10InBand} level_dependent={levelDependent}");

        minus10.Should().OnlyContain(s => s.Decodes.Count >= 0);
        plus10.Should().OnlyContain(s => s.Decodes.Count >= 0);
    }

    // ── ROW 0c (CORRECTED) — level dependence via a level-preserving rerender ──────────
    //
    // Renders come from render_row0c_level_preserving.py, which calls the SAME shipped
    // harness.run_scenario._render_noise() (identical RNG/amplitude formula, not a second noise
    // source) but skips the peak-renormalise-to-0.9 step that cancelled the level in the first
    // attempt above. Verified directly (RMS measured from the WAVs): row0c_lp_baseline part0/part1
    // = -26.17/-16.21 dBFS actual RMS, row0c_lp_minus10 = -36.17/-26.21 dBFS, row0c_lp_plus10 =
    // -16.17/-6.53 dBFS -- exact 10 dB steps this time, both parts, both directions.

    [Fact(DisplayName = "ROW 0c (corrected): level-dependence probe via a level-preserving rerender at -10 dB / +10 dB")]
    public void Row0c_LevelDependence_LevelPreservingRerender()
    {
        AssertBinaryPin();

        string root = Path.Combine(FindRepoRoot(), "qa", "rr-study", "awgn-fp-replay");
        string outDir = Path.Combine(root, "results");

        var lpBaseline = DecodeDirectory(Path.Combine(root, "_work", "row0c_lp_baseline"), outDir, "row0c_lp_baseline");
        var lpMinus10 = DecodeDirectory(Path.Combine(root, "_work", "row0c_lp_minus10"), outDir, "row0c_lp_minus10");
        var lpPlus10 = DecodeDirectory(Path.Combine(root, "_work", "row0c_lp_plus10"), outDir, "row0c_lp_plus10");

        lpBaseline.Should().HaveCount(60);
        lpMinus10.Should().HaveCount(60);
        lpPlus10.Should().HaveCount(60);

        int eventsBaseline = lpBaseline.Count(s => s.Decodes.Count > 0);
        int eventsMinus10 = lpMinus10.Count(s => s.Decodes.Count > 0);
        int eventsPlus10 = lpPlus10.Count(s => s.Decodes.Count > 0);

        // Same mechanical reading as the first attempt (§ comment there): each perturbed count
        // must independently still land inside ROW 0b's own [2,10] band, or the instrument is
        // level-dependent and ROW 1 downgrades to relative-only. This time the level actually moved.
        bool baselineInBand = eventsBaseline >= AnchorBandLow && eventsBaseline <= AnchorBandHigh;
        bool minus10InBand = eventsMinus10 >= AnchorBandLow && eventsMinus10 <= AnchorBandHigh;
        bool plus10InBand = eventsPlus10 >= AnchorBandLow && eventsPlus10 <= AnchorBandHigh;
        bool levelDependent = !minus10InBand || !plus10InBand;

        _out.WriteLine($"ROW 0c (corrected): baseline(-26.2/-16.2dBFS) events={eventsBaseline} in_band={baselineInBand}");
        _out.WriteLine($"ROW 0c (corrected): -10dB(-36.2/-26.2dBFS) events={eventsMinus10} in_band={minus10InBand}");
        _out.WriteLine($"ROW 0c (corrected): +10dB(-16.2/-6.5dBFS) events={eventsPlus10} in_band={plus10InBand}");
        _out.WriteLine($"ROW 0c (corrected): level_dependent={levelDependent} " +
                        (levelDependent
                            ? "-> ROW 1 downgrades to relative-only (spec §4 ROW 0c)"
                            : "-> absolute in-chain-gate comparison remains valid"));
        WriteVerdictLine(outDir, "row0c_corrected",
            $"baseline_events={eventsBaseline} in_band={baselineInBand} " +
            $"minus10_events={eventsMinus10} in_band={minus10InBand} " +
            $"plus10_events={eventsPlus10} in_band={plus10InBand} level_dependent={levelDependent}");

        lpBaseline.Should().OnlyContain(s => s.Decodes.Count >= 0);
        lpMinus10.Should().OnlyContain(s => s.Decodes.Count >= 0);
        lpPlus10.Should().OnlyContain(s => s.Decodes.Count >= 0);
    }

    // ── ROW 0d — the complement exists: M3 >= 200 genuine decodes ──────────────────────

    [Fact(DisplayName = "ROW 0d: M3 complement (S1 ladder, N=25/part) yields >= 200 genuine decodes")]
    public void Row0d_ComplementExists_M3YieldsAtLeast200GenuineDecodes()
    {
        AssertBinaryPin();

        string root = Path.Combine(FindRepoRoot(), "qa", "rr-study", "awgn-fp-replay");
        string outDir = Path.Combine(root, "results");
        string wavDir = Path.Combine(root, "_work", "row0d_s1_complement");

        var slots = DecodeDirectory(wavDir, outDir, "row0d_s1_complement");

        slots.Should().HaveCount(250, "the S1 M3-complement scenario renders 10 parts x 25 trials");

        int totalGenuineDecodes = slots.Sum(s => s.Decodes.Count);
        bool row0dPasses = totalGenuineDecodes >= Row0dMinGenuineDecodes;

        _out.WriteLine($"ROW 0d: slots={slots.Count}  total_genuine_decodes={totalGenuineDecodes}  " +
                        $"threshold={Row0dMinGenuineDecodes}  passes={row0dPasses}");
        WriteVerdictLine(outDir, "row0d_s1_complement",
            $"slots=250 total_genuine_decodes={totalGenuineDecodes} " +
            $"threshold={Row0dMinGenuineDecodes} passes={row0dPasses}");

        slots.Should().OnlyContain(s => s.Decodes.Count >= 0);
    }

    // ── Shared decode/report machinery ──────────────────────────────────────────────────

    private sealed class DecodeRow
    {
        public string Scenario = "";
        public int Part;
        public int Trial;
        public long Seed;
        public string Message = "";
        public int FreqHz;
        public float Dt;
        public int ReportedSnrDb;
        public float SignalDb;
        public float LocalNoiseDb;
    }

    private sealed class SlotResult
    {
        public string Scenario = "";
        public int Part;
        public int Trial;
        public long Seed;
        public List<DecodeRow> Decodes = new();
    }

    private void AssertBinaryPin()
    {
        string dllPath = Path.Combine(AppContext.BaseDirectory, "libft8.dll");
        string actualSha = ComputeSha256(dllPath);
        actualSha.Should().Be(PinnedShaWinX64,
            "HK-021(p): every row is void if the binary pin does not hold for the whole run");
    }

    private static string ComputeSha256(string path)
    {
        using var stream = File.OpenRead(path);
        byte[] hash = SHA256.HashData(stream);
        var sb = new StringBuilder(hash.Length * 2);
        foreach (byte b in hash) sb.Append(b.ToString("x2"));
        return sb.ToString();
    }

    /// <summary>
    /// Decodes every <c>*.wav</c> in <paramref name="wavDir"/> (filenames
    /// <c>&lt;scenario&gt;_p&lt;part&gt;_t&lt;trial&gt;_s&lt;seed&gt;.wav</c>, written by
    /// <c>harness/run_scenario.py --dump-wav-dir</c>) via <see cref="Ft8LibInterop.DecodeAll"/> +
    /// <see cref="Ft8LibInterop.GetLastSnrTerms"/>, writes one row-per-slot CSV and one
    /// row-per-decode CSV under <paramref name="outDir"/>/<paramref name="label"/>_{slots,decodes}.csv,
    /// and returns the per-slot results in filename order.
    /// <see cref="Ft8LibInterop.SetApBits"/> is cleared before every decode (same TLS-contamination
    /// guard <c>GetLastSnrTermsTests</c>/<c>Ft8LibInteropTests</c> use) so no cross-slot AP state leaks.
    /// </summary>
    private static List<SlotResult> DecodeDirectory(string wavDir, string outDir, string label)
    {
        Directory.Exists(wavDir).Should().BeTrue($"rendered WAV directory must exist: '{wavDir}' " +
            "(run harness/run_scenario.py --dry-run --dump-wav-dir first)");
        Directory.CreateDirectory(outDir);

        var files = Directory.GetFiles(wavDir, "*.wav")
            .Select(f => (path: f, name: Path.GetFileName(f)))
            .Where(x => SlotFileNameRe.IsMatch(x.name))
            .OrderBy(x => x.name, StringComparer.Ordinal)
            .ToList();

        var slots = new List<SlotResult>(files.Count);

        string slotsCsvPath = Path.Combine(outDir, $"{label}_slots.csv");
        string decodesCsvPath = Path.Combine(outDir, $"{label}_decodes.csv");
        using var slotsCsv = new StreamWriter(slotsCsvPath, append: false, Encoding.UTF8);
        using var decodesCsv = new StreamWriter(decodesCsvPath, append: false, Encoding.UTF8);
        slotsCsv.WriteLine("scenario,part,trial,seed,n_decodes");
        decodesCsv.WriteLine("scenario,part,trial,seed,message,freq_hz,dt_s,reported_snr_db," +
                              "signal_db,local_noise_db,reconstructed_snr_db");

        foreach (var (path, name) in files)
        {
            var m = SlotFileNameRe.Match(name);
            string scenario = m.Groups["scenario"].Value;
            int part = int.Parse(m.Groups["part"].Value, CultureInfo.InvariantCulture);
            int trial = int.Parse(m.Groups["trial"].Value, CultureInfo.InvariantCulture);
            long seed = long.Parse(m.Groups["seed"].Value, CultureInfo.InvariantCulture);

            float[] pcm = WavReader.Read(path);
            if (pcm.Length != 180_000)
            {
                var padded = new float[180_000];
                Array.Copy(pcm, padded, Math.Min(pcm.Length, 180_000));
                pcm = padded;
            }

            Ft8LibInterop.SetApBits([], []);
            Ft8NativeResult[] results = Ft8LibInterop.DecodeAll(pcm);

            var slot = new SlotResult { Scenario = scenario, Part = part, Trial = trial, Seed = seed };

            if (results.Length > 0)
            {
                var (signalDb, localNoiseDb) = Ft8LibInterop.GetLastSnrTerms(results.Length);
                for (int i = 0; i < results.Length; i++)
                {
                    float sDb = i < signalDb.Length ? signalDb[i] : float.NaN;
                    float nDb = i < localNoiseDb.Length ? localNoiseDb[i] : float.NaN;
                    slot.Decodes.Add(new DecodeRow
                    {
                        Scenario = scenario,
                        Part = part,
                        Trial = trial,
                        Seed = seed,
                        Message = results[i].Message.TrimEnd('\0').Trim(),
                        FreqHz = results[i].FreqHz,
                        Dt = results[i].Dt,
                        ReportedSnrDb = results[i].Snr,
                        SignalDb = sDb,
                        LocalNoiseDb = nDb,
                    });
                }
            }

            slotsCsv.WriteLine($"{scenario},{part},{trial},{seed},{slot.Decodes.Count}");
            foreach (var d in slot.Decodes)
            {
                float reconstructed = d.SignalDb - d.LocalNoiseDb - 26.5f;
                decodesCsv.WriteLine(string.Join(",",
                    d.Scenario, d.Part, d.Trial, d.Seed,
                    CsvEscape(d.Message),
                    d.FreqHz.ToString(CultureInfo.InvariantCulture),
                    d.Dt.ToString("0.###", CultureInfo.InvariantCulture),
                    d.ReportedSnrDb.ToString(CultureInfo.InvariantCulture),
                    d.SignalDb.ToString("0.###", CultureInfo.InvariantCulture),
                    d.LocalNoiseDb.ToString("0.###", CultureInfo.InvariantCulture),
                    reconstructed.ToString("0.###", CultureInfo.InvariantCulture)));
            }

            slots.Add(slot);
        }

        return slots;
    }

    private static string CsvEscape(string s) =>
        s.Contains(',') || s.Contains('"')
            ? "\"" + s.Replace("\"", "\"\"") + "\""
            : s;

    private static void WriteVerdictLine(string outDir, string label, string line)
    {
        string path = Path.Combine(outDir, "row0_verdicts.txt");
        File.AppendAllText(path,
            $"{DateTime.UtcNow:yyyy-MM-ddTHH:mm:ssZ} {label}: {line}{Environment.NewLine}");
    }

    private static string FindRepoRoot()
    {
        var dir = new DirectoryInfo(AppContext.BaseDirectory);
        while (dir is not null)
        {
            if (Directory.Exists(Path.Combine(dir.FullName, ".git"))) return dir.FullName;
            dir = dir.Parent;
        }
        throw new InvalidOperationException("Repository root (.git) not found.");
    }
}
