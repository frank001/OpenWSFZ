using System.Net.Sockets;
using System.Text;

namespace OpenWSFZ.Rig.Internal;

/// <summary>
/// Production <see cref="ITcpConnection"/> backed by <see cref="TcpClient"/>.
/// Sets a 500 ms receive timeout after the connection is established.
/// </summary>
internal sealed class TcpConnectionWrapper : ITcpConnection
{
    private const int ReceiveTimeoutMs = 500;

    private TcpClient?    _client;
    private StreamReader? _reader;
    private StreamWriter? _writer;

    public bool IsConnected => _client?.Connected ?? false;

    public async Task ConnectAsync(string host, int port, CancellationToken ct = default)
    {
        _client = new TcpClient();
        await _client.ConnectAsync(host, port, ct).ConfigureAwait(false);
        _client.ReceiveTimeout = ReceiveTimeoutMs;

        var stream = _client.GetStream();
        _reader    = new StreamReader(stream, Encoding.ASCII, leaveOpen: true);
        _writer    = new StreamWriter(stream, Encoding.ASCII, leaveOpen: true)
                     { AutoFlush = true };
    }

    public async Task SendAsync(string message, CancellationToken ct = default)
    {
        if (_writer is null) throw new InvalidOperationException("Not connected.");
        await _writer.WriteAsync(message.AsMemory(), ct).ConfigureAwait(false);
    }

    public async Task<string> ReceiveLineAsync(CancellationToken ct = default)
    {
        if (_reader is null) throw new InvalidOperationException("Not connected.");
        try
        {
            var line = await _reader.ReadLineAsync(ct).ConfigureAwait(false);
            return line ?? throw new System.IO.IOException("Connection closed by remote.");
        }
        catch (System.IO.IOException ex) when (
            ex.InnerException is SocketException { SocketErrorCode: SocketError.TimedOut })
        {
            throw new TimeoutException(
                $"rigctld: no response within {ReceiveTimeoutMs} ms.", ex);
        }
    }

    public void Close() => _client?.Close();

    public void Dispose()
    {
        _reader?.Dispose();
        _writer?.Dispose();
        _client?.Dispose();
    }
}
