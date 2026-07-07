# Endurance Test Report — 2026-07-07

## 1. Study hypothesis

**What is this run testing?**

Continuous live off-air operation of OpenWSFZ against real 40 m FT8 signals over a ~17-hour
session (2026-07-06 23:16 → 2026-07-07 16:15 local), with WSJT-X running in parallel as a
reference decoder. This is the first extended endurance run at main HEAD `bb0a1c4` (shim
20260033), following this session's D-012 (`hash_table_add` reject-counter overcounting fix)
and F-005 (hash-table saturation diagnostic — reject counter exposed via `DaemonStatus`), plus
CI-only work (release-tag automation, native binary rebuilds) since the last endurance
baseline (`qa/endurance/2026-07-06-7340e45`, shim 20260031). Neither D-012 nor F-005 touches
the decode pipeline's weak-signal recovery path or the hash table's actual resolution logic
(D-012 fixed only the *diagnostic reject counter*, not `hash_table_add`'s lookup/insert
behaviour — see §3.5), so this run's primary purpose is again confirmatory rather than
exploratory for the D-001 recall baseline.

This is also the longest single endurance session run to date, and the first to span a full
day/night/day propagation cycle (evening → overnight → full following daytime) rather than
evening-through-dawn. It is also the first run investigated for a new question raised by the
Captain mid-session: whether the false-positive guard's rejections are disproportionately
associated with callsigns that resolve to "Unknown" region (the advisory region-lookup
capability, F-002) — a signal that, if present, would be informative for future false-positive
heuristics.

Primary objectives:

- **(a) Stability:** Confirm the pipeline runs reliably for a full day/night session with no
  crashes, audio dropouts, or unrecoverable gaps, on the current main-HEAD binary.
- **(b) D-001 baseline reconfirmation:** Compare S7/S8-style recall statistics (decode rate vs
  WSJT-X-as-oracle, SNR-stratified recall) against the immediately preceding endurance report
  (`qa/endurance/2026-07-06-7340e45`, shim 20260031) to confirm the open co-channel/weak-signal
  decode gap is unchanged by the intervening D-012/F-005 work.
- **(c) Hashed-callsign field check, continued:** The 07-06 report flagged an unresolved
  question (H₀-3 NOT CONFIRMED there) — the OpenWSFZ-only hashed-callsign rate had *increased*
  rather than decreased after F-001 shipped, with two competing explanations left open. This
  run reports the same metric for a second data point.
- **(d) NEW — FP-guard / region correlation:** Characterise, for the first time, whether
  messages rejected by the false-positive plausibility guard (`IsPlausibleMessage`) skew toward
  "Unknown region" callsigns relative to the accepted-decode baseline rate.

**Null hypotheses:**

- **H₀-1 (stability):** OpenWSFZ completes the session without any unrecoverable pipeline
  failure, crash, or audio gap > 30 seconds.
- **H₀-2 (D-001 unchanged):** SNR-stratified recall this run falls within ordinary
  night-to-night band-noise variance of the 07-06 baseline, with no systematic directional
  shift attributable to D-012/F-005.
- **H₀-3 (hashed-callsign rate):** The OpenWSFZ-only hashed-callsign rate per cycle this run is
  not lower than the 07-06 baseline rate (i.e., testing whether the prior run's spike persists
  or was band-specific).
- **H₀-4 (NEW — FP/region correlation):** The "Unknown region" rate among FP-guard-rejected
  messages is no different from the "Unknown region" rate among accepted decodes.

**Defects under observation:** D-001 (open, #3). D-009 (closed, `ef16040`) FP-rate sanity
re-checked as a standing regression guard. D-012 (closed, `b8ebcb7`) — diagnostic-counter fix
only, mentioned for version-provenance context, not re-tested here (covered by its own unit
regression suite, not an endurance-run concern).

**What constitutes a meaningful result?**

- Stability: zero crashes, zero unrecoverable gaps, clean operator-initiated stop.
- D-001: SNR-stratified recall within a few percentage points of the 07-06 baseline in each
  band, with no consistent directional trend.
- Hashed-callsign rate: informational only — no acceptance threshold set.
- FP/region correlation: informational/exploratory — no acceptance threshold set; reported for
  the record and to inform whether this is worth pursuing as a future FP heuristic input.

---

## 2. Data summary

| Field | Value |
|---|---|
| Date | 2026-07-06/07 UTC (local 2026-07-06 23:16 → 2026-07-07 16:15 CEST) |
| OpenWSFZ SHA | `bb0a1c4` (main HEAD) |
| ft8_lib shim | 20260033 (D-012 hash-table reject-counter fix; F-005 reject-counter exposure; no change to decode-recovery path since shim 20260031) |
| Session start (UTC) | 2026-07-06 21:16:43 (capture start; first decoded cycle `260706_211645`, 2 s later) |
| Session end (UTC) | 2026-07-07 14:15:54 (graceful operator-initiated stop; last decoded cycle `260707_141530`) |
| Duration | 16 hours 59 minutes 11 seconds (capture-session basis) |
| Total 15-second cycles | 4,055 (union of cycles with ≥1 decode from either decoder) |
| Band | 40 m (7.074 MHz FT8) |
| Audio device | USB Audio CODEC (`d451e08c`) — same device as the 06-22 and 07-06 baselines |
| WSJT-X | Parallel reference decoder, restarted fresh at session start |
| Daemon log file | `logs/openswfz-20260706T210818Z.log` (49,908 lines) |
| Shutdown | Graceful (operator-initiated `POST /api/v1/decode/stop`; daemon and WSJT-X both fully closed afterward, unlike the 07-06 run which left the daemon running) |
| Audio chunks captured | 979,508 (main session). A brief 12-second setup/verification capture at process start (23:08:18–23:08:30, 197 chunks, operator-stopped) preceded the main session and is excluded from the analysis window, consistent with the exclusion convention used in the 07-06 report. |

**Corpus:** Live off-air 40 m FT8 reception spanning a European evening, full overnight period,
and the following full daytime — the first endurance session long enough to include an
extended midday propagation lull, directly observed live (multiple consecutive 0-decode cycles
around 2026-07-07 11:49–14:00 UTC, confirmed healthy via `captureActive=true`,
`audioActive=true`, `dataFlowing=true` heartbeats and non-zero RMS throughout — a genuine band
condition, not a fault). The raw ALL.TXT files, WAV recordings (4,075 files, 1.4 GB), and daemon
log are stored at `artefacts/20260706_live_run_2308/` (outside VCS, git-ignored per NFR-021 —
they contain real third-party callsigns). This report contains no individual callsigns; all
analysis is aggregate. The analysis script (`analyse_live_run.py`, adapted unchanged from the
07-06 report's script for direct methodological comparability) and the FP/region-correlation
watch script (`fp_region_watch.py`, plus its accumulated `fp_events.log` and `state.json`) are
committed alongside the raw logs at that path for reproducibility.

**Acceptance thresholds (this run):**

- Stability: 0 crashes, 0 unrecoverable gaps > 30 s, 0 log ERR/WRN/FTL entries.
- D-001: SNR-stratified recall within a few points of the 07-06 baseline in each band;
  informational, not gating.
- Hashed-callsign rate and FP/region correlation: informational only.

---

## 3. Results

### 3.1 Stability

OpenWSFZ ran cleanly for 16h59m11s (4,055 decoded cycles) without crash, audio dropout, or
decode gap, on the current main-HEAD binary.

| Metric | Value |
|---|---|
| Log ERR entries | **0** |
| Log WRN entries | **0** |
| Log FTL entries | **0** |
| Unhandled exceptions / access violations | **0** |
| Heartbeat count | 12,347 (≈5 s cadence) |
| Max heartbeat gap | 9.2 s (threshold: flag if > 30 s) |
| Heartbeat gaps > 30 s | **0** |
| Daemon process identity | Single PID throughout (no restart) |
| Shutdown | Graceful (operator API call; both OpenWSFZ and WSJT-X fully closed post-run) |

This is a new longest-confirmed clean endurance run (previous longest: 10h52m,
`2026-07-06-7340e45`), and the first to run across a complete day/night/day propagation cycle.
One heartbeat tick briefly reported `captureActive=false` at 16:15:55 — this was not a fault:
the daemon log confirms it is the direct, expected result of the operator's own graceful
`POST /api/v1/decode/stop` one second earlier (`RecordingStopped (graceful)`, `Capture stopped
... (operator-stopped). Chunks received: 979508`), not an unexpected dropout. No other anomaly
of any kind was observed in the log across the full session.

**H₀-1: CONFIRMED — zero failures, clean 16h59m run, longest to date.**

### 3.2 Decode rate and recall (S7/S8-style comparison vs the 07-06 baseline)

| Metric | This run | Baseline (`2026-07-06-7340e45`, shim 20260031) |
|---|---|---|
| Total decodes | OpenWSFZ 48,028 / WSJT-X 76,920 | OpenWSFZ 47,013 / WSJT-X 75,193 |
| Mean decodes / cycle | 11.8 / 19.0 | 18.0 / 28.8 |
| Min decodes / cycle | 0 / 0 | 3 / 3 |
| Max decodes / cycle | 29 / 50 | 32 / 58 |
| Stdev decodes / cycle | 8.1 / 12.7 | 5.2 / 9.5 |
| Per-cycle count Pearson r | 0.945 | 0.833 |

The lower per-cycle means and the minimum of 0 (vs the baseline's minimum of 3) directly
reflect this run's extended midday lull — a genuinely quiet band, not a capture problem (§3.1,
§2). The correlation between the two decoders is markedly *tighter* this run (r = 0.945 vs
0.833): both decoders go quiet in the same cycles during the lull, which mechanically raises
the correlation coefficient. This is an artefact of the longer, more propagation-varied session
rather than a change in decoder agreement during active periods.

**Recall analysis (WSJT-X as oracle):**

| Category | This run | Baseline |
|---|---|---|
| Decoded by both | 43,305 | 40,459 |
| OpenWSFZ only (all) | 4,723 | 6,554 |
| — of which: `<...>` hashed callsign | 3,086 | 4,671 |
| — of which: normal text | 1,637 | 1,883 |
| WSJT-X only (all) | 33,615 | 34,734 |
| — of which: hashed callsign form | 6,545 | 9,887 |
| — of which: normal text | 27,070 | 24,847 |

| Recall metric | This run | Baseline | Δ |
|---|---|---|---|
| Overall recall (WSJT-X as oracle, all messages) | **56.30%** (43,305 / 76,920) | 53.81% (40,459 / 75,193) | +2.49 pp |
| Recall excluding hashed WSJT-X messages | **60.46%** (41,398 / 68,468) | 60.60% (38,223 / 63,070) | −0.14 pp |

**Recall by SNR (WSJT-X SNR, non-hashed messages only):**

| WSJT-X SNR band | This run | Baseline | Δ |
|---|---|---|---|
| −25 to −20 dB | 22.7% (747/3,295) | 23.5% (691/2,939) | −0.8 pp |
| −20 to −15 dB | 32.2% (2,362/7,332) | 34.7% (2,129/6,144) | −2.5 pp |
| −15 to −10 dB | 44.4% (5,062/11,406) | 43.1% (4,126/9,574) | +1.3 pp |
| −10 to −5 dB | 57.1% (7,116/12,468) | 55.2% (6,840/12,397) | +1.9 pp |
| −5 to +0 dB | 67.2% (7,644/11,371) | 66.5% (8,050/12,106) | +0.7 pp |
| 0 to +5 dB | 75.7% (6,604/8,728) | 76.7% (7,200/9,383) | −1.0 pp |
| +5 to +10 dB | 82.7% (5,174/6,255) | 83.9% (4,574/5,454) | −1.2 pp |
| +10 to +20 dB | 87.3% (5,721/6,551) | 90.6% (4,036/4,454) | −3.3 pp |

Per-band recall sits within roughly 1–3 points of the 07-06 baseline across the SNR range
(largest single deviation −3.3 pp at the strongest-signal band), with no consistent
directional trend — some bands improved, some declined, none moved by more than the ordinary
run-to-run variance already established across the last three endurance reports. This is
consistent with D-012/F-005 not touching the decoder's weak-signal recovery path: a flat,
slightly-noisy SNR curve is the expected outcome, not a new finding.

**H₀-2: CONFIRMED — SNR-stratified recall is within ordinary run-to-run variance of the 07-06
baseline; no systematic shift attributable to D-012/F-005.**

### 3.3 D-009 OSD false-positive sanity check

The D-009 fix (shim 20260029, unchanged through 20260033) calibrated OSD FP rate at 0.042
FPs/slot under S5 (AWGN, no signals). Over 4,055 cycles, the expected FP count is:

> 4,055 × 0.042 ≈ **170 expected OSD false positives**

Observed OpenWSFZ-only normal-text messages: **1,637**.

As in both prior reports, the excess over the pure-FP estimate is not attributable to runaway
OSD — WSJT-X is not an infallible oracle in a live band, and this excess is most plausibly
genuine weak signals WSJT-X missed. The proportion of OpenWSFZ-only normal-text decodes to
total OpenWSFZ decodes (1,637 / 48,028 = 3.4%) is comparable to — slightly better than — the
07-06 baseline's (1,883 / 47,013 = 4.0%).

**D-009 fix holds — no evidence of anomalous OSD FP behaviour.**

### 3.4 DT and SNR reporting

**DT (timing offset relative to cycle boundary):**

| | This run — Mean | This run — Median | This run — Stdev | Baseline — Mean | Baseline — Median | Baseline — Stdev |
|---|---|---|---|---|---|---|
| OpenWSFZ | −0.114 s | −0.100 s | 0.698 s | −0.013 s | +0.000 s | 0.597 s |
| WSJT-X | +0.218 s | +0.200 s | 0.372 s | +0.219 s | +0.200 s | 0.336 s |

WSJT-X's DT is essentially unchanged from baseline, as expected (independent reference
decoder). OpenWSFZ's mean DT continues to drift slightly more negative (−0.114 s vs −0.013 s,
and −0.013 s vs +0.099 s the run before that) and its spread continues to widen a little further
each run (0.698 vs 0.597 vs 0.513 s stdev, three consecutive reports). This remains
informational — DT does not affect decode correctness — but it is now a three-point trend
rather than a single observation and is called out more firmly in §5 for that reason.

**SNR bias (matched messages):**

| | This run | Baseline |
|---|---|---|
| OpenWSFZ SNR − WSJT-X SNR (mean) | −10.46 dB | −9.60 dB |
| Median | −10.00 dB | −9.00 dB |
| Stdev | 8.55 dB | 8.89 dB |

Consistent with both prior reports' conclusion: a live-band artefact of independent noise-floor
estimation in a dense multi-signal environment, not a calibration regression. The synthetic S1
single-signal bench calibration (+1.42 dB bias) remains the valid reference for controlled
conditions. No corrective action required.

### 3.5 Hashed callsign gap — continued field check

The 07-06 report left an open question: after F-001 shipped, the OpenWSFZ-only hashed-callsign
rate per cycle had *increased* relative to the pre-F-001 06-22 baseline (1.79/cycle vs
1.04/cycle), the opposite of the expected effect, with two competing hypotheses proposed
(structural cold-start floor vs a genuine F-001 effectiveness gap) and a narrow follow-up
recommended but not yet performed.

| | This run | 07-06 baseline | 06-22 (pre-F-001) baseline |
|---|---|---|---|
| OpenWSFZ-only hashed-callsign count | 3,086 | 4,671 | 2,126 |
| Cycles (union) | 4,055 | 2,610 | 2,054 |
| Rate per cycle | **0.76** | 1.79 | 1.04 |

**This run's rate (0.76/cycle) is markedly lower than both the 07-06 baseline and the original
pre-F-001 06-22 baseline** — a 57% reduction from 07-06 and a 27% reduction from the original
pre-F-001 figure.

**Important scope note on D-012:** it would be tempting to credit this drop to D-012 (merged
since the 07-06 report), but D-012 is explicitly a fix to the *diagnostic reject counter*
(`g_hash_table_reject_count`) only — the dev-task record for D-012 states plainly that "the
hash table's actual contents and resolution behaviour are unaffected," and that F-005 (which
introduced the counter's exposure) "didn't touch `hash_table_add`'s body" beyond comments. The
underlying session-scoped hash-resolution logic that determines whether a `<...>` token appears
in `ALL.TXT` at all has been unchanged since F-001 originally shipped through both this run and
the 07-06 baseline. D-012 cannot mechanically explain this metric's movement.

**The session-average comparison above does not hold up as a clean before/after signal once
checked at finer granularity — the first draft of this section drew a conclusion the data did
not actually support, corrected here.** Hour-by-hour, both this run's and the 07-06 baseline's
OpenWSFZ-only hashed rate are not flat:

| Hour (UTC) | This run — OWSFZ decodes | This run — hashed-only rate | Baseline — OWSFZ decodes | Baseline — hashed-only rate |
|---|---|---|---|---|
| 21 | 3,333 | 3.2% | 1,967 (20 h) | 2.1% |
| 22 | 4,287 | 3.1% | 5,387 | 5.5% |
| 23 | 4,516 | 4.7% | 4,921 | 5.9% |
| 00 | 4,845 | 5.9% | 4,446 | 9.0% |
| 01 | 4,868 | 3.4% | 4,574 | **13.6%** |
| 02 | 4,724 | 4.0% | 4,583 | **20.7%** |
| 03 | 4,702 | 6.3% | 4,896 | 11.5% |
| 04 | 3,974 | 5.6% | 4,887 | 12.6% |
| 05 | 3,701 | **13.8%** | 4,496 | 9.4% |
| 06 | 2,991 | **11.0%** | 3,364 | 4.3% |
| 07 | 2,123 | **19.4%** | 2,522 | 4.0% |
| 08–14 | ≤1,621/hr, declining to near-zero | 0–8% on trivial samples | 970 (last hour, session ended 07:31 UTC) | 4.0% |

Both runs show a **multi-hour transient spike** in the hashed-only rate (this run: 05:00–07:00
UTC, 11–19%; baseline: 00:00–04:00 UTC, up to 20.7%) sitting on top of a broadly comparable 2–9%
background rate either side of it. Critically, **WSJT-X's own hashed-only bucket shows the same
spike at the same hours this run** (13.2%, 11.2%, 19.2% for 05–07 UTC) — confirmed independently
by both decoders, ruling out an OpenWSFZ-specific cause. The spike falls at different clock
hours in the two runs (05–07 UTC tonight vs 00–04 UTC in the baseline), so it does not appear to
be a fixed local-dawn effect; it more plausibly tracks whichever grey-line/propagation-path
opening happens to cross this station on a given night — a new observation this run's finer
analysis surfaced, not previously reported.

**Corrected explanation for the lower session-average:** tonight's session ran roughly five
hours longer than the baseline and, unlike the baseline (which ended at 07:31 UTC), continued
into a long near-dead daytime stretch (08:00–14:00 UTC) contributing very little to either
decoder's totals. That extra low-rate tail dilutes tonight's overall average downward relative
to the baseline's shorter, spike-inclusive window — a session-composition effect, not evidence
about F-001's field effectiveness one way or the other. The original hypothesis-1-vs-hypothesis-2
framing from the 07-06 report is **not resolved by this run**; the session-average figures in
the table above are not safely comparable between runs of different length and different
overlap with whatever propagation window produces the spike.

**H₀-3: INCONCLUSIVE, revised from the original draft's overstated conclusion.** The lower
session-average rate is adequately explained by session-length/composition rather than by
either competing hypothesis from the 07-06 report, so neither hypothesis 1 nor hypothesis 2 is
confirmed or refuted by this run. The narrow follow-up recommended in the 07-06 report (mining
`OpenWSFZ ALL.TXT` for `<...>` tokens against same-session decode history) remains the only way
to close that original question, and should now additionally be time-binned around the
spike-window hours identified here to test whether the spike itself is structural
(new-station-never-yet-heard) or a genuine resolution gap concentrated in fast-changing
conditions.

### 3.6 NEW — False-positive-guard rejection vs "Unknown region" correlation

This section reports a new, exploratory analysis requested mid-session: whether messages
rejected by the false-positive plausibility guard (`IsPlausibleMessage`,
`Ft8Decoder.cs`) are disproportionately associated with a primary callsign token that resolves
to "Unknown" region under the advisory region-lookup capability (F-002,
`CallsignRegionStore.TryGetRegion`), relative to the same classification applied to genuinely
accepted decodes.

**Method:** A monitoring script (`fp_region_watch.py`, run for the duration of the session)
tailed the daemon log for `"filtered implausible message '...' (false-positive guard)"` entries
and `ALL.TXT` for accepted decodes. For each message, it replicated the decoder's own
`ExtractPrimaryCallsignToken` logic to identify the callsign-position token, then replicated
`CallsignRegionStore.TryGetRegion`'s longest-prefix-match logic against the live
`callsign-regions.json` to classify the token as Known or Unknown region. This is an offline
replication for analysis purposes only — the production code never performs region lookup on
guard-rejected messages (region resolution only runs on messages that already passed the
guard); this script deliberately extends the same logic to the rejected side to test the
hypothesis.

| | Total messages | Unknown region | Rate |
|---|---|---|---|
| FP-guard rejected | 3,621 | 2,856 | **78.9%** |
| Accepted decodes | 48,025 | 20,252 | **42.2%** |

**Delta: +36.7 percentage points.** This held remarkably steady across the full session —
sampled at 30 checkpoints through the run, the delta ranged only 29.5–38.1 pp with no drift
toward zero as the sample grew from dozens to thousands of rejected messages, and the final
figure (36.7 pp) sits squarely within that range.

**Known confound (works against, not for, the finding):** the region table's broadest entries
match on a single leading character (`K`/`N`/`W` → United States, `G` → England, `F` → France).
A handful of confirmed cases were observed where a clearly-garbage OSD-noise token (e.g.
`NXMMS86KX6-K1`, `G9V8HSV63CN`) was classified "Known region" purely because it happened to
start with one of these letters, not because it carries genuine regional signal. This confound
inflates the "Known" bucket on *both* sides indiscriminately, but because single-letter-prefix
countries are common, high-population allocations, garbage is more likely to coincidentally
match one of them than a genuine transmitted callsign is to be under-represented by it. If
anything, this means the true correlation is understated by these raw figures, not overstated.

**Interpretation:** the finding is consistent with the expectation that OSD false-positive
candidates are largely CRC-14 coincidences on noise — essentially random bit patterns are far
less likely to fall inside a real allocated callsign-prefix range than a genuinely transmitted
callsign is. It is not, on its own, strong enough to justify making "Unknown region" a
rejection criterion (78.9% Unknown among rejects is still well short of certainty, and 42.2% of
*all genuine accepted traffic* is also Unknown, reflecting the seed table's deliberate
incompleteness — see the region-lookup enhancement idea, GitHub issue #40 — rather than a flaw
in genuine decodes). But it is a real, reproducible, session-long signal, and it is the first
time this correlation has been measured.

**H₀-4: REJECTED — a statistically consistent +36.7pp difference in Unknown-region rate exists
between FP-guard-rejected and accepted messages.**

---

## 4. Summary verdict table

| Metric | Value | Threshold | Verdict |
|---|---|---|---|
| Stability — no crash | 0 crashes | 0 | **PASS** |
| Stability — no gap > 30 s | 0 gaps (max 9.2 s) | 0 | **PASS** |
| Stability — no log ERR/WRN/FTL | 0/0/0 | 0 | **PASS** |
| Duration | 16h59m11s | new benchmark (prior: 10h52m) | **PASS** |
| D-009 FP live validation | ~170 expected; 1,637 observed (excess explained, ratio slightly better than baseline) | ≤ 3× or explained | **PASS** |
| Recall > +5 dB SNR | 82.7–87.3% | within a few pp of 83.9–90.6% baseline | **PASS** (informational) |
| Recall −5 to +5 dB | 67.2–75.7% | informational | — |
| Recall < −15 dB | 22.7–32.2% | informational (D-001) | — |
| Overall recall vs WSJT-X | 56.30% (53.81% baseline) | informational | — |
| SNR-stratified recall vs baseline | within 0.7–3.3 pp, no directional trend | ordinary variance | **PASS** (no regression) |
| Hashed-callsign rate | 0.76/cycle, down from 1.79 (07-06) and 1.04 (06-22); driven by session-length/composition, not resolved either way | informational | **INCONCLUSIVE** — session averages not safely comparable; new spike-window phenomenon found instead |
| FP-guard rejection vs Unknown-region correlation (NEW) | +36.7 pp (78.9% vs 42.2%), stable across session | informational/exploratory | **NOTABLE FINDING** |

**Overall verdict: PASS** — stability objectives met (new endurance benchmark, first full
day/night/day cycle); D-001 decode gap reconfirmed unchanged, no regression from D-012/F-005;
D-009 fix holds; the hashed-callsign rate question from the 07-06 report remains genuinely
open (this run's data does not resolve it either way), but finer-grained analysis surfaced a
new, independently-confirmed transient spike phenomenon worth its own follow-up; and a new,
reproducible FP-guard/region correlation has been established as a candidate input for future
false-positive work.

---

## 5. Recommendations

**D-001 (#3 — open):** No new action required. This run reconfirms the SNR-stratified recall
profile within ordinary variance, on the longest session yet and a newer main HEAD. The gap
remains most severe below −15 dB (23–32% recall) and best above +5 dB (83–87%). The next
diagnostic step for D-001 remains MMSE (H7) or further iterative subtraction tuning, unchanged
from the last two reports.

**Hashed-callsign rate (F-001) — original question still open; new spike phenomenon to
investigate:** This run's session-average comparison against the 07-06 baseline does not
resolve hypothesis 1 vs hypothesis 2 from that report — the lower average is adequately
explained by this run's longer, differently-composed session rather than by either hypothesis.
However, hour-by-hour analysis surfaced a multi-hour transient spike in the hashed-only rate
(11–19% vs a 2–9% background), confirmed independently in both OpenWSFZ's and WSJT-X's own
hashed-only buckets, at different clock hours in this run vs the baseline. Recommended, not
blocking:
1. The originally recommended follow-up (mining `OpenWSFZ ALL.TXT` for `<...>` tokens against
   same-session decode history) remains the right way to close the original hypothesis-1-vs-2
   question, and should now be time-binned specifically around each run's spike window to test
   whether the spike itself is structural (genuinely new stations, never heard before in that
   window) or a resolution gap specific to fast-changing propagation.
2. Track whether the spike's timing correlates with a specific grey-line/propagation-path
   transition (rather than fixed local sunrise) across further endurance runs — worth a
   dedicated propagation-timing note if the pattern repeats a third time.

**FP-guard / Unknown-region correlation (new):** The +36.7pp signal is real and reproducible
but exploratory. Recommended next steps, none blocking:
1. Repeat the measurement on a future endurance run to confirm it holds a third time before
   treating it as an established property rather than a two-data-point (well, one full-session)
   observation.
2. If a future change considers using region as an FP-detection input, first address the
   single-letter-prefix confound noted in §3.6 — possibly by tracking a separate "matched only
   on a single-character prefix" sub-bucket, since that confound currently cuts against
   overstating the correlation but would need proper accounting in any operational use.
3. Consider whether widening `callsign-regions.json` (GitHub issue #40, sourcing from a real
   country file) would sharpen or dampen this signal — a fuller table could either strengthen
   the correlation (fewer coincidental single-letter matches diluting the Known bucket) or
   reveal it was partly an artefact of table sparseness. Not scoped as a change; recorded for
   whoever picks up issue #40.

**DT spread (three-run trend):** OpenWSFZ DT stdev has now widened in three consecutive reports
(0.513 → 0.597 → 0.698 s) while WSJT-X's has stayed flat (0.336 → 0.372 s, no clear trend).
Still no decode failures attributable to it, but this is no longer a single informational
data point — recommend a dedicated look at OpenWSFZ's cycle-framing/DT-computation path before
it is dismissed again in the next report.

**Next endurance run:** No blocking issues. A follow-up run after any future D-001-targeted
change (e.g. MMSE/H7) should use this run's SNR-stratified recall table (§3.2) as the
pre-change baseline, alongside the 07-06 and 06-22 figures. The FP/region correlation (§3.6)
should be re-measured on that run too, per recommendation 1 above.
