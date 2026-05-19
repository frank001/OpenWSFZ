using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.StaticFiles;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.FileProviders;
using Microsoft.Extensions.Hosting;
using OpenWSFZ.Abstractions;
using System.Net;

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
    public static WebApplication Create(int port, IBindPolicy? bindPolicy = null)
    {
        var builder = WebApplication.CreateBuilder();

        // Register services.
        builder.Services.AddSingleton<IBindPolicy>(
            sp => bindPolicy ?? new LoopbackBindPolicy(
                sp.GetRequiredService<Microsoft.Extensions.Logging.ILogger<LoopbackBindPolicy>>()));
        builder.Services.AddSingleton<IAuthPolicy, NullAuthPolicy>();

        // AOT-safe JSON serialisation.
        builder.Services.ConfigureHttpJsonOptions(opts =>
            opts.SerializerOptions.TypeInfoResolverChain.Insert(0, AppJsonContext.Default));

        // Kestrel: resolve endpoint via bind policy.
        builder.WebHost.ConfigureKestrel((_, kestrel) =>
        {
            var policy = bindPolicy ?? new LoopbackBindPolicy(
                kestrel.ApplicationServices
                    .GetRequiredService<Microsoft.Extensions.Logging.ILogger<LoopbackBindPolicy>>());
            var endpoint = policy.Resolve(IPAddress.Loopback, port);
            kestrel.Listen(endpoint);
        });

        // Logging: suppress noisy ASP.NET Core startup messages in production.
        builder.Logging.SetMinimumLevel(Microsoft.Extensions.Logging.LogLevel.Warning);

        var app = builder.Build();

        // Middleware pipeline.
        app.UseWebSockets();

        // Static files from the `web/` directory next to the executable.
        var webRoot = Path.Combine(AppContext.BaseDirectory, "web");
        if (Directory.Exists(webRoot))
        {
            app.UseStaticFiles(new StaticFileOptions
            {
                FileProvider = new PhysicalFileProvider(webRoot),
                RequestPath = string.Empty,
            });
        }

        // Endpoints.
        app.MapGet("/api/v1/status", () =>
            TypedResults.Ok(new DaemonStatus(State: "Running", Version: GetVersion())));

        app.MapGet("/api/v1/ws", async (HttpContext ctx) =>
        {
            if (!ctx.WebSockets.IsWebSocketRequest)
            {
                ctx.Response.StatusCode = StatusCodes.Status400BadRequest;
                return;
            }

            using var ws = await ctx.WebSockets.AcceptWebSocketAsync();
            await WebSocketHub.HandleAsync(ws, ctx.RequestAborted);
        });

        return app;
    }

    private static string GetVersion()
    {
        var asm = typeof(WebApp).Assembly;
        return asm.GetName().Version?.ToString() ?? "0.0.0";
    }
}
