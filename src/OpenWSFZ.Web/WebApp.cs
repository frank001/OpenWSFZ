using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.StaticFiles;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.FileProviders;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Audio;
using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Text.Json;

namespace OpenWSFZ.Web;

/// <summary>
/// Factory for the ASP.NET Core web application.
/// Called by <c>OpenWSFZ.Daemon</c> in production and by test fixtures directly.
/// </summary>
public static class WebApp
{
    /// <summary>
    /// Creates and configures a <see cref="WebApplication"/> bound to
    /// <paramref name="port"/> via the supplied <see cref="IBindPolicy"/>.
    /// Pass <paramref name="port"/><c> = 0</c> for an OS-assigned ephemeral port
    /// (used by tests).
    /// </summary>
    /// <param name="port">Port to bind on. 0 = OS-assigned ephemeral port.</param>
    /// <param name="bindPolicy">Optional bind policy override (tests may supply a passthrough).</param>
    /// <param name="configStore">
    /// <see cref="IConfigStore"/> to register as a singleton.
    /// Defaults to an in-memory store backed by a default <see cref="AppConfig"/>.
    /// </param>
    /// <param name="audioProvider">
    /// <see cref="IAudioDeviceProvider"/> to register as a singleton.
    /// Defaults to <see cref="InMemoryAudioDeviceProvider"/> (empty list).
    /// </param>
    public static WebApplication Create(
        int port,
        IBindPolicy?                                        bindPolicy                  = null,
        IConfigStore?                                       configStore                 = null,
        IFrequencyStore?                                    frequencyStore              = null,
        IAudioDeviceProvider?                               audioProvider               = null,
        Func<IServiceProvider, IAudioDeviceProvider>?       audioProviderFactory        = null,
        IAudioOutputDeviceProvider?                         audioOutputProvider         = null,
        Func<IServiceProvider, IAudioOutputDeviceProvider>? audioOutputProviderFactory  = null,
        CaptureManager?                                     captureManager              = null,
        AudioActivityMonitor?                               audioMonitor                = null,
        DataFlowMonitor?                                    dataFlowMonitor             = null,
        ICatState?                                          catState                    = null,
        Action<ILoggingBuilder>?                            configureLogging            = null,
        Func<Task>?                                         restartPipeline             = null,
        Action<IServiceCollection>?                         configureServices           = null)
    {
        // S1: unique scope ID for this WebApp instance, used to tag every WebSocket
        // connection accepted through this app's /api/v1/ws endpoint.  AbortAll(appScope)
        // only aborts connections belonging to this instance, preventing test-infrastructure
        // apps (e.g. WebApplicationFactory) from aborting sockets owned by a concurrently
        // running integration-test server.
        var appScope = Guid.NewGuid();

        // CatEventBus carries appScope so BroadcastCatStatus only delivers to sockets
        // belonging to this WebApp instance (scope guard — mirrors AbortAll pattern).
        var catEventBus = new CatEventBus(appScope);

        var builder = WebApplication.CreateBuilder();

        // ── Services ──────────────────────────────────────────────────────────

        // Register the scoped CatEventBus before any caller-supplied registrations so
        // that CatPollingService (registered via configureServices) resolves the correct
        // instance when the DI container builds.
        builder.Services.AddSingleton(catEventBus);

        builder.Services.AddSingleton<IBindPolicy>(
            sp => bindPolicy ?? new LoopbackBindPolicy(
                sp.GetRequiredService<Microsoft.Extensions.Logging.ILogger<LoopbackBindPolicy>>()));
        builder.Services.AddSingleton<IAuthPolicy, NullAuthPolicy>();

        builder.Services.AddSingleton<IConfigStore>(
            configStore ?? new InMemoryConfigStore());

        builder.Services.AddSingleton<IFrequencyStore>(
            frequencyStore ?? new InMemoryFrequencyStore());

        if (audioProviderFactory is not null)
            builder.Services.AddSingleton<IAudioDeviceProvider>(audioProviderFactory);
        else
            builder.Services.AddSingleton<IAudioDeviceProvider>(
                audioProvider ?? new InMemoryAudioDeviceProvider());

        if (audioOutputProviderFactory is not null)
            builder.Services.AddSingleton<IAudioOutputDeviceProvider>(audioOutputProviderFactory);
        else
            builder.Services.AddSingleton<IAudioOutputDeviceProvider>(
                audioOutputProvider ?? new InMemoryAudioOutputDeviceProvider());

        // Caller-supplied DI registrations (e.g. LoggingPipeline, LogRotationService).
        configureServices?.Invoke(builder.Services);

        // AOT-safe JSON serialisation.
        builder.Services.ConfigureHttpJsonOptions(opts =>
            opts.SerializerOptions.TypeInfoResolverChain.Insert(0, AppJsonContext.Default));

        // ── Kestrel ───────────────────────────────────────────────────────────

        // Always resolve IBindPolicy from DI so the same instance is used
        // everywhere — Kestrel, the DI container, and future callers all see the
        // same object.  Constructing a second instance inline would cause Kestrel
        // to silently bypass any config-derived state on the registered singleton.
        builder.WebHost.ConfigureKestrel((_, kestrel) =>
        {
            var policy = kestrel.ApplicationServices.GetRequiredService<IBindPolicy>();
            var endpoint = policy.Resolve(IPAddress.Loopback, port);
            kestrel.Listen(endpoint);
        });

        // Logging: use the caller-supplied configuration (FR-019) or fall back to
        // a minimal warning-only setup so tests stay quiet by default.
        if (configureLogging is not null)
            configureLogging(builder.Logging);
        else
            builder.Logging.SetMinimumLevel(LogLevel.Warning);

        var app = builder.Build();

        // ── Middleware ────────────────────────────────────────────────────────

        // Auth middleware (D3): placed before UseWebSockets, UseDefaultFiles,
        // UseStaticFiles, and all route registrations so that every request —
        // including WebSocket upgrades and static-file requests — is gated.
        // AOT-safe: plain lambda, no reflection or attribute-based filters.
        var authPolicy = app.Services.GetRequiredService<IAuthPolicy>();

        // Paths that must be reachable before authentication (browsers cannot
        // carry ?key= into sub-resource requests after the initial page-load):
        //   /login.html  — the auth UI itself
        //   /css/        — stylesheets
        //   /js/         — ES module scripts
        //   /favicon.ico — browser chrome (avoids a spurious 302 in the console)
        // API paths are intentionally excluded — they must always be gated.
        static bool IsPublicPath(PathString path) =>
            path.StartsWithSegments("/login.html",  StringComparison.OrdinalIgnoreCase) ||
            path.StartsWithSegments("/css",         StringComparison.OrdinalIgnoreCase) ||
            path.StartsWithSegments("/js",          StringComparison.OrdinalIgnoreCase) ||
            path.Equals("/favicon.ico",             StringComparison.OrdinalIgnoreCase);

        app.Use(async (ctx, next) =>
        {
            if (IsPublicPath(ctx.Request.Path))
            {
                await next(ctx);
                return;
            }

            var remoteIp      = ctx.Connection.RemoteIpAddress;
            var apiKeyHeader  = ctx.Request.Headers["X-Api-Key"].ToString();
            var keyQueryParam = ctx.Request.Query["key"].ToString();

            if (!authPolicy.IsAuthorized(
                    remoteIp,
                    apiKeyHeader.Length  > 0 ? apiKeyHeader  : null,
                    keyQueryParam.Length > 0 ? keyQueryParam : null))
            {
                // API paths and WebSocket upgrades return 401 so JS can handle them.
                // Browser page-loads (everything else) redirect to the login page.
                // Note: StartsWithSegments uses segment-boundary comparison; "/api" (no
                // trailing slash) correctly matches /api/v1/status, /api/v1/ws, etc.
                if (ctx.Request.Path.StartsWithSegments("/api", StringComparison.OrdinalIgnoreCase))
                {
                    ctx.Response.StatusCode = StatusCodes.Status401Unauthorized;
                    return;
                }

                ctx.Response.Redirect("/login.html");
                return;
            }

            await next(ctx);
        });

        app.UseWebSockets();

        // Static files from the `web/` directory next to the executable.
        var webRoot = Path.Combine(AppContext.BaseDirectory, "web");
        if (Directory.Exists(webRoot))
        {
            var fileProvider = new PhysicalFileProvider(webRoot);

            // Map GET / → /index.html (must precede UseStaticFiles).
            app.UseDefaultFiles(new DefaultFilesOptions
            {
                FileProvider = fileProvider,
                RequestPath  = string.Empty,
            });

            app.UseStaticFiles(new StaticFileOptions
            {
                FileProvider = fileProvider,
                RequestPath  = string.Empty,
            });
        }

        // Logger for the config POST endpoint (CAT validation warnings).
        var configApiLogger = app.Services.GetRequiredService<ILoggerFactory>()
                                          .CreateLogger("OpenWSFZ.Web.ConfigApi");

        // ── REST Endpoints ────────────────────────────────────────────────────

        app.MapGet("/api/v1/status", (IConfigStore store) =>
        {
            var effectiveFreq = ResolveEffectiveFrequency(catState, store.Current);
            return TypedResults.Ok(new DaemonStatus(
                State:               "Running",
                Version:             AssemblyVersion.Get(),
                AudioDevice:         store.Current.AudioDeviceFriendlyName ?? store.Current.AudioDeviceId,
                CaptureActive:       captureManager?.IsCapturing ?? false,
                AudioActive:         audioMonitor?.IsActive ?? false,
                DecodingEnabled:     store.Current.DecodingEnabled,
                DialFrequencyMHz:    effectiveFreq,
                CatConnectionStatus: catState?.Status.ToString() ?? "Disabled"));
        });

        app.MapGet("/api/v1/audio/devices", async (
            IAudioDeviceProvider provider,
            CancellationToken ct) =>
        {
            var devices = new List<AudioDeviceInfo>(await provider.GetDevicesAsync(ct));
            return TypedResults.Ok(devices);
        });

        app.MapGet("/api/v1/audio/output-devices", async (
            IAudioOutputDeviceProvider outputProvider,
            CancellationToken ct) =>
        {
            var devices = new List<AudioDeviceInfo>(await outputProvider.GetDevicesAsync(ct));
            return TypedResults.Ok(devices);
        });

        app.MapGet("/api/v1/serial/ports", () =>
        {
            string[] ports;
            try
            {
                ports = System.IO.Ports.SerialPort.GetPortNames().OrderBy(p => p).ToArray();
            }
            catch
            {
                ports = [];
            }
            return TypedResults.Ok(ports);
        });

        app.MapGet("/api/v1/config", (IConfigStore store) =>
            TypedResults.Ok(store.Current));

        app.MapPost("/api/v1/config", async (
            HttpRequest  request,
            IConfigStore store,
            CancellationToken ct) =>
        {
            AppConfig? config;
            try
            {
                config = await request.ReadFromJsonAsync(AppJsonContext.Default.AppConfig, ct);
            }
            catch (JsonException)
            {
                // Results.BadRequest (non-generic) is intentional: mixing TypedResults.BadRequest<string>
                // with TypedResults.Ok<AppConfig> in the same lambda produces a type-unification error
                // (CS1593) because C# cannot infer a common return type across the two IResult
                // implementations. The non-generic Results.* form returns IResult directly, which
                // resolves the inference. TypedResults.Ok on the happy path is preserved for
                // OpenAPI schema generation on the success response.
                return Results.BadRequest("Malformed JSON.");
            }

            if (config is null)
                return Results.BadRequest("Missing or empty request body.");

            // ── CAT config validation (FR-031, FR-034) ─────────────────────────
            if (config.Cat is { } cat)
            {
                var sanitisedCat = cat;

                // Clamp pollIntervalSeconds to [1, 60].
                if (cat.PollIntervalSeconds < 1 || cat.PollIntervalSeconds > 60)
                {
                    var clamped = Math.Clamp(cat.PollIntervalSeconds, 1, 60);
                    configApiLogger.LogWarning(
                        "CAT: pollIntervalSeconds {Original} out of range [1, 60] — clamped to {Clamped}.",
                        cat.PollIntervalSeconds, clamped);
                    sanitisedCat = sanitisedCat with { PollIntervalSeconds = clamped };
                }

                // Warn on unknown rigModel (daemon handles graceful disable, no 400 here).
                if (cat.RigModel is not ("SerialCat" or "RigCtld"))
                {
                    configApiLogger.LogWarning(
                        "CAT: unrecognised rigModel '{RigModel}' — CAT will be disabled at runtime.",
                        cat.RigModel);
                }

                if (!ReferenceEquals(sanitisedCat, cat))
                    config = config with { Cat = sanitisedCat };
            }

            // ── TX config validation (ft8-qso-answerer-v1) ─────────────────────
            if (config.Tx is { } txIn)
            {
                var sanitisedTx = txIn;

                // WatchdogMinutes < 1 → CancelAfter(TimeSpan.Zero) = immediate cancellation.
                if (txIn.WatchdogMinutes < 1)
                {
                    configApiLogger.LogWarning(
                        "TX: watchdogMinutes {Original} below minimum (1) — clamped to 1.",
                        txIn.WatchdogMinutes);
                    sanitisedTx = sanitisedTx with { WatchdogMinutes = 1 };
                }

                if (txIn.RetryCount < 1)
                {
                    configApiLogger.LogWarning(
                        "TX: retryCount {Original} below minimum (1) — clamped to 1.",
                        txIn.RetryCount);
                    sanitisedTx = sanitisedTx with { RetryCount = 1 };
                }

                if (!ReferenceEquals(sanitisedTx, txIn))
                    config = config with { Tx = sanitisedTx };
            }

            await store.SaveAsync(config, ct);
            return TypedResults.Ok(store.Current);
        });

        app.MapPost("/api/v1/decode/start", async (
            IConfigStore store,
            CancellationToken ct) =>
        {
            if (store.Current.AudioDeviceId is null)
                return Results.BadRequest(
                    "No audio device configured. Select a device in Settings before starting decoding.");

            await store.SaveAsync(store.Current with { DecodingEnabled = true }, ct);
            var freqStart = ResolveEffectiveFrequency(catState, store.Current);
            return TypedResults.Ok(new DaemonStatus(
                State:               "Running",
                Version:             AssemblyVersion.Get(),
                AudioDevice:         store.Current.AudioDeviceFriendlyName ?? store.Current.AudioDeviceId,
                CaptureActive:       captureManager?.IsCapturing ?? false,
                AudioActive:         audioMonitor?.IsActive ?? false,
                DecodingEnabled:     store.Current.DecodingEnabled,
                DialFrequencyMHz:    freqStart,
                CatConnectionStatus: catState?.Status.ToString() ?? "Disabled"));
        });

        app.MapPost("/api/v1/decode/stop", async (
            IConfigStore store,
            CancellationToken ct) =>
        {
            await store.SaveAsync(store.Current with { DecodingEnabled = false }, ct);
            var freqStop = ResolveEffectiveFrequency(catState, store.Current);
            return TypedResults.Ok(new DaemonStatus(
                State:               "Running",
                Version:             AssemblyVersion.Get(),
                AudioDevice:         store.Current.AudioDeviceFriendlyName ?? store.Current.AudioDeviceId,
                CaptureActive:       captureManager?.IsCapturing ?? false,
                AudioActive:         audioMonitor?.IsActive ?? false,
                DecodingEnabled:     store.Current.DecodingEnabled,
                DialFrequencyMHz:    freqStop,
                CatConnectionStatus: catState?.Status.ToString() ?? "Disabled"));
        });

        // ── Frequency list endpoints (FR-042) ─────────────────────────────────

        app.MapGet("/api/v1/frequencies", (IFrequencyStore freqStore) =>
            TypedResults.Ok(freqStore.Entries.ToList()));

        app.MapPost("/api/v1/frequencies", async (
            HttpRequest       request,
            IFrequencyStore   freqStore,
            CancellationToken ct) =>
        {
            List<FrequencyEntry>? entries;
            try
            {
                entries = await request.ReadFromJsonAsync(
                    AppJsonContext.Default.ListFrequencyEntry, ct);
            }
            catch (JsonException)
            {
                return Results.BadRequest("Malformed JSON — expected an array of frequency entries.");
            }

            if (entries is null)
                return Results.BadRequest("Missing or empty request body.");

            await freqStore.SaveAsync(entries, ct);
            return TypedResults.Ok(freqStore.Entries.ToList());
        });

        // ── Tune endpoint (FR-045) ────────────────────────────────────────────

        var tuneLogger = app.Services.GetRequiredService<ILoggerFactory>()
                                     .CreateLogger("OpenWSFZ.Web.TuneApi");

        // Capture ICatTuner from the service container (may be null in tests or when CAT is disabled).
        // Captured here rather than as a handler parameter to avoid the RequestDelegateGenerator
        // mistakenly treating a nullable interface as a JSON-bound body parameter.
        var catTuner = app.Services.GetService<ICatTuner>();

        // Capture ICatController (lifecycle control — retry on demand).
        var catController = app.Services.GetService<ICatController>();

        // Capture IQsoController (may be null in tests or when the TX subsystem is not wired).
        var qsoController = app.Services.GetService<IQsoController>();

        // Capture AudioOffsetEventBus (may be null in tests that don't register it).
        var audioOffsetEventBus = app.Services.GetService<AudioOffsetEventBus>();

        app.MapPost("/api/v1/tune", async (
            HttpRequest       request,
            IConfigStore      store,
            CancellationToken ct) =>
        {
            TuneRequest? body;
            try
            {
                body = await request.ReadFromJsonAsync(AppJsonContext.Default.TuneRequest, ct);
            }
            catch (JsonException)
            {
                return Results.BadRequest("Malformed JSON.");
            }

            if (body?.FrequencyMHz is not { } freq)
                return Results.BadRequest("Missing or non-numeric frequencyMHz.");

            if (freq < 0)
                return Results.BadRequest("frequencyMHz must not be negative.");

            var status = catState?.Status ?? CatConnectionStatus.Disabled;

            if (status is CatConnectionStatus.Connected or CatConnectionStatus.Connecting)
            {
                // CAT active path: command the rig; ICatTuner updates CatState optimistically.
                if (catTuner is null)
                {
                    tuneLogger.LogWarning(
                        "POST /api/v1/tune: CAT status is {Status} but no ICatTuner is registered.",
                        status);
                    return Results.Problem(
                        statusCode: StatusCodes.Status502BadGateway,
                        detail: "CAT tuner service is not available.");
                }

                try
                {
                    await catTuner.SetDialFrequencyAsync(freq, ct);
                }
                catch (Exception ex)
                {
                    tuneLogger.LogWarning(ex,
                        "POST /api/v1/tune: SetDialFrequencyAsync({FreqMHz}) failed: {Message}",
                        freq, ex.Message);
                    return Results.Problem(
                        statusCode: StatusCodes.Status502BadGateway,
                        detail: "CAT set-frequency command failed.");
                }
            }
            else
            {
                // CAT inactive path: update the manual dial frequency config.
                var updated = store.Current with
                {
                    DecodeLog = (store.Current.DecodeLog ?? new DecodeLogConfig())
                                    with { DialFrequencyMHz = freq }
                };
                await store.SaveAsync(updated, ct);
            }

            return TypedResults.Ok(new TuneResponse(freq));
        });

        // ── CAT retry endpoint (FR-034) ───────────────────────────────────────

        app.MapPost("/api/v1/cat/retry", () =>
        {
            if (catController is null)
                return Results.Problem(
                    statusCode: StatusCodes.Status503ServiceUnavailable,
                    detail: "CAT polling service is not available.");

            catController.TriggerRetry();
            return Results.NoContent();
        });

        // ── Audio offset endpoint ─────────────────────────────────────────────

        app.MapPost("/api/v1/audio-offset", async (
            HttpRequest   request,
            IConfigStore  store,
            CancellationToken ct) =>
        {
            AudioOffsetRequest? body;
            try
            {
                body = await request.ReadFromJsonAsync(AppJsonContext.Default.AudioOffsetRequest, ct);
            }
            catch (JsonException)
            {
                return Results.BadRequest("Malformed JSON.");
            }

            if (body is null)
                return Results.BadRequest("Missing or empty request body.");

            if (body.RxHz < 0 || body.RxHz > 3000)
                return Results.BadRequest($"rxHz {body.RxHz} is out of range [0, 3000].");

            if (body.TxHz < 0 || body.TxHz > 3000)
                return Results.BadRequest($"txHz {body.TxHz} is out of range [0, 3000].");

            var currentTx = store.Current.Tx ?? new TxConfig();
            var updated   = store.Current with
            {
                Tx = currentTx with
                {
                    RxAudioOffsetHz = body.RxHz,
                    TxAudioOffsetHz = body.TxHz,
                    HoldTxFreq      = body.HoldTxFreq,
                }
            };
            await store.SaveAsync(updated, ct);

            audioOffsetEventBus?.Publish(body.RxHz, body.TxHz, body.HoldTxFreq);

            return TypedResults.Ok(new AudioOffsetRequest(body.RxHz, body.TxHz, body.HoldTxFreq));
        });

        // ── TX / QSO answerer endpoints (FR-047) ─────────────────────────────

        app.MapGet("/api/v1/tx/status", (IConfigStore store) =>
        {
            var state              = qsoController?.State   ?? QsoState.Idle;
            var partner            = qsoController?.Partner;
            var autoAnswerEnabled  = store.Current.Tx?.AutoAnswer ?? false;
            return TypedResults.Ok(new TxStatusResponse(state.ToString(), partner, autoAnswerEnabled));
        });

        app.MapPost("/api/v1/tx/enable", async (IConfigStore store, CancellationToken ct) =>
        {
            var currentTx = store.Current.Tx ?? new TxConfig();
            await store.SaveAsync(store.Current with { Tx = currentTx with { AutoAnswer = true } }, ct);
            var state   = qsoController?.State  ?? QsoState.Idle;
            var partner = qsoController?.Partner;
            return TypedResults.Ok(new TxStatusResponse(state.ToString(), partner, AutoAnswerEnabled: true));
        });

        app.MapPost("/api/v1/tx/disable", async (IConfigStore store, CancellationToken ct) =>
        {
            var currentTx = store.Current.Tx ?? new TxConfig();
            await store.SaveAsync(store.Current with { Tx = currentTx with { AutoAnswer = false } }, ct);
            var state   = qsoController?.State  ?? QsoState.Idle;
            var partner = qsoController?.Partner;
            return TypedResults.Ok(new TxStatusResponse(state.ToString(), partner, AutoAnswerEnabled: false));
        });

        app.MapPost("/api/v1/tx/abort", async (IConfigStore store, CancellationToken ct) =>
        {
            if (qsoController is not null)
                await qsoController.AbortAsync(ct);

            // D-TX-UI-001: disarm after abort. Idempotent with the save in
            // SafeAbortToIdleAsync — both write the same value; no conflict.
            var currentTx = store.Current.Tx ?? new TxConfig();
            await store.SaveAsync(store.Current with { Tx = currentTx with { AutoAnswer = false } }, ct);

            var state   = qsoController?.State  ?? QsoState.Idle;
            var partner = qsoController?.Partner;
            return TypedResults.Ok(new TxStatusResponse(state.ToString(), partner, AutoAnswerEnabled: false));
        });

        // ── POST /api/v1/tx/answer-cq (TX-D01 phase-aware CQ answer) ──────────

        app.MapPost("/api/v1/tx/answer-cq", async (
            HttpRequest   request,
            CancellationToken ct) =>
        {
            if (qsoController is null)
                return Results.Problem("TX controller not available.", statusCode: 503);

            if (qsoController.State != QsoState.Idle)
                return Results.Conflict();

            AnswerCqRequest? req;
            try
            {
                req = await request.ReadFromJsonAsync(AppJsonContext.Default.AnswerCqRequest, ct);
            }
            catch (JsonException)
            {
                return Results.BadRequest("Malformed JSON.");
            }

            if (req is null)
                return Results.BadRequest("Missing or empty request body.");

            if (!DateTimeOffset.TryParse(
                    req.CqCycleStartUtc,
                    null,
                    System.Globalization.DateTimeStyles.RoundtripKind,
                    out var cqCycleStart))
            {
                return Results.BadRequest("cqCycleStartUtc is not a valid ISO 8601 date-time.");
            }

            await qsoController.AnswerCqAsync(req.Callsign, req.FrequencyHz, cqCycleStart, ct);

            var txState   = qsoController.State;
            var txPartner = qsoController.Partner;
            return TypedResults.Ok(new TxStatusResponse(txState.ToString(), txPartner, AutoAnswerEnabled: true));
        });

        // ── WebSocket Endpoint ────────────────────────────────────────────────

        // Create a per-class logger from the DI container after the app is built.
        // audioMonitor is captured from the outer scope (closure); it is null in tests
        // that don't wire up audio capture.
        var wsLogger = app.Services.GetRequiredService<ILoggerFactory>()
                                   .CreateLogger("OpenWSFZ.Web.WebSocketHub");

        // Wire the static broadcast logger used by the fire-and-forget path.
        WebSocketHub.SetBroadcastLogger(wsLogger);

        // B3: construct a singleton AudioWatchdog so all connected clients share one
        // instance. Per-connection watchdogs would cause N concurrent pipeline restarts
        // when N clients are connected and the audio goes silent.
        var audioWatchdog = captureManager is not null && restartPipeline is not null
            ? new AudioWatchdog(
                  isCapturing: () => captureManager.IsCapturing,
                  onRestart:   restartPipeline,
                  threshold:   3)
            : null;

        // S1: abort only this app instance's WebSocket connections at the start of
        // ApplicationStopping so the browser UI goes dark immediately at Ctrl+C.
        // Registered here (inside Create, before the caller's ApplicationStopping hooks)
        // so it fires first — before the capture pipeline's semaphore wait and teardown.
        // The scope guard ensures that a test-infrastructure app (e.g. WebApplicationFactory)
        // cannot abort sockets owned by a concurrently-running integration-test server.
        app.Lifetime.ApplicationStopping.Register(() => WebSocketHub.AbortAll(appScope));

        // Captured once so the WebSocket handler can gate new connections without
        // closing over the WebApplication reference itself.
        var appStopping = app.Lifetime.ApplicationStopping;

        app.MapGet("/api/v1/ws", async (HttpContext ctx, IConfigStore store) =>
        {
            if (!ctx.WebSockets.IsWebSocketRequest)
            {
                ctx.Response.StatusCode = StatusCodes.Status400BadRequest;
                return;
            }

            // S2: reject new WebSocket upgrade requests once shutdown has started.
            // Without this gate, the browser's 1-second reconnect timer can fire
            // while Kestrel is still draining, establishing a new connection that
            // was never covered by AbortAll — holding up process exit indefinitely.
            // A 503 response causes ws.js's exponential back-off to take over, so
            // the browser stops hammering the dying process.
            if (appStopping.IsCancellationRequested)
            {
                ctx.Response.StatusCode = StatusCodes.Status503ServiceUnavailable;
                return;
            }

            using var ws = await ctx.WebSockets.AcceptWebSocketAsync();
            await WebSocketHub.HandleAsync(
                ws, store, audioMonitor, dataFlowMonitor,
                captureManager, audioWatchdog, catState,
                wsLogger, appScope, ctx.RequestAborted);
        });

        return app;
    }

    /// <summary>
    /// Resolves the effective dial frequency using the three-tier rule (FR-039):
    ///   1. Live in-session CAT value (<see cref="ICatState.DialFrequencyMHz"/> — non-null)
    ///   2. Persisted last-known CAT value (<see cref="CatConfig.LastPolledFrequencyMHz"/>),
    ///      only when <c>cat.enabled</c> is <c>true</c>
    ///   3. Operator's manual fallback (<see cref="DecodeLogConfig.DialFrequencyMHz"/>)
    /// </summary>
    public static double ResolveEffectiveFrequency(ICatState? catState, AppConfig config)
    {
        if (catState?.DialFrequencyMHz is { } live)
            return live;

        var cat = config.Cat;
        if (cat is { Enabled: true, LastPolledFrequencyMHz: { } persisted })
            return persisted;

        return config.DecodeLog?.DialFrequencyMHz ?? 0.0;
    }
}

/// <summary>
/// In-memory <see cref="IConfigStore"/> used as the default in tests and when
/// no persistent store is supplied to <see cref="WebApp.Create"/>.
/// </summary>
internal sealed class InMemoryConfigStore : IConfigStore
{
    private volatile AppConfig _current;

    public InMemoryConfigStore(AppConfig? initial = null)
        => _current = initial ?? new AppConfig();

    public AppConfig Current => _current;

    public event Action<AppConfig>? OnSaved;

    public Task SaveAsync(AppConfig config, CancellationToken ct = default)
    {
        _current = config;
        OnSaved?.Invoke(config);
        return Task.CompletedTask;
    }
}

/// <summary>
/// In-memory <see cref="IAudioDeviceProvider"/> that always returns an empty list.
/// Used as the default in tests.
/// </summary>
internal sealed class InMemoryAudioDeviceProvider : IAudioDeviceProvider
{
    private readonly IReadOnlyList<AudioDeviceInfo> _devices;

    public InMemoryAudioDeviceProvider(IReadOnlyList<AudioDeviceInfo>? devices = null)
        => _devices = devices ?? [];

    public Task<IReadOnlyList<AudioDeviceInfo>> GetDevicesAsync(CancellationToken ct = default)
        => Task.FromResult(_devices);
}

/// <summary>
/// In-memory <see cref="IAudioOutputDeviceProvider"/> that always returns an empty list.
/// Used as the default in tests.
/// </summary>
internal sealed class InMemoryAudioOutputDeviceProvider : IAudioOutputDeviceProvider
{
    private readonly IReadOnlyList<AudioDeviceInfo> _devices;

    public InMemoryAudioOutputDeviceProvider(IReadOnlyList<AudioDeviceInfo>? devices = null)
        => _devices = devices ?? [];

    public Task<IReadOnlyList<AudioDeviceInfo>> GetDevicesAsync(CancellationToken ct = default)
        => Task.FromResult(_devices);
}

/// <summary>
/// In-memory <see cref="IFrequencyStore"/> used as the default in tests and when
/// no persistent store is supplied to <see cref="WebApp.Create"/>.
/// </summary>
internal sealed class InMemoryFrequencyStore : IFrequencyStore
{
    private volatile IReadOnlyList<FrequencyEntry> _entries;

    public InMemoryFrequencyStore(IReadOnlyList<FrequencyEntry>? initial = null)
        => _entries = initial ?? [];

    public IReadOnlyList<FrequencyEntry> Entries => _entries;

    public Task SaveAsync(IReadOnlyList<FrequencyEntry> entries, CancellationToken ct = default)
    {
        _entries = entries;
        return Task.CompletedTask;
    }
}
