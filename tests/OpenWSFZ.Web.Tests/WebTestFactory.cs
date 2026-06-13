using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;
using OpenWSFZ.Abstractions;

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

            // Replace the production ICatController (backed by CatPollingService)
            // with a test double so POST /api/v1/cat/retry returns 204 and tests
            // can assert TriggerRetry() was called.
            services.RemoveAll<ICatController>();
            services.AddSingleton<ICatController>(CatController);
        });
    }
}
