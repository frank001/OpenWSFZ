namespace OpenWSFZ.Ft8;

/// <summary>
/// XC-BUILD R13: the numbers-only diagnostic sink. <see cref="Ft8Decoder"/> calls it once per tested template, live and shadow, after the stage's parallel run (on the decoding thread, in test order, so an
/// implementation needs no locking). <b>Numbers only</b>: no message text, no callsign, no payload, no hash (HK-037, NFR-021). <c>null</c> by default; the shipped build has no subscriber. It exists so the
/// TRAIN arm can read the per-test S_E* distribution of the shadow null (a counts-only log line cannot give a quantile) and set T_E.
/// </summary>
internal interface ICrossCyclePriorProbe
{
    /// <summary>One template was tested. An exception thrown here is logged and swallowed: a diagnostic can never lose a cycle's decodes.</summary>
    void OnTemplateTested(in CrossCycleTestRecord record);
}

/// <summary>Which prior population a tested template came from.</summary>
internal enum CrossCycleKind
{
    /// <summary>A same-parity prior (published 30, 60 or 90 s earlier): a detection is published as batch 6.</summary>
    Live = 0,

    /// <summary>An opposite-parity prior (15, 45 or 75 s earlier): the null. Counted and logged, never published, never stored.</summary>
    Shadow = 1,
}

/// <summary>
/// What the diagnostic sink is told about one tested template: numbers only.
/// </summary>
/// <param name="Kind">Live or shadow.</param>
/// <param name="SStar">S_E*, the maximum of the statistic over the search window.</param>
/// <param name="AgeCycles">The prior's age in 15 s cycles: 2, 4 or 6 for live; 1, 3 or 5 for shadow.</param>
/// <param name="OffsetHz">The argmax's frequency minus the prior's frequency, Hz.</param>
/// <param name="OffsetS">The argmax's dt minus the prior's dt, seconds.</param>
/// <param name="CycleStart">The cycle's start stamp (UTC).</param>
/// <param name="SP">R15: S_P, the statistic over frame symbols 43 to 71 at the S_E* argmax.</param>
/// <param name="PriorFreqHz">The prior's own frequency, Hz (as published in its cycle). With <see cref="PriorDt"/> and <see cref="PriorBatch"/> this lets a reader tell which test carried which text (QA's K1) without the text.</param>
/// <param name="PriorDt">The prior's own dt, seconds, in OUR dt convention (the one batches 1 to 5 publish).</param>
/// <param name="PriorBatch">The batch (1 to 5) the prior was published in.</param>
/// <param name="Vetoed">R14's verdict: a decode of batches 1 to 5 of this cycle with a different text is co-located with the argmax. True whether or not the veto is applied (a run with the veto off counts it, does not apply it).</param>
internal readonly record struct CrossCycleTestRecord(CrossCycleKind Kind, double SStar, int AgeCycles, double OffsetHz, double OffsetS, DateTime CycleStart,
                                                     double SP = 0.0, double PriorFreqHz = 0.0, double PriorDt = 0.0, int PriorBatch = 0, bool Vetoed = false);

/// <summary>
/// XC-BUILD R2/R3: the per-decoder-instance store of the messages PUBLISHED in batches 1 to 5 of each cycle, keyed by the cycle's 15 s slot, keeping the last 6 cycles (90 s, both parities).
///
/// <list type="bullet">
///   <item><b>Batch 6 never enters it</b> (no chaining): <see cref="Ft8Decoder"/> calls <see cref="Record"/> only from the mapping of batches 1 to 5.</item>
///   <item><b>Cleared on a band change</b> (<see cref="BeginCycle"/>: the band differs from the previous staged cycle's; null on both counts as no change).</item>
///   <item><b>Gap rule:</b> a prior counts only if its slot is exactly the current slot minus 2, 4 or 6 (live: 30, 60, 90 s) or 1, 3 or 5 (shadow). A missing cycle therefore leaves a hole, never a shifted age.</item>
///   <item>The early decode never reads or writes it, and with the setting OFF <see cref="Ft8Decoder"/> never calls it at all (R11).</item>
/// </list>
///
/// <para>
/// The slot is the cycle's start rounded to the nearest 15 s, so a cycle start with millisecond framing jitter (the live <c>CycleFramer</c>) lands on the same slot as the exact stamp Replay81 passes.
/// Thread-safety: the decoder is called once per cycle under the daemon's decode gate, so there is no concurrent use; every public member nevertheless takes one lock, so an overlapping call could not
/// corrupt a list (cheap: a handful of calls per cycle).
/// </para>
/// </summary>
internal sealed class CrossCyclePriorStore
{
    /// <summary>The cycle length, seconds.</summary>
    internal const int CycleSeconds = 15;

    /// <summary>Cycles kept besides the current one: 6, which is 90 s (the oldest live prior).</summary>
    internal const int RetainedCycles = 6;

    /// <summary>The ages, in cycles, of the live priors (30, 60 and 90 s), nearest first.</summary>
    internal static readonly int[] LiveAges = [2, 4, 6];

    /// <summary>The ages, in cycles, of the shadow priors (15, 45 and 75 s), nearest first.</summary>
    internal static readonly int[] ShadowAges = [1, 3, 5];

    /// <summary>One published message: its text, the position it was published at (the native result's frequency and dt) and its batch (1 to 5).</summary>
    internal sealed record Prior(string Text, double FreqHz, double Dt, int Batch);

    /// <summary>A prior chosen for cycle t, with its age in cycles.</summary>
    internal sealed record Candidate(Prior Prior, int AgeCycles);

    private readonly object _lock = new();
    private readonly Dictionary<long, List<Prior>> _byCycle = [];
    private long _currentSlot = long.MinValue;
    private bool _hasBand;
    private string? _band;

    /// <summary>The slot of a cycle start: the start rounded to the nearest 15 s.</summary>
    internal static long SlotOf(DateTime cycleStart)
    {
        const long period = CycleSeconds * TimeSpan.TicksPerSecond;
        return (cycleStart.Ticks + period / 2) / period;
    }

    /// <summary>
    /// Opens cycle <paramref name="cycleStart"/>: clears the store when the band differs from the previous cycle's, drops cycles older than the last six, and starts an empty list for this one (a cycle
    /// that is decoded again replaces its own entry).
    /// </summary>
    internal void BeginCycle(DateTime cycleStart, string? band)
    {
        long slot = SlotOf(cycleStart);
        lock (_lock)
        {
            if (_hasBand && !string.Equals(_band, band, StringComparison.Ordinal)) _byCycle.Clear();
            _hasBand = true;
            _band = band;
            _currentSlot = slot;
            foreach (long key in _byCycle.Keys.ToArray())
                if (key < slot - RetainedCycles || key > slot) _byCycle.Remove(key);
            _byCycle[slot] = [];
        }
    }

    /// <summary>Adds a message published in batch 1 to 5 of the current cycle. Never called for batch 6.</summary>
    internal void Record(Prior prior)
    {
        lock (_lock)
        {
            if (!_byCycle.TryGetValue(_currentSlot, out var list)) return;
            list.Add(prior);
        }
    }

    /// <summary>
    /// R14: a snapshot of the messages published so far in batches 1 to 5 of the CURRENT cycle (text, position in our own dt convention, batch), in publish order. Called once per staged cycle, only with the
    /// stage ON, after batches 1 to 5 are out.
    /// </summary>
    internal List<Prior> CurrentCycleDecodes()
    {
        lock (_lock) return _byCycle.TryGetValue(_currentSlot, out var list) ? [.. list] : [];
    }

    /// <summary>The number of cycles held (the current cycle's entry included), for the tests.</summary>
    internal int CycleCount { get { lock (_lock) return _byCycle.Count; } }

    /// <summary>The number of messages held for the cycle <paramref name="ageCycles"/> before the current one (0 = the current cycle), for the tests.</summary>
    internal int CountAt(int ageCycles)
    {
        lock (_lock) return _byCycle.TryGetValue(_currentSlot - ageCycles, out var l) ? l.Count : 0;
    }

    /// <summary>Every message held, all cycles, for the "OFF writes nothing" and "batch 6 never enters" tests (counts, not text, are what they assert).</summary>
    internal int TotalCount { get { lock (_lock) return _byCycle.Values.Sum(l => l.Count); } }

    /// <summary>
    /// R3: the distinct texts at the exact ages (<see cref="LiveAges"/> or <see cref="ShadowAges"/>), nearest prior first; where a text occurs at several ages the NEAREST one's position is used.
    /// The exclusions (already published, hashed, refused by the encoder) are applied by the caller.
    /// </summary>
    internal List<Candidate> Candidates(bool shadow)
    {
        var ages = shadow ? ShadowAges : LiveAges;
        var result = new List<Candidate>();
        var seen = new HashSet<string>(StringComparer.Ordinal);
        lock (_lock)
        {
            foreach (int age in ages)
            {
                if (!_byCycle.TryGetValue(_currentSlot - age, out var list)) continue;
                foreach (var prior in list)
                    if (seen.Add(prior.Text)) result.Add(new Candidate(prior, age));
            }
        }
        return result;
    }
}
