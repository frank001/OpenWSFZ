using FluentAssertions;
using OpenWSFZ.Daemon.Logging;
using Serilog;
using Serilog.Core;
using Serilog.Events;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// A trivial <see cref="ILogEventSink"/> that appends every received event to a list, so tests
/// can assert on exactly which sink (i.e. which underlying logger) an event reached.
/// </summary>
internal sealed class RecordingSink : ILogEventSink
{
    public List<LogEvent> Events { get; } = [];
    public void Emit(LogEvent logEvent) => Events.Add(logEvent);
}

/// <summary>
/// Unit tests for <see cref="ReconfigurableLogger"/> — the fix for the Serilog/MEL logger
/// staleness bug found during f-004 manual verification (log-viewer): Serilog.Extensions.
/// Logging's <c>SerilogLogger</c> resolves <c>Serilog.Log.Logger</c> exactly once per category,
/// on that category's first use, and caches the result forever — so reassigning
/// <c>Log.Logger</c> to a brand-new object (as <see cref="LoggingPipeline.Apply"/> previously
/// did on every reconfigure) is invisible to any <c>ILogger&lt;T&gt;</c> resolved before that
/// point. These tests reproduce that exact shape (capture a reference, THEN swap the target,
/// THEN write through the captured reference) without needing a full ASP.NET Core host.
/// </summary>
public sealed class ReconfigurableLoggerTests
{
    [Fact(DisplayName = "log-viewer: writing directly through the wrapper reaches the current inner logger after Reconfigure")]
    public void Write_AfterReconfigure_ReachesNewInnerLogger()
    {
        var sink1 = new RecordingSink();
        var sink2 = new RecordingSink();
        using var logger1 = new LoggerConfiguration().WriteTo.Sink(sink1).CreateLogger();
        using var logger2 = new LoggerConfiguration().WriteTo.Sink(sink2).CreateLogger();

        var wrapper = new ReconfigurableLogger(logger1);
        // Typed as Serilog.ILogger, matching how the real code uses it (assigned to
        // Serilog.Log.Logger, itself an ILogger) — the concrete class does not itself expose
        // the interface's default convenience methods (e.g. Information); they must be called
        // through the interface, exactly as with any other C# default interface member.
        Serilog.ILogger loggerRef = wrapper;

        loggerRef.Information("event-one");
        sink1.Events.Should().ContainSingle();
        sink2.Events.Should().BeEmpty();

        wrapper.Reconfigure(logger2);
        loggerRef.Information("event-two");

        sink1.Events.Should().ContainSingle("no further events should reach the old logger after Reconfigure");
        sink2.Events.Should().ContainSingle("the new logger must receive events written after Reconfigure");
    }

    [Fact(DisplayName = "log-viewer: a reference captured via ForContext BEFORE Reconfigure still reaches the new inner logger AFTER it")]
    public void Write_ThroughPreCapturedForContextLogger_ReachesNewInnerLoggerAfterReconfigure()
    {
        // This is the exact shape of the real bug: Serilog.Extensions.Logging's SerilogLogger
        // constructor does the equivalent of `_logger = Log.Logger.ForContext(...)` exactly once,
        // then never re-reads Log.Logger again — so `contextualLogger` here plays the role of
        // that permanently-cached per-category ILogger.
        var sink1 = new RecordingSink();
        var sink2 = new RecordingSink();
        using var logger1 = new LoggerConfiguration().WriteTo.Sink(sink1).CreateLogger();
        using var logger2 = new LoggerConfiguration().WriteTo.Sink(sink2).CreateLogger();

        var wrapper = new ReconfigurableLogger(logger1);
        Serilog.ILogger loggerRef = wrapper;

        // Captured ONCE, "early" — mirrors ILogger<T> being resolved once at DI/host startup.
        Serilog.ILogger contextualLogger = loggerRef.ForContext<ReconfigurableLoggerTests>();

        contextualLogger.Information("before-reconfigure");
        sink1.Events.Should().ContainSingle();

        // Simulates LoggingPipeline.Apply() swapping the target — e.g. the operator enabling
        // file logging via the Settings page while the daemon is already running.
        wrapper.Reconfigure(logger2);

        // Reusing the SAME captured reference — this is what a cached ILogger<T> would do; it
        // never re-resolves anything, it just calls back into the object it already has.
        contextualLogger.Information("after-reconfigure");

        sink1.Events.Should().ContainSingle(
            "the pre-captured logger must not keep writing to the old target after Reconfigure");
        sink2.Events.Should().ContainSingle(
            "the pre-captured logger must observe the new target — this is the entire point of " +
            "ReconfigurableLogger: fixing exactly this staleness for every already-resolved " +
            "ILogger<T> in the application, without needing to touch DI/MEL bridging code");
    }

    [Fact(DisplayName = "log-viewer: IsEnabled reflects the current inner logger's configured level after Reconfigure")]
    public void IsEnabled_AfterReconfigure_ReflectsNewInnerLoggersLevel()
    {
        using var permissiveLogger = new LoggerConfiguration()
            .MinimumLevel.Verbose()
            .WriteTo.Sink(new RecordingSink())
            .CreateLogger();
        using var restrictiveLogger = new LoggerConfiguration()
            .MinimumLevel.Warning()
            .WriteTo.Sink(new RecordingSink())
            .CreateLogger();

        var wrapper = new ReconfigurableLogger(permissiveLogger);
        Serilog.ILogger loggerRef = wrapper;
        loggerRef.IsEnabled(LogEventLevel.Debug).Should().BeTrue();

        wrapper.Reconfigure(restrictiveLogger);
        loggerRef.IsEnabled(LogEventLevel.Debug).Should().BeFalse(
            "IsEnabled must reflect whichever inner logger is current, not a stale snapshot");
    }
}
