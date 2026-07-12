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
#if WASAPI_SUPPORTED
using System.Runtime.Versioning;
#endif

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

// Resolve the prop-modes.json path — same data directory as app.json (qso-log-dialog).
var propModesPath = Path.Combine(
    Path.GetDirectoryName(configPath) ?? AppContext.BaseDirectory,
    "prop-modes.json");

// Create the PropModeStore (logger not available yet; assigned after host builds).
var propModeStore = new PropModeStore(propModesPath);

// Resolve the callsign-grammar.json / callsign-regions.json paths — same data
// directory as app.json (f-002-callsign-structure-region-lookup).
var callsignGrammarPath = Path.Combine(
    Path.GetDirectoryName(configPath) ?? AppContext.BaseDirectory,
    "callsign-grammar.json");
var callsignRegionsPath = Path.Combine(
    Path.GetDirectoryName(configPath) ?? AppContext.BaseDirectory,
    "callsign-regions.json");

// Create the callsign grammar/region stores (logger not available yet; assigned after host builds).
var callsignGrammarStore = new CallsignGrammarStore(callsignGrammarPath);
var callsignRegionStore  = new CallsignRegionStore(callsignRegionsPath);

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
// Pass null so the factory resolves Log.Logger dynamically at each emit, rather than
// capturing the instance at construction time.  This allows loggingPipeline.Apply()
// to replace Log.Logger at runtime (e.g. when the operator enables file logging via
// the settings page) and have all ILogger<T> consumers immediately route to the new
// pipeline — without a daemon restart.
using var loggerFactory = new Serilog.Extensions.Logging.SerilogLoggerFactory(
    null, dispose: false);

void ConfigureLogging(ILoggingBuilder lb)
{
    lb.ClearProviders();
    // Pass no logger so the Serilog MEL provider resolves Log.Logger dynamically
    // at each emit.  This mirrors the standalone loggerFactory above and ensures
    // loggingPipeline.Apply() replacements are visible to all ILogger<T> consumers
    // without a restart.  Note: SetMinimumLevel is still fixed at startup, so
    // console log-level changes still require a restart; file-sink enable/disable
    // and file log level take effect immediately.
    lb.AddSerilog(dispose: false);
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

// region-lookup-data-refresh (f-006): fetch/convert components for the operator-triggered
// POST /api/v1/region-data/refresh endpoint. The HttpClient is long-lived (one instance for the
// daemon's lifetime, matching the style of other singletons constructed here) with a bounded
// timeout so an unreachable country-files.com cannot hang the endpoint indefinitely. The fetch
// only ever happens in response to an explicit operator request (never on startup or a timer).
var countryFileHttpClient = new HttpClient { Timeout = TimeSpan.FromSeconds(30) };
countryFileHttpClient.DefaultRequestHeaders.UserAgent.ParseAdd(
    $"OpenWSFZ/{OpenWSFZ.Web.AssemblyVersion.Get()}");
var countryFileSource    = new HttpCountryFileSource(
    countryFileHttpClient, loggerFactory.CreateLogger<HttpCountryFileSource>());
var countryFileConverter = new CountryFilePlistConverter();

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

// Worked-before index (qso-confirmation): resolves "worked before" advisory state from
// ADIF.log's history, resolving each logged callsign's DXCC entity/continent via the
// callsign region store above. Constructed here (after loggerFactory exists) so it gets a
// real logger, unlike callsignRegionStore/callsignGrammarStore above.
var workedBeforeIndex = new WorkedBeforeIndex(
    configStore, callsignRegionStore, loggerFactory.CreateLogger<WorkedBeforeIndex>());

// ── FT8 decode pipeline ──────────────────────────────────────────────────────

var clock          = new SystemClock();
var ft8Decoder     = new Ft8Decoder(
    clock,
    loggerFactory.CreateLogger<Ft8Decoder>(),
    grammarStore:      callsignGrammarStore,
    regionStore:       callsignRegionStore,
    workedBeforeIndex: workedBeforeIndex);

// f-004-operator-visibility-improvements (daemon-status-visibility): force the native
// shim's lazy load + ABI self-test to run now, at true process startup, rather than
// waiting for the first decode cycle. A version mismatch throws here — before the web
// host starts listening — and the retained value is ready to serve on GET /api/v1/status
// from the very first request (design.md Decision 1).
var shimVersion = Ft8Decoder.LoadedShimVersion;
startupLogger.LogInformation("Native FT8 decoder shim ABI version: {ShimVersion}.", shimVersion);

// N6: generated once, up front, so DecodeEventBus (constructed here, before WebApp.Create
// runs) carries the same app-instance scope as the sockets WebApp.Create will register.
// Threaded through to WebApp.Create, ITxEventBus, and AudioOffsetEventBus below so all four
// share one scope rather than each independently minting its own (which would defeat N6's
// scope-guard fix).
var appScope = Guid.NewGuid();
var decodeEventBus = new DecodeEventBus(appScope);
// AllTxtWriter no longer holds a reference to ICatState; the caller (decode pump) supplies
// the snapshotted dial frequency for each cycle (defect: dial-freq-snapshot, FR-032).
var allTxtWriter = new AllTxtWriter(configStore, loggerFactory.CreateLogger<AllTxtWriter>());

// Channel 1: CycleFramer → (float[] Pcm, DateTime CycleStart, double? DialFrequencyMHz) windows → decode pump
// CycleFramer records the cycle-start timestamp AND the dial frequency snapshot at window-open
// time. The decode pump compares the snapshot against the current live frequency; if they differ
// the cycle audio spans two bands and the window is discarded (defect: dial-freq-snapshot).
// Channel 2: decode pump → DecodeEventBus (direct call, no channel needed)
// Channel 3a: decode pump → QsoAnswererService (bounded, DropOldest — answerer must never block decode).
// Channel 3b: decode pump → QsoCallerService  (bounded, DropOldest — same rationale).
//   Both channels carry DecodeBatch so the authoritative UTC cycle-start is always available;
//   avoids the fallback-to-UtcNow bug (D-TX-UI-004).  The decode pump fan-outs to both channels;
//   QsoControllerRouter activates the appropriate service via IsActive flags.
var qsoAnswererChannel = Channel.CreateBounded<DecodeBatch>(new BoundedChannelOptions(2)
{
    FullMode     = BoundedChannelFullMode.DropOldest,
    SingleWriter = true,
    SingleReader = true,
});
var qsoCallerChannel = Channel.CreateBounded<DecodeBatch>(new BoundedChannelOptions(2)
{
    FullMode     = BoundedChannelFullMode.DropOldest,
    SingleWriter = true,
    SingleReader = true,
});

// Channel 3c: decode pump → ExternalReportingService (bounded, DropOldest — same rationale as
// the two channels above). Dedicated rather than a DecodeEventBus subscription (design.md
// originally sketched the latter, but DecodeEventBus is a one-way WebSocket broadcaster with no
// subscriber surface) — mirrors the existing per-consumer decode-batch-channel pattern exactly.
var externalReportingChannel = Channel.CreateBounded<DecodeBatch>(new BoundedChannelOptions(2)
{
    FullMode     = BoundedChannelFullMode.DropOldest,
    SingleWriter = true,
    SingleReader = true,
});

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

// ── LAN remote-access policy selection (lan-remote-access phase) ──────────────
//
// Read RemoteAccessConfig from the loaded config and register the appropriate
// IBindPolicy and IAuthPolicy singletons before WebApp.Create is called (D6).
// The bind address is set once at Kestrel startup and cannot change without a restart.

var remoteAccess = configStore.Current.RemoteAccess;

// SEC-001: Refuse to start when LAN mode is enabled without a passphrase.
// An empty passphrase would register NullAuthPolicy and leave every endpoint
// open to any device on the local network.
if (!LanModeValidator.IsValid(remoteAccess, out var lanError))
{
    startupLogger.LogCritical("{Error}", lanError);
    return 1;
}

IBindPolicy bindPolicy = remoteAccess.Enabled
    ? new LanBindPolicy(loggerFactory.CreateLogger<LanBindPolicy>())
    : new LoopbackBindPolicy(loggerFactory.CreateLogger<LoopbackBindPolicy>());

IAuthPolicy authPolicy = (remoteAccess.Enabled && !string.IsNullOrEmpty(remoteAccess.Passphrase))
    ? new PassphraseAuthPolicy(remoteAccess.Passphrase)
    : new NullAuthPolicy();

startupLogger.LogInformation(
    "Remote access: Enabled={Enabled} → bind={BindPolicy}, auth={AuthPolicy}.",
    remoteAccess.Enabled,
    bindPolicy.GetType().Name,
    authPolicy.GetType().Name);

// Create and configure the web application.
var app = WebApp.Create(
    port,
    appScope:                   appScope,
    bindPolicy:                 bindPolicy,
    configStore:                configStore,
    frequencyStore:             frequencyStore,
    propModeStore:              propModeStore,
    audioProviderFactory:       sp => new PlatformAudioDeviceProvider(
                                          sp.GetRequiredService<ILoggerFactory>()),
    audioOutputProviderFactory: sp => new PlatformAudioOutputDeviceProvider(
                                          sp.GetRequiredService<ILoggerFactory>()),
    captureManager:       captureManager,
    audioMonitor:         audioMonitor,
    dataFlowMonitor:      dataFlowMonitor,
    catState:             catState,
    configureLogging:     ConfigureLogging,
    restartPipeline:      restartPipeline,
    shimVersion:          shimVersion,
    // f-005-hash-table-saturation-diagnostic (D2): live provider so GET /api/v1/status can
    // report the native hash-table reject count mid-session (it changes over time, unlike
    // the fixed shimVersion above).
    hashTableRejectCountProvider: () => ft8Decoder.GetHashTableRejectCount(),
    configureServices:    services =>
    {
        // Register the auth policy selected above (daemon wins over WebApp.Create default).
        services.AddSingleton<IAuthPolicy>(authPolicy);
        services.AddSingleton(loggingPipeline);
        // ILogFileSource (log-viewer): lets WebApp.cs read the active log file path
        // without OpenWSFZ.Web depending on OpenWSFZ.Daemon.
        services.AddSingleton<ILogFileSource>(loggingPipeline);
        services.AddSingleton(allTxtWriter);
        services.AddHostedService<LogRotationService>();

        // Frequency store DI wiring (FR-042).
        services.AddSingleton<IFrequencyStore>(frequencyStore);

        // Prop mode store DI wiring (qso-log-dialog).
        services.AddSingleton<IPropModeStore>(propModeStore);

        // Callsign grammar / region store DI wiring (f-002-callsign-structure-region-lookup).
        services.AddSingleton<ICallsignGrammarStore>(callsignGrammarStore);
        services.AddSingleton<ICallsignRegionStore>(callsignRegionStore);

        // Worked-before index DI wiring (qso-confirmation). AdifLogWriter picks this up via
        // constructor injection to register newly-logged QSOs into the live index.
        services.AddSingleton<IWorkedBeforeIndex>(workedBeforeIndex);

        // Region-data-refresh fetch/convert DI wiring (region-lookup-data-refresh, f-006).
        services.AddSingleton<ICountryFileSource>(countryFileSource);
        services.AddSingleton<ICountryFileConverter>(countryFileConverter);

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
        services.AddSingleton<ICatController>(sp => sp.GetRequiredService<CatPollingService>());
        // ICatPttGate (task 6.4, FR-056): the narrow seam CatPttController depends on so
        // PTT commands are always serialised against the poll loop — see CatPollingService's
        // class remarks and design.md Decision 1 of the cat-tx-ptt change.
        services.AddSingleton<ICatPttGate>(sp => sp.GetRequiredService<CatPollingService>());
        services.AddHostedService(sp => sp.GetRequiredService<CatPollingService>());

        // PTT controller (task 4.5, extended by cat-tx-ptt task 11.1, FR-056): a three-way
        // switch on AppConfig.Ptt.Method selects exactly one IPttController implementation
        // at startup, falling back to AudioOnlyPttController/NullPttController per the
        // existing WASAPI_SUPPORTED platform gating when WASAPI is unavailable or the
        // configured Method is unrecognised (design.md Decision 6 — matches the existing
        // CatConfig.RigModel unknown-value handling, FR-034). A missing ptt config key
        // defaults to Method = "AudioVox", preserving today's behaviour exactly.
        // CA1416: suppressed — the CatCommand/SerialRtsDtr branches are only compiled when
        //         WASAPI_SUPPORTED is defined, which is set exclusively on Windows targets
        //         (see .csproj) — same rationale as the pre-existing AudioVox branch.
#pragma warning disable CA1416
#if WASAPI_SUPPORTED
        switch (PttControllerSelector.Resolve(configStore.Current.Ptt.Method, startupLogger))
        {
            case PttControllerKind.CatCommand:
                services.AddSingleton<IPttController, CatPttController>();
                break;
            case PttControllerKind.SerialRtsDtr:
                services.AddSingleton<IPttController, SerialRtsDtrPttController>();
                break;
            default:
                services.AddSingleton<IPttController, AudioOnlyPttController>();
                break;
        }
#else
        services.AddSingleton<IPttController, NullPttController>();
#endif
#pragma warning restore CA1416

        // QSO controller and ADIF log writer.
        // N6: constructed with the shared appScope (closed over from the outer Program.cs
        // scope, consistent with allTxtWriter/loggingPipeline/callsignRegionStore etc. below)
        // rather than letting the DI container default-construct these types, so their
        // WebSocketHub.Broadcast* calls carry the same scope as decodeEventBus and the
        // sockets WebApp.Create registers.
        services.AddSingleton<ITxEventBus>(new TxEventBus(appScope));
        services.AddSingleton(new AudioOffsetEventBus(appScope));
        services.AddSingleton<AdifLogWriter>();

        // gridtracker-udp-reporting: ExternalReportingService registered unconditionally
        // (inert by default — opens no sockets until externalReporting.enabled=true with at
        // least one enabled target). Reads decode batches from its own dedicated channel
        // (declared above, fed by the decode pump below) and is resolved lazily by
        // QsoLoggedNotifyingAdifWriter and by IQsoController/IExternalReplyTarget consumers
        // via IServiceProvider (see ExternalReportingService's class remarks for why this must
        // be lazy rather than a constructor dependency — it avoids a DI construction cycle
        // through IAdifLogWriter below).
        // ICallsignRegionStore is passed so the absolute, non-configurable synthetic/unknown-
        // region exclusion (Captain's directive — see ExternalReportingService's class remarks)
        // can resolve a bare partner callsign's region for Status/QSOLogged, which (unlike
        // outbound Decode) carry only a callsign string with no pre-resolved DecodeResult.Region.
        services.AddSingleton(sp => new ExternalReportingService(
            externalReportingChannel.Reader,
            sp.GetRequiredService<IConfigStore>(),
            sp,
            sp.GetRequiredService<ILogger<ExternalReportingService>>(),
            sp.GetService<ICatState>(),
            sp.GetService<ICallsignRegionStore>()));
        services.AddHostedService(sp => sp.GetRequiredService<ExternalReportingService>());

        // IAdifLogWriter resolves to a decorator so every ADIF write (direct-write path AND
        // WebApp's POST /api/v1/tx/log-qso) also emits an outbound QSOLogged datagram — see
        // QsoLoggedNotifyingAdifWriter's class remarks.
        services.AddSingleton<IAdifLogWriter>(sp => new QsoLoggedNotifyingAdifWriter(
            sp.GetRequiredService<AdifLogWriter>(),
            sp.GetRequiredService<ExternalReportingService>()));

        // H6 AP decode (D-001): register the ft8Decoder instance as IApConstraintSink so
        // the active QSO controller can arm/disarm AP constraints during active QSO sessions.
        services.AddSingleton<IApConstraintSink>(ft8Decoder);

        // QSO controller — router pattern (Call CQ, task 11.4).
        // Both services are always registered and run as HostedServices; each gets its own
        // dedicated decode channel so they never compete for batches.  QsoControllerRouter
        // activates the appropriate service via IsActive flags and acts as the IQsoController
        // proxy.  Runtime role switching (Call CQ) is thus possible without a daemon restart.
        var txRole = configStore.Current.Tx?.Role ?? TxRole.Answerer;

        services.AddSingleton<QsoAnswererService>(sp => {
            var svc = new QsoAnswererService(
                qsoAnswererChannel.Reader,
                sp.GetRequiredService<IConfigStore>(),
                sp.GetRequiredService<IPttController>(),
                sp.GetRequiredService<ITxEventBus>(),
                sp.GetRequiredService<IAdifLogWriter>(),
                sp.GetRequiredService<AudioOffsetEventBus>(),
                sp.GetRequiredService<ILogger<QsoAnswererService>>(),
                sp.GetService<IApConstraintSink>(),
                sp.GetService<ICatState>(),
                sp.GetService<IDecodeFilterStore>());
            // Set IsActive immediately so the service behaves correctly from the first batch.
            svc.IsActive = (txRole == TxRole.Answerer);
            return svc;
        });

        services.AddSingleton<QsoCallerService>(sp => {
            var svc = new QsoCallerService(
                qsoCallerChannel.Reader,
                sp.GetRequiredService<IConfigStore>(),
                sp.GetRequiredService<IPttController>(),
                sp.GetRequiredService<ITxEventBus>(),
                sp.GetRequiredService<IAdifLogWriter>(),
                sp.GetRequiredService<AudioOffsetEventBus>(),
                sp.GetRequiredService<ILogger<QsoCallerService>>(),
                sp.GetService<IApConstraintSink>(),
                sp.GetService<ICatState>(),
                sp.GetService<IDecodeFilterStore>());
            svc.IsActive = (txRole == TxRole.Caller);
            return svc;
        });

        // Router is registered as:
        //   QsoControllerRouter — resolved by its own DI factory (the root singleton)
        //   IQsoController      — all existing consumers (WebApp status/enable/abort/etc.)
        //   IQsoRoleSwitcher    — call-cq endpoint in WebApp (avoids a Daemon→Web circular ref)
        services.AddSingleton<QsoControllerRouter>();
        services.AddSingleton<IQsoController>(sp => sp.GetRequiredService<QsoControllerRouter>());
        services.AddSingleton<IQsoRoleSwitcher>(sp => sp.GetRequiredService<QsoControllerRouter>());
        // IExternalReplyTarget (gridtracker-udp-reporting): the inbound Reply handler in
        // ExternalReportingService resolves this to route by whichever role is active.
        services.AddSingleton<IExternalReplyTarget>(sp => sp.GetRequiredService<QsoControllerRouter>());

        // Both services run as HostedServices; the inactive one discards batches cheaply.
        services.AddHostedService(sp => sp.GetRequiredService<QsoAnswererService>());
        services.AddHostedService(sp => sp.GetRequiredService<QsoCallerService>());
    });

// ── Lifecycle hooks ──────────────────────────────────────────────────────────

app.Lifetime.ApplicationStarted.Register(() =>
{
    WelcomeBannerEmitter.Emit(port);
    startupLogger.LogInformation("OpenWSFZ started on port {Port}.", port);

    // ── Apply initial decoder parameters before the first decode cycle (task 5.2) ─
    // Null decoder key in config is treated as calibrated defaults (new DecoderConfig()).
    var initialDecoder = configStore.Current.Decoder ?? new DecoderConfig();
    ft8Decoder.SetDecodeParams(
        initialDecoder.KMinScorePass2,
        initialDecoder.OsdCorrThreshold,
        initialDecoder.OsdNhardMax);

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

                // qso-confirmation-band-awareness: resolve the session's current active band
                // alongside dialFreq, using the same already-trustworthy (D-013) value — no
                // second frequency resolution, just a band-name conversion via the shared
                // BandTable (design.md Decision 4). null when dialFreq is 0.0 (unresolvable).
                var currentBand = BandTable.DeriveBand(dialFreq);
                var results     = await ft8Decoder.DecodeAsync(pcmWindow, cycleStart, currentBand);

                // decode-noise-suppression: a deliberate, operator-opt-in exception to the
                // region-lookup capability's "a lookup miss ... SHALL still reach ALL.TXT and the
                // UI" invariant — see DecodeNoiseSuppressionFilter's doc comment. region-lookup's
                // own resolution logic above is untouched; only the decode-panel broadcast and the
                // QSO-controller batches below are gated. ALL.TXT (next line) always receives the
                // unfiltered `results`.
                var visibleResults = DecodeNoiseSuppressionFilter.Apply(
                    results, configStore.Current.DecodeNoiseSuppression, callsignRegionStore);

                _ = decodeEventBus.Publish(visibleResults); // fire-and-forget: do not await WebSocket delivery
                await allTxtWriter.AppendAsync(cycleStart, dialFreq, results); // unfiltered — ALL.TXT unaffected

                // Fan-out to both QSO controller channels (non-blocking; DropOldest when full).
                // QsoControllerRouter activates only one service at a time via IsActive flags;
                // the inactive service's HandleIdleAsync is a no-op, so the extra batches are cheap.
                var batch = new DecodeBatch(new DateTimeOffset(cycleStart, TimeSpan.Zero), visibleResults);
                qsoAnswererChannel.Writer.TryWrite(batch);
                qsoCallerChannel.Writer.TryWrite(batch);
                externalReportingChannel.Writer.TryWrite(batch);
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
    // ── Decoder params update (decoder-settings-page, task 5.1) ─────────────
    // Apply the new decoder parameters immediately so the next decode cycle
    // picks them up.  Null decoder is treated as calibrated defaults.
    var dec = newConfig.Decoder ?? new DecoderConfig();
    ft8Decoder.SetDecodeParams(dec.KMinScorePass2, dec.OsdCorrThreshold, dec.OsdNhardMax);
    // Re-apply the Serilog pipeline only when logging-related settings actually
    // change, so that non-logging saves (e.g. Cat.LastPolledFrequencyMHz) do not
    // create a spurious new log file and reset the active sink.
    //
    // File-sink enable/disable and file log level take effect immediately: the
    // loggerFactory and ASP.NET host both resolve Log.Logger dynamically (null
    // passed to SerilogLoggerFactory / AddSerilog), so Apply()'s replacement of
    // Log.Logger is visible to all ILogger<T> consumers without a restart.
    // Console log level still requires a restart (SetMinimumLevel is fixed at
    // host-build time and has no runtime equivalent without a full LevelSwitch).
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

        // f-005-hash-table-saturation-diagnostic (D2): read the session's final native
        // hash-table reject count once at graceful shutdown and log it, so table
        // saturation can be confirmed or ruled out during endurance-run review without a
        // live diagnostic query. The decode pump has already stopped by this point, so no
        // torn read of the process-global counter is possible. Logged BEFORE loggingPipeline
        // is disposed so the line reaches the file sink. HashTableRejectCountReporter swallows
        // any native/ABI fault so a best-effort diagnostic read can never block shutdown.
        HashTableRejectCountReporter.Report(startupLogger, () => ft8Decoder.GetHashTableRejectCount());

        loggingPipeline.Dispose();    // flush buffered file events before process exit
    }
    finally
    {
        restartSemaphore.Release();
    }
});

// Load (or create) frequencies.json before starting the web host (FR-042, task 3.3).
await frequencyStore.LoadAsync();

// Load (or create) prop-modes.json before starting the web host (qso-log-dialog).
await propModeStore.LoadAsync();

// Load (or create) callsign-grammar.json / callsign-regions.json before starting the
// web host (f-002-callsign-structure-region-lookup) — Ft8Decoder is already constructed
// with references to these stores, so this must complete before the first decode cycle.
await callsignGrammarStore.LoadAsync();
await callsignRegionStore.LoadAsync();

// Build the worked-before index from ADIF.log before starting the web host
// (qso-confirmation) — Ft8Decoder is already constructed with a reference to it, so this
// must complete before the first decode cycle. Depends on callsignRegionStore above having
// already loaded (entity/continent resolution for each logged callsign).
await workedBeforeIndex.LoadAsync();

await app.RunAsync();
return 0;

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
