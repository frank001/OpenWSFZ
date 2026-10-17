using FluentAssertions;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Audio;
using OpenWSFZ.TestSupport;
using System.Text.RegularExpressions;
using Xunit;

namespace OpenWSFZ.Audio.Tests;

/// <summary>
/// capture-loss-instrument 1.6: <see cref="CaptureManager"/> counts chunks its DropOldest
/// channel discards, and forwards the source's overrun counters.
/// </summary>
public sealed class CaptureLossCounterTests
{
    private const int ChannelCapacity = 16;

    /// <summary>Yields <c>count</c> chunks as fast as the writer takes them.</summary>
    private sealed class BurstSource : IAudioSource, ICaptureLossCounters
    {
        private readonly int _count;
        public BurstSource(int count) => _count = count;
        public int  SampleRate   => 12_000;
        public int  ChannelCount => 1;
        public long CaptureOverrunCount      => 3;

        public async IAsyncEnumerable<float[]> CaptureAsync(
            string deviceId,
            [System.Runtime.CompilerServices.EnumeratorCancellation] CancellationToken ct)
        {
            for (int i = 0; i < _count; i++)
            {
                await Task.Yield();
                yield return new float[2048];
            }
        }

        public ValueTask DisposeAsync() => ValueTask.CompletedTask;
    }

    /// <summary>Yields one chunk, then waits for the consumer to ask for the next (lock-step).</summary>
    private sealed class LockStepSource : IAudioSource
    {
        private readonly int           _count;
        private readonly SemaphoreSlim _go = new(1);
        public LockStepSource(int count) => _count = count;
        public int SampleRate   => 12_000;
        public int ChannelCount => 1;
        public void Next() => _go.Release();

        public async IAsyncEnumerable<float[]> CaptureAsync(
            string deviceId,
            [System.Runtime.CompilerServices.EnumeratorCancellation] CancellationToken ct)
        {
            for (int i = 0; i < _count; i++)
            {
                await _go.WaitAsync(ct);
                yield return new float[2048];
            }
        }

        public ValueTask DisposeAsync() => ValueTask.CompletedTask;
    }

    [Fact(DisplayName = "capture-loss 1.6: a source that outruns a non-reading consumer increments the drop counter by exactly the chunks dropped")]
    public async Task NonReadingConsumer_DropCounter_EqualsChunksDropped()
    {
        const int Total = ChannelCapacity + 37;
        await using var cm = new CaptureManager(new BurstSource(Total));

        await cm.StartAsync("dev");
        await Poll.UntilAsync(() => !cm.IsCapturing, timeout: TimeSpan.FromSeconds(10));

        cm.CaptureChannelDroppedChunks.Should().Be(37, "capacity 16 holds the newest 16; the older 37 were dropped");
        cm.Samples.Count.Should().Be(ChannelCapacity);
    }

    [Fact(DisplayName = "capture-loss 1.6: the first and every 100th drop log a Warning with a UTC millisecond time")]
    public async Task Drops_LogWarning_OnFirstAndEvery100th_WithUtcMillisecondTime()
    {
        const int Dropped = 250;
        var log = new RecordingLogger<CaptureManager>();
        await using var cm = new CaptureManager(new BurstSource(ChannelCapacity + Dropped), log);

        await cm.StartAsync("dev");
        await Poll.UntilAsync(() => !cm.IsCapturing, timeout: TimeSpan.FromSeconds(10));

        cm.CaptureChannelDroppedChunks.Should().Be(Dropped);
        var drops = log.Entries
            .Where(e => e.Level == LogLevel.Warning && e.Message.Contains("dropped", StringComparison.OrdinalIgnoreCase)
                     && e.Message.Contains("channel", StringComparison.OrdinalIgnoreCase))
            .ToList();
        drops.Should().HaveCount(3, "drops 1, 100 and 200");
        drops.Should().OnlyContain(d => Regex.IsMatch(d.Message, @"\d{2}:\d{2}:\d{2}\.\d{3}"));
    }

    [Fact(DisplayName = "capture-loss 1.6: with a draining consumer the drop counter stays 0")]
    public async Task DrainingConsumer_DropCounter_StaysZero()
    {
        var source = new LockStepSource(count: ChannelCapacity * 3);
        await using var cm = new CaptureManager(source);

        await cm.StartAsync("dev");
        for (int i = 0; i < ChannelCapacity * 3; i++)
        {
            await cm.Samples.ReadAsync().AsTask().WaitAsync(TimeSpan.FromSeconds(10));
            source.Next();
        }

        cm.CaptureChannelDroppedChunks.Should().Be(0);
    }

    [Fact(DisplayName = "capture-loss: CaptureManager forwards the source's overrun counters and defaults them to 0")]
    public async Task OverrunCounters_AreForwardedFromTheSource_AndDefaultToZero()
    {
        await using var withCounters = new CaptureManager(new BurstSource(1));
        withCounters.CaptureOverrunCount.Should().Be(3);
        withCounters.GetLossSnapshot().Should().Be(new CaptureLossSnapshot(3, 0));

        await using var without = new CaptureManager(new InfiniteAudioSource());
        without.CaptureOverrunCount.Should().Be(0);
        without.GetLossSnapshot().Should().Be(default(CaptureLossSnapshot));
    }
}
