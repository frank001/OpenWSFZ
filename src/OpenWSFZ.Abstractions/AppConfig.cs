namespace OpenWSFZ.Abstractions;

/// <summary>
/// Operator configuration persisted to the config file.
/// Phase 2 schema: audio device selection and port.
/// Future phases will add FT8 parameters, UI preferences, etc.
/// </summary>
public sealed record AppConfig(
    string? AudioDeviceName    = null,
    int     Port               = 8080,
    bool    ShowCycleCountdown = false,
    /// <summary>
    /// Minimum log level for the application.  Must be one of the names defined by
    /// <c>Microsoft.Extensions.Logging.LogLevel</c>: Trace, Debug, Information, Warning,
    /// Error, Critical, or None.  Takes effect on the next application start.
    /// Default: "Information".
    /// </summary>
    string  LogLevel           = "Information");
