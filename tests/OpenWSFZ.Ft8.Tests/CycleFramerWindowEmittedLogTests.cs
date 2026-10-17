using System.Text.RegularExpressions;
using FluentAssertions;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Ft8;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// capture-loss-instrument 1.7: the framer's per-window line is the loss-agnostic check on the
/// other loss points, so it must be visible at Information and carry both what the grid asked
/// for (<c>wanted</c>) and what was applied, in samples.  The alignment behaviour itself is
/// pinned by the existing oracle tests, which this change does not touch.
/// </summary>
public sealed class CycleFramerWindowEmittedLogTests
{
    private const int    SampleRate  = 12_000;
    private const double DriftedHz   = 11_999.42; // 48.4 ppm slow: a small non-zero `wanted` every window
    private const int    ChunkSamples = 2048;

    private static readonly Regex Line = new(
        @"^Window emitted \((?<samples>\d+) samples, cycle (?<cycle>\d\d:\d\d:\d\d)\); " +
        @"wanted (?<wanted>-?\d+), applied (?<applied>-?\d+) samples; consumed (?<consumed>\d+) source samples",
        RegexOptions.CultureInvariant);

    private sealed class ListLogger : ILogger<CycleFramer>
    {
        private readonly List<(LogLevel Level, string Message)> _entries = new();
        public IReadOnlyList<(LogLevel Level, string Message)> Entries { get { lock (_entries) return [.. _entries]; } }

        IDisposable? ILogger.BeginScope<TState>(TState state) => null;
        bool ILogger.IsEnabled(LogLevel logLevel) => true;
        void ILogger.Log<TState>(LogLevel logLevel, EventId eventId, TState state,
            Exception? exception, Func<TState, Exception?, string> formatter)
        {
            lock (_entries) _entries.Add((logLevel, formatter(state, exception)));
        }
    }

    [Fact(DisplayName = "capture-loss 1.7: every emitted window logs one Information line with cycle start, wanted and applied samples")]
    public async Task EveryWindow_LogsInformation_WithCycleStart_Wanted_AndApplied()
    {
        var startUtc = new DateTime(2026, 1, 1, 0, 0, 0, DateTimeKind.Utc);
        var clock    = new FakeClock(startUtc);
        long total   = (long)Math.Round(DriftedHz * 20 * 60); // 20 minutes of drifting capture

        var device   = new SimulatedCaptureDevice(clock, startUtc, DriftedHz, ChunkSamples, total);
        var recorder = new WindowRecorder();
        var logger   = new ListLogger();
        var framer   = new CycleFramer(device, clock, logger);

        await framer.RunAsync(recorder, CancellationToken.None);

        var emitted = logger.Entries.Where(e => e.Message.StartsWith("Window emitted (")).ToList();
        emitted.Should().HaveCount(recorder.Windows.Count, "one line per emitted window");
        emitted.Should().OnlyContain(e => e.Level == LogLevel.Information,
            "the line is the loss-agnostic check and must be on by default (it was Debug)");

        var parsed = emitted.Select(e => Line.Match(e.Message)).ToList();
        parsed.Should().OnlyContain(m => m.Success, "every line carries cycle, wanted, applied and consumed");

        for (int i = 0; i < parsed.Count; i++)
        {
            var m       = parsed[i];
            int wanted  = int.Parse(m.Groups["wanted"].Value);
            int applied = int.Parse(m.Groups["applied"].Value);
            int consumed = int.Parse(m.Groups["consumed"].Value);

            m.Groups["cycle"].Value.Should().Be(recorder.Windows[i].CycleStart.ToString("HH:mm:ss"));
            applied.Should().Be(Math.Clamp(wanted, -3_000, 3_000), "applied is wanted after the 250 ms clamp");
            consumed.Should().Be(180_000 - applied, "consume is the window length minus the applied correction");
        }

        // A drifting source must show a non-zero `wanted` somewhere, or the field is not being filled.
        parsed.Skip(1).Select(m => int.Parse(m.Groups["wanted"].Value)).Should().Contain(w => w != 0,
            "48 ppm of drift asks for a correction on most windows");
    }
}
