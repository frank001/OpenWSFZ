using System.Net;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Web;

/// <summary>
/// Bind policy for LAN remote access: resolves to <c>0.0.0.0</c> (all IPv4 interfaces)
/// so the web interface is reachable from other devices on the local network.
/// Activated when <c>RemoteAccess.Enabled = true</c>.
/// </summary>
public sealed class LanBindPolicy : IBindPolicy
{
    private readonly ILogger<LanBindPolicy> _logger;

    public LanBindPolicy(ILogger<LanBindPolicy> logger)
        => _logger = logger;

    /// <inheritdoc />
    /// <remarks>
    /// Always returns an endpoint bound to <see cref="IPAddress.Any"/> (0.0.0.0),
    /// regardless of the <paramref name="desired"/> address.
    /// </remarks>
    public IPEndPoint Resolve(IPAddress desired, int port)
    {
        var endpoint = new IPEndPoint(IPAddress.Any, port);
        _logger.LogInformation(
            "LanBindPolicy: binding Kestrel to {Endpoint} (LAN access enabled).",
            endpoint);
        return endpoint;
    }
}
