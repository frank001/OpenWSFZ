using System.Text.RegularExpressions;
using FluentAssertions;
using Microsoft.Extensions.Logging;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// Unit tests for <see cref="CaptureHealthMonitor"/> (capture-stall-detection-unattended #188,
/// design.md Decision 1). Exercises <see cref="CaptureHealthMonitor.TickOnceAsync"/> directly —
/// the unit under test has no dependency on wall-clock time, so these simulate N windows by
/// calling it N times rather than waiting through real 5 s sleeps (gate G10).
///
/// Maps to tasks.md §5: U3 (headless watchdog / N-client over-tick regression), U4
/// (lastChunkAgeMs — see <c>DataFlowMonitorTests</c> for the field itself; this file covers the
/// ticker wiring), U6 (surfaces agree — REST/WS side covered in <c>WebSocketTests</c>/
/// <c>StatusAndBindingTests</c>; this file covers the shared snapshot the ticker publishes), and
/// U7 (heartbeat format).
/// </summary>
public sealed class CaptureHealthMonitorTests
{
    // ── Test doubles ─────────────────────────────────────────────────────────

    /// <summary>
    /// <see cref="ILogger{T}"/> that records every log entry for assertion — local to this file,
    /// mirroring <c>HashTableRejectCountLoggingTests</c>' equivalent test double.
    /// </summary>
    private sealed class RecordingLogger<T> : ILogger<T>
    {
        private readonly List<(LogLevel Level, string Message)> _entries = new();
        private readonly object _lock = new();

        public IReadOnlyList<(LogLevel Level, string Message)> Entries
        {
            get { lock (_lock) return [.. _entries]; }
        }

        IDisposable? ILogger.BeginScope<TState>(TState state) => null;
        bool ILogger.IsEnabled(LogLevel logLevel) => true;

        void ILogger.Log<TState>(
            LogLevel logLevel, EventId eventId, TState state, Exception? exception,
            Func<TState, Exception?, string> formatter)
        {
            var msg = formatter(state, exception);
            lock (_lock) _entries.Add((logLevel, msg));
        }
    }

    private static RecordingLogger<CaptureHealthMonitorTests> NewLogger() => new();

    // ── U3: headless watchdog / N-client over-tick regression ──────────────────

    [Fact(DisplayName = "FR-067: zero clients — exactly one restart after 3 consecutive silent windows while capturing (U3)")]
    public async Task TickOnceAsync_HeadlessWatchdog_FiresOnceAfterThreeSilentWindows()
    {
        // "Zero clients" is structural here, not a parameter: TickOnceAsync takes no client-count
        // argument at all, so this proves the watchdog fires purely from windows evaluated,
        // exactly as it would with a browser tab open or none (design D1).
        var restarts = 0;
        var watchdog = new AudioWatchdog(
            isCapturing: () => true,
            onRestart:   () => { restarts++; return Task.CompletedTask; },
            threshold:   3);
        var dataFlow = new DataFlowMonitor();
        var monitor  = new CaptureHealthMonitor(
            isCapturing:     () => true,
            dataFlowMonitor: dataFlow,
            watchdog:        watchdog,
            logger:          NewLogger());

        await monitor.TickOnceAsync(); // window 1 — silent
        await monitor.TickOnceAsync(); // window 2 — silent
        restarts.Should().Be(0, "the threshold has not been reached yet");

        await monitor.TickOnceAsync(); // window 3 — silent, crosses threshold

        restarts.Should().Be(1, "exactly one restart after 3 consecutive silent windows");
        monitor.WatchdogRestartCount.Should().Be(1, "WatchdogRestartCount must reflect the same fired restart");
    }

    [Fact(DisplayName = "FR-067: the watchdog advances exactly once per TickOnceAsync call, independent of however many readers observe Current concurrently (N-client over-tick regression, U3)")]
    public async Task TickOnceAsync_AdvancesWatchdogExactlyOncePerCall_RegardlessOfConcurrentReaders()
    {
        // Before this change, N connected WebSocket clients each independently ticked the SAME
        // singleton watchdog on their own 5 s timer, reaching the threshold after ~15/N seconds
        // instead of 15 s. Here, several "readers" (standing in for connected clients) poll
        // Current concurrently on their own loop WHILE the test drives exactly 10 windows via
        // TickOnceAsync — the assertion is that the watchdog only ever sees 10 ticks, because
        // reading Current cannot itself tick anything (design D6: WebSocket connections are pure
        // readers).
        var restarts = 0;
        var watchdog = new AudioWatchdog(
            isCapturing: () => true,
            onRestart:   () => { restarts++; return Task.CompletedTask; },
            threshold:   11); // higher than the 10 windows driven below — must never fire
        var dataFlow = new DataFlowMonitor();
        var monitor  = new CaptureHealthMonitor(
            isCapturing:     () => true,
            dataFlowMonitor: dataFlow,
            watchdog:        watchdog,
            logger:          NewLogger());

        using var readerCts = new CancellationTokenSource();
        var readers = Enumerable.Range(0, 3).Select(readerIndex => Task.Run(async () =>
        {
            while (!readerCts.IsCancellationRequested)
            {
                _ = monitor.Current; // simulates a connected client's heartbeat-loop read
                await Task.Yield();
            }
        })).ToArray();

        try
        {
            for (var i = 0; i < 10; i++)
                await monitor.TickOnceAsync();
        }
        finally
        {
            readerCts.Cancel();
            await Task.WhenAll(readers);
        }

        restarts.Should().Be(0,
            "10 windows must advance the watchdog exactly 10 times — below the threshold of 11 — " +
            "regardless of how many concurrent readers observed Current in between");

        // Prove the accounting is exact (not merely "didn't over-fire"): one more window must be
        // enough to cross the threshold, confirming the internal silent-window count is exactly 10,
        // not fewer.
        await monitor.TickOnceAsync();
        restarts.Should().Be(1, "the 11th window must be exactly the one that crosses the threshold");
    }

    [Fact(DisplayName = "FR-067: stopped capture is not a stall — the watchdog never fires however many windows pass")]
    public async Task TickOnceAsync_NeverFires_WhenCaptureIsNotActive()
    {
        var restarts = 0;
        var watchdog = new AudioWatchdog(
            isCapturing: () => false, // no capture session running
            onRestart:   () => { restarts++; return Task.CompletedTask; },
            threshold:   3);
        var dataFlow = new DataFlowMonitor();
        var monitor  = new CaptureHealthMonitor(
            isCapturing:     () => false,
            dataFlowMonitor: dataFlow,
            watchdog:        watchdog,
            logger:          NewLogger());

        for (var i = 0; i < 10; i++)
            await monitor.TickOnceAsync();

        restarts.Should().Be(0, "the watchdog must never trigger a restart for a pipeline that isn't running");
        monitor.Current.CaptureActive.Should().BeFalse();
    }

    // ── U6: audioActive == dataFlowing of the last completed window, on the published snapshot ──

    [Fact(DisplayName = "FR-069: AudioActive on the published snapshot always equals DataFlowing (Captain-ratified Option A, U6)")]
    public async Task Snapshot_AudioActiveEqualsDataFlowing_Always()
    {
        var dataFlow = new DataFlowMonitor();
        var monitor  = new CaptureHealthMonitor(
            isCapturing:     () => true,
            dataFlowMonitor: dataFlow,
            watchdog:        null,
            logger:          NewLogger());

        // Window with a chunk.
        dataFlow.OnChunkReceived();
        await monitor.TickOnceAsync();
        monitor.Current.DataFlowing.Should().BeTrue();
        monitor.Current.AudioActive.Should().BeTrue("Option A: audioActive == dataFlowing, everywhere");

        // Window without a chunk.
        await monitor.TickOnceAsync();
        monitor.Current.DataFlowing.Should().BeFalse();
        monitor.Current.AudioActive.Should().BeFalse("audioActive must fall the moment dataFlowing does — it does not latch");
    }

    [Fact(DisplayName = "FR-067: quiet-but-flowing audio (chunks delivered, samples near zero) is not a stall")]
    public async Task TickOnceAsync_QuietButFlowing_IsNotAStall()
    {
        // DataFlowMonitor.OnChunkReceived() carries no amplitude information — any chunk counts,
        // which is exactly the distinction this scenario exercises (spec.md "Quiet but flowing
        // audio is not a stall").
        var restarts = 0;
        var watchdog = new AudioWatchdog(
            isCapturing: () => true,
            onRestart:   () => { restarts++; return Task.CompletedTask; },
            threshold:   3);
        var dataFlow = new DataFlowMonitor();
        var monitor  = new CaptureHealthMonitor(
            isCapturing:     () => true,
            dataFlowMonitor: dataFlow,
            watchdog:        watchdog,
            logger:          NewLogger());

        for (var i = 0; i < 6; i++)
        {
            dataFlow.OnChunkReceived(); // a chunk arrives every window, amplitude irrelevant
            await monitor.TickOnceAsync();
        }

        restarts.Should().Be(0, "chunks were delivered every window — never a stall, regardless of amplitude");
        monitor.Current.DataFlowing.Should().BeTrue();
        monitor.Current.AudioActive.Should().BeTrue();
    }

    // ── U7: Heartbeat: line format ───────────────────────────────────────────

    [Fact(DisplayName = "U7: the Heartbeat: line matches the exact byte-identical lowercase format, once per TickOnceAsync call")]
    public async Task TickOnceAsync_WritesHeartbeatLine_ExactFormat()
    {
        var logger = NewLogger();
        var dataFlow = new DataFlowMonitor();
        var monitor  = new CaptureHealthMonitor(
            isCapturing:     () => true,
            dataFlowMonitor: dataFlow,
            watchdog:        null,
            logger:          logger);

        dataFlow.OnChunkReceived();
        await monitor.TickOnceAsync(); // flowing window
        await monitor.TickOnceAsync(); // silent window

        var heartbeatLines = logger.Entries
            .Where(e => e.Message.StartsWith("Heartbeat:", StringComparison.Ordinal))
            .ToList();

        heartbeatLines.Should().HaveCount(2, "exactly one Heartbeat: line per TickOnceAsync call");

        var regex = new Regex(
            "^Heartbeat: captureActive=(true|false), audioActive=(true|false), dataFlowing=(true|false)$",
            RegexOptions.None);

        foreach (var (level, message) in heartbeatLines)
        {
            level.Should().Be(LogLevel.Information, "the Heartbeat: line must be written at Information level");
            regex.IsMatch(message).Should().BeTrue(
                $"'{message}' must match the exact lowercase format — older QA supervisor scripts string-match on it");
        }

        heartbeatLines[0].Message.Should().Be("Heartbeat: captureActive=true, audioActive=true, dataFlowing=true");
        heartbeatLines[1].Message.Should().Be("Heartbeat: captureActive=true, audioActive=false, dataFlowing=false");
    }

    [Fact(DisplayName = "U7: exactly one Heartbeat: line is written per window regardless of how many readers observe Current in between (0/1/N \"clients\")")]
    public async Task TickOnceAsync_WritesExactlyOneHeartbeatLine_PerWindow_RegardlessOfReaderCount()
    {
        var logger   = NewLogger();
        var dataFlow = new DataFlowMonitor();
        var monitor  = new CaptureHealthMonitor(
            isCapturing:     () => false,
            dataFlowMonitor: dataFlow,
            watchdog:        null,
            logger:          logger);

        const int windows = 5;
        for (var i = 0; i < windows; i++)
            await monitor.TickOnceAsync();

        // Simulate 0, then 1, then N readers observing the same published snapshot — none of
        // these reads may themselves write a Heartbeat: line (design D5/D6: the ticker alone
        // owns the log line; WebSocket connections are pure readers).
        _ = monitor.Current;
        for (var i = 0; i < 4; i++) _ = monitor.Current;

        var heartbeatCount = logger.Entries.Count(e => e.Message.StartsWith("Heartbeat:", StringComparison.Ordinal));
        heartbeatCount.Should().Be(windows,
            "exactly one Heartbeat: line per window evaluated, unaffected by how many times Current is read");
    }

    // ── WatchdogRestartCount wiring ──────────────────────────────────────────

    [Fact(DisplayName = "FR-068: WatchdogRestartCount is 0 when no watchdog is wired, and TickOnceAsync does not throw")]
    public async Task WatchdogRestartCount_IsZero_WhenWatchdogIsNull()
    {
        var dataFlow = new DataFlowMonitor();
        var monitor  = new CaptureHealthMonitor(
            isCapturing:     () => true,
            dataFlowMonitor: dataFlow,
            watchdog:        null,
            logger:          NewLogger());

        for (var i = 0; i < 5; i++)
            await monitor.TickOnceAsync();

        monitor.WatchdogRestartCount.Should().Be(0, "no watchdog is wired — there is nothing to count");
    }

    [Fact(DisplayName = "FR-068: WatchdogRestartCount tracks the watchdog's own RestartCount exactly (single source of truth)")]
    public async Task WatchdogRestartCount_TracksUnderlyingWatchdog()
    {
        var watchdog = new AudioWatchdog(
            isCapturing: () => true,
            onRestart:   () => Task.CompletedTask,
            threshold:   3);
        var dataFlow = new DataFlowMonitor();
        var monitor  = new CaptureHealthMonitor(
            isCapturing:     () => true,
            dataFlowMonitor: dataFlow,
            watchdog:        watchdog,
            logger:          NewLogger());

        for (var i = 0; i < 3; i++)
            await monitor.TickOnceAsync(); // fires at window 3

        monitor.WatchdogRestartCount.Should().Be(watchdog.RestartCount)
            .And.Be(1);
    }

    // ── Initial snapshot / empty default ────────────────────────────────────

    [Fact(DisplayName = "CaptureHealthSnapshot.Empty is all-false — the fallback every surface reports with no monitor wired")]
    public void Empty_IsAllFalse()
    {
        var empty = CaptureHealthSnapshot.Empty;

        empty.CaptureActive.Should().BeFalse();
        empty.DataFlowing.Should().BeFalse();
        empty.AudioActive.Should().BeFalse();
    }

    [Fact(DisplayName = "FR-067: the initial snapshot before any TickOnceAsync call is all-false (dataFlowing is false before the first window completes)")]
    public void Current_IsAllFalse_BeforeFirstTick()
    {
        var dataFlow = new DataFlowMonitor();
        var monitor  = new CaptureHealthMonitor(
            isCapturing:     () => true,
            dataFlowMonitor: dataFlow,
            watchdog:        null,
            logger:          NewLogger());

        monitor.Current.CaptureActive.Should().BeFalse();
        monitor.Current.DataFlowing.Should().BeFalse();
        monitor.Current.AudioActive.Should().BeFalse();
    }
}
