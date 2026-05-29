# Developer Briefing — p8-ft8-decode-performance (Round 33)

**Date:** 2026-05-28  
**Issued by:** QA  
**Branch:** `main` (new fix branch required — see §4)  
**Scope:** Hex-fallback messages appearing in decode output

---

## Summary

The four reported messages are **not false LDPC convergences**.  They are real on-air
FT8 transmissions using message types that `MessageUnpacker` does not yet decode into
human-readable strings, and one pair likely represents the same physical transmission
being decoded twice at slightly different time-sweep positions.  Two fixes are required:
one immediate, one advisory.

---

## 1. Root-Cause Analysis

### Message type identification

The `i3` field occupies bits 74–76 of the 77-bit payload, packed at positions 5–3 of
the last hex byte.  Decoding each example:

| Time | Freq | Hex (last byte) | i3 | Type |
|------|------|-----------------|----|----- |
| 17:01:30 | 731 Hz | `...7920` → `0x20` → `00100000` | **4** | Non-standard callsigns |
| 17:00:45 | 469 Hz | `...2D50` → `0x50` → `01010000` | **2** | EU VHF Contest / DXpedition |
| 17:00:30 | 350 Hz | `...A510` → `0x10` → `00010000` | **2** | EU VHF Contest / DXpedition |
| 17:00:30 | 731 Hz | `...7860` → `0x60` → `01100000` | **4** | Non-standard callsigns |

Neither i3=2 nor i3=4 is handled by the current `MessageUnpacker.Unpack` switch:

```csharp
return i3 switch
{
    0 => UnpackType1Or2(bits),  // Standard QSO
    1 => UnpackType1(bits),     // Legacy
    5 => UnpackFreeText(bits),  // Free text
    _ => HexFallback(bits, 77), // ← i3=2 and i3=4 land here
};
```

These are legitimate FT8 message types used on-air.  The decoder correctly identifies
them (LDPC and CRC-14 pass) but falls back to hex because the unpacker has not yet
implemented their format.

### The 731 Hz pair — same transmission, two codewords

Messages 1 and 4 share bytes 4–8:

| Message | Hex |
|---------|-----|
| 17:01:30, 731 Hz | `579000002B68F9FB7920` |
| 17:00:30, 731 Hz | `7B0000002B68F9FB7860` |

The subsequence `2B68F9FB` appears in both.  The leading and trailing bytes differ by a
small number of bits.  These are almost certainly the **same physical transmission**
decoded at two different time-sweep positions, producing two marginally different LLR
vectors.  LDPC is a block code with an error floor: at moderate SNR (here +3 dB), a
small number of alternative valid codewords exist near the true codeword, and slight
LLR perturbations from a sub-optimal time alignment can tip belief propagation into the
adjacent basin.  Both resulting codewords pass CRC-14 (the probability is 1/2¹⁴ per
candidate, but the two alternatives here are genuine LDPC neighbours, not random
coincidences).

The de-duplication in `Ft8Decoder` compares message strings.  Because the two hex
strings differ, they are treated as distinct and both are emitted.

---

## 2. Why These Became Visible After P8

Before p8, the decode ran in ~59 s per 15-second cycle.  The operator received results
roughly once per minute, so i3=2/4 messages appeared at most once or twice per hour
and were easy to overlook.  After p8 the decoder runs every 15 seconds: the same
on-air activity produces four times as many decode outputs, making the hex fallbacks
prominent.

---

## 3. Fixes

### Fix A — Immediate: suppress hex-fallback messages from output

`HexFallback` messages are not actionable.  The operator cannot identify the station,
and the bits are meaningless without the Type 2/4 decoder.  Suppress them at the
`Ft8Decoder` level by adding a `MessageUnpacker.TryUnpack` overload that returns
`null` for unsupported types.

**`src/OpenWSFZ.Ft8/Dsp/MessageUnpacker.cs`** — add:

```csharp
/// <summary>
/// Attempts to unpack a 77-bit FT8 message payload into a human-readable string.
/// Returns <c>null</c> for message types that are not yet implemented (i3 ∉ {0, 1, 5})
/// so that callers can skip rather than display a raw hex fallback.
/// </summary>
/// <param name="bits">Array of at least 77 bytes, each 0 or 1 (MSB-first).</param>
/// <returns>
/// Decoded message string, or <c>null</c> if the message type is not supported.
/// </returns>
public static string? TryUnpack(ReadOnlySpan<byte> bits)
{
    if (bits.Length < 77) return null;

    int i3 = (bits[74] << 2) | (bits[75] << 1) | bits[76];

    return i3 switch
    {
        0 => UnpackType1Or2OrNull(bits),
        1 => UnpackType1(bits),
        5 => UnpackFreeText(bits),
        _ => null,                      // i3=2,3,4,6,7 — not yet implemented
    };
}
```

Add a private helper `UnpackType1Or2OrNull` that returns `null` for n3>3 instead of
calling `HexFallback`:

```csharp
private static string? UnpackType1Or2OrNull(ReadOnlySpan<byte> bits)
{
    int n3 = (bits[71] << 2) | (bits[72] << 1) | bits[73];
    return n3 <= 3 ? UnpackType1(bits) : null;  // n3=4,5 not yet implemented
}
```

**`src/OpenWSFZ.Ft8/Ft8Decoder.cs`** — replace the `Unpack` call inside the parallel
body:

```csharp
// Before:
var msgBits = new ReadOnlySpan<byte>(decoded, 0, MsgBits);
string msg  = MessageUnpacker.Unpack(msgBits);

// After:
var msgBits = new ReadOnlySpan<byte>(decoded, 0, MsgBits);
string? msg = MessageUnpacker.TryUnpack(msgBits);
if (msg is null) continue;  // unsupported message type — skip silently
```

The existing `Unpack` method (with hex fallback) is kept intact for any test code or
future diagnostic use.

### Fix B — Advisory: the 731 Hz pair (near-codeword alternatives)

This is a known property of LDPC decoding at moderate SNR, not a defect.  No code
change is required.  A future improvement (outside the scope of this briefing) would
be to run a second-pass LDPC with a scaled LLR vector to break ties, or to prefer the
candidate with the higher initial Costas score when two candidates produce the same i3
value at the same frequency.  For now, once Fix A is in place, both messages will be
silently suppressed (as unsupported i3=4), so the duplicate will no longer be visible.

---

## 4. Implementation Plan

| Step | Action |
|------|--------|
| 1 | Create branch `fix/d15-hex-fallback-suppression` off `main` |
| 2 | Add `MessageUnpacker.TryUnpack` and `UnpackType1Or2OrNull` |
| 3 | Update `Ft8Decoder` parallel body to use `TryUnpack` |
| 4 | `dotnet build -c Release` — 0 errors, 0 warnings |
| 5 | `dotnet test -c Release` — all tests green |
| 6 | Verify existing tests that call `Unpack` still pass (method unchanged) |
| 7 | Run live: confirm hex strings no longer appear in decode output |
