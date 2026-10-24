using System.Buffers.Binary;
using System.Runtime.InteropServices;

namespace OpenWSFZ.Ft8.Interop;

/// <summary>COH-FALLBACK Stage 2 (shim 20260068): mirrors <c>FT8CohFallbackCycleStats</c> (96 bytes).</summary>
[StructLayout(LayoutKind.Sequential)]
internal struct CohFallbackStatsNative
{
    public int NCandidates, NDecoded, NDupPosition, NEligible, NAttempted, NCrcOk, NCrcNew, NF1bComputed, NGated, NPublished,
               NAbandoned, NEdge, NDecodedEstimated, NRows, NWalkEntered, Reserved1;
    public double EstimateMs, F1bMs, C3BpMs, TotalMs;

    /// <summary>sizeof(FT8CohFallbackCycleStats).</summary>
    public const int ExpectedNativeSizeBytes = 96;
}

/// <summary>COH-FALLBACK Stage 2 (shim 20260068): mirrors <c>FT8CohFallbackOut</c> (56 bytes). The 12 payload bytes are a ulong and a uint (little-endian).</summary>
[StructLayout(LayoutKind.Sequential)]
internal struct CohFallbackOutNative
{
    public float FreqHz, DtS, OutFreqHz, OutDtS;
    public int Pass, Edge, State, SnrDb;
    public double F1bDb;
    public ulong Payload0;
    public uint Payload1;
    /// <summary>COH-MULTISET (20260071; was Reserved): the set that produced the payload (0 V3, 1 C1, 2 J2, 3 J3, 4 N1, -1 the walk found nothing).</summary>
    public int Provenance;

    /// <summary>sizeof(FT8CohFallbackOut).</summary>
    public const int ExpectedNativeSizeBytes = 56;
}

/// <summary>What became of one eligible candidate (<c>FT8_COH_STATE_*</c>).</summary>
internal enum CohFallbackState
{
    /// <summary>Not attempted: the deadline passed or the run was cancelled.</summary>
    Abandoned = 0,
    /// <summary>Attempted; the BP output was not CRC-valid.</summary>
    NoCrc = 1,
    /// <summary>CRC-valid, but a payload the ordinary decode produced in the call.</summary>
    Known = 2,
    /// <summary>CRC-valid, new payload, F1b above T1.</summary>
    GatedOut = 3,
    /// <summary>CRC-valid, new payload, F1b at or below T1: a candidate for publication.</summary>
    NewGated = 4,
}

/// <summary>One eligible candidate's outcome.</summary>
internal sealed record CohFallbackRow(
    float FreqHz, float DtS, float OutFreqHz, float OutDtS, int Pass, bool Edge, CohFallbackState State, int SnrDb, double F1bDb,
    byte[] Payload)
{
    /// <summary>
    /// COH-MULTISET: the set that produced <see cref="Payload"/>: 0 = V3 (always 0 with the multi-set flag off), 1 = C1, 2 = J2, 3 = J3, 4 = N1,
    /// -1 = the walk ran and found nothing. Meaningful for attempted rows.
    /// </summary>
    public int Provenance { get; init; }

    internal static CohFallbackRow From(in CohFallbackOutNative n)
    {
        var payload = new byte[12];
        BinaryPrimitives.WriteUInt64LittleEndian(payload.AsSpan(0, 8), n.Payload0);
        BinaryPrimitives.WriteUInt32LittleEndian(payload.AsSpan(8, 4), n.Payload1);
        return new CohFallbackRow(n.FreqHz, n.DtS, n.OutFreqHz, n.OutDtS, n.Pass, n.Edge != 0, (CohFallbackState)n.State, n.SnrDb, n.F1bDb, payload)
        {
            Provenance = n.Provenance,
        };
    }
}

/// <summary>The counters of one fallback run (the spec's R12' line plus the times).</summary>
internal readonly record struct CohFallbackStats(
    int Candidates, int Decoded, int DupPosition, int Eligible, int Attempted, int CrcOk, int CrcNew, int F1bComputed, int Gated,
    int Abandoned, int Edge, double EstimateMs, double F1bMs, double C3BpMs, double TotalMs)
{
    /// <summary>COH-MULTISET: candidates that entered the walk (V3 gave no CRC-valid output with the multi-set flag on); 0 with it off.</summary>
    public int WalkEntered { get; init; }

    internal static CohFallbackStats From(in CohFallbackStatsNative n) => new(
        n.NCandidates, n.NDecoded, n.NDupPosition, n.NEligible, n.NAttempted, n.NCrcOk, n.NCrcNew, n.NF1bComputed, n.NGated,
        n.NAbandoned, n.NEdge, n.EstimateMs, n.F1bMs, n.C3BpMs, n.TotalMs)
    {
        WalkEntered = n.NWalkEntered,
    };
}

/// <summary>The rows (candidate order) and counters of one fallback run.</summary>
internal sealed record CohFallbackRunResult(CohFallbackStats Stats, IReadOnlyList<CohFallbackRow> Rows)
{
    /// <summary>COH-FALLBACK step 4 (R15): the number of worker threads the run used (1 for the single-thread run).</summary>
    public int Workers { get; init; } = 1;

    /// <summary>
    /// COH-MULTISET: how many attempted rows carry a CRC-valid payload (state Known, GatedOut or NewGated) produced by <paramref name="set"/>
    /// (0 V3, 1 C1, 2 J2, 3 J3, 4 N1). Counted from the rows' provenance.
    /// </summary>
    public int CrcValidBySet(int set) => Rows.Count(r => r.Provenance == set
        && r.State is CohFallbackState.Known or CohFallbackState.GatedOut or CohFallbackState.NewGated);
}

/// <summary>
/// COH-FALLBACK step 4 (shim 20260069): what the native <c>ft8_coherent_fallback_plan</c> says about a snapshot: the counts, the snapshot
/// index of each eligible candidate in candidate order, and one row per eligible candidate pre-filled as <see cref="CohFallbackState.Abandoned"/>.
/// </summary>
internal sealed record CohFallbackPlan(CohFallbackStats Stats, IReadOnlyList<int> CandidateIndex, IReadOnlyList<CohFallbackRow> Rows);

/// <summary>
/// COH-FALLBACK step 4: one worker thread's native scratch context. NOT thread-safe: one worker object per thread, used by that thread
/// only. Disposing frees the native context.
/// </summary>
internal interface ICohFallbackWorker : IDisposable
{
    /// <summary>Runs the eligible candidate at snapshot index <paramref name="candidateIndex"/> and returns its row.</summary>
    /// <exception cref="Interop.NativeAccessViolationException">An access violation was contained by the native SEH wrapper; the worker must not be used again.</exception>
    CohFallbackRow Process(float[] pcm, byte[] snapshot, int candidateIndex);

    /// <summary>The counts and times of every candidate this worker has run so far (attempted, crcOk, crcNew, f1bComputed, gated, edge, ms).</summary>
    CohFallbackStats Accumulated { get; }

    /// <summary>
    /// COH-MULTISET: sets the multi-set walk bit on this worker's native context. The runner calls it on EVERY worker before the cycle's
    /// <see cref="Process"/> calls, because a context may outlive a cycle while the flag changes at run time (Architect A1.1). Default: no-op
    /// (a fake does not model the walk).
    /// </summary>
    void SetMultiSet(bool on) { }
}

/// <summary>COH-FALLBACK step 4: the native side of the parallel cycle, behind a seam so the scheduling can be tested without the library.</summary>
internal interface ICohFallbackBackend
{
    /// <summary>The eligible candidates of a snapshot, in candidate order. <c>null</c> when the plan cannot be made.</summary>
    CohFallbackPlan? Plan(byte[] snapshot);

    /// <summary>A new worker context (one per worker thread).</summary>
    ICohFallbackWorker CreateWorker();
}

/// <summary>COH-MULTISET Stage 1 (shim 20260071): mirrors <c>FT8CohSetOutcome</c> (32 bytes), the BP-only outcome of one 174-value vector.</summary>
[StructLayout(LayoutKind.Sequential)]
internal struct CohSetOutcomeNative
{
    public int BpRc, BpPath, BpCrcOk, BpLdpcErrors;
    public ulong A910;
    public uint A911;
    public int Reserved;

    /// <summary>sizeof(FT8CohSetOutcome).</summary>
    public const int ExpectedNativeSizeBytes = 32;
}

/// <summary>COH-MULTISET Stage 1 (shim 20260071): mirrors <c>FT8CohSetsResult</c> (216 bytes).</summary>
[StructLayout(LayoutKind.Sequential)]
internal struct CohSetsResultNative
{
    public double EstDfHz, EstDtS, Peak;
    public int DtStep, Edge, WalkEntered, WalkSet;
    public ulong WalkA910;
    public uint WalkA911;
    public int Reserved;
    public CohSetOutcomeNative V3, C1, J2, J3, N1;

    /// <summary>sizeof(FT8CohSetsResult).</summary>
    public const int ExpectedNativeSizeBytes = 216;
}

/// <summary>The BP-only outcome of one 174-value vector (V3 or one of the four further sets).</summary>
internal sealed record CohSetOutcome(int BpRc, int BpPath, bool CrcOk, int LdpcErrors, byte[] A91)
{
    /// <summary>True iff BP returned a codeword whose CRC-14 matched (the walk's test).</summary>
    public bool CrcValid => BpRc == 0 && CrcOk;

    internal static CohSetOutcome From(in CohSetOutcomeNative n)
    {
        var a91 = new byte[12];
        BinaryPrimitives.WriteUInt64LittleEndian(a91.AsSpan(0, 8), n.A910);
        BinaryPrimitives.WriteUInt32LittleEndian(a91.AsSpan(8, 4), n.A911);
        return new CohSetOutcome(n.BpRc, n.BpPath, n.BpCrcOk != 0, n.BpLdpcErrors, a91);
    }
}

/// <summary>
/// COH-MULTISET Stage 1: the diagnostic result of <c>ft8_coherent_fallback_sets_at</c>. <see cref="Sets"/> is C1, J2, J3, N1 in the walk's order;
/// <see cref="Raw"/> holds the 174 raw values of V3 then C1, J2, J3, N1. <see cref="WalkSet"/>: 0 V3 (no walk), 1 C1, 2 J2, 3 J3, 4 N1, -1 none.
/// </summary>
internal sealed record CohSetsResult(
    double EstDfHz, double EstDtS, double Peak, int DtStep, bool Edge, bool WalkEntered, int WalkSet, byte[] WalkPayload,
    CohSetOutcome V3, IReadOnlyList<CohSetOutcome> Sets, double[][] Raw);
