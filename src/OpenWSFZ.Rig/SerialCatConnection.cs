using Microsoft.Extensions.Logging;
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
/// Frequency query (<see cref="GetDialFrequencyMhzAsync"/>): sends <c>FA;\r</c>
/// (semicolon + carriage-return — the CR is required by Yaesu firmware to flush the
/// command buffer; Kenwood rigs accept and ignore it), reads the response up to the
/// <c>;</c> delimiter.  The response must start with <c>FA</c> followed by 8–11
/// decimal Hz digits.
/// Example: <c>FA00014074000;</c> (11-digit) or <c>FA007074000;</c> (9-digit) → 7.074 MHz.
/// The receive buffer is flushed via <c>DiscardInBuffer</c> before each query to
/// clear any transient rig response from a preceding set command.
/// On the first successful response the digit count is recorded in <see cref="_freqWidth"/>
/// and used by all subsequent <see cref="SetDialFrequencyMhzAsync"/> calls.
/// </para>
///
/// <para>
/// Frequency set (<see cref="SetDialFrequencyMhzAsync"/>): sends
/// <c>FA&lt;Hz&gt;;</c> with the Hz value zero-padded to the rig's native digit width
/// (self-calibrated from the first successful query response; falls back to 11 digits
/// until the first poll completes) (FR-045).  No read-back is performed; any rig
/// response is cleared by the next <c>GetDialFrequencyMhzAsync</c> call.
/// </para>
/// </summary>
public sealed class SerialCatConnection : IRadioConnection, IDisposable
{
    private const int    ReadTimeoutMs    = 500;
    private const int    DefaultFreqWidth = 11;
    private const string CatCommand       = "FA;\r";
    private const string ResponseDelim    = ";";

    private readonly ISerialPort _port;
    private readonly ILogger?    _logger;

    // Rig's native FA command digit width, discovered on the first successful GET.
    // Written exactly once (0 → measured value); read-only after that.
    // volatile ensures the poll-loop write is immediately visible to the HTTP-request thread.
    private volatile int _freqWidth = 0;

    // ── Public constructor (production use) ───────────────────────────────────

    /// <summary>
    /// Creates a <see cref="SerialCatConnection"/> that will use the given serial port.
    /// </summary>
    /// <param name="portName">OS serial port name (e.g. <c>COM6</c>, <c>/dev/ttyUSB0</c>).</param>
    /// <param name="baudRate">Baud rate (e.g. <c>9600</c>).</param>
    /// <param name="logger">Optional logger; serial I/O bytes are emitted at <c>Debug</c> level.</param>
    public SerialCatConnection(string portName, int baudRate, ILogger<SerialCatConnection>? logger = null)
        : this(new SerialPortWrapper(portName, baudRate), logger) { }

    // ── Internal constructor (test use) ──────────────────────────────────────

    /// <summary>
    /// Creates a <see cref="SerialCatConnection"/> backed by the supplied
    /// <paramref name="serialPort"/> abstraction.  Used by unit tests.
    /// </summary>
    internal SerialCatConnection(ISerialPort serialPort, ILogger? logger = null)
    {
        _port             = serialPort;
        _port.ReadTimeout = ReadTimeoutMs;
        _logger           = logger;
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
    /// On the first successful call the digit count is recorded for use by
    /// <see cref="SetDialFrequencyMhzAsync"/>.
    /// </summary>
    /// <exception cref="InvalidOperationException">
    /// The response does not start with <c>FA</c>, or its digit count is outside 8–11.
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

        _logger?.LogDebug("Serial CAT GET: raw response '{Raw}'", raw);

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

        // Self-calibrate: record the rig's native digit width on the first successful
        // response so SetDialFrequencyMhzAsync can use the correct zero-pad width.
        // Written only once (0 → measured value); idempotent for subsequent calls
        // because the condition is false once _freqWidth is non-zero (D2, D4).
        if (_freqWidth == 0) _freqWidth = digitCount;

        return Task.FromResult(hz / 1_000_000.0);
    }

    /// <summary>
    /// Sends <c>FA&lt;Hz&gt;;</c> to command VFO-A to <paramref name="frequencyMHz"/> (FR-045).
    /// The Hz integer is rounded to the nearest integer and zero-padded to the rig's native
    /// digit width (self-calibrated from the first successful <see cref="GetDialFrequencyMhzAsync"/>
    /// call on this connection).  Falls back to 11 digits until the first poll completes (D3).
    /// The method returns after the write completes — no read-back is performed.
    /// </summary>
    /// <example>
    /// 9-digit rig: <c>14.074 MHz → FA014074000;</c><br/>
    /// 11-digit rig: <c>14.074 MHz → FA00014074000;</c>
    /// </example>
    public Task SetDialFrequencyMhzAsync(
        double            frequencyMHz,
        CancellationToken cancellationToken = default)
    {
        var hz      = (long)Math.Round(frequencyMHz * 1_000_000.0);
        var width   = _freqWidth > 0 ? _freqWidth : DefaultFreqWidth;
        var command = $"FA{hz.ToString().PadLeft(width, '0')};";
        _logger?.LogDebug("Serial CAT SET: writing '{Command}'", command);
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
