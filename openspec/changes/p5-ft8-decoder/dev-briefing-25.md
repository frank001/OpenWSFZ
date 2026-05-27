# Developer Briefing — p5-ft8-decoder (Round 25)

**Date:** 2026-05-27  
**Issued by:** QA  
**Branch:** `feat/p7-p6-logging-and-display`  
**Scope:** D11 — Zero decodes on complete windows despite strong WSJT-X signals

---

## Situation

D10 is **confirmed resolved**. After the hard-decision Costas fix, decode times are now 1–5 seconds
(down from 30–62 seconds). All 48 tests pass.

However, the live application still produces zero decodes on the second and third complete windows
while WSJT-X simultaneously decodes 15+ signals (−8 to −22 dB SNR) from the same USB Audio CODEC
device.

---

## Evidence

From `logs/openswfz-20260527T151907Z.log` and the WSJT-X screenshot taken at approximately 15:19:30
UTC:

| Window | OpenWSFZ label | UTC coverage | Decode time | Result |
|--------|---------------|--------------|-------------|--------|
| 1 | Cycle 15:19:15 | 15:19:00 – 15:19:15 | 1.8 s | 0 ← **expected** (see §Analysis) |
| 2 | Cycle 15:19:30 | 15:19:15 – 15:19:30 | 4.0 s | 0 ← **BUG** |
| 3 | Cycle 15:19:45 | 15:19:30 – 15:19:45 | 5.0 s | 0 ← **BUG** |

WSJT-X shows "151915" decodes — transmissions sent at 15:19:15 UTC — at the exact time
OpenWSFZ is processing window 2. 15+ signals at −8 to −22 dB, frequencies 499–2495 Hz,
all within OpenWSFZ's 50–3000 Hz sweep range and dt values −0.2 to +1.1 s, well within the
8.12-second time-domain sweep.

---

## Analysis

### Window 1: zero decodes expected

The daemon started at UTC 15:19:07.15, so the first window has 85 800 samples of leading
silence followed by 7.85 s of real audio. A 15:19:00 FT8 transmission started at sample
−85 800 (before capture began); only symbols 45–78 are present in the buffer. The first
two Costas arrays (symbols 0–6 and 36–42) are absent. The maximum achievable Costas score
against the D10 hard-decision criterion is 7/21 = 0.33, below the 0.45 threshold. Zero
decodes is **correct** for window 1.

### Window 2: zero decodes is a defect

Window 2 covers UTC 15:19:15 – 15:19:30 exactly (no leading silence). A 15:19:15 UTC FT8
transmission lands at sample 0, runs to sample 151 680 — fully contained within the 180 000
sample buffer. All three Costas arrays are present. WSJT-X confirms strong signals exist in
this audio. The decoder should find decodes; it finds none.

---

## Possible Failure Points

There are exactly three places the pipeline can drop a signal after D10:

| Stage | Symptom in diagnostic log |
|-------|--------------------------|
| **A — Costas not finding candidates** | `Costas candidates=0` |
| **B — LDPC failing to converge** | `Costas candidates=N>0, LDPC converged=0` |
| **C — CRC failing after LDPC** | `LDPC converged=N>0, CRC passed=0` |

Without instrumentation it is impossible to distinguish these three cases from the logs alone.

---

## Diagnostic Logging Already Applied

QA has added three counters and one per-candidate Debug log line to `Ft8Decoder.DecodeAsync`
in `src/OpenWSFZ.Ft8/Ft8Decoder.cs`. All 48 tests still pass. The counters emit at
**Information** level so no log-level change is required.

**New log line format (Information level):**

```
Cycle 15:19:30: 0 decode(s) found. [diag] Costas candidates=247, LDPC converged=12, CRC passed=0.
```

**Per-candidate log line format (Debug level):**

```
Costas hit: startSample=0, base=493.75 Hz, score=0.952.
```

To see per-candidate Debug lines, set `"LogLevel": "Debug"` in `config.json`.

---

## Instructions

### Step 1 — Rebuild and run against live audio

```
dotnet build src/OpenWSFZ.Ft8/ -c Release
dotnet run --project src/OpenWSFZ.Daemon/ -c Release
```

Connect the USB Audio CODEC to a known-active FT8 band (40 m / 7.074 MHz, or use a WSJT-X
cross-check on the same device). Confirm WSJT-X is decoding signals at the same time.

### Step 2 — Read the diagnostic output

Check two or three complete cycles (labels Cycle HH:MM:30 or HH:MM:45, i.e., not the
first truncated window). The `[diag]` suffix will be present on every decode line.

**Interpret the result as follows:**

---

#### Case A — `Costas candidates=0`

The Costas hard-decision threshold is rejecting all candidates. Real signals are not reaching
the Goertzel stage.

Likely cause: For real audio the FFT spectrogram energy in the correct Costas tone may be
competing with adjacent noise bins. The hard-decision criterion (`costas >= maxE`) requires
the exact Costas tone to be the absolute peak among all 8 signal-band bins for *every*
Costas symbol position. At the SNR levels observed (−8 to −22 dB WSJT reference), this
should hold with probability > 0.6 per symbol even for the weakest signal, yielding an
expected score of 0.6 × 21/21 ≈ 0.6 >> 0.45. If it is not holding, investigate the FFT
bin alignment:

- Is `ExtractFromSpectrogram` reading the correct FFT bin for each of the 21 Costas tones?
- Does the spectrogram power at the Costas-tone bin exceed the adjacent bins by a clear margin
  for at least 13 of the 21 positions?

If the FFT path is suspect, consider testing Goertzel-only Costas scoring as a diagnostic.

---

#### Case B — `Costas candidates=N > 0, LDPC converged=0`

Costas candidates are found but LDPC belief propagation does not satisfy the parity check
in 50 iterations. This means the LLRs entering the decoder are too weak, too large, or have
the wrong sign pattern.

**Most likely root cause: The H matrix in `LdpcDecoder` may not match the H matrix used to
encode real FT8 signals.**

The round-trip synthetic test (`DecodeAsync_WavFixture_ReturnsKnownDecodes`) **cannot**
detect an H matrix error because `TestFt8Encoder` uses the same H matrix for encoding that
`LdpcDecoder` uses for decoding — a self-consistent but potentially wrong pair. Real
transmissions from WSJT-X use the definitive kgoba/ft8_lib H matrix.

**Verification approach:**

1. Capture a segment of real FT8 audio on which WSJT-X produces a known decode.
2. Recover the raw decoded bits (77 message bits + 14 CRC) from WSJT-X (use `--display-debug`
   mode or extract from its source).
3. Add a unit test that feeds perfect LLRs derived from the known codeword into `LdpcDecoder`
   and checks the output matches the known bits.

Alternatively:
- Check that `LdpcDecoder.H` satisfies `H · G^T = 0` for the generator matrix used in
  `TestFt8Encoder`. This confirms H and G are a consistent pair for the standard FT8 code.

---

#### Case C — `LDPC converged=N > 0, CRC passed=0`

LDPC converges but the CRC-14 check always fails. This points to a bit-ordering or
polynomial mismatch between OpenWSFZ's `Crc14` and the FT8 standard.

CRC-14 parameters for FT8 (Franke & Taylor 2019):
- Polynomial: 0x2757 (x¹⁴ + x¹³ + x¹⁰ + x⁹ + x⁸ + x⁶ + x⁴ + x² + x + 1)
- Initial register: 0
- Input: 77 message bits, MSB-first
- Appended: 14 check bits

The `Crc14.Verify` implementation should be compared against the WSJT-X source
(`lib/ft8/crc14.f90`). The key detail is whether the input bits are processed MSB-first
(bit index 0 = most significant) — OpenWSFZ's current implementation does process
MSB-first.

---

## Summary

| Item | Status |
|------|--------|
| D10 — Costas soft-match O(minutes) decode | ✅ Resolved, confirmed in live log |
| Window 1 zero decodes | ✅ Expected (truncated first capture window) |
| **D11 — Zero decodes on complete windows** | ❌ **Active blocker** |
| Diagnostic counters added | ✅ In `Ft8Decoder.cs`, all 48 tests pass |

Run with live audio, collect two complete cycle log lines with `[diag]` suffixes, and return
for re-analysis. One data point is all that is needed to identify the failure stage.
