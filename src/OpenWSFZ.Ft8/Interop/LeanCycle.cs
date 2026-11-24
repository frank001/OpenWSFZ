using System.Runtime.InteropServices;

namespace OpenWSFZ.Ft8.Interop;

/// <summary>
/// What a lean cycle is asked to do (step 2b): the worker count, whether the CQ a-priori attempt runs (<c>decoder.cqApEnabled</c>), the wall-clock
/// budget tier B and CQ-AP may still spend (<c>null</c> = none), and a candidate cap (0 = the primary pass's 140; tests lower it).
/// </summary>
internal readonly record struct LeanCycleParams(int Threads, bool CqAp = false, int? BudgetMs = null, int MaxCandidates = 0);

/// <summary>Where a lean result came from (the native <c>FTZ_TIER_*</c> values).</summary>
internal static class LeanTier
{
    /// <summary>Tier A: magnitude likelihoods, belief propagation, CRC.</summary>
    public const byte A = 0;

    /// <summary>Tier B: the coherent fallback's per-candidate body.</summary>
    public const byte B = 1;

    /// <summary>The CQ a-priori attempt.</summary>
    public const byte CqAp = 2;
}

/// <summary>
/// Mirror of the native <c>ftz_params_t</c> (<c>native/ftz_decoder/ftz_decoder.h</c>): eight 32-bit integers, 32 bytes. A zero field means "today's
/// primary value" on the native side.
/// </summary>
[StructLayout(LayoutKind.Sequential)]
internal struct FtzParamsWire
{
    public int StructSize;
    public int Threads;
    public int MinScore;
    public int MaxCandidates;
    public int LdpcIterations;
    public int Flags;
    public int BudgetMs;
    public int Reserved;

    /// <summary><c>FTZ_FLAG_CQ_AP</c>.</summary>
    public const int FlagCqAp = 1;

    /// <summary><c>FTZ_FLAG_BUDGET</c>.</summary>
    public const int FlagBudget = 2;
}

/// <summary>Mirror of the native <c>ftz_stats_t</c>: twenty 32-bit integers and fourteen 64-bit microsecond counters, 192 bytes.</summary>
[StructLayout(LayoutKind.Sequential)]
internal struct FtzStatsWire
{
    public int StructSize;
    public int Error;
    public int NCandidates;
    public int NTierA;
    public int NResults;
    public int Threads;
    public int Abandoned;
    public int Reserved0;
    public int NBEligible, NBAttempted, NBCrcValid, NBF1b, NBGated, NBPublished, NBEdge, NBSkipped;
    public int NCqAttempts, NCqDecodes;
    public int Reserved1, Reserved2;
    public long SpectrogramWallUs, SpectrogramCpuUs;
    public long CandidatesWallUs, CandidatesCpuUs;
    public long TierAWallUs, TierACpuUs;
    public long TierBWallUs, TierBCpuUs;
    public long CqApWallUs, CqApCpuUs;
    public long UnpackWallUs, UnpackCpuUs;
    public long TotalWallUs, TotalCpuUs;
}

/// <summary>
/// The lean engine's per-cycle aggregates (DR-2): per-stage wall and CPU time, the candidate and per-tier counts, the effective thread count,
/// the abandoned flag and the native error code. Counts and times only; never message text (HK-037).
/// </summary>
internal readonly record struct LeanCycleStats(
    int Error,
    int Candidates,
    int TierADecodes,
    int Results,
    int Threads,
    bool Abandoned,
    long SpectrogramWallUs, long SpectrogramCpuUs,
    long CandidatesWallUs, long CandidatesCpuUs,
    long TierAWallUs, long TierACpuUs,
    long UnpackWallUs, long UnpackCpuUs,
    long TotalWallUs, long TotalCpuUs)
{
    /// <summary>The native error codes of <c>ftz_decoder.h</c>.</summary>
    public const int Ok = 0, ErrArg = -1, ErrNoMem = -2, ErrFault = -3, ErrBadAudio = -4;

    /// <summary>Tier B: candidates that failed tier A and were eligible.</summary>
    public int TierBEligible { get; init; }
    /// <summary>Tier B: of those, run (not skipped by the budget).</summary>
    public int TierBAttempted { get; init; }
    /// <summary>Tier B: attempted with a CRC-valid output.</summary>
    public int TierBCrcValid { get; init; }
    /// <summary>Tier B: CRC-valid with a payload tier A did not produce (F1b computed).</summary>
    public int TierBF1b { get; init; }
    /// <summary>Tier B: of those, F1b at most T1.</summary>
    public int TierBGated { get; init; }
    /// <summary>Tier B: rows in the output.</summary>
    public int TierBPublished { get; init; }
    /// <summary>Tier B: attempted rows whose estimate sits on a window edge.</summary>
    public int TierBEdge { get; init; }
    /// <summary>Tier B: eligible candidates the budget kept from being attempted.</summary>
    public int TierBSkipped { get; init; }
    /// <summary>CQ-AP attempts.</summary>
    public int CqApAttempts { get; init; }
    /// <summary>CQ-AP rows in the output.</summary>
    public int CqApDecodes { get; init; }
    /// <summary>Tier B wall time, microseconds.</summary>
    public long TierBWallUs { get; init; }
    /// <summary>Tier B CPU time summed over the workers, microseconds.</summary>
    public long TierBCpuUs { get; init; }
    /// <summary>CQ-AP wall time, microseconds.</summary>
    public long CqApWallUs { get; init; }
    /// <summary>CQ-AP CPU time summed over the workers, microseconds.</summary>
    public long CqApCpuUs { get; init; }

    /// <summary>A stats record for a cycle that never reached the native call (used by test doubles and the error paths).</summary>
    public static LeanCycleStats None(int error = 0) =>
        new(error, 0, 0, 0, 0, false, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0);

    /// <summary>Builds the record from the native struct.</summary>
    internal static LeanCycleStats From(in FtzStatsWire s) => new(
        s.Error, s.NCandidates, s.NTierA, s.NResults, s.Threads, s.Abandoned != 0,
        s.SpectrogramWallUs, s.SpectrogramCpuUs, s.CandidatesWallUs, s.CandidatesCpuUs,
        s.TierAWallUs, s.TierACpuUs, s.UnpackWallUs, s.UnpackCpuUs, s.TotalWallUs, s.TotalCpuUs)
    {
        TierBEligible = s.NBEligible, TierBAttempted = s.NBAttempted, TierBCrcValid = s.NBCrcValid, TierBF1b = s.NBF1b, TierBGated = s.NBGated,
        TierBPublished = s.NBPublished, TierBEdge = s.NBEdge, TierBSkipped = s.NBSkipped,
        CqApAttempts = s.NCqAttempts, CqApDecodes = s.NCqDecodes,
        TierBWallUs = s.TierBWallUs, TierBCpuUs = s.TierBCpuUs, CqApWallUs = s.CqApWallUs, CqApCpuUs = s.CqApCpuUs,
    };
}

/// <summary>
/// What one <c>ftz_decode_cycle</c> call returned: the results (already sorted by the native side; every result the call had written when it
/// stopped, also on an error) and the statistics. <see cref="LeanCycleStats.Error"/> is non-zero when the native call reported an error.
/// </summary>
internal readonly record struct LeanCycleOutcome(Ft8NativeResult[] Results, LeanCycleStats Stats)
{
    /// <summary>The tier of each result (<see cref="LeanTier"/>), index-aligned with <see cref="Results"/>; empty means every result is tier A.</summary>
    public byte[] Tiers { get; init; } = [];
}
