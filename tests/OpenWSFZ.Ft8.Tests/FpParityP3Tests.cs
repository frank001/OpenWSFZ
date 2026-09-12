using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Config;
using OpenWSFZ.Ft8.Interop;
using Xunit;
using Xunit.Abstractions;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// `FP-PARITY` Amendment 3 (P3) — decode-param parity (ROW 0o), path identity and the
/// <c>20260050</c> binary pin (ROW 0p), and the normalisation paired re-decode (ROW 0n / ROW 0n-C).
/// <para>
/// Spec: <c>qa/rr-study/2026-09-06-0951-architect-to-qa-spec-fp-parity-p3-normalisation-and-param-parity.md</c>
/// — "<c>FP-PARITY</c> Amendment 3", a document distinct from <c>AWGN-FP</c>'s own A3.1–A3.4
/// (that spec's own numbering-collision note applies: name the spec when citing any A3.x).
/// </para>
/// <para>
/// <b>Why a new class, not a Fact on <see cref="AwgnFpReplayTests"/> or <see cref="Row0rCarryForwardTests"/>:</b>
/// following the <c>Row0rCarryForwardTests.cs</c> precedent exactly — a parallel class, its own
/// pin (<see cref="PinnedShaWinX64"/>, a NEW literal computed independently by QA), the two
/// existing landed classes and their historical pins untouched. Spec §0.2 A3.1 ruling: P3 runs on
/// <c>20260050</c>, and <c>AwgnFpReplayTests.PinnedShaWinX64</c> (the <c>20260049</c> identity of
/// every already-landed row, <c>AWGN-FP</c> A3.1) is not to be touched a second time.
/// </para>
/// <para>
/// <b>Clobber guard (spec §3.2, MANDATORY):</b> every output path is asserted <i>untracked</i> by
/// git (<see cref="AssertPathUntracked"/>) before any file is opened. Writes go only to
/// <c>qa/rr-study/fp-parity/_out/</c> (gitignored) — never to <c>fp-parity/results/</c>, which is
/// where an unfiltered <c>AwgnFpReplayTests</c> run clobbered 12 redaction-mapped committed CSVs
/// twice in one day on 2026-09-06. Promotion into <c>results/</c> is a separate, deliberate
/// redact-then-rescan-then-commit step — never this fixture's own write.
/// </para>
/// <para>
/// <b>No HK-011 cycle</b> (spec §3.1): <see cref="Ft8Decoder.NormalisePcm"/> is <c>internal static</c>
/// and <c>[assembly: InternalsVisibleTo("OpenWSFZ.Ft8.Tests")]</c> is already present
/// (<c>src/OpenWSFZ.Ft8/AssemblyAttributes.cs:3</c>) — zero <c>src/</c>/<c>native/</c> diff, no
/// Developer session needed for this file.
/// </para>
/// <para>
/// <b>ROW 0o meaning change (<c>NHARD40-DEFAULT</c>, 2026-09-12, <c>dev-tasks/2026-09-12-
/// nhard40-default-migration.md</c>):</b> ROW 0o now asserts parity against 40, not 60. It reads
/// the config file directly via <see cref="ReadLiveEffectiveDecoderConfig"/>
/// (<c>ConfigPathResolver.ResolvePath()</c>), bypassing <c>JsonConfigStore</c>'s migration
/// entirely, so it will legitimately FIRE on any machine whose <c>config.json</c> still has an
/// un-migrated explicit <c>osdNhardMax: 60</c> — that is not a test bug, it is ROW 0o doing its
/// job. Re-run <c>pre_merge_check.py</c>'s own gate list is unaffected; this is a QA-owned
/// measurement test, not a merge gate (HK-006).
/// </para>
/// </summary>
[Trait("Category", "RequiresNativeBinary")]
[Trait("Category", "AwgnFpReplay")]
public sealed class FpParityP3Tests
{
    private readonly ITestOutputHelper _out;

    public FpParityP3Tests(ITestOutputHelper output) => _out = output;

    // ── ROW 0p pin — win-x64 SHA256 for the 20260050 shim, computed by QA directly from
    //    src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll at main@1b7ca29 (git show 1b7ca29:<path> |
    //    sha256sum) and independently cross-checked with
    //    `python tools/check_native_version.py <path> 20260050` -> "OK, shim version 20260050".
    //    NOT copied from any document — spec §4 ROW 0p states no value on purpose. A NEW literal
    //    in a NEW class: AwgnFpReplayTests.PinnedShaWinX64 (the 20260049 identity) is untouched. ──
    private const string PinnedShaWinX64 =
        "6b2e16a6991ae953d18c85e5f0fea99d1e003c84b90ae5a69a8f1cfade34f85c";

    // ── ROW 0n-C — the standing false-accept ceiling T = C + 1.0, C = +1.622 dB (offline,
    //    un-normalised, 20260049; FP-PARITY §1.3 / P2). FIRES iff any normalised-leg false accept
    //    exceeds this — meaning T must be re-derived before P4b runs at all. ──
    private const float RowNCCeilingDb = 2.622f;

    // ── §3.3 drift-sanity literal only. The value actually passed to NormalisePcm below is read
    //    by reflection from Ft8Decoder's own private const, never this literal — hard-coding would
    //    let production drift away from the parity run silently (HK-022). This constant exists so
    //    that drift trips a loud, named assertion here instead. ──
    private const float ExpectedTargetRmsToday = 0.20f;

    private static readonly Regex SlotFileNameRe =
        new(@"^(?<scenario>[A-Za-z0-9]+)_p(?<part>\d+)_t(?<trial>\d+)_s(?<seed>\d+)\.wav$",
            RegexOptions.Compiled);

    // ── ROW 0p — path identity and the 20260050 binary pin. No decode. ─────────────────

    [Fact(DisplayName = "ROW 0p: 20260050 binary pin + path identity (180,000 samples/slot, no resample/DC-removal) — before any decode")]
    public void Row0p_PathIdentityAndBinaryPin()
    {
        string dllPath = Path.Combine(AppContext.BaseDirectory, "libft8.dll");
        File.Exists(dllPath).Should().BeTrue($"the native binary under test must be present at '{dllPath}'");

        string actualSha = ComputeSha256(dllPath);
        _out.WriteLine($"ROW 0p: loaded binary = {dllPath}");
        _out.WriteLine($"ROW 0p: actual SHA256 = {actualSha}");
        _out.WriteLine($"ROW 0p: pinned SHA256 = {PinnedShaWinX64}  " +
                        "(QA-computed from main@1b7ca29; cross-checked via tools/check_native_version.py -> shim 20260050 OK)");
        actualSha.Should().Be(PinnedShaWinX64,
            "ROW 0p FIRES on any mismatch -> STOP, the instrument is not the one P3 specified");

        string wavDir = Path.Combine(FindRepoRoot(), "qa", "rr-study", "awgn-fp-replay", "_work", "m1m4_s5");
        Directory.Exists(wavDir).Should().BeTrue($"P3's population must exist: '{wavDir}'");

        var files = Directory.GetFiles(wavDir, "*.wav")
            .Where(f => SlotFileNameRe.IsMatch(Path.GetFileName(f)))
            .ToList();
        files.Should().HaveCount(4000, "P3 runs over the full, identical 4,000-WAV population ROW 0r used");

        // 180,000 samples/slot, no resample, no DC removal: WavReader.cs is a pure int16 -> float
        // conversion (cited, not re-implemented here) — reading every file without decoding
        // verifies the population contract itself before any native call is reachable.
        int wrongLength = files.Count(f => WavReader.Read(f).Length != 180_000);
        _out.WriteLine($"ROW 0p: files scanned = {files.Count}, files NOT exactly 180,000 samples = {wrongLength}");
        wrongLength.Should().Be(0,
            "ROW 0p asserts 180,000 samples/slot with no silent padding — a short/long WAV means " +
            "the population itself has drifted from the render contract");
    }

    // ── ROW 0o — decode-param parity. No decode; compares config, not output. ─────────
    //
    // NHARD40-DEFAULT (2026-09-12): asserts parity against the new code default (40), not
    // the retired 60. Reads the raw config file directly (ReadLiveEffectiveDecoderConfig),
    // bypassing JsonConfigStore's migration, so it legitimately FIRES on any machine whose
    // config.json still has an un-migrated explicit osdNhardMax: 60 — that is not a test
    // bug, it is ROW 0o doing its job (see the class doc comment above for the full
    // disclosure). Re-run pre_merge_check.py's own gate list is unaffected; this is a
    // QA-owned measurement test, not a merge gate (HK-006).

    [Fact(DisplayName = "ROW 0o: decode-param parity — offline seam configured identically to production's effective values (nhard default 40, NHARD40-DEFAULT 2026-09-12)")]
    public void Row0o_DecodeParamParity()
    {
        var (k, corr, nhard, keyPresent) = ReadLiveEffectiveDecoderConfig(out string configPath);
        var codeDefault = new DecoderConfig();

        _out.WriteLine($"ROW 0o: config path = {configPath} (exists={File.Exists(configPath)})");
        _out.WriteLine($"ROW 0o: 'decoder' key present in config.json = {keyPresent}");
        _out.WriteLine($"ROW 0o: live-effective (K,Corr,Nhard)          = ({k}, {corr}, {nhard})");
        _out.WriteLine($"ROW 0o: DecoderConfig() code default (K,Corr,Nhard) = " +
                        $"({codeDefault.KMinScorePass2}, {codeDefault.OsdCorrThreshold}, {codeDefault.OsdNhardMax})");

        bool fires = k != codeDefault.KMinScorePass2
                  || !corr.Equals(codeDefault.OsdCorrThreshold)
                  || nhard != codeDefault.OsdNhardMax;

        _out.WriteLine($"ROW 0o: FIRES (any of the three differs) = {fires}");
        fires.Should().BeFalse(
            "ROW 0o FIRES -> every offline absolute rate this project holds is void until re-run " +
            "at parity, including 10.875% (nhard=60, pre-NHARD40-DEFAULT), ROW 0s's baseline, and " +
            "ROW 0n's. STOP; do not re-run first and report second.");
    }

    // ── ROW 0n + ROW 0n-C — the one paired, normalised re-decode. ───────────────────────

    [Fact(DisplayName = "ROW 0n + ROW 0n-C: normalised paired re-decode of the M1 S5 population (N=4,000) under the production input contract")]
    public void Row0n_NormalisedPairedDecode_And_Row0nC_FalseAcceptCeiling()
    {
        // Re-assert ROW 0p's pin — HK-021(p): every row is void without it, independent of
        // xunit's own (undefined) intra-class ordering.
        string dllPath = Path.Combine(AppContext.BaseDirectory, "libft8.dll");
        ComputeSha256(dllPath).Should().Be(PinnedShaWinX64, "HK-021(p): this Fact is void if the pin does not hold");

        // Re-assert ROW 0o's parity and obtain the values that actually drive this decode.
        var (k, corr, nhard, _) = ReadLiveEffectiveDecoderConfig(out _);
        var codeDefault = new DecoderConfig();
        bool row0oFires = k != codeDefault.KMinScorePass2
                       || !corr.Equals(codeDefault.OsdCorrThreshold)
                       || nhard != codeDefault.OsdNhardMax;
        row0oFires.Should().BeFalse("ROW 0o must not fire before this Fact decodes anything");
        Ft8LibInterop.SetDecodeParams(k, corr, nhard);

        // §3.3 — read the production target RMS by reflection; never hard-code it.
        FieldInfo? field = typeof(Ft8Decoder).GetField(
            "PcmNormalisationTargetRms", BindingFlags.NonPublic | BindingFlags.Static);
        field.Should().NotBeNull("Ft8Decoder.PcmNormalisationTargetRms must exist as a private static const");
        float targetRms = (float)field!.GetRawConstantValue()!;
        _out.WriteLine($"ROW 0n: NormalisePcm target RMS (read by reflection) = {targetRms}");
        targetRms.Should().Be(ExpectedTargetRmsToday,
            "drift sanity check (HK-022): if production's target RMS has moved since this literal " +
            "was written, that is itself a finding to report, not something to silently absorb");

        string repoRoot = FindRepoRoot();
        string wavDir = Path.Combine(repoRoot, "qa", "rr-study", "awgn-fp-replay", "_work", "m1m4_s5");
        string outDir = Path.Combine(repoRoot, "qa", "rr-study", "fp-parity", "_out");
        Directory.CreateDirectory(outDir);

        string slotsCsvPath = Path.Combine(outDir, "p3_norm_slots.csv");
        string decodesCsvPath = Path.Combine(outDir, "p3_norm_decodes.csv");

        // MANDATORY clobber guard (spec §3.2): every output path asserted untracked BEFORE any
        // file is opened. A guard that runs after the write is not a guard.
        AssertPathUntracked(repoRoot, slotsCsvPath);
        AssertPathUntracked(repoRoot, decodesCsvPath);

        var files = Directory.GetFiles(wavDir, "*.wav")
            .Select(f => (path: f, name: Path.GetFileName(f)))
            .Where(x => SlotFileNameRe.IsMatch(x.name))
            .OrderBy(x => x.name, StringComparer.Ordinal)
            .ToList();
        files.Should().HaveCount(4000, "N=4,000, pre-registered before any normalised decode exists (spec §1.2)");

        using var slotsCsv = new StreamWriter(slotsCsvPath, append: false, Encoding.UTF8);
        using var decodesCsv = new StreamWriter(decodesCsvPath, append: false, Encoding.UTF8);
        slotsCsv.WriteLine("scenario,part,trial,seed,n_decodes");
        decodesCsv.WriteLine("scenario,part,trial,seed,message,freq_hz,dt_s,reported_snr_db,signal_db,local_noise_db");

        int decodeAllCalls = 0;
        int slotCount = 0;

        foreach (var (path, name) in files)
        {
            var m = SlotFileNameRe.Match(name);
            string scenario = m.Groups["scenario"].Value;
            int part = int.Parse(m.Groups["part"].Value, CultureInfo.InvariantCulture);
            int trial = int.Parse(m.Groups["trial"].Value, CultureInfo.InvariantCulture);
            long seed = long.Parse(m.Groups["seed"].Value, CultureInfo.InvariantCulture);

            float[] pcm = WavReader.Read(path);
            pcm.Length.Should().Be(180_000, $"ROW 0p already asserted this population is exactly 180,000 samples/slot: '{name}'");

            float[] normalised = Ft8Decoder.NormalisePcm(pcm, targetRms);

            Ft8LibInterop.SetApBits([], []);   // AP-bits-cleared-before-every-decode invariant (ROW 0p)
            Ft8NativeResult[] results = Ft8LibInterop.DecodeAll(normalised);
            decodeAllCalls++;                  // exactly-one-DecodeAll-per-slot invariant (ROW 0p)
            slotCount++;

            int nDecodes = results.Length;
            slotsCsv.WriteLine($"{scenario},{part},{trial},{seed},{nDecodes}");

            if (nDecodes > 0)
            {
                var (signalDb, localNoiseDb) = Ft8LibInterop.GetLastSnrTerms(nDecodes);
                for (int i = 0; i < nDecodes; i++)
                {
                    float sDb = i < signalDb.Length ? signalDb[i] : float.NaN;
                    float nDb = i < localNoiseDb.Length ? localNoiseDb[i] : float.NaN;
                    decodesCsv.WriteLine(string.Join(",",
                        scenario, part, trial, seed,
                        CsvEscape(results[i].Message.TrimEnd('\0').Trim()),
                        results[i].FreqHz.ToString(CultureInfo.InvariantCulture),
                        results[i].Dt.ToString("0.###", CultureInfo.InvariantCulture),
                        results[i].Snr.ToString(CultureInfo.InvariantCulture),
                        sDb.ToString("0.###", CultureInfo.InvariantCulture),
                        nDb.ToString("0.###", CultureInfo.InvariantCulture)));
                }
            }
        }

        decodeAllCalls.Should().Be(slotCount, "ROW 0p: exactly one DecodeAll per slot");
        slotCount.Should().Be(4000);

        _out.WriteLine($"ROW 0n: wrote {slotsCsvPath}");
        _out.WriteLine($"ROW 0n: wrote {decodesCsvPath}");
        _out.WriteLine($"ROW 0n: slots={slotCount} (normalised leg; the un-normalised leg is ROW 0r's " +
                        "already-committed qa/rr-study/fp-parity/results/m1m4_s5_20260050_slots.csv, asserted by ROW 0s)");
        _out.WriteLine($"ROW 0n-C: ceiling T = {RowNCCeilingDb} dB (= C + 1.0, C = +1.622 dB, offline un-normalised 20260049) " +
                        "— excess distribution computed by the paired analysis step over this decodes CSV's signal_db/local_noise_db columns");

        // Mechanical sanity only — ROW 0n's McNemar verdict and ROW 0n-C's ceiling check are
        // computed by the paired analysis step (qa/rr-study/fp-parity/p3_parity.py), which joins
        // this file against ROW 0s's baseline and is not duplicated here in C# (HK-025/§4).
        slotCount.Should().BeGreaterThan(0);
    }

    // ── Shared machinery ─────────────────────────────────────────────────────────────

    private static (int K, float Corr, int Nhard, bool KeyPresent) ReadLiveEffectiveDecoderConfig(out string configPath)
    {
        configPath = ConfigPathResolver.ResolvePath();
        var fallback = new DecoderConfig();
        if (!File.Exists(configPath))
            return (fallback.KMinScorePass2, fallback.OsdCorrThreshold, fallback.OsdNhardMax, false);

        using var doc = JsonDocument.Parse(File.ReadAllText(configPath));
        if (!doc.RootElement.TryGetProperty("decoder", out var decoderEl)
            || decoderEl.ValueKind is JsonValueKind.Null or JsonValueKind.Undefined)
        {
            return (fallback.KMinScorePass2, fallback.OsdCorrThreshold, fallback.OsdNhardMax, false);
        }

        int k = decoderEl.TryGetProperty("kMinScorePass2", out var kEl) ? kEl.GetInt32() : fallback.KMinScorePass2;
        float corr = decoderEl.TryGetProperty("osdCorrThreshold", out var cEl) ? cEl.GetSingle() : fallback.OsdCorrThreshold;
        int nhard = decoderEl.TryGetProperty("osdNhardMax", out var nEl) ? nEl.GetInt32() : fallback.OsdNhardMax;
        return (k, corr, nhard, true);
    }

    /// <summary>
    /// MANDATORY clobber guard (spec §3.2): throws before any file at <paramref name="absolutePath"/>
    /// is opened for writing if that path is currently tracked by git. A guard that runs after the
    /// write is not a guard.
    /// </summary>
    private static void AssertPathUntracked(string repoRoot, string absolutePath)
    {
        string relative = Path.GetRelativePath(repoRoot, absolutePath).Replace('\\', '/');
        var psi = new ProcessStartInfo("git")
        {
            WorkingDirectory = repoRoot,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
        };
        psi.ArgumentList.Add("ls-files");
        psi.ArgumentList.Add("--error-unmatch");
        psi.ArgumentList.Add(relative);

        using var proc = Process.Start(psi)!;
        proc.WaitForExit();

        // Exit code 0 => git recognises the path as tracked => the guard must fire.
        (proc.ExitCode == 0).Should().BeFalse(
            $"clobber guard (spec §3.2): output path '{relative}' is TRACKED by git — " +
            "FpParityP3Tests may not write to any tracked results path, checked before any file is opened.");
    }

    private static string ComputeSha256(string path)
    {
        using var stream = File.OpenRead(path);
        byte[] hash = SHA256.HashData(stream);
        var sb = new StringBuilder(hash.Length * 2);
        foreach (byte b in hash) sb.Append(b.ToString("x2"));
        return sb.ToString();
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
