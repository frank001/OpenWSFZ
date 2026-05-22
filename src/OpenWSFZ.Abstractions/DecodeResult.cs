namespace OpenWSFZ.Abstractions;

/// <summary>
/// Represents a single decoded FT8 message from one 15-second cycle.
/// </summary>
/// <param name="Time">UTC cycle start, formatted as <c>HH:mm:ss</c>.</param>
/// <param name="Snr">Signal-to-noise ratio in dB, relative to the 2500 Hz noise floor.</param>
/// <param name="Dt">Timing offset in seconds of the transmission within the cycle.</param>
/// <param name="FreqHz">Audio frequency offset in Hz of the strongest tone.</param>
/// <param name="Message">Decoded message text, or a 20-character hex string for unrecognised types.</param>
public sealed record DecodeResult(
    string Time,
    int    Snr,
    double Dt,
    int    FreqHz,
    string Message);
