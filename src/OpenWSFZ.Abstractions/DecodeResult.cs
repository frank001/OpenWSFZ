namespace OpenWSFZ.Abstractions;

/// <summary>
/// Represents a single decoded FT8 message from one 15-second cycle.
/// </summary>
/// <param name="Time">UTC cycle start, formatted as <c>HH:mm:ss</c>.</param>
/// <param name="Snr">Signal-to-noise ratio in dB, relative to the 2500 Hz noise floor.</param>
/// <param name="Dt">Timing offset in seconds of the transmission within the cycle.</param>
/// <param name="FreqHz">Audio frequency offset in Hz of the strongest tone.</param>
/// <param name="Message">Decoded message text, or a 20-character hex string for unrecognised types.</param>
/// <param name="Region">
/// Advisory continent/entity region resolved from the message's primary
/// callsign-position token (<c>region-lookup</c> capability), or <c>null</c> on a
/// lookup miss, a missing/malformed <c>callsign-regions.json</c>, or when no
/// <see cref="ICallsignRegionStore"/> was supplied to the decoder. The frontend
/// renders <c>null</c> as <c>"Unknown"</c>. Never affects decode acceptance.
/// </param>
public sealed record DecodeResult(
    string      Time,
    int         Snr,
    double      Dt,
    int         FreqHz,
    string      Message,
    RegionInfo? Region = null);
