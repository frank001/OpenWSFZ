using System.Net;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Web;

/// <summary>
/// Phase 1 bind policy: forces all Kestrel listeners to <c>127.0.0.1</c>.
/// Any request for a non-loopback address is overridden and logged as a warning.
/// </summary>
public sealed class LoopbackBindPolicy : IBindPolicy
{
    private readonly ILogger<LoopbackBindPolicy> _logger;

    public LoopbackBindPolicy(ILogger<LoopbackBindPolicy> logger)
        => _logger = logger;

    /// <inheritdoc />
    public IPEndPoint Resolve(IPAddress desired, int port)
    {
        if (!desired.Equals(IPAddress.Loopback))
        {
            _logger.LogWarning(
                "LoopbackBindPolicy: requested bind address {Desired} overridden to 127.0.0.1 (NFR-004).",
                desired);
        }

        return new IPEndPoint(IPAddress.Loopback, port);
    }
}
