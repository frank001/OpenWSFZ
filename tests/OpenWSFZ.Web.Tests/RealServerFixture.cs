using Microsoft.AspNetCore.Hosting.Server;
using Microsoft.AspNetCore.Hosting.Server.Features;
using Microsoft.Extensions.DependencyInjection;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// Test fixture that starts <see cref="WebApp"/> against a real Kestrel listener
/// on an OS-assigned ephemeral port.  Required for WebSocket upgrade tests, which
/// cannot go through <c>TestServer</c>'s in-memory transport.
/// </summary>
public sealed class RealServerFixture : IAsyncLifetime
{
    private Microsoft.AspNetCore.Builder.WebApplication? _app;

    /// <summary>The port Kestrel actually bound to (available after <see cref="InitializeAsync"/>).</summary>
    public int Port { get; private set; }

    /// <summary>The host/IP Kestrel actually bound to (available after <see cref="InitializeAsync"/>).</summary>
    public string BoundHost { get; private set; } = string.Empty;

    /// <summary>
    /// App-instance scope (N6) generated for this fixture's <see cref="WebApp"/> and handed
    /// to <see cref="WebApp.Create"/> so it is the same value tagged onto every socket this
    /// server accepts. Tests that broadcast directly via <c>DecodeEventBus</c>/<c>TxEventBus</c>
    /// (rather than through a resolved DI singleton, which this bare
    /// <c>WebApp.Create(port: 0)</c> fixture does not register) must construct those buses with
    /// this scope so their broadcasts reach this fixture's sockets and no other concurrently
    /// running <see cref="WebApp"/> instance's sockets.
    /// </summary>
    public Guid AppScope { get; } = Guid.NewGuid();

    public async Task InitializeAsync()
    {
        // Port 0 → OS assigns an ephemeral port.
        _app = OpenWSFZ.Web.WebApp.Create(port: 0, appScope: AppScope);
        await _app.StartAsync();

        // Read back the actual bound address.
        var feature = _app.Services
            .GetRequiredService<IServer>()
            .Features.Get<IServerAddressesFeature>();

        var addr = feature?.Addresses.FirstOrDefault()
            ?? throw new InvalidOperationException("Server did not bind to any address.");

        var uri  = new Uri(addr);
        Port      = uri.Port;
        BoundHost = uri.Host;
    }

    public async Task DisposeAsync()
    {
        if (_app != null)
        {
            await _app.StopAsync();
            await _app.DisposeAsync();
        }
    }
}
