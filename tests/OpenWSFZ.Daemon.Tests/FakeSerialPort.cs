using OpenWSFZ.Rig.Internal;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Hand-written <see cref="ISerialPort"/> test double (task 3.3, FR-056) exposing
/// settable/observable <see cref="RtsEnable"/>/<see cref="DtrEnable"/> state, used by
/// <c>SerialRtsDtrPttController</c>'s unit tests (task 12.7). Lives alongside
/// <c>OpenWSFZ.Rig.Tests</c>'s NSubstitute-based fakes that already back
/// <c>SerialCatConnectionTests</c> — a hand-rolled double is used here (rather than
/// <c>Substitute.For&lt;ISerialPort&gt;()</c>) because <see cref="Open"/> failure
/// injection and write-history inspection read more directly this way for a controller
/// whose whole job is toggling two boolean control lines in a precise order.
/// </summary>
internal sealed class FakeSerialPort : ISerialPort
{
    private readonly List<string> _written = new();

    public bool IsOpen      { get; private set; }
    public int  ReadTimeout { get; set; }
    public bool RtsEnable   { get; set; }
    public bool DtrEnable   { get; set; }

    /// <summary>When set, <see cref="Open"/> throws this instead of succeeding.</summary>
    public Exception? ThrowOnOpen { get; set; }

    /// <summary>All strings passed to <see cref="Write"/>, in order.</summary>
    public IReadOnlyList<string> Written => _written;

    public int CloseCallCount { get; private set; }
    public int DisposeCallCount { get; private set; }

    public void Open()
    {
        if (ThrowOnOpen is not null) throw ThrowOnOpen;
        IsOpen = true;
    }

    public void Write(string text) => _written.Add(text);

    public string ReadTo(string value) => string.Empty;

    public void DiscardInBuffer() { /* no-op — RTS/DTR PTT never reads from the port */ }

    public void Close()
    {
        CloseCallCount++;
        IsOpen = false;
    }

    public void Dispose() => DisposeCallCount++;
}
