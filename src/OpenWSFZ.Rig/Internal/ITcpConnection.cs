namespace OpenWSFZ.Rig.Internal;

/// <summary>
/// Thin abstraction over a TCP connection used by <see cref="RigctldConnection"/>
/// to enable unit testing without a real <c>rigctld</c> daemon.
/// </summary>
internal interface ITcpConnection : IDisposable
{
    bool IsConnected { get; }

    Task ConnectAsync(string host, int port, CancellationToken ct = default);
    Task SendAsync(string message, CancellationToken ct = default);

    /// <summary>
    /// Reads one line (terminated by LF) from the stream.
    /// </summary>
    /// <exception cref="TimeoutException">No data arrived within the receive timeout.</exception>
    Task<string> ReceiveLineAsync(CancellationToken ct = default);

    void Close();
}
