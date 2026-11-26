using System.Runtime.InteropServices;

namespace OpenWSFZ.Ft8.Interop;

/// <summary>
/// What a lean cycle is asked to do: the worker count, whether the CQ a-priori attempt runs (<c>decoder.cqApEnabled</c>), the wall-clock
/// budget tier B and CQ-AP may still spend (<c>null</c> = none), and a candidate cap (0 = the primary pass's 140; tests lower it).
/// Step 2c: <paramref name="Rounds"/> runs the subtract-and-retry loop after round 0 (off by default, so a step-2b caller is unchanged),
/// <paramref name="MaxRounds"/> caps it (0 = 3), <paramref name="ResidualUngated"/> and <paramref name="ResidualCandidates"/> carry
/// <c>decoder.coherentFallbackResidualUngated</c> and <c>decoder.coherentFallbackResidualCandidates</c> (each only with the fallback audio mode Both),
/// and <paramref name="ExpireRound"/> is a TEST HOOK: the budget is treated as gone at that round's decode stage (0 = none).
/// Step 2d: <paramref name="NoTierB"/> is <c>decoder.effort = fast</c> (no tier B in any round; the caller also sets <paramref name="MaxRounds"/> to 1) and
/// <paramref name="WantResidual"/> asks for the final residual buffer (<see cref="LeanCycleOutcome.Residual"/>).
/// Step 2e: <paramref name="SkipFits"/> turns on the fit-skip rule (a result is fitted only if a failed candidate of its round lies in its patch window; off by default
/// here, on in the daemon's lean cycle) and <paramref name="InjectErrorRound"/> is a TEST HOOK (a simulated allocation failure after the first chunk of that round's fits).
/// </summary>
internal readonly record struct LeanCycleParams(
    int Threads, bool CqAp = false, int? BudgetMs = null, int MaxCandidates = 0,
    bool Rounds = false, int MaxRounds = 0, bool ResidualUngated = false, bool ResidualCandidates = false, int ExpireRound = 0,
    bool NoTierB = false, bool WantResidual = false, bool SkipFits = false, int InjectErrorRound = 0);

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
/// Mirror of the native <c>ftz_params_t</c> (<c>native/ftz_decoder/ftz_decoder.h</c>): ten 32-bit integers, 40 bytes. A zero field means the
/// primary pass's value (or "off") on the native side. Step 2d adds three pointers (the round-0 callback, its context and the residual buffer): 64 bytes.
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
    public int MaxRounds;
    public int ExpireRound;
    public IntPtr Round0Callback;
    public IntPtr Round0Context;
    public IntPtr OutResidual;
    public int InjectErrorRound;
    public int Reserved2;

    /// <summary><c>FTZ_FLAG_NO_TIER_B</c>.</summary>
    public const int FlagNoTierB = 32;

    /// <summary><c>FTZ_FLAG_SKIP_FITS</c>.</summary>
    public const int FlagSkipFits = 64;

    /// <summary><c>FTZ_FLAG_CQ_AP</c>.</summary>
    public const int FlagCqAp = 1;

    /// <summary><c>FTZ_FLAG_BUDGET</c>.</summary>
    public const int FlagBudget = 2;

    /// <summary><c>FTZ_FLAG_ROUNDS</c>.</summary>
    public const int FlagRounds = 4;

    /// <summary><c>FTZ_FLAG_RESIDUAL_UNGATED</c>.</summary>
    public const int FlagResidualUngated = 8;

    /// <summary><c>FTZ_FLAG_RESIDUAL_CANDS</c>.</summary>
    public const int FlagResidualCandidates = 16;
}

/// <summary>Mirror of the native <c>ftz_round_stats_t</c>: ten 32-bit counts and nine 64-bit microsecond counters, 112 bytes.</summary>
[StructLayout(LayoutKind.Sequential)]
internal struct FtzRoundWire
{
    public int NFits, NSubtracted, NFitNone, NFound, NKept, NTierA, NResults, NUngated, NFitSkipped, Reserved;
    public long SubWallUs, FitCpuUs, SumCpuUs;
    public long SpecWallUs, SpecCpuUs;
    public long SearchWallUs, SearchCpuUs;
    public long DecodeWallUs, DecodeCpuUs;
}

/// <summary>Mirror of the native <c>ftz_stats_t</c>: twenty 32-bit integers, fourteen 64-bit microsecond counters (192 bytes) and four <see cref="FtzRoundWire"/> (640 bytes in all).</summary>
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
    public int NRounds;
    public int NBEligible, NBAttempted, NBCrcValid, NBF1b, NBGated, NBPublished, NBEdge, NBSkipped;
    public int NCqAttempts, NCqDecodes;
    public int NUngated, HasResidual;
    public long SpectrogramWallUs, SpectrogramCpuUs;
    public long CandidatesWallUs, CandidatesCpuUs;
    public long TierAWallUs, TierACpuUs;
    public long TierBWallUs, TierBCpuUs;
    public long CqApWallUs, CqApCpuUs;
    public long UnpackWallUs, UnpackCpuUs;
    public long TotalWallUs, TotalCpuUs;
    public FtzRoundWire Round0, Round1, Round2, Round3;
}

/// <summary>
/// One round of the lean engine (step 2c; round 0 is the step-2b decode): counts and times only (HK-037). Times are microseconds: wall, and CPU summed
/// over the workers. <see cref="SubWallUs"/> is the whole subtract step (the fits and the sum into the residual); <see cref="FitCpuUs"/> is the fits' CPU
/// and <see cref="SumCpuUs"/> the sum's. Search is <c>ftx_find_candidates</c> and the patch rule; decode is tier A, tier B, CQ-AP and unpack.
/// </summary>
internal readonly record struct LeanRoundStats(
    int Fits, int Subtracted, int FitNone, int Found, int Kept, int TierA, int Results, int Ungated,
    long SubWallUs, long FitCpuUs, long SumCpuUs,
    long SpecWallUs, long SpecCpuUs, long SearchWallUs, long SearchCpuUs, long DecodeWallUs, long DecodeCpuUs)
{
    /// <summary>Step 2e: re-encodable results the fit-skip rule left unfitted in this round's subtract step.</summary>
    public int FitSkipped { get; init; }

    /// <summary>The subtract step's CPU: the fits plus the sum.</summary>
    public long SubCpuUs => FitCpuUs + SumCpuUs;

    internal static LeanRoundStats From(in FtzRoundWire r) => new(
        r.NFits, r.NSubtracted, r.NFitNone, r.NFound, r.NKept, r.NTierA, r.NResults, r.NUngated,
        r.SubWallUs, r.FitCpuUs, r.SumCpuUs, r.SpecWallUs, r.SpecCpuUs, r.SearchWallUs, r.SearchCpuUs, r.DecodeWallUs, r.DecodeCpuUs)
    {
        FitSkipped = r.NFitSkipped,
    };
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
    /// <summary>Step 2c: subtract-and-retry rounds run (0 to 3).</summary>
    public int RoundsRun { get; init; }
    /// <summary>Step 2c: residual tier-B rows published only because the ungating is on.</summary>
    public int Ungated { get; init; }
    /// <summary>Step 2c: per round, index 0 (round 0) to 3; empty for a cycle that never reached the native call.</summary>
    public LeanRoundStats[] Rounds { get; init; } = [];

    /// <summary>Step 2e: signals the fit-skip rule left unfitted, over rounds 1 to 3.</summary>
    public int S3FitSkipped => Rounds.Skip(1).Sum(r => r.FitSkipped);
    /// <summary>The CPU of every round's fits (the subtract step), microseconds: the S3 cost of fitting.</summary>
    public long S3FitCpuUs => Rounds.Skip(1).Sum(r => r.FitCpuUs);
    /// <summary>The CPU of every round's candidate search (<c>ftx_find_candidates</c> and the patch rule), microseconds.</summary>
    public long S3SearchCpuUs => Rounds.Skip(1).Sum(r => r.SearchCpuUs);
    /// <summary>The CPU of every round's decode (tier A, B, CQ-AP, unpack), microseconds.</summary>
    public long S3DecodeCpuUs => Rounds.Skip(1).Sum(r => r.DecodeCpuUs);
    /// <summary>The CPU of every round's sum into the residual and re-spectrogram, microseconds.</summary>
    public long S3OtherCpuUs => Rounds.Skip(1).Sum(r => r.SumCpuUs + r.SpecCpuUs);
    /// <summary>The wall time of all of S3 (rounds 1 to 3), microseconds.</summary>
    public long S3WallUs => Rounds.Skip(1).Sum(r => r.SubWallUs + r.SpecWallUs + r.SearchWallUs + r.DecodeWallUs);
    /// <summary>The CPU of all of S3 (rounds 1 to 3), microseconds.</summary>
    public long S3CpuUs => S3FitCpuUs + S3SearchCpuUs + S3DecodeCpuUs + S3OtherCpuUs;

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
        RoundsRun = s.NRounds, Ungated = s.NUngated,
        Rounds = [LeanRoundStats.From(in s.Round0), LeanRoundStats.From(in s.Round1), LeanRoundStats.From(in s.Round2), LeanRoundStats.From(in s.Round3)],
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

    /// <summary>The round (0 to 3) in which each result was found, index-aligned with <see cref="Results"/>; empty means every result is round 0.</summary>
    public byte[] Rounds { get; init; } = [];

    /// <summary>
    /// Step 2d: the residual buffer as of the last subtraction made (180 000 samples, the conditioned audio less every fitted signal), or <c>null</c> when the cycle
    /// subtracted nothing, a fit round was stopped, or none was asked for. Results found in the last round are NOT subtracted from it.
    /// </summary>
    public float[]? Residual { get; init; }
}

/// <summary>
/// Step 2d: what the native engine hands over right after round 0 is unpacked, before round 1 starts: round 0's results and their tiers. It is a copy; the native
/// call goes on while the consumer holds it.
/// </summary>
internal sealed record LeanRound0(Ft8NativeResult[] Results, byte[] Tiers);
