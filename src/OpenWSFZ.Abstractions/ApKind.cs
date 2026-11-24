namespace OpenWSFZ.Abstractions;

/// <summary>
/// CQ-AP: the a-priori provenance of a decode. The numeric values are the native shim's <c>ft8_get_last_ap_kinds</c> codes
/// (<c>FT8_AP_KIND_NONE</c> / <c>FT8_AP_KIND_CQ</c>) and the replay harness's column; do not renumber.
/// </summary>
public enum ApKind
{
    /// <summary>An ordinary decode (the normal attempt, the coherent fallback, or any decode with <c>cqApEnabled</c> off).</summary>
    None = 0,

    /// <summary>Decoded by the CQ a-priori attempt: payload bits 0-28 and 74-76 forced to the encoding of <c>CQ</c>, BP only.</summary>
    Cq = 1,
}
