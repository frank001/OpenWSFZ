using System.Reflection;
using System.Threading.Channels;
using OpenWSFZ.Ft8;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// A decode channel that records what the consuming service's loop does to it, so a test can wait for
/// the positive condition "the batch has been PROCESSED", not just "the batch has been dequeued".
/// </summary>
/// <remarks>
/// <para>
/// <c>QsoCallerService</c> and <c>QsoAnswererService</c> both run
/// <c>while (...) { batch = await ReadNextBatchAsync(); await ProcessBatchAsync(batch); }</c>: strictly
/// sequential. So after the loop has dequeued a batch, the next time it touches the decode reader is
/// necessarily from the NEXT <c>ReadNextBatchAsync</c>, which can only start once
/// <c>ProcessBatchAsync</c> for that batch has returned. <see cref="IsProcessedThroughLastDequeue"/>
/// is exactly that observation: the channel is empty AND the reader has been touched again after the
/// last successful dequeue.
/// </para>
/// <para>
/// The old condition, <c>channel.Reader.Count == 0</c>, became true the moment the service READ the
/// batch, before <c>ProcessBatchAsync</c> had acted on it. That read-versus-processed gap was the
/// cause of the D-015 flake and was invisible to Gate G10 (there is no delay literal to find).
/// </para>
/// </remarks>
internal sealed class ObservedDecodeChannel : Channel<DecodeBatch>
{
    private readonly Channel<DecodeBatch> _inner = Channel.CreateUnbounded<DecodeBatch>();
    private long _readerEvents;     // every reader call start and every successful dequeue gets a number
    private long _lastDequeueEvent; // the event number of the most recent successful dequeue

    private ObservedDecodeChannel()
    {
        Writer = _inner.Writer;
        Reader = new ObservedReader(this);
    }

    /// <summary>Creates a channel to hand to a QSO service as its decode source.</summary>
    public static ObservedDecodeChannel Create() => new();

    /// <summary>
    /// True when nothing is queued AND the service's loop has returned to reading since it last
    /// dequeued a batch, i.e. every batch it ever dequeued has been fully processed.
    /// </summary>
    public bool IsProcessedThroughLastDequeue =>
        _inner.Reader.Count == 0
        && Interlocked.Read(ref _readerEvents) > Interlocked.Read(ref _lastDequeueEvent);

    /// <summary>Casts a test's <see cref="Channel{T}"/> back to the observed type, or fails loudly.</summary>
    public static ObservedDecodeChannel From(Channel<DecodeBatch> channel)
        => channel as ObservedDecodeChannel
           ?? throw new InvalidOperationException(
               "This test's decode channel was not created with ObservedDecodeChannel.Create(), so " +
               "'the batch was processed' cannot be observed. Create it with ObservedDecodeChannel.Create().");

    private long NextEvent() => Interlocked.Increment(ref _readerEvents);

    private void RecordDequeue() => Interlocked.Exchange(ref _lastDequeueEvent, NextEvent());

    private sealed class ObservedReader : ChannelReader<DecodeBatch>
    {
        private readonly ObservedDecodeChannel _owner;
        private ChannelReader<DecodeBatch> Inner => _owner._inner.Reader;

        public ObservedReader(ObservedDecodeChannel owner) => _owner = owner;

        public override Task Completion => Inner.Completion;
        public override bool CanCount => Inner.CanCount;
        public override int Count => Inner.Count;

        public override bool TryRead(out DecodeBatch item)
        {
            _owner.NextEvent();
            var ok = Inner.TryRead(out item!);
            if (ok) _owner.RecordDequeue();
            return ok;
        }

        public override ValueTask<bool> WaitToReadAsync(CancellationToken cancellationToken = default)
        {
            _owner.NextEvent();
            return Inner.WaitToReadAsync(cancellationToken);
        }

        public override async ValueTask<DecodeBatch> ReadAsync(CancellationToken cancellationToken = default)
        {
            _owner.NextEvent();
            var item = await Inner.ReadAsync(cancellationToken).ConfigureAwait(false);
            _owner.RecordDequeue();
            return item;
        }
    }
}

/// <summary>
/// Test-only handling of a QSO service's internal wakeup channel (<c>_wakeupChannel</c>).
/// </summary>
/// <remarks>
/// <c>SelectResponderAsync</c> / <c>AnswerCqAsync</c> / <c>EngageAtAsync</c> push an EMPTY wakeup batch
/// whose <c>CycleStart</c> comes from the real <c>DateTimeOffset.UtcNow</c>. The service loop acts on it
/// by the wall-clock phase: half the time it fires TX immediately, half the time it holds. Tests that
/// control the phase with explicit fixed-stamp batches must therefore keep that stray wakeup out of the
/// loop. The old way, "drain it, then sleep 50 ms to let the loop settle", loses the race
/// whenever the loop reads the wakeup before the test's drain does.
/// <see cref="Discard"/> closes the race instead of waiting it out: the stray wakeup is swallowed on
/// the writer side, so the loop can never see it, and the test observes that it was produced.
/// </remarks>
internal static class WakeupChannelProbe
{
    /// <summary>
    /// Replaces <paramref name="service"/>'s <c>_wakeupChannel</c> with one that discards every batch
    /// written to it. Call BEFORE <c>StartAsync</c> (the loop reads the field once it is running).
    /// </summary>
    public static DiscardingWakeupChannel Discard(object service)
    {
        var field = service.GetType().GetField(
            "_wakeupChannel", BindingFlags.NonPublic | BindingFlags.Public | BindingFlags.Instance)
            ?? throw new InvalidOperationException(
                $"{service.GetType().Name} has no '_wakeupChannel' field; the wakeup probe needs updating.");
        var replacement = new DiscardingWakeupChannel();
        field.SetValue(service, replacement);
        return replacement;
    }
}

/// <summary>A wakeup channel that counts the batches written to it and delivers none of them.</summary>
internal sealed class DiscardingWakeupChannel : Channel<DecodeBatch>
{
    private readonly Channel<DecodeBatch> _inner = Channel.CreateUnbounded<DecodeBatch>();
    private int _discarded;

    public DiscardingWakeupChannel()
    {
        Writer = new CountingDiscardWriter(this);
        Reader = _inner.Reader; // never receives anything, so the loop's WaitToReadAsync simply never fires
    }

    /// <summary>How many wakeup batches the service tried to push (and were swallowed).</summary>
    public int Discarded => Volatile.Read(ref _discarded);

    private sealed class CountingDiscardWriter : ChannelWriter<DecodeBatch>
    {
        private readonly DiscardingWakeupChannel _owner;
        public CountingDiscardWriter(DiscardingWakeupChannel owner) => _owner = owner;

        public override bool TryWrite(DecodeBatch item)
        {
            Interlocked.Increment(ref _owner._discarded);
            return true;
        }

        public override ValueTask<bool> WaitToWriteAsync(CancellationToken cancellationToken = default)
            => new(true);
    }
}
