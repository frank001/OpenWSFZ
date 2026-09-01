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
    /// Return the process-lifetime count of Type 4 callsign announcements discarded because
    /// the native session-scoped hash table was already at its 4096-slot capacity
    /// (f-005-hash-table-saturation-diagnostic, shim 20260032; capacity raised from 256 to
    /// 4096 at shim 20260038, g2-hash-table-sizing-and-candidate-passband).
    /// <para>
    /// Process-global (not thread-local): unlike the other getters here it may be read from
    /// any thread, including the daemon shutdown path.  Read-only — reading it never resets the
    /// counter or alters hash resolution.  Returns 0 if the table never reached capacity.
    /// </para>
    /// </summary>
    int GetHashTableRejectCount();

    /// <summary>
    /// Process-lifetime count of EMITTED decodes whose display resolved via the 12-bit
    /// nonstandard-callsign hash path (f001-sup-b-instrumented-suppression-sizing, shim
    /// 20260047). Denominator for spec Sec.3.1's S and D. Process-global, read-only.
    /// </summary>
    int GetH12DisplayingCount();

    /// <summary>
    /// Of <see cref="GetH12DisplayingCount"/>, how many resolved against a probe chain
    /// holding ≥2 matching entries (shim 20260047). Process-global, read-only.
    /// </summary>
    int GetH12AmbiguousCount();

    /// <summary>
    /// Of <see cref="GetH12DisplayingCount"/>, how many had their most-recently-announced
    /// matching entry differ from the first (displayed) match (shim 20260047). A ceiling
    /// on change, not a benefit — see spec Sec.6.5's three prohibitions before citing this
    /// anywhere. Process-global, read-only.
    /// </summary>
    int GetH12DivergentCount();

    /// <summary>
    /// Process-lifetime count of EMITTED decodes whose 12-bit callsign was suppressed because
    /// its probe chain held ≥2 matching entries (f001-h12-unique-match-suppression, shim
    /// 20260049). By design, arithmetically identical to <see cref="GetH12AmbiguousCount"/> on
    /// every run — a wiring invariant between the decision site and the counting site, not new
    /// information; see the native getter's own doc comment. Process-global, read-only.
    /// </summary>
    int GetH12SuppressedCount();

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

    /// <summary>
    /// Diagnostic-only per-candidate coherent sync refinement
    /// (r1-sync-refiner-instrument-validation, shim 20260040; extended with the coarse/fine
    /// time-search decomposition at r1b-sync-refiner-instrument-correction, shim 20260041).
    /// Given the cycle's PCM and a candidate's coarse <c>(freq_hz, dt)</c> position, returns a
    /// refined <c>(Δf, Δt)</c> RELATIVE TO that coarse position, a sync quality score, and the
    /// two search-stage selections (<c>CoarseDtSamp</c>, <c>FineDtSamp</c>) whose sum equals
    /// the returned <c>Δt</c> to within float32 rounding tolerance.
    /// <para>
    /// Reachable only from the validation harness and test code — no production call site
    /// invokes it.
    /// </para>
    /// </summary>
    /// <param name="pcm">12 kHz mono float32 PCM, normalised to [-1, 1]; must be exactly 180 000 samples.</param>
    /// <param name="coarseFreqHz">Coarse candidate frequency (Hz).</param>
    /// <param name="coarseTimeOffsetS">Coarse candidate time offset (s) from cycle start.</param>
    (float DeltaFreqHz, float DeltaTimeS, float SyncScore, int CoarseDtSamp, int FineDtSamp) RefineCandidate(
        float[] pcm, int coarseFreqHz, float coarseTimeOffsetS);

    /// <summary>
    /// Diagnostic-only per-candidate coherent multi-symbol LLR formation
    /// (r2-coherent-llr-instrument, Route B2 Phase 1, shim 20260043). Given the cycle's
    /// PCM and a candidate's EXISTING, UNREFINED grid <c>(freqHz, timeOffsetS)</c>, returns
    /// 174 coherent per-bit LLRs, normalised to the same scale production's <c>log174</c>
    /// uses. NEVER calls <c>ft8_refine_candidate</c>/<see cref="RefineCandidate"/>
    /// internally (design.md D1).
    /// <para>
    /// Reachable only from test code and the Phase 1 gate harness — no production call
    /// site invokes it.
    /// </para>
    /// </summary>
    /// <param name="pcm">12 kHz mono float32 PCM, normalised to [-1, 1]; must be exactly 180 000 samples.</param>
    /// <param name="freqHz">Candidate grid frequency (Hz) — tone 0's frequency, unrefined.</param>
    /// <param name="timeOffsetS">Candidate grid time offset (s) from cycle start, unrefined.</param>
    float[] CoherentLlrAt(float[] pcm, float freqHz, float timeOffsetS);

    /// <summary>
    /// Return the two terms of the per-signal SNR formula for every decode
    /// returned by the most recent <see cref="DecodeAll"/> call on this thread
    /// (Amendment 2, corrected by Amendment 3, shim 20260045).
    /// <para>
    /// <c>snr = signal_db - local_noise_db - 26.5f</c>. <c>SignalDb[i]</c> /
    /// <c>LocalNoiseDb[i]</c> correspond to the <c>i</c>-th result from that
    /// same <see cref="DecodeAll"/> call — INDEX-ALIGNED, same order.
    /// </para>
    /// MUST be called on the same thread as <see cref="DecodeAll"/>.
    /// </summary>
    /// <param name="maxDecoded">Maximum number of decodes to query (array capacity).</param>
    (float[] SignalDb, float[] LocalNoiseDb) GetLastSnrTerms(int maxDecoded);
}
