namespace OpenWSFZ.Ft8;

/// <summary>
/// CQ-AP: the per-cycle state of the CQ a-priori attempt, created once per decode cycle by <see cref="Ft8Decoder"/> (which reads
/// <c>decoder.cqApEnabled</c> once, there) and handed to every native decode of that cycle: pass 0, the residual pass, the third pass and the late
/// round. <see cref="Enabled"/> is the flag those decodes set on their own thread; the counters feed the one <c>cq-ap: attempts=N decodes=M</c>
/// line. The native decodes run on several threads, so the counters are incremented atomically. Counts only: never a callsign or message text.
/// </summary>
internal sealed class CqApCycleCounters
{
    private int _attempts;
    private int _decodes;

    /// <summary>Creates the cycle's state. <paramref name="enabled"/> is the flag as read once for this cycle.</summary>
    public CqApCycleCounters(bool enabled) => Enabled = enabled;

    /// <summary>Whether the CQ a-priori attempt is on for this cycle.</summary>
    public bool Enabled { get; }

    /// <summary>CQ-AP attempts made by the native decodes of this cycle so far (candidates whose normal attempt failed).</summary>
    public int Attempts => Volatile.Read(ref _attempts);

    /// <summary>CQ-AP decodes published in this cycle so far (past the plausibility filter and the text de-duplication).</summary>
    public int Decodes => Volatile.Read(ref _decodes);

    /// <summary>Adds the attempts one native decode reported.</summary>
    public void AddAttempts(int attempts) => Interlocked.Add(ref _attempts, attempts);

    /// <summary>Counts one published CQ-AP decode.</summary>
    public void AddDecode() => Interlocked.Increment(ref _decodes);
}
