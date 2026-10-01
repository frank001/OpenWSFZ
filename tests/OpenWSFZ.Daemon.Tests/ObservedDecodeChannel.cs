using System.Reflection;
using System.Threading.Channels;
using Microsoft.Extensions.Hosting;
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
/// is exactly that observation, plus the requirement that everything written has been dequeued.
/// </para>
/// <para>
/// The old condition, <c>channel.Reader.Count == 0</c>, was wrong in two ways: it turned true the moment
/// the service READ a batch (before <c>ProcessBatchAsync</c> had acted on it: the D-015 cause), and it
/// was already true for a batch written while the loop was parked in <c>ReadAsync</c> (an unbounded
/// channel hands the item straight to the waiting reader, so <c>Count</c> stays 0). Writes are therefore
/// counted on the writer side. Gate G10 cannot see either defect (there is no delay literal).
/// </para>
/// </remarks>
internal sealed class ObservedDecodeChannel : Channel<DecodeBatch>
{
    private readonly Channel<DecodeBatch> _inner = Channel.CreateUnbounded<DecodeBatch>();
    private readonly object _gate = new();
    private long _written;          // items accepted by the writer
    private long _dequeued;         // items the reader has handed to the consumer
    private long _readerEvents;     // every reader call start and every successful dequeue gets a number
    private long _lastDequeueEvent; // the event number of the most recent successful dequeue

    private ObservedDecodeChannel()
    {
        Writer = new ObservedWriter(this);
        Reader = new ObservedReader(this);
    }

    /// <summary>Creates a channel to hand to a QSO service as its decode source.</summary>
    public static ObservedDecodeChannel Create() => new();

    /// <summary>
    /// True when every item ever written has been dequeued AND the service's loop has returned to
    /// reading since it last dequeued, i.e. every batch it dequeued has been fully processed.
    /// </summary>
    /// <remarks>
    /// <c>written == dequeued</c> has no parked-reader hole, and the dequeue is only counted AFTER the
    /// item reaches the consumer, so the gap between "taken from the queue" and "counted" reads as
    /// not-yet. All counters are read together under one lock, so the pair is atomic.
    /// </remarks>
    public bool IsProcessedThroughLastDequeue
    {
        get { lock (_gate) return _dequeued == _written && _readerEvents > _lastDequeueEvent; }
    }

    /// <summary>Casts a test's <see cref="Channel{T}"/> back to the observed type, or fails loudly.</summary>
    public static ObservedDecodeChannel From(Channel<DecodeBatch> channel)
        => channel as ObservedDecodeChannel
           ?? throw new InvalidOperationException(
               "This test's decode channel was not created with ObservedDecodeChannel.Create(), so " +
               "'the batch was processed' cannot be observed. Create it with ObservedDecodeChannel.Create().");

    private void NoteReaderCall() { lock (_gate) _readerEvents++; }

    private void NoteDequeue()
    {
        lock (_gate)
        {
            _dequeued++;
            _lastDequeueEvent = ++_readerEvents;
        }
    }

    private sealed class ObservedWriter : ChannelWriter<DecodeBatch>
    {
        private readonly ObservedDecodeChannel _owner;
        public ObservedWriter(ObservedDecodeChannel owner) => _owner = owner;

        public override bool TryWrite(DecodeBatch item)
        {
            // Count BEFORE the write so a consumer can never dequeue an item that was not yet counted.
            lock (_owner._gate) _owner._written++;
            if (_owner._inner.Writer.TryWrite(item)) return true;
            lock (_owner._gate) _owner._written--; // not accepted (completed channel)
            return false;
        }

        public override ValueTask<bool> WaitToWriteAsync(CancellationToken cancellationToken = default)
            => _owner._inner.Writer.WaitToWriteAsync(cancellationToken);

        public override bool TryComplete(Exception? error = null) => _owner._inner.Writer.TryComplete(error);
    }

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
            _owner.NoteReaderCall();
            var ok = Inner.TryRead(out item!);
            if (ok) _owner.NoteDequeue();
            return ok;
        }

        public override ValueTask<bool> WaitToReadAsync(CancellationToken cancellationToken = default)
        {
            _owner.NoteReaderCall();
            return Inner.WaitToReadAsync(cancellationToken);
        }

        public override async ValueTask<DecodeBatch> ReadAsync(CancellationToken cancellationToken = default)
        {
            _owner.NoteReaderCall();
            var item = await Inner.ReadAsync(cancellationToken).ConfigureAwait(false);
            _owner.NoteDequeue();
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
    /// written to it. Must be called BEFORE <c>StartAsync</c> (the running loop may already hold the
    /// original channel); this is enforced and throws otherwise.
    /// </summary>
    public static DiscardingWakeupChannel Discard(object service)
    {
        if (service is BackgroundService { ExecuteTask: not null })
            throw new InvalidOperationException(
                "WakeupChannelProbe.Discard must be called before StartAsync: the running loop may already hold the original channel.");
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
