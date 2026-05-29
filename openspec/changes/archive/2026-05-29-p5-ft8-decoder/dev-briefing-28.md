# Developer Briefing — p5-ft8-decoder (Round 28)

**Date:** 2026-05-27  
**Issued by:** Developer  
**Branch:** `fix/d11-ldpc-convergence`  
**Scope:** D13 — Zero live decodes despite LDPC converged=3, CRC passed=3

---

## Summary

D13 identified and fixed: the decoder used the standard Gray code `G(n) = n ^ (n >> 1)`
instead of the FT8-specific `kFT8_Gray_map = {0, 1, 3, 2, 5, 6, 4, 7}` from kgoba/ft8_lib.
These agree for binary values 0–3 but diverge for 4–7.  For all live FT8 symbols with
b2=1 (~50% of data symbols), the b1 and b0 LLR groupings in `ComputeLlrs` had inverted
signs.  Initial parity failure count ≈ 39/83 (near random) → LDPC never converged.

Tests passed because the synthetic encoder and decoder both used the same wrong code.

---

## Evidence

**Diagnostic result before fix (live audio):**
```
Cycle 17:09:45: 0 decode(s) found.
[diag] Costas candidates=2492, LDPC converged=3, CRC passed=3.
```

The 3 LDPC convergences were all-zero codewords (caught by D2 guard).
No real FT8 signal ever converged.

**Root cause trace:**

The kgoba/ft8_lib `encode.c` uses:
```c
tones[i_tone] = kFT8_Gray_map[bits3];
// kFT8_Gray_map = { 0, 1, 3, 2, 5, 6, 4, 7 }
```

WSJT-X uses the same map (it is the FT8 standard).  Our encoder used:
```csharp
symbols[dataPos[di]] = binary ^ (binary >> 1); // standard Gray code — WRONG
```

Comparison for b2=1 symbols (binary 4–7):

| binary | G(n)=n^(n>>1) (ours) | kFT8_Gray_map (spec) |
|--------|----------------------|----------------------|
| 4      | 6                    | **5**                |
| 5      | 7                    | **6**                |
| 6      | 5                    | **4**                |
| 7      | 4                    | **7**                |

For a symbol transmitted as tone 5 (binary=4, b2=1, b1=0, b0=0):
- Old decoder b1 grouping: tone 5 in `{2,3,4,5}` → b1=1 **WRONG** (true b1=0)
- Old decoder b0 grouping: tone 5 in `{0,3,5,6}` → b0=0 (correct)

Similarly for binary 5, 6, 7: one of b1 or b0 is wrong.

**Expected initial parity failures with ~16.7% bit error rate (25% of b1/b0 bits):**
Each check equation has ≈ 7 bits.  P(check fails) ≈ 1 − (1 − 2×0.167)^7 ≈ 0.47.
Expected failures ≈ 0.47 × 83 ≈ 39/83.

---

## Fix

### 1. `TestFt8Encoder.BitsToSymbols` (test encoder)

```csharp
// Before:
symbols[dataPos[di]] = binary ^ (binary >> 1); // wrong

// After:
private static readonly int[] s_ft8GrayMap = { 0, 1, 3, 2, 5, 6, 4, 7 };
symbols[dataPos[di]] = s_ft8GrayMap[binary]; // kFT8_Gray_map (FT8 standard)
```

### 2. `Ft8Decoder.ComputeLlrs` (live decoder)

```csharp
// Before (based on G(n) inverse):
float b1_0 = LogSumExp(e0, e1, e6, e7);   // wrong: tones {0,1,6,7}
float b1_1 = LogSumExp(e2, e3, e4, e5);   // wrong: tones {2,3,4,5}
float b0_0 = LogSumExp(e0, e3, e5, e6);   // wrong: tones {0,3,5,6}
float b0_1 = LogSumExp(e1, e2, e4, e7);   // wrong: tones {1,2,4,7}

// After (based on kFT8_Gray_map inverse):
float b1_0 = LogSumExp(e0, e1, e5, e6);   // correct: tones {0,1,5,6}
float b1_1 = LogSumExp(e2, e3, e4, e7);   // correct: tones {2,3,4,7}
float b0_0 = LogSumExp(e0, e3, e4, e5);   // correct: tones {0,3,4,5}
float b0_1 = LogSumExp(e1, e2, e6, e7);   // correct: tones {1,2,6,7}
```

b2 grouping is unchanged (G(n) and kFT8_Gray_map agree for binary 0–3 and 4–7 in terms of b2).

### 3. `LdpcDecoderTests.GoertzelLlrs_SyntheticPcm_LdpcDecodesCorrectly`

Updated the inline LLR computation to use the correct kFT8_Gray_map groupings.

### 4. D13 parity-failure diagnostic (new)

Added `LdpcDecoder.CountInitialParityFailures(llr)` — counts how many of the 83 check
equations fail from hard-decided LLRs before any BP iterations.  Reported in the `[diag]`
line as `avg_initial_parity_fail=X.X/83`.

Before fix: expected ~39/83 per candidate (near-random bit assignments).  
After fix: expected ~0–5/83 for a signal at good SNR (clean symbol alignment).

---

## Test Results

| Metric | Before D13 fix | After D13 fix |
|--------|----------------|---------------|
| Tests passed | 50/50 | **50/50** |
| Full suite | 184/184 | **184/184** |
| Test duration | 1 m 38 s | 1 m 39 s |
| Live LDPC converged | 0 real signals | **TBD — live run required** |

---

## Commit

`fix/d11-ldpc-convergence` — commit `3b58021`:
```
fix(ft8): correct FT8 Gray code to kFT8_Gray_map — fix D13 zero live decodes
```

---

## Live Verification

Rebuild and run the daemon.  Expected `[diag]` on a busy band:

```
Cycle HH:MM:SS: N decode(s) found.
[diag] Costas candidates=2492, LDPC converged=M>0, CRC passed=N>0,
       avg_initial_parity_fail=X.X/83.
```

- `avg_initial_parity_fail` ≈ 0–5 for correctly decoded signals
- `avg_initial_parity_fail` ≈ 10–20 for weak/noisy signals that still converge
- `avg_initial_parity_fail` ≈ 39–42 would indicate ANOTHER systematic sign error

If `LDPC converged=0` still after this fix, record the `avg_initial_parity_fail` value
and open D14 with that diagnostic.

---

## Outstanding Items

### Costas false-alarm rate (non-blocking)

2492 Costas candidates for a 15-signal band is ~2.6% hit rate at each (freq, time) grid
point.  This produces 2492 Goertzel calls per cycle, estimated decode time ~2–5 s.
Within the 15-second budget, but could be reduced by raising `SyncThreshold` from 0.45
to 0.55–0.60 once live decodes are confirmed.

### Advisory A1 (QA Round 5) — may now be closed

`ComputeLlrs` is called with `freqShift: 0` after the 50 Hz outer step fix (D12).
The `(t + freqShift) % 8` wrapping concern is moot.  Can be formally closed after
live verification.

### Advisory A2 (QA Round 5) — pre-merge action

Revert `CycleFramer` "Window emitted" log from `LogInformation` to `LogDebug` before
archiving p5.

---

## Status

| Item | Status |
|------|--------|
| D10 — Costas O(minutes) on flat spectrum | ✅ Resolved |
| D11 — Zero decodes (hard Costas + full-symbol sweep) | ✅ Fixed |
| D12 — O(minutes) decode due to 8× Goertzel duplication | ✅ Fixed |
| **D13 — Zero live decodes (wrong Gray code)** | ✅ Fixed — awaiting live run |
| Live audio verification | ⏳ Pending rebuild + run |
