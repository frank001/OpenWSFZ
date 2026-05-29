# Developer Remediation — `feat/p11-decoder-port`

**Issued by:** QA Engineer  
**Date:** 2026-05-29  
**QA review document:** `QA-REVIEW-p11-decoder-port.md`  
**Branch:** `feat/p11-decoder-port`  
**Verdict:** ❌ RETURN FOR CHANGES — address all four mandatory items then re-submit

---

## Summary of required changes

| # | Severity | File | Change required |
|---|---|---|---|
| 1 | 🔴 BLOCKER | `Ft8Decoder.cs` | Raise `SyncThreshold` above the 0.125 noise floor |
| 2 | 🔴 BLOCKER | `MessageUnpacker.cs` | Fix the tautological grid bound in `IsValidExtra15` |
| 3 | 🟠 DEFECT | `MessageUnpacker.cs` | Raise SNR ceiling from `val ≤ 60` to `val ≤ 84` |
| 4 | 🟠 DEFECT | `MessageUnpacker.cs` | Remove or document the unreachable R-prefix branch in `DecodeReport15` |
| 5 | 🟡 CLEANUP | `MessageUnpacker.cs` | Delete dead method `IsValidCallsign28` |
| 6 | 🟡 CLEANUP | `Ft8Decoder.cs` | Delete unused constant `LlrClamp` and its contradicting comment block |
| 7 | 🟡 CLEANUP | `Ft8Decoder.cs` | Update pipeline XML doc (step 3 still names Goertzel) |

Findings 1–4 must be fixed before re-review. Findings 5–7 are strongly recommended in the same commit pass.

---

## Fix 1 — 🔴 Raise `SyncThreshold` above the noise floor

**File:** `src/OpenWSFZ.Ft8/Ft8Decoder.cs`  
**Line:** 64

### Why this is a blocker

The softmax Costas formula (D18, added to `CostasSynchroniser`) produces a score of exactly **0.125** for uniform noise — eight equal-energy tones give each symbol `exp(E) / (8 × exp(E)) = 1/8`, summed and normalised across 21 Costas positions.

`SyncThreshold = 0.1f` sits *below* this floor. On any real 40 m band frame (i.e. any audio that is not digital silence), every `freqShift` at every `baseHz` step passes `FindCandidates`. With `MaxCandidatesPerSweep = 8` also at its maximum:

```
59 baseHz steps × 8 candidates × 102 startSample positions ≈ 48 000 LDPC runs per cycle
```

This is the direct cause of the three failing G6 gate tests. The decode budget is exhausted on noise; the real target signals have no meaningful priority.

### What to change

```csharp
// Before (line 64):
private const float  SyncThreshold = 0.1f;

// After:
// Softmax Costas threshold.
// Uniform noise score = 0.125 (each of 8 tones contributes 1/8 per position).
// 0.20 sits above the noise floor and below 0.33 (3 equal-power interferers),
// which is the minimum meaningful signal-to-noise discrimination point.
private const float  SyncThreshold = 0.20f;
```

Also tidy the duplicate comment block at lines 55–64. The sentence *"The CRC-14 gate provides the final false-positive suppression"* appears twice. Remove the first occurrence (lines 55–59); keep only the single comment that precedes the constant.

---

## Fix 2 — 🔴 Correct the tautological grid bound in `IsValidExtra15`

**File:** `src/OpenWSFZ.Ft8/Dsp/MessageUnpacker.cs`  
**Line:** 264

### Why this is a blocker

```csharp
ulong val = packed & 0x3FFFUL;  // 14-bit mask → maximum value = 16 383
return isReport
    ? val >= 1 && val <= 60
    : val < 32_724;             // 16 383 < 32 724 is ALWAYS true
```

The non-report branch never returns `false`. `0x3FFF` = 16 383, and 16 383 is unconditionally less than 32 724. Every grid-square bit pattern passes the filter regardless of content. The guard provides no filtering at all, and the comment claiming it enforces the 32 399-ceiling is actively misleading.

### What to change

The 14-bit mask makes it impossible to reach 32 399 (the maximum standard Maidenhead grid value) directly. Two useful options:

**Option A — validate the decoded sub-fields (preferred):**

```csharp
private static bool IsValidExtra15(ulong packed)
{
    bool isReport = (packed & 0x4000UL) != 0;
    ulong val     = packed & 0x3FFFUL;

    if (isReport)
        return val >= 1 && val <= 84; // RRR/RR73/73 and SNR −31 to +49 dB (see Fix 3)

    // Grid square: decode sub-fields and validate each is in range.
    // Standard 4-char Maidenhead: r1 ∈ [0,17], r2 ∈ [0,17], r3 ∈ [0,9], r4 ∈ [0,9].
    // With the 14-bit mask, val is at most 16 383 — well within the 18×18×10×10 space.
    // Check for encodings that would produce impossible grid letters (r1 or r2 ≥ 18).
    return (val / 1800) < 18 && ((val % 1800) / 100) < 18;
}
```

**Option B — document the limitation and accept all grid values:**

```csharp
private static bool IsValidExtra15(ulong packed)
{
    bool isReport = (packed & 0x4000UL) != 0;
    ulong val     = packed & 0x3FFFUL;

    if (isReport)
        return val >= 1 && val <= 84; // RRR/RR73/73 and SNR −31 to +49 dB (see Fix 3)

    // Grid squares: the 14-bit mask caps val at 16 383, which is below the
    // standard Maidenhead upper bound (32 399). No values reachable through this
    // mask produce out-of-range grid letters; all pass. R-prefix contest values
    // (32 400+) are also unreachable here — see DecodeReport15 for that limitation.
    return true;
}
```

Option A is preferred — it adds genuine validation that catches the impossibly large `r1`/`r2` values that could arise from random bit patterns. Option B is acceptable if you want to preserve exactly the current false-positive filtering behaviour (none, for grids) and simply fix the misleading comment.

---

## Fix 3 — 🟠 Raise SNR ceiling to `val ≤ 84`

**File:** `src/OpenWSFZ.Ft8/Dsp/MessageUnpacker.cs`  
**Line:** 263 (inside `IsValidExtra15`)

### Why this matters

`DecodeReport15` line 208 contains the comment `// range -35 to +49`, acknowledging that val = 84 corresponds to a valid +49 dB report. The current ceiling at val = 60 (+25 dB) silently discards any station that is:

- Within short skip range (< 500 km) on 40 m
- Using a directional or elevated antenna
- Running full power into a resonant system

Such a station's decoded message passes both LDPC and CRC-14, reaches `TryUnpack`, and is dropped without trace.

The p10 corpus observation that all false positives had val > 60 does **not** imply val > 60 is invalid. The corpus contained no high-SNR close-in stations. The filter must match the spec, not the corpus.

### What to change

Inside `IsValidExtra15`, change the report branch ceiling:

```csharp
// Before:
? val >= 1 && val <= 60   // covers RRR/RR73/73 and SNR −34 to +25 dB

// After:
? val >= 1 && val <= 84   // RRR/RR73/73 and SNR −31 to +49 dB per FT8 spec
```

Update the XML summary comment on `IsValidExtra15` to reflect the corrected range.

> **Note on false-positive suppression:** if tests show that raising the ceiling from 60 to 84 re-introduces false positives, that indicates a deeper issue in the LDPC or CRC pipeline that must be investigated and fixed there — not papered over by tightening this filter below the spec limit.

---

## Fix 4 — 🟠 Remove the unreachable R-prefix branch in `DecodeReport15`

**File:** `src/OpenWSFZ.Ft8/Dsp/MessageUnpacker.cs`  
**Line:** 195

### Why this matters

```csharp
ulong val = packed & 0x3FFFUL;   // max = 16 383
if (val >= 32400) return $"R{val - 32400}";  // never reached
```

`val` is masked to 14 bits. 16 383 < 32 400. This branch is dead. Any FT8 contest message with an R-prefix serial number is silently mis-decoded as a standard grid square: for example, a packed value that would represent `R0001` (val = 32 401) arrives after masking as `val = 17`, and `DecodeReport15` returns `"AA17"`.

The branch gives false confidence that R-prefix contest messages are supported. They are not.

### What to change

Remove the dead branch and replace it with a comment:

```csharp
private static string DecodeReport15(ulong packed)
{
    bool isReport = (packed & 0x4000UL) != 0;
    ulong val     = packed & 0x3FFFUL;

    if (!isReport)
    {
        // R-prefix contest serial numbers (val ≥ 32 400) are not supported.
        // The 14-bit mask applied here caps val at 16 383, making that range
        // unreachable. Contest messages with R-prefix serials will be mis-decoded
        // as standard grid squares. This is a known limitation.
        int r1 = (int)(val / 1800);
        int r2 = (int)((val % 1800) / 100);
        int r3 = (int)((val % 100) / 10);
        int r4 = (int)(val % 10);
        return $"{GridLetters[r1]}{GridLetters[r2]}{r3}{r4}";
    }
    else
    {
        if (val == 1) return "RRR";
        if (val == 2) return "RR73";
        if (val == 3) return "73";
        int snr = (int)val - 35;
        return snr >= 0 ? $"+{snr:D2}" : $"{snr:D3}";
    }
}
```

---

## Fix 5 — 🟡 Delete dead method `IsValidCallsign28`

**File:** `src/OpenWSFZ.Ft8/Dsp/MessageUnpacker.cs`  
**Lines:** 230–263

The method is private and is not called from anywhere in the production code path. It is also algorithmically wrong: it uses the old uniform base-37 decode (dividing by 37 at all six positions), while `DecodeCallsign28` now uses the correct mixed-radix decode (base-27 for positions 3–5, base-10 for position 2, base-37 for positions 0–1). For packed = 4 134 219 (Q0ABC under mixed-radix), `IsValidCallsign28` decodes position 2 as `'6'` and would return incorrect results if ever connected.

Delete the entire method and its XML doc comment. The test file already documents why it is not called.

---

## Fix 6 — 🟡 Delete `LlrClamp` and its contradicting comment block

**File:** `src/OpenWSFZ.Ft8/Ft8Decoder.cs`  
**Lines:** 66–71

```csharp
// LLR clamp applied before LDPC.  Strong adjacent-channel interference can
// produce LLRs of ±7–8 with the wrong sign, completely overwhelming the 6
// neighbour-contributions (~6 × 0.3 = 1.8) that LDPC needs to flip the bit.
// Clamping to ±1.5 reduces wrong LLRs to a magnitude that the correct neighbours
// can overcome, while leaving typical clean signal LLRs (≈0.3) unchanged.
private const float  LlrClamp = 1.5f;
```

`LlrClamp` is never used. The usage site (line 190) has a comment saying clamping is *explicitly not applied*. The two comments directly contradict each other. Any developer who trusts the constant's documentation and wires it up with `MathF.Clamp(llr[i], -LlrClamp, LlrClamp)` will clip clean-signal LLRs from ≈8 down to ±1.5 and cause LDPC to diverge on every high-SNR signal.

Delete the constant and the six-line rationale block above it entirely. The usage-site comment at line 190–191 is sufficient:

```csharp
// No LLR clamping: strong-signal LLRs (≈8–9) must dominate weak-interference LLRs
// (≈2–3) so LDPC converges to the correct codeword rather than an interference codeword.
```

---

## Fix 7 — 🟡 Update pipeline XML doc (step 3 names Goertzel)

**File:** `src/OpenWSFZ.Ft8/Ft8Decoder.cs`  
**Line:** ~18 (class-level XML `<summary>`)

The pipeline description reads:

> *3. For each Costas candidate, recompute the 79 × 15 grid via Goertzel (`SymbolExtractor.Extract`) at the exact tone frequencies.*

`SymbolExtractor.Extract` (the Goertzel path) is not called anywhere in `DecodeAsync`. Both the Costas detection grid and the per-candidate LLR grid are produced by `ExtractFromSpectrogram`. Replace the pipeline description with:

```csharp
/// Pipeline per cycle (exact-DFT spectrogram):
///   1. For each symbol-aligned time offset, compute a 79 × 960 exact-DFT spectrogram
///      once via <see cref="SymbolExtractor.FillSpectrogramExact"/> (Bluestein chirp-Z,
///      1 920-point DFT, bin spacing = 6.25 Hz exactly).
///   2. Sweep candidate base frequencies (50–3 000 Hz, steps of 50 Hz).
///      Extract a 79 × 15 log-energy grid via <see cref="SymbolExtractor.ExtractFromSpectrogram"/>
///      and run <see cref="CostasSynchroniser.FindCandidates"/> to find Costas sync hits.
///   3. For each Costas candidate, re-extract the 79 × 15 grid from the same spectrogram
///      at the exact candidate base frequency, derive 174 soft LLRs via
///      <see cref="ComputeLlrs"/>, run <see cref="LdpcDecoder"/>, verify with
///      <see cref="Crc14"/>, unpack with <see cref="MessageUnpacker"/>.
///   4. De-duplicate messages; return the unique set as <see cref="DecodeResult"/> records.
```

---

## Test obligations

The existing `MessageUnpackerTests` cover the SNR-rejection path (Fixes 2 and 3 may require test updates — verify the existing `TryUnpack_ExtraVal2194_ReturnsNull` and `TryUnpack_ExtraVal4052_ReturnsNull` tests still pass after raising the ceiling to 84). No new tests are required for the cleanup items (5–7).

After all fixes are applied, run the full suite and confirm:

```
dotnet test -c Release   →   Failed: 0, Passed: 76
```

The three G6 gate tests must go green. If they remain red after Fix 1, investigate whether `MaxCandidatesPerSweep = 8` is still appropriate at the corrected threshold — at `SyncThreshold = 0.20`, fewer candidates should pass `FindCandidates`, and the previous value of 2 may be sufficient again.

---

## Commit guidance

Address all four mandatory items (Fixes 1–4) in a single commit. Include the three cleanup items (5–7) in the same commit or a follow-up tidy commit on the same branch. Do **not** open a separate branch — these are corrections to the p11 work already on `feat/p11-decoder-port`.

Suggested commit message:

```
fix(p11): QA remediation — sync threshold, IsValidExtra15, SNR ceiling, dead code
```
