using System.Buffers.Binary;
using System.Runtime.InteropServices;

namespace OpenWSFZ.Ft8.Interop;

/// <summary>COH-FALLBACK Stage 2 (shim 20260068): mirrors <c>FT8CohFallbackCycleStats</c> (96 bytes).</summary>
[StructLayout(LayoutKind.Sequential)]
internal struct CohFallbackStatsNative
{
    public int NCandidates, NDecoded, NDupPosition, NEligible, NAttempted, NCrcOk, NCrcNew, NF1bComputed, NGated, NPublished,
               NAbandoned, NEdge, NDecodedEstimated, NRows, Reserved0, Reserved1;
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
    public int Reserved;

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
    internal static CohFallbackRow From(in CohFallbackOutNative n)
    {
        var payload = new byte[12];
        BinaryPrimitives.WriteUInt64LittleEndian(payload.AsSpan(0, 8), n.Payload0);
        BinaryPrimitives.WriteUInt32LittleEndian(payload.AsSpan(8, 4), n.Payload1);
        return new CohFallbackRow(n.FreqHz, n.DtS, n.OutFreqHz, n.OutDtS, n.Pass, n.Edge != 0, (CohFallbackState)n.State, n.SnrDb, n.F1bDb, payload);
    }
}

/// <summary>The counters of one fallback run (the spec's R12' line plus the times).</summary>
internal readonly record struct CohFallbackStats(
    int Candidates, int Decoded, int DupPosition, int Eligible, int Attempted, int CrcOk, int CrcNew, int F1bComputed, int Gated,
    int Abandoned, int Edge, double EstimateMs, double F1bMs, double C3BpMs, double TotalMs)
{
    internal static CohFallbackStats From(in CohFallbackStatsNative n) => new(
        n.NCandidates, n.NDecoded, n.NDupPosition, n.NEligible, n.NAttempted, n.NCrcOk, n.NCrcNew, n.NF1bComputed, n.NGated,
        n.NAbandoned, n.NEdge, n.EstimateMs, n.F1bMs, n.C3BpMs, n.TotalMs);
}

/// <summary>The rows (candidate order) and counters of one fallback run.</summary>
internal sealed record CohFallbackRunResult(CohFallbackStats Stats, IReadOnlyList<CohFallbackRow> Rows)
{
    /// <summary>COH-FALLBACK step 4 (R15): the number of worker threads the run used (1 for the single-thread run).</summary>
    public int Workers { get; init; } = 1;
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
}

/// <summary>COH-FALLBACK step 4: the native side of the parallel cycle, behind a seam so the scheduling can be tested without the library.</summary>
internal interface ICohFallbackBackend
{
    /// <summary>The eligible candidates of a snapshot, in candidate order. <c>null</c> when the plan cannot be made.</summary>
    CohFallbackPlan? Plan(byte[] snapshot);

    /// <summary>A new worker context (one per worker thread).</summary>
    ICohFallbackWorker CreateWorker();
}
