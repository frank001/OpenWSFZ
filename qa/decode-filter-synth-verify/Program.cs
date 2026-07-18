using System.Diagnostics;
using System.Threading.Channels;
using Microsoft.Extensions.Logging.Abstractions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon;
using OpenWSFZ.Ft8;
using OpenWSFZ.Web;

namespace DecodeFilterSynthVerify;

/// <summary>
/// Standalone, manually-run verification tool for the <c>decode-panel-filtering</c> capability
/// (see the README in this directory, and
/// <c>openspec/changes/decode-panel-filtering/tasks.md</c> task 6.4). Not part of
/// <c>OpenWSFZ.slnx</c> and not exercised by <c>dotnet test</c> — run it explicitly with
/// <c>dotnet run -c Release</c> from this directory.
///
/// <para>
/// Exercises the real signal chain: <c>qa/rr-study/synth_wav.py</c> (the R&amp;R study's own
/// synthesiser, invoked fresh on every run) generates four clean FT8 signals — two CQs and two
/// responses to our own CQ; each pair is summed into one 15-second cycle and decoded by the
/// real, unmocked <see cref="Ft8Decoder"/> (a genuine P/Invoke call into <c>libft8</c>), with a
/// real (small, in-memory) region store and worked-before index attached so every one of
/// <see cref="DecodeFilterState"/>'s nine independent axes has real, decoder-attached metadata
/// to filter on. The real <see cref="DecodeFilterEvaluator"/>, a real in-memory
/// <see cref="IDecodeFilterStore"/>, and real <see cref="QsoAnswererService"/>/
/// <see cref="QsoCallerService"/> instances then decide who gets engaged.
/// </para>
///
/// <para>
/// Coverage: all nine <see cref="DecodeFilterState"/> axes (one representative scenario each,
/// against <see cref="QsoAnswererService"/>'s CQ-scan gate), the "every candidate filtered out"
/// case, and three <see cref="QsoCallerService"/>-specific mechanism proofs (First-mode skip,
/// First-mode all-filtered, and <c>None</c>-mode <c>SelectResponderAsync</c> rejection) — the
/// distinct code paths that gate consult <see cref="DecodeFilterEvaluator.IsVisible"/> from.
/// The evaluator's own per-axis logic is exercised once per axis on the answerer side, since it
/// is the same shared predicate both services call; re-running all nine axes a second time
/// against the caller would prove the identical logic again rather than anything new about the
/// caller's own gating mechanism.
/// </para>
/// </summary>
internal static class Program
{
    private const string OurCallsign = "Q1OFZ";
    private const string OurGrid     = "JO33";

    private const string CallsignAlpha = "Q1AAA";
    private const string CallsignBravo = "Q1BBB";
    private const string EntityAlpha   = "Testland Alpha";
    private const string EntityBravo   = "Testland Bravo";

    private const string CqMessageAlpha  = "CQ Q1AAA JO22";
    private const string CqMessageBravo  = "CQ Q1BBB KP20";
    private const string RespMessageAlpha = "Q1OFZ Q1AAA JO22";
    private const string RespMessageBravo = "Q1OFZ Q1BBB KP20";

    private static async Task<int> Main()
    {
        Console.WriteLine("decode-panel-filtering — synthesised-signal verification");
        Console.WriteLine("=========================================================");
        Console.WriteLine();

        var failures = new List<string>();

        try
        {
            var repoRoot = FindRepoRoot();
            var workDir  = Path.Combine(Path.GetTempPath(), "decode-filter-synth-verify-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(workDir);

            try
            {
                // ── Step 1: synthesise four real FT8 signals, fresh, every run ──────────────
                Console.WriteLine("[1/4] Synthesising four FT8 signals via qa/rr-study/synth_wav.py ...");
                string cqAlphaWav   = Path.Combine(workDir, "cq_alpha.wav");
                string cqBravoWav   = Path.Combine(workDir, "cq_bravo.wav");
                string respAlphaWav = Path.Combine(workDir, "resp_alpha.wav");
                string respBravoWav = Path.Combine(workDir, "resp_bravo.wav");

                await RunSynthWavAsync(repoRoot, CqMessageAlpha,   freqHz: 800,  seed: 1, outPath: cqAlphaWav);
                await RunSynthWavAsync(repoRoot, CqMessageBravo,   freqHz: 1800, seed: 2, outPath: cqBravoWav);
                await RunSynthWavAsync(repoRoot, RespMessageAlpha, freqHz: 800,  seed: 3, outPath: respAlphaWav);
                await RunSynthWavAsync(repoRoot, RespMessageBravo, freqHz: 1800, seed: 4, outPath: respBravoWav);
                Console.WriteLine("      wrote 4 WAVs (2 CQs, 2 responses).");

                // ── Step 2: sum each pair into a cycle, decode with the REAL native decoder ─
                Console.WriteLine("[2/4] Decoding both cycles with the real Ft8Decoder (libft8 P/Invoke) ...");

                // Real (small, in-memory) region + worked-before stores, keyed by callsign, so
                // the decoder's own real enrichment code path attaches full metadata for all
                // nine DecodeFilterState axes — not overlaid afterwards by this tool.
                var regionStore = new FakeRegionStore(new Dictionary<string, RegionInfo>(StringComparer.OrdinalIgnoreCase)
                {
                    [CallsignAlpha] = new RegionInfo(Continent: "EU", Entity: EntityAlpha, Synthetic: true, CqZone: 14, ItuZone: 27),
                    [CallsignBravo] = new RegionInfo(Continent: "NA", Entity: EntityBravo, Synthetic: true, CqZone: 33, ItuZone: 10),
                });
                var workedBeforeIndex = new FakeWorkedBeforeIndex(new Dictionary<string, WorkedBeforeInfo>(StringComparer.OrdinalIgnoreCase)
                {
                    // Alpha: worked before on every axis, on this band — the "filter this one out" station.
                    [CallsignAlpha] = new WorkedBeforeInfo(
                        Contact: WorkedBeforeState.ThisBand, Country: WorkedBeforeState.ThisBand,
                        Continent: WorkedBeforeState.ThisBand, CqZone: WorkedBeforeState.ThisBand, ItuZone: WorkedBeforeState.ThisBand),
                    // Bravo: never worked on any axis — always the "passes the filter" station.
                    [CallsignBravo] = WorkedBeforeInfo.None,
                });

                var clock = new FixedClock(new DateTime(2026, 7, 10, 12, 0, 0, DateTimeKind.Utc));

                var (alphaCq, bravoCq) = await DecodePairAsync(
                    clock, regionStore, workedBeforeIndex, cqAlphaWav, cqBravoWav,
                    CqMessageAlpha, CqMessageBravo, failures, "CQ cycle");

                var (alphaResp, bravoResp) = await DecodePairAsync(
                    clock, regionStore, workedBeforeIndex, respAlphaWav, respBravoWav,
                    RespMessageAlpha, RespMessageBravo, failures, "response cycle");

                if (failures.Count > 0) { Report(failures); return 1; }

                Console.WriteLine($"      CQ cycle recovered:       {alphaCq!.Message} | {bravoCq!.Message}");
                Console.WriteLine($"      response cycle recovered: {alphaResp!.Message} | {bravoResp!.Message}");

                // ── Step 3: QsoAnswererService — all nine DecodeFilterState axes ────────────
                Console.WriteLine("[3/4] QsoAnswererService — all nine DecodeFilterState axes, plus all-filtered-out:");

                await RunAnswererAxisScenarioAsync("AllowedEntities",
                    DecodeFilterState.Unfiltered with { AllowedEntities = new HashSet<string> { EntityBravo } },
                    alphaCq, bravoCq, expectedPartner: CallsignBravo, failures);

                await RunAnswererAxisScenarioAsync("AllowedContinents",
                    DecodeFilterState.Unfiltered with { AllowedContinents = new HashSet<string> { "NA" } },
                    alphaCq, bravoCq, expectedPartner: CallsignBravo, failures);

                await RunAnswererAxisScenarioAsync("AllowedCqZones",
                    DecodeFilterState.Unfiltered with { AllowedCqZones = new HashSet<int> { 33 } },
                    alphaCq, bravoCq, expectedPartner: CallsignBravo, failures);

                await RunAnswererAxisScenarioAsync("AllowedItuZones",
                    DecodeFilterState.Unfiltered with { AllowedItuZones = new HashSet<int> { 10 } },
                    alphaCq, bravoCq, expectedPartner: CallsignBravo, failures);

                var excludeThisBand = new HashSet<WorkedBeforeState> { WorkedBeforeState.Never, WorkedBeforeState.DifferentBand };

                await RunAnswererAxisScenarioAsync("ContactStates",
                    DecodeFilterState.Unfiltered with { ContactStates = excludeThisBand },
                    alphaCq, bravoCq, expectedPartner: CallsignBravo, failures);

                await RunAnswererAxisScenarioAsync("CountryStates",
                    DecodeFilterState.Unfiltered with { CountryStates = excludeThisBand },
                    alphaCq, bravoCq, expectedPartner: CallsignBravo, failures);

                await RunAnswererAxisScenarioAsync("ContinentStates",
                    DecodeFilterState.Unfiltered with { ContinentStates = excludeThisBand },
                    alphaCq, bravoCq, expectedPartner: CallsignBravo, failures);

                await RunAnswererAxisScenarioAsync("CqZoneStates",
                    DecodeFilterState.Unfiltered with { CqZoneStates = excludeThisBand },
                    alphaCq, bravoCq, expectedPartner: CallsignBravo, failures);

                await RunAnswererAxisScenarioAsync("ItuZoneStates",
                    DecodeFilterState.Unfiltered with { ItuZoneStates = excludeThisBand },
                    alphaCq, bravoCq, expectedPartner: CallsignBravo, failures);

                await RunAnswererAxisScenarioAsync("AllowedEntities (both filtered out)",
                    DecodeFilterState.Unfiltered with { AllowedEntities = new HashSet<string>() },
                    alphaCq, bravoCq, expectedPartner: null, failures);

                // ── Step 4: QsoCallerService — the three distinct gating mechanisms ─────────
                Console.WriteLine("[4/4] QsoCallerService — First-mode skip, all-filtered, and None-mode rejection:");

                await RunCallerFirstModeSkipScenarioAsync(alphaResp, bravoResp, failures);
                await RunCallerFirstModeAllFilteredScenarioAsync(alphaResp, bravoResp, failures);
                await RunCallerNoneModeRejectionScenarioAsync(alphaResp, failures);
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

    private static async Task<(DecodeResult? alpha, DecodeResult? bravo)> DecodePairAsync(
        IClock clock, ICallsignRegionStore regionStore, IWorkedBeforeIndex workedBeforeIndex,
        string alphaWavPath, string bravoWavPath,
        string expectedAlphaMessage, string expectedBravoMessage,
        List<string> failures, string cycleLabel)
    {
        float[] alphaPcm = ReadMono16BitWav(alphaWavPath, expectedSampleRateHz: 12_000);
        float[] bravoPcm = ReadMono16BitWav(bravoWavPath, expectedSampleRateHz: 12_000);

        if (alphaPcm.Length != bravoPcm.Length)
        {
            failures.Add($"{cycleLabel}: fixture length mismatch (alpha={alphaPcm.Length}, bravo={bravoPcm.Length} samples).");
            return (null, null);
        }

        var combinedCycle = new float[alphaPcm.Length];
        for (int i = 0; i < combinedCycle.Length; i++)
            combinedCycle[i] = alphaPcm[i] + bravoPcm[i];

        var decoder = new Ft8Decoder(clock, logger: null, grammarStore: null, regionStore: regionStore, workedBeforeIndex: workedBeforeIndex);
        IReadOnlyList<DecodeResult> decoded = await decoder.DecodeAsync(combinedCycle, clock.UtcNow, CancellationToken.None);
        var messages = decoded.Select(r => r.Message).ToList();

        Check(failures, messages.Contains(expectedAlphaMessage),
            $"{cycleLabel}: real decoder must recover '{expectedAlphaMessage}'. Decoded: [{string.Join(", ", messages)}]");
        Check(failures, messages.Contains(expectedBravoMessage),
            $"{cycleLabel}: real decoder must recover '{expectedBravoMessage}'. Decoded: [{string.Join(", ", messages)}]");

        var alpha = decoded.FirstOrDefault(r => r.Message == expectedAlphaMessage);
        var bravo = decoded.FirstOrDefault(r => r.Message == expectedBravoMessage);

        if (alpha is not null)
        {
            Check(failures, alpha.Region?.Entity == EntityAlpha, $"{cycleLabel}: Alpha's Region.Entity should be '{EntityAlpha}'.");
            Check(failures, alpha.WorkedBefore?.Contact == WorkedBeforeState.ThisBand, $"{cycleLabel}: Alpha's WorkedBefore.Contact should be ThisBand.");
        }
        if (bravo is not null)
        {
            Check(failures, bravo.Region?.Entity == EntityBravo, $"{cycleLabel}: Bravo's Region.Entity should be '{EntityBravo}'.");
            Check(failures, bravo.WorkedBefore?.Contact == WorkedBeforeState.Never, $"{cycleLabel}: Bravo's WorkedBefore.Contact should be Never.");
        }

        return (alpha, bravo);
    }

    // ── QsoAnswererService scenario runner (covers all nine axes + all-filtered-out) ────────

    private static async Task RunAnswererAxisScenarioAsync(
        string axisLabel, DecodeFilterState filter,
        DecodeResult alphaCq, DecodeResult bravoCq,
        string? expectedPartner, List<string> failures)
    {
        var filterStore = new MutableDecodeFilterStore();
        filterStore.Set(filter);

        var ptt = new RecordingPttController();
        var configStore = new SimpleConfigStore(new AppConfig() with
        {
            Tx = new TxConfig { AutoAnswer = true, Callsign = OurCallsign, Grid = OurGrid, RetryCount = 2, WatchdogMinutes = 4 },
        });
        var adifLog = new AdifLogWriter(configStore, NullLogger<AdifLogWriter>.Instance);
        var channel = Channel.CreateUnbounded<DecodeBatch>();

        // IsActive defaults to true (internal property, not settable from outside
        // OpenWSFZ.Daemon's assembly) — fine here, no competing QsoCallerService instance exists.
        var sut = new QsoAnswererService(
            channel.Reader, configStore, ptt, new TxEventBus(),
            adifLog, new AudioOffsetEventBus(), NullLogger<QsoAnswererService>.Instance,
            decoder: null, catState: null, decodeFilterStore: filterStore);

        var stopCts = new CancellationTokenSource();
        await sut.StartAsync(stopCts.Token);

        try
        {
            channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow, [alphaCq, bravoCq]));

            if (expectedPartner is not null)
            {
                bool reached = await WaitForStateAsync(sut, QsoState.WaitReport, TimeSpan.FromSeconds(5));
                Check(failures, reached, $"[{axisLabel}] expected WaitReport within 5 s; actual state {sut.State}, partner {sut.Partner ?? "(none)"}.");
                Check(failures, sut.Partner == expectedPartner, $"[{axisLabel}] expected partner '{expectedPartner}'; actual '{sut.Partner ?? "(none)"}'.");
                Check(failures, ptt.KeyedDown, $"[{axisLabel}] expected IPttController.KeyDownAsync to have been called.");
                Console.WriteLine(ptt.KeyedDown && sut.Partner == expectedPartner
                    ? $"      OK  [{axisLabel,-36}] partner = {sut.Partner}"
                    : $"      FAIL[{axisLabel,-36}] partner = {sut.Partner ?? "(none)"}, state = {sut.State}");
            }
            else
            {
                await Task.Delay(400); // give the (unbounded) channel's reader a chance to process
                Check(failures, sut.State == QsoState.Idle, $"[{axisLabel}] expected to remain Idle (all candidates filtered out); actual state {sut.State}.");
                Check(failures, !ptt.KeyedDown, $"[{axisLabel}] expected no PTT engagement when every candidate is filtered out.");
                Console.WriteLine(sut.State == QsoState.Idle && !ptt.KeyedDown
                    ? $"      OK  [{axisLabel,-36}] stayed Idle, no TX"
                    : $"      FAIL[{axisLabel,-36}] state = {sut.State}, PTT keyed = {ptt.KeyedDown}");
            }
        }
        finally
        {
            await stopCts.CancelAsync();
            await sut.StopAsync(CancellationToken.None);
            await ptt.DisposeAsync();
        }
    }

    // ── QsoCallerService scenarios ───────────────────────────────────────────────────────────

    private static (QsoCallerService sut, RecordingPttController ptt, Channel<DecodeBatch> channel, CancellationTokenSource stopCts)
        BuildCaller(CallerPartnerSelectMode partnerSelect, IDecodeFilterStore? filterStore)
    {
        var ptt = new RecordingPttController();
        var configStore = new SimpleConfigStore(new AppConfig() with
        {
            Tx = new TxConfig
            {
                AutoAnswer          = true,
                Callsign            = OurCallsign,
                Grid                = OurGrid,
                CallerPartnerSelect = partnerSelect,
                RetryCount          = 3,
                WatchdogMinutes     = 4,
            },
        });
        var adifLog = new AdifLogWriter(configStore, NullLogger<AdifLogWriter>.Instance);
        var channel = Channel.CreateUnbounded<DecodeBatch>();

        var sut = new QsoCallerService(
            channel.Reader, configStore, ptt, new TxEventBus(),
            adifLog, new AudioOffsetEventBus(), NullLogger<QsoCallerService>.Instance,
            decoder: null, catState: null, decodeFilterStore: filterStore);

        return (sut, ptt, channel, new CancellationTokenSource());
    }

    /// <summary>Primes a fresh caller into WaitAnswer (mapped to <see cref="QsoState.WaitReport"/>
    /// — design.md D8) by feeding one irrelevant decode so its own auto-CQ transmission proceeds.
    /// The content here is deliberately not one of the four synthesised signals — it is disregarded
    /// noise whose only job is to advance the decode-batch-driven state machine, exactly mirroring
    /// <c>QsoCallerServiceTests</c>' own priming step.</summary>
    private static async Task<bool> PrimeCallerIntoWaitAnswerAsync(QsoCallerService sut, Channel<DecodeBatch> channel, CancellationTokenSource stopCts)
    {
        await sut.StartAsync(stopCts.Token);
        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [new DecodeResult(Time: "12:00:00", Snr: -5, Dt: 0.1, FreqHz: 1500, Message: "CQ Q2NOISE JO00")]));
        return await WaitForStateAsync(sut, QsoState.WaitReport, TimeSpan.FromSeconds(5));
    }

    private static async Task RunCallerFirstModeSkipScenarioAsync(DecodeResult alphaResp, DecodeResult bravoResp, List<string> failures)
    {
        const string label = "Caller First-mode skip";
        var filterStore = new MutableDecodeFilterStore();
        filterStore.Set(DecodeFilterState.Unfiltered with { AllowedEntities = new HashSet<string> { EntityBravo } });

        var (sut, ptt, channel, stopCts) = BuildCaller(CallerPartnerSelectMode.First, filterStore);
        try
        {
            bool primed = await PrimeCallerIntoWaitAnswerAsync(sut, channel, stopCts);
            Check(failures, primed, $"[{label}] failed to reach WaitAnswer during priming.");

            channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow, [alphaResp, bravoResp]));
            bool reached = await WaitForStateAsync(sut, QsoState.WaitRr73, TimeSpan.FromSeconds(5));

            Check(failures, reached, $"[{label}] expected WaitRr73 within 5 s; actual state {sut.State}, partner {sut.Partner ?? "(none)"}.");
            Check(failures, sut.Partner == CallsignBravo, $"[{label}] expected partner '{CallsignBravo}' (Alpha filtered out); actual '{sut.Partner ?? "(none)"}'.");
            Console.WriteLine(sut.Partner == CallsignBravo
                ? $"      OK  [{label,-28}] partner = {sut.Partner}"
                : $"      FAIL[{label,-28}] partner = {sut.Partner ?? "(none)"}, state = {sut.State}");
        }
        finally
        {
            await stopCts.CancelAsync();
            await sut.StopAsync(CancellationToken.None);
            await ptt.DisposeAsync();
        }
    }

    private static async Task RunCallerFirstModeAllFilteredScenarioAsync(DecodeResult alphaResp, DecodeResult bravoResp, List<string> failures)
    {
        const string label = "Caller First-mode all-filtered";
        var filterStore = new MutableDecodeFilterStore();
        filterStore.Set(DecodeFilterState.Unfiltered with { AllowedEntities = new HashSet<string>() });

        var (sut, ptt, channel, stopCts) = BuildCaller(CallerPartnerSelectMode.First, filterStore);
        try
        {
            bool primed = await PrimeCallerIntoWaitAnswerAsync(sut, channel, stopCts);
            Check(failures, primed, $"[{label}] failed to reach WaitAnswer during priming.");

            channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow, [alphaResp, bravoResp]));
            await Task.Delay(400);

            Check(failures, sut.State == QsoState.WaitReport, $"[{label}] expected to remain WaitAnswer (WaitReport); actual state {sut.State}.");
            Check(failures, sut.Partner is null, $"[{label}] expected no partner selected; actual '{sut.Partner}'.");
            Console.WriteLine(sut.State == QsoState.WaitReport && sut.Partner is null
                ? $"      OK  [{label,-28}] stayed WaitAnswer, no partner selected"
                : $"      FAIL[{label,-28}] state = {sut.State}, partner = {sut.Partner ?? "(none)"}");
        }
        finally
        {
            await stopCts.CancelAsync();
            await sut.StopAsync(CancellationToken.None);
            await ptt.DisposeAsync();
        }
    }

    private static async Task RunCallerNoneModeRejectionScenarioAsync(DecodeResult alphaResp, List<string> failures)
    {
        const string label = "Caller None-mode SelectResponderAsync rejection";
        var filterStore = new MutableDecodeFilterStore();
        filterStore.Set(DecodeFilterState.Unfiltered with { AllowedEntities = new HashSet<string> { EntityBravo } }); // Alpha filtered out

        var (sut, ptt, channel, stopCts) = BuildCaller(CallerPartnerSelectMode.None, filterStore);
        try
        {
            bool primed = await PrimeCallerIntoWaitAnswerAsync(sut, channel, stopCts);
            Check(failures, primed, $"[{label}] failed to reach WaitAnswer during priming.");

            // Record the (filtered-out) responder decode so SelectResponderAsync has something
            // to evaluate against — None mode records every recognised responder regardless of
            // filter state; the rejection happens inside SelectResponderAsync itself.
            channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow, [alphaResp]));
            await Task.Delay(300);

            var bPhaseResponse = new DateTimeOffset(2026, 6, 25, 14, 29, 15, TimeSpan.Zero);
            await sut.SelectResponderAsync(CallsignAlpha, alphaResp.FreqHz, bPhaseResponse, CancellationToken.None);
            await Task.Delay(300);

            Check(failures, sut.State == QsoState.WaitReport, $"[{label}] expected no state transition (rejected callsign); actual state {sut.State}.");
            Check(failures, sut.Partner is null, $"[{label}] expected no pending responder armed; actual '{sut.Partner}'.");
            Console.WriteLine(sut.State == QsoState.WaitReport && sut.Partner is null
                ? $"      OK  [{label,-28}] filtered-out callsign rejected outright"
                : $"      FAIL[{label,-28}] state = {sut.State}, partner = {sut.Partner ?? "(none)"}");
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
            Console.WriteLine("RESULT: PASS — filtering and TX-automation gating behave as intended across all nine axes and both services.");
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

    // ── Small local test doubles (region + worked-before lookup, filter store, clock, PTT) ──

    private sealed class FixedClock(DateTime utcNow) : IClock
    {
        public DateTime UtcNow { get; } = utcNow;
    }

    /// <summary>
    /// Deterministic, in-memory <see cref="ICallsignRegionStore"/> mapping exactly the two test
    /// callsigns used by this tool to their (fictitious) DXCC entities/zones — a stand-in for the
    /// real 29 000-entry <c>callsign-regions.json</c>, which has no entry for synthetic Q-prefix
    /// test calls by design (NFR-021). Everything downstream of this lookup (the decoder's own
    /// message-parsing/enrichment wiring, <see cref="DecodeFilterEvaluator"/>,
    /// <see cref="QsoAnswererService"/>/<see cref="QsoCallerService"/>) is genuine production code.
    /// </summary>
    private sealed class FakeRegionStore(IReadOnlyDictionary<string, RegionInfo> map) : ICallsignRegionStore
    {
        public IReadOnlyList<CallsignRegionEntry> Entries => [];

        public RegionInfo? TryGetRegion(string callsignToken)
            => map.TryGetValue(callsignToken, out var region) ? region : null;

        public Task SaveAsync(IReadOnlyList<CallsignRegionEntry> entries, CancellationToken cancellationToken = default)
            => throw new NotSupportedException("Not needed by this tool — region data is fixed for its lifetime.");
    }

    /// <summary>Deterministic, in-memory <see cref="IWorkedBeforeIndex"/> stand-in — a real
    /// <c>ADIF.log</c>-backed index would need an actual log file; this tool only needs fixed,
    /// known worked-before states so all five worked-before axes have real decoder-attached
    /// metadata to filter on.</summary>
    private sealed class FakeWorkedBeforeIndex(IReadOnlyDictionary<string, WorkedBeforeInfo> map) : IWorkedBeforeIndex
    {
        public Task LoadAsync(CancellationToken cancellationToken = default) => Task.CompletedTask;
        public void Register(string callsign, string? band) { }
        public WorkedBeforeInfo Resolve(string callsignToken, string? currentBand)
            => map.TryGetValue(callsignToken, out var wb) ? wb : WorkedBeforeInfo.None;
    }

    private sealed class MutableDecodeFilterStore : IDecodeFilterStore
    {
        public DecodeFilterState Current { get; private set; } = DecodeFilterState.Unfiltered;
        public void Set(DecodeFilterState state) => Current = state;

        // fix-decode-filter-new-value-admission: this in-process synth-verify tool exercises
        // DecodeFilterEvaluator/the nine-axis matrix directly, not daemon-side admission — real
        // AdmitNewValues coverage lives in DecodeFilterStoreAdmitNewValuesTests (OpenWSFZ.Web.Tests)
        // and in live_verify_9_axes.py's Phase 7 (real isolated daemon).
        public DecodeFilterState? AdmitNewValues(DecodeResult decode) => null;
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
