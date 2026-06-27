using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Web;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// In-memory <see cref="ICatController"/> used by <see cref="WebTestFactory"/>.
/// Records <see cref="TriggerRetry"/> calls so endpoint tests can assert
/// that the service was invoked.
/// </summary>
internal sealed class TestCatController : ICatController
{
    private int _retryCount;

    /// <summary>Number of times <see cref="TriggerRetry"/> has been called.</summary>
    public int RetryCount => _retryCount;

    /// <inheritdoc/>
    public void TriggerRetry() => Interlocked.Increment(ref _retryCount);
}

/// <summary>
/// Integration-test factory for HTTP-only tests.  Uses <c>TestServer</c> (in-process,
/// no real socket) which is fast and sufficient for REST endpoint tests.
/// WebSocket upgrade tests use <see cref="RealServerFixture"/> instead.
/// </summary>
/// <remarks>
/// <para>
/// <see cref="WebApplicationFactory{TEntryPoint}"/> runs the full <c>Program.cs</c>
/// startup, which creates a file-backed <see cref="IConfigStore"/> and
/// <see cref="IFrequencyStore"/> rooted at the operator's live
/// <c>%APPDATA%\OpenWSFZ\</c> directory.  Any test that POSTs to
/// <c>/api/v1/config</c> or <c>/api/v1/frequencies</c> would therefore overwrite
/// the operator's settings on the development machine.
/// </para>
/// <para>
/// The <see cref="ConfigureWebHost"/> override replaces both singletons with
/// in-memory test doubles so that tests never touch the live files, regardless of
/// which HTTP endpoints are exercised.
/// </para>
/// </remarks>
public sealed class WebTestFactory : WebApplicationFactory<Program>
{
    /// <summary>
    /// Shared test double for <see cref="ICatController"/>.
    /// Exposed (internal — test assembly only) so endpoint tests can assert
    /// <see cref="TestCatController.RetryCount"/>.
    /// </summary>
    internal TestCatController CatController { get; } = new TestCatController();

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.ConfigureServices(services =>
        {
            // Remove the file-backed IConfigStore registered by Program.cs startup
            // and substitute an in-memory test double so that POST /api/v1/config
            // does not overwrite %APPDATA%\OpenWSFZ\config.json.
            services.RemoveAll<IConfigStore>();
            services.AddSingleton<IConfigStore>(new TestConfigStore());

            // Same isolation for IFrequencyStore: POST /api/v1/frequencies must
            // not overwrite %APPDATA%\OpenWSFZ\frequencies.json.
            services.RemoveAll<IFrequencyStore>();
            services.AddSingleton<IFrequencyStore>(new TestFrequencyStore());

            // Same isolation for IPropModeStore: POST /api/v1/prop-modes must not
            // write to %APPDATA%\OpenWSFZ\prop-modes.json during tests.
            services.RemoveAll<IPropModeStore>();
            services.AddSingleton<IPropModeStore>(new InMemoryPropModeStore());

            // Register a no-op IAdifLogWriter so POST /api/v1/tx/log-qso returns 200
            // rather than 503 in WebApplicationFactory tests (qso-log-dialog task 7.4).
            services.RemoveAll<IAdifLogWriter>();
            services.AddSingleton<IAdifLogWriter>(new NullAdifLogWriter());

            // Replace the production ICatController (backed by CatPollingService)
            // with a test double so POST /api/v1/cat/retry returns 204 and tests
            // can assert TriggerRetry() was called.
            services.RemoveAll<ICatController>();
            services.AddSingleton<ICatController>(CatController);

            // Restore NullAuthPolicy so tests are isolated from the operator's live
            // auth configuration.  PassphraseAuthPolicy (registered by Program.cs when
            // RemoteAccess is enabled in the live config) would reject all in-process
            // TestServer requests because RemoteIpAddress is null on the test transport,
            // defeating the loopback bypass.  Auth-middleware behaviour is already tested
            // in AuthMiddlewareTests using its own bespoke server instances.
            services.RemoveAll<IAuthPolicy>();
            services.AddSingleton<IAuthPolicy, NullAuthPolicy>();
        });
    }
}
