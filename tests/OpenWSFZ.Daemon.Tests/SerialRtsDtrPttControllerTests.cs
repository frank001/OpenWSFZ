using FluentAssertions;
using Microsoft.Extensions.Logging.Abstractions;
using NSubstitute;
using OpenWSFZ.Abstractions;
using OpenWSFZ.TestSupport;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Unit tests for <see cref="SerialRtsDtrPttController"/> (FR-056, task 12.7). A
/// <see cref="FakeSerialPort"/> and an injected playback-override delegate are used
/// throughout, mirroring <see cref="CatPttController"/>'s/<see cref="AudioOnlyPttController"/>'s
/// own test seams, so no real hardware is required.
/// </summary>
#if WASAPI_SUPPORTED
[System.Runtime.Versioning.SupportedOSPlatform("windows")]
public sealed class SerialRtsDtrPttControllerTests
{
    private static readonly float[] SomeSamples = new float[606_720]; // 79 × 7680 at 48 kHz

    // ── LoadAudio + KeyDownAsync ──────────────────────────────────────────────

    [Fact(DisplayName = "CatTx-Ptt: KeyDownAsync without LoadAudio throws and does not assert the line")]
    public async Task KeyDownAsync_WithoutLoadAudio_ThrowsAndDoesNotAssertLine()
    {
        await using var sut = MakeSut(out var port);

        var act = async () => await sut.KeyDownAsync();

        await act.Should().ThrowExactlyAsync<InvalidOperationException>()
            .WithMessage("*LoadAudio*");
        port.RtsEnable.Should().BeFalse();
        port.DtrEnable.Should().BeFalse();
    }

    [Fact(DisplayName = "CatTx-Ptt: KeyDownAsync asserts the RTS line before audio playback starts (default line)")]
    public async Task KeyDownAsync_AssertsRtsBeforeAudioStarts()
    {
        var order    = new List<string>();
        var fakePort = new FakeSerialPort();
        var store    = MakeConfigStore();
        var logger   = NullLogger<SerialRtsDtrPttController>.Instance;

        // Constructed directly (not via MakeSut) so the playback-override closure can
        // reference fakePort — an out-parameter from MakeSut cannot be read inside a
        // lambda argument passed within that same call (CS0165).
        await using var sut = new SerialRtsDtrPttController(store, logger, fakePort, (_, _, _) =>
        {
            order.Add($"audio-start(rts={fakePort.RtsEnable})");
            return Task.CompletedTask;
        });

        sut.LoadAudio(SomeSamples);
        await sut.KeyDownAsync();

        fakePort.RtsEnable.Should().BeTrue();
        fakePort.DtrEnable.Should().BeFalse();
        order.Should().ContainSingle().Which.Should().Be("audio-start(rts=True)",
            "RTS must already be asserted by the time playback starts");
    }

    [Fact(DisplayName = "CatTx-Ptt: DTR line is asserted instead of RTS when configured")]
    public async Task KeyDownAsync_SerialLineDtr_AssertsDtrNotRts()
    {
        await using var sut = MakeSut(out var port, serialLine: "Dtr");

        sut.LoadAudio(SomeSamples);
        await sut.KeyDownAsync();

        port.DtrEnable.Should().BeTrue();
        port.RtsEnable.Should().BeFalse();
    }

    [Fact(DisplayName = "CatTx-Ptt: unrecognised serialLine falls back to RTS with a logged Warning")]
    public async Task KeyDownAsync_UnrecognisedSerialLine_FallsBackToRts()
    {
        var logger = new CapturingLogger();
        await using var sut = MakeSut(out var port, serialLine: "Bogus", logger: logger);

        sut.LoadAudio(SomeSamples);
        await sut.KeyDownAsync();

        port.RtsEnable.Should().BeTrue("an unrecognised serialLine value must fall back to Rts");
        port.DtrEnable.Should().BeFalse();
        logger.Entries.Should().Contain(e =>
            e.Level == Microsoft.Extensions.Logging.LogLevel.Warning &&
            e.Message.Contains("Bogus"),
            "the fallback must be logged at Warning naming the invalid value");
    }

    [Fact(DisplayName = "CatTx-Ptt: KeyDownAsync honours LeadTimeMs before audio playback starts")]
    public async Task KeyDownAsync_HonoursLeadTimeMs()
    {
        var sw = System.Diagnostics.Stopwatch.StartNew();
        TimeSpan? audioStartedAt = null;

        await using var sut = MakeSut(out _, playerOverride: (_, _, _) =>
        {
            audioStartedAt = sw.Elapsed;
            return Task.CompletedTask;
        }, leadTimeMs: 80);

        sut.LoadAudio(SomeSamples);
        await sut.KeyDownAsync();

        audioStartedAt.Should().NotBeNull();
        audioStartedAt!.Value.TotalMilliseconds.Should().BeGreaterThanOrEqualTo(
            75, "playback must not begin until at least LeadTimeMs has elapsed after the line is asserted");
    }

    [Fact(DisplayName = "CatTx-Ptt: port-open failure propagates from KeyDownAsync rather than silently skipping PTT assertion")]
    public async Task KeyDownAsync_PortOpenFails_Throws()
    {
        var fakePort = new FakeSerialPort { ThrowOnOpen = new UnauthorizedAccessException("port in use") };
        var store    = MakeConfigStore();
        var logger   = NullLogger<SerialRtsDtrPttController>.Instance;
        var sut      = new SerialRtsDtrPttController(store, logger, fakePort, (_, _, _) => Task.CompletedTask);

        sut.LoadAudio(SomeSamples);

        var act = async () => await sut.KeyDownAsync();
        await act.Should().ThrowAsync<UnauthorizedAccessException>();

        fakePort.RtsEnable.Should().BeFalse("PTT must never be asserted when the port failed to open");
        await sut.DisposeAsync();
    }

    [Fact(DisplayName = "CatTx-Ptt: PTT line is de-asserted before an exception from playback propagates")]
    public async Task KeyDownAsync_PlayerThrows_StillDeassertsLineFirst()
    {
        await using var sut = MakeSut(out var port, (_, _, _) =>
            Task.FromException(new InvalidOperationException("device busy")));

        sut.LoadAudio(SomeSamples);

        var act = async () => await sut.KeyDownAsync();
        await act.Should().ThrowExactlyAsync<InvalidOperationException>();

        port.RtsEnable.Should().BeFalse("the line must be de-asserted even though playback threw");
    }

    // ── KeyUpAsync ────────────────────────────────────────────────────────────

    [Fact(DisplayName = "CatTx-Ptt: KeyUpAsync when not asserted completes without touching the line")]
    public async Task KeyUpAsync_WhenNotAsserted_CompletesGracefully()
    {
        await using var sut = MakeSut(out var port);

        var act = async () => await sut.KeyUpAsync();
        await act.Should().NotThrowAsync();

        port.RtsEnable.Should().BeFalse();
    }

    [Fact(DisplayName = "CatTx-Ptt: KeyUpAsync de-asserts the line only after TailTimeMs has elapsed")]
    public async Task KeyUpAsync_HonoursTailTimeMsBeforeDeasserting()
    {
        await using var sut = MakeSut(out var port, (_, _, _) => Task.CompletedTask, tailTimeMs: 80);

        sut.LoadAudio(SomeSamples);
        await sut.KeyDownAsync();
        port.RtsEnable.Should().BeTrue();

        var sw = System.Diagnostics.Stopwatch.StartNew();
        await sut.KeyUpAsync();
        sw.Stop();

        port.RtsEnable.Should().BeFalse();
        sw.Elapsed.TotalMilliseconds.Should().BeGreaterThanOrEqualTo(
            75, "the line must not be de-asserted until at least TailTimeMs has elapsed");
    }

    // ── DisposeAsync ──────────────────────────────────────────────────────────

    [Fact(DisplayName = "CatTx-Ptt: DisposeAsync de-asserts the line if still asserted, and closes the port")]
    public async Task DisposeAsync_WhileAsserted_DeassertsAndClosesPort()
    {
        var fakePort = new FakeSerialPort();
        var store    = MakeConfigStore(leadTimeMs: 0, tailTimeMs: 0);
        var logger   = NullLogger<SerialRtsDtrPttController>.Instance;
        var sut      = new SerialRtsDtrPttController(
            store, logger, fakePort, (_, _, ct) => Task.Delay(Timeout.Infinite, ct));

        sut.LoadAudio(SomeSamples);
        using var cts = new CancellationTokenSource();
        var keyDownTask = sut.KeyDownAsync(cts.Token);

        // Wait until KeyDownAsync has asserted the line — before it reaches the hung player —
        // rather than guessing a fixed settle delay.
        await Poll.UntilAsync(() => fakePort.RtsEnable, timeout: TimeSpan.FromSeconds(2));
        fakePort.RtsEnable.Should().BeTrue();

        await sut.DisposeAsync();

        fakePort.RtsEnable.Should().BeFalse("DisposeAsync must force-release an asserted line");
        fakePort.CloseCallCount.Should().Be(1);
        fakePort.DisposeCallCount.Should().Be(1);

        cts.Cancel();
        try { await keyDownTask; } catch { /* expected — cancelled/disposed mid-flight */ }
    }

    [Fact(DisplayName = "CatTx-Ptt: DisposeAsync when not asserted still closes the port without touching the line")]
    public async Task DisposeAsync_WhenNotAsserted_ClosesPortOnly()
    {
        var fakePort = new FakeSerialPort();
        var store    = MakeConfigStore();
        var logger   = NullLogger<SerialRtsDtrPttController>.Instance;
        var sut      = new SerialRtsDtrPttController(store, logger, fakePort, (_, _, _) => Task.CompletedTask);

        await sut.DisposeAsync();

        fakePort.RtsEnable.Should().BeFalse();
        fakePort.DisposeCallCount.Should().Be(1);
    }

    // ── Independence from CAT ────────────────────────────────────────────────

    [Fact(DisplayName = "CatTx-Ptt: keys/unkeys correctly with no CAT dependency of any kind")]
    public async Task KeyDownAndUp_NoCatDependency_WorksStandalone()
    {
        // SerialRtsDtrPttController's constructor takes no ICatPttGate/CatPollingService
        // reference at all — this test simply proves the full cycle works using only its
        // own IConfigStore + ISerialPort, with no CAT-related type anywhere in scope.
        await using var sut = MakeSut(out var port, (_, _, _) => Task.CompletedTask);

        sut.LoadAudio(SomeSamples);
        await sut.KeyDownAsync();
        port.RtsEnable.Should().BeTrue();

        await sut.KeyUpAsync();
        port.RtsEnable.Should().BeFalse();
    }

    // ── Call-serialisation (task 17.2) ───────────────────────────────────────

    [Fact(DisplayName = "CatTx-Ptt: two concurrent KeyDownAsync callers serialise rather than interleave")]
    public async Task KeyDownAsync_TwoConcurrentCallers_Serialise()
    {
        var order     = new List<string>();
        var callCount = 0;
        var firstPlaybackReleaseGate = new TaskCompletionSource();

        var fakePort = new FakeSerialPort();
        var store    = MakeConfigStore();
        var logger   = NullLogger<SerialRtsDtrPttController>.Instance;

        await using var sut = new SerialRtsDtrPttController(store, logger, fakePort, async (_, _, _) =>
        {
            var n = Interlocked.Increment(ref callCount);
            lock (order) order.Add($"audio-start-{n}(rts={fakePort.RtsEnable})");
            if (n == 1)
                await firstPlaybackReleaseGate.Task; // held open until the test releases it
        });

        sut.LoadAudio(SomeSamples);

        // Caller #1 — simulates the real, active QsoAnswererService/QsoCallerService
        // transmission — begins and stays "mid-transmission" until released below.
        var firstKeyDown = sut.KeyDownAsync();

        await Poll.UntilAsync(() => callCount >= 1, timeout: TimeSpan.FromSeconds(2));
        callCount.Should().Be(1, "caller #1 must have started its playback by now");
        fakePort.RtsEnable.Should().BeTrue("caller #1 must have asserted PTT by now");

        // Caller #2 — simulates a Settings-page Test click racing the real transmission.
        var secondKeyDown = Task.Run(() => sut.KeyDownAsync());

        // Give caller #2 a chance to (incorrectly) race ahead if the lock were missing: poll for
        // the forbidden second playback and require it never appears within the window, instead of
        // a bare fixed delay (fix-flaky-test-delay-synchronization). A broken lock would push
        // callCount to 2 promptly and this poll would return without throwing.
        var raceAhead = async () => await Poll.WaitForEqualAsync(() => callCount, 2,
            timeout: TimeSpan.FromMilliseconds(100));
        await raceAhead.Should().ThrowAsync<TimeoutException>();
        callCount.Should().Be(1,
            "caller #2 must remain blocked behind caller #1's still-open KeyUpAsync — it must " +
            "not be able to assert (and, worse, later de-assert) the line while caller #1's real " +
            "transmission is still in flight");

        // Complete caller #1's cycle exactly as the real state machine would.
        firstPlaybackReleaseGate.SetResult();
        await firstKeyDown;
        await sut.KeyUpAsync();

        // Caller #2 must now be able to proceed and assert the line for its own cycle.
        await secondKeyDown.WaitAsync(TimeSpan.FromSeconds(5));

        callCount.Should().Be(2);
        order.Should().Equal(["audio-start-1(rts=True)", "audio-start-2(rts=True)"],
            "caller #2's playback must not start until caller #1's KeyUpAsync has completed");
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private static IConfigStore MakeConfigStore(
        string serialLine = "Rts", int leadTimeMs = 0, int tailTimeMs = 0, int watchdogTimeoutMs = 20_000)
    {
        var store = Substitute.For<IConfigStore>();
        store.Current.Returns(new AppConfig() with
        {
            Ptt = new PttConfig
            {
                Method            = "SerialRtsDtr",
                SerialLine        = serialLine,
                LeadTimeMs        = leadTimeMs,
                TailTimeMs        = tailTimeMs,
                WatchdogTimeoutMs = watchdogTimeoutMs,
            }
        });
        return store;
    }

    private static SerialRtsDtrPttController MakeSut(
        out FakeSerialPort port,
        Func<float[], string?, CancellationToken, Task>? playerOverride = null,
        string serialLine = "Rts",
        int leadTimeMs = 0,
        int tailTimeMs = 0,
        int watchdogTimeoutMs = 20_000,
        CapturingLogger? logger = null)
    {
        var fakePort = new FakeSerialPort();
        port = fakePort;

        var store = MakeConfigStore(serialLine, leadTimeMs, tailTimeMs, watchdogTimeoutMs);
        Microsoft.Extensions.Logging.ILogger<SerialRtsDtrPttController> log = logger is not null
            ? logger
            : NullLogger<SerialRtsDtrPttController>.Instance;

        return new SerialRtsDtrPttController(
            store, log, fakePort, playerOverride ?? ((_, _, _) => Task.CompletedTask));
    }

    // ── Test logger (shared shape with PttWatchdogTests, kept local to avoid a
    //    cross-file dependency on an internal test type) ────────────────────

    private sealed class CapturingLogger : Microsoft.Extensions.Logging.ILogger<SerialRtsDtrPttController>
    {
        public List<(Microsoft.Extensions.Logging.LogLevel Level, string Message)> Entries { get; } = new();

        public IDisposable BeginScope<TState>(TState state) where TState : notnull => NullScope.Instance;
        public bool IsEnabled(Microsoft.Extensions.Logging.LogLevel logLevel) => true;

        public void Log<TState>(
            Microsoft.Extensions.Logging.LogLevel logLevel, Microsoft.Extensions.Logging.EventId eventId,
            TState state, Exception? exception, Func<TState, Exception?, string> formatter)
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
#endif
