using OpenWSFZ.Abstractions;
using OpenWSFZ.Rig.Internal;

namespace OpenWSFZ.Rig;

/// <summary>
/// Implements <see cref="IRadioConnection"/> using a direct serial port and the
/// Kenwood/Yaesu serial CAT protocol (FR-031, FR-032, FR-045).
///
/// <para>
/// Constructable from a port name and baud rate.  All serial I/O uses a 500 ms
/// <c>ReadTimeout</c>.
/// </para>
///
/// <para>
/// Frequency query (<see cref="GetDialFrequencyMhzAsync"/>): sends <c>FA;</c>,
/// reads the response up to the <c>;</c> delimiter.  The response must start with
/// <c>FA</c> followed by 8–11 decimal Hz digits.
/// Example: <c>FA00014074000;</c> → 14.074 MHz.
/// The receive buffer is flushed via <c>DiscardInBuffer</c> before each query to
/// clear any transient rig response from a preceding set command.
/// </para>
///
/// <para>
/// Frequency set (<see cref="SetDialFrequencyMhzAsync"/>): sends
/// <c>FA&lt;11-digit-Hz&gt;;</c> (FR-045).  No read-back is performed; any rig
/// response is cleared by the next <c>GetDialFrequencyMhzAsync</c> call.
/// </para>
/// </summary>
public sealed class SerialCatConnection : IRadioConnection, IDisposable
{
    private const int    ReadTimeoutMs   = 500;
    private const int    DefaultDigits   = 11;
    private const string CatCommand      = "FA;";
    private const string ResponseDelim   = ";";

    private readonly ISerialPort _port;

    // Digit count observed in the most recent successful GetDialFrequencyMhzAsync
    // response.  Kenwood rigs (TS-2000, TS-590S …) use 11 digits; Yaesu rigs
    // (FT-991A, FT-817 …) use 9.  GetDialFrequencyMhzAsync updates this field so
    // SetDialFrequencyMhzAsync can send the format the rig actually understands.
    // Defaults to 11 (Kenwood standard) so that the very first SET before any GET
    // uses a reasonable format.
    private int _freqDigitCount = DefaultDigits;

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
    /// Sends <c>FA;</c>, reads the response until <c>;</c>, validates the
    /// format, and returns VFO-A frequency in MHz.
    /// </summary>
    /// <exception cref="InvalidOperationException">
    /// The response does not start with <c>FA</c> or is not exactly 14 characters (13 before <c>;</c> plus the delimiter).
    /// </exception>
    /// <exception cref="TimeoutException">
    /// No response arrived within 500 ms.
    /// </exception>
    public Task<double> GetDialFrequencyMhzAsync(CancellationToken cancellationToken = default)
    {
        // Discard any stale data in the receive buffer before issuing the query.
        // This drains any response the rig left from a preceding SetDialFrequencyMhzAsync
        // call (e.g. a "?;" error acknowledgement), which would otherwise be read in
        // place of the FA; response and cause a spurious InvalidOperationException (F-003).
        _port.DiscardInBuffer();

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

        // ReadTo returns everything BEFORE the delimiter, so raw = "FA00014074000" (11-digit)
        // or "FA007074000" (9-digit — some rig families use fewer leading digits).
        // Full response = raw + ";" = FA(2) + 8..11 Hz digits + semicolon(1).
        var full       = raw + ";";
        var digitCount = full.Length - 3; // strip "FA" prefix and ";" suffix
        if (!full.StartsWith("FA", StringComparison.Ordinal) || digitCount < 8 || digitCount > 11)
        {
            throw new InvalidOperationException(
                $"Serial CAT: unexpected FA; response (raw='{raw}'). " +
                "Expected format: FA<8–11 digit Hz>;");
        }

        if (!long.TryParse(full.AsSpan(2, digitCount), out var hz) || hz < 0)
        {
            throw new InvalidOperationException(
                $"Serial CAT: cannot parse Hz value from response '{raw}'.");
        }

        // Record the digit count this rig uses so SetDialFrequencyMhzAsync can
        // send the matching format (9 digits for Yaesu FT-991A / FT-817 family,
        // 11 digits for Kenwood TS-2000 / TS-590 family).
        _freqDigitCount = digitCount;

        return Task.FromResult(hz / 1_000_000.0);
    }

    /// <summary>
    /// Sends <c>FA&lt;Hz&gt;;</c> to command VFO-A to <paramref name="frequencyMHz"/>
    /// (FR-045).  The Hz integer is rounded to the nearest integer and zero-padded
    /// to match the digit count observed in the most recent
    /// <see cref="GetDialFrequencyMhzAsync"/> response (9 for Yaesu FT-991A / FT-817
    /// family, 11 for Kenwood TS-2000 / TS-590 family).  Before the first
    /// <see cref="GetDialFrequencyMhzAsync"/> call the default of 11 digits is used.
    /// The method returns after the write completes — no read-back is performed.
    /// </summary>
    /// <example>
    /// 9-digit rig (Yaesu):  <c>14.074 MHz → FA014074000;</c><br/>
    /// 11-digit rig (Kenwood): <c>14.074 MHz → FA00014074000;</c>
    /// </example>
    public Task SetDialFrequencyMhzAsync(
        double            frequencyMHz,
        CancellationToken cancellationToken = default)
    {
        var hz      = (long)Math.Round(frequencyMHz * 1_000_000.0);
        var command = $"FA{hz.ToString().PadLeft(_freqDigitCount, '0')};";
        _port.Write(command);
        return Task.CompletedTask;
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
