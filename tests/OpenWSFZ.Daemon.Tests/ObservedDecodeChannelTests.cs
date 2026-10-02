using System.Threading.Channels;
using FluentAssertions;
using OpenWSFZ.Ft8;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Tests for <see cref="ObservedDecodeChannel"/>, the instrument behind the QSO tests'
/// <c>WaitForBatchDrainedAsync</c>. An instrument whose reading is wrong makes every test built on it
/// wrong, so its claim ("the batch has been PROCESSED") is checked here directly, including the
/// parked-<c>ReadAsync</c> handoff where <c>Reader.Count</c> is 0 before anything was dequeued.
/// </summary>
public sealed class ObservedDecodeChannelTests
{
    private static DecodeBatch Batch() => new(DateTimeOffset.UnixEpoch, []);

    [Fact(DisplayName = "ObservedDecodeChannel: a fresh channel nobody has read from is not yet 'processed'")]
    public void Fresh_NoReaderActivity_IsNotProcessed()
        => ObservedDecodeChannel.Create().IsProcessedThroughLastDequeue.Should().BeFalse();

    [Fact(DisplayName = "ObservedDecodeChannel: false while a batch is queued, even with a reader parked in WaitToReadAsync")]
    public async Task BatchQueued_IsNotProcessed()
    {
        var ch = ObservedDecodeChannel.Create();
        var wait = ch.Reader.WaitToReadAsync().AsTask(); // parked, like the loop's Task.WhenAny branch
        ch.Writer.TryWrite(Batch());

        ch.IsProcessedThroughLastDequeue.Should().BeFalse("a batch is sitting in the queue");
        (await wait).Should().BeTrue();
        ch.IsProcessedThroughLastDequeue.Should().BeFalse("it has been announced but not dequeued");
    }

    [Fact(DisplayName = "ObservedDecodeChannel: true only after the batch is dequeued AND the reader is touched again")]
    public void ProcessedBatch_IsProcessedOnlyAfterNextReadStarts()
    {
        var ch = ObservedDecodeChannel.Create();
        ch.Writer.TryWrite(Batch());

        ch.Reader.TryRead(out _).Should().BeTrue();
        ch.IsProcessedThroughLastDequeue.Should().BeFalse("dequeued, but the service may still be processing it");

        ch.Reader.TryRead(out _).Should().BeFalse(); // the loop's next ReadNextBatchAsync
        ch.IsProcessedThroughLastDequeue.Should().BeTrue();
    }

    [Fact(DisplayName = "ObservedDecodeChannel: a batch handed straight to a parked ReadAsync is not 'processed' until dequeued and re-read")]
    public async Task ParkedReadAsync_Handoff_IsNotProcessedUntilDequeuedAndNextReadStarted()
    {
        var ch = ObservedDecodeChannel.Create();
        var parked = ch.Reader.ReadAsync().AsTask(); // the non-wakeup branch of ReadNextBatchAsync

        ch.Writer.TryWrite(Batch());

        // The hole: an unbounded channel hands the item straight to the parked reader, so the underlying
        // Count is 0 although nothing has been processed. The observation must not be fooled by it.
        ch.Reader.Count.Should().Be(0, "premise: Count cannot see an item handed to a parked ReadAsync");
        // Not asserted on parked's completion state: the handoff may or may not have run its continuation.
        // Either way the batch has been written but the consumer has not yet counted the dequeue, or has
        // dequeued without a following read, so the reading must be false at every instant here.
        ch.IsProcessedThroughLastDequeue.Should().BeFalse("written but not yet dequeued and re-read");

        await parked;
        ch.IsProcessedThroughLastDequeue.Should().BeFalse("dequeued, but the next read has not started");

        _ = ch.Reader.ReadAsync().AsTask(); // the loop is back at its next read
        ch.IsProcessedThroughLastDequeue.Should().BeTrue();
    }

    [Fact(DisplayName = "ObservedDecodeChannel: the parked-ReadAsync handoff never reads as 'processed' in the window before the consumer counts the dequeue")]
    public async Task ParkedReadAsync_Handoff_NeverReadsProcessedBeforeTheDequeueIsCounted()
    {
        // The channel completes a parked ReadAsync by queueing its continuation to the thread pool, so
        // right after TryWrite there is a window in which the item has left the channel (Count == 0) but
        // the consumer has not yet run. A condition built on Count (the old WaitForBatchDrainedAsync, or
        // Count plus a reader-activity check) reads TRUE in that window. Sample it immediately after the
        // write, over many fresh channels, so the window is hit; the correct reading is false every time.
        var readTrueInWindow = 0;
        for (var i = 0; i < 2000; i++)
        {
            var ch = ObservedDecodeChannel.Create();
            var parked = ch.Reader.ReadAsync().AsTask();
            ch.Writer.TryWrite(Batch());
            if (ch.IsProcessedThroughLastDequeue) readTrueInWindow++;
            await parked;
        }
        readTrueInWindow.Should().Be(0, "a batch handed to a parked reader is not processed until it is dequeued and the next read starts");
    }

    [Fact(DisplayName = "ObservedDecodeChannel: several queued batches are processed only when all are dequeued")]
    public void MultipleBatches_ProcessedOnlyWhenAllDequeued()
    {
        var ch = ObservedDecodeChannel.Create();
        for (var i = 0; i < 3; i++) ch.Writer.TryWrite(Batch());

        for (var i = 0; i < 3; i++)
        {
            ch.IsProcessedThroughLastDequeue.Should().BeFalse($"{3 - i} still queued or in flight");
            ch.Reader.TryRead(out _).Should().BeTrue();
        }
        ch.IsProcessedThroughLastDequeue.Should().BeFalse("the last one is dequeued but its processing is not known to be over");
        ch.Reader.TryRead(out _).Should().BeFalse();
        ch.IsProcessedThroughLastDequeue.Should().BeTrue();
    }

    [Fact(DisplayName = "ObservedDecodeChannel: From() rejects a plain channel loudly")]
    public void From_PlainChannel_Throws()
    {
        var act = () => ObservedDecodeChannel.From(Channel.CreateUnbounded<DecodeBatch>());
        act.Should().Throw<InvalidOperationException>().WithMessage("*ObservedDecodeChannel.Create()*");
    }
}
