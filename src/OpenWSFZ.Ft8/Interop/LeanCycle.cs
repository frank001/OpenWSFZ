using System.Runtime.InteropServices;

namespace OpenWSFZ.Ft8.Interop;

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
    public int Reserved0, Reserved1, Reserved2;
}

/// <summary>Mirror of the native <c>ftz_stats_t</c>: eight 32-bit integers and ten 64-bit microsecond counters, 112 bytes.</summary>
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
    public long SpectrogramWallUs, SpectrogramCpuUs;
    public long CandidatesWallUs, CandidatesCpuUs;
    public long TierAWallUs, TierACpuUs;
    public long UnpackWallUs, UnpackCpuUs;
    public long TotalWallUs, TotalCpuUs;
}

/// <summary>
/// The lean engine's per-cycle aggregates (DR-2 step 2a): per-stage wall and CPU time, the candidate and tier-A counts, the effective thread count,
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

    /// <summary>A stats record for a cycle that never reached the native call (used by test doubles and the error paths).</summary>
    public static LeanCycleStats None(int error = 0) =>
        new(error, 0, 0, 0, 0, false, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0);

    /// <summary>Builds the record from the native struct.</summary>
    internal static LeanCycleStats From(in FtzStatsWire s) => new(
        s.Error, s.NCandidates, s.NTierA, s.NResults, s.Threads, s.Abandoned != 0,
        s.SpectrogramWallUs, s.SpectrogramCpuUs, s.CandidatesWallUs, s.CandidatesCpuUs,
        s.TierAWallUs, s.TierACpuUs, s.UnpackWallUs, s.UnpackCpuUs, s.TotalWallUs, s.TotalCpuUs);
}

/// <summary>
/// What one <c>ftz_decode_cycle</c> call returned: the results (already sorted by the native side; every result the call had written when it
/// stopped, also on an error) and the statistics. <see cref="LeanCycleStats.Error"/> is non-zero when the native call reported an error.
/// </summary>
internal readonly record struct LeanCycleOutcome(Ft8NativeResult[] Results, LeanCycleStats Stats);
