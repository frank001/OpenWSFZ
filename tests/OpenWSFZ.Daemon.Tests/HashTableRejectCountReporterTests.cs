using FluentAssertions;
using Microsoft.Extensions.Logging;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Unit tests for <see cref="HashTableRejectCountReporter"/> — the session-end log-line
/// wiring the daemon's <c>ApplicationStopping</c> hook uses to surface the native hash-table
/// reject count (f-005-hash-table-saturation-diagnostic, tasks.md §4.4 and design.md Risk 1:
/// "the getter is added but nothing ever calls it").
///
/// <para>
/// Directly exercises the extracted reporter rather than booting the full daemon host, which
/// has no test harness. Confirms (a) the line is emitted at Information with the provided value
/// interpolated, and (b) a native/ABI fault while reading the counter is contained and never
/// propagates out of the shutdown path.
/// </para>
/// </summary>
[Trait("Category", "Unit")]
public sealed class HashTableRejectCountReporterTests
{
    /// <summary>Minimal <see cref="ILogger"/> that records every entry's level and formatted text.</summary>
    private sealed class CapturingLogger : ILogger
    {
        public readonly List<(LogLevel Level, string Message, Exception? Exception)> Entries = new();

        public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;
        public bool IsEnabled(LogLevel logLevel) => true;

        public void Log<TState>(
            LogLevel logLevel, EventId eventId, TState state, Exception? exception,
            Func<TState, Exception?, string> formatter)
            => Entries.Add((logLevel, formatter(state, exception), exception));
    }

    [Fact(DisplayName = "f-005: reporter logs the reject count at Information with the provided value")]
    public void Report_EmitsInformationLine_WithRejectCountValue()
    {
        var logger = new CapturingLogger();

        HashTableRejectCountReporter.Report(logger, () => 42);

        logger.Entries.Should().ContainSingle(e => e.Level == LogLevel.Information)
            .Which.Message.Should().Contain("Hash table reject count (session): 42",
                "the session-end diagnostic line must carry the exact counter value read at shutdown");
    }

    [Fact(DisplayName = "f-005: reporter logs a zero count (table never saturated) without special-casing")]
    public void Report_EmitsInformationLine_WhenCountIsZero()
    {
        var logger = new CapturingLogger();

        HashTableRejectCountReporter.Report(logger, () => 0);

        logger.Entries.Should().ContainSingle(e => e.Level == LogLevel.Information)
            .Which.Message.Should().Contain("Hash table reject count (session): 0");
    }

    [Fact(DisplayName = "f-005: a fault reading the native counter is contained (Warning) and never blocks shutdown")]
    public void Report_WhenProviderThrows_LogsWarning_AndDoesNotPropagate()
    {
        var logger = new CapturingLogger();

        var act = () => HashTableRejectCountReporter.Report(
            logger, () => throw new InvalidOperationException("native ABI mismatch"));

        act.Should().NotThrow("a best-effort diagnostic read must never fault the shutdown path");
        logger.Entries.Should().ContainSingle(e => e.Level == LogLevel.Warning)
            .Which.Exception.Should().BeOfType<InvalidOperationException>();
    }
}
