namespace OpenWSFZ.Ft8.Interop;

/// <summary>
/// Production implementation of <see cref="IFt8NativeInterop"/> that
/// delegates to the static <see cref="Ft8LibInterop"/> P/Invoke binding.
///
/// <para>
/// Sealed and stateless — safe to share as a static singleton.
/// </para>
/// </summary>
internal sealed class Ft8NativeInteropAdapter : IFt8NativeInterop
{
    public int MaxDecodePasses
        => Ft8LibInterop.MaxDecodePasses;

    /// <inheritdoc/>
    /// <exception cref="NativeAccessViolationException">
    /// Re-thrown from <see cref="Ft8LibInterop.DecodeAll"/> when the native
    /// shim's SEH wrapper catches an access violation.
    /// </exception>
    public Ft8NativeResult[] DecodeAll(float[] pcm)
        => Ft8LibInterop.DecodeAll(pcm);

    public int[] GetLastPassCounts(int maxPasses)
        => Ft8LibInterop.GetLastPassCounts(maxPasses);

    public int[] GetLastCandidateCounts(int maxPasses)
        => Ft8LibInterop.GetLastCandidateCounts(maxPasses);

    public float GetLastNoiseFloorDb()
        => Ft8LibInterop.GetLastNoiseFloorDb();

    public int GetHashTableRejectCount()
        => Ft8LibInterop.GetHashTableRejectCount();

    public int GetH12DisplayingCount() => Ft8LibInterop.GetH12DisplayingCount();
    public int GetH12AmbiguousCount()  => Ft8LibInterop.GetH12AmbiguousCount();
    public int GetH12DivergentCount()  => Ft8LibInterop.GetH12DivergentCount();

    public (float[] MeanAbs, float[] PrenormVariance, int[] FailCount) GetLastLlrStats(int maxPasses)
        => Ft8LibInterop.GetLastLlrStats(maxPasses);

    public void SetApBits(byte[] mycallBits, byte[] hiscallBits)
        => Ft8LibInterop.SetApBits(mycallBits, hiscallBits);

    public void SetDecodeParams(int kMinScorePass2, float osdCorrThreshold, int osdNhardMax)
        => Ft8LibInterop.SetDecodeParams(kMinScorePass2, osdCorrThreshold, osdNhardMax);

    public (float DeltaFreqHz, float DeltaTimeS, float SyncScore, int CoarseDtSamp, int FineDtSamp) RefineCandidate(
        float[] pcm, int coarseFreqHz, float coarseTimeOffsetS)
        => Ft8LibInterop.RefineCandidate(pcm, coarseFreqHz, coarseTimeOffsetS);

    public float[] CoherentLlrAt(float[] pcm, float freqHz, float timeOffsetS)
        => Ft8LibInterop.CoherentLlrAt(pcm, freqHz, timeOffsetS);

    public (float[] SignalDb, float[] LocalNoiseDb) GetLastSnrTerms(int maxDecoded)
        => Ft8LibInterop.GetLastSnrTerms(maxDecoded);
}
