namespace OpenWSFZ.Rig.Internal;

/// <summary>
/// Thin abstraction over <see cref="System.IO.Ports.SerialPort"/> used by
/// <see cref="SerialCatConnection"/> to enable unit testing without real hardware.
/// </summary>
internal interface ISerialPort : IDisposable
{
    bool IsOpen       { get; }
    int  ReadTimeout  { get; set; }

    void   Open();
    void   Write(string text);
    string ReadTo(string value);
    void   Close();
}
