# D-001 decomposed: half the gap is in the live path, and it is time-varying

**Author:** Architect, 2026-07-25. **Status:** provisional — a coarse count-ratio analysis that
anticipates `tasks.md` 11.10's rigorous paired version. **Do not quote the δ figures in §4 as
measurements**; they are predictions for 11.10 to confirm or falsify.
**Sources:** `artefacts/20260724_live_run_2227/` (daemon logs, `ALL.TXT`, `wsjt-x ALL.TXT`) and
Phase 1b's arm-A baseline (`_work/phase1b/baseline_decoded/k10_c0.10_n60/ALL.TXT`). All local and
git-ignored per NFR-021; this document contains aggregate counts only, no callsigns.

---

## 1. The headline

Three decode counts over the same 11h51m session and the same 2,827 cycles of audio:

| | decodes/cycle | cycles decoding nothing |
|---|---|---|
| **OpenWSFZ, live** | **7.08** | **1,050 / 2,839 (37.0%)** |
| OpenWSFZ, same decoder replayed offline on grid-aligned audio | 18.35 | **0 / 2,827** |
| WSJT-X, same audio | 29.34 | — |

**D-001's gap splits almost exactly in half.** `+11.27` decodes/cycle are lost in the live path;
`+10.99` are genuine decoder quality. The live path is worth as much as the entire decoder gap.

This is the separation §1 of the study SPEC has wanted from the start, and no previous run had the
data to make. It also retro-explains the D-001 runtime-parameter sweep's "BASELINE DOMINATES, knobs
exhausted" verdict (`qa/rr-study/d001-param-sweep-2026-07-22/`): that sweep was tuning decoder
parameters against the decoder half of the gap while an equally large loss sat untouched in the
capture path, invisible to every knob it turned.

## 2. The loss is not uniform — it is progressive, and the first decile is clean

Live vs. offline replay of the same audio, by session decile:

| decile | window (UTC) | live /cyc | replay /cyc | **retention** |
|---|---|---|---|---|
| 1 | 20:28–21:39 | 21.22 | 21.57 | **0.984** |
| 2 | 21:39–22:50 | 11.86 | 19.62 | 0.604 |
| 3 | 22:50–00:01 | 0.53 | 19.23 | **0.027** |
| 4 | 00:01–01:12 | 0.48 | 20.15 | **0.024** |
| 5 | 01:12–02:23 | 9.70 | 20.05 | 0.484 |
| 6 | 02:23–03:34 | 6.93 | 21.08 | 0.329 |
| 7 | 03:34–04:45 | 6.70 | 19.02 | 0.352 |
| 8 | 04:45–05:56 | 7.06 | 17.05 | 0.414 |
| 9 | 05:56–07:07 | 3.84 | 14.98 | 0.256 |
| 10 | 07:07–08:18 | 2.68 | 10.86 | 0.247 |
| **session** | | **7.08** | **18.35** | **0.386** |

**In its first decile the live daemon ran at parity with the offline replay (0.984).** Whatever the
live path does wrong, it is not doing it at the start of the session. Everything after decile 1 is
degradation, and deciles 3–4 lose **97–98%** of the available decodes while the replay on that exact
audio, in those exact hours, returns ~20 per cycle.

The replay column also shows what a *real* propagation decline looks like: a gentle 21.6 → 10.9 slide
across the night, with **zero** starved cycles at any hour. Nothing in it resembles the live
collapse.

## 3. Four alternative explanations, all excluded

| candidate | verdict | evidence |
|---|---|---|
| **Transmit blanking** (daemon deaf while transmitting) | **excluded** | Zero `Transmit`/`PTT`/`Sending` events in the daemon log. Zero/non-zero cycles alternate on only **28.2%** of transitions; TX-every-other-cycle would approach 100%. |
| **Band conditions / dead band** | **excluded** | The offline replay covers the identical hours on the identical audio and never once drops below **five** decodes in a cycle. The signals were demonstrably present while the live daemon heard nothing. |
| **Daemon downtime** | **excluded** | 2,839 cycles processed against 2,827 WAVs — the daemon covered the whole session. The HK-013 supervisor's restarts all fired at 08:20–08:27, *after* the last WAV at 08:18:15. |
| **Decoder incapacity** | **excluded** | Same binary, same decoder settings, reaches 18.35/cycle offline and 21.22/cycle live in decile 1. |

What remains is a **time-varying defect in the live receive path** — which is what
`fix-cycle-boundary-clock-drift` targets. The shape is a sawtooth (collapse in 3–4, partial recovery
at 5, renewed decline through 9–10), the signature of a correction loop that fires but does not
converge. That is exactly what round 9.5 reported from the framer's *internal* deviation log; this
is the first time it has been seen from the **outcome** side.

## 4. Predicted alignment error — for 11.10 to falsify

Inverting the measured recall(δ) curve (Phase 1a + 1b) at each decile's retention gives the
alignment error that would be required to explain it. Both branches are shown because a count ratio
carries no sign:

| decile | retention | implied δ (negative branch) | implied δ (positive branch) |
|---|---|---|---|
| 1 | 0.984 | −0.26 | +0.33 |
| 2 | 0.604 | −2.31 | +2.38 |
| 3 | 0.027 | *beyond −2.75* | +3.26 |
| 4 | 0.024 | *beyond −2.75* | +3.29 |
| 5 | 0.484 | −2.35 | +2.44 |
| 6 | 0.329 | −2.41 | +2.54 |
| 7 | 0.352 | −2.40 | +2.52 |
| 8 | 0.414 | −2.38 | +2.48 |
| 9 | 0.256 | −2.44 | +2.61 |
| 10 | 0.247 | −2.44 | +2.62 |

**The prediction 11.10 must test:** reconstructed `δ_live(k)` should sit near **0 in decile 1**,
reach **|δ| ≈ 2.3 by decile 2**, exceed **|δ| ≈ 3 in deciles 3–4**, and hover at **|δ| ≈ 2.4–2.6**
thereafter.

- **If it matches** — alignment explains essentially the whole live-path half of D-001, and a working
  `CycleFramer` fix is worth ~11 decodes/cycle, roughly half the total D-001 gap. That is a far
  larger prize than this change has ever been credited with.
- **If it does not match** — a second, distinct mechanism exists in the capture path, and five live
  rounds have been aimed at a mechanism that is not the dominant one. This is the more important
  outcome to be able to detect, and it is why the prediction is stated numerically and in advance.

## 5. Limitations — read before quoting any of this

1. **Count ratio, not the paired within-cycle recall metric.** §5.3's metric compares *which* signals
   survive within a cycle; this compares only how many. The two coincide only if the live decodes are
   a subset of the replay's. 11.10 must use the paired metric.
2. **Not sample-identical audio.** The replay runs on WSJT-X's capture; the live run used OpenWSFZ's
   own. Same RF and same wall clock, but two different captures — so "live vs replay" still bundles
   alignment error together with any other capture-path difference (gain, dropped samples,
   resampling). Separating those is exactly 11.10's job. **Do not attempt sample-level registration**
   (SPEC §6).
3. **Deciles are equal-count, not equal-time**, and the two series are indexed independently (2,839
   live cycles vs 2,827 replay cycles). Alignment between the two columns is approximate at the
   decile boundaries — adequate for an effect of this size, not for anything subtle.
4. **The δ inversion assumes the misalignment is a per-cycle constant** applied to a population with
   the session's own `DT_med` = +0.80. Real per-cycle excursions vary within a decile, and the curve
   is nonlinear, so the implied figures are indicative magnitudes, not measurements.
5. **Single session, single band, single night.** `artefacts/20260723_live_run_2223/` is the
   independent replication.

## 6. Consequences

- **11.10 is now the highest-value open item in the change**, and larger in scope than its original
  task text assumed. It should absorb this analysis and settle the alignment-vs-other question.
- **10.8's live session should not be scheduled until 11.10 reports.** If the live-path loss is not
  alignment, a passing 10.8 would certify a framer that fixed the wrong thing. 11.10 is offline and
  costs no radio time.
- **Deliverable #4** (predicted recall cost of the 9.5 session's excursions, SPEC §10) is largely
  answered by §2's retention column, pending 11.10's confirmation.
- The 37% zero-decode figure is a **user-visible** symptom, not merely a metric: for more than a
  third of the session the operator saw an empty decode panel while the band was open.
