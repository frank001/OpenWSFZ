namespace OpenWSFZ.Daemon;

/// <summary>
/// late-batches-in-qso: the outcome of one supplementary (batch 2 or 3) decision in a QSO service. Logged with exactly
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
/// <param name="BatchNumber">The supplementary batch number (2 or 3) that created it; used only for the log line.</param>
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
    /// <summary>
    /// Capacity of the answerer and caller decode channels: 3 batches x 2 cycles + 2 spare (the Architect's judgement,
    /// HK-038). A QSO service is blocked for a whole 12.64 s transmission, so up to two cycles of three batches can queue;
    /// at the old capacity of 2 a batch 1 was dropped by the batches that followed it.
    /// </summary>
    public const int QsoChannelCapacity = 8;

    /// <summary>The bounded DropOldest channel Program.cs gives each QSO service (one writer: the pump; one reader).</summary>
    public static System.Threading.Channels.Channel<DecodeBatch> CreateQsoChannel()
        => System.Threading.Channels.Channel.CreateBounded<DecodeBatch>(
            new System.Threading.Channels.BoundedChannelOptions(QsoChannelCapacity)
            {
                FullMode     = System.Threading.Channels.BoundedChannelFullMode.DropOldest,
                SingleWriter = true,
                SingleReader = true,
            });

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
