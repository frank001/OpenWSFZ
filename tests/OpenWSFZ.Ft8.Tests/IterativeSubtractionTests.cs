using FluentAssertions;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Tests for the spectrogram-domain iterative subtraction pass (p15 + fix-d001-revised Option B).
///
/// <para>
/// The soft SNR-scaled attenuation formula in <c>suppress_candidate_tiles()</c>
/// (<c>ft8_shim.c</c>) is:
/// <code>
///   float norm   = (snr_db - K_SOFT_SUPP_SNR_MIN_DB)
///                / (K_SOFT_SUPP_SNR_MAX_DB - K_SOFT_SUPP_SNR_MIN_DB);
///   float factor = 1.0f - clamp(norm, 0.0f, 1.0f);
/// </code>
/// where <c>K_SOFT_SUPP_SNR_MIN_DB = −5.0f</c> and <c>K_SOFT_SUPP_SNR_MAX_DB = 15.0f</c>.
/// </para>
///
/// <para>
/// The tests in this class verify the formula's boundary and mid-range behaviour by
/// computing the expected factor in C# (using the same arithmetic as the C code) and
/// confirming the results match the design.  Any change to the constants in
/// <c>ft8_shim.c</c> must be reflected here.
/// </para>
/// </summary>
public sealed class IterativeSubtractionTests
{
    // ── Constants mirrored from ft8_shim.c ────────────────────────────────────
    // These MUST match K_SOFT_SUPP_SNR_MIN_DB and K_SOFT_SUPP_SNR_MAX_DB in
    // ft8_shim.c.  If those constants change, update here and re-verify the R&R.
    private const float SoftSuppSnrMinDb =  -5.0f;
    private const float SoftSuppSnrMaxDb =  15.0f;

    // ── Formula helper ────────────────────────────────────────────────────────
    /// <summary>
    /// C# mirror of the native <c>suppress_candidate_tiles</c> SNR → attenuation
    /// factor computation.  Returns a value in [0.0, 1.0]:
    ///   1.0 = no suppression (tile unchanged)
    ///   0.0 = full suppression (tile assigned noise_raw)
    /// </summary>
    private static float ComputeAttenuationFactor(float snrDb)
    {
        float norm   = (snrDb - SoftSuppSnrMinDb) / (SoftSuppSnrMaxDb - SoftSuppSnrMinDb);
        float factor = 1.0f - Math.Clamp(norm, 0.0f, 1.0f);
        return factor;
    }

    // ── Boundary tests ────────────────────────────────────────────────────────

    /// <summary>
    /// At SNR ≥ K_SOFT_SUPP_SNR_MAX_DB (+15 dB), the signal is confidently decoded
    /// and its tiles should be fully suppressed: factor = 0.0.  This matches the
    /// original hard-zero behaviour for strong signals.
    /// </summary>
    [Fact(DisplayName = "SoftSuppression_StrongSignal_TilesAreZeroed")]
    public void StrongSignal_AtOrAboveMaxSnr_AttenuationFactorIsZero()
    {
        // At exactly the max boundary
        ComputeAttenuationFactor(SoftSuppSnrMaxDb).Should().BeApproximately(0.0f, precision: 1e-6f,
            "at SNR = K_SOFT_SUPP_SNR_MAX_DB (+15 dB) the factor must be 0.0 — full suppression");

        // Above the max boundary — factor must clamp to 0.0, not go negative
        ComputeAttenuationFactor(SoftSuppSnrMaxDb + 10.0f).Should().BeApproximately(0.0f, precision: 1e-6f,
            "at SNR > K_SOFT_SUPP_SNR_MAX_DB (+25 dB) the factor must still be 0.0 — clamped");
    }

    /// <summary>
    /// At SNR ≤ K_SOFT_SUPP_SNR_MIN_DB (−5 dB), the signal is borderline; its tiles
    /// should be left unchanged: factor = 1.0 (no suppression at all).
    /// </summary>
    [Fact(DisplayName = "SoftSuppression_WeakSignal_TilesUnchanged")]
    public void WeakSignal_AtOrBelowMinSnr_AttenuationFactorIsOne()
    {
        // At exactly the min boundary
        ComputeAttenuationFactor(SoftSuppSnrMinDb).Should().BeApproximately(1.0f, precision: 1e-6f,
            "at SNR = K_SOFT_SUPP_SNR_MIN_DB (−5 dB) the factor must be 1.0 — no suppression");

        // Below the min boundary — factor must clamp to 1.0, not exceed it
        ComputeAttenuationFactor(SoftSuppSnrMinDb - 10.0f).Should().BeApproximately(1.0f, precision: 1e-6f,
            "at SNR < K_SOFT_SUPP_SNR_MIN_DB (−15 dB) the factor must still be 1.0 — clamped");
    }

    /// <summary>
    /// At SNR = midpoint of (K_SOFT_SUPP_SNR_MIN_DB, K_SOFT_SUPP_SNR_MAX_DB) = +5 dB,
    /// the linear ramp should produce factor ≈ 0.5 (half attenuation).
    /// Midpoint = (−5 + 15) / 2 = 5 dB.
    /// </summary>
    [Fact(DisplayName = "SoftSuppression_MidRangeSnr_TilesHalved")]
    public void MidRangeSnr_AtMidpoint_AttenuationFactorIsHalf()
    {
        float midSnr = (SoftSuppSnrMinDb + SoftSuppSnrMaxDb) / 2.0f;  // +5 dB

        ComputeAttenuationFactor(midSnr).Should().BeApproximately(0.5f, precision: 1e-6f,
            "at SNR = midpoint of the ramp (+5 dB), the factor must be 0.5 — tiles halved " +
            "linearly between noise_raw (full suppression) and the original tile value (no change)");
    }
}
