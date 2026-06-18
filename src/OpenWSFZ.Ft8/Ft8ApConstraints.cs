namespace OpenWSFZ.Ft8;

/// <summary>
/// AP decode constraints for a directed FT8 decode (H6, D-001).
/// Packed bit arrays for mycall and hiscall, injected as hard LLR
/// constraints (±40.0) into the pass-0 LDPC input via ft8_set_ap_bits().
/// </summary>
/// <param name="MycallBits">
///   28-bit packed mycall, MSB-first, 4 bytes. Produced by
///   <see cref="Ft8CallsignPacker.Pack28"/>. Empty array disables the mycall constraint.
/// </param>
/// <param name="HiscallBits">
///   28-bit packed hiscall, MSB-first, 4 bytes.
/// </param>
public sealed record Ft8ApConstraints(byte[] MycallBits, byte[] HiscallBits);
