namespace OpenWSFZ.Daemon;

/// <summary>
/// late-batches-in-qso: the outcome of one supplementary (batch 2, 3 or 4) decision in a QSO service. Logged with exactly
/// one token per decision (<see cref="LateBatch.Token"/>); QA counts these lines over an endurance run.
/// </summary>
internal enum LateOutcome
{
    /// <summary>A message-driven transition was made and its reply transmitted at once.</summary>
    AppliedImmediate,
    /// <summary>A message-driven transition was made (Wait states) or a late CQ was chosen (Idle); the reply is held.</summary>
    AppliedDeferred,
    /// <summary>A held reply was dropped because a newer message-driven event won (or the operator did).</summary>
    Superseded,
    /// <summary>A batch of cycle N read after a batch 1 of a later cycle: ignored.</summary>
    IgnoredStale,
    /// <summary>A batch of cycle N after batch 1 (or an earlier late batch) of N already caused a transition: ignored.</summary>
    IgnoredAnswered,
    /// <summary>Nothing in the batch drives a transition: nothing changes, nothing is counted.</summary>
    NoMatch,
}

/// <summary>What a held reply, sent later by the first batch 1 of the right parity, will do.</summary>
internal enum DeferredKind
{
    /// <summary>Wait state, report reply: state is already WaitRr73; send the R-report held in <c>_lastTxMessage</c>.</summary>
    Report,
    /// <summary>Wait state, closing message (answerer 73 / caller RR73): send it and complete the QSO.</summary>
    Closing,
    /// <summary>Idle only (answerer): answer a late CQ. NO state has changed yet; the transition happens at send time.</summary>
    Answer,
}

/// <summary>
/// A reply held back because a late batch was processed too late to start it within the latest-whole-signal guard.
/// </summary>
/// <param name="Kind">What to do when it is sent.</param>
/// <param name="CycleStart">Start of the cycle whose decodes caused it (N). It is sent after a batch 1 of a LATER cycle.</param>
/// <param name="BatchNumber">The supplementary batch number (2, 3 or 4) that created it; used only for the log line.</param>
/// <param name="Partner">The station to answer (<see cref="DeferredKind.Answer"/> only).</param>
/// <param name="FreqHz">Its audio frequency (<see cref="DeferredKind.Answer"/> only).</param>
/// <param name="Grid">Its grid, if the CQ carried one (<see cref="DeferredKind.Answer"/> only).</param>
internal sealed record DeferredTx(
    DeferredKind   Kind,
    DateTimeOffset CycleStart,
    int            BatchNumber,
    string?        Partner = null,
    double         FreqHz  = 0,
    string?        Grid    = null);

/// <summary>Timing rules and log tokens shared by the answerer and the caller.</summary>
internal static class LateBatch
{
    /// <summary>Cycles whose batches can queue while a QSO service is blocked in one 12.64 s transmission (the Architect's judgement, HK-038).</summary>
    public const int QsoCyclesQueued = 2;

    /// <summary>Spare slots on top of the queued cycles (the Architect's judgement, HK-038).</summary>
    public const int QsoChannelSpare = 2;

    /// <summary>Batches a cycle can deliver to a QSO service with <c>decoder.coherentFallbackEnabled</c> OFF: batch 1, the residual pass, the third pass.</summary>
    public const int BatchesPerCycleFallbackOff = 3;

    /// <summary>COH-FALLBACK step 4 (R14): batches a cycle can deliver with the flag ON: the three above and the fallback's own batch 4 (Deep).</summary>
    public const int BatchesPerCycleFallbackOn = 4;

    /// <summary>The channel capacity for a given number of batches per cycle: batches x <see cref="QsoCyclesQueued"/> cycles + <see cref="QsoChannelSpare"/> spare.</summary>
    public static int QsoCapacityFor(int batchesPerCycle) => batchesPerCycle * QsoCyclesQueued + QsoChannelSpare;

    /// <summary>
    /// Capacity of the answerer and caller decode channels with the fallback flag OFF: 3 batches x 2 cycles + 2 spare = 8 (the
    /// Architect's judgement, HK-038). A QSO service is blocked for a whole 12.64 s transmission, so up to two cycles of three batches can
    /// queue; at the old capacity of 2 a batch 1 was dropped by the batches that followed it. Unchanged by the fallback (R13).
    /// </summary>
    public const int QsoChannelCapacity = BatchesPerCycleFallbackOff * QsoCyclesQueued + QsoChannelSpare;

    /// <summary>COH-FALLBACK step 4 (R14): 4 batches x 2 cycles + 2 spare = 10, in force only while the flag is ON.</summary>
    public const int QsoChannelCapacityFallbackOn = BatchesPerCycleFallbackOn * QsoCyclesQueued + QsoChannelSpare;

    /// <summary>The bounded DropOldest channel Program.cs gives each QSO service (one writer: the pump; one reader).</summary>
    public static System.Threading.Channels.Channel<DecodeBatch> CreateQsoChannel()
        => System.Threading.Channels.Channel.CreateBounded<DecodeBatch>(
            new System.Threading.Channels.BoundedChannelOptions(QsoChannelCapacity)
            {
                FullMode     = System.Threading.Channels.BoundedChannelFullMode.DropOldest,
                SingleWriter = true,
                SingleReader = true,
            });

    /// <summary>
    /// COH-FALLBACK step 4 (R14): the queue Program.cs gives each QSO service. The channel is created once, at start-up, but
    /// <c>decoder.coherentFallbackEnabled</c> can change at run time, so the channel is built for the larger capacity
    /// (<see cref="QsoChannelCapacityFallbackOn"/>) and the WRITER enforces the effective one: before each write it drops the oldest
    /// batches until fewer than the effective capacity are queued. With the flag OFF that is exactly a bounded DropOldest channel of
    /// <see cref="QsoChannelCapacity"/>: a write into a queue holding 8 drops the oldest and leaves 8, as before. Because the writer
    /// reads (to drop), the inner channel is not SingleReader; the pump remains the only writer and the service the only consumer.
    /// </summary>
    public static QsoBatchQueue CreateQsoQueue(Func<bool> fallbackOn) => new(fallbackOn);

    /// <summary>One FT8 cycle, in milliseconds (integers, so the 2.36 s guard is exact).</summary>
    public const int CycleMilliseconds = 15_000;

    /// <summary>79 symbols x 160 ms: the airtime of a whole FT8 signal, in milliseconds.</summary>
    public const int SignalMilliseconds = 12_640;

    /// <summary>One FT8 cycle.</summary>
    public const double CycleSeconds = CycleMilliseconds / 1000.0;

    /// <summary>
    /// 15 s - 12.64 s = 2.36 s: the latest a whole FT8 signal can start inside its slot. A start later than this is
    /// truncated at the window boundary (D-CALLER-021), so a late reply is held for the next own-parity slot instead.
    /// </summary>
    public static readonly TimeSpan LatestWholeStart = TimeSpan.FromMilliseconds(CycleMilliseconds - SignalMilliseconds);

    /// <summary>
    /// True when a batch of cycle <paramref name="cycleStart"/>, processed at <paramref name="now"/>, can still start its
    /// reply in the slot that follows the cycle (S = cycle start + 15 s) without truncation: now &lt;= S + 2.36 s.
    /// <paramref name="now"/> is the time the SERVICE processes the batch, not the time the decode finished.
    /// </summary>
    public static bool CanStartWhole(DateTimeOffset now, DateTimeOffset cycleStart)
        => now - (cycleStart + TimeSpan.FromMilliseconds(CycleMilliseconds)) <= LatestWholeStart;

    /// <summary>True when the slot after <paramref name="cycleStart"/> is an A-phase (:00/:30) slot.</summary>
    public static bool ReplySlotIsAPhase(DateTimeOffset cycleStart)
    {
        // Same definition as both services' IsAPhase (Second % 30 == 0) applied to the slot start, as the
        // pending-target phase check does: IsAPhase(batch.CycleStart + 15 s).
        return (cycleStart + TimeSpan.FromMilliseconds(CycleMilliseconds)).Second % 30 == 0;
    }

    /// <summary>The exact log token for an outcome (AC10). Do not change: QA greps for these.</summary>
    public static string Token(LateOutcome outcome) => outcome switch
    {
        LateOutcome.AppliedImmediate => "applied-immediate",
        LateOutcome.AppliedDeferred  => "applied-deferred",
        LateOutcome.Superseded       => "superseded",
        LateOutcome.IgnoredStale     => "ignored-stale",
        LateOutcome.IgnoredAnswered  => "ignored-answered",
        LateOutcome.NoMatch          => "no-match",
        _                            => throw new ArgumentOutOfRangeException(nameof(outcome)),
    };
}

/// <summary>See <see cref="LateBatch.CreateQsoQueue"/>.</summary>
internal sealed class QsoBatchQueue
{
    private readonly System.Threading.Channels.Channel<DecodeBatch> _inner;
    private readonly Func<bool> _fallbackOn;

    internal QsoBatchQueue(Func<bool> fallbackOn)
    {
        ArgumentNullException.ThrowIfNull(fallbackOn);
        _fallbackOn = fallbackOn;
        _inner = System.Threading.Channels.Channel.CreateBounded<DecodeBatch>(
            new System.Threading.Channels.BoundedChannelOptions(LateBatch.QsoChannelCapacityFallbackOn)
            {
                FullMode     = System.Threading.Channels.BoundedChannelFullMode.DropOldest,
                SingleWriter = true,
                SingleReader = false,   // the writer trims the queue to the effective capacity
            });
        Writer = new TrimmingWriter(this);
    }

    /// <summary>The service's end of the queue.</summary>
    public System.Threading.Channels.ChannelReader<DecodeBatch> Reader => _inner.Reader;

    /// <summary>The pump's end of the queue: DropOldest at the effective capacity.</summary>
    public System.Threading.Channels.ChannelWriter<DecodeBatch> Writer { get; }

    /// <summary>The capacity in force now: 8 with the flag OFF, 10 with it ON.</summary>
    public int EffectiveCapacity => _fallbackOn() ? LateBatch.QsoChannelCapacityFallbackOn : LateBatch.QsoChannelCapacity;

    private sealed class TrimmingWriter(QsoBatchQueue queue) : System.Threading.Channels.ChannelWriter<DecodeBatch>
    {
        public override bool TryWrite(DecodeBatch item)
        {
            int capacity = queue.EffectiveCapacity;
            var reader = queue._inner.Reader;
            while (reader.Count >= capacity && reader.TryRead(out _)) { }
            return queue._inner.Writer.TryWrite(item);
        }

        public override System.Threading.Tasks.ValueTask<bool> WaitToWriteAsync(CancellationToken cancellationToken = default)
            => queue._inner.Writer.WaitToWriteAsync(cancellationToken);

        public override bool TryComplete(Exception? error = null) => queue._inner.Writer.TryComplete(error);
    }
}
