using System.Threading.Channels;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Audio;
using OpenWSFZ.Config;
using OpenWSFZ.Daemon;
using OpenWSFZ.Daemon.Cat;
using OpenWSFZ.Daemon.Logging;
using OpenWSFZ.Ft8;
using OpenWSFZ.Ft8.Dsp;
using OpenWSFZ.Web;
using Serilog;

// Parse CLI options before building the host.
var options = LaunchOptions.Parse(args);

// Resolve the config file path (CLI flag → env var → platform default).
var (configPath, configSource) = ConfigPathResolver.Resolve(options.ConfigPath);
Console.Error.WriteLine($"[OpenWSFZ] Config: {configSource} → {configPath}");

// Load (or create) the config file.
// Note: constructed before the logger exists (bootstrap phase).
var configStore = new JsonConfigStore(configPath);

// Resolve the frequencies.json path — same data directory as app.json (FR-042).
var frequenciesPath = Path.Combine(
    Path.GetDirectoryName(configPath) ?? AppContext.BaseDirectory,
    "frequencies.json");

// Create the FrequencyStore (logger not available yet; assigned after host builds).
var frequencyStore = new FrequencyStore(frequenciesPath);

// ── Logging setup (FR-019, FR-022, FR-023, FR-024) ────────────────────────────
// Parse the configured log level.  Invalid values fall back to Information.
var logLevel = Enum.TryParse<LogLevel>(configStore.Current.LogLevel, ignoreCase: true, out var parsedLevel)
    ? parsedLevel
    : LogLevel.Information;

// Suppress ASP.NET Core / System framework categories at Warning or higher
// (whichever is more restrictive) so they don't pollute the operator log.
var frameworkLevel = logLevel > LogLevel.Warning ? logLevel : LogLevel.Warning;

// Bootstrap the Serilog pipeline before any loggerFactory is created so that
// CaptureManager / CycleFramer / Ft8Decoder startup logs reach the file sink.
var loggingPipeline = new LoggingPipeline();
loggingPipeline.Apply(configStore.Current.Logging ?? new LoggingConfig(), consoleLevel: logLevel);

// Standalone logger factory delegates to Log.Logger (set above).
using var loggerFactory = new Serilog.Extensions.Logging.SerilogLoggerFactory(
    Log.Logger, dispose: false);

void ConfigureLogging(ILoggingBuilder lb)
{
    lb.ClearProviders();
    lb.AddSerilog(Log.Logger, dispose: false);
    lb.SetMinimumLevel(logLevel);
    lb.AddFilter("Microsoft", frameworkLevel);
    lb.AddFilter("System",    frameworkLevel);
}

// Log the startup info that the bootstrap Console.Error already printed.
var startupLogger = loggerFactory.CreateLogger("OpenWSFZ.Daemon.Program");
startupLogger.LogInformation("Config: {Source} → {Path}", configSource, configPath);
startupLogger.LogInformation("Log level: {Level}", logLevel);

// CLI --port wins; fall back to the persisted config value.
var port = options.Port ?? configStore.Current.Port;

// ── Audio capture ─────────────────────────────────────────────────────────────

var audioSource    = new PlatformAudioSource(loggerFactory);
var captureManager = new CaptureManager(audioSource, loggerFactory.CreateLogger<CaptureManager>());

// ── Audio activity monitor (FR-020) ──────────────────────────────────────────

var audioMonitor    = new AudioActivityMonitor();
var dataFlowMonitor = new DataFlowMonitor();

// ── Spectrum analyser ─────────────────────────────────────────────────────
var spectrumAnalyser = new SpectrumAnalyser();
var spectrumBus      = new SpectrumEventBus();

// Wire monitors and spectrum analyser to the capture callback.
// audioMonitor tracks amplitude for the heartbeat UI (FR-020).
// dataFlowMonitor tracks any-chunk-received for the watchdog (B18).
// spectrumAnalyser accumulates samples and fires SpectrumReady every 2048 samples.
captureManager.ChunkReceived = chunk =>
{
    audioMonitor.ObserveSamples(chunk);
    dataFlowMonitor.OnChunkReceived();
    spectrumAnalyser.Push(chunk);
};

spectrumAnalyser.SpectrumReady += magnitudes =>
{
    // Gate: skip serialisation if no clients are connected.
    if (!spectrumBus.HasClients) return;

    // Map dBFS [−100, −20] → int [0, 255]. (D1)
    // FT8 signals at typical SDR/microphone levels sit at roughly −70 to −85 dBFS per
    // FFT bin. The old [−120, 0] range mapped them to intensities 64–106, visually
    // indistinguishable from the noise floor at ≈64 (uniform blue-cyan wash).
    // Narrowing to [−100, −20] places those signals at intensities 125–188 — clearly
    // distinct from a noise floor at 0 and from clipping at 255.
    const float DbMin   = -100f;
    const float DbMax   =  -20f;
    const float DbRange = DbMax - DbMin; // 80 dB
    var bins = new int[SpectrumAnalyser.OutputBinCount];
    for (var i = 0; i < bins.Length; i++)
    {
        var db = magnitudes[i];
        if (db < DbMin) db = DbMin;
        if (db > DbMax) db = DbMax;
        bins[i] = (int)MathF.Round((db - DbMin) / DbRange * 255f);
    }

    spectrumBus.Publish(bins);
};

// ── CAT rig control (FR-031, FR-032) ─────────────────────────────────────────

// CatState is the live telemetry singleton (task 11.1).
// CatEventBus is constructed inside WebApp.Create (with the app-instance scope)
// and registered in DI — no manual construction needed here.
var catState = new CatState();

// ── FT8 decode pipeline ──────────────────────────────────────────────────────

var clock          = new SystemClock();
var ft8Decoder     = new Ft8Decoder(clock, loggerFactory.CreateLogger<Ft8Decoder>());
var decodeEventBus = new DecodeEventBus();
// AllTxtWriter no longer holds a reference to ICatState; the caller (decode pump) supplies
// the snapshotted dial frequency for each cycle (defect: dial-freq-snapshot, FR-032).
var allTxtWriter = new AllTxtWriter(configStore, loggerFactory.CreateLogger<AllTxtWriter>());

// Channel 1: CycleFramer → (float[] Pcm, DateTime CycleStart, double? DialFrequencyMHz) windows → decode pump
// CycleFramer records the cycle-start timestamp AND the dial frequency snapshot at window-open
// time. The decode pump compares the snapshot against the current live frequency; if they differ
// the cycle audio spans two bands and the window is discarded (defect: dial-freq-snapshot).
// Channel 2: decode pump → DecodeEventBus (direct call, no channel needed)
var framerOutput = Channel.CreateBounded<(float[] Pcm, DateTime CycleStart, double? DialFrequencyMHz)>(new BoundedChannelOptions(2)
{
    FullMode     = BoundedChannelFullMode.DropOldest,
    SingleWriter = true,
    SingleReader = true,
});

CancellationTokenSource? framerCts          = null;
Task?                    framerTask         = null;
var                      captureRestartCount = 0; // L-13 (DIAG): counts auto-restart attempts
var                      restartSemaphore   = new SemaphoreSlim(1, 1); // B2: serialise concurrent restart paths

// Surface inner capture faults to the operator and auto-restart the pipeline.
// Audio capture must always be running (Captain's directive).
// Registered here (after all closed-over variables are declared) so the
// lambda's forward references resolve correctly at compile time.
captureManager.CaptureFailed += ex =>
{
    startupLogger.LogError(ex,
        "Audio capture failed on '{Device}': {Message}",
        configStore.Current.AudioDeviceFriendlyName ?? configStore.Current.AudioDeviceId,
        ex.Message);

    // Auto-restart: schedule a restart with a 5-second backoff to prevent
    // rapid restart loops on persistent failures (e.g. device genuinely
    // unavailable) while keeping recovery prompt for transient stops
    // (driver power-management, format re-negotiation, session expiry).
    var device = configStore.Current.AudioDeviceId;
    if (device is null) return;

    _ = Task.Run(async () =>
    {
        await Task.Delay(TimeSpan.FromSeconds(5));

        // L-14 (DIAG): log the IsCapturing guard result so we can tell whether
        // the restart was skipped because another path already recovered.
        var isCapturing = captureManager.IsCapturing;
        startupLogger.LogDebug(
            "Restart guard check on '{Device}': IsCapturing={IsCapturing}.",
            device, isCapturing);
        if (isCapturing) return;

        // L-13 (DIAG): increment and log restart attempt number.
        captureRestartCount++;
        startupLogger.LogInformation(
            "Auto-restarting audio capture on device '{Device}' after failure " +
            "(attempt #{RestartCount}).", device, captureRestartCount);

        await RestartPipelineAsync(device, stopCaptureManager: false);
    });
};

// S6: watchdog restart action. Wraps StopFramerAsync / StopAsync / StartPipeline
// so the heartbeat loop can fire-and-forget it without blocking.
// The top-level try-catch ensures restart failures are logged rather than
// silently swallowed by the discarded ValueTask at the call site.
Func<Task> restartPipeline = () => Task.Run(async () =>
{
    try
    {
        var device      = configStore.Current.AudioDeviceId;
        var displayName = configStore.Current.AudioDeviceFriendlyName ?? device;
        startupLogger.LogWarning(
            "Watchdog: audio silent for 15 s while capturing on '{Device}' — restarting pipeline.",
            displayName);
        await RestartPipelineAsync(device, stopCaptureManager: true);
    }
    catch (Exception ex)
    {
        startupLogger.LogError(ex,
            "Watchdog pipeline restart failed on device '{Device}': {Message}",
            configStore.Current.AudioDeviceFriendlyName ?? configStore.Current.AudioDeviceId,
            ex.Message);
    }
});

// Create and configure the web application.
var app = WebApp.Create(
    port,
    configStore:          configStore,
    frequencyStore:       frequencyStore,
    audioProviderFactory: sp => new PlatformAudioDeviceProvider(
                                    sp.GetRequiredService<ILoggerFactory>()),
    captureManager:       captureManager,
    audioMonitor:         audioMonitor,
    dataFlowMonitor:      dataFlowMonitor,
    catState:             catState,
    configureLogging:     ConfigureLogging,
    restartPipeline:      restartPipeline,
    configureServices:    services =>
    {
        services.AddSingleton(loggingPipeline);
        services.AddSingleton(allTxtWriter);
        services.AddHostedService<LogRotationService>();

        // Frequency store DI wiring (FR-042).
        services.AddSingleton<IFrequencyStore>(frequencyStore);

        // CAT DI wiring (tasks 11.1–11.3, FR-031).
        // Register the CatState singleton under both its concrete type (for
        // CatPollingService to call internal Update) and the ICatState interface
        // (for any future consumer that only needs the read side).
        services.AddSingleton(catState);
        services.AddSingleton<ICatState>(catState);

        // CatPollingService registered as a singleton so ICatTuner (FR-045) can
        // be resolved from DI by the web layer.  Also wired as IHostedService
        // so the ASP.NET Core host starts and stops it automatically.
        services.AddSingleton<CatPollingService>();
        services.AddSingleton<ICatTuner>(sp => sp.GetRequiredService<CatPollingService>());
        services.AddHostedService(sp => sp.GetRequiredService<CatPollingService>());
    });

// ── Lifecycle hooks ──────────────────────────────────────────────────────────

app.Lifetime.ApplicationStarted.Register(() =>
{
    WelcomeBannerEmitter.Emit(port);
    startupLogger.LogInformation("OpenWSFZ started on port {Port}.", port);

    var deviceName = configStore.Current.AudioDeviceId;
    if (deviceName is not null && configStore.Current.DecodingEnabled)
        StartPipeline(deviceName);

    // Decode-pump: reads completed PCM windows, decodes, broadcasts results.
    // A3: pass the application stopping token so ReadAllAsync exits promptly on
    // shutdown rather than waiting for the current DecodeAsync to finish.
    var stoppingToken = app.Lifetime.ApplicationStopping;
    _ = Task.Run(async () =>
    {
        await foreach (var (pcmWindow, cycleStart, windowDialFreq) in
            framerOutput.Reader.ReadAllAsync(stoppingToken))
        {
            try
            {
                // Snapshot the live frequency immediately before decoding.
                // If a band change occurred during the 15-second capture window, the audio
                // spans two bands and cannot be reliably labeled with either frequency.
                // Discard the cycle: a mislabeled decode is worse than no decode (FR-032,
                // defect: dial-freq-snapshot).
                var currentDialFreq = (double?)WebApp.ResolveEffectiveFrequency(catState, configStore.Current);
                if (windowDialFreq != currentDialFreq)
                {
                    startupLogger.LogInformation(
                        "Cycle {CycleStart:HH:mm:ss}: discarded — dial frequency changed " +
                        "from {Before} to {After} MHz during capture window.",
                        cycleStart,
                        windowDialFreq?.ToString("F3") ?? "unknown",
                        currentDialFreq?.ToString("F3") ?? "unknown");
                    continue;
                }

                // cycleStart is the UTC instant at which CycleFramer began accumulating
                // this window — the authoritative cycle timestamp (R3 / FR-028).
                // dialFreq falls back to the configured value when CAT is absent.
                var dialFreq = windowDialFreq ?? configStore.Current.DecodeLog?.DialFrequencyMHz ?? 0.0;
                var results  = await ft8Decoder.DecodeAsync(pcmWindow, cycleStart);
                decodeEventBus.Publish(results);
                await allTxtWriter.AppendAsync(cycleStart, dialFreq, results);
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
            {
                break; // clean shutdown
            }
            catch (Exception ex)
            {
                startupLogger.LogError(ex, "Decode error: {Message}", ex.Message);
            }
        }
    });
});

// Restart pipeline when the device name changes via POST /api/v1/config.
string?       runningDevice       = configStore.Current.AudioDeviceId;
bool          runningEnabled      = configStore.Current.DecodingEnabled;
// Track the last applied logging state so the OnSaved handler below can skip
// Apply() on saves that only touch non-logging fields (e.g. Cat.LastPolledFrequencyMHz
// from FR-039).  LoggingConfig is a sealed record, so == is value equality.
LoggingConfig lastLoggingConfig   = configStore.Current.Logging ?? new LoggingConfig();
LogLevel      lastLogConsoleLevel = logLevel;
configStore.OnSaved += newConfig =>
{
    // Re-apply the Serilog pipeline only when logging-related settings actually
    // change, so that non-logging saves (e.g. Cat.LastPolledFrequencyMHz) do not
    // create a spurious new log file and reset the active sink.
    //
    // NOTE: the MEL ILoggerFactory was wired to the Serilog instance captured
    // at startup (lb.AddSerilog(Log.Logger, ...)) and the MEL minimum level was
    // fixed via lb.SetMinimumLevel(). Neither updates dynamically, so console-
    // level and file-level changes do NOT take effect until the next restart.
    // TODO: replace with a SerilogLoggingLevelSwitch wired to both the Serilog
    //       pipeline and the MEL factory to achieve true live log-level updates.
    var newConsoleLevel  = Enum.TryParse<LogLevel>(newConfig.LogLevel,
        ignoreCase: true, out var nl) ? nl : LogLevel.Information;
    var newLoggingConfig = newConfig.Logging ?? new LoggingConfig();
    if (newLoggingConfig != lastLoggingConfig || newConsoleLevel != lastLogConsoleLevel)
    {
        lastLoggingConfig   = newLoggingConfig;
        lastLogConsoleLevel = newConsoleLevel;
        loggingPipeline.Apply(newLoggingConfig, consoleLevel: newConsoleLevel);
    }

    var newDevice  = newConfig.AudioDeviceId;
    var newEnabled = newConfig.DecodingEnabled;

    // ── Device-change transition ──────────────────────────────────────────
    if (newDevice != runningDevice)
    {
        runningDevice  = newDevice;
        runningEnabled = newEnabled;

        _ = Task.Run(async () =>
        {
            try
            {
                await RestartPipelineAsync(newDevice, stopCaptureManager: true);
            }
            catch (Exception ex)
            {
                startupLogger.LogError(ex,
                    "Audio capture failed to restart on device '{Device}'.", newDevice);
            }
        });
        return;
    }

    // ── DecodingEnabled transition ────────────────────────────────────────
    if (newEnabled == runningEnabled) return;

    runningEnabled = newEnabled;

    if (newEnabled && newDevice is not null)
    {
        // Operator enabled decoding — start pipeline.
        _ = Task.Run(async () =>
        {
            try
            {
                await restartSemaphore.WaitAsync();
                try { StartPipeline(newDevice); }
                finally { restartSemaphore.Release(); }
            }
            catch (Exception ex)
            {
                startupLogger.LogError(ex,
                    "Failed to start pipeline after DecodingEnabled = true on device '{Device}'.",
                    newDevice);
            }
        });
    }
    else if (!newEnabled && runningDevice is not null)
    {
        // Operator disabled decoding — stop pipeline.
        _ = Task.Run(async () =>
        {
            try
            {
                await restartSemaphore.WaitAsync();
                try
                {
                    await StopFramerAsync();
                    await captureManager.StopAsync();
                }
                finally { restartSemaphore.Release(); }
            }
            catch (Exception ex)
            {
                startupLogger.LogError(ex,
                    "Failed to stop pipeline after DecodingEnabled = false.");
            }
        });
    }
};

// Stop pipeline and dispose on application shutdown.
// Note: WebApp.Create registers an ApplicationStopping hook (AbortAll) that fires first
// (registration order), immediately aborting all WebSocket connections.  By the time this
// callback runs, the browser UI is already dark.
app.Lifetime.ApplicationStopping.Register(() =>
{
    startupLogger.LogInformation(
        "Application stopping — aborting WebSocket connections and shutting down capture pipeline.");

    // B2: wait for any in-progress restart to complete before tearing down,
    // so shutdown cannot race with a concurrent CaptureFailed / watchdog restart.
    restartSemaphore.Wait();
    try
    {
        StopFramerAsync().GetAwaiter().GetResult();
        captureManager.StopAsync().GetAwaiter().GetResult();
        captureManager.DisposeAsync().AsTask().GetAwaiter().GetResult();
        framerOutput.Writer.TryComplete();
        loggingPipeline.Dispose();    // flush buffered file events before process exit
    }
    finally
    {
        restartSemaphore.Release();
    }
});

// Load (or create) frequencies.json before starting the web host (FR-042, task 3.3).
await frequencyStore.LoadAsync();

await app.RunAsync();

// ── Helper methods ───────────────────────────────────────────────────────────

void StartPipeline(string deviceName)
{
    startupLogger.LogInformation("Starting FT8 pipeline for device '{Device}'.", deviceName);

    // StartAsync itself completes before _captureTask runs; inner faults are
    // reported via the captureManager.CaptureFailed event (wired above).
    _ = captureManager.StartAsync(deviceName);

    framerCts = new CancellationTokenSource();
    var ct = framerCts.Token;

    var cycleFramer = new CycleFramer(
        captureManager.Samples,
        clock,
        loggerFactory.CreateLogger<CycleFramer>(),
        dialFreqProvider: () => WebApp.ResolveEffectiveFrequency(catState, configStore.Current));

    framerTask = Task.Run(() => cycleFramer.RunAsync(framerOutput.Writer, ct));
}

async Task StopFramerAsync()
{
    var cts = framerCts;
    if (cts is null) return;

    cts.Cancel();

    var task = framerTask;
    if (task is not null)
    {
        try { await task.WaitAsync(TimeSpan.FromSeconds(3)); }
        catch (TimeoutException)          { }
        catch (OperationCanceledException){ }
        catch (Exception)                 { }
    }

    cts.Dispose();
    framerCts  = null;
    framerTask = null;
}

async Task RestartPipelineAsync(string? device, bool stopCaptureManager)
{
    // B2: serialise all restart callers (CaptureFailed, watchdog, config change).
    await restartSemaphore.WaitAsync();
    try
    {
        await StopFramerAsync();
        if (stopCaptureManager)
            await captureManager.StopAsync();
        audioMonitor.Reset();
        dataFlowMonitor.Reset();
        spectrumAnalyser.Reset();
        if (device is not null)
            StartPipeline(device);
    }
    finally
    {
        restartSemaphore.Release();
    }
}

// Public partial Program class — type anchor for WebApplicationFactory<Program> in tests.
public partial class Program { }
