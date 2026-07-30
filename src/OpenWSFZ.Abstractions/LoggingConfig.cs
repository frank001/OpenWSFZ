using System.Text.Json.Serialization;

namespace OpenWSFZ.Abstractions;

/// <summary>
/// Configuration for the file logging sink (FR-022, FR-023, FR-024).
/// All fields have defaults so existing config.json files without a
/// "logging" key continue to deserialise without error.
/// </summary>
public sealed record LoggingConfig
{
    // ── Deserialization note (Lesson 6 / D-WFC-001 pattern, mirrors CycleAudioArchiveConfig/
    // DecodeNoiseSuppressionConfig/ExternalReportingConfig)
    //
    // RotationSchedule ("daily"), RotationTime ("00:00"), RotationDayOfWeek ("Monday") and
    // MaxFiles (7) all have non-CLR-zero defaults. A JSON "logging" object that is present but
    // omits any of these keys — exactly what a hand-edit that only sets fileEnabled/directory/
    // fileLogLevel produces — would otherwise deserialise them to null/null/null/0 under STJ
    // source generation, silently bypassing the property initialisers below. That null
    // RotationSchedule then falls through LogRotationService.CalculateNextBoundary's switch
    // catch-all into a ~100-year Task.Delay, which throws ArgumentOutOfRangeException and
    // crashes the whole host (BackgroundServiceExceptionBehavior.StopHost). The explicit
    // [JsonConstructor] with matching parameter defaults is required — see
    // CycleAudioArchiveConfig.cs for the same pattern and its rationale.
    // ─────────────────────────────────────────────────────────────────────────────────────────

    /// <summary>
    /// Deserialization constructor used by the STJ source-generated context. Parameter defaults
    /// ensure a field absent from a partial config object loads with the documented default
    /// rather than a CLR zero-value (Lesson 6 / D-WFC-001 pattern).
    /// </summary>
    [JsonConstructor]
    public LoggingConfig(
        bool   fileEnabled       = false,
        string directory         = "logs",
        string fileLogLevel      = "Information",
        string rotationSchedule  = "daily",
        string rotationTime      = "00:00",
        string rotationDayOfWeek = "Monday",
        int    maxFiles          = 7)
    {
        FileEnabled       = fileEnabled;
        Directory         = directory;
        FileLogLevel      = fileLogLevel;
        RotationSchedule  = rotationSchedule;
        RotationTime      = rotationTime;
        RotationDayOfWeek = rotationDayOfWeek;
        MaxFiles          = maxFiles;
    }

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
