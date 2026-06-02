using OpenWSFZ.Abstractions;
using OpenWSFZ.Rig.Internal;

namespace OpenWSFZ.Rig;

/// <summary>
/// Implements <see cref="IRadioConnection"/> using a direct serial port and the
/// serial CAT <c>FA;</c> frequency query command (FR-031, FR-032).
///
/// <para>
/// Constructable from a port name and baud rate.  All serial I/O uses a 500 ms
/// <c>ReadTimeout</c>.  Only the read-only <c>FA;</c> command is ever sent — no
/// frequency-set, mode-set, or PTT commands are issued by this class.
/// </para>
///
/// <para>
/// Serial CAT protocol: the command is written as <c>FA;\r</c> (carriage-return
/// terminator); the response is read up to the <c>;</c> delimiter and must be
/// exactly 14 characters before the delimiter (total 15 with the semicolon),
/// starting with <c>FA</c> followed by 11 decimal Hz digits.
/// Example: <c>FA00014074000;</c> → 14.074 MHz.
/// </para>
/// </summary>
public sealed class SerialCatConnection : IRadioConnection, IDisposable
{
    private const int    ReadTimeoutMs = 500;
    private const string CatCommand    = "FA;\r";
    private const string ResponseDelim = ";";

    private readonly ISerialPort _port;

    // ── Public constructor (production use) ───────────────────────────────────

    /// <summary>
    /// Creates a <see cref="SerialCatConnection"/> that will use the given serial port.
    /// </summary>
    /// <param name="portName">OS serial port name (e.g. <c>COM6</c>, <c>/dev/ttyUSB0</c>).</param>
    /// <param name="baudRate">Baud rate (e.g. <c>9600</c>).</param>
    public SerialCatConnection(string portName, int baudRate)
        : this(new SerialPortWrapper(portName, baudRate)) { }

    // ── Internal constructor (test use) ──────────────────────────────────────

    /// <summary>
    /// Creates a <see cref="SerialCatConnection"/> backed by the supplied
    /// <paramref name="serialPort"/> abstraction.  Used by unit tests.
    /// </summary>
    internal SerialCatConnection(ISerialPort serialPort)
    {
        _port             = serialPort;
        _port.ReadTimeout = ReadTimeoutMs;
    }

    // ── IRadioConnection ─────────────────────────────────────────────────────

    /// <inheritdoc/>
    public bool IsConnected => _port.IsOpen;

    /// <summary>
    /// Opens the serial port (8N1, 500 ms read timeout).
    /// </summary>
    /// <exception cref="UnauthorizedAccessException">
    /// The port is already open by another application.
    /// </exception>
    /// <exception cref="System.IO.IOException">
    /// The port does not exist or cannot be opened.
    /// </exception>
    public Task ConnectAsync(CancellationToken cancellationToken = default)
    {
        _port.Open();
        return Task.CompletedTask;
    }

    /// <summary>
    /// Sends <c>FA;\r</c>, reads the response until <c>;</c>, validates the
    /// format, and returns VFO-A frequency in MHz.
    /// </summary>
    /// <exception cref="InvalidOperationException">
    /// The response does not start with <c>FA</c> or is not exactly 15 characters.
    /// </exception>
    /// <exception cref="TimeoutException">
    /// No response arrived within 500 ms.
    /// </exception>
    public Task<double> GetDialFrequencyMhzAsync(CancellationToken cancellationToken = default)
    {
        _port.Write(CatCommand);

        string raw;
        try
        {
            raw = _port.ReadTo(ResponseDelim);
        }
        catch (TimeoutException)
        {
            throw new TimeoutException(
                $"Serial CAT: no response to FA; within {ReadTimeoutMs} ms.");
        }
        catch (System.IO.IOException ex) when (
            ex.Message.Contains("timed out", StringComparison.OrdinalIgnoreCase))
        {
            // Some OS/driver combinations surface the read timeout as an IOException.
            throw new TimeoutException(
                $"Serial CAT: no response to FA; within {ReadTimeoutMs} ms.", ex);
        }

        // ReadTo returns everything BEFORE the delimiter, so raw = "FA00014074000"
        // Full response is raw + ";" = 14 chars: FA(2) + 11 Hz digits + semicolon(1).
        var full = raw + ";";
        if (full.Length != 14 || !full.StartsWith("FA", StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                $"Serial CAT: unexpected FA; response (raw='{raw}'). " +
                "Expected format: FA<11-digit-Hz>;");
        }

        // Digits are positions 2–12 (11 chars = Hz value), position 13 = ';'.
        if (!long.TryParse(full.AsSpan(2, 11), out var hz) || hz < 0)
        {
            throw new InvalidOperationException(
                $"Serial CAT: cannot parse Hz value from response '{raw}'.");
        }

        return Task.FromResult(hz / 1_000_000.0);
    }

    /// <summary>Closes the serial port.</summary>
    public Task DisconnectAsync(CancellationToken cancellationToken = default)
    {
        if (_port.IsOpen)
            _port.Close();
        return Task.CompletedTask;
    }

    // ── IDisposable ───────────────────────────────────────────────────────────

    /// <summary>Closes and disposes the underlying serial port.</summary>
    public void Dispose()
    {
        if (_port.IsOpen)
        {
            try { _port.Close(); } catch { /* best-effort */ }
        }
        _port.Dispose();
    }
}
