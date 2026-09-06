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
/// `AWGN-FP` Amendment 3, A3.2 — ROW 0r: does the M1 S5 AWGN false-accept population's decode set
/// survive the <c>20260049</c>→<c>20260050</c> shim bump (<c>ac6150d</c>, `F-001` L3 export)?
/// <para>
/// Spec: <c>qa/rr-study/2026-09-02-1906-architect-to-qa-spec-awgn-fp-offline-replay.md</c>
/// Amendment 3 A3.2, operationalised by
/// <c>qa/rr-study/2026-09-04-1322-architect-to-qa-execution-pack-post-shim-bump.md</c> block P2.
/// </para>
/// <para>
/// <b>Why this is a separate file, not a new Fact appended to <see cref="AwgnFpReplayTests"/>:</b>
/// that class's own <c>AssertBinaryPin</c> hard-codes and re-asserts the <c>20260049</c> SHA256 on
/// every Fact (HK-021(p), "every row is void if the binary pin does not hold") — AWGN-FP Amendment
/// 3 Ruling 1 ("the pin moves behind its existing trait; it is NOT re-pinned") requires that pin
/// to keep meaning exactly "the identity of every already-landed row" forever. This Fact runs
/// against the CURRENT (<c>20260050</c>) binary on purpose, so it cannot share that assertion or
/// that class without corrupting its historical meaning — hence a new, separate class.
/// </para>
/// <para>
/// <b>A structural finding, disclosed rather than worked around silently:</b> <see cref="Ft8LibInterop"/>'s
/// ABI self-test (<c>ExpectedShimVersion</c>, currently <c>20260050</c>) is a hard-coded constant
/// baked into whichever assembly is running. There is no way to decode with the OLD (<c>20260049</c>)
/// binary from a build of the CURRENT source tree — the resolver loads the DLL fine, but
/// <c>LoadAndVerify</c> throws on the version mismatch before any decode call is reachable. Getting
/// a live decode pass against the old binary would require a second checkout/build (e.g. a git
/// worktree at the commit before the bump) — out of proportion for a carry-forward check when the
/// EXACT decode output ROW 0r needs to compare against already exists, tracked in git, from the
/// <c>4a7fb3d</c> run that produced it under the pinned <c>20260049</c> binary (that run's own ROW
/// 0a passed at the time; confirmed byte-identical since via
/// <c>git diff --stat 4a7fb3d HEAD -- .../m1m4_s5_decodes.csv .../m1m4_s5_slots.csv</c>, empty).
/// This Fact therefore supplies only the CURRENT-binary half of the comparison; the diff against
/// the preserved <c>20260049</c> CSVs is done by
/// <c>qa/rr-study/fp-parity/row0r_carry_forward.py</c>, which also re-verifies the old binary's
/// SHA256 as a real artefact per A3.2 step 1-2 before treating those CSVs as trustworthy.
/// </para>
/// </summary>
[Trait("Category", "AwgnFpReplay")]
public sealed class Row0rCarryForwardTests
{
    private readonly ITestOutputHelper _out;

    public Row0rCarryForwardTests(ITestOutputHelper output) => _out = output;

    // Current win-x64 SHA256 as of the F-001 L3 export (ac6150d, shim 20260050) --
    // src/OpenWSFZ.Ft8/Native/win-x64/libft8.version.txt. Asserted here (not re-derived from the
    // manifest text) so this Fact fails loudly if a future shim bump lands without updating it --
    // ROW 0r must always be re-run against whichever binary is actually loaded (AWGN-FP A3.3).
    private const string PinnedShaWinX64_20260050 =
        "6b2e16a6991ae953d18c85e5f0fea99d1e003c84b90ae5a69a8f1cfade34f85c";

    private static readonly Regex SlotFileNameRe =
        new(@"^(?<scenario>[A-Za-z0-9]+)_p(?<part>\d+)_t(?<trial>\d+)_s(?<seed>\d+)\.wav$",
            RegexOptions.Compiled);

    [Fact(DisplayName = "ROW 0r: decode the M1 S5 AWGN population on the CURRENT (20260050) binary for carry-forward diffing")]
    public void Row0r_M1S5Population_DecodeOnCurrentBinary()
    {
        string dllPath = Path.Combine(AppContext.BaseDirectory, "libft8.dll");
        File.Exists(dllPath).Should().BeTrue($"the native binary under test must be present at '{dllPath}'");
        string actualSha = ComputeSha256(dllPath);
        _out.WriteLine($"ROW 0r: loaded binary  = {dllPath}");
        _out.WriteLine($"ROW 0r: actual  SHA256 = {actualSha}");
        _out.WriteLine($"ROW 0r: current SHA256 = {PinnedShaWinX64_20260050}");
        actualSha.Should().Be(PinnedShaWinX64_20260050,
            "ROW 0r must record which binary it actually ran against; a mismatch here means the " +
            "committed win-x64 DLL moved without this Fact's own record being updated (A3.3: ROW 0r " +
            "re-runs for every shim bump the arm spans)");

        string root = Path.Combine(FindRepoRoot(), "qa", "rr-study", "awgn-fp-replay");
        string wavDir = Path.Combine(root, "_work", "m1m4_s5");
        string outDir = Path.Combine(FindRepoRoot(), "qa", "rr-study", "fp-parity", "results");
        Directory.CreateDirectory(outDir);

        // Deliberately DIFFERENT filenames from AwgnFpReplayTests' own "m1m4_s5_{slots,decodes}.csv"
        // so the preserved 20260049 evidence (tracked in git since 4a7fb3d) is never at risk of
        // being overwritten by this run.
        var slots = DecodeDirectory(wavDir, outDir, "m1m4_s5_20260050");

        slots.Should().HaveCount(4000, "same population ROW 0r must cover in full, per A3.2 step 3 -- no sampling, no truncation");

        int events = slots.Count(s => s.Decodes.Count > 0);
        int decodeRows = slots.Sum(s => s.Decodes.Count);
        _out.WriteLine($"ROW 0r (20260050): slots={slots.Count} events(>=1 decode)={events} decode_rows={decodeRows}");

        slots.Should().OnlyContain(s => s.Decodes.Count >= 0);
    }

    // ── Decode/report machinery, deliberately mirroring AwgnFpReplayTests.DecodeDirectory's
    //    process configuration exactly (same SetApBits([],[]) clear, same DecodeAll call, no
    //    NormalisePcm -- that repair is ROW 0n, explicitly out of this row's scope per the
    //    execution pack's P2/P3 split) so this is a same-process-configuration comparison, not a
    //    different harness. Duplicated rather than shared to avoid touching AwgnFpReplayTests.cs
    //    at all (AWGN-FP A3.2/A3.1: nothing about that file's already-landed rows may change). ──

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

    private static string ComputeSha256(string path)
    {
        using var stream = File.OpenRead(path);
        byte[] hash = SHA256.HashData(stream);
        var sb = new StringBuilder(hash.Length * 2);
        foreach (byte b in hash) sb.Append(b.ToString("x2"));
        return sb.ToString();
    }

    private static List<SlotResult> DecodeDirectory(string wavDir, string outDir, string label)
    {
        Directory.Exists(wavDir).Should().BeTrue($"rendered WAV directory must exist: '{wavDir}'");
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
