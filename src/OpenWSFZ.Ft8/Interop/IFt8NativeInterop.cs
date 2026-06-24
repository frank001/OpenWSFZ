namespace OpenWSFZ.Ft8.Interop;

/// <summary>
/// Abstraction over the native ft8_lib P/Invoke binding layer.
///
/// <para>
/// Introduced so that <see cref="Ft8Decoder"/> can be unit-tested without
/// requiring the native <c>libft8</c> binary.  The production implementation
/// is <see cref="Ft8NativeInteropAdapter"/>; test doubles can throw
/// <see cref="NativeAccessViolationException"/> to simulate an AV in the
/// native pipeline.
/// </para>
/// </summary>
internal interface IFt8NativeInterop
{
    /// <summary>
    /// Number of decode passes executed per <see cref="DecodeAll"/> call.
    /// Mirrors the native <c>K_MAX_PASSES</c> compile-time constant.
    /// </summary>
    int MaxDecodePasses { get; }

    /// <summary>
    /// Decode all FT8 signals from a 180 000-sample PCM buffer.
    /// </summary>
    /// <param name="pcm">12 kHz mono float32 PCM, normalised to [-1, 1].</param>
    /// <returns>Array of decoded results (may be empty; never null).</returns>
    /// <exception cref="NativeAccessViolationException">
    /// Thrown when the native shim reports an access violation (return code -2).
    /// </exception>
    Ft8NativeResult[] DecodeAll(float[] pcm);

    /// <summary>
    /// Return per-pass new-decode counts from the most recent
    /// <see cref="DecodeAll"/> call on this thread.
    /// MUST be called on the same thread as <see cref="DecodeAll"/>.
    /// </summary>
    int[] GetLastPassCounts(int maxPasses);

    /// <summary>
    /// Return per-pass candidate counts (raw <c>ftx_find_candidates</c> output)
    /// from the most recent <see cref="DecodeAll"/> call on this thread.
    /// MUST be called on the same thread as <see cref="DecodeAll"/>.
    /// </summary>
    int[] GetLastCandidateCounts(int maxPasses);

    /// <summary>
    /// Return the histogram-median waterfall noise floor (dB) from the most
    /// recent <see cref="DecodeAll"/> call on this thread.
    /// MUST be called on the same thread as <see cref="DecodeAll"/>.
    /// </summary>
    float GetLastNoiseFloorDb();

    /// <summary>
    /// Return per-pass LLR statistics for LDPC-failing candidates from the most
    /// recent <see cref="DecodeAll"/> call on this thread (redesigned at shim 20260020).
    /// <para>
    /// <c>MeanAbs[i]</c> — post-normalisation mean abs(LLR) for pass <c>i</c>.
    /// <c>PrenormVariance[i]</c> — pre-normalisation variance of raw log174 for pass <c>i</c>;
    /// confirms D-001 root cause when small.
    /// <c>FailCount[i]</c> — LDPC-failing candidate count for pass <c>i</c>.
    /// </para>
    /// MUST be called on the same thread as <see cref="DecodeAll"/>.
    /// </summary>
    (float[] MeanAbs, float[] PrenormVariance, int[] FailCount) GetLastLlrStats(int maxPasses);

    /// <summary>
    /// Supply known AP bit constraints for the next decode cycle (H6 directed AP decode,
    /// shim 20260020).  Pass empty arrays to disable.
    /// MUST be called on the same thread as <see cref="DecodeAll"/> or before it.
    /// </summary>
    void SetApBits(byte[] mycallBits, byte[] hiscallBits);

    /// <summary>
    /// Update the three runtime-configurable OSD gate parameters (decoder-settings-page,
    /// shim 20260030).  Values take effect on the next <see cref="DecodeAll"/> call.
    /// Safe to call before the first <see cref="DecodeAll"/> invocation.
    /// </summary>
    /// <param name="kMinScorePass2">Pass-1 candidate score floor (default 10, valid [5, 30]).</param>
    /// <param name="osdCorrThreshold">OSD normalised correlation gate (default 0.10f, valid [0.05, 0.40]).</param>
    /// <param name="osdNhardMax">OSD maximum Hamming-distance gate (default 60, valid [30, 100]).</param>
    void SetDecodeParams(int kMinScorePass2, float osdCorrThreshold, int osdNhardMax);
}
