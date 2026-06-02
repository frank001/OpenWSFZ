using System.Net.Sockets;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Rig.Internal;

namespace OpenWSFZ.Rig;

/// <summary>
/// Implements <see cref="IRadioConnection"/> over a TCP connection to a running
/// <c>rigctld</c> daemon (FR-031, FR-032).
///
/// <para>
/// The operator is responsible for starting <c>rigctld</c> before enabling this mode.
/// If <c>rigctld</c> is not reachable, <see cref="ConnectAsync"/> throws
/// <see cref="SocketException"/>.
/// </para>
///
/// <para>
/// Protocol: send <c>\get_freq\n</c>, read one response line containing the
/// frequency in Hz as a plain decimal integer (e.g. <c>14074000</c> → 14.074 MHz).
/// <c>rigctld</c> error responses begin with <c>RPRT</c> and cause
/// <see cref="InvalidOperationException"/> to be thrown.
/// </para>
///
/// <para>
/// Only the read-only frequency query is sent — no PTT, frequency-set, or
/// mode-set commands are issued.
/// </para>
/// </summary>
public sealed class RigctldConnection : IRadioConnection, IDisposable
{
    private readonly string          _host;
    private readonly int             _port;
    private readonly ITcpConnection  _tcp;

    private bool _connected;

    // ── Public constructor (production use) ───────────────────────────────────

    /// <summary>
    /// Creates a <see cref="RigctldConnection"/> targeting the specified host and port.
    /// </summary>
    /// <param name="rigctldHost">Hostname or IP of the <c>rigctld</c> daemon (default <c>"127.0.0.1"</c>).</param>
    /// <param name="rigctldPort">TCP port of the <c>rigctld</c> daemon (default <c>4532</c>).</param>
    public RigctldConnection(string rigctldHost = "127.0.0.1", int rigctldPort = 4532)
        : this(rigctldHost, rigctldPort, new TcpConnectionWrapper()) { }

    // ── Internal constructor (test use) ──────────────────────────────────────

    internal RigctldConnection(string host, int port, ITcpConnection tcpConnection)
    {
        _host = host;
        _port = port;
        _tcp  = tcpConnection;
    }

    // ── IRadioConnection ─────────────────────────────────────────────────────

    /// <inheritdoc/>
    public bool IsConnected => _connected;

    /// <summary>
    /// Opens a TCP connection to <c>rigctld</c>.
    /// </summary>
    /// <exception cref="SocketException">
    /// No process is listening on the configured host and port.
    /// </exception>
    public async Task ConnectAsync(CancellationToken cancellationToken = default)
    {
        await _tcp.ConnectAsync(_host, _port, cancellationToken).ConfigureAwait(false);
        _connected = true;
    }

    /// <summary>
    /// Sends <c>\get_freq\n</c>, reads the response line, and returns VFO-A
    /// frequency in MHz.
    /// </summary>
    /// <exception cref="InvalidOperationException">
    /// <c>rigctld</c> returned an error (<c>RPRT …</c>) or a non-numeric value.
    /// </exception>
    /// <exception cref="TimeoutException">
    /// No response arrived within 500 ms.
    /// </exception>
    public async Task<double> GetDialFrequencyMhzAsync(CancellationToken cancellationToken = default)
    {
        await _tcp.SendAsync(@"\get_freq" + "\n", cancellationToken).ConfigureAwait(false);
        var line = (await _tcp.ReceiveLineAsync(cancellationToken).ConfigureAwait(false)).Trim();

        if (line.StartsWith("RPRT", StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidOperationException(
                $"rigctld returned error response: '{line}'.");
        }

        if (!long.TryParse(line, out var hz) || hz < 0)
        {
            throw new InvalidOperationException(
                $"rigctld returned unexpected frequency value: '{line}'.");
        }

        return hz / 1_000_000.0;
    }

    /// <summary>Closes the TCP connection.</summary>
    public Task DisconnectAsync(CancellationToken cancellationToken = default)
    {
        _tcp.Close();
        _connected = false;
        return Task.CompletedTask;
    }

    // ── IDisposable ───────────────────────────────────────────────────────────

    /// <summary>Closes and disposes the TCP connection.</summary>
    public void Dispose()
    {
        try { _tcp.Close(); } catch { /* best-effort */ }
        _tcp.Dispose();
        _connected = false;
    }
}
