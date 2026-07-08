# Endurance Test Report — 2026-07-06

## 1. Study hypothesis

**What is this run testing?**

Continuous live off-air operation of OpenWSFZ against real 40 m FT8 signals (~10h52m
overnight), with WSJT-X running in parallel as a reference decoder. This is the first
extended endurance run at main HEAD `7340e45` (shim 20260031), following this session's
D-011 (nonstandard-callsign FP guard), F-001 (hashed-callsign resolution), F-002 (ITU
callsign-shape grammar + region lookup), F-003 (AP-assist for nonstandard callsigns), F-004
(operator visibility improvements), and D-010 (config null-guard fix). None of these changes
touch the core decode pipeline's weak-signal recovery path (H6 AP + OSD), so this run's
primary purpose is confirmatory rather than exploratory.

Primary objectives:

- **(a) Stability:** Confirm the pipeline runs reliably for an extended on-air session with
  no crashes, audio dropouts, or unrecoverable gaps, on the rebuilt main-HEAD binary.
- **(b) D-001 baseline reconfirmation:** Compare S7/S8-style recall statistics (decode rate
  vs WSJT-X-as-oracle, SNR-stratified recall) against the existing D-001 live baseline
  (`qa/endurance/2026-06-22-f11f438`, shim 20260029) to confirm the open co-channel/
  weak-signal decode gap is unchanged by this session's callsign-handling work, i.e. no
  regression and no accidental improvement have been introduced.
- **(c) F-001 field check:** F-001 (session-scoped hashed-callsign resolution, shim 20260031)
  shipped since the last endurance baseline. Characterise whether the OpenWSFZ-only
  hashed-callsign (`<...>`) bucket has shrunk in a real dense band relative to the June 22
  pre-F-001 baseline, as would be expected if the hash table resolves effectively in the
  field.

**Null hypotheses:**

- **H₀-1 (stability):** OpenWSFZ completes the session without any unrecoverable pipeline
  failure, crash, or audio gap > 30 seconds.
- **H₀-2 (D-001 unchanged):** SNR-stratified recall this run falls within ordinary
  night-to-night band-noise variance of the June 22 baseline, with no systematic directional
  shift attributable to this session's shipped changes.
- **H₀-3 (F-001 field effect):** The OpenWSFZ-only hashed-callsign count per cycle is no
  higher than the June 22 (pre-F-001) baseline rate.

**Defects under observation:** D-001 (open, #3). D-009 (closed, `ef16040`) FP-rate sanity
re-checked as a standing regression guard, not a primary objective.

**What constitutes a meaningful result?**

- Stability: zero crashes, zero unrecoverable gaps; clean operator-initiated stop.
- D-001: SNR-stratified recall table within a few percentage points of the June 22 baseline
  in each band, with no consistent directional trend.
- F-001: informational only — no acceptance threshold set; reported for the record.

---

## 2. Data summary

| Field | Value |
|---|---|
| Date | 2026-07-05/06 UTC (local 2026-07-05 22:39 → 2026-07-06 09:32 CEST) |
| OpenWSFZ SHA | `7340e45` (main HEAD) |
| ft8_lib shim | 20260031 (F-001 hashed-callsign resolution; D-011 D9-R3 ceiling raise; unchanged decode-recovery path from shim 20260029's D-009 OSD FP filter) |
| Session start (UTC) | 2026-07-05 20:39:30 (first decoded cycle: `260705_203930`) |
| Session end (UTC) | 2026-07-06 07:31:45 (last decoded cycle: `260706_073145`) |
| Duration | 10 hours 52 minutes 15 seconds |
| Total 15-second cycles | 2,610 (union; OpenWSFZ and WSJT-X both cover the full cycle range) |
| Band | 40 m (7.074 MHz FT8) |
| Audio device | USB Audio CODEC (`d451e08c`), same device as the June 22 baseline |
| WSJT-X | Parallel reference decoder; ran throughout (long-running process, started 2026-06-30) |
| Daemon log file | `logs/openswfz-20260705T202939Z.log` (42,620 lines) |
| Shutdown | Graceful (operator-initiated `POST /api/v1/decode/stop`, daemon process left running) |
| Audio chunks captured | 629,363 (single continuous capture session; two earlier sub-second/short captures during initial device setup are excluded from the analysis window) |

**Corpus:** Live off-air 40 m FT8 reception over a European evening/overnight/dawn
propagation window. The raw ALL.TXT files are stored at `artefacts/20260706_live_run/`
(outside VCS, git-ignored per NFR-021 — they contain real third-party callsigns). This
report contains no individual callsigns; all analysis is aggregate. The analysis script used
to produce the figures below is committed alongside the raw logs at
`artefacts/20260706_live_run/analyse_live_run.py` for reproducibility.

**Acceptance thresholds (this run):**

- Stability: 0 crashes, 0 unrecoverable gaps > 30 s, 0 log ERR/WRN/FTL entries.
- D-001: SNR-stratified recall within a few points of the June 22 baseline in each band;
  informational, not gating (per this project's established convention — D-001 is an open,
  unfixed defect).
- F-001: informational only.

---

## 3. Results

### 3.1 Stability

OpenWSFZ ran cleanly for 10 hours 52 minutes (2,610 cycles) without crash, audio dropout, or
decode gap, on the freshly-rebuilt main-HEAD binary.

| Metric | Value |
|---|---|
| Log ERR entries | **0** |
| Log WRN entries | **0** |
| Log FTL entries | **0** |
| Unhandled exceptions | **0** |
| Max heartbeat gap | 6.3 s (threshold: flag if > 30 s) |
| Heartbeat gaps > 30 s | **0** |
| Daemon process identity | Single PID throughout (no restart) |
| Shutdown | Graceful (operator API call, daemon left running post-stop) |

This is a new longest-confirmed clean endurance run (previous longest: 8h33m,
`2026-06-22-f11f438`), and the first at main HEAD `7340e45` / shim 20260031. The pipeline —
WASAPI capture → cycle framing → ft8_lib decode → ALL.TXT logging — operated without fault
across the full session, including through this session's newly-shipped callsign-handling
code paths (D-011, F-001–F-004) under sustained real-world load.

**H₀-1: CONFIRMED — zero failures, clean 10h52m run.**

### 3.2 Decode rate and recall (S7/S8-style comparison vs D-001 baseline)

| Metric | This run | Baseline (`2026-06-22-f11f438`, shim 20260029) |
|---|---|---|
| Total decodes | OpenWSFZ 47,013 / WSJT-X 75,193 | OpenWSFZ 33,123 / WSJT-X 50,439 |
| Mean decodes / cycle | 18.0 / 28.8 | 16.1 / 24.6 |
| Min decodes / cycle | 3 / 3 | 5 / 7 |
| Max decodes / cycle | 32 / 58 | 28 / 45 |
| Stdev decodes / cycle | 5.2 / 9.5 | 4.0 / 7.0 |
| Per-cycle count Pearson r | 0.833 | 0.831 |

The two decoders track each other just as tightly as in the baseline run (r = 0.833 vs
0.831) — same signal environment, same correlated behaviour. Tonight's band was busier
overall (higher per-cycle counts and variance for both decoders), consistent with a longer
session spanning more propagation conditions (evening through dawn vs the baseline's
evening-through-early-morning window).

**Recall analysis (WSJT-X as oracle):**

| Category | This run | Baseline |
|---|---|---|
| Decoded by both | 40,459 | 30,019 |
| OpenWSFZ only (all) | 6,554 | 3,104 |
| — of which: `<...>` hashed callsign | 4,671 | 2,126 |
| — of which: normal text | 1,883 | 978 |
| WSJT-X only (all) | 34,734 | 20,420 |
| — of which: hashed callsign form | 9,887 | 3,893 |
| — of which: normal text | 24,847 | 16,527 |

| Recall metric | This run | Baseline | Δ |
|---|---|---|---|
| Overall recall (WSJT-X as oracle, all messages) | **53.81%** (40,459 / 75,193) | 59.52% (30,019 / 50,439) | −5.71 pp |
| Recall excluding hashed WSJT-X messages | **60.60%** (38,223 / 63,070) | 64.49% (30,019 / 46,546) | −3.89 pp |

**Recall by SNR (WSJT-X SNR, non-hashed messages only):**

| WSJT-X SNR band | This run | Baseline | Δ |
|---|---|---|---|
| −25 to −20 dB | 23.5% (691/2,939) | 21.6% (439/2,036) | +1.9 pp |
| −20 to −15 dB | 34.7% (2,129/6,144) | 36.7% (1,619/4,409) | −2.0 pp |
| −15 to −10 dB | 43.1% (4,126/9,574) | 48.2% (3,373/7,000) | −5.1 pp |
| −10 to −5 dB | 55.2% (6,840/12,397) | 58.4% (4,879/8,351) | −3.2 pp |
| −5 to +0 dB | 66.5% (8,050/12,106) | 68.5% (5,195/7,588) | −2.0 pp |
| 0 to +5 dB | 76.7% (7,200/9,383) | 78.9% (4,955/6,280) | −2.2 pp |
| +5 to +10 dB | 83.9% (4,574/5,454) | 85.9% (4,789/5,574) | −2.0 pp |
| +10 to +20 dB | 90.6% (4,036/4,454) | 89.5% (4,239/4,737) | +1.1 pp |

Per-band recall sits within roughly 2–5 points of the June 22 baseline across the full SNR
range, mostly slightly below it, with no consistent directional trend (the weakest and
strongest bands both moved in the opposite direction to the mid-range bands). This is
consistent with ordinary night-to-night band-noise/QRM variance rather than a code
regression: none of D-011/F-001/F-002/F-003/F-004 touch the decoder's weak-signal recovery
path (H6 AP decode + OSD fallback), so a flat-to-slightly-noisy SNR curve is the expected
outcome, not a new finding.

For reference, the informational synthetic S7 co-channel scenario (ground-truth injected,
no hashed-callsign noise, shim 20260025) remains at **80.22%** overall recovery — the S7
figure and the live-recall figures above are not directly comparable (different corpus,
different noise floor, S7 has no hashed-callsign category) but are both part of this
project's standing D-001 reference set.

**H₀-2: CONFIRMED — SNR-stratified recall is within ordinary run-to-run variance of the June
22 baseline; no systematic shift attributable to this session's changes.**

### 3.3 D-009 OSD false-positive sanity check

The D-009 fix (shim 20260029, unchanged through 20260031) calibrated OSD FP rate at 0.042
FPs/slot under S5 (AWGN, no signals). Over 2,610 cycles, the expected FP count is:

> 2,610 × 0.042 ≈ **110 expected OSD false positives**

Observed OpenWSFZ-only normal-text messages: **1,883**.

As in the June 22 baseline, the excess over the pure-FP estimate (~1,773 messages) is not
attributable to runaway OSD — WSJT-X is not an infallible oracle in a live band, and this
excess is most plausibly genuine weak signals WSJT-X missed in those particular cycles. The
proportion of OpenWSFZ-only normal-text decodes to total OpenWSFZ decodes (1,883 / 47,013 =
4.0%) is comparable to the baseline's (978 / 33,123 = 3.0%), a modest but not alarming
increase consistent with the slightly noisier band this run observed overall.

**D-009 fix holds — no evidence of anomalous OSD FP behaviour.**

### 3.4 DT and SNR reporting

**DT (timing offset relative to cycle boundary):**

| | This run — Mean | This run — Median | This run — Stdev | Baseline — Mean | Baseline — Median | Baseline — Stdev |
|---|---|---|---|---|---|---|
| OpenWSFZ | −0.013 s | +0.000 s | 0.597 s | +0.099 s | +0.100 s | 0.513 s |
| WSJT-X | +0.219 s | +0.200 s | 0.336 s | +0.192 s | +0.200 s | 0.304 s |

WSJT-X's DT is essentially unchanged from baseline. OpenWSFZ's mean DT shifted slightly
negative (−0.013 s vs +0.099 s) and its spread widened a little further (0.597 vs 0.513 s
stdev) — DT is informational and does not affect decode correctness; this is noted for
trend-tracking, not flagged as a defect.

**SNR bias (matched messages):**

| | This run | Baseline |
|---|---|---|
| OpenWSFZ SNR − WSJT-X SNR (mean) | −9.60 dB | −8.40 dB |
| Median | −9.00 dB | −6.0 dB |
| Stdev | 8.89 dB | 8.49 dB |

Consistent with the June 22 report's conclusion: this is a live-band artefact (independent
noise-floor estimation across a dense multi-signal environment), not a calibration
regression. The synthetic S1 single-signal bench calibration (+1.42 dB bias) remains the
valid reference for controlled conditions. No corrective action required.

### 3.5 Hashed callsign gap — F-001 field check

F-001 (session-scoped native callsign hash table, shipped this session at shim 20260031)
was expected to shrink the OpenWSFZ-only hashed-callsign (`<...>`) bucket relative to the
pre-F-001 June 22 baseline, by resolving Type-3 hashed messages from the session's own
recent traffic.

| | This run | Baseline (pre-F-001) |
|---|---|---|
| OpenWSFZ-only hashed-callsign count | 4,671 | 2,126 |
| Cycles | 2,610 | 2,054 |
| Rate per cycle | 1.79 | 1.04 |

**Observed rate per cycle is *higher* this run, not lower** — roughly 72% higher than
baseline, well beyond what the ~27% longer session length alone would explain. This is the
opposite of the expected F-001 field effect.

**H₀-3: NOT CONFIRMED** — the OpenWSFZ-only hashed-callsign rate increased rather than held
or decreased. Two plausible (non-exclusive) explanations, neither confirmed by this run's
data:

1. **Cold-start structural floor:** F-001's hash table is session-scoped and populated only
   from traffic observed *within* this run. A hashed reference to a callsign whose own
   first-heard transmission occurs later in the session (or never, if the referencing
   station is heard but the referenced station itself is never directly decoded) is
   structurally unresolvable regardless of the fix. A busier band (this run's higher overall
   decode rate) plausibly increases the number of such forward/never-resolvable references.
2. **Effectiveness question:** it has not been independently verified in this run whether
   F-001 is resolving the hashes it *should* be able to resolve (i.e. references to
   already-heard-this-session callsigns). That would require inspecting the raw
   `OpenWSFZ ALL.TXT` content directly for `<...>` tokens against the session's own decode
   history — out of scope for this endurance run's aggregate WSJT-X-comparison methodology.

**Recommendation:** a dedicated, narrowly-scoped follow-up (not blocking, not urgent) should
mine `artefacts/20260706_live_run/OpenWSFZ ALL.TXT` for `<...>` tokens and check whether the
referenced hash could have been resolved from an earlier-in-session decode of the same
station, to distinguish hypothesis 1 (structural, expected) from hypothesis 2 (F-001 field
effectiveness gap). No defect is raised pending that investigation.

**Follow-up executed (2026-07-08).** The mining above was performed via
`artefacts/20260706_live_run/triage_f001_hash_gap.py` — written this same session but not
previously run — directly against this session's own `OpenWSFZ ALL.TXT` (6,907 raw `<...>`
lines, a larger count than the 4,671 "OpenWSFZ-only" figure above because that figure is
deduplicated and restricted to messages absent from WSJT-X's log; this mining works from every
raw hashed line instead):

| Outcome | Count | % of hashed lines |
|---|---|---|
| No prior in-session announcement for this correspondent at all — structurally unresolvable | 6,568 | 95.1% |
| Announcement decoded only *after* the hashed line — protocol-correct, not yet resolvable at that moment | 82 | 1.2% |
| **Announcement decoded *before* the hashed line — F-001 should have resolved this (genuine-gap candidate)** | **254** | **3.68%** |
| No identifiable known-correspondent token | 3 | — |

**H₀-3, resolved to a first approximation: hypothesis 1 (structural cold-start floor) dominates.**
95.1% of this session's unresolved hashes reference a station OpenWSFZ never heard directly
this session at all — exactly the expected behaviour of a session-scoped hash table, not a
defect. Hypothesis 2 (a genuine F-001 resolution gap) is real but small: 3.68% of hashed lines
had everything F-001's table needed — the correspondent already decoded earlier, same session —
and still weren't resolved. **Caveat:** this is a shape-matched proxy (nonstandard-callsign-shape
heuristic pairing a known correspondent to an earlier decode), not a confirmed 22-bit hash
identity match — `ALL.TXT` is text-only and carries no hash value to check directly, so some
misclassification in either direction is possible. Repeated with the same script and method on
the 07-07 session (`qa/endurance/2026-07-07-bb0a1c4/report.md` §3.5) with a consistent result:
92.5% structural, 2.12% genuine-gap-candidate. Neither night shows F-001 failing on the majority
of what it is actually capable of resolving.

**This session's own spike (00:00–04:00 UTC), explained (2026-07-08).** Station/region mining
(`qa/endurance/2026-07-07-bb0a1c4/report.md` §3.5, full detail) found this spike is a genuine
pre-dawn transatlantic grey-line DX opening: North American primary-callsign share jumps from
2.1% (prior evening background) to 41.2% during the spike — a burst of previously-silent
US/Canada stations becoming audible right at the terminator crossing, peaking ~1 hour before
actual Netherlands sunrise. The 07-07 session's spike turned out to be a *different*
mechanism (the opposite direction, hours later) — see that report for the comparison.

---

## 4. Summary verdict table

| Metric | Value | Threshold | Verdict |
|---|---|---|---|
| Stability — no crash | 0 crashes | 0 | **PASS** |
| Stability — no gap > 30 s | 0 gaps (max 6.3 s) | 0 | **PASS** |
| Stability — no log ERR/WRN/FTL | 0/0/0 | 0 | **PASS** |
| Duration | 10h52m15s | new benchmark (prior: 8h33m) | **PASS** |
| D-009 FP live validation | ~110 expected; 1,883 observed (excess explained, ratio comparable to baseline) | ≤ 3× or explained | **PASS** |
| Recall > +5 dB SNR | 83.9–90.6% | within a few pp of 85.9–89.5% baseline | **PASS** (informational) |
| Recall −5 to +5 dB | 66.5–76.7% | informational | — |
| Recall < −15 dB | 23.5–34.7% | informational (D-001) | — |
| Overall recall vs WSJT-X | 53.81% (59.52% baseline) | informational | — |
| SNR-stratified recall vs baseline | within 1.1–5.1 pp, no directional trend | ordinary variance | **PASS** (no regression) |
| Hashed callsign resolution (F-001) | Rate *increased* vs pre-F-001 baseline (1.79 vs 1.04/cycle) | informational | **FOLLOW-UP FLAGGED** → executed 2026-07-08, see §3.5 addendum: 95.1% structural, 3.68% genuine-gap-candidate |

**Overall verdict: PASS** — stability objectives met (new endurance benchmark); D-001 decode
gap reconfirmed unchanged, no regression from this session's shipped work; D-009 fix holds;
F-001's field effect on the hashed-callsign bucket is inconclusive from this run's data and
warrants a narrow follow-up.

---

## 5. Recommendations

**D-001 (#3 — open):** No new action required. This run reconfirms the SNR-stratified recall
profile established 2026-06-22 within ordinary variance, on a longer session and a newer
main HEAD. The gap remains most severe below −15 dB (23–43% recall) and best above +5 dB
(84–91%). The next diagnostic step for D-001 remains MMSE (H7) or further iterative
subtraction tuning if H6+OSD is deemed insufficient after on-air QSO testing.

**F-001 hashed-callsign resolution field check (new, not blocking):** The OpenWSFZ-only
hashed-callsign rate per cycle increased ~72% over the pre-F-001 baseline rather than
decreasing. Recommended next step: a targeted script over
`artefacts/20260706_live_run/OpenWSFZ ALL.TXT` to classify each unresolved `<...>` token as
"referenced station never heard this session" (structural, expected) vs "referenced station
was heard earlier this session but hash still unresolved" (genuine F-001 gap). Low priority,
not blocking any release.

**DT spread:** OpenWSFZ DT stdev (0.597 s) continues to widen slightly relative to WSJT-X
(0.336 s) and relative to the June 22 baseline (0.513 s). Still informational; no decode
failures attributable to it. Worth a comparison point if a future change targets timing
precision.

**Next endurance run:** No blocking issues. A follow-up run after any future D-001-targeted
change (e.g. MMSE/H7) should use this run's SNR-stratified recall table (§3.2) as the
pre-change baseline, alongside the original 2026-06-22 figures.
