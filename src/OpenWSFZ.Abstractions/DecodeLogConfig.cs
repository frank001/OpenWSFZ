using System.Text.Json.Serialization;

namespace OpenWSFZ.Abstractions;

/// <summary>
/// Configuration for the WSJT-X compatible ALL.TXT decode log (FR-027, FR-028).
/// All fields have defaults so existing config.json files without a "decodeLog"
/// key continue to deserialise without error.
/// </summary>
public sealed record DecodeLogConfig
{

    // Deserialization note (Lesson 6 / D-WFC-001 pattern, see LoggingConfig.cs and #209):
    // without an explicit [JsonConstructor] the STJ source generator reads default(T) for a key
    // that is absent from a PRESENT section, bypassing the initialisers below. Every property is
    // therefore a constructor parameter carrying the same default as its initialiser.

    /// <summary>Deserialization constructor (parameter defaults mirror the initialisers).</summary>
    [JsonConstructor]
    public DecodeLogConfig(bool enabled = false, string path = "ALL.TXT", double dialFrequencyMHz = 0.0)
    {
        Enabled          = enabled;
        Path             = path;
        DialFrequencyMHz = dialFrequencyMHz;
    }

    /// <summary>When false (default), no decode log file is created or written.</summary>
    public bool   Enabled          { get; init; } = false;

    /// <summary>
    /// Path to the ALL.TXT output file.
    /// Relative paths are resolved from the directory containing the executable.
    /// Default: <c>"ALL.TXT"</c> beside the executable.
    /// </summary>
    public string Path             { get; init; } = "ALL.TXT";

    /// <summary>
    /// Radio dial frequency in MHz (e.g. 7.074 for 40 m FT8).
    /// Written to each log line as the D.DDD column.
    /// Default: <c>0.0</c> (unconfigured; will appear as "0.000" in the log).
    /// </summary>
    public double DialFrequencyMHz { get; init; } = 0.0;
}
