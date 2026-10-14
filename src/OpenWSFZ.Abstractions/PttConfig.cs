using System.Text.Json.Serialization;

namespace OpenWSFZ.Abstractions;

/// <summary>
/// PTT (push-to-talk) keying configuration (FR-056).
/// All fields have defaults so a partial or absent <c>ptt</c> JSON key loads without
/// error, and the all-defaults instance is byte-for-byte today's pre-<c>cat-tx-ptt</c>
/// behaviour: audio-only VOX keying, nothing else touched.
/// </summary>
public sealed record PttConfig
{

    // Deserialization note (Lesson 6 / D-WFC-001 pattern, see LoggingConfig.cs and #209):
    // without an explicit [JsonConstructor] the STJ source generator reads default(T) for a key
    // that is absent from a PRESENT section, bypassing the initialisers below. Every property is
    // therefore a constructor parameter carrying the same default as its initialiser.

    /// <summary>
    /// Deserialization constructor (parameter defaults mirror the initialisers). A <c>null</c>
    /// <paramref name="serialPort"/> (its platform default cannot be a compile-time constant)
    /// resolves to the platform default.
    /// </summary>
    [JsonConstructor]
    public PttConfig(
        string  method            = "AudioVox",
        string? serialPort        = null,
        string  serialLine        = "Rts",
        int     leadTimeMs        = 50,
        int     tailTimeMs        = 50,
        int     watchdogTimeoutMs = 20000)
    {
        Method            = method;
        SerialPort        = serialPort ?? DefaultSerialPort;
        SerialLine        = serialLine;
        LeadTimeMs        = leadTimeMs;
        TailTimeMs        = tailTimeMs;
        WatchdogTimeoutMs = watchdogTimeoutMs;
    }

    private static string DefaultSerialPort =>
        OperatingSystem.IsWindows() ? "COM7" :
        OperatingSystem.IsMacOS()   ? "/dev/cu.usbserial-ptt" :
                                      "/dev/ttyUSB1";

    /// <summary>
    /// Selects which <c>IPttController</c> implementation is registered at daemon startup.
    /// Recognised values: <c>"AudioVox"</c> (default — existing VOX-only behaviour,
    /// unchanged), <c>"CatCommand"</c> (keys PTT via the CAT link), <c>"SerialRtsDtr"</c>
    /// (keys PTT via a raw RTS/DTR serial control line, independent of any CAT connection).
    /// Unknown values log a Warning and fall back to <c>"AudioVox"</c>.
    /// </summary>
    public string Method { get; init; } = "AudioVox";

    /// <summary>
    /// Serial port used for <c>SerialRtsDtr</c> PTT keying. Independent of
    /// <see cref="CatConfig.SerialPort"/> — in practice RTS/DTR PTT wiring is
    /// frequently on a different physical interface than the CAT link.
    /// Platform default: <c>COM7</c> on Windows, <c>/dev/ttyUSB1</c> on Linux,
    /// <c>/dev/cu.usbserial-ptt</c> on macOS.
    /// Used only when <see cref="Method"/> is <c>"SerialRtsDtr"</c>.
    /// </summary>
    public string SerialPort { get; init; } =
        OperatingSystem.IsWindows() ? "COM7" :
        OperatingSystem.IsMacOS()   ? "/dev/cu.usbserial-ptt" :
                                      "/dev/ttyUSB1";

    /// <summary>
    /// Which serial control line asserts PTT. Recognised values: <c>"Rts"</c> (default),
    /// <c>"Dtr"</c>. Unrecognised values log a Warning and fall back to <c>"Rts"</c>.
    /// Used only when <see cref="Method"/> is <c>"SerialRtsDtr"</c>.
    /// </summary>
    public string SerialLine { get; init; } = "Rts";

    /// <summary>
    /// Milliseconds to wait after asserting PTT before TX audio playback begins.
    /// Gives the rig's PA time to come up cleanly before audio appears. Default: 50.
    /// Used only by <c>CatPttController</c>/<c>SerialRtsDtrPttController</c>.
    /// </summary>
    public int LeadTimeMs { get; init; } = 50;

    /// <summary>
    /// Milliseconds to wait after TX audio playback ends before PTT is released.
    /// Avoids clipping the tail of the last symbol. Default: 50.
    /// Used only by <c>CatPttController</c>/<c>SerialRtsDtrPttController</c>.
    /// </summary>
    public int TailTimeMs { get; init; } = 50;

    /// <summary>
    /// Hard failsafe ceiling, in milliseconds, on how long PTT may remain asserted
    /// without <c>KeyUpAsync</c> completing its release step. If exceeded, PTT is
    /// force-released (bypassing <see cref="TailTimeMs"/>) and an Error is logged.
    /// Default: 20000 (comfortably above one FT8 transmission's 12 640 ms).
    /// Used only by <c>CatPttController</c>/<c>SerialRtsDtrPttController</c>.
    /// </summary>
    public int WatchdogTimeoutMs { get; init; } = 20000;
}
