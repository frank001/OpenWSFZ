namespace OpenWSFZ.Ft8;

/// <summary>
/// One pass-0 candidate's diagnostic record from the C.2 LLR-normalisation investigation
/// (dev-tasks/2026-07-26-d001-c2-llr-normalization.md).
///
/// <para>
/// Emitted only when diagnostic capture is enabled via
/// <see cref="Ft8Decoder.SetCandidateDiagCapture"/> — disabled by default, so this record
/// never appears on the production decode path. Covers every pass-0 candidate examined
/// during a decode cycle, whether or not it went on to decode, so callers can compare the
/// LLR-normalisation statistics of candidates that did and did not survive LDPC/OSD.
/// </para>
/// </summary>
/// <param name="FreqHz">Candidate centre frequency, Hz (same formula as <c>DecodeResult.FreqHz</c>).</param>
/// <param name="Dt">Candidate time offset from cycle start, seconds.</param>
/// <param name="Score">Sync score (<c>ftx_candidate_t.score</c> in the native shim).</param>
/// <param name="Decoded">
/// <c>true</c> if the native LDPC/OSD decode converged and the CRC matched for this
/// candidate this cycle. Independent of any later cross-pass dedup or text-unpack outcome —
/// this is the LDPC-survival signal the C.2 hypothesis is about, not "appeared in the
/// cycle's final decode list."
/// </param>
/// <param name="PrenormVariance">Pre-normalisation variance of the raw log174 array.</param>
/// <param name="PostnormMeanAbsLlr">
/// Post-normalisation mean|LLR|. <see cref="float.NaN"/> for degenerate candidates
/// (pre-normalisation variance == 0) — callers must check <see cref="float.IsFinite(float)"/>
/// before using this value.
/// </param>
public sealed record Ft8CandidateDiagnostic(
    float FreqHz,
    float Dt,
    short Score,
    bool  Decoded,
    float PrenormVariance,
    float PostnormMeanAbsLlr);
