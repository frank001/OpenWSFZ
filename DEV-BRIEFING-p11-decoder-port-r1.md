# Developer Briefing — p11 Decoder Port — Round 1 Remediation

**Issued by:** QA Engineer  
**Date:** 2026-05-29  
**Branch:** `feat/p11-decoder-port`  
**QA verdict:** ❌ RETURN FOR CHANGES — see `QA-REVIEW-p11-decoder-port.md`  
**Remediation analysis:** `DEV-REMEDIATION-p11-decoder-port.md`

---

## Objective

Fix seven items identified in the QA review. Items 1–4 are mandatory; the branch will not be
approved without them. Items 5–7 are cleanup that must travel in the same commit pass.

After all seven items are applied, `dotnet test -c Release` must exit 0 with the three
`RealSignalFixtureTests` **green**. That is the G6 gate passing. If those three tests remain
red after Fix 1, investigate `MaxCandidatesPerSweep` (see note at end).

---

## Fix 1 — 🔴 MANDATORY — `Ft8Decoder.cs` — Raise `SyncThreshold` above the noise floor

**File:** `src/OpenWSFZ.Ft8/Ft8Decoder.cs`  
**Why:** `SyncThreshold = 0.1f` is below the uniform-noise floor of 0.125. Every frequency
position at every time offset passes `FindCandidates` on real band audio, flooding LDPC with
~48 000 runs per cycle on noise. This is the direct cause of G6 failing.

### Change

Find the constant (near line 64):

```csharp
// Before
private const float SyncThreshold = 0.1f;

// After
// Softmax Costas threshold.
// Uniform noise score = 0.125 (each of 8 equal-energy tones contributes 1/8 per position).
// 0.20 sits above the noise floor and below 0.33 (3 equal-power interferers).
private const float SyncThreshold = 0.20f;
```

Also remove the duplicate comment block (lines 55–59, the one starting "The CRC-14 gate
provides the final false-positive suppression"). That sentence already appears once below —
the duplicate is dead commentary left over from an earlier draft.

---

## Fix 2 — 🔴 MANDATORY — `MessageUnpacker.cs` — Fix tautological grid bound in `IsValidExtra15`

**File:** `src/OpenWSFZ.Ft8/Dsp/MessageUnpacker.cs`  
**Why:** `val < 32_724` is always true when `val` is masked to 14 bits (max 16 383). The
non-report branch of `IsValidExtra15` never rejects anything — the comment claiming it
enforces the 32 399-ceiling is actively misleading.

### Change

Replace the non-report branch with a sub-field validator:

```csharp
private static bool IsValidExtra15(ulong packed)
{
    bool isReport = (packed & 0x4000UL) != 0;
    ulong val     = packed & 0x3FFFUL;

    if (isReport)
        return val >= 1 && val <= 84; // RRR/RR73/73 and SNR −31 to +49 dB (see Fix 3)

    // Grid square: validate sub-fields so impossible letter combinations are rejected.
    // Standard 4-char Maidenhead: r1 ∈ [0,17], r2 ∈ [0,17], r3 ∈ [0,9], r4 ∈ [0,9].
    // With the 14-bit mask val ≤ 16 383, which is within the standard grid space,
    // so only the letter sub-fields need guarding.
    return (val / 1800) < 18 && ((val % 1800) / 100) < 18;
}
```

Note that the `isReport` ceiling is changed to 84 as part of Fix 3 — apply both together.

---

## Fix 3 — 🔴 MANDATORY — `MessageUnpacker.cs` — Raise SNR ceiling to `val ≤ 84`

**File:** `src/OpenWSFZ.Ft8/Dsp/MessageUnpacker.cs`  
**Why:** The FT8 spec allows SNR val 1–84 (−31 to +49 dB). The current ceiling of 60 (+25 dB)
silently discards any station within short-skip range on 40 m. `DecodeReport15` line 208 even
carries a comment acknowledging the range goes to +49 — the ceiling contradicts the code's own
comment. Fix 2 above already incorporates this change in `IsValidExtra15`; make sure
`DecodeReport15` is consistent.

### Check `DecodeReport15`

Confirm the SNR decode expression uses `val − 35` and does **not** have its own ceiling check
capping at 60. If it does, remove it. The valid range check belongs entirely in
`IsValidExtra15`; `DecodeReport15` should decode whatever passes the filter.

---

## Fix 4 — 🔴 MANDATORY — `MessageUnpacker.cs` — Remove the unreachable R-prefix branch

**File:** `src/OpenWSFZ.Ft8/Dsp/MessageUnpacker.cs`  
**Why:** In `DecodeReport15`, the branch `if (val >= 32400) return $"R{val - 32400}";` is dead
code. `val` is masked to 14 bits (max 16 383); 16 383 < 32 400. It cannot execute and gives
false confidence that R-prefix contest messages are handled. They are not.

### Change

Remove the dead branch and replace it with a comment:

```csharp
if (!isReport)
{
    // R-prefix contest serial numbers (val ≥ 32 400) are NOT supported.
    // The 14-bit mask caps val at 16 383, making that range unreachable.
    // Contest messages with R-prefix serials will be mis-decoded as grid squares.
    // This is a known limitation.
    int r1 = (int)(val / 1800);
    int r2 = (int)((val % 1800) / 100);
    int r3 = (int)((val % 100) / 10);
    int r4 = (int)(val % 10);
    return $"{GridLetters[r1]}{GridLetters[r2]}{r3}{r4}";
}
```

---

## Fix 5 — 🟡 CLEANUP — `MessageUnpacker.cs` — Delete dead method `IsValidCallsign28`

**File:** `src/OpenWSFZ.Ft8/Dsp/MessageUnpacker.cs`  
**Why:** The method is private and never called. It also uses the old uniform base-37 decode
(not the current mixed-radix algorithm), so it produces wrong results for most callsigns and
is a maintenance trap.

Delete the entire method and its XML doc comment. The existing test file comment explains
why it is not called.

---

## Fix 6 — 🟡 CLEANUP — `Ft8Decoder.cs` — Delete `LlrClamp` and its contradicting comment

**File:** `src/OpenWSFZ.Ft8/Ft8Decoder.cs`  
**Why:** `LlrClamp = 1.5f` is defined but never used. The rationale block above it argues FOR
clamping; the usage-site comment 20 lines later argues AGAINST it. The two contradict each
other. A developer who trusts the constant's documentation could wire it up and destroy
high-SNR decode performance.

Delete the constant and its six-line rationale block. Keep only the usage-site comment:

```csharp
// No LLR clamping: strong-signal LLRs (≈8–9) must dominate weak-interference LLRs
// (≈2–3) so LDPC converges to the correct codeword rather than an interference codeword.
```

---

## Fix 7 — 🟡 CLEANUP — `Ft8Decoder.cs` — Update pipeline XML doc

**File:** `src/OpenWSFZ.Ft8/Ft8Decoder.cs` (class-level `<summary>`, near line 18)  
**Why:** Step 3 of the pipeline description still names Goertzel and `SymbolExtractor.Extract`.
Neither is called in `DecodeAsync` — the actual code uses `ExtractFromSpectrogram`.

Replace step 3 of the pipeline summary with the accurate description:

```csharp
/// Pipeline per cycle (exact-DFT spectrogram):
///   1. For each symbol-aligned time offset, compute a 79 × 960 exact-DFT spectrogram
///      once via <see cref="SymbolExtractor.FillSpectrogramExact"/>.
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

## Test verification

### 1. Existing tests must stay green

```
dotnet test tests/OpenWSFZ.Ft8.Tests -c Release --no-build
```

Specifically check that these do **not** regress after raising the SNR ceiling to 84:

- `TryUnpack_ExtraVal2194_ReturnsNull`
- `TryUnpack_ExtraVal4052_ReturnsNull`

If either fails, the test fixture values are for val > 84 — update the expected outcome
(they should now return a value rather than null) or replace with fixtures at val > 84 that
represent genuinely invalid content rather than merely high SNR.

### 2. G6 gate must go green

```
dotnet test tests/OpenWSFZ.Ft8.Tests -c Release --no-build --filter "RealSignal"
```

All three `RealSignalFixtureTests` must pass. If they remain red after Fix 1:

- Check whether `MaxCandidatesPerSweep` is still set to 8. At `SyncThreshold = 0.20` fewer
  candidates pass `FindCandidates`; the prior value of **2** may be sufficient again and will
  reduce the per-cycle LDPC load significantly on busy-band frames.
- If the tests time out rather than fail an assertion, the candidate count is still too high —
  lower `MaxCandidatesPerSweep` first and re-run.

### 3. Full suite

```
dotnet test -c Release
```

Target: `Failed: 0`. All 186+ tests pass.

---

## Commit

Address all seven items in a single commit on `feat/p11-decoder-port`:

```
fix(p11): QA remediation — sync threshold, IsValidExtra15, SNR ceiling, dead code
```

Do **not** open a new branch. These are corrections to the existing p11 work.

Once committed and pushed, re-submit for QA review.
