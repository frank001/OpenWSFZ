using FluentAssertions;
using Microsoft.Extensions.Logging;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Unit tests for <see cref="PttControllerSelector"/> (FR-056, task 12.9) — the pure
/// mapping <c>Program.cs</c> uses to pick which concrete <c>IPttController</c> to
/// register for each <c>AppConfig.Ptt.Method</c> value.
/// </summary>
[Trait("Category", "Unit")]
public sealed class PttControllerSelectorTests
{
    // xUnit test methods must be public, but PttControllerKind is internal — an enum-typed
    // [Theory] parameter would trip CS0051 (inconsistent accessibility). Three explicit
    // [Fact]s instead; the enum is only ever used inside each method body, never in a
    // public signature.

    [Fact(DisplayName = "CatTx-Ptt: Ptt.Method \"AudioVox\" resolves to PttControllerKind.AudioVox")]
    public void Resolve_AudioVox_ReturnsAudioVox()
    {
        var logger = new CapturingLogger();

        var kind = PttControllerSelector.Resolve("AudioVox", logger);

        kind.Should().Be(PttControllerKind.AudioVox);
        logger.Entries.Should().BeEmpty("a recognised method must not log anything");
    }

    [Fact(DisplayName = "CatTx-Ptt: Ptt.Method \"CatCommand\" resolves to PttControllerKind.CatCommand")]
    public void Resolve_CatCommand_ReturnsCatCommand()
    {
        var logger = new CapturingLogger();

        var kind = PttControllerSelector.Resolve("CatCommand", logger);

        kind.Should().Be(PttControllerKind.CatCommand);
        logger.Entries.Should().BeEmpty("a recognised method must not log anything");
    }

    [Fact(DisplayName = "CatTx-Ptt: Ptt.Method \"SerialRtsDtr\" resolves to PttControllerKind.SerialRtsDtr")]
    public void Resolve_SerialRtsDtr_ReturnsSerialRtsDtr()
    {
        var logger = new CapturingLogger();

        var kind = PttControllerSelector.Resolve("SerialRtsDtr", logger);

        kind.Should().Be(PttControllerKind.SerialRtsDtr);
        logger.Entries.Should().BeEmpty("a recognised method must not log anything");
    }

    [Fact(DisplayName = "CatTx-Ptt: unrecognised Ptt.Method falls back to AudioVox and logs a Warning naming the invalid value")]
    public void Resolve_UnrecognisedMethod_FallsBackToAudioVoxAndLogsWarning()
    {
        var logger = new CapturingLogger();

        var kind = PttControllerSelector.Resolve("SomeBogusMethod", logger);

        kind.Should().Be(PttControllerKind.AudioVox);
        logger.Entries.Should().Contain(e =>
            e.Level == LogLevel.Warning && e.Message.Contains("SomeBogusMethod"),
            "the fallback must be logged at Warning naming the invalid value");
    }

    [Fact(DisplayName = "CatTx-Ptt: missing/default Ptt.Method (\"AudioVox\") resolves to AudioVox — preserves today's behaviour")]
    public void Resolve_DefaultMethod_ResolvesToAudioVox()
    {
        var logger = new CapturingLogger();
        var defaultMethod = new OpenWSFZ.Abstractions.PttConfig().Method;

        var kind = PttControllerSelector.Resolve(defaultMethod, logger);

        kind.Should().Be(PttControllerKind.AudioVox);
    }

    // ── Test logger ───────────────────────────────────────────────────────────

    private sealed class CapturingLogger : ILogger
    {
        public List<(LogLevel Level, string Message)> Entries { get; } = new();

        public IDisposable BeginScope<TState>(TState state) where TState : notnull => NullScope.Instance;
        public bool IsEnabled(LogLevel logLevel) => true;

        public void Log<TState>(
            LogLevel logLevel, EventId eventId, TState state, Exception? exception,
            Func<TState, Exception?, string> formatter)
        {
            lock (Entries) Entries.Add((logLevel, formatter(state, exception)));
        }

        private sealed class NullScope : IDisposable
        {
            public static readonly NullScope Instance = new();
            public void Dispose() { }
        }
    }
}
