using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Daemon;

/// <summary>
/// Compiled-in default FT8 working frequency list mirroring the standard WSJT-X
/// frequencies (FR-042). Used when <c>frequencies.json</c> is absent or malformed.
/// </summary>
public static class FrequencyDefaults
{
    /// <summary>
    /// The 15-entry default FT8 frequency list covering 160 m through 70 cm.
    /// </summary>
    public static readonly IReadOnlyList<FrequencyEntry> Entries =
    [
        new FrequencyEntry("FT8",   1.840, "160m"),
        new FrequencyEntry("FT8",   3.573, "80m"),
        new FrequencyEntry("FT8",   5.357, "60m"),
        new FrequencyEntry("FT8",   7.074, "40m"),
        new FrequencyEntry("FT8",  10.136, "30m"),
        new FrequencyEntry("FT8",  14.074, "20m"),
        new FrequencyEntry("FT8",  18.100, "17m"),
        new FrequencyEntry("FT8",  21.074, "15m"),
        new FrequencyEntry("FT8",  24.915, "12m"),
        new FrequencyEntry("FT8",  28.074, "10m"),
        new FrequencyEntry("FT8",  50.313, "6m"),
        new FrequencyEntry("FT8",  70.100, "4m"),
        new FrequencyEntry("FT8", 144.174, "2m"),
        new FrequencyEntry("FT8", 222.065, "1.25m"),
        new FrequencyEntry("FT8", 432.065, "70cm"),
    ];
}
