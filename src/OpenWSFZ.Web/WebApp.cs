using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.StaticFiles;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.FileProviders;
using Microsoft.Extensions.Hosting;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Audio;
using System.Collections.Generic;
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
        IBindPolicy?          bindPolicy      = null,
        IConfigStore?         configStore     = null,
        IAudioDeviceProvider? audioProvider   = null,
        CaptureManager?       captureManager  = null)
    {
        var builder = WebApplication.CreateBuilder();

        // ── Services ──────────────────────────────────────────────────────────

        builder.Services.AddSingleton<IBindPolicy>(
            sp => bindPolicy ?? new LoopbackBindPolicy(
                sp.GetRequiredService<Microsoft.Extensions.Logging.ILogger<LoopbackBindPolicy>>()));
        builder.Services.AddSingleton<IAuthPolicy, NullAuthPolicy>();

        builder.Services.AddSingleton<IConfigStore>(
            configStore ?? new InMemoryConfigStore());

        builder.Services.AddSingleton<IAudioDeviceProvider>(
            audioProvider ?? new InMemoryAudioDeviceProvider());

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

        // Logging: suppress noisy ASP.NET Core startup messages in production.
        builder.Logging.SetMinimumLevel(Microsoft.Extensions.Logging.LogLevel.Warning);

        var app = builder.Build();

        // ── Middleware ────────────────────────────────────────────────────────

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

        // ── REST Endpoints ────────────────────────────────────────────────────

        app.MapGet("/api/v1/status", (IConfigStore store) =>
            TypedResults.Ok(new DaemonStatus(
                State:         "Running",
                Version:       AssemblyVersion.Get(),
                AudioDevice:   store.Current.AudioDeviceName,
                CaptureActive: captureManager?.IsCapturing ?? false)));

        app.MapGet("/api/v1/audio/devices", async (
            IAudioDeviceProvider provider,
            CancellationToken ct) =>
        {
            var devices = new List<AudioDeviceInfo>(await provider.GetDevicesAsync(ct));
            return TypedResults.Ok(devices);
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

            await store.SaveAsync(config, ct);
            return TypedResults.Ok(store.Current);
        });

        // ── WebSocket Endpoint ────────────────────────────────────────────────

        app.MapGet("/api/v1/ws", async (HttpContext ctx, IConfigStore store) =>
        {
            if (!ctx.WebSockets.IsWebSocketRequest)
            {
                ctx.Response.StatusCode = StatusCodes.Status400BadRequest;
                return;
            }

            using var ws = await ctx.WebSockets.AcceptWebSocketAsync();
            await WebSocketHub.HandleAsync(ws, store, ctx.RequestAborted);
        });

        return app;
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
