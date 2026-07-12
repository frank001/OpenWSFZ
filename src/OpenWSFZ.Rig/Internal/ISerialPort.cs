namespace OpenWSFZ.Rig.Internal;

/// <summary>
/// Thin abstraction over <see cref="System.IO.Ports.SerialPort"/> used by
/// <see cref="SerialCatConnection"/> to enable unit testing without real hardware.
/// </summary>
internal interface ISerialPort : IDisposable
{
    bool IsOpen       { get; }
    int  ReadTimeout  { get; set; }

    /// <summary>
    /// Controls the RTS (Request To Send) control line (FR-056). Mirrors
    /// <see cref="System.IO.Ports.SerialPort.RtsEnable"/> 1:1. Used by
    /// <c>SerialRtsDtrPttController</c> to key PTT via a raw serial control line.
    /// </summary>
    bool RtsEnable    { get; set; }

    /// <summary>
    /// Controls the DTR (Data Terminal Ready) control line (FR-056). Mirrors
    /// <see cref="System.IO.Ports.SerialPort.DtrEnable"/> 1:1. Used by
    /// <c>SerialRtsDtrPttController</c> to key PTT via a raw serial control line.
    /// </summary>
    bool DtrEnable    { get; set; }

    void   Open();
    void   Write(string text);
    string ReadTo(string value);
    void   DiscardInBuffer();
    void   Close();
}
