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

    public async Task InitializeAsync()
    {
        // Port 0 → OS assigns an ephemeral port.
        _app = OpenWSFZ.Web.WebApp.Create(port: 0);
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
