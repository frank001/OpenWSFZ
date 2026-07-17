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
    /// <param name="shimVersion">
    /// The native FT8 decoder shim's actual loaded ABI version, surfaced as
    /// <see cref="DaemonStatus.ShimVersion"/> on <c>GET /api/v1/status</c> and the initial
    /// WebSocket <c>status</c> event (daemon-status-visibility). Callers should read
    /// <c>Ft8Decoder.LoadedShimVersion</c> once at startup and pass it here; defaults to 0
    /// for callers (e.g. minimal test fixtures) that do not wire up the native shim.
    /// </param>
    /// <param name="hashTableRejectCountProvider">
    /// Live provider for the native hash-table reject count, surfaced as
    /// <see cref="DaemonStatus.HashTableRejectCount"/> on <c>GET /api/v1/status</c> and the
    /// initial WebSocket <c>status</c> event (f-005-hash-table-saturation-diagnostic, D2).
    /// Unlike <paramref name="shimVersion"/> this value changes over the session, so it is
    /// supplied as a delegate and invoked fresh on each read (callers pass
    /// <c>() =&gt; ft8Decoder.GetHashTableRejectCount()</c>). Defaults to <c>null</c> →
    /// reported as 0 for callers (e.g. minimal test fixtures) that do not wire up the native shim.
    /// </param>
    /// <param name="appScope">
    /// App-instance scope GUID to tag every WebSocket connection accepted through this
    /// instance's <c>/api/v1/ws</c> endpoint (N6). Pass this when a bus that broadcasts
    /// before <see cref="Create"/> runs (e.g. <c>DecodeEventBus</c>, constructed directly in
    /// <c>Program.cs</c> ahead of the web host) must carry the same scope as the sockets this
    /// call will register. Defaults to <c>null</c>, in which case a fresh GUID is minted, as
    /// before.
    /// </param>
    public static WebApplication Create(
        int port,
        IBindPolicy?                                        bindPolicy                  = null,
        IConfigStore?                                       configStore                 = null,
        IFrequencyStore?                                    frequencyStore              = null,
        IPropModeStore?                                     propModeStore               = null,
        IAdifLogWriter?                                     adifLogWriter               = null,
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
        Action<IServiceCollection>?                         configureServices           = null,
        int                                                  shimVersion                 = 0,
        Func<int>?                                           hashTableRejectCountProvider = null,
        Guid?                                                appScope                    = null)
    {
        // S1: unique scope ID for this WebApp instance, used to tag every WebSocket
        // connection accepted through this app's /api/v1/ws endpoint.  AbortAll(scope)
        // only aborts connections belonging to this instance, preventing test-infrastructure
        // apps (e.g. WebApplicationFactory) from aborting sockets owned by a concurrently
        // running integration-test server.
        //
        // N6: use the caller-supplied value when given — Program.cs generates one up front
        // so DecodeEventBus, constructed before WebApp.Create runs, can carry the same scope
        // as the sockets this call registers — otherwise mint one, as before.
        var scope = appScope ?? Guid.NewGuid();

        // CatEventBus carries scope so BroadcastCatStatus only delivers to sockets
        // belonging to this WebApp instance (scope guard — mirrors AbortAll pattern).
        var catEventBus = new CatEventBus(scope);

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

        builder.Services.AddSingleton<IPropModeStore>(
            propModeStore ?? new InMemoryPropModeStore());

        // Decode-filter store (decode-panel-filtering): always in-memory, never persisted —
        // no test/production override parameter exists because there is only ever one kind
        // of implementation (design.md Decision 3). Registered here, before configureServices
        // runs, so QsoAnswererService/QsoCallerService factories (added via configureServices
        // in Program.cs) can resolve IDecodeFilterStore from the same container.
        builder.Services.AddSingleton<IDecodeFilterStore, DecodeFilterStore>();

        // engagement-target-validation: default pass-through registered here (before
        // configureServices below), so any caller that doesn't wire up
        // ICallsignRegionStore/ICallsignGrammarStore (test fixtures, minimal hosts) still gets a
        // resolvable IEngagementTargetValidator that behaves exactly like today (no rejections) —
        // mirrors the IAuthPolicy/NullAuthPolicy default-then-override pattern below. Daemon's
        // Program.cs overrides this via configureServices with the real, store-backed validator.
        builder.Services.AddSingleton<IEngagementTargetValidator, NullEngagementTargetValidator>();

        // IAdifLogWriter: supplied explicitly by callers that need to capture writes (qso-log-dialog).
        // When null, the endpoint returns 503 (no writer available) — which is the correct behaviour
        // for test instances that do not wire the TX subsystem.
        if (adifLogWriter is not null)
            builder.Services.AddSingleton<IAdifLogWriter>(adifLogWriter);

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

            // SEC-002B: Allow genuine WebSocket upgrade requests to /api/v1/ws through
            // the auth middleware.  Auth for non-loopback WS connections is delegated to
            // the first WS message frame (see the /api/v1/ws handler below and
            // WebSocketHub.AuthenticateViaFrameAsync).
            //
            // IMPORTANT: the path scope (/api/v1/ws) is required.  Without it, any REST
            // request that carries the 'Upgrade: websocket' header would bypass auth
            // entirely (F1 — QA review R1).  Plain HTTP GETs, REST calls, and any
            // other path that happens to carry the header still go through normal
            // credential gating and return 401.
            bool isWebSocketUpgrade =
                ctx.Request.Path.StartsWithSegments("/api/v1/ws", StringComparison.OrdinalIgnoreCase) &&
                ctx.Request.Headers.TryGetValue("Upgrade", out var upgradeValues) &&
                upgradeValues.ToString().Equals("websocket", StringComparison.OrdinalIgnoreCase);

            if (isWebSocketUpgrade)
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

                var returnUrl = Uri.EscapeDataString(ctx.Request.Path.Value ?? "/");
                ctx.Response.Redirect($"/login.html?return={returnUrl}");
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
                CatConnectionStatus: catState?.Status.ToString() ?? "Disabled",
                ShimVersion:         shimVersion,
                HashTableRejectCount: hashTableRejectCountProvider?.Invoke() ?? 0));
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

            // Guard against the same STJ source-generation quirk documented in
            // JsonConfigStore.Load(): a JSON payload that omits "logging" or "decodeLog"
            // deserialises those non-nullable properties to null instead of falling back
            // to their initialisers. Left unguarded here, a null DecodeLog persists into
            // the live in-memory config and crashes every subsequent decode cycle
            // (D-010: unguarded NRE in AllTxtWriter.AppendAsync).
            if (config.Logging is null)
                config = config with { Logging = new LoggingConfig() };
            if (config.DecodeLog is null)
                config = config with { DecodeLog = new DecodeLogConfig() };
            if (config.DecodeNoiseSuppression is null)
                config = config with { DecodeNoiseSuppression = new DecodeNoiseSuppressionConfig() };
            if (config.ExternalReporting is null)
                config = config with { ExternalReporting = new ExternalReportingConfig() };
            // Ptt gets a different fallback than the four guards above: web/js/settings.js
            // never sends a "ptt" key at all (there is deliberately no Settings-page UI for
            // it — design.md Decision 6), so EVERY Settings-page save hits this branch, not
            // just a hypothetical missing-key edge case. Defaulting to a fresh new PttConfig()
            // here would silently revert an operator's manually-edited ptt.method (e.g.
            // "CatCommand") back to "AudioVox" on the very next unrelated save (toggling
            // showCycleCountdown, etc.) — reproducing the exact stuck-on-VOX symptom this fix
            // exists to prevent. Falling back to the already-persisted store.Current.Ptt
            // instead makes an omitted "ptt" key a true no-op: whatever was on disk before
            // this save stays there. store.Current.Ptt is itself never null by this point
            // (JsonConfigStore.Load() and SaveAsync both guard it), so the ?? new PttConfig()
            // is pure defense-in-depth, not the expected path.
            if (config.Ptt is null)
                config = config with { Ptt = store.Current.Ptt ?? new PttConfig() };

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
                if (txIn.WatchdogMinutes > 60)
                {
                    configApiLogger.LogWarning(
                        "TX: watchdogMinutes {Original} exceeds maximum (60) — clamped to 60.",
                        txIn.WatchdogMinutes);
                    sanitisedTx = sanitisedTx with { WatchdogMinutes = 60 };
                }

                // RetryCount = 0 means unlimited; watchdog is the backstop.
                if (txIn.RetryCount < 0)
                {
                    configApiLogger.LogWarning(
                        "TX: retryCount {Original} below minimum (0) — clamped to 0.",
                        txIn.RetryCount);
                    sanitisedTx = sanitisedTx with { RetryCount = 0 };
                }
                if (txIn.RetryCount > 200)
                {
                    configApiLogger.LogWarning(
                        "TX: retryCount {Original} exceeds maximum (200) — clamped to 200.",
                        txIn.RetryCount);
                    sanitisedTx = sanitisedTx with { RetryCount = 200 };
                }

                if (!ReferenceEquals(sanitisedTx, txIn))
                    config = config with { Tx = sanitisedTx };
            }

            // ── Decoder config validation (decoder-settings-page) ───────────────
            if (config.Decoder is { } decoderIn)
            {
                var sanitisedDecoder = decoderIn;

                // Clamp kMinScorePass2 to [5, 30].
                if (decoderIn.KMinScorePass2 < 5 || decoderIn.KMinScorePass2 > 30)
                {
                    var clamped = Math.Clamp(decoderIn.KMinScorePass2, 5, 30);
                    configApiLogger.LogWarning(
                        "Decoder: kMinScorePass2 {Original} out of range [5, 30] — clamped to {Clamped}.",
                        decoderIn.KMinScorePass2, clamped);
                    sanitisedDecoder = sanitisedDecoder with { KMinScorePass2 = clamped };
                }

                // Clamp osdCorrThreshold to [0.05, 0.40].
                if (decoderIn.OsdCorrThreshold < 0.05f || decoderIn.OsdCorrThreshold > 0.40f)
                {
                    var clamped = Math.Clamp(decoderIn.OsdCorrThreshold, 0.05f, 0.40f);
                    configApiLogger.LogWarning(
                        "Decoder: osdCorrThreshold {Original} out of range [0.05, 0.40] — clamped to {Clamped}.",
                        decoderIn.OsdCorrThreshold, clamped);
                    sanitisedDecoder = sanitisedDecoder with { OsdCorrThreshold = clamped };
                }

                // Clamp osdNhardMax to [30, 100].
                if (decoderIn.OsdNhardMax < 30 || decoderIn.OsdNhardMax > 100)
                {
                    var clamped = Math.Clamp(decoderIn.OsdNhardMax, 30, 100);
                    configApiLogger.LogWarning(
                        "Decoder: osdNhardMax {Original} out of range [30, 100] — clamped to {Clamped}.",
                        decoderIn.OsdNhardMax, clamped);
                    sanitisedDecoder = sanitisedDecoder with { OsdNhardMax = clamped };
                }

                if (!ReferenceEquals(sanitisedDecoder, decoderIn))
                    config = config with { Decoder = sanitisedDecoder };
            }

            // ── External reporting config validation (gridtracker-udp-reporting) ────
            // Any target with a port outside 1–65535 is rejected outright (HTTP 400, no
            // partial persistence) — unlike CAT/TX/Decoder above, which clamp with a warning.
            if (config.ExternalReporting is { } extRep)
            {
                foreach (var target in extRep.Targets)
                {
                    if (target.Port is < 1 or > 65535)
                    {
                        return Results.BadRequest(
                            $"externalReporting target '{target.Name}' has port {target.Port}, " +
                            "which is outside the valid range 1-65535.");
                    }
                }
            }

            // ── Remote access config validation (SEC-001 / D-LAN-006) ──────────────
            // The daemon refuses to start when Enabled = true and Passphrase is absent.
            // Reject the save here so the operator cannot commit an unlaunchable config.
            if (config.RemoteAccess is { Enabled: true } &&
                string.IsNullOrWhiteSpace(config.RemoteAccess.Passphrase))
            {
                return Results.BadRequest(
                    "A passphrase is required when remote access is enabled. " +
                    "Enter a passphrase before saving.");
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
                CatConnectionStatus: catState?.Status.ToString() ?? "Disabled",
                ShimVersion:         shimVersion,
                HashTableRejectCount: hashTableRejectCountProvider?.Invoke() ?? 0));
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
                CatConnectionStatus: catState?.Status.ToString() ?? "Disabled",
                ShimVersion:         shimVersion,
                HashTableRejectCount: hashTableRejectCountProvider?.Invoke() ?? 0));
        });

        // ── Decode filter endpoints (decode-panel-filtering) ──────────────────
        //
        // GET  /api/v1/decode-filter — returns the current daemon-owned filter state.
        // POST /api/v1/decode-filter — whole-object replace (matches the existing
        //      POST /api/v1/config convention), then broadcasts decodeFilterChanged to every
        //      connected client (including the one that issued the POST) so every open tab's
        //      popup and rendered table update immediately.

        app.MapGet("/api/v1/decode-filter", (IDecodeFilterStore filterStore) =>
            TypedResults.Ok(filterStore.Current));

        app.MapPost("/api/v1/decode-filter", async (
            HttpRequest        request,
            IDecodeFilterStore filterStore,
            CancellationToken  ct) =>
        {
            DecodeFilterState? state;
            try
            {
                state = await request.ReadFromJsonAsync(AppJsonContext.Default.DecodeFilterState, ct);
            }
            catch (JsonException)
            {
                return Results.BadRequest("Malformed JSON.");
            }

            if (state is null)
                return Results.BadRequest("Missing or empty request body.");

            filterStore.Set(state);
            WebSocketHub.BroadcastDecodeFilterChanged(scope, state);

            return TypedResults.Ok(filterStore.Current);
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

        // ── Propagation mode list endpoints (qso-log-dialog) ─────────────────

        app.MapGet("/api/v1/prop-modes", (IPropModeStore pmStore) =>
            TypedResults.Ok(pmStore.Entries.ToList()));

        app.MapPost("/api/v1/prop-modes", async (
            HttpRequest       request,
            IPropModeStore    pmStore,
            CancellationToken ct) =>
        {
            List<PropModeEntry>? entries;
            try
            {
                entries = await request.ReadFromJsonAsync(
                    AppJsonContext.Default.ListPropModeEntry, ct);
            }
            catch (JsonException)
            {
                return Results.BadRequest("Malformed JSON — expected an array of prop mode entries.");
            }

            if (entries is null)
                return Results.BadRequest("Missing or empty request body.");

            await pmStore.SaveAsync(entries, ct);
            return TypedResults.Ok(pmStore.Entries.ToList());
        });

        // ── Region data refresh + status + lookup endpoints (region-lookup-data-refresh) ──

        var regionRefreshLogger = app.Services.GetRequiredService<ILoggerFactory>()
                                     .CreateLogger("OpenWSFZ.Web.RegionDataRefreshApi");

        // This-session refresh history, captured by both the refresh endpoint (writer) and the
        // status endpoint (reader) via closure — same pattern as regionRefreshLogger above. No
        // new persistence: resets on daemon restart, consistent with "refresh is never
        // automatic" (f-006 §6.1). Not a static/singleton field — scoped to this WebApp instance
        // like every other captured variable in this method.
        var regionRefreshHasRun    = false;
        DateTimeOffset? regionRefreshLastUtc        = null;
        bool?           regionRefreshLastSucceeded  = null;
        string?         regionRefreshLastVersion    = null;
        string?         regionRefreshLastError      = null;

        app.MapPost("/api/v1/region-data/refresh", async (
            ICountryFileSource    source,
            ICountryFileConverter converter,
            ICallsignRegionStore  regionStore,
            CancellationToken     ct) =>
        {
            string xml;
            try
            {
                xml = await source.FetchAsync(ct);
            }
            catch (CountryFileFetchException ex)
            {
                regionRefreshLogger.LogWarning(ex,
                    "Region data refresh: fetch from country-files.com failed — existing data retained.");
                regionRefreshHasRun          = true;
                regionRefreshLastUtc         = DateTimeOffset.UtcNow;
                regionRefreshLastSucceeded   = false;
                regionRefreshLastError       = ex.Message;
                return Results.Problem(statusCode: StatusCodes.Status502BadGateway, detail: ex.Message);
            }

            IReadOnlyList<CallsignRegionEntry> converted;
            try
            {
                // Pass-through mode (prefixBlocksOnly: false): callsign-regions.json is never
                // committed to version control, so individual-callsign exception entries are
                // installed unfiltered (region-lookup-data-refresh, NFR-021 note in design.md).
                converted = converter.Convert(xml, prefixBlocksOnly: false);
            }
            catch (CountryFileConversionException ex)
            {
                regionRefreshLogger.LogWarning(ex,
                    "Region data refresh: conversion of fetched release failed — existing data retained.");
                regionRefreshHasRun          = true;
                regionRefreshLastUtc         = DateTimeOffset.UtcNow;
                regionRefreshLastSucceeded   = false;
                regionRefreshLastError       = ex.Message;
                return Results.Problem(statusCode: StatusCodes.Status502BadGateway, detail: ex.Message);
            }

            try
            {
                await regionStore.SaveAsync(converted, ct);
            }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
            {
                // f-006 §6.2: mirror the fetch/convert siblings above — a write failure (disk
                // full, permissions, AV lock) is logged and reported the same way, rather than
                // propagating as an unhandled 500. SaveAsync is atomic (write-temp-then-rename),
                // so existing region data is guaranteed untouched by a failed write.
                regionRefreshLogger.LogWarning(ex,
                    "Region data refresh: saving converted data failed — existing data retained.");
                regionRefreshHasRun          = true;
                regionRefreshLastUtc         = DateTimeOffset.UtcNow;
                regionRefreshLastSucceeded   = false;
                regionRefreshLastError       = ex.Message;
                return Results.Problem(statusCode: StatusCodes.Status502BadGateway, detail: ex.Message);
            }

            // Best-effort extraction of the release's VERyyyymmdd marker entry (see
            // cty-dat-format's version-tracking convention) so the operator can confirm which
            // release was installed. Absent or unrecognised → null, not a failure.
            var releaseVersion = converted
                .Select(e => e.PrefixStart)
                .FirstOrDefault(alias =>
                    alias.Length == 11 &&
                    alias.StartsWith("VER", StringComparison.Ordinal) &&
                    alias[3..].All(char.IsAsciiDigit))
                ?[3..];

            // regionStore.Entries.Count (not converted.Count): CallsignRegionStore.SaveAsync may
            // silently top up a synthetic Q-series entry the converted release doesn't carry (see
            // its remarks) — report what's actually active after the save, not the pre-save count,
            // so the two numbers can never quietly disagree.
            var activeCount = regionStore.Entries.Count;

            regionRefreshHasRun         = true;
            regionRefreshLastUtc        = DateTimeOffset.UtcNow;
            regionRefreshLastSucceeded  = true;
            regionRefreshLastVersion    = releaseVersion;
            regionRefreshLastError      = null;

            regionRefreshLogger.LogInformation(
                "Region data refresh succeeded: {Count} entries installed (release {Version}).",
                activeCount, releaseVersion ?? "unknown");

            return TypedResults.Ok(new RegionRefreshResponse(true, activeCount, releaseVersion));
        });

        // GET /api/v1/region-data/status (f-006 §6.1): operator-facing summary of the active
        // region table and this session's refresh history — no GUI reachability existed for the
        // refresh capability until this endpoint + the "Region data" settings tab were added.
        // EffectiveSuppressUnknownRegion (decode-noise-suppression, task 3.4) reuses this same
        // entry-count check via DecodeNoiseSuppressionDefaults — the single source of truth also
        // consulted by OpenWSFZ.Daemon's DecodeNoiseSuppressionFilter — so the settings page never
        // computes or duplicates this logic itself.
        app.MapGet("/api/v1/region-data/status", (ICallsignRegionStore regionStore, IConfigStore configStore) =>
            TypedResults.Ok(new RegionDataStatusResponse(
                EntryCount:               regionStore.Entries.Count,
                HasRefreshedThisSession:  regionRefreshHasRun,
                LastRefreshUtc:           regionRefreshLastUtc,
                LastRefreshSucceeded:     regionRefreshLastSucceeded,
                LastReleaseVersion:       regionRefreshLastVersion,
                LastErrorMessage:         regionRefreshLastError,
                EffectiveSuppressUnknownRegion: DecodeNoiseSuppressionDefaults.ResolveEffectiveSuppressUnknownRegion(
                    configStore.Current.DecodeNoiseSuppression.SuppressUnknownRegion, regionStore))));

        // GET /api/v1/region-data/lookup?callsign={token} (f-006 §6.4): read-only diagnostic —
        // resolves a callsign against the active region table using the same longest-prefix-match
        // logic the decode pipeline uses (ICallsignRegionStore.TryGetRegion), so an operator can
        // confirm coverage or investigate an "Unknown" result without decoding a live signal.
        app.MapGet("/api/v1/region-data/lookup", (string? callsign, ICallsignRegionStore regionStore) =>
        {
            if (string.IsNullOrWhiteSpace(callsign))
                return Results.BadRequest("Missing or empty callsign query parameter.");

            var region = regionStore.TryGetRegion(callsign);

            return TypedResults.Ok(region is null
                ? new RegionLookupResponse(false, null, null, null, null, false)
                : new RegionLookupResponse(true, region.Entity, region.Continent, region.CqZone, region.ItuZone, region.Synthetic));
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

        // Capture IPttController (cat-tx-ptt, task 17.3) — the currently-running singleton
        // resolved by Program.cs's Ptt.Method switch at DI-registration time. May be null in
        // test fixtures that don't wire the TX subsystem; POST /api/v1/ptt/test treats that
        // the same as "nothing to test" (503). A newly-selected ptt.method only takes effect
        // after a daemon restart (remote-daemon-restart: no longer requires physical/console
        // access — see POST /api/v1/system/restart below).
        var pttController = app.Services.GetService<IPttController>();

        // Capture IDaemonRelauncher (remote-daemon-restart) — the narrow seam
        // POST /api/v1/system/restart spawns a replacement process through. Null in test
        // fixtures that don't register one; the endpoint logs and refuses to proceed rather
        // than throwing, exactly like the pttController/qsoController null-guards above.
        var daemonRelauncher = app.Services.GetService<IDaemonRelauncher>();

        // Capture IQsoRoleSwitcher for runtime role switching (Call CQ, task 11.5).
        // Null in tests that register a plain IQsoController stub rather than the full router.
        var qsoRoleSwitcher = app.Services.GetService<IQsoRoleSwitcher>();

        // Capture AudioOffsetEventBus (may be null in tests that don't register it).
        var audioOffsetEventBus = app.Services.GetService<AudioOffsetEventBus>();

        // Capture IAdifLogWriter (may be null in tests that don't wire the TX subsystem).
        // Using a different local name to avoid shadowing the method parameter of the same name.
        var adifLogSvc = app.Services.GetService<IAdifLogWriter>();

        // Capture ILogFileSource (log-viewer). May be null in tests that don't wire up
        // LoggingPipeline — both endpoints below treat that the same as "no active log file".
        var logFileSource = app.Services.GetService<ILogFileSource>();

        // ── GET /api/v1/logs/tail (log-viewer) ────────────────────────────────
        // Returns the last N lines (default 150, capped at 1000) of the daemon's currently
        // active log file. Returns an empty array with HTTP 200 — never an error — when file
        // logging is disabled or no log file has been created yet.
        const int DefaultTailLines = 150;
        const int MaxTailLines     = 1000;

        app.MapGet("/api/v1/logs/tail", (int? lines) =>
        {
            var requested = Math.Clamp(lines ?? DefaultTailLines, 1, MaxTailLines);
            var path      = logFileSource?.CurrentLogFilePath;

            if (path is null || !File.Exists(path))
                return TypedResults.Ok(new LogTailResponse([]));

            try
            {
                // FileShare.ReadWrite: the Serilog file sink (buffered, same process) may hold
                // the file open for writing concurrently — this read must not be blocked by that.
                using var fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite);
                using var sr = new StreamReader(fs);
                var allLines = sr.ReadToEnd()
                                  .Split('\n')
                                  .Select(l => l.TrimEnd('\r'))
                                  .ToArray();

                var tail = allLines.Length > requested
                    ? allLines[^requested..]
                    : allLines;
                return TypedResults.Ok(new LogTailResponse(tail));
            }
            catch (IOException)
            {
                // Rotation/deletion raced with this read — treat as "nothing to show" rather
                // than surfacing a transient filesystem error to the operator.
                return TypedResults.Ok(new LogTailResponse([]));
            }
        });

        // ── GET /api/v1/logs/full (log-viewer) ────────────────────────────────
        // Returns the complete current contents of the daemon's currently active log file as
        // plain text. Returns an empty body with HTTP 200 when no active log file exists.
        app.MapGet("/api/v1/logs/full", () =>
        {
            var path = logFileSource?.CurrentLogFilePath;

            if (path is null || !File.Exists(path))
                return Results.Text(string.Empty, "text/plain");

            try
            {
                using var fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite);
                using var sr = new StreamReader(fs);
                return Results.Text(sr.ReadToEnd(), "text/plain");
            }
            catch (IOException)
            {
                return Results.Text(string.Empty, "text/plain");
            }
        });

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

        // ── PTT test endpoint (cat-tx-ptt, task 17.3, FR-057) ─────────────────
        //
        // Fires a brief (~250 ms), silent (zero-amplitude) software PTT pulse against the
        // currently-running IPttController singleton: assert → tiny silence buffer → release.
        // Pass means the assert/release commands were accepted without throwing — it does NOT
        // mean the rig visibly keyed (IRadioConnection.SetPttAsync defines no read-back; see
        // its own doc comment). The operator must still watch the rig.
        //
        // Safety-critical (design.md Decision 6 amendment): this is a second, independent
        // caller of the same DI singleton QsoAnswererService/QsoCallerService already drive.
        // Layer 1 here rejects with 409 while a real QSO is keying; layer 2 (CatPttController/
        // SerialRtsDtrPttController's own SemaphoreSlim, task 17.2) closes the remaining race
        // for any request that gets past this check just as a real transmission begins.
        const int PttTestSampleRate    = 48_000;
        const int PttTestDurationMs    = 250;
        var       pttTestSilence       = new float[PttTestSampleRate * PttTestDurationMs / 1000];

        app.MapPost("/api/v1/ptt/test", async (IConfigStore store, CancellationToken ct) =>
        {
            if (qsoController?.Keying == true)
                return Results.Problem(
                    statusCode: StatusCodes.Status409Conflict,
                    detail: "a QSO is currently transmitting");

            var method = store.Current.Ptt?.Method ?? "AudioVox";
            if (string.Equals(method, "AudioVox", StringComparison.OrdinalIgnoreCase))
                return Results.Problem(
                    statusCode: StatusCodes.Status409Conflict,
                    detail: "PTT method is AudioVox — OpenWSFZ never asserts PTT itself in this " +
                            "mode (the rig's own VOX keys from audio), so there is nothing to test.");

            if (pttController is null)
                return Results.Problem(
                    statusCode: StatusCodes.Status503ServiceUnavailable,
                    detail: "PTT controller is not available.");

            try
            {
                pttController.LoadAudio(pttTestSilence);
                await pttController.KeyDownAsync(ct).ConfigureAwait(false);
                await pttController.KeyUpAsync(ct).ConfigureAwait(false);
                return TypedResults.Ok(new PttTestResponse("pass"));
            }
            catch (Exception ex)
            {
                // Expected, handleable outcome (a real CAT/serial failure) — not a server
                // error, so HTTP 200 with an error payload rather than a 500 (task 17.3).
                return TypedResults.Ok(new PttTestResponse("error", ex.Message));
            }
        });

        // ── System restart endpoint (remote-daemon-restart) ──────────────────
        //
        // Restarts the daemon process in place: spawns a fresh instance of itself (same
        // executable/args, tagged --relaunched-from — see IDaemonRelauncher), then gracefully
        // stops the current instance via the existing, unmodified ApplicationStopping shutdown
        // chain so the new instance can bind the listening port. Refuses with 409 while a real
        // QSO is transmitting (design.md Decision 5) — same guard, same message style as
        // /api/v1/ptt/test above. Responds 202 immediately; the actual spawn-then-stop runs on
        // a fire-and-forget delayed task (design.md Decision 3) so the HTTP response has time
        // to flush to the client before the connection is torn down.
        var systemRestartLogger = app.Services.GetRequiredService<ILoggerFactory>()
                                              .CreateLogger("OpenWSFZ.Web.SystemRestartApi");
        const int RestartFlushDelayMs = 500;

        app.MapPost("/api/v1/system/restart", () =>
        {
            if (qsoController?.Keying == true)
                return Results.Problem(
                    statusCode: StatusCodes.Status409Conflict,
                    detail: "a QSO is currently transmitting");

            _ = Task.Run(async () =>
            {
                await Task.Delay(RestartFlushDelayMs).ConfigureAwait(false);

                if (daemonRelauncher is null)
                {
                    systemRestartLogger.LogError(
                        "POST /api/v1/system/restart: no IDaemonRelauncher is registered — " +
                        "cannot restart.");
                    return;
                }

                // Spawn-before-stop ordering (design.md Decision 3): only stop the current
                // instance once the replacement has been confirmed to start, so the daemon is
                // never left with zero running instances.
                if (daemonRelauncher.TrySpawnReplacement())
                    app.Lifetime.StopApplication();
            });

            return Results.Accepted(uri: (string?)null, value: new SystemRestartResponse("restarting"));
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
            var state                = qsoController?.State   ?? QsoState.Idle;
            var partner              = qsoController?.Partner;
            var autoAnswerEnabled    = store.Current.Tx?.AutoAnswer ?? false;
            var role                 = qsoController?.Role.ToString().ToLowerInvariant() ?? "answerer";
            var callerPartnerSelect  = store.Current.Tx?.CallerPartnerSelect.ToString() ?? "First";
            var keying               = qsoController?.Keying ?? false;
            return TypedResults.Ok(new TxStatusResponse(state.ToString(), partner, autoAnswerEnabled, role, callerPartnerSelect, keying));
        });

        app.MapPost("/api/v1/tx/enable", async (IConfigStore store, CancellationToken ct) =>
        {
            var currentTx = store.Current.Tx ?? new TxConfig();
            await store.SaveAsync(store.Current with { Tx = currentTx with { AutoAnswer = true } }, ct);
            var state               = qsoController?.State  ?? QsoState.Idle;
            var partner             = qsoController?.Partner;
            var role                = qsoController?.Role.ToString().ToLowerInvariant() ?? "answerer";
            var callerPartnerSelect = store.Current.Tx?.CallerPartnerSelect.ToString() ?? "First";
            var keying              = qsoController?.Keying ?? false;
            return TypedResults.Ok(new TxStatusResponse(state.ToString(), partner, AutoAnswerEnabled: true, Role: role, CallerPartnerSelect: callerPartnerSelect, Keying: keying));
        });

        app.MapPost("/api/v1/tx/disable", async (IConfigStore store, CancellationToken ct) =>
        {
            var currentTx = store.Current.Tx ?? new TxConfig();
            await store.SaveAsync(store.Current with { Tx = currentTx with { AutoAnswer = false } }, ct);
            var state               = qsoController?.State  ?? QsoState.Idle;
            var partner             = qsoController?.Partner;
            var role                = qsoController?.Role.ToString().ToLowerInvariant() ?? "answerer";
            var callerPartnerSelect = store.Current.Tx?.CallerPartnerSelect.ToString() ?? "First";
            var keying              = qsoController?.Keying ?? false;
            return TypedResults.Ok(new TxStatusResponse(state.ToString(), partner, AutoAnswerEnabled: false, Role: role, CallerPartnerSelect: callerPartnerSelect, Keying: keying));
        });

        app.MapPost("/api/v1/tx/abort", async (IConfigStore store, CancellationToken ct) =>
        {
            if (qsoController is not null)
                await qsoController.AbortAsync(ct);

            // D-TX-UI-001: disarm after abort. Idempotent with the save in
            // SafeAbortToIdleAsync — both write the same value; no conflict.
            var currentTx = store.Current.Tx ?? new TxConfig();
            await store.SaveAsync(store.Current with { Tx = currentTx with { AutoAnswer = false } }, ct);

            var state               = qsoController?.State  ?? QsoState.Idle;
            var partner             = qsoController?.Partner;
            var role                = qsoController?.Role.ToString().ToLowerInvariant() ?? "answerer";
            var callerPartnerSelect = store.Current.Tx?.CallerPartnerSelect.ToString() ?? "First";
            var keying              = qsoController?.Keying ?? false;
            return TypedResults.Ok(new TxStatusResponse(state.ToString(), partner, AutoAnswerEnabled: false, Role: role, CallerPartnerSelect: callerPartnerSelect, Keying: keying));
        });

        // ── POST /api/v1/tx/stop-cq (qso-controller — Call CQ graceful stop) ──
        //
        // Requests a graceful stop: any in-progress TX sample completes normally, then the
        // service returns to Idle. Unlike /abort, this does NOT hardcode
        // AutoAnswerEnabled: false in the response — the service may still be mid-TX at the
        // time of the response, and the frontend does not act on this response directly;
        // it waits for the subsequent txState WebSocket event to reflect the completed stop.

        app.MapPost("/api/v1/tx/stop-cq", async (IConfigStore store, CancellationToken ct) =>
        {
            if (qsoController is null)
                return Results.Problem("TX controller not available.", statusCode: 503);

            await qsoController.GracefulStopAsync(ct);

            var state               = qsoController.State;
            var partner             = qsoController.Partner;
            var autoAnswerEnabled   = store.Current.Tx?.AutoAnswer ?? false;
            var role                = qsoController.Role.ToString().ToLowerInvariant();
            var callerPartnerSelect = store.Current.Tx?.CallerPartnerSelect.ToString() ?? "First";
            var keying              = qsoController.Keying;
            return TypedResults.Ok(new TxStatusResponse(
                state.ToString(), partner, autoAnswerEnabled, role, callerPartnerSelect, keying));
        });

        // ── POST /api/v1/tx/answer-cq (TX-D01 phase-aware CQ answer) ──────────

        app.MapPost("/api/v1/tx/answer-cq", async (
            HttpRequest   request,
            IConfigStore  store,
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

            var txState             = qsoController.State;
            var txPartner           = qsoController.Partner;
            var txRole              = qsoController.Role.ToString().ToLowerInvariant();
            var callerPartnerSelect = store.Current.Tx?.CallerPartnerSelect.ToString() ?? "First";
            var keying              = qsoController.Keying;
            return TypedResults.Ok(new TxStatusResponse(txState.ToString(), txPartner, AutoAnswerEnabled: true, Role: txRole, CallerPartnerSelect: callerPartnerSelect, Keying: keying));
        });

        // ── POST /api/v1/tx/select-responder (qso-caller, None mode) ─────────

        app.MapPost("/api/v1/tx/select-responder", async (
            HttpRequest       request,
            IConfigStore      store,
            CancellationToken ct) =>
        {
            if (qsoController is null)
                return Results.Problem("TX controller not available.", statusCode: 503);

            // 405 if active role is Answerer — this endpoint is caller-only.
            if (qsoController.Role != OpenWSFZ.Abstractions.QsoRole.Caller)
                return Results.StatusCode(405);

            // 409 if the caller is not in WaitAnswer (proxy: QsoState.WaitReport).
            if (qsoController.State != QsoState.WaitReport)
                return Results.Conflict();

            SelectResponderRequest? req;
            try
            {
                req = await request.ReadFromJsonAsync(AppJsonContext.Default.SelectResponderRequest, ct);
            }
            catch (JsonException)
            {
                return Results.BadRequest("Malformed JSON.");
            }

            if (req is null)
                return Results.BadRequest("Missing or empty request body.");

            if (!DateTimeOffset.TryParse(
                    req.ResponseCycleStartUtc,
                    null,
                    System.Globalization.DateTimeStyles.RoundtripKind,
                    out var responseCycleStart))
            {
                return Results.BadRequest("responseCycleStartUtc is not a valid ISO 8601 date-time.");
            }

            await qsoController.SelectResponderAsync(req.Callsign, req.FrequencyHz, responseCycleStart, ct);

            var txState             = qsoController.State;
            var txPartner           = qsoController.Partner;
            var txRole              = qsoController.Role.ToString().ToLowerInvariant();
            var callerPartnerSelect = store.Current.Tx?.CallerPartnerSelect.ToString() ?? "First";
            var keying              = qsoController.Keying;
            return TypedResults.Ok(new TxStatusResponse(txState.ToString(), txPartner, AutoAnswerEnabled: true, Role: txRole, CallerPartnerSelect: callerPartnerSelect, Keying: keying));
        });

        // ── POST /api/v1/tx/engage-decode (D-CALLER-012) ─────────────────────────────
        //
        // Atomically aborts any in-progress QSO and engages a new one based on the
        // double-clicked decode row.  Dispatches by message type:
        //
        //   CQ ...                 → AnswerCqAsync   (same as clicking a CQ row)
        //   OURS PARTNER -NN/+NN   → EngageAtAsync(SendReport)   → TxReport
        //   OURS PARTNER R±NN/RRR  → EngageAtAsync(SendRr73)     → Tx73/QsoComplete
        //   OURS PARTNER RR73      → EngageAtAsync(Send73)        → Tx73/QsoComplete
        //   OURS PARTNER 73        → abort only (QSO already done)
        //   Any other pattern      → 422 Unprocessable Entity

        var engageDecodeLogger = app.Services.GetRequiredService<ILoggerFactory>()
                                             .CreateLogger("OpenWSFZ.Web.EngageDecodeApi");

        app.MapPost("/api/v1/tx/engage-decode", async (
            HttpRequest   request,
            IConfigStore  store,
            IEngagementTargetValidator engagementValidator,
            CancellationToken ct) =>
        {
            if (qsoController is null)
                return Results.Problem("TX controller not available.", statusCode: 503);

            EngageDecodeRequest? req;
            try
            {
                req = await request.ReadFromJsonAsync(
                    AppJsonContext.Default.EngageDecodeRequest, ct);
            }
            catch (JsonException)
            {
                return Results.BadRequest("Malformed JSON.");
            }

            if (req is null)
                return Results.BadRequest("Missing or empty request body.");

            if (!DateTimeOffset.TryParse(
                    req.CycleStartUtc,
                    null,
                    System.Globalization.DateTimeStyles.RoundtripKind,
                    out var cycleStart))
            {
                return Results.BadRequest("cycleStartUtc is not a valid ISO 8601 date-time.");
            }

            // ── Abort-if-not-Idle helper ───────────────────────────────────────────
            //
            // dev-task 2026-07-17-engagement-target-validation-qa-review-findings (Finding F):
            // this used to run unconditionally as "Step 1", ahead of engagement-target-validation's
            // check below — so a rejected target's prior in-progress QSO was aborted for nothing
            // before the operator even saw the confirmation prompt. Now called only once a target
            // is known Allowed (or explicitly confirmed), immediately before the dispatch that
            // actually consumes the abort. The 73/not-addressed-to-us paths below don't validate a
            // target at all, so they still abort unconditionally, same as before.
            async Task<IResult?> AbortIfNotIdleAsync()
            {
                if (qsoController.State != QsoState.Idle)
                {
                    await qsoController.AbortAsync(ct).ConfigureAwait(false);

                    // SafeAbortToIdleAsync runs on the background service thread; poll until
                    // the state propagates.  2-second deadline is generous: in practice
                    // KeyUpAsync completes in <100 ms.
                    var deadline = DateTimeOffset.UtcNow.AddSeconds(2);
                    while (qsoController.State != QsoState.Idle
                           && DateTimeOffset.UtcNow < deadline)
                    {
                        await Task.Delay(10, ct).ConfigureAwait(false);
                    }

                    if (qsoController.State != QsoState.Idle)
                    {
                        return Results.Problem(
                            "QSO did not abort in time; please retry.",
                            statusCode: 503);
                    }
                }
                return null;
            }

            // ── Parse message and dispatch ────────────────────────────────────────

            var txConfig     = store.Current.Tx ?? new TxConfig();
            var ourCallsign  = txConfig.Callsign ?? string.Empty;
            var ourBase      = ourCallsign.Split('/')[0];    // strip /P, /M suffixes

            var tokens = req.Message.Trim().Split(
                ' ', StringSplitOptions.RemoveEmptyEntries);

            if (tokens.Length < 2)
                return Results.UnprocessableEntity();

            // ── Case A: CQ row ────────────────────────────────────────────────────
            if (tokens[0].Equals("CQ", StringComparison.OrdinalIgnoreCase))
            {
                // CQ PARTNER GRID  →  partner = tokens[1]
                // CQ DX PARTNER    →  partner = tokens[2]
                // CQ modifier PARTNER [GRID]  →  partner = tokens[2]
                var partnerCallsign = tokens.Length >= 4 ? tokens[2] : tokens[1];

                // engagement-target-validation: soft block with explicit operator override
                // (design.md Decision 4) — a human is looking at this specific row. Validated
                // BEFORE any abort (Finding F) — a rejected target must leave a prior in-progress
                // QSO completely untouched.
                var cqValidation = engagementValidator.Validate(partnerCallsign);
                if (!cqValidation.IsAllowed && !req.Confirm)
                {
                    // dev-task 2026-07-17-engagement-target-validation-live-verification-findings
                    // (Finding B): logged so a live rejection is diagnosable from the daemon log
                    // alone — the reason previously only reached the HTTP response body, which
                    // ASP.NET Core's request logging never captures.
                    engageDecodeLogger.LogInformation(
                        "engage-decode: rejecting CQ-row engagement target '{Callsign}' — {Reason}",
                        partnerCallsign, cqValidation.RejectionReason);
                    return Results.Json(
                        new EngagementRejectedResponse(cqValidation.RejectionReason ?? "Rejected."),
                        AppJsonContext.Default.EngagementRejectedResponse,
                        statusCode: StatusCodes.Status409Conflict);
                }

                var abortResult = await AbortIfNotIdleAsync().ConfigureAwait(false);
                if (abortResult is not null)
                    return abortResult;

                await qsoController.AnswerCqAsync(
                    partnerCallsign, req.FrequencyHz, cycleStart, ct).ConfigureAwait(false);
            }

            // ── Case B: Directed message TO us ────────────────────────────────────
            else if (tokens.Length >= 3
                     && (tokens[0].Equals(ourCallsign, StringComparison.OrdinalIgnoreCase)
                         || tokens[0].Equals(ourBase,   StringComparison.OrdinalIgnoreCase)))
            {
                var partner = tokens[1];
                var info    = tokens[2];

                static bool IsPlainSnr(string s) =>
                    s.Length == 3
                    && (s[0] == '+' || s[0] == '-')
                    && char.IsDigit(s[1])
                    && char.IsDigit(s[2]);

                static bool IsRReport(string s) =>
                    s.Length >= 4
                    && s[0] == 'R'
                    && IsPlainSnr(s[1..]);

                static bool IsGridSquare(string s) =>
                    (s.Length == 4 || s.Length == 6)
                    && char.IsLetter(s[0]) && char.IsLetter(s[1])
                    && char.IsDigit(s[2])  && char.IsDigit(s[3])
                    && (s.Length == 4 || (char.IsLetter(s[4]) && char.IsLetter(s[5])));

                if (info.Equals("73", StringComparison.OrdinalIgnoreCase))
                {
                    // QSO already complete — abort only.  Return Idle.  No transmission on this
                    // path — engagement-target-validation does not apply, so no target to validate
                    // before aborting.
                    var abortResult = await AbortIfNotIdleAsync().ConfigureAwait(false);
                    if (abortResult is not null)
                        return abortResult;
                }
                else
                {
                    // Every remaining recognised-payload branch below transmits — validate the
                    // target once, up front (design.md Decision 4: soft block with explicit
                    // operator override, since a human is looking at this specific row), BEFORE any
                    // abort (Finding F) — same rationale as the CQ-row branch above.
                    var directedValidation = engagementValidator.Validate(partner);
                    if (!directedValidation.IsAllowed && !req.Confirm)
                    {
                        // See the CQ-row branch above — same rationale (Finding B).
                        engageDecodeLogger.LogInformation(
                            "engage-decode: rejecting directed-message engagement target '{Callsign}' — {Reason}",
                            partner, directedValidation.RejectionReason);
                        return Results.Json(
                            new EngagementRejectedResponse(directedValidation.RejectionReason ?? "Rejected."),
                            AppJsonContext.Default.EngagementRejectedResponse,
                            statusCode: StatusCodes.Status409Conflict);
                    }

                    var abortResult = await AbortIfNotIdleAsync().ConfigureAwait(false);
                    if (abortResult is not null)
                        return abortResult;

                    if (info.Equals("RR73", StringComparison.OrdinalIgnoreCase))
                    {
                        await qsoController.EngageAtAsync(
                            partner, req.FrequencyHz, cycleStart, EngagePoint.Send73, info, ct)
                            .ConfigureAwait(false);
                    }
                    else if (info.Equals("RRR", StringComparison.OrdinalIgnoreCase) || IsRReport(info))
                    {
                        await qsoController.EngageAtAsync(
                            partner, req.FrequencyHz, cycleStart, EngagePoint.SendRr73, info, ct)
                            .ConfigureAwait(false);
                    }
                    else if (IsPlainSnr(info))
                    {
                        await qsoController.EngageAtAsync(
                            partner, req.FrequencyHz, cycleStart, EngagePoint.SendReport, info, ct)
                            .ConfigureAwait(false);
                    }
                    else if (IsGridSquare(info))
                    {
                        // OURCALL PARTNER GRID: partner is answering our CQ with their grid square.
                        // Semantically equivalent to a plain-SNR first exchange — respond with our report.
                        await qsoController.EngageAtAsync(
                            partner, req.FrequencyHz, cycleStart, EngagePoint.SendReport, info, ct)
                            .ConfigureAwait(false);
                    }
                    else
                    {
                        // Unrecognised payload (e.g. CQ or free-text bleed-through). Already
                        // aborted above (this is not a validated-target rejection — the abort here
                        // matches this endpoint's pre-existing behaviour for malformed payloads).
                        return Results.UnprocessableEntity();
                    }
                }
            }

            // ── Case C: Message not addressed to us ───────────────────────────────
            else
            {
                // No target to validate on this path — abort unconditionally, same as before.
                var abortResult = await AbortIfNotIdleAsync().ConfigureAwait(false);
                if (abortResult is not null)
                    return abortResult;

                return Results.UnprocessableEntity();
            }

            // ── Step 3: Return new state ──────────────────────────────────────────
            var state               = qsoController.State;
            var partner_out         = qsoController.Partner;
            var role                = qsoController.Role.ToString().ToLowerInvariant();
            var callerPartnerSelect = store.Current.Tx?.CallerPartnerSelect.ToString() ?? "First";
            var autoAnswer          = store.Current.Tx?.AutoAnswer ?? false;
            var keying               = qsoController.Keying;

            return TypedResults.Ok(new TxStatusResponse(
                state.ToString(),
                partner_out,
                AutoAnswerEnabled: autoAnswer,
                Role:              role,
                CallerPartnerSelect: callerPartnerSelect,
                Keying:            keying));
        });

        // ── POST /api/v1/tx/call-cq (Call CQ button — runtime role switch) ────

        app.MapPost("/api/v1/tx/call-cq", async (IConfigStore store, CancellationToken ct) =>
        {
            // 503 if TX subsystem is not wired (e.g. minimal test fixture).
            if (qsoController is null)
                return Results.Problem("TX controller not available.", statusCode: 503);

            // 409 if any QSO is already in progress.
            if (qsoController.State != QsoState.Idle)
                return Results.Conflict();

            if (qsoRoleSwitcher is not null)
            {
                // Full router path: switches to Caller and arms AutoAnswer atomically.
                await qsoRoleSwitcher.SwitchToCallerAsync(ct);
            }
            else
            {
                // Fallback path: no router wired (test fixtures with plain IQsoController stub).
                // Just set AutoAnswer = true; the role field in the response is always "caller".
                var currentTx = store.Current.Tx ?? new TxConfig();
                await store.SaveAsync(
                    store.Current with { Tx = currentTx with { AutoAnswer = true } }, ct);
            }

            var newState            = qsoController.State;
            var newPartner          = qsoController.Partner;
            var callerPartnerSelect = store.Current.Tx?.CallerPartnerSelect.ToString() ?? "First";
            var keying              = qsoController.Keying;
            return TypedResults.Ok(new TxStatusResponse(
                newState.ToString(), newPartner, AutoAnswerEnabled: true, Role: "caller",
                CallerPartnerSelect: callerPartnerSelect, Keying: keying));
        });

        // ── POST /api/v1/tx/caller-partner-select (FR-PILEUP-001) ────────────

        app.MapPost("/api/v1/tx/caller-partner-select", async (
            HttpRequest  request,
            IConfigStore store,
            CancellationToken ct) =>
        {
            CallerPartnerSelectRequest? body;
            try
            {
                body = await request.ReadFromJsonAsync(
                    AppJsonContext.Default.CallerPartnerSelectRequest, ct);
            }
            catch (JsonException)
            {
                return Results.BadRequest("Malformed JSON.");
            }

            if (body is null || (body.Mode != "First" && body.Mode != "None"))
                return Results.BadRequest("mode must be \"First\" or \"None\"");

            var parsedMode = body.Mode == "First"
                ? CallerPartnerSelectMode.First
                : CallerPartnerSelectMode.None;

            var currentTx = store.Current.Tx ?? new TxConfig();
            await store.SaveAsync(
                store.Current with { Tx = currentTx with { CallerPartnerSelect = parsedMode } }, ct);

            var state   = qsoController?.State  ?? QsoState.Idle;
            var partner = qsoController?.Partner;
            var role    = qsoController?.Role.ToString().ToLowerInvariant() ?? "answerer";
            var keying  = qsoController?.Keying ?? false;
            return TypedResults.Ok(new TxStatusResponse(
                state.ToString(), partner,
                AutoAnswerEnabled: store.Current.Tx?.AutoAnswer ?? false,
                Role: role,
                CallerPartnerSelect: body.Mode,
                Keying: keying));
        });

        // ── POST /api/v1/tx/log-qso (qso-log-dialog) ─────────────────────────

        app.MapPost("/api/v1/tx/log-qso", async (
            HttpRequest       request,
            IConfigStore      store,
            CancellationToken ct) =>
        {
            LogQsoRequest? req;
            try
            {
                req = await request.ReadFromJsonAsync(AppJsonContext.Default.LogQsoRequest, ct);
            }
            catch (JsonException)
            {
                return Results.BadRequest("Malformed JSON.");
            }

            if (req is null)
                return Results.BadRequest("Missing or empty request body.");

            if (adifLogSvc is null)
                return Results.Problem("ADIF log writer not available.", statusCode: 503);

            // Parse timestamps.
            if (!DateTime.TryParse(req.StartUtc, null,
                    System.Globalization.DateTimeStyles.RoundtripKind, out var startUtc))
                return Results.BadRequest("startUtc is not a valid ISO 8601 date-time.");

            if (!DateTime.TryParse(req.EndUtc, null,
                    System.Globalization.DateTimeStyles.RoundtripKind, out var endUtc))
                return Results.BadRequest("endUtc is not a valid ISO 8601 date-time.");

            // Build QsoRecord from the request body.
            var record = new QsoRecord
            {
                PartnerCallsign  = req.Callsign,
                PartnerGrid      = req.Grid,
                RstSent          = req.RstSent,
                RstRcvd          = req.RstRcvd,
                QsoStartUtc      = startUtc,
                QsoEndUtc        = endUtc,
                OperatorCallsign = req.OperatorCallsign,
                OperatorGrid     = store.Current.Tx?.Grid ?? string.Empty,
                DialFrequencyMHz = req.FreqMHz,
                PartnerName      = req.Name,
                TxPower          = req.TxPower,
                Comment          = req.Comment,
                PropMode         = req.PropMode,
                ExchSent         = req.ExchSent,
                ExchRcvd         = req.ExchRcvd,
            };

            // Write ADIF log entry.
            await adifLogSvc.AppendQsoAsync(record);

            // Update retained fields in config for any field whose retain flag is set.
            var currentTxForRetain = store.Current.Tx ?? new TxConfig();
            var needsSave = req.RetainTxPower || req.RetainComment || req.RetainPropMode;

            if (needsSave)
            {
                var updatedTx = currentTxForRetain with
                {
                    RetainedTxPower  = req.RetainTxPower  ? (req.TxPower  ?? string.Empty) : currentTxForRetain.RetainedTxPower,
                    RetainedComment  = req.RetainComment  ? (req.Comment  ?? string.Empty) : currentTxForRetain.RetainedComment,
                    RetainedPropMode = req.RetainPropMode ? (req.PropMode ?? string.Empty) : currentTxForRetain.RetainedPropMode,
                };
                await store.SaveAsync(store.Current with { Tx = updatedTx }, ct);
            }

            return TypedResults.Ok(new LogQsoResponse(Logged: true));
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
        app.Lifetime.ApplicationStopping.Register(() => WebSocketHub.AbortAll(scope));

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

            // SEC-002B: Authenticate non-loopback connections via the first WS frame.
            // Loopback connections (local browser accessing 127.0.0.1) bypass auth here
            // — they were already trusted by the auth middleware (D1).
            // A null RemoteIpAddress is treated as non-loopback and therefore requires
            // auth (F3 — QA review R1).  Under direct-Kestrel deployment this is
            // unreachable in production but we default to requiring auth rather than
            // granting silent trust for an unknown origin.
            var remoteIp = ctx.Connection.RemoteIpAddress;
            if (remoteIp is null || !IPAddress.IsLoopback(remoteIp))
            {
                if (!await WebSocketHub.AuthenticateViaFrameAsync(ws, authPolicy, ctx.RequestAborted))
                    return; // Socket already closed with code 4001 by AuthenticateViaFrameAsync.
            }

            await WebSocketHub.HandleAsync(
                ws, store, audioMonitor, dataFlowMonitor,
                captureManager, audioWatchdog, catState,
                wsLogger, scope, shimVersion,
                hashTableRejectCountProvider?.Invoke() ?? 0, ctx.RequestAborted);
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

internal sealed class InMemoryPropModeStore : IPropModeStore
{
    private volatile IReadOnlyList<PropModeEntry> _entries;

    public InMemoryPropModeStore(IReadOnlyList<PropModeEntry>? initial = null)
        => _entries = initial ?? [];

    public IReadOnlyList<PropModeEntry> Entries => _entries;

    public Task SaveAsync(IEnumerable<PropModeEntry> entries, CancellationToken ct = default)
    {
        _entries = entries.ToList();
        return Task.CompletedTask;
    }
}

/// <summary>
/// In-memory <see cref="IDecodeFilterStore"/> — the only implementation this app ever uses
/// (<c>decode-panel-filtering</c> capability, design.md Decision 3): there is no persisted
/// variant, unlike <see cref="IConfigStore"/>/<see cref="IFrequencyStore"/>, because the filter
/// is explicitly never written to disk and always resets to
/// <see cref="DecodeFilterState.Unfiltered"/> on daemon restart.
/// </summary>
internal sealed class DecodeFilterStore : IDecodeFilterStore
{
    private volatile DecodeFilterState _current = DecodeFilterState.Unfiltered;

    public DecodeFilterState Current => _current;

    public void Set(DecodeFilterState state) => _current = state;
}
