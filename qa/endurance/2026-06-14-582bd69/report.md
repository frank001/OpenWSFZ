# Endurance Test Report — 2026-06-14

## 1. Study hypothesis

**What is this run testing?**
Continuous live operation of OpenWSFZ against real off-air 40 m FT8 signals over an extended period (~2h04m), with WSJT-X running in parallel as reference. Primary objectives: (a) validate shim 20260012 (D-003/D-004 local noise floor fix) under live multi-signal conditions, extending the 2026-06-13 soak; (b) confirm stability over a longer session. Secondary: matched-pair SNR delta analysis to quantify whether the local noise floor fix reduces the D-004 live bias measured in the previous run (−6.32 dB).

**Null hypotheses:**
- H₀-1: OpenWSFZ completes the full session without any unrecoverable pipeline failure
- H₀-2: D-003 (intermittent SNR under-report) is not present under shim 20260012 (local noise floor fix)
- H₀-3: D-004 SNR bias (multi-signal) passes ±2.0 dB threshold under shim 20260012
- H₀-4: D-004 SNR bias is uniform across the audio frequency range (no frequency-dependent component)

**Defects under observation:** D-001, D-003, D-004, D-005, D-006 (new — first production session with shim 20260012)

**What constitutes a meaningful result?**
- Stability: zero unrecoverable gaps > 30 s; no process crash
- D-003: incidence of matched-pair deltas ≤ −10 dB compared to previous run (2.1% at shim 20260010)
- D-004: mean matched-pair SNR delta vs WSJT-X; threshold ±2.0 dB; σ ≤ 4.0 dB
- D-004 frequency profile: per-200 Hz bin means to identify whether the fix is frequency-uniform

---

## 2. Data summary

| Field | Value |
|---|---|
| Date | 2026-06-13/14 UTC (local 2026-06-14) |
| OpenWSFZ SHA | `582bd69` |
| ft8_lib shim | 20260012 (D-003/D-004 local noise floor fix) |
| Session start (UTC) | 2026-06-13 23:15:00 |
| Session end (UTC) | 2026-06-14 01:18:30 (last complete cycle before crash) |
| Crash cycle (UTC) | 2026-06-14 01:18:45 — process-terminating AV (D-006) |
| Duration (productive) | 2h03m30s (495 cycles) |
| Total 15-second cycles | 495 (OpenWSFZ completed) / 496 (WSJT-X, incl. crash cycle) |
| Band | 40 m (7.074 MHz) |
| Audio device | USB Audio CODEC |
| WSJT-X version | Parallel reference decoder; ran uninterrupted |

**Corpus:** Live off-air 40 m FT8 reception. WAV recordings saved by WSJT-X (`20260614_live_run/save/`, 2,171 files); git-ignored per NFR-021 (real callsigns). OpenWSFZ `ALL.TXT`: 9,676 lines. WSJT-X `ALL.TXT`: 61,025 lines (full session including post-crash). Crash trace: `20260614_live_run/CRASH.txt`.

**Matched-pair analysis window:** 495 overlapping cycles (23:15:00 → 01:18:30 UTC). 8,709 signal pairs matched on exact message text within the same cycle.

**Acceptance thresholds:**
- SNR bias: ±2.0 dB
- SNR spread (σ): ≤ 4.0 dB
- Stability: 0 unrecoverable gaps > 30 s; 0 process crashes
- D-003 improvement criterion (informational): incidence lower than 2.1% baseline (shim 20260010, previous run)

---

## 3. Results

### 3.1 Stability

OpenWSFZ ran cleanly for 495 cycles (2h03m30s). No decode gaps, no audio loss, no silent cycles. All 495 overlapping cycles produced output.

At 2026-06-14 01:18:45 UTC (local 03:18:45), OpenWSFZ suffered a fatal `0xC0000005` access violation in `ft8_decode_all` while processing cycle `260614_011845`. The process was killed by the runtime. WSJT-X was unaffected (separate process) and ran uninterrupted until 08:16:45 UTC.

Stack trace (from `CRASH.txt`):
```
Fatal error. 0xC0000005
  at OpenWSFZ.Ft8.Interop.Ft8LibInterop.NativeDecodeAll(...)
  at OpenWSFZ.Ft8.Interop.Ft8LibInterop.DecodeAll(Single[])
  at OpenWSFZ.Ft8.Ft8Decoder+<>c__DisplayClass7_0.<DecodeAsync>b__0()
```

The crashing cycle contained 34 signals (WSJT-X), SNR −24 to +15 dB, maximum audio frequency 2704 Hz. Signal count and frequency profile are unremarkable relative to the preceding four cycles (37–42 signals, max 2827 Hz). No obvious trigger has been identified.

**Containment:** SEH wrapper added to `ft8_decode_all` in shim 20260013 (`fix/seh-av-containment`, merged `a29c27c`). Future occurrences will skip the cycle and log a WARNING rather than terminating the process.

**H₀-1: REJECTED — process crash at 01:18:45 UTC.**

### 3.2 Decode rate

| Metric | Value |
|---|---|
| OpenWSFZ total decodes (495 cycles) | 9,676 |
| WSJT-X total decodes (overlap window) | 15,133 |
| True positives (both decoded) | 8,709 |
| False negatives (WSJT-X only) | 6,424 |
| False positives (OpenWSFZ only) | 967 |
| OpenWSFZ decode rate vs WSJT-X | **57.5%** |
| OpenWSFZ mean decodes / cycle | 19.5 (max 30) |
| WSJT-X mean decodes / cycle | 30.6 (max 44) |
| Per-cycle decode count Pearson r | 0.690 |

FN rate by WSJT-X SNR (selected bands):

| WSJT-X SNR | Recovery rate |
|---|---|
| ≤ −19 dB | 14–29% |
| −18 to −12 dB | 27–49% |
| −11 to 0 dB | 49–62% |
| +1 to +10 dB | 63–72% |
| +11 to +18 dB | 79–93% |
| ≥ +20 dB | 88–100% |

The 967 false positives (10.0% of OpenWSFZ output) have median SNR −4.0 dB, std dev 9.6 dB; 26% are below −10 dB. Some are plausible weak decodes that WSJT-X missed; the remainder are the known D-001 false-positive floor.

### 3.3 D-003 — SNR under-report (shim 20260012)

| Metric | Shim 20260010 (2026-06-13) | Shim 20260012 (this run) |
|---|---|---|
| Matched pairs | ~11,190 | 8,709 |
| Incidence (delta ≤ −10 dB) | 2.1% (235 events) | **12.1% (1,054 events)** |
| Worst observed delta | −29 dB | −37 dB |

D-003 incidence increased substantially relative to the previous run despite the local noise floor fix. Analysis of the worst cases reveals two distinct mechanisms:

**Mechanism 1 — low-frequency sideband contamination (primary driver):** Signals below 600 Hz show extreme under-reporting (see §3.4). At 100–199 Hz, `compute_local_noise_floor_db` samples left-sideband bins near DC (bins 0–31 at 6.25 Hz/bin). These bins carry elevated energy from DC offset and 50/60 Hz harmonic interference in the audio chain. The median of the sideband histogram is inflated → local noise floor estimate inflated → SNR negative. Five of the ten worst D-003 cases (delta ≤ −31 dB) occur at 352–353 Hz and 199 Hz.

**Mechanism 2 — adjacent-signal contamination at high frequency:** Five of the ten worst cases occur at a single signal near 2499 Hz, recurring over approximately 10 minutes (timestamps 001415–002015 UTC), with WSJT-X SNR +12 to +18 dB and OpenWSFZ SNR −16 to −24 dB. The right sideband (K=32 bins, 200 Hz window) of a 2499 Hz signal spans bins 408–440 (2550–2750 Hz). A co-located strong station in this window would dominate the histogram and inflate the local noise floor estimate for the target signal.

The local noise floor approach is inherently susceptible to these contamination modes. The global noise floor (shim 20260010) is unaffected by individual signals because it takes the median of the entire waterfall.

**H₀-2: REJECTED — D-003 is active under shim 20260012, and at higher incidence than shim 20260010.**

### 3.4 D-004 — SNR bias, multi-signal (shim 20260012)

| Metric | Value | Threshold | Verdict |
|---|---|---|---|
| Mean delta (8,709 pairs) | −3.78 dB | ±2.0 dB | FAIL |
| Median delta | −3.00 dB | — | — |
| Std dev | 5.41 dB | ≤ 4.0 dB | FAIL |
| Range | −37 to +14 dB | — | — |

Compare: shim 20260010 live run (2026-06-13) showed −6.32 dB. The local noise floor fix improves the overall bias by approximately 2.5 dB. The fix is partially effective but does not meet the ±2.0 dB threshold.

**Frequency-dependent bias profile:**

| Freq range | N | Mean Δ (dB) | Verdict |
|---|---|---|---|
| 100–199 Hz | 42 | −17.0 | FAIL — severe |
| 200–399 Hz | 354 | −11.0 | FAIL — severe |
| 400–599 Hz | 595 | −8.3 | FAIL |
| 600–799 Hz | 753 | −6.9 | FAIL |
| 800–999 Hz | 769 | −3.4 | FAIL |
| **1000–1199 Hz** | **518** | **−1.4** | **PASS** |
| **1200–1399 Hz** | **759** | **+0.2** | **PASS** |
| **1400–1599 Hz** | **980** | **−0.5** | **PASS** |
| 1600–1799 Hz | 714 | −3.4 | FAIL |
| 1800–1999 Hz | 781 | −3.5 | FAIL |
| 2000–2199 Hz | 761 | −3.5 | FAIL |
| 2200–2399 Hz | 646 | −4.9 | FAIL |
| 2400–2599 Hz | 360 | −6.1 | FAIL |
| 2600–2799 Hz | 656 | −2.0 | FAIL |

The local noise floor fix achieves the ±2.0 dB threshold **only in the 1000–1599 Hz mid-band**. The bias degrades monotonically toward DC below 1000 Hz (DC/hum contamination) and is consistently negative above 1600 Hz (adjacent-signal contamination or audio chain rolloff at higher frequencies).

**H₀-3: REJECTED — D-004 bias is −3.78 dB overall (FAIL).**

**H₀-4: REJECTED — D-004 bias is strongly frequency-dependent. Mid-band (1000–1599 Hz) passes; band extremes fail severely.**

### 3.5 D-005 — False-positive guard (new finding: root cause identified)

30 filtered events observed across 7 unique message patterns. All follow the structure `<HASH> CALLSIGN ` with a trailing space.

**Root cause:** `ft8_lib` pads its message buffer to fixed width with spaces before the null terminator. A Type 4 hash message such as `<HASH> CALLSIGN` is returned as `<HASH> CALLSIGN \0` in `FT8Result.message`. The C# marshaller preserves the trailing space. `IsPlausibleMessage` counts two spaces, enters the three-token branch, extracts the last token as the empty string, finds no recognisable field, and returns `false`.

The filter is functioning correctly; the input is malformed. The fix is a single `.TrimEnd()` call on `nr.Message` before deduplication and plausibility checking in `Ft8Decoder.DecodeAsync`.

Impact: 30 suppressed valid decodes in 2h04m (≈ 14.5 per hour).

### 3.6 D-006 — Native access violation (new defect)

First production occurrence of a process-terminating AV in `ft8_decode_all`. The crash occurred during cycle `260614_011845` (34 signals, max frequency 2704 Hz). All sideband bounds in `compute_local_noise_floor_db` are code-verified as correctly clamped (lines 609, 614 in `ft8_shim.c`). No memory safety defect has been identified in static analysis. Root cause is unknown.

The WAV file for the crashing cycle is preserved at `20260614_live_run/save/260614_011845.wav` (local, git-ignored). This constitutes a reproducibility asset.

---

## 4. Summary verdict table

| Metric | Value | Threshold | Verdict |
|---|---|---|---|
| Stability — no unrecoverable gap > 30 s | 0 gaps in 2h03m30s | 0 | **PASS** |
| Stability — no process crash | 1 crash at 01:18:45 UTC | 0 | **FAIL** |
| Decode performance | All 495 cycles completed before crash | < 15,000 ms | **PASS** |
| D-003 incidence (delta ≤ −10 dB) | 12.1% (1,054 events) | improvement over 2.1% baseline | **WORSE** |
| D-004 SNR bias (mean) | −3.78 dB | ±2.0 dB | **FAIL** |
| D-004 SNR spread (σ) | 5.41 dB | ≤ 4.0 dB | **FAIL** |
| D-004 mid-band bias (1000–1599 Hz) | −0.5 to +0.2 dB | ±2.0 dB | **PASS** |
| D-004 bias uniformity (frequency) | −17.0 to +0.2 dB across band | uniform | **FAIL** |
| D-005 events | 30 (root cause identified) | 0 | **FAIL** |
| Decode recovery vs WSJT-X | 57.5% | informational | — |

**Overall verdict: FAIL** (process crash; D-003/D-004 active; D-005 root cause identified but not fixed)

---

## 5. Recommendations

**D-006 (#16 — not yet filed):** File GitHub issue. Before the next live run, attach ProcDump (`procdump -e 1 -ma -w OpenWSFZ.exe`) — WER LocalDumps is configured but will not fire because the SEH wrapper (shim 20260013) prevents the crash from reaching Windows error handling. Replay `260614_011845.wav` through VB-CABLE with ProcDump running to attempt crash reproduction and capture the faulting instruction. Root cause cannot be determined without a crash dump.

**D-003 / D-004 (#11, #12):** The local noise floor approach (shim 20260012) improves the overall bias from −6.32 dB to −3.78 dB and achieves ±2.0 dB in the 1000–1599 Hz mid-band. However it introduces new failure modes at the band extremes. Two distinct mechanisms are now identified: (a) DC/hum contamination of left-sideband bins for low-frequency signals; (b) adjacent strong-signal contamination of the K=32 sideband window in dense spectrum. The developer should evaluate: (1) widening K beyond 32 bins to reduce contamination probability; (2) excluding low-frequency bins (< 16, i.e. < 100 Hz) from the sideband histogram; (3) a higher percentile (e.g. 25th) instead of median to reduce susceptibility to contaminating peaks. Any change requires S1 re-run and a repeat endurance soak. Note: NS-001 trigger condition (b) (D-003/D-004 fix merged → re-run S1) remains outstanding against shim 20260012.

**D-005 (#15):** Root cause confirmed. Fix is one line: apply `.TrimEnd()` to `nr.Message` in `Ft8Decoder.DecodeAsync` before deduplication and before `IsPlausibleMessage`. Low risk; no shim rebuild required. Recommend fixing in the next managed-layer change.
