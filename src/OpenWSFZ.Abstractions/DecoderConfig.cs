using System.Text.Json.Serialization;

namespace OpenWSFZ.Abstractions;

/// <summary>
/// Runtime-configurable OSD gate parameters for the FT8 decode pipeline
/// (decoder-settings-page, shim 20260030).
///
/// <para>
/// All three fields default to the D-009 R&amp;R study calibrated values.
/// A null <see cref="AppConfig.Decoder"/> is treated by all consumers as equivalent
/// to <c>new DecoderConfig()</c>, preserving the calibrated operating point for
/// existing config files that predate this feature.
/// </para>
/// </summary>
public sealed record DecoderConfig
{
    // ── Deserialization note (Lesson 6 / D-WFC-001 pattern) ─────────────────────
    //
    // STJ source-generation initialises value-type fields from JSON using CLR defaults
    // (int → 0, float → 0.0f) for fields absent from the JSON object.  Since these
    // fields have non-zero defaults (10, 0.10f, 60), a [JsonConstructor] with matching
    // parameter defaults is required so that a partial or empty JSON decoder object
    // deserialises to the calibrated values rather than zero-values.
    // ─────────────────────────────────────────────────────────────────────────────

    /// <summary>
    /// Deserialization constructor used by the STJ source-generated context.
    /// Parameter defaults ensure fields absent from older config files load with
    /// calibrated values rather than CLR zero-defaults (Lesson 6 / D-WFC-001 pattern).
    /// </summary>
    [JsonConstructor]
    public DecoderConfig(
        int   kMinScorePass2    = 10,
        float osdCorrThreshold  = 0.10f,
        int   osdNhardMax       = 60)
    {
        KMinScorePass2   = kMinScorePass2;
        OsdCorrThreshold = osdCorrThreshold;
        OsdNhardMax      = osdNhardMax;
    }

    /// <summary>
    /// Pass-1 candidate score floor.
    /// Controls how many pass-1 candidates are admitted to LDPC/OSD.
    /// Lower values increase sensitivity (more co-channel decode attempts) at the cost
    /// of more false positives.  Valid API range: [5, 30].
    /// Default: 10 (D-009 calibrated: S5 FP −94%, S7 co-channel sweep 86.67%).
    /// </summary>
    public int   KMinScorePass2   { get; init; } = 10;

    /// <summary>
    /// OSD normalised correlation gate.
    /// Candidates whose normalised inner-product score (corr/norm) is below this
    /// threshold are rejected as likely noise CRC-14 coincidences.
    /// Valid API range: [0.05, 0.40].
    /// Default: 0.10f (D-009 calibrated: R5 two-feature gate operating point).
    /// </summary>
    public float OsdCorrThreshold { get; init; } = 0.10f;

    /// <summary>
    /// OSD maximum Hamming-distance gate.
    /// Candidates with more hard-decision bit errors than this value are rejected.
    /// Genuine decodes cluster low; noise CRC-14 coincidences cluster near 87 (= 174/2).
    /// Valid API range: [30, 100].
    /// Default: 60 (D-009 calibrated: S5/S7 histogram operating point).
    /// </summary>
    public int   OsdNhardMax      { get; init; } = 60;
}
