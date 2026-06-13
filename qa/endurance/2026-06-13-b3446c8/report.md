# Endurance Test Report — 2026-06-13

## 1. Study hypothesis

**What is this run testing?**
Continuous live operation of OpenWSFZ against real off-air FT8 signals over an extended period (~1h40m), with WSJT-X running in parallel as reference. The primary objective is stability: does the application run without crashes, hangs, or silent audio loss for a sustained session? Secondary objectives are to observe D-003 and D-004 under live multi-signal conditions (previously characterised only via synthetic S1–S8 and corpus S6 replays).

**Null hypotheses:**
- H₀-1: OpenWSFZ completes the full session without any unrecoverable pipeline failure
- H₀-2: D-003 (SNR under-report) does not manifest in live conditions
- H₀-3: D-004 (SNR bias, multi-signal) does not manifest in live conditions

**Defects under observation:** D-001, D-003, D-004

**What constitutes a meaningful result?**
- Stability: zero unrecoverable gaps > 30 s in the productive decode period (18:27–20:09 UTC)
- D-003: presence/absence of SNR values below −24 dB (the FT8 theoretical floor), confirmed by matched-pair comparison with WSJT-X
- D-004: matched-pair SNR delta vs WSJT-X; threshold ±2.0 dB

---

## 2. Data summary

| Field | Value |
|---|---|
| Date | 2026-06-13 |
| OpenWSFZ SHA | `b3446c8` |
| ft8_lib shim | 20260010 (H4 baseline) |
| Session start (UTC) | 18:27:15 |
| Session end (UTC) | 20:08:45 |
| Duration (productive) | 1h41m30s |
| Total 15-second cycles | 406 (OpenWSFZ) / 407 (WSJT-X) |
| Audio device | USB Audio CODEC → `Microphone (2- USB Audio CODEC )` |
| WSJT-X version | (see `wsjt-version.txt` in corpus study directories) |

**Band structure:**

| Phase | UTC | Band | OpenWSFZ freq | WSJT-X freq | Comparable |
|---|---|---|---|---|---|
| 1 | 18:27–19:36 | 20m | 14.074 MHz | 14.074 MHz | Yes |
| 2 | 19:36–20:09 | 40m | 7.074 MHz (config entry was 70.740 — typo) | 7.074 MHz | Yes |

**Corpus:** Live off-air FT8 reception. WAV recordings git-ignored (real callsigns, NFR-021). Source files: `20260613_live run 1h40_items/` (local only).

**Acceptance thresholds (carried from prior studies):**
- SNR bias: ±2.0 dB
- SNR spread (σ): ≤ 4.0 dB
- Gap tolerance: 0 unrecoverable gaps > 30 s in productive period
- D-003 floor: 0 decodes with SNR ≤ −30 dB (WSJT-X produces 0 such values)

---

## 3. Results

### 3.1 Stability

No gaps exceeding 30 seconds were present in the productive decode period (18:27–20:09 UTC). Both decoders produced output in every 15-second cycle throughout.

The application handled a mid-session band change (19:36 UTC) cleanly: one cycle was correctly discarded (`Cycle 19:36:30: discarded — dial frequency changed from 14.074 to 70.740 MHz during capture window`) and decodes resumed from the following cycle without pipeline restart.

Shutdown at 20:09 UTC was graceful (`RecordingStopped (graceful)`; 98,397 audio chunks received).

**H₀-1: FAIL TO REJECT — no unrecoverable failure in the productive period.**

### 3.2 Decode rate

| Phase | OpenWSFZ decodes | WSJT-X decodes | OpenWSFZ avg/cycle | WSJT-X avg/cycle | Recovery |
|---|---|---|---|---|---|
| Phase 1 (20m) | 5,765 | 10,871 | 20.8 | 39.4 | 50.5% |
| Phase 2 (40m) | 2,926 | 5,006 | 22.7 | 38.2 | 55.7% |
| **Combined** | **8,691** | **15,877** | **21.4** | **39.0** | **52.1%** |

Decode performance (from log): mean 46 ms per cycle, max 80 ms, min 37 ms. Zero-decode cycles: 0.

Decode rate is consistent with D-001 (co-channel / weak-signal gap). No improvement is expected or observed at this shim level.

### 3.3 D-003 — SNR under-report

| Metric | Value |
|---|---|
| OpenWSFZ decodes with SNR ≤ −30 dB (Phase 1, 20m) | 113 (2.0%) |
| OpenWSFZ decodes with SNR ≤ −30 dB (Phase 2, 40m) | 65 (2.2%) |
| WSJT-X decodes with SNR ≤ −30 dB (all) | 0 (0.0%) |
| Matched-pair confirmations (same cycle + message; OpenWSFZ SNR < −24 dB, WSJT-X normal) | 235 |
| Largest observed delta | −29 dB (OpenWSFZ −43 dB vs WSJT-X −14 dB) |
| SNR value range of anomalies | −30 to −44 dB |
| D-003 incidence by 15-min window | 1.4% → 2.5% (slight upward drift) |

The defect is active on both bands at consistent rates. The 235 matched-pair events — where WSJT-X reports a normal SNR for an identical message in the same cycle — definitively confirm that these are SNR *reporting* errors, not decode failures. The underlying message is decoded correctly.

**H₀-2: REJECTED — D-003 is active in live conditions.**

### 3.4 D-004 — SNR bias, multi-signal

| Condition | Matched pairs | Mean delta (OpenWSFZ − WSJT-X) | σ | Verdict |
|---|---|---|---|---|
| All Phase 1 matched pairs | 5,485 | −6.32 dB | 9.01 dB | FAIL |
| Excluding D-003 contaminated (O SNR < −24 dB) | 5,250 | −5.68 dB | 8.57 dB | FAIL |
| All Phase 2 matched pairs | 2,786 | −6.91 dB | 8.53 dB | FAIL |

Both phases exceed the ±2.0 dB threshold. The bias is consistent across bands, confirming D-004 is a systematic property of the implementation rather than a band-specific artefact. Even excluding D-003-contaminated pairs, the bias far exceeds threshold.

Compare: S6 corpus replay (synthetic, VB-CABLE) showed −3.091 dB. Live conditions show −6.3 to −6.9 dB. The difference likely reflects live signal density and diversity vs the controlled S6 corpus.

**H₀-3: REJECTED — D-004 is active and consistent across bands in live conditions.**

### 3.5 D-005 — False-positive guard (new finding)

27 decode suppression events were observed in the log (`filtered implausible message`). All share the pattern: hashed first callsign (`<...>` or cache-resolved) + special-format second callsign + absent third field. Suppressed stations were confirmed active by WSJT-X. Full characterisation in GitHub issue #15.

Yield impact if fixed: +27 decodes / 102 min = +0.17 pp recovery rate improvement (52.09% → 52.26%). **Low priority.**

### 3.6 Hashed callsign `<...>` volume

OpenWSFZ ALL.TXT contains 454 unresolved-hash placeholders vs 167 in WSJT-X ALL.TXT (2.7× ratio). Expected — WSJT-X has a longer operating history and larger pre-populated hash cache. Impact: the 52.1% recovery figure is a modest underestimate; some matched signals appear as `<...> X` in OpenWSFZ vs `<CALLSIGN> X` in WSJT-X and do not match on message text.

---

## 4. Summary verdict table

| Metric | Value | Threshold | Verdict |
|---|---|---|---|
| Stability — no unrecoverable gap > 30 s | 0 gaps | 0 | **PASS** |
| Band change handling | 1 cycle discarded, clean recovery | — | **PASS** |
| Shutdown | Graceful | — | **PASS** |
| Decode performance (mean elapsed) | 46 ms | < 15,000 ms | **PASS** |
| D-003 SNR under-report incidence | 2.1% of decodes | 0% | **FAIL** |
| D-004 SNR bias (matched-pair, all) | −6.32 dB | ±2.0 dB | **FAIL** |
| D-004 SNR bias (D-003 excluded) | −5.68 dB | ±2.0 dB | **FAIL** |
| D-004 SNR spread (σ, Phase 1) | 9.01 dB | ≤ 4.0 dB | **FAIL** |
| Decode recovery vs WSJT-X | 52.1% | informational | — |

**Overall verdict: FAIL** (D-003 and D-004 active; stability objectives met)

---

## 5. Recommendations

**D-003 (#11):** Soak test objective is now satisfied. This run provides 235 matched-pair events with exact cycle timestamps and decoded messages that can be used to isolate the trigger condition in `ft8_shim.c`. Recommended next step: instrument `signal_db` computation against the specific (timestamp, frequency-offset) pairs from this run to determine whether the error occurs in the row-index lookup or upstream in the waterfall.

**D-004 (#12):** The live matched-pair bias (−6.32 dB) is roughly twice the S6 corpus figure (−3.091 dB). The SNR fix (shim −26.5 dB) was calibrated on a single-signal synthetic baseline (S1); it does not generalise. Recommended next step: root-cause analysis in `ft8_shim.c` — the single-signal calibration offset likely interacts badly with the waterfall noise floor estimate under multi-signal load.

**D-005 (#15):** Low priority. Yield is negligible (+0.17 pp). Fix when convenient; no urgency.
