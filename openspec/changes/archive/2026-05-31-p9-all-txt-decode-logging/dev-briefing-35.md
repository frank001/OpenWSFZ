# Developer Briefing — p9-all-txt-decode-logging (Round 35)

**Date:** 2026-05-28  
**Issued by:** QA  
**Branch:** `feat/p9-all-txt-decode-logging`  
**Scope:** Round 34 review findings — one mandatory fix (D16 doc comment); D18 root-cause analysis and next diagnostic steps

---

## Summary

The Round 34 implementation is approved save for one mandatory correction: a stale XML
documentation comment in `AllTxtWriter.cs` that still advertises the old 5-character DT
field.  Fix that, commit, and the D16/D17 portion is cleared for merge.

D18 is not fixed in this round — that was expected.  The diagnostic data has been analysed
and the audio path has been conclusively exonerated.  The fault lies in the DSP stage that
follows Costas detection.  This briefing specifies the next targeted investigation.

| Item | Severity | Action |
|------|----------|--------|
| Stale XML doc comment in `AllTxtWriter.cs` | Low | **Fix and commit** |
| D18 — stale `actualBase` passed to `SymbolExtractor.Extract` | Critical | Diagnostic only (see §2) |

---

## 1. Mandatory Fix — Stale XML Doc Comment (D16 follow-up)

### Location

`src/OpenWSFZ.Daemon/AllTxtWriter.cs`, lines 12–15, `<code>` block inside the XML
summary:

```csharp
/// <code>
/// YYMMDD_HHMMSS     D.DDD Rx FT8 {snr,6} {dt,5:F1} {freq,4} {message}
/// </code>
```

### Problem

When D16 corrected `{result.Dt,5:F1}` to `{result.Dt,4:F1}` in the implementation, the
XML documentation comment was not updated.  It still shows `{dt,5:F1}`.  The spec, the
test, the requirements document, and the code are all correct; only this comment is stale.

### Fix

```csharp
// Before:
/// YYMMDD_HHMMSS     D.DDD Rx FT8 {snr,6} {dt,5:F1} {freq,4} {message}

// After:
/// YYMMDD_HHMMSS     D.DDD Rx FT8 {snr,6} {dt,4:F1} {freq,4} {message}
```

### Verification

`dotnet build -c Release` — 0 errors, 0 warnings.  No test changes required.

---

## 2. D18 — Diagnostic Results and Next Steps

### 2.1 What the Round 34 data tells us

**D18-1 — PCM window statistics (both cycles observed):**

| Field | Cycle 1 | Cycle 2 | Expected |
|-------|---------|---------|----------|
| `count` | 180,000 | 180,000 | ~180,000 |
| `min/max` | ±0.058 | ±0.057 | ±0.05–±1.0 |
| `rms` | 0.0132 | 0.0162 | 0.005–0.3 |

**H1 is eliminated.**  The capture layer delivers correct 12,000 Hz mono float32 PCM.
No further investigation of the audio path is warranted.

**D18-2 and D18-3 — Not observed.**

The detection condition `startSample is >= 960 and <= 1440` was too narrow.  With
`TimeSweepStep = 960` the sweep visits positions 0, 960, 1920, 2880, …  The WSJT-X
signal at DT ≈ 0.1 s corresponds to sample 1,200 — between positions 960 and 1920.
Neither falls in [960, 1440].

Despite this, the Costas hit log confirms the 731 Hz signal IS passing the gate in cycle 2:

```
startSample=1920  base=731.25 Hz  score=0.486   ← real signal, above 0.45 threshold
startSample=2880  base=731.25 Hz  score=0.489
startSample=28800 base=731.25 Hz  score=0.532
```

**The Costas stage is not the problem.**

**Summary diagnostic counters:**

| Cycle | Costas candidates | LDPC converged | CRC passed | avg_parity_fail |
|-------|------------------|----------------|------------|----------------|
| 21:40:45 | 457 | 4 | 4 | 40.8 / 83 |
| 21:41:00 | 2,797 | 24 | 16 | 41.1 / 83 |

`avg_initial_parity_fail ≈ 41/83` is statistically indistinguishable from the random
baseline of 41.5/83 (binary parity check, random input).  The LLRs reaching the LDPC
decoder carry no signal information whatsoever, on average.  Every entry in ALL.TXT is
a CRC-14 coincidence on random bit patterns — confirmed by the invalid callsigns
(`1TJK`, `0BZH3J`, `23P6PA`, …) and impossible RSL values (`+2158`, `+4011`, `+8113`).

### 2.2 Working hypothesis — H4: `startSample` misalignment in Goertzel extraction

The Costas stage operates on a spectrogram computed once from `startSample`.  After a
Costas hit, `SymbolExtractor.Extract(pcm, startSample, actualBase)` is called to
recompute the 79 × 15 energy grid via Goertzel at the confirmed tone frequencies.  This
Goertzel pass uses the *same* `startSample`.

However, the sweep is intentionally coarse (step = 960 samples = half a symbol).  For a
signal whose actual alignment is 1,200 samples (DT = 0.1 s), the nearest sweep position
is 960 or 1,920 — both misaligned by up to 240 samples (≈ 12.5 % of a symbol period).

In isolation, 12.5 % misalignment causes moderate LLR degradation; it should not produce
completely random output.  The more likely mechanism is an error internal to
`SymbolExtractor.Extract` or `ComputeLlrs` that is exposed only with live, complex audio.
Unit tests pass because they use single-tone, perfectly-aligned synthetic PCM that makes
any timing error in the extraction window irrelevant.

Specific candidates to investigate, in priority order:

1. **Tone frequency mapping in `SymbolExtractor.Extract`** — does the Goertzel
   computation use the correct set of 8 tone frequencies for the confirmed `actualBase`?
   Verify that the 8 Goertzel target frequencies are
   `actualBase + k × ToneSpacing` for k = 0…7, and that the base frequency used is
   `actualBase` (after adding `cand.FreqBinOffset * ToneSpacing`), not `baseHz`.

2. **LLR sign convention in `ComputeLlrs`** — FT8 LLRs must be positive for the
   hypothesis "this bit is 0" and negative for "this bit is 1" (or vice versa,
   consistently).  A sign inversion that is masked by the ideal synthetic-signal tests
   would produce ≈ 41/83 parity failures on live audio.  Verify the sign against the
   WSJT-X soft-decision convention.

3. **Goertzel window length** — the Goertzel DFT must integrate over exactly one symbol
   period (1,920 samples per symbol).  If the window length was accidentally halved
   (e.g. 960 samples), each symbol's energy is computed from mixed symbol content,
   producing near-random LLRs.

### 2.3 Required diagnostics — report before attempting any fix

Add the following temporary `LogDebug` instrumentation.  Run one live cycle, capture the
output, and report the raw log lines.  Do not attempt to fix D18 until QA has reviewed
the values.

---

**Diagnostic 4 — Goertzel frequencies at a known Costas hit**

Location: `SymbolExtractor.Extract`, immediately after the tone frequency array is
constructed.  Log the first symbol's Goertzel target frequencies for the candidate
nearest to `actualBase ≈ 731 Hz`.

```csharp
// TEMPORARY D18 DIAGNOSTIC — remove after investigation
if (Math.Abs(actualBase - 731.25) < 10.0 && _logger?.IsEnabled(LogLevel.Debug) == true)
{
    _logger!.LogDebug(
        "[D18-4] Goertzel tones for actualBase={Base:F2} Hz: {T0:F2} {T1:F2} {T2:F2} {T3:F2} {T4:F2} {T5:F2} {T6:F2} {T7:F2}",
        actualBase, tones[0], tones[1], tones[2], tones[3],
        tones[4], tones[5], tones[6], tones[7]);
}
```

*(If `tones` is computed inline rather than stored in an array, adapt accordingly.)*

**Expected values** for a correctly-decoded 731.25 Hz signal:

```
731.25  737.50  743.75  750.00  756.25  762.50  768.75  775.00
```

Any deviation from these values identifies a frequency mapping error.

---

**Diagnostic 5 — Raw Goertzel energies at the 731 Hz candidate, first 8 symbols**

Location: `SymbolExtractor.Extract`, after Goertzel energy values are computed for the
first 8 symbol slots.  Log the raw energies (not log-transformed) for tone 0 and tone 3
across the first 8 symbols.  These two tones are the first Costas array tones (sequence
3, 1, 4, 0, 6, 5, 2 — indices 3 and 1 being the first two non-trivial ones) and will
show clearly whether energy concentration is present.

```csharp
// TEMPORARY D18 DIAGNOSTIC — remove after investigation
if (Math.Abs(actualBase - 731.25) < 10.0 && _logger?.IsEnabled(LogLevel.Debug) == true)
{
    var sb = new System.Text.StringBuilder();
    for (int sym = 0; sym < Math.Min(8, grid.GetLength(0)); sym++)
        sb.Append($"sym{sym}:[{grid[sym, 0]:F3},{grid[sym, 3]:F3}] ");
    _logger!.LogDebug("[D18-5] Energy grid (tone0,tone3) at 731 Hz: {Grid}", sb.ToString());
}
```

**Interpretation:**

| Pattern | Diagnosis |
|---------|-----------|
| All values near the same low constant | Goertzel window wrong — no signal energy being captured |
| Highly variable values with peaks at expected Costas positions (sym 0, 36, 72) | Extraction is working; proceed to LLR check |
| Uniformly random-looking values | Frequency mismatch — wrong tones being evaluated |

---

**Diagnostic 6 — First 12 raw LLRs from `ComputeLlrs`**

Location: `Ft8Decoder`, immediately after `ComputeLlrs` returns, for the 731 Hz candidate.

```csharp
// TEMPORARY D18 DIAGNOSTIC — remove after investigation
if (Math.Abs(actualBase - 731.25) < 10.0 && _logger?.IsEnabled(LogLevel.Debug) == true)
{
    _logger!.LogDebug(
        "[D18-6] First 12 LLRs at 731 Hz: {L0:+0.00;-0.00} {L1:+0.00;-0.00} {L2:+0.00;-0.00} {L3:+0.00;-0.00} {L4:+0.00;-0.00} {L5:+0.00;-0.00} {L6:+0.00;-0.00} {L7:+0.00;-0.00} {L8:+0.00;-0.00} {L9:+0.00;-0.00} {L10:+0.00;-0.00} {L11:+0.00;-0.00}",
        llr[0], llr[1], llr[2], llr[3], llr[4], llr[5],
        llr[6], llr[7], llr[8], llr[9], llr[10], llr[11]);
}
```

**Interpretation:**

| Pattern | Diagnosis |
|---------|-----------|
| Magnitudes consistently < 0.1 | Goertzel energies are near-equal — no signal discrimination; extraction is failing |
| Magnitudes 0.5–5.0 with mixed signs | LLRs look plausible; LDPC should be viable — check sign convention |
| Alternating signs in a systematic pattern | Sign inversion artefact in `ComputeLlrs` |

---

### 2.4 Updated D18-2 condition (widen the window)

Replace the existing D18-2 and D18-3 conditions in `Ft8Decoder.cs`:

```csharp
// Before:
bool isKnownSignal = Math.Abs(baseHz - 700) < 1 && cand.FreqBinOffset == 5 &&
                     startSample is >= 960 and <= 1440;

// After — widen to cover the two sweep positions nearest to DT = 0.1 s:
bool isKnownSignal = Math.Abs(actualBase - 731.25) < 7.0 &&
                     startSample is >= 960 and <= 1920;
```

This uses `actualBase` (already computed by the time D18-2 fires) rather than
`baseHz + FreqBinOffset`, and widens the time window to include both startSample=960
and startSample=1920.

---

## 3. Implementation Plan

### Step 1 — Mandatory fix (do first)

| # | Action |
|---|--------|
| 1 | `AllTxtWriter.cs`: update XML doc comment `{dt,5:F1}` → `{dt,4:F1}` |
| 2 | `dotnet build -c Release` — 0 errors, 0 warnings |
| 3 | `dotnet test -c Release` — all tests green |
| 4 | Commit to `feat/p9-all-txt-decode-logging` |

### Step 2 — D18 diagnostic run

| # | Action |
|---|--------|
| 1 | Widen D18-2/D18-3 condition as specified in §2.4 |
| 2 | Add D18-4 (Goertzel tone frequencies) instrumentation |
| 3 | Add D18-5 (raw energy grid) instrumentation |
| 4 | Add D18-6 (first 12 LLRs) instrumentation |
| 5 | Set log level to Debug for `OpenWSFZ.Ft8` and `OpenWSFZ.Daemon` namespaces |
| 6 | Run one live 15-second decode cycle on 7.074 MHz |
| 7 | Paste `[D18-2]`, `[D18-3]`, `[D18-4]`, `[D18-5]`, `[D18-6]` log lines back to QA |
| 8 | Do **not** attempt any fix — QA will issue fix instructions based on the measurements |
