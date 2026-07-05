namespace OpenWSFZ.Abstractions;

/// <summary>
/// Abstraction exposing the daemon's currently active log file path (log-viewer,
/// f-004-operator-visibility-improvements). Separating the interface from the concrete
/// <c>LoggingPipeline</c> class allows the <c>GET /api/v1/logs/tail</c> and
/// <c>GET /api/v1/logs/full</c> web endpoints to read the active log file without creating
/// a direct dependency from <c>OpenWSFZ.Web</c> to <c>OpenWSFZ.Daemon</c> — the same pattern
/// already used for <see cref="IAdifLogWriter"/>.
/// </summary>
public interface ILogFileSource
{
    /// <summary>
    /// The daemon's currently active log file path, or <see langword="null"/> when file
    /// logging is disabled or the file could not be created.
    /// </summary>
    string? CurrentLogFilePath { get; }
}
