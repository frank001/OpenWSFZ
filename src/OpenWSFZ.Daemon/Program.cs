using System.Threading.Channels;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Audio;
using OpenWSFZ.Config;
using OpenWSFZ.Daemon;
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

// ── FT8 decode pipeline ──────────────────────────────────────────────────────

var clock          = new SystemClock();
var ft8Decoder     = new Ft8Decoder(clock, loggerFactory.CreateLogger<Ft8Decoder>());
var decodeEventBus = new DecodeEventBus();
var allTxtWriter   = new AllTxtWriter(configStore, loggerFactory.CreateLogger<AllTxtWriter>());

// Channel 1: CycleFramer → float[] PCM windows → decode pump
// Channel 2: decode pump → DecodeEventBus (direct call, no channel needed)
var framerOutput = Channel.CreateBounded<float[]>(new BoundedChannelOptions(2)
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
    audioProviderFactory: sp => new PlatformAudioDeviceProvider(
                                    sp.GetRequiredService<ILoggerFactory>()),
    captureManager:       captureManager,
    audioMonitor:         audioMonitor,
    dataFlowMonitor:      dataFlowMonitor,
    configureLogging:     ConfigureLogging,
    restartPipeline:      restartPipeline,
    configureServices:    services =>
    {
        services.AddSingleton(loggingPipeline);
        services.AddSingleton(allTxtWriter);
        services.AddHostedService<LogRotationService>();
    });

// ── Lifecycle hooks ──────────────────────────────────────────────────────────

app.Lifetime.ApplicationStarted.Register(() =>
{
    WelcomeBannerEmitter.Emit(port);
    startupLogger.LogInformation("OpenWSFZ started on port {Port}.", port);

    var deviceName = configStore.Current.AudioDeviceId;
    if (deviceName is not null)
        StartPipeline(deviceName);

    // Decode-pump: reads completed PCM windows, decodes, broadcasts results.
    // A3: pass the application stopping token so ReadAllAsync exits promptly on
    // shutdown rather than waiting for the current DecodeAsync to finish.
    var stoppingToken = app.Lifetime.ApplicationStopping;
    _ = Task.Run(async () =>
    {
        await foreach (var pcmWindow in framerOutput.Reader.ReadAllAsync(stoppingToken))
        {
            try
            {
                // Capture UTC timestamp immediately before decode so AllTxtWriter
                // can use the correct date in the YYMMDD prefix (D3 / FR-028).
                var cycleUtc = DateTime.UtcNow;
                var results  = await ft8Decoder.DecodeAsync(pcmWindow);
                decodeEventBus.Publish(results);
                await allTxtWriter.AppendAsync(cycleUtc, results);
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
string? runningDevice = configStore.Current.AudioDeviceId;
configStore.OnSaved += newConfig =>
{
    // Re-apply the logging pipeline on every save so file-logging changes
    // and console level changes take effect immediately (FR-022, FR-019).
    var newConsoleLevel = Enum.TryParse<LogLevel>(newConfig.LogLevel,
        ignoreCase: true, out var nl) ? nl : LogLevel.Information;
    loggingPipeline.Apply(newConfig.Logging ?? new LoggingConfig(), consoleLevel: newConsoleLevel);

    var newDevice = newConfig.AudioDeviceId;
    if (newDevice == runningDevice) return;

    runningDevice = newDevice;

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
        loggerFactory.CreateLogger<CycleFramer>());

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
