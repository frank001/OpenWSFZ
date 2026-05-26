namespace OpenWSFZ.Abstractions;

/// <summary>
/// Configuration for the file logging sink (FR-022, FR-023, FR-024).
/// All fields have defaults so existing config.json files without a
/// "logging" key continue to deserialise without error.
/// </summary>
public sealed record LoggingConfig
{
    /// <summary>When false (default), no log file is created.</summary>
    public bool   FileEnabled       { get; init; } = false;

    /// <summary>Directory for log files. Relative paths are resolved from the executable.</summary>
    public string Directory         { get; init; } = "logs";

    /// <summary>Minimum severity written to the file sink. Independent of the console level.</summary>
    public string FileLogLevel      { get; init; } = "Information";

    /// <summary>"session" | "hourly" | "daily" | "weekly"</summary>
    public string RotationSchedule  { get; init; } = "daily";

    /// <summary>UTC time of day for daily/weekly rotation. Format: "HH:MM".</summary>
    public string RotationTime      { get; init; } = "00:00";

    /// <summary>Day of week for weekly rotation. E.g. "Monday".</summary>
    public string RotationDayOfWeek { get; init; } = "Monday";

    /// <summary>Maximum number of log files to retain. Values ≤ 0 are clamped to 1.</summary>
    public int    MaxFiles          { get; init; } = 7;
}
