using System.IO.Ports;

namespace OpenWSFZ.Rig.Internal;

/// <summary>
/// Production implementation of <see cref="ISerialPort"/> backed by
/// <see cref="System.IO.Ports.SerialPort"/>.
/// </summary>
internal sealed class SerialPortWrapper : ISerialPort
{
    private readonly SerialPort _port;

    public SerialPortWrapper(string portName, int baudRate)
    {
        _port = new SerialPort(
            portName,
            baudRate,
            Parity.None,
            dataBits: 8,
            StopBits.One);
    }

    public bool IsOpen           => _port.IsOpen;
    public int  ReadTimeout
    {
        get => _port.ReadTimeout;
        set => _port.ReadTimeout = value;
    }

    public void   Open()                 => _port.Open();
    public void   Write(string text)     => _port.Write(text);
    public string ReadTo(string value)   => _port.ReadTo(value);
    public void   Close()                => _port.Close();
    public void   Dispose()              => _port.Dispose();
}
