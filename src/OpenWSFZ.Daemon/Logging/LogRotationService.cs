using Microsoft.Extensions.Hosting;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Daemon.Logging;

/// <summary>
/// Fires scheduled log rotation (FR-023) based on <see cref="LoggingConfig.RotationSchedule"/>.
/// Exits immediately if file logging is disabled or schedule is "session".
/// </summary>
internal sealed class LogRotationService : BackgroundService
{
    private readonly LoggingPipeline _pipeline;
    private readonly IConfigStore    _configStore;

    public LogRotationService(LoggingPipeline pipeline, IConfigStore configStore)
    {
        _pipeline    = pipeline;
        _configStore = configStore;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        var cfg = _configStore.Current.Logging;

        if (!cfg.FileEnabled || cfg.RotationSchedule == "session")
            return;

        while (!stoppingToken.IsCancellationRequested)
        {
            var delay = CalculateNextBoundary(DateTime.UtcNow, cfg) - DateTime.UtcNow;
            if (delay > TimeSpan.Zero)
            {
                try   { await Task.Delay(delay, stoppingToken); }
                catch (OperationCanceledException) { return; }
            }

            if (stoppingToken.IsCancellationRequested) return;

            _pipeline.Rotate();

            cfg = _configStore.Current.Logging;
            if (!cfg.FileEnabled || cfg.RotationSchedule == "session") return;
        }
    }

    /// <summary>
    /// Returns the next UTC moment at which rotation should fire,
    /// always strictly in the future.
    /// </summary>
    /// <remarks>
    /// Belt-and-braces guard (dev-tasks/2026-07-29-fix-loggingconfig-null-rotationschedule-crash.md
    /// §3): the catch-all below must never return a delay that exceeds <see cref="Task.Delay"/>'s
    /// maximum (~24.8 days / <see cref="int.MaxValue"/> ms). This is reachable for *any*
    /// unrecognised <see cref="LoggingConfig.RotationSchedule"/> value — not just the intentional
    /// "session" literal already short-circuited by the caller — e.g. a hand-typed typo such as
    /// "Daily". A previous version returned <c>utcNow.AddDays(36500)</c> here (~100 years), which
    /// overflows <c>Task.Delay</c>'s valid range, throws <see cref="ArgumentOutOfRangeException"/>
    /// uncaught inside a <see cref="BackgroundService"/>, and crashes the entire host under the
    /// default <c>BackgroundServiceExceptionBehavior.StopHost</c>. "Come back and check again
    /// tomorrow" is a safe, cheap fallback for any value this switch doesn't recognise.
    /// </remarks>
    internal static DateTime CalculateNextBoundary(DateTime utcNow, LoggingConfig cfg) =>
        cfg.RotationSchedule switch
        {
            "hourly" => NextHourly(utcNow),
            "daily"  => NextDaily(utcNow, cfg.RotationTime),
            "weekly" => NextWeekly(utcNow, cfg.RotationDayOfWeek, cfg.RotationTime),
            _        => utcNow.AddDays(1), // "session", null, or unrecognised — re-check tomorrow, never a Task.Delay overflow
        };

    private static DateTime NextHourly(DateTime utcNow)
    {
        var next = new DateTime(utcNow.Year, utcNow.Month, utcNow.Day,
                                utcNow.Hour, 0, 0, DateTimeKind.Utc).AddHours(1);
        return next > utcNow ? next : next.AddHours(1);
    }

    private static DateTime NextDaily(DateTime utcNow, string rotationTime)
    {
        var (h, m) = ParseHHMM(rotationTime);
        var today  = new DateTime(utcNow.Year, utcNow.Month, utcNow.Day,
                                  h, m, 0, DateTimeKind.Utc);
        return today > utcNow ? today : today.AddDays(1);
    }

    private static DateTime NextWeekly(DateTime utcNow, string dayOfWeek, string rotationTime)
    {
        var (h, m) = ParseHHMM(rotationTime);
        var target = Enum.TryParse<DayOfWeek>(dayOfWeek, ignoreCase: true, out var dow)
            ? dow : DayOfWeek.Monday;

        var candidate = new DateTime(utcNow.Year, utcNow.Month, utcNow.Day,
                                     h, m, 0, DateTimeKind.Utc);
        var daysUntil = ((int)target - (int)candidate.DayOfWeek + 7) % 7;
        candidate = candidate.AddDays(daysUntil);
        return candidate > utcNow ? candidate : candidate.AddDays(7);
    }

    private static (int h, int m) ParseHHMM(string hhmm)
    {
        var parts = hhmm.Split(':');
        return parts.Length == 2
               && int.TryParse(parts[0], out var h) && h is >= 0 and <= 23
               && int.TryParse(parts[1], out var m) && m is >= 0 and <= 59
            ? (h, m)
            : (0, 0);
    }
}
