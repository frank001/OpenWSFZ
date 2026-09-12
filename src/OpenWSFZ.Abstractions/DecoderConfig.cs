using System.Text.Json.Serialization;

namespace OpenWSFZ.Abstractions;

/// <summary>
/// Runtime-configurable OSD gate parameters for the FT8 decode pipeline
/// (decoder-settings-page, shim 20260030).
///
/// <para>
/// <see cref="KMinScorePass2"/> and <see cref="OsdCorrThreshold"/> default to the D-009
/// R&amp;R study calibrated values; <see cref="OsdNhardMax"/> defaults to the
/// <c>NHARD40-DEFAULT</c> arm's calibrated value (2026-09-12, see its own doc comment).
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
        int   kMinScorePass2           = 10,
        float osdCorrThreshold         = 0.10f,
        int   osdNhardMax              = 40,
        bool  nhard40MigrationApplied  = false)
    {
        KMinScorePass2          = kMinScorePass2;
        OsdCorrThreshold        = osdCorrThreshold;
        OsdNhardMax             = osdNhardMax;
        Nhard40MigrationApplied = nhard40MigrationApplied;
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
    /// <para>
    /// Default: 40 (<c>NHARD40-DEFAULT</c> arm, 2026-09-12: 60→40 removes 95–98% of false
    /// decodes with zero measured genuine loss on AWGN near-threshold/co-channel; native
    /// default unchanged, see below). No genuine loss detected, at 60 → 40, in isolated
    /// near-threshold or S7 co-channel conditions on AWGN; 95–98% fewer false decodes.
    /// Fading, drift, Doppler, timing spread (E4) and any live corroborated-loss floor
    /// remain untested/unbounded — never cite this default as "safe".
    /// </para>
    /// <para>
    /// The old "60 (D-009 calibrated: S5/S7 histogram operating point)" framing is
    /// retired: the <c>NHARD40-DEFAULT</c> <c>CC</c> leg's R6 finding established that the
    /// 2026-06-20 S7 "genuine" OSD population this calibration rested on was false accepts,
    /// not genuine decodes (native <c>decode.c:41</c> still carries the now-known-false
    /// claim — flagged to the Architect separately, not fixed by this change).
    /// </para>
    /// <para>
    /// <b>Deliberate C#/native divergence:</b> the native <c>ft8_shim.c</c> binary's own
    /// compiled-in <c>decode.c:41</c> default stays 60 — this managed default is what the
    /// daemon actually passes to <c>SetDecodeParams</c> at startup, so the shim's
    /// compiled-in default and the daemon's effective default are now different numbers
    /// on purpose. A future native-side change to match is a separate, native-rebuild-gated
    /// task, not this one.
    /// </para>
    /// </summary>
    public int   OsdNhardMax      { get; init; } = 40;

    /// <summary>
    /// One-time migration marker (M2, <c>NHARD40-DEFAULT</c>, 2026-09-12): set to
    /// <c>true</c> the first time <see cref="OsdNhardMax"/>'s persisted value of exactly
    /// <c>60</c> is migrated to the new code default of <c>40</c> by
    /// <c>JsonConfigStore.Load()</c>, so that an operator who deliberately restores
    /// <c>60</c> afterwards is not silently re-migrated back to <c>40</c> on a later
    /// restart.
    /// <para>
    /// <b>Server-owned — no request body may ever set or clear this field.</b>
    /// <c>POST /api/v1/config</c> full-replaces <see cref="OpenWSFZ.Abstractions.AppConfig"/>
    /// and <c>web/js/settings.js</c> only ever sends the other three decoder fields, never
    /// this marker; the handler carries it forward from the already-persisted config
    /// regardless of what (if anything) the request body's <c>decoder</c> object contains.
    /// Only <c>JsonConfigStore.Load()</c>'s own migration logic may flip it to <c>true</c>.
    /// </para>
    /// </summary>
    public bool  Nhard40MigrationApplied { get; init; } = false;
}
