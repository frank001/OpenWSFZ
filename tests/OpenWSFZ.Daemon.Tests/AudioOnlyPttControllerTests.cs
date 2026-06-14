using FluentAssertions;
using Microsoft.Extensions.Logging.Abstractions;
using NSubstitute;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Unit tests for <see cref="AudioOnlyPttController"/> (task 4.6).
///
/// All tests use the internal test constructor that injects a delegate in place of
/// real WASAPI playback, so no audio hardware is required.  The WASAPI-gated
/// <c>#if WASAPI_SUPPORTED</c> block below is excluded on non-Windows builds.
/// </summary>
#if WASAPI_SUPPORTED
[System.Runtime.Versioning.SupportedOSPlatform("windows")]
public sealed class AudioOnlyPttControllerTests
{
    private static readonly float[] SomeSamples = new float[606_720]; // 79 × 7680 at 48 kHz

    // ── LoadAudio + KeyDownAsync ──────────────────────────────────────────────

    [Fact(DisplayName = "KeyDownAsync without LoadAudio throws InvalidOperationException")]
    public async Task KeyDownAsync_WithoutLoadAudio_ThrowsInvalidOperationException()
    {
        await using var sut = MakeSut(out _);

        var act = async () => await sut.KeyDownAsync();

        await act.Should().ThrowExactlyAsync<InvalidOperationException>()
            .WithMessage("*LoadAudio*");
    }

    [Fact(DisplayName = "KeyDownAsync after LoadAudio invokes the player delegate")]
    public async Task KeyDownAsync_AfterLoadAudio_InvokesPlayerDelegate()
    {
        int    callCount      = 0;
        float[]? capturedSamples = null;

        await using var sut = MakeSut(out _, (samples, _, _) =>
        {
            callCount++;
            capturedSamples = samples;
            return Task.CompletedTask;
        });

        sut.LoadAudio(SomeSamples);
        await sut.KeyDownAsync();

        callCount.Should().Be(1, "KeyDownAsync must invoke the player exactly once");
        capturedSamples.Should().BeSameAs(SomeSamples,
            "the exact buffer supplied to LoadAudio must be passed to the player");
    }

    [Fact(DisplayName = "KeyDownAsync propagates player delegate exception")]
    public async Task KeyDownAsync_PlayerThrows_PropagatesException()
    {
        await using var sut = MakeSut(out _, (_, _, _) =>
            Task.FromException(new InvalidOperationException("device busy")));

        sut.LoadAudio(SomeSamples);

        var act = async () => await sut.KeyDownAsync();
        await act.Should().ThrowExactlyAsync<InvalidOperationException>()
            .WithMessage("device busy");
    }

    // ── KeyUpAsync ────────────────────────────────────────────────────────────

    [Fact(DisplayName = "KeyUpAsync when not playing completes without throwing")]
    public async Task KeyUpAsync_WhenNotPlaying_CompletesGracefully()
    {
        await using var sut = MakeSut(out _);

        // Should not throw even though no transmission is in progress.
        var act = async () => await sut.KeyUpAsync();
        await act.Should().NotThrowAsync();
    }

    // ── DisposeAsync ──────────────────────────────────────────────────────────

    [Fact(DisplayName = "DisposeAsync when not playing completes without throwing")]
    public async Task DisposeAsync_WhenNotPlaying_CompletesGracefully()
    {
        var sut = MakeSut(out _);

        var act = async () => await sut.DisposeAsync();
        await act.Should().NotThrowAsync();
    }

    [Fact(DisplayName = "DisposeAsync is idempotent — second call does not throw")]
    public async Task DisposeAsync_CalledTwice_SecondCallIsNoOp()
    {
        var sut = MakeSut(out _);

        await sut.DisposeAsync();

        // Second DisposeAsync should not throw (idempotent).
        var act = async () => await sut.DisposeAsync();
        await act.Should().NotThrowAsync();
    }

    // ── Cancellation ─────────────────────────────────────────────────────────

    [Fact(DisplayName = "KeyDownAsync honours cancellation token")]
    public async Task KeyDownAsync_CancellationRequested_ThrowsOperationCanceledException()
    {
        using var cts = new CancellationTokenSource();

        await using var sut = MakeSut(out _, async (_, _, innerCt) =>
        {
            // Simulate a long-running playback that respects cancellation.
            await Task.Delay(Timeout.Infinite, innerCt);
        });

        sut.LoadAudio(SomeSamples);

        // Cancel after a short delay.
        cts.CancelAfter(TimeSpan.FromMilliseconds(50));

        var act = async () => await sut.KeyDownAsync(cts.Token);
        await act.Should().ThrowAsync<OperationCanceledException>();
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private static AudioOnlyPttController MakeSut(
        out IConfigStore configStore,
        Func<float[], string?, CancellationToken, Task>? playerOverride = null)
    {
        var store = Substitute.For<IConfigStore>();
        store.Current.Returns(new AppConfig());
        configStore = store;

        var logger = NullLogger<AudioOnlyPttController>.Instance;

        return playerOverride is not null
            ? new AudioOnlyPttController(configStore, logger, playerOverride)
            : new AudioOnlyPttController(configStore, logger,
                  (_, _, _) => Task.CompletedTask); // default no-op for tests that don't care
    }
}
#endif
