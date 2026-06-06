# QA Findings — Run `6bab388` — S7 Co-channel Decode Gap

**Raised:** 2026-06-06
**Raised by:** QA
**Run:** `6bab388` (first full PASS run; two consecutive runs confirm finding)
**Status:** Open — product defect raised; Captain has elected to track formally
**GitHub issue:** frank001/OpenWSFZ#3

---

## D-001 — Medium — OpenWSFZ co-channel and time-freq decode gap vs WSJT-X

### Evidence

Two consecutive R&R runs (`4c34ef6` and `6bab388`) produce consistent S7 results,
confirming this is a stable signal rather than measurement noise:

#### Recovery by overlap family

| Family | Condition | WSJT-X (`4c34ef6`) | OpenWSFZ (`4c34ef6`) | WSJT-X (`6bab388`) | OpenWSFZ (`6bab388`) |
|---|---|---|---|---|---|
| co_channel | 2-stack, equal SNR | 38.1% | 0.0% | 38.1% | 4.8% |
| time_freq | co-freq, staggered DT | 100.0% | 44.4% | 100.0% | 38.9% |
| near_collision | 3–50 Hz separation | 86.7% | 80.0% | 100.0% | 76.7% |
| capture | co-freq, unequal SNR | 87.5% | 50.0% | 66.7% | 50.0% |
| **all** | | **78.5%** | **47.3%** | **77.4%** | **46.2%** |

#### Per-part detail (run `6bab388`)

| Part | Family | Condition | WSJT-X | OpenWSFZ |
|---|---|---|---|---|
| P0 | co_channel | 2-stack, equal 0 dB | 4/6 | 0/6 |
| P1 | co_channel | 2-stack, equal −5 dB | 4/6 | 1/6 |
| P2 | co_channel | 3-stack, equal 0 dB | 0/9 | 0/9 |
| P3 | near_collision | delta 3 Hz | 6/6 | 6/6 |
| P4 | near_collision | delta 6 Hz | 6/6 | 2/6 |
| P5 | near_collision | delta 12 Hz | 6/6 | 3/6 |
| P6 | near_collision | delta 25 Hz | 6/6 | 6/6 |
| P7 | near_collision | delta 50 Hz | 6/6 | 6/6 |
| P8 | time_freq | co-freq, dt 0.0 / 0.5 s | 6/6 | 0/6 |
| P9 | time_freq | co-freq, dt 0.0 / 1.0 s | 6/6 | 3/6 |
| P10 | time_freq | co-freq, dt 0.0 / 2.0 s | 6/6 | 4/6 |
| P11 | capture | co-freq, 0 / −3 dB | 4/6 | 3/6 |
| P12 | capture | co-freq, 0 / −6 dB | 4/6 | 3/6 |
| P13 | capture | co-freq, 0 / −10 dB | 4/6 | 3/6 |
| P14 | capture | co-freq, +3 / −10 dB | 4/6 | 3/6 |

### Severity classification

**Medium.** OpenWSFZ can complete a two-way QSO under typical single-signal conditions
(S1–S5 all PASS). The co-channel gap degrades performance in pileup / contest operating
conditions but does not prevent normal use. No crash, no data loss, no silent
misconfiguration.

### Root cause analysis

OpenWSFZ decodes via a single call to `ft8_lib` (`ft8_decode_all`). The p15 phase added
a spectrogram-domain second-pass (suppress decoded carriers, re-decode), which improved
overall recovery from 66.6% to 69.1% on the ground-truth corpus. However, spectrogram
subtraction operates at ±3.125 Hz FFT bin resolution, which is insufficient for coherent
PCM-domain cancellation of co-channel signals sharing the same or adjacent tone grid.

WSJT-X is known to implement iterative successive interference cancellation (SIC) in the
PCM domain — estimating each decoded signal's waveform at sub-Hz precision and subtracting
it before re-running the decoder. This is the most probable explanation for WSJT-X's
ability to recover 4/6 trials from a 2-stack equal-SNR co-channel pair (P0) where
OpenWSFZ recovers 0/6.

The 3-stack equal-SNR case (P2) recovers 0/9 for *both* apps — this is consistent with
the theoretical mutual-interference floor; no defect there.

The time_freq gap (P8: 0/6 OpenWSFZ vs 6/6 WSJT-X at dt offset = 0.5 s) suggests the
second-pass suppression is also failing to separate near-simultaneous co-frequency signals
that differ only in timing.

### What a fix would require

Closing this gap substantially requires **PCM-domain iterative subtraction**:

1. **Sub-Hz carrier frequency estimation** — after decoding a signal, re-estimate its
   exact audio frequency from the matched filter peak, not the FFT bin centre.
2. **Waveform reconstruction** — re-synthesise the decoded message at the estimated
   frequency, amplitude, and DT to produce a clean PCM replica.
3. **Subtract and re-decode** — subtract the replica from the raw PCM buffer and run
   `ft8_decode_all` again.

This is a non-trivial extension of the existing p15 second-pass infrastructure.
Complexity is medium-high; the architecture is open to it but it has not been attempted.

### Out of scope for this defect

- The 3-stack equal-SNR case (P2) — both apps fail; this is likely a theoretical limit,
  not an OpenWSFZ-specific defect.
- WSJT-X capture-effect regression (`4c34ef6` → `6bab388`: 87.5% → 66.7%) — this is a
  WSJT-X result variation; not an OpenWSFZ concern.

---

## Summary

| ID | Severity | Component | Description |
|---|---|---|---|
| D-001 | **Medium** | `OpenWSFZ.Ft8` decode pipeline | Co-channel and time-freq decode gap vs WSJT-X; root cause: no PCM-domain SIC |
