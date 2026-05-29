# QA Review — `feat/p11-decoder-port`

**Reviewer:** QA  
**Date:** 2026-05-29  
**Branch:** `feat/p11-decoder-port`  
**Base:** `main`  
**Verdict:** ❌ **RETURN FOR CHANGES**

---

## Summary

Seven findings. Two are blockers that must be fixed before merge; two are defects that should be fixed in the same pass; three are cleanup items that may follow in a housekeeping commit.

| # | Severity | File | Line | Short description |
|---|---|---|---|---|
| 1 | 🔴 BLOCKER | `Ft8Decoder.cs` | 64 | `SyncThreshold = 0.1` is below the noise floor — floods LDPC on every real band frame |
| 2 | 🟠 DEFECT | `MessageUnpacker.cs` | 264 | `IsValidExtra15` grid branch is a tautology — never filters anything |
| 3 | 🟠 DEFECT | `MessageUnpacker.cs` | 263 | SNR ceiling at val ≤ 60 silently drops valid +26 to +49 dB reports |
| 4 | 🟠 DEFECT | `MessageUnpacker.cs` | 195 | `DecodeReport15` R-prefix branch (`val >= 32400`) is unreachable dead code |
| 5 | 🟡 CLEANUP | `MessageUnpacker.cs` | 230 | `IsValidCallsign28` is dead code using the wrong (base-37) algorithm |
| 6 | 🟡 CLEANUP | `Ft8Decoder.cs` | 71 | `LlrClamp = 1.5f` defined but never applied; contradicted in-place |
| 7 | 🟡 CLEANUP | `Ft8Decoder.cs` | 18 | Class XML doc step 3 names Goertzel; actual code uses `ExtractFromSpectrogram` |

---

## Finding 1 — 🔴 BLOCKER

**`SyncThreshold = 0.1f` is below the documented uniform-noise floor of 0.125**  
`src/OpenWSFZ.Ft8/Ft8Decoder.cs` line 64

### What is wrong

The softmax Costas formula produces a normalised score of exactly **0.125** per position for uniform noise (each of the 21 Costas symbols contributes `exp(E) / (8 × exp(E)) = 1/8`; dividing the total by `maxPossible = 21` gives `21 × 0.125 / 21 = 0.125`).

`SyncThreshold = 0.1f` sits *below* this floor. On any real 40 m band frame where DFT bin energies exceed the `maxE < −18` silent-band guard — which is the normal state for recorded band audio — every one of the 8 `freqShift` values passes `FindCandidates` at every `baseHz` step. With `MaxCandidatesPerSweep = 8` also at its maximum, the worst-case load is:

```
59 baseHz steps × 8 candidates × 102 startSample positions ≈ 48 000 LDPC runs
```

…on noise, per 15-second cycle. The decode will never complete within budget.

The `CostasSynchroniser` doc-comment at line 41 states explicitly:

> *"The threshold of 0.45 is appropriate for the softmax formula."*

The value 0.45 was chosen because it is above 0.125 (noise) and below 0.33 (two equal-power interferers). Crowded-band signals with three equal interferers (score ≈ 0.33) need a threshold lower than 0.33. If the intent was to catch these, a value in the range **0.15–0.25** would sit above the noise floor while still being more permissive than 0.45. The choice of 0.1 appears to be an over-correction.

### How to fix

Raise `SyncThreshold` to a value **strictly above 0.125**. A value of **0.20** is a reasonable starting point:

```csharp
// Crowded-band threshold (above uniform-noise floor of 0.125; below 0.33 = 3 equal interferers).
private const float SyncThreshold = 0.20f;
```

Update the comment to document the noise-floor arithmetic so the constraint is preserved in future tuning.

---

## Finding 2 — 🟠 DEFECT

**`IsValidExtra15` grid-square guard is a tautology — it never rejects anything**  
`src/OpenWSFZ.Ft8/Dsp/MessageUnpacker.cs` line 264

### What is wrong

```csharp
private static bool IsValidExtra15(ulong packed)
{
    bool isReport = (packed & 0x4000UL) != 0;
    ulong val     = packed & 0x3FFFUL;   // ← 14-bit mask: max value = 16 383

    return isReport
        ? val >= 1 && val <= 60
        : val < 32_724;                  // ← 16383 < 32724 is ALWAYS true
}
```

`0x3FFF` = 16 383. Since 16 383 < 32 724 unconditionally, the non-report branch can never return `false`. Every bit-pattern with `isReport = false` passes the filter regardless of value. The comment claims the guard enforces the standard-grid ceiling (32 400) plus the R-prefix contest range (up to 32 723), but it provides no filtering at all.

As a secondary consequence, the R-prefix branch in `DecodeReport15` (Finding 4) is also dead for the same reason.

### How to fix

The maximum valid value for a standard 4-character Maidenhead grid is `18 × 18 × 10 × 10 − 1 = 32 399`. The R-prefix contest range adds a further 32 400 values (R0000–R32399), but since these are also unreachable after the 14-bit mask (see Finding 4), the practical upper bound for currently-decodeable grids is **32 399**, which itself exceeds the 14-bit maximum of 16 383. A useful guard must operate on the 14-bit value and catch encodings that have no valid grid interpretation:

```csharp
// Grid squares: standard 4-char Maidenhead uses val 0–32399.
// With the 14-bit mask, val is at most 16383 — all values are within
// the standard range. No filtering possible until the 15-bit mask
// ambiguity is resolved (see issue tracker).
: true;
```

Or, if the intent is to reject values that decode as clearly impossible grids (e.g., `r1 ≥ 18` or `r2 ≥ 18`), validate the decoded sub-fields instead:

```csharp
: (val / 1800) < 18 && ((val % 1800) / 100) < 18;
```

At a minimum, replace the misleading `val < 32_724` with a comment explaining why no useful bound can be applied after the 14-bit mask.

---

## Finding 3 — 🟠 DEFECT

**`IsValidExtra15` SNR ceiling at val ≤ 60 silently drops valid strong-signal reports**  
`src/OpenWSFZ.Ft8/Dsp/MessageUnpacker.cs` line 263

### What is wrong

The filter rejects `val > 60`, corresponding to SNR > +25 dB. However, `DecodeReport15` line 208 carries the comment:

```csharp
int snr = (int)val - 35; // range -35 to +49
```

This acknowledges that val values up to 84 (+49 dB) are spec-valid. A station 1–2 km away on 40 m with a gain antenna can easily produce SNR readings of +30 dB or more. Such a signal (val = 65) would pass CRC-14 and LDPC, reach `TryUnpack`, and be silently discarded.

The p10 corpus observation — that all false positives had val > 60 — does **not** imply that all val > 60 reports are false positives. It only means the corpus contained no legitimate strong-signal reports.

### How to fix

Align the ceiling with the spec. The FT8 encoding allows SNR val 4–84 (−31 to +49 dB) plus the three special values (1 = RRR, 2 = RR73, 3 = 73):

```csharp
? val >= 1 && val <= 84   // RRR/RR73/73 and SNR −31 to +49 dB per spec
```

If the false-positive suppression was genuinely relying on `val <= 60` for the p10 corpus, that behaviour indicates a deeper problem in the LDPC/CRC pipeline that should be investigated separately rather than papered over with an artificially low ceiling here.

---

## Finding 4 — 🟠 DEFECT

**`DecodeReport15` R-prefix contest branch is unreachable dead code**  
`src/OpenWSFZ.Ft8/Dsp/MessageUnpacker.cs` line 195

### What is wrong

```csharp
private static string DecodeReport15(ulong packed)
{
    ulong val = packed & 0x3FFFUL;  // max = 16 383

    if (!isReport)
    {
        if (val >= 32400) return $"R{val - 32400}";  // ← unreachable: 16383 < 32400
        ...
    }
}
```

`val` is a 14-bit value (max 16 383). The condition `val >= 32400` can never be true. Any FT8 message whose rg field encodes an R-prefix contest serial number is silently mis-decoded as a standard grid square. For example, val = 32401 (R0001) arrives as `packed = 32401`; after masking, `val = 32401 & 0x3FFF = 17` → decoded as grid square `"AA17"`.

This is consistent with Finding 2: both `IsValidExtra15` and `DecodeReport15` use the same 14-bit mask, making the R-prefix range mutually unreachable in both functions.

### How to fix

The root cause is that `ReadBits` correctly reads 15 bits, but `DecodeReport15` masks to 14 bits with `0x3FFFUL` instead of passing the full 15-bit value. The fix is to pass the unmasked `rg` value:

```csharp
bool isReport = (packed & 0x4000UL) != 0;  // bit 14 is the report flag
ulong val     = packed & 0x3FFFUL;          // bits 0–13
```

The issue here is that `packed` already *is* the 15-bit value. Bit 14 is correctly extracted as `isReport`. `val` must be `packed & 0x3FFFUL` for standard numeric decoding — the R-prefix interpretation depends on reading `val` relative to a combined 15-bit value. The actual problem is that 32400–32399+N contest values require **more than 14 bits** to represent directly; they require 15 bits. The current mask discards that information.

In the short term: document the limitation — R-prefix contest messages are not supported by this decoder. Remove the dead branch and add a comment.

In the long term: rework `DecodeReport15` to accept the full 15-bit `packed` value (not post-masked `val`) and handle the R-prefix range correctly.

---

## Finding 5 — 🟡 CLEANUP

**`IsValidCallsign28` is dead code using the old base-37 algorithm**  
`src/OpenWSFZ.Ft8/Dsp/MessageUnpacker.cs` line 230

### What is wrong

The function is private and never called from any production path. It also uses a pure base-37 decode (dividing by 37 at all six positions), while the actual `DecodeCallsign28` now uses mixed-radix (base-27 for positions 3–5, base-10 for position 2, base-37 for positions 0–1). For packed = 4134219 (K0ABC under mixed-radix), `IsValidCallsign28` decodes position 2 as `'6'` rather than `'0'` — the function would return incorrect results for virtually every callsign if it were ever connected.

### How to fix

Delete the method entirely. The test comment already documents why it is not called. Leaving dead code with a subtle algorithmic error is a trap for future maintenance.

---

## Finding 6 — 🟡 CLEANUP

**`LlrClamp = 1.5f` is defined but never applied; contradicted in-place**  
`src/OpenWSFZ.Ft8/Ft8Decoder.cs` line 71

### What is wrong

```csharp
// LLR clamp applied before LDPC.  Strong adjacent-channel interference can
// produce LLRs of ±7–8 with the wrong sign, completely overwhelming the 6
// neighbour-contributions (~6 × 0.3 = 1.8) that LDPC needs to flip the bit.
// Clamping to ±1.5 reduces wrong LLRs …
private const float LlrClamp = 1.5f;

// ... 20 lines later, after ComputeLlrs:
// No LLR clamping — strong-signal LLRs (~8-9) must dominate over
// interference (~2-3) so LDPC converges to the correct codeword.
```

The constant and its rationale comment directly contradict the usage-site comment. A developer who encounters `LlrClamp` and trusts its documentation could add `MathF.Clamp(llr[i], -LlrClamp, LlrClamp)` — inadvertently clipping strong-signal LLRs from ≈8 down to ±1.5 and causing LDPC to diverge on high-SNR signals.

### How to fix

Remove `LlrClamp` and its rationale comment block entirely. Leave only the usage-site comment explaining why clamping is *not* applied:

```csharp
// No LLR clamping: strong-signal LLRs (≈8–9) must dominate weak-interference LLRs
// (≈2–3) so LDPC converges to the correct codeword rather than an interference codeword.
```

---

## Finding 7 — 🟡 CLEANUP

**Class XML doc step 3 names Goertzel; actual code calls `ExtractFromSpectrogram`**  
`src/OpenWSFZ.Ft8/Ft8Decoder.cs` line 18

### What is wrong

The pipeline summary reads:

> *3. For each Costas candidate, recompute the 79 × 15 grid via Goertzel (`SymbolExtractor.Extract`) at the exact tone frequencies.*

`SymbolExtractor.Extract` is never called anywhere in `DecodeAsync`. Both the Costas detection grid (line 164) and the per-candidate LLR grid (line 187) are produced by `ExtractFromSpectrogram`. The pipeline title also still contains the word "Goertzel".

### How to fix

Update the XML doc to reflect the actual pipeline:

```csharp
/// Pipeline per cycle (exact-DFT spectrogram):
///   1. For each symbol-aligned time offset, compute a 79 × 960 exact-DFT spectrogram
///      once via <see cref="SymbolExtractor.FillSpectrogramExact"/>.
///   2. Sweep candidate base frequencies (50–3000 Hz, steps of 50 Hz).
///      Extract a 79 × 15 log-energy grid via <see cref="SymbolExtractor.ExtractFromSpectrogram"/>
///      and run <see cref="CostasSynchroniser.FindCandidates"/> to find Costas sync hits.
///   3. For each Costas candidate, re-extract the 79 × 15 grid from the same spectrogram
///      at the exact candidate base frequency, derive 174 soft LLRs, run LDPC, verify CRC,
///      and unpack the message.
///   4. De-duplicate; return the unique set as <see cref="DecodeResult"/> records.
```

---

## Required actions before re-review

| Priority | Action |
|---|---|
| **Must fix** | Finding 1 — raise `SyncThreshold` above 0.125 |
| **Must fix** | Finding 2 — correct or remove the tautological grid bound in `IsValidExtra15` |
| **Must fix** | Finding 3 — raise the SNR ceiling to val ≤ 84 |
| **Must fix** | Finding 4 — document (or fix) the R-prefix dead branch in `DecodeReport15` |
| Recommended | Finding 5 — delete `IsValidCallsign28` |
| Recommended | Finding 6 — delete `LlrClamp` constant and contradicting comment |
| Recommended | Finding 7 — update pipeline XML doc |

Once the four mandatory items are addressed, please re-submit for review.
