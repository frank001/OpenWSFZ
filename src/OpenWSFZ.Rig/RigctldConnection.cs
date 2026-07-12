using System.Net.Sockets;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Rig.Internal;

namespace OpenWSFZ.Rig;

/// <summary>
/// Implements <see cref="IRadioConnection"/> over a TCP connection to a running
/// <c>rigctld</c> daemon (FR-031, FR-032, FR-045).
///
/// <para>
/// The operator is responsible for starting <c>rigctld</c> before enabling this mode.
/// If <c>rigctld</c> is not reachable, <see cref="ConnectAsync"/> throws
/// <see cref="SocketException"/>.
/// </para>
///
/// <para>
/// Protocol: each command–response pair is exchanged over the same persistent TCP
/// connection.  <see cref="GetDialFrequencyMhzAsync"/> sends <c>\get_freq\n</c> and
/// reads one decimal-integer Hz line.  <see cref="SetDialFrequencyMhzAsync"/> sends
/// <c>\set_freq &lt;Hz&gt;\n</c> and reads the <c>RPRT 0</c> acknowledgement that
/// <c>rigctld</c> sends for every command; an <c>RPRT -N</c> reply throws
/// <see cref="InvalidOperationException"/>.  <see cref="SetPttAsync"/> sends
/// <c>\set_ptt 1\n</c> / <c>\set_ptt 0\n</c> (FR-056) and consumes the <c>RPRT</c>
/// acknowledgement the same way.
/// </para>
/// </summary>
public sealed class RigctldConnection : IRadioConnection, IDisposable
{
    private readonly string          _host;
    private readonly int             _port;
    private readonly ITcpConnection  _tcp;

    private volatile bool _connected;

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

    /// <summary>
    /// Sends <c>\set_freq &lt;Hz&gt;\n</c> to command VFO-A to
    /// <paramref name="frequencyMHz"/> (FR-045), then reads and validates the
    /// <c>RPRT 0</c> acknowledgement that <c>rigctld</c> sends for every command.
    /// The Hz integer is rounded to the nearest integer.
    /// </summary>
    /// <exception cref="InvalidOperationException">
    /// <c>rigctld</c> returned a non-zero RPRT code (e.g. <c>RPRT -1</c>).
    /// </exception>
    /// <example>
    /// <c>14.074 MHz → \set_freq 14074000\n</c>
    /// </example>
    public async Task SetDialFrequencyMhzAsync(
        double            frequencyMHz,
        CancellationToken cancellationToken = default)
    {
        var hz      = (long)Math.Round(frequencyMHz * 1_000_000.0);
        var command = $@"\set_freq {hz}" + "\n";
        await _tcp.SendAsync(command, cancellationToken).ConfigureAwait(false);

        // rigctld acknowledges every command with an RPRT line.  Consume it now
        // so the receive buffer stays aligned for the next GetDialFrequencyMhzAsync
        // call (F-006 Root A).  An unread RPRT would otherwise be returned as the
        // Hz value of the next \get_freq and trigger a spurious error.
        var ack = (await _tcp.ReceiveLineAsync(cancellationToken).ConfigureAwait(false)).Trim();
        if (!ack.Equals("RPRT 0", StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException(
                $@"rigctld returned error for \set_freq {hz}: '{ack}'");
    }

    /// <summary>
    /// Sends <c>\set_ptt 1\n</c> to key the transmitter (<paramref name="transmitting"/> =
    /// <c>true</c>) or <c>\set_ptt 0\n</c> to unkey it (<paramref name="transmitting"/> =
    /// <c>false</c>) (FR-056), then reads and validates the <c>RPRT 0</c> acknowledgement
    /// exactly as <see cref="SetDialFrequencyMhzAsync"/> does for <c>\set_freq</c> — this
    /// keeps the receive buffer aligned for the next <see cref="GetDialFrequencyMhzAsync"/>
    /// call (same rationale as F-006 Root A).
    /// </summary>
    /// <exception cref="InvalidOperationException">
    /// <c>rigctld</c> returned a non-zero RPRT code (e.g. <c>RPRT -1</c>).
    /// </exception>
    public async Task SetPttAsync(bool transmitting, CancellationToken cancellationToken = default)
    {
        var command = $@"\set_ptt {(transmitting ? 1 : 0)}" + "\n";
        await _tcp.SendAsync(command, cancellationToken).ConfigureAwait(false);

        var ack = (await _tcp.ReceiveLineAsync(cancellationToken).ConfigureAwait(false)).Trim();
        if (!ack.Equals("RPRT 0", StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException(
                $@"rigctld returned error for \set_ptt {(transmitting ? 1 : 0)}: '{ack}'");
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
