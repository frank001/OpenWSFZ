# Developer Briefing — p5-ft8-decoder (Round 29)

**Date:** 2026-05-27  
**Issued by:** Developer  
**Branch:** `fix/d11-ldpc-convergence`  
**Scope:** D14 — CRC passes 0 despite LDPC converging for real FT8 signals

---

## Summary

D14 identified and fixed: the FT8 CRC-14 is computed over **82 bits** (77 message bits + 5
implicit zero-padding bits), not 77 bits.  Our decoder called `Crc14.Verify(decoded, 91)`,
which computed the CRC over only 77 bits and compared with the stored 14-bit CRC that
WSJT-X had computed over 82 bits.  The values never matched, so `CRC passed=0` on every
live on-air signal even after LDPC converged correctly.

---

## Evidence

**Pre-fix diagnostic (kFT8_Gray_map groupings, live audio):**
```
Cycle 21:20:45: 0 decode(s) found.
[diag] Costas candidates=3128, LDPC converged=24, CRC passed=0, avg_initial_parity_fail=41.2/83.
```

24 LDPC convergences, 0 CRC passes — systematic failure at the CRC stage.

**Post-fix diagnostic (same D-13 kFT8_Gray_map groupings + D14 CRC fix):**
```
Cycle 21:22:00: 13 decode(s) found.
[diag] Costas candidates=3124, LDPC converged=24, CRC passed=24, avg_initial_parity_fail=41.2/83.

Cycle 21:22:15: 16 decode(s) found.
[diag] Costas candidates=2432, LDPC converged=28, CRC passed=28, avg_initial_parity_fail=41.3/83.
```

All 24/28 LDPC convergences now pass CRC.  13 and 16 unique messages decoded per cycle.

---

## Root Cause

### kgoba/ft8_lib `crc.c` reference

```c
void ftx_add_crc(const uint8_t payload[], uint8_t a91[])
{
    // Zero bits 77–79 (lower 3 bits of a91[9]) and bits 80–87 (a91[10]).
    a91[9] &= 0xF8u;
    a91[10] = 0;

    // CRC computed over 82 bits: 77 message bits + 5 zero-padding bits.
    uint16_t checksum = ftx_compute_crc(a91, 96 - 14);  // = 82

    // Store 14-bit CRC MSB-first at bits [77..90].
    a91[9] |= (uint8_t)(checksum >> 11);
    a91[10] = (uint8_t)(checksum >> 3);
    a91[11] = (uint8_t)(checksum << 5);
}
```

The 91-bit FT8 information block layout is:
- bits [0..76]  — 77 message bits
- bits [77..90] — 14 CRC bits (computed over 77 msg + 5 zero padding = 82 bits)

Our previous call `Crc14.Verify(decoded, 91)` computed `messageBits = 91 − 14 = 77` and
ran CRC over only 77 bits, giving a different value from the stored CRC.

---

## Fix

### 1. `Crc14.VerifyFt8` (new method)

```csharp
public static bool VerifyFt8(ReadOnlySpan<byte> bits91)
{
    if (bits91.Length < 91) return false;

    // 82-bit input: 77 message bits + 5 zero-padding bits.
    Span<byte> buf = stackalloc byte[82]; // zero-initialised
    bits91[..77].CopyTo(buf);

    uint expected = Compute(buf, 82);

    uint stored = 0u;
    for (int i = 0; i < 14; i++)
        stored = (stored << 1) | (bits91[77 + i] & 1u);

    return expected == stored;
}
```

### 2. `Ft8Decoder.DecodeAsync` — swap CRC call

```csharp
// Before (always fails for live signals):
bool crcOk = Crc14.Verify(decoded, 91);

// After:
bool crcOk = Crc14.VerifyFt8(decoded);
```

### 3. `TestFt8Encoder.AppendCrc14` — generate 82-bit CRC in test encoder

```csharp
// Before: Crc14.Compute(info, 77)
// After:
var crcBuf = new byte[82]; // zero-initialised
Array.Copy(msgBits, crcBuf, 77);
uint crc = Crc14.Compute(crcBuf, 82);
```

### 4. `LdpcDecoderTests` — updated two CRC calls to `Crc14.VerifyFt8`

---

## Note on avg_initial_parity_fail

The `avg_initial_parity_fail=41.2/83` figure looks alarming but is benign.  It is the
**mean over all 3128 Costas candidates**, the vast majority of which are noise false-alarms
whose random LLRs yield ~41.5/83 parity failures.  The 24 real signals each have ≈0–5/83
failures; their contribution is invisible in the average.  The metric is still useful as an
early-warning for systematic LLR sign errors (it would climb sharply if the Gray-code groupings
were wrong for every candidate, not just false-alarms).

---

## Test Results

| Metric | After D14 fix |
|--------|---------------|
| Tests passed | **184/184** |
| Live LDPC converged | 24–28 per cycle |
| Live CRC passed | **24–28 per cycle** (was 0) |
| Live decoded messages | **13–16 per cycle** |

---

## Commit

`fix/d11-ldpc-convergence` — commit `bb453dd`:
```
fix(ft8): correct CRC to 82-bit FT8 standard — live decodes confirmed (D14)
```

---

## Status

| Item | Status |
|------|--------|
| D10 — Costas O(minutes) on flat spectrum | ✅ Resolved |
| D11 — Zero decodes (hard Costas + full-symbol sweep) | ✅ Fixed |
| D12 — O(minutes) decode due to 8× Goertzel duplication | ✅ Fixed |
| D13 — Correct Gray code (kFT8_Gray_map) | ✅ Fixed |
| **D14 — CRC over 82 bits (77 msg + 5 zero padding)** | ✅ Fixed — live confirmed |
| Advisory A1 — freqShift % 8 wrapping | ✅ Closed (freqShift=0 always) |
| Advisory A2 — CycleFramer "Window emitted" → LogDebug | ✅ Already LogDebug |
| **Live audio verification** | ✅ 13–16 decodes/cycle confirmed |
| **p5 ready to merge** | ✅ All defects resolved |
