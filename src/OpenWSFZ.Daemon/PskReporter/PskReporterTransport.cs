using System.Net;
using System.Net.Sockets;

namespace OpenWSFZ.Daemon.PskReporter;

/// <summary>The upload's UDP socket: one per enabled period, every datagram through it.</summary>
internal interface IPskTransport : IDisposable
{
    /// <summary>Sends one datagram; throws on a DNS or socket error (the service logs it once per window and retries next window).</summary>
    Task SendAsync(byte[] datagram, CancellationToken ct);
}

/// <summary>Creates the transport for a host and port. Called once per enabled period, never per window.</summary>
internal delegate IPskTransport PskTransportFactory(string host, int port);

/// <summary>
/// The real transport: one IPv4 UDP socket, unbound (the OS picks the source port; it is NEVER bound to 4739), kept for the life of the
/// enabled period so the collector sees one source port. The host name is resolved at send time (so nothing resolves while disabled).
/// </summary>
internal sealed class UdpPskTransport : IPskTransport
{
    private readonly UdpClient _client = new(AddressFamily.InterNetwork);
    private readonly string _host;
    private readonly int _port;
    private readonly Func<string, CancellationToken, Task<IPAddress[]>> _resolve;

    public UdpPskTransport(string host, int port, Func<string, CancellationToken, Task<IPAddress[]>>? resolver = null)
    {
        _host    = host;
        _port    = port;
        _resolve = resolver ?? ((name, ct) => Dns.GetHostAddressesAsync(name, AddressFamily.InterNetwork, ct));
    }

    /// <summary>The local endpoint after the first send (for tests and diagnostics); <c>null</c> before it.</summary>
    public IPEndPoint? LocalEndPoint => _client.Client.IsBound ? (IPEndPoint?)_client.Client.LocalEndPoint : null;

    public async Task SendAsync(byte[] datagram, CancellationToken ct)
    {
        var addresses = await _resolve(_host, ct).ConfigureAwait(false);
        var v4 = addresses.FirstOrDefault(a => a.AddressFamily == AddressFamily.InterNetwork)
                 ?? throw new SocketException((int)SocketError.HostNotFound);
        await _client.SendAsync(datagram, new IPEndPoint(v4, _port), ct).ConfigureAwait(false);
    }

    public void Dispose() => _client.Dispose();
}
