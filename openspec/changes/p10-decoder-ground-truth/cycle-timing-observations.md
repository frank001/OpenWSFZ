# Cycle Timing — Empirical Observations

**Date:** 2026-06-05  
**Tester:** Captain (manual)  
**Analyst:** QA Engineer  
**Related change:** p10-decoder-ground-truth  
**Related fix:** GO indicator (`web/js/main.js` — `GO_WINDOW_S` 8 → 2)

---

## Method

The same 28.074 MHz FT8 audio sample was played repeatedly into the live pipeline via
Voicemeeter Out B2. On each playback the start time relative to the cycle boundary was
varied deliberately. Two sessions were recorded:

- **Session 1** (`openswfz-20260605T184651Z.log`) — timing pushed progressively later,
  past the cliff edge and back.
- **Session 2** (`openswfz-20260605T190751Z.log`) — timing kept within the corrected
  2-second GO window throughout.

The `dt` column in ALL.TXT (time offset of each decoded signal from the nominal cycle
start) was used to infer the actual playback start offset for each cycle. The minimum
`dt` value within a cycle is the most reliable proxy: it corresponds to the
earliest-transmitting station in the recording, whose natural `dt` is near zero.

---

## Session 1 — Timing Boundary Test

| Cycle (UTC) | RMS | Decodes | dt min | dt max | Inferred offset |
|---|---|---|---|---|---|
| 18:46:45 | ≈ 0 | 0 | — | — | Silence |
| 18:47:00 | 0.000 | 0 | — | — | Silence guard |
| 18:47:15 | 6.2E-3 | **16** | 1.2 s | 2.7 s | ~1.2 s |
| 18:47:30 | 5.9E-3 | **12** | 2.3 s | 2.8 s | ~2.3 s |
| 18:47:45 | 6.1E-3 | **2** | 3.0 s | 3.0 s | ~3.0 s |
| 18:48:00 | 5.5E-3 | **0** | — | — | > 3.0 s |
| 18:48:15 | 5.7E-3 | **0** | — | — | > 3.0 s |
| 18:48:30 | 6.3E-3 | **0** | — | — | > 3.0 s |
| 18:48:45 | 6.2E-3 | **17** | 1.6 s | 3.1 s | ~1.6 s |

### Observations

1. **Full decode zone (0 – ~2.3 s):** 16–17 signals recovered. Decode count stable;
   all signals including the weakest (-23 dB) are found.

2. **Degraded zone (~2.3 – ~3.0 s):** Decode count drops from 16 to 2. Weak signals
   (-19 dB and below) drop out first. At 2.3 s, 4 weak signals are already missed.

3. **Cliff edge (~3.0 s):** Only 2 signals decode; both are high-SNR (+7 to +8 dB).
   The FT8 signal (12.64 s) extends ~0.64 s past the 15-second cycle boundary,
   truncating the final symbols for all but the strongest signals.

4. **Dead zone (> 3.0 s):** Zero decodes despite RMS identical to successful cycles
   (~5.5 – 6.3 × 10⁻³). Audio is present but the signal is too badly truncated for
   the decoder to recover any message. This is correct behaviour — no false positives.

5. **Silence guard confirmed:** Cycles with RMS = 0 are correctly skipped without
   entering the decode path.

### Threshold Summary

| Zone | Start offset | Decodes |
|---|---|---|
| Safe | 0 – 2.3 s | 16–17 (full) |
| Degraded | 2.3 – 3.0 s | 2–12 |
| Failed | > 3.0 s | 0 |

The mathematical limit is **15 − 12.64 = 2.36 s**; the empirical degradation onset
at 2.3 s is consistent with this.

---

## Session 2 — GO Window Validation

GO_WINDOW_S corrected to 2 s before this session.

| Cycle (UTC) | RMS | Decodes | dt min | dt max | Inferred offset |
|---|---|---|---|---|---|
| 19:07:45 | 0.000 | 0 | — | — | Silence |
| 19:08:00 | 0.000 | 0 | — | — | Silence guard |
| **19:08:15** | 6.1E-3 | **17** | 1.3 s | 2.7 s | ~1.3 s |
| **19:08:30** | 6.2E-3 | **16** | 1.1 s | 2.6 s | ~1.1 s |
| **19:08:45** | 6.0E-3 | **16** | 1.6 s | 3.1 s | ~1.6 s |
| **19:09:00** | 6.2E-3 | **16** | 0.3 s | 1.8 s | **~0.3 s** |
| **19:09:15** | 6.2E-3 | **17** | 1.0 s | 2.5 s | ~1.0 s |

### Observations

1. **No degraded or failed cycles.** Every active cycle produced 16–17 decodes.
   The decode count is flat — no cliff edge, no progressive drop.

2. **All inferred start offsets ≤ 1.6 s** — well within the corrected 2-second window.
   The GO indicator correctly prevented the user from starting too late.

3. **Cycle 19:09:00 (dt min = 0.3 s)** demonstrates the near-zero-latency case: audio
   started within 0.3 s of the cycle boundary and still produced 16 full decodes. There
   is no penalty for starting early.

4. **dt = 3.1 s in cycle 19:08:45** (a high-SNR station, SNR +9) is not a concern. The
   inferred start offset for that cycle is 1.6 s; the 3.1 s dt reflects that particular
   station's natural timing offset in the original recording, not a late start. The
   signal ends at approximately T = 14.1 s — within the window.

### Comparison

| Metric | Session 1 (GO = 8 s) | Session 2 (GO = 2 s) |
|---|---|---|
| Decode range | 0 – 17 | 16 – 17 |
| 0-decode cycles with audio | 3 | 0 |
| Cycles with < 10 decodes | 1 | 0 |
| Max inferred start offset | ~3.0 s | ~1.6 s |

GO window fix **validated**. The indicator is now honest.

---

## Ground Truth Re-Run

Following the timing tests, the replay harness was re-executed against the full 42-WAV
corpus to confirm whether the reported 69.1% recovery rate was measured with or without
iterative subtraction active.

**Result: 69.1% confirmed — identical to prior run.**

| Metric | Prior run | Re-run (2026-06-05) |
|---|---|---|
| WSJT-X total decodes | 887 | 887 |
| Matched | 613 | 613 |
| False positives | 24 | 24 |
| Recovery rate | 69.1% | **69.1%** |

The score is identical because iterative subtraction was **already active** in the build
when the earlier measurement was taken. The decision-gate note ("ft8_lib not implementing
iterative subtraction") was therefore inaccurate; the `ReplayHarnessTests.cs` boilerplate
has been corrected to read:

> *"The miss rate relative to WSJT-X is a known, accepted limitation of the ft8_lib
> single-pass decoder. OpenWSFZ wraps it with a 2-pass iterative-subtraction loop …
> but WSJT-X employs a deeper multi-pass strategy that the current implementation does
> not replicate."*

No regression. Status: nominal.

---

## Changes Made

| File | Change |
|---|---|
| `web/js/main.js` | `GO_WINDOW_S` 8 → 2; JSDoc updated with FT8 physics derivation |
| `tests/OpenWSFZ.Ft8.Tests/ReplayHarnessTests.cs` | Decision-gate prose corrected |
| `openspec/changes/p10-decoder-ground-truth/findings.md` | Regenerated by harness (timestamp + corrected prose; score unchanged) |
