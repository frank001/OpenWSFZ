using System.Diagnostics;
using System.Threading.Channels;
using Microsoft.Extensions.Logging.Abstractions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon;
using OpenWSFZ.Ft8;
using OpenWSFZ.Web;

namespace DCaller020WorkingCqFalseAbortVerify;

/// <summary>
/// Standalone, manually-run live verification tool for D-CALLER-020 (see the README in this
/// directory, and <c>dev-tasks/2026-07-14-working-cq-false-abort.md</c> §5). Not part of
/// <c>OpenWSFZ.slnx</c> and not exercised by <c>dotnet test</c> — run it explicitly with
/// <c>dotnet run -c Release</c> from this directory.
///
/// <para>
/// Reproduces the field defect: <c>QsoAnswererService.HandleWaitReportAsync</c> and
/// <c>QsoCallerService.HandleWaitRr73Async</c> used to abort the QSO the instant they decoded
/// <em>any</em> message from the partner not addressed to us — including the partner simply
/// re-transmitting their own CQ because they hadn't decoded us yet. The fix narrows the abort
/// condition to exclude <c>dest == "CQ"</c>, falling through to the existing retry/watchdog
/// backstop instead.
/// </para>
///
/// <para>
/// This tool proves the fix against genuinely synthesised-and-decoded FT8 audio — two separate
/// renders of the partner's own CQ (<c>qa/rr-study/synth_wav.py</c>, fresh every run, different
/// seeds so the two renders are not byte-identical) decoded by the real, unmocked
/// <see cref="Ft8Decoder"/> (a genuine P/Invoke call into <c>libft8</c>) — fed into the real,
/// unmodified <see cref="QsoAnswererService"/>/<see cref="QsoCallerService"/> production classes,
/// not hand-authored <see cref="DecodeResult"/> strings as the unit tests use. A genuine
/// third-party message is also decoded and fed in as a control, proving the genuine-abort path
/// (AC-2/AC-4 in the dev-task) still fires correctly and was not disabled by the fix.
/// </para>
/// </summary>
internal static class Program
{
    private const string OurCallsign  = "Q1OFZ";
    private const string OurGrid      = "JO33";
    private const string PartnerCall  = "Q1TST";
    private const string PartnerGrid  = "JO22";
    // NB: must be a real-callsign-grammar-compressible token (digit at index 1, length <= 5)
    // for the synthesiser/decoder round-trip — "Q2OTHER" (7 chars) doesn't compress and decodes
    // back as a hashed "<...>" placeholder instead of the literal text, unlike the unit tests'
    // hand-authored DecodeResult strings which skip real FT8 packing entirely.
    private const string ThirdParty   = "Q2OTR";

    // Partner's CQ — rendered twice (different seeds/freq-jitter-free but distinct synth runs) to
    // stand in for "partner calling CQ", then "partner calling CQ again a cycle later" — the
    // exact field sequence from logs/openswfz-20260714T171230Z.log.
    private const string CqMessage         = $"CQ {PartnerCall} {PartnerGrid}";
    // Partner responding directly to our own CQ (used to drive the caller side into WaitRr73).
    private const string RespToUsMessage   = $"{OurCallsign} {PartnerCall} {PartnerGrid}";
    // Partner genuinely addressing a different, real station — the case that must still abort.
    private const string ThirdPartyMessage = $"{ThirdParty} {PartnerCall} +03";

    private static async Task<int> Main()
    {
        Console.WriteLine("D-CALLER-020 — working-CQ false-abort live verification");
        Console.WriteLine("=========================================================");
        Console.WriteLine();

        var failures = new List<string>();

        try
        {
            var repoRoot = FindRepoRoot();
            var workDir  = Path.Combine(Path.GetTempPath(), "d-caller-020-verify-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(workDir);

            try
            {
                // ── Step 1: synthesise three real FT8 signals, fresh, every run ─────────────
                Console.WriteLine("[1/3] Synthesising FT8 signals via qa/rr-study/synth_wav.py ...");
                string cqWav1    = Path.Combine(workDir, "cq_1.wav");
                string cqWav2    = Path.Combine(workDir, "cq_2.wav");
                string respWav   = Path.Combine(workDir, "resp.wav");
                string thirdWav  = Path.Combine(workDir, "third.wav");

                await RunSynthWavAsync(repoRoot, CqMessage,         freqHz: 800, seed: 1, outPath: cqWav1);
                await RunSynthWavAsync(repoRoot, CqMessage,         freqHz: 800, seed: 7, outPath: cqWav2);
                await RunSynthWavAsync(repoRoot, RespToUsMessage,   freqHz: 800, seed: 3, outPath: respWav);
                await RunSynthWavAsync(repoRoot, ThirdPartyMessage, freqHz: 800, seed: 5, outPath: thirdWav);
                Console.WriteLine("      wrote 4 WAVs (CQ x2 distinct renders, response-to-us, third-party).");

                // ── Step 2: decode each with the REAL native decoder ────────────────────────
                Console.WriteLine("[2/3] Decoding all four with the real Ft8Decoder (libft8 P/Invoke) ...");
                var clock = new FixedClock(new DateTime(2026, 7, 14, 12, 0, 0, DateTimeKind.Utc));

                var cqDecode1    = await DecodeOneAsync(clock, cqWav1,   CqMessage,         failures, "CQ (1st render)");
                var cqDecode2    = await DecodeOneAsync(clock, cqWav2,   CqMessage,         failures, "CQ (2nd render — the re-transmission)");
                var respDecode   = await DecodeOneAsync(clock, respWav, RespToUsMessage,    failures, "response to us");
                var thirdDecode  = await DecodeOneAsync(clock, thirdWav, ThirdPartyMessage, failures, "third-party message");

                if (failures.Count > 0) { Report(failures); return 1; }

                Console.WriteLine($"      CQ (1st):        {cqDecode1!.Message}");
                Console.WriteLine($"      CQ (2nd/re-tx):   {cqDecode2!.Message}");
                Console.WriteLine($"      response-to-us:  {respDecode!.Message}");
                Console.WriteLine($"      third-party:     {thirdDecode!.Message}");

                // ── Step 3: drive the real services ──────────────────────────────────────────
                Console.WriteLine("[3/3] Driving real QsoAnswererService / QsoCallerService with the decoded batches:");
                await RunAnswererScenarioAsync(cqDecode1, cqDecode2, thirdDecode, failures);
                await RunCallerScenarioAsync(respDecode, cqDecode2, thirdDecode, failures);
            }
            finally
            {
                try { Directory.Delete(workDir, recursive: true); } catch { /* best-effort cleanup */ }
            }
        }
        catch (Exception ex)
        {
            failures.Add($"Unhandled exception: {ex}");
        }

        Report(failures);
        return failures.Count == 0 ? 0 : 1;
    }

    // ── Decode helper ────────────────────────────────────────────────────────────────────────

    private static async Task<DecodeResult?> DecodeOneAsync(
        IClock clock, string wavPath, string expectedMessage, List<string> failures, string label)
    {
        float[] pcm = ReadMono16BitWav(wavPath, expectedSampleRateHz: 12_000);

        var decoder = new Ft8Decoder(clock, logger: null, grammarStore: null, regionStore: null, workedBeforeIndex: null);
        IReadOnlyList<DecodeResult> decoded = await decoder.DecodeAsync(pcm, clock.UtcNow, CancellationToken.None);
        var messages = decoded.Select(r => r.Message).ToList();

        Check(failures, messages.Contains(expectedMessage),
            $"{label}: real decoder must recover '{expectedMessage}'. Decoded: [{string.Join(", ", messages)}]");

        return decoded.FirstOrDefault(r => r.Message == expectedMessage);
    }

    // ── QsoAnswererService scenario ──────────────────────────────────────────────────────────

    private static async Task RunAnswererScenarioAsync(
        DecodeResult cq1, DecodeResult cq2, DecodeResult third, List<string> failures)
    {
        const string label = "QsoAnswererService";

        var ptt = new RecordingPttController();
        var configStore = new SimpleConfigStore(new AppConfig() with
        {
            Tx = new TxConfig { AutoAnswer = true, Callsign = OurCallsign, Grid = OurGrid, RetryCount = 2, WatchdogMinutes = 4 },
        });
        var adifLog = new AdifLogWriter(configStore, NullLogger<AdifLogWriter>.Instance);
        var channel = Channel.CreateUnbounded<DecodeBatch>();

        var sut = new QsoAnswererService(
            channel.Reader, configStore, ptt, new TxEventBus(),
            adifLog, new AudioOffsetEventBus(), NullLogger<QsoAnswererService>.Instance,
            decoder: null, catState: null, decodeFilterStore: null);

        var stopCts = new CancellationTokenSource();
        await sut.StartAsync(stopCts.Token);

        try
        {
            // Engage on the partner's CQ.
            channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow, [cq1]));
            bool engaged = await WaitForStateAsync(sut, QsoState.WaitReport, TimeSpan.FromSeconds(5));
            Check(failures, engaged, $"[{label}] expected WaitReport after engaging partner's CQ; actual state {sut.State}.");
            Check(failures, sut.Partner == PartnerCall, $"[{label}] expected partner '{PartnerCall}'; actual '{sut.Partner ?? "(none)"}'.");
            Console.WriteLine(engaged && sut.Partner == PartnerCall
                ? $"      OK  [{label,-20}] engaged {sut.Partner}, state = WaitReport"
                : $"      FAIL[{label,-20}] engage failed — state = {sut.State}, partner = {sut.Partner ?? "(none)"}");

            // D-CALLER-020: partner re-transmits their own CQ instead of answering — must NOT abort.
            channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow, [cq2]));
            await Task.Delay(400);
            bool stillWaiting = sut.State == QsoState.WaitReport;
            Check(failures, stillWaiting,
                $"[{label}] D-CALLER-020 regression: partner re-transmitting their own CQ must not abort the QSO; actual state {sut.State}.");
            Console.WriteLine(stillWaiting
                ? $"      OK  [{label,-20}] partner's own CQ re-transmission did NOT abort — still WaitReport"
                : $"      FAIL[{label,-20}] partner's own CQ re-transmission caused an abort — state = {sut.State}");

            // Control: a genuine third-party message must still abort immediately (AC-2).
            channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow, [third]));
            bool aborted = await WaitForStateAsync(sut, QsoState.Idle, TimeSpan.FromSeconds(5));
            Check(failures, aborted,
                $"[{label}] control case: partner addressing a genuine third station must still abort; actual state {sut.State}.");
            Console.WriteLine(aborted
                ? $"      OK  [{label,-20}] genuine third-party message still aborts to Idle (AC-2 unaffected)"
                : $"      FAIL[{label,-20}] genuine third-party message did not abort — state = {sut.State}");
        }
        finally
        {
            await stopCts.CancelAsync();
            await sut.StopAsync(CancellationToken.None);
            await ptt.DisposeAsync();
        }
    }

    // ── QsoCallerService scenario ────────────────────────────────────────────────────────────

    private static async Task RunCallerScenarioAsync(
        DecodeResult respToUs, DecodeResult cqReTx, DecodeResult third, List<string> failures)
    {
        const string label = "QsoCallerService";

        var ptt = new RecordingPttController();
        var configStore = new SimpleConfigStore(new AppConfig() with
        {
            Tx = new TxConfig
            {
                AutoAnswer          = true,
                Callsign            = OurCallsign,
                Grid                = OurGrid,
                CallerPartnerSelect = CallerPartnerSelectMode.First,
                RetryCount          = 2,
                WatchdogMinutes     = 4,
            },
        });
        var adifLog = new AdifLogWriter(configStore, NullLogger<AdifLogWriter>.Instance);
        var channel = Channel.CreateUnbounded<DecodeBatch>();

        var sut = new QsoCallerService(
            channel.Reader, configStore, ptt, new TxEventBus(),
            adifLog, new AudioOffsetEventBus(), NullLogger<QsoCallerService>.Instance,
            decoder: null, catState: null, decodeFilterStore: null);

        var stopCts = new CancellationTokenSource();
        await sut.StartAsync(stopCts.Token);

        try
        {
            // Prime into WaitAnswer (WaitReport) with an irrelevant decode so our own CQ TX fires,
            // exactly mirroring QsoCallerServiceTests' own priming step.
            channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
                [new DecodeResult(Time: "12:00:00", Snr: -5, Dt: 0.1, FreqHz: 800, Message: "CQ Q2NOISE JO00")]));
            bool primed = await WaitForStateAsync(sut, QsoState.WaitReport, TimeSpan.FromSeconds(5));
            Check(failures, primed, $"[{label}] failed to reach WaitAnswer during priming.");

            // Partner responds to our CQ — advances TxReport → WaitRr73.
            channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow, [respToUs]));
            bool inWaitRr73 = await WaitForStateAsync(sut, QsoState.WaitRr73, TimeSpan.FromSeconds(5));
            Check(failures, inWaitRr73, $"[{label}] expected WaitRr73 after partner's response; actual state {sut.State}.");
            Check(failures, sut.Partner == PartnerCall, $"[{label}] expected partner '{PartnerCall}'; actual '{sut.Partner ?? "(none)"}'.");
            Console.WriteLine(inWaitRr73 && sut.Partner == PartnerCall
                ? $"      OK  [{label,-20}] partner {sut.Partner} responded, state = WaitRr73"
                : $"      FAIL[{label,-20}] failed to reach WaitRr73 — state = {sut.State}, partner = {sut.Partner ?? "(none)"}");

            // D-CALLER-020: partner re-transmits their own CQ instead of sending RR73 — must NOT abort.
            channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow, [cqReTx]));
            await Task.Delay(400);
            bool stillWaiting = sut.State == QsoState.WaitRr73;
            Check(failures, stillWaiting,
                $"[{label}] D-CALLER-020 regression: partner re-transmitting their own CQ must not abort the QSO; actual state {sut.State}.");
            Console.WriteLine(stillWaiting
                ? $"      OK  [{label,-20}] partner's own CQ re-transmission did NOT abort — still WaitRr73"
                : $"      FAIL[{label,-20}] partner's own CQ re-transmission caused an abort — state = {sut.State}");

            // Control: a genuine third-party message must still abort immediately (AC-4).
            channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow, [third]));
            bool aborted = await WaitForStateAsync(sut, QsoState.Idle, TimeSpan.FromSeconds(5));
            Check(failures, aborted,
                $"[{label}] control case: partner addressing a genuine third station must still abort; actual state {sut.State}.");
            Console.WriteLine(aborted
                ? $"      OK  [{label,-20}] genuine third-party message still aborts to Idle (AC-4 unaffected)"
                : $"      FAIL[{label,-20}] genuine third-party message did not abort — state = {sut.State}");
        }
        finally
        {
            await stopCts.CancelAsync();
            await sut.StopAsync(CancellationToken.None);
            await ptt.DisposeAsync();
        }
    }

    // ── Shared wait / check / report helpers ─────────────────────────────────────────────────

    private static async Task<bool> WaitForStateAsync(QsoAnswererService svc, QsoState expected, TimeSpan timeout)
    {
        var deadline = DateTime.UtcNow + timeout;
        while (DateTime.UtcNow < deadline)
        {
            if (svc.State == expected) return true;
            await Task.Delay(20);
        }
        return false;
    }

    private static async Task<bool> WaitForStateAsync(QsoCallerService svc, QsoState expected, TimeSpan timeout)
    {
        var deadline = DateTime.UtcNow + timeout;
        while (DateTime.UtcNow < deadline)
        {
            if (svc.State == expected) return true;
            await Task.Delay(20);
        }
        return false;
    }

    private static void Check(List<string> failures, bool condition, string failureMessage)
    {
        if (!condition) failures.Add(failureMessage);
    }

    private static void Report(List<string> failures)
    {
        Console.WriteLine();
        if (failures.Count == 0)
        {
            Console.WriteLine("RESULT: PASS — the partner re-transmitting their own CQ no longer aborts either service's "
                + "WaitReport/WaitRr73 wait; genuine third-party messages still abort correctly.");
            return;
        }

        Console.WriteLine($"RESULT: FAIL — {failures.Count} check(s) failed:");
        foreach (var f in failures)
            Console.WriteLine($"  - {f}");
    }

    // ── Synthesiser subprocess ───────────────────────────────────────────────────────────────

    private static async Task RunSynthWavAsync(string repoRoot, string message, int freqHz, int seed, string outPath)
    {
        string pythonExe   = ResolvePythonExe(repoRoot);
        string synthScript = Path.Combine(repoRoot, "qa", "rr-study", "synth_wav.py");

        if (!File.Exists(pythonExe))
            throw new FileNotFoundException(
                $"R&R study venv Python not found at '{pythonExe}'. Set up the venv first: " +
                "cd qa/rr-study && python -m venv .venv && .venv/Scripts/pip install -r requirements.txt " +
                "(see docs/rr-synth-cli-guide.md).", pythonExe);
        if (!File.Exists(synthScript))
            throw new FileNotFoundException($"synth_wav.py not found at '{synthScript}'.", synthScript);

        var psi = new ProcessStartInfo(pythonExe)
        {
            WorkingDirectory       = Path.Combine(repoRoot, "qa", "rr-study"),
            RedirectStandardOutput = true,
            RedirectStandardError  = true,
            UseShellExecute        = false,
        };
        psi.ArgumentList.Add(synthScript);
        psi.ArgumentList.Add(message);
        psi.ArgumentList.Add("--freq");
        psi.ArgumentList.Add(freqHz.ToString());
        psi.ArgumentList.Add("--rate");
        psi.ArgumentList.Add("12000");
        psi.ArgumentList.Add("--snr");
        psi.ArgumentList.Add("none");
        psi.ArgumentList.Add("--seed");
        psi.ArgumentList.Add(seed.ToString());
        psi.ArgumentList.Add("--out");
        psi.ArgumentList.Add(outPath);

        using var process = Process.Start(psi)
            ?? throw new InvalidOperationException($"Failed to start process: {pythonExe}");

        string stdout = await process.StandardOutput.ReadToEndAsync();
        string stderr = await process.StandardError.ReadToEndAsync();
        await process.WaitForExitAsync();

        if (process.ExitCode != 0)
            throw new InvalidOperationException(
                $"synth_wav.py failed (exit {process.ExitCode}) for message '{message}':\n{stdout}\n{stderr}");
    }

    private static string ResolvePythonExe(string repoRoot)
    {
        var venvDir = Path.Combine(repoRoot, "qa", "rr-study", ".venv");
        var windows = Path.Combine(venvDir, "Scripts", "python.exe");
        var posix   = Path.Combine(venvDir, "bin", "python");
        return File.Exists(windows) ? windows : posix;
    }

    private static string FindRepoRoot()
    {
        var dir = AppContext.BaseDirectory;
        while (dir is not null)
        {
            if (File.Exists(Path.Combine(dir, "OpenWSFZ.slnx")))
                return dir;
            dir = Path.GetDirectoryName(dir);
        }
        throw new DirectoryNotFoundException("Could not locate repository root (OpenWSFZ.slnx not found).");
    }

    // ── Minimal WAV reader (12 kHz mono 16-bit PCM only) ─────────────────────────────────────

    private static float[] ReadMono16BitWav(string path, int expectedSampleRateHz)
    {
        using var stream = File.OpenRead(path);
        using var reader = new BinaryReader(stream);

        string riff = new string(reader.ReadChars(4));
        if (riff != "RIFF") throw new InvalidDataException($"'{path}': not a RIFF file.");
        reader.ReadInt32();
        string wave = new string(reader.ReadChars(4));
        if (wave != "WAVE") throw new InvalidDataException($"'{path}': RIFF subtype is not WAVE.");

        int sampleRate = 0;
        byte[]? data   = null;

        while (stream.Position + 8 <= stream.Length)
        {
            string chunkId   = new string(reader.ReadChars(4));
            int    chunkSize = reader.ReadInt32();

            if (chunkId == "fmt ")
            {
                reader.ReadInt16();          // audio format
                reader.ReadInt16();          // channels
                sampleRate = reader.ReadInt32();
                reader.ReadInt32();          // byte rate
                reader.ReadInt16();          // block align
                reader.ReadInt16();          // bits per sample
                int extra = chunkSize - 16;
                if (extra > 0) reader.ReadBytes(extra);
            }
            else if (chunkId == "data")
            {
                data = reader.ReadBytes(chunkSize);
            }
            else
            {
                reader.ReadBytes(chunkSize);
            }
            if (chunkSize % 2 != 0 && stream.Position < stream.Length) reader.ReadByte();
        }

        if (sampleRate != expectedSampleRateHz)
            throw new InvalidDataException($"'{path}': expected {expectedSampleRateHz} Hz, got {sampleRate} Hz.");
        if (data is null)
            throw new InvalidDataException($"'{path}': no data chunk found.");

        var pcm = new float[data.Length / 2];
        for (int i = 0; i < pcm.Length; i++)
        {
            short s = (short)(data[i * 2] | (data[i * 2 + 1] << 8));
            pcm[i]  = s / 32768.0f;
        }
        return pcm;
    }

    // ── Small local test doubles (clock, config store, PTT) ─────────────────────────────────

    private sealed class FixedClock(DateTime utcNow) : IClock
    {
        public DateTime UtcNow { get; } = utcNow;
    }

    private sealed class SimpleConfigStore(AppConfig current) : IConfigStore
    {
        public AppConfig Current { get; } = current;
        public event Action<AppConfig>? OnSaved;
        public Task SaveAsync(AppConfig config, CancellationToken ct = default)
        {
            OnSaved?.Invoke(config);
            return Task.CompletedTask;
        }
    }

    /// <summary>Records whether <see cref="KeyDownAsync"/> was ever called — proof the service
    /// genuinely engaged, without any real (or virtual) PTT hardware.</summary>
    private sealed class RecordingPttController : IPttController
    {
        public bool KeyedDown { get; private set; }
        public void LoadAudio(float[] samples) { }
        public Task KeyDownAsync(CancellationToken ct = default) { KeyedDown = true; return Task.CompletedTask; }
        public Task KeyUpAsync(CancellationToken ct = default) => Task.CompletedTask;
        public ValueTask DisposeAsync() => ValueTask.CompletedTask;
    }
}
