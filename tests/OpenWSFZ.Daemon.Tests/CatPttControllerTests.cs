using FluentAssertions;
using Microsoft.Extensions.Logging.Abstractions;
using NSubstitute;
using OpenWSFZ.Abstractions;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Unit tests for <see cref="CatPttController"/> (FR-056, task 12.6).
/// A mocked <see cref="ICatPttGate"/> and an injected playback-override delegate are
/// used throughout, mirroring <see cref="AudioOnlyPttController"/>'s own test seam, so
/// no real CAT link or WASAPI hardware is required.
/// </summary>
#if WASAPI_SUPPORTED
[System.Runtime.Versioning.SupportedOSPlatform("windows")]
public sealed class CatPttControllerTests
{
    private static readonly float[] SomeSamples = new float[606_720]; // 79 × 7680 at 48 kHz

    // ── LoadAudio + KeyDownAsync ──────────────────────────────────────────────

    [Fact(DisplayName = "CatTx-Ptt: KeyDownAsync without LoadAudio throws and does not assert PTT")]
    public async Task KeyDownAsync_WithoutLoadAudio_ThrowsAndDoesNotAssertPtt()
    {
        await using var sut = MakeSut(out var gate);

        var act = async () => await sut.KeyDownAsync();

        await act.Should().ThrowExactlyAsync<InvalidOperationException>()
            .WithMessage("*LoadAudio*");
        await gate.DidNotReceive().SetPttAsync(Arg.Any<bool>(), Arg.Any<CancellationToken>());
    }

    [Fact(DisplayName = "CatTx-Ptt: KeyDownAsync asserts PTT before audio playback starts")]
    public async Task KeyDownAsync_AssertsPttBeforeAudioStarts()
    {
        var order = new List<string>();

        await using var sut = MakeSut(out var gate, playerOverride: (_, _, _) =>
        {
            order.Add("audio-start");
            return Task.CompletedTask;
        });
        gate.SetPttAsync(true, Arg.Any<CancellationToken>())
            .Returns(_ => { order.Add("ptt-on"); return Task.CompletedTask; });

        sut.LoadAudio(SomeSamples);
        await sut.KeyDownAsync();

        order.Should().Equal("ptt-on", "audio-start");
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
            75, "playback must not begin until at least LeadTimeMs has elapsed after PTT is asserted");
    }

    [Fact(DisplayName = "CatTx-Ptt: KeyDownAsync propagates player delegate exception")]
    public async Task KeyDownAsync_PlayerThrows_PropagatesException()
    {
        await using var sut = MakeSut(out _, (_, _, _) =>
            Task.FromException(new InvalidOperationException("device busy")));

        sut.LoadAudio(SomeSamples);

        var act = async () => await sut.KeyDownAsync();
        await act.Should().ThrowExactlyAsync<InvalidOperationException>()
            .WithMessage("device busy");
    }

    [Fact(DisplayName = "CatTx-Ptt: PTT is released before the exception propagates when playback throws")]
    public async Task KeyDownAsync_PlayerThrows_StillReleasesPttFirst()
    {
        await using var sut = MakeSut(out var gate, (_, _, _) =>
            Task.FromException(new InvalidOperationException("device busy")));

        sut.LoadAudio(SomeSamples);

        var act = async () => await sut.KeyDownAsync();
        await act.Should().ThrowExactlyAsync<InvalidOperationException>();

        await gate.Received(1).SetPttAsync(true, Arg.Any<CancellationToken>());
        await gate.Received(1).SetPttAsync(false, Arg.Any<CancellationToken>());
    }

    // ── KeyUpAsync ────────────────────────────────────────────────────────────

    [Fact(DisplayName = "CatTx-Ptt: KeyUpAsync when not asserted completes without releasing PTT")]
    public async Task KeyUpAsync_WhenNotAsserted_CompletesGracefully()
    {
        await using var sut = MakeSut(out var gate);

        var act = async () => await sut.KeyUpAsync();
        await act.Should().NotThrowAsync();

        await gate.DidNotReceive().SetPttAsync(Arg.Any<bool>(), Arg.Any<CancellationToken>());
    }

    [Fact(DisplayName = "CatTx-Ptt: KeyUpAsync releases PTT only after TailTimeMs has elapsed")]
    public async Task KeyUpAsync_HonoursTailTimeMsBeforeReleasingPtt()
    {
        TimeSpan? releasedAt = null;
        var sw = System.Diagnostics.Stopwatch.StartNew();

        await using var sut = MakeSut(out var gate, (_, _, _) => Task.CompletedTask, tailTimeMs: 80);
        gate.SetPttAsync(false, Arg.Any<CancellationToken>())
            .Returns(_ => { releasedAt = sw.Elapsed; return Task.CompletedTask; });

        sut.LoadAudio(SomeSamples);
        await sut.KeyDownAsync();

        sw.Restart();
        await sut.KeyUpAsync();

        releasedAt.Should().NotBeNull();
        releasedAt!.Value.TotalMilliseconds.Should().BeGreaterThanOrEqualTo(
            75, "PTT must not be released until at least TailTimeMs has elapsed after playback stops");
    }

    // ── DisposeAsync ──────────────────────────────────────────────────────────

    [Fact(DisplayName = "CatTx-Ptt: DisposeAsync releases PTT if still asserted")]
    public async Task DisposeAsync_WhilePttAsserted_ReleasesPtt()
    {
        var sut  = MakeSut(out var gate, (_, _, ct) => Task.Delay(Timeout.Infinite, ct));
        // KeyDownAsync will hang on the infinite delay — fire it without awaiting so we
        // can dispose while PTT is still asserted but playback is mid-flight.
        sut.LoadAudio(SomeSamples);
        using var cts = new CancellationTokenSource();
        var keyDownTask = sut.KeyDownAsync(cts.Token);

        // Give KeyDownAsync time to assert PTT and reach the (infinitely) blocked player.
        await Task.Delay(50);

        await sut.DisposeAsync();

        await gate.Received(1).SetPttAsync(false, Arg.Any<CancellationToken>());

        cts.Cancel();
        try { await keyDownTask; } catch { /* expected — cancelled/disposed mid-flight */ }
    }

    [Fact(DisplayName = "CatTx-Ptt: DisposeAsync when PTT not asserted does not call SetPttAsync")]
    public async Task DisposeAsync_WhenNotAsserted_DoesNotReleasePtt()
    {
        var sut = MakeSut(out var gate);

        await sut.DisposeAsync();

        await gate.DidNotReceive().SetPttAsync(Arg.Any<bool>(), Arg.Any<CancellationToken>());
    }

    [Fact(DisplayName = "CatTx-Ptt: DisposeAsync is idempotent — second call does not throw")]
    public async Task DisposeAsync_CalledTwice_SecondCallIsNoOp()
    {
        var sut = MakeSut(out _);

        await sut.DisposeAsync();

        var act = async () => await sut.DisposeAsync();
        await act.Should().NotThrowAsync();
    }

    // ── Watchdog integration ─────────────────────────────────────────────────

    [Fact(DisplayName = "CatTx-Ptt: watchdog force-releases PTT when KeyUpAsync is never called")]
    public async Task Watchdog_ForcesRelease_WhenKeyUpNeverCalled()
    {
        await using var sut = MakeSut(out var gate,
            (_, _, ct) => Task.Delay(Timeout.Infinite, ct), watchdogTimeoutMs: 50);

        sut.LoadAudio(SomeSamples);
        // Fire-and-forget: the player hangs forever, so KeyDownAsync never returns on its
        // own — the watchdog must force a release regardless.
        _ = sut.KeyDownAsync();

        // Poll for the forced release rather than a single fixed delay, to keep this
        // robust under slow CI runners.
        var deadline = DateTime.UtcNow + TimeSpan.FromSeconds(2);
        while (DateTime.UtcNow < deadline &&
               gate.ReceivedCalls().Count(c => c.GetMethodInfo().Name == nameof(ICatPttGate.SetPttAsync)) < 2)
        {
            await Task.Delay(20);
        }

        await gate.Received(1).SetPttAsync(true, Arg.Any<CancellationToken>());
        await gate.Received(1).SetPttAsync(false, Arg.Any<CancellationToken>());
    }

    // ── Call-serialisation (task 17.2) ───────────────────────────────────────

    [Fact(DisplayName = "CatTx-Ptt: two concurrent KeyDownAsync callers serialise rather than interleave")]
    public async Task KeyDownAsync_TwoConcurrentCallers_Serialise()
    {
        var order      = new List<string>();
        var callCount  = 0;
        var firstPlaybackReleaseGate = new TaskCompletionSource();

        await using var sut = MakeSut(out var gate, playerOverride: async (_, _, _) =>
        {
            var n = Interlocked.Increment(ref callCount);
            lock (order) order.Add($"audio-start-{n}");
            if (n == 1)
                await firstPlaybackReleaseGate.Task; // held open until the test releases it
        });

        sut.LoadAudio(SomeSamples);

        // Caller #1 — simulates the real, active QsoAnswererService/QsoCallerService
        // transmission — begins and stays "mid-transmission" (audio still playing) until
        // the test explicitly lets it finish below.
        var firstKeyDown = sut.KeyDownAsync();

        // Give caller #1 time to acquire the lock, assert PTT, and enter the player.
        var deadline = DateTime.UtcNow + TimeSpan.FromSeconds(2);
        while (DateTime.UtcNow < deadline && callCount < 1)
            await Task.Delay(10);
        callCount.Should().Be(1, "caller #1 must have started its playback by now");

        // Caller #2 — simulates a Settings-page Test click racing the real transmission —
        // starts concurrently while #1 is still mid-transmission.
        var secondKeyDown = Task.Run(() => sut.KeyDownAsync());

        // Give caller #2 a chance to (incorrectly) race ahead if the lock were missing.
        await Task.Delay(100);
        callCount.Should().Be(1,
            "caller #2 must remain blocked behind caller #1's still-open KeyUpAsync — it must " +
            "not be able to assert PTT again (and, worse, later de-assert it) while caller #1's " +
            "real transmission is still in flight");
        await gate.Received(1).SetPttAsync(true, Arg.Any<CancellationToken>());

        // Complete caller #1's cycle exactly as the real state machine would: let its
        // playback finish, then call its matching KeyUpAsync.
        firstPlaybackReleaseGate.SetResult();
        await firstKeyDown;
        await sut.KeyUpAsync();

        // Caller #2 must now be able to proceed and assert PTT for its own cycle.
        await secondKeyDown.WaitAsync(TimeSpan.FromSeconds(5));

        callCount.Should().Be(2);
        await gate.Received(2).SetPttAsync(true, Arg.Any<CancellationToken>());
        order.Should().Equal(["audio-start-1", "audio-start-2"],
            "caller #2's playback must not start until caller #1's KeyUpAsync has completed");
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private static CatPttController MakeSut(
        out ICatPttGate gate,
        Func<float[], string?, CancellationToken, Task>? playerOverride = null,
        int leadTimeMs = 0,
        int tailTimeMs = 0,
        int watchdogTimeoutMs = 20_000)
    {
        var mockGate = Substitute.For<ICatPttGate>();
        gate = mockGate;

        var store = Substitute.For<IConfigStore>();
        store.Current.Returns(new AppConfig() with
        {
            Ptt = new PttConfig
            {
                Method            = "CatCommand",
                LeadTimeMs        = leadTimeMs,
                TailTimeMs        = tailTimeMs,
                WatchdogTimeoutMs = watchdogTimeoutMs,
            }
        });

        var logger = NullLogger<CatPttController>.Instance;

        return playerOverride is not null
            ? new CatPttController(mockGate, store, logger, playerOverride)
            : new CatPttController(mockGate, store, logger, (_, _, _) => Task.CompletedTask);
    }
}
#endif
