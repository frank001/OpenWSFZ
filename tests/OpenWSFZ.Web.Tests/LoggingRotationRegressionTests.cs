using System.Net;
using FluentAssertions;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;
using OpenWSFZ.Abstractions;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// Host-level regression test for
/// dev-tasks/2026-07-29-fix-loggingconfig-null-rotationschedule-crash.md. Boots the real
/// <c>Program.cs</c> host (via <see cref="WebApplicationFactory{TEntryPoint}"/>, exercising the
/// actual <c>AddHostedService&lt;LogRotationService&gt;()</c> registration) with a
/// <see cref="LoggingConfig"/> whose <see cref="LoggingConfig.RotationSchedule"/> is
/// <see langword="null"/> — precisely what STJ source generation produced for a partial
/// <c>"logging"</c> JSON object before this dev-task's <c>[JsonConstructor]</c> fix — and asserts
/// the host starts and stays up rather than tearing itself down under
/// <c>BackgroundServiceExceptionBehavior.StopHost</c>.
/// </summary>
internal sealed class SeededConfigStore : IConfigStore
{
    private AppConfig _current;
    public SeededConfigStore(AppConfig initial) => _current = initial;
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
/// Same test-double substitutions as <see cref="WebTestFactory"/> (avoid touching the operator's
/// live <c>%APPDATA%\OpenWSFZ\</c> files / auth config during tests), but seeds
/// <see cref="IConfigStore"/> with a deliberately "corrupted" <see cref="LoggingConfig"/> instead
/// of the default.
/// </summary>
public sealed class NullRotationScheduleWebTestFactory : WebApplicationFactory<Program>
{
    private readonly string _logDirectory = Path.Combine(
        Path.GetTempPath(), "openwsfz-logrotregress-" + Path.GetRandomFileName());

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.ConfigureServices(services =>
        {
            services.RemoveAll<IConfigStore>();
            services.AddSingleton<IConfigStore>(new SeededConfigStore(new AppConfig
            {
                Logging = new LoggingConfig
                {
                    FileEnabled      = true,
                    Directory        = _logDirectory,
                    FileLogLevel     = "Debug",
                    // Simulates the pre-fix STJ result for a partial "logging" JSON object
                    // (dev-tasks/2026-07-29-fix-loggingconfig-null-rotationschedule-crash.md §2):
                    // rotationSchedule/rotationTime/rotationDayOfWeek/maxFiles all absent from the
                    // hand-edited JSON resolved to null/null/null/0 instead of their documented
                    // defaults. RotationSchedule = null is the one that reaches
                    // LogRotationService.CalculateNextBoundary's switch catch-all and, before the
                    // belt-and-braces fix in that method, produced a ~100-year Task.Delay that
                    // threw ArgumentOutOfRangeException and crashed the whole host.
                    RotationSchedule  = null!,
                    RotationTime      = null!,
                    RotationDayOfWeek = null!,
                    MaxFiles          = 0,
                },
            }));

            services.RemoveAll<IFrequencyStore>();
            services.AddSingleton<IFrequencyStore>(new TestFrequencyStore());

            services.RemoveAll<IPropModeStore>();
            services.AddSingleton<IPropModeStore>(new InMemoryPropModeStore());

            services.RemoveAll<IAdifLogWriter>();
            services.AddSingleton<IAdifLogWriter>(new NullAdifLogWriter());

            services.RemoveAll<ICatController>();
            services.AddSingleton<ICatController>(new TestCatController());

            services.RemoveAll<IAuthPolicy>();
            services.AddSingleton<IAuthPolicy, NullAuthPolicy>();
        });
    }

    protected override void Dispose(bool disposing)
    {
        base.Dispose(disposing);
        try { Directory.Delete(_logDirectory, recursive: true); } catch { /* best-effort */ }
    }
}

public sealed class LoggingRotationRegressionTests
    : IClassFixture<NullRotationScheduleWebTestFactory>
{
    private readonly HttpClient _client;

    public LoggingRotationRegressionTests(NullRotationScheduleWebTestFactory factory)
    {
        _client = factory.CreateClient(new WebApplicationFactoryClientOptions
        {
            BaseAddress = new Uri("http://127.0.0.1"),
        });
    }

    [Fact(DisplayName =
        "Regression: host with fileEnabled=true and a null RotationSchedule starts and stays up " +
        "(dev-tasks/2026-07-29-fix-loggingconfig-null-rotationschedule-crash.md)")]
    public async Task Host_WithNullRotationSchedule_StartsAndStaysUp()
    {
        // Triggers host startup (including LogRotationService.ExecuteAsync) on first request.
        // Pre-fix, the host would have already torn itself down by the time this call returns —
        // either this throws (connection refused / host faulted) or returns a non-200.
        var response = await _client.GetAsync("/api/v1/status");

        response.StatusCode.Should().Be(HttpStatusCode.OK,
            "the host must survive a null RotationSchedule, not crash under " +
            "BackgroundServiceExceptionBehavior.StopHost");

        // A second request after a short delay confirms the host is still alive — not merely
        // that it hadn't crashed *yet* at the moment of the first request.
        await Task.Delay(TimeSpan.FromMilliseconds(200));
        var second = await _client.GetAsync("/api/v1/status");
        second.StatusCode.Should().Be(HttpStatusCode.OK,
            "the host must remain up, not crash shortly after startup");
    }
}
