using Microsoft.Extensions.Logging;

namespace OpenWSFZ.Daemon.Logging;

/// <summary>
/// <para>
/// Writes log entries exclusively to the application's standard error stream
/// using the OpenWSFZ house format (FR-019):
/// </para>
/// <code>
/// [OpenWSFZ] YYYY-MM-DD HH:MM:SS [LEVEL]  ComponentName — message
/// </code>
/// <para>
/// LEVEL is the four-character abbreviation used by the .NET console logger:
/// trce / dbug / info / warn / fail / crit.
/// </para>
/// </summary>
internal sealed class StderrLoggerProvider : ILoggerProvider
{
    private readonly LogLevel _minLevel;

    public StderrLoggerProvider(LogLevel minLevel) => _minLevel = minLevel;

    public ILogger CreateLogger(string categoryName)
        => new StderrLogger(categoryName, _minLevel);

    public void Dispose() { }
}

internal sealed class StderrLogger(string categoryName, LogLevel minLevel) : ILogger
{
    // Derive a short component name from the fully-qualified category.
    // "OpenWSFZ.Audio.CaptureManager" → "CaptureManager"
    private readonly string _short = categoryName.LastIndexOf('.') is >= 0 and int i
        ? categoryName[(i + 1)..]
        : categoryName;

    public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;

    public bool IsEnabled(LogLevel logLevel)
        => logLevel != LogLevel.None && logLevel >= minLevel;

    public void Log<TState>(
        LogLevel logLevel,
        EventId eventId,
        TState state,
        Exception? exception,
        Func<TState, Exception?, string> formatter)
    {
        if (!IsEnabled(logLevel)) return;

        var abbrev = logLevel switch
        {
            LogLevel.Trace       => "trce",
            LogLevel.Debug       => "dbug",
            LogLevel.Information => "info",
            LogLevel.Warning     => "warn",
            LogLevel.Error       => "fail",
            LogLevel.Critical    => "crit",
            _                    => "????",
        };

        var ts  = DateTime.UtcNow.ToString("yyyy-MM-dd HH:mm:ss");
        var msg = formatter(state, exception);

        Console.Error.WriteLine($"[OpenWSFZ] {ts} [{abbrev}]  {_short} — {msg}");

        if (exception is not null)
            Console.Error.WriteLine($"[OpenWSFZ] {ts} [{abbrev}]  {_short} — {exception}");
    }
}
