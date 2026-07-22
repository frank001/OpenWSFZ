# D-001 — Runtime-Parameter Recall/False-Positive Pareto Sweep: Results Report

| Field | Value |
|---|---|
| Defect ID | D-001 (open, issue #3); touches D-009 (false-positive calibration) |
| Type | Offline decode sweep (no product/decoder/shim code touched — QA tooling only) |
| Governing spec | `dev-tasks/2026-07-22-d001-runtime-param-recall-fp-sweep-spec.md` |
| Work order | `dev-tasks/2026-07-22-d001-runtime-param-sweep-work-order.md` |
| Analysis date | 2026-07-22 |
| Repo HEAD at analysis time | `ea88d12` (native shim 20260033 — unchanged; the sweep drives runtime `ft8_set_decode_params` only) |
| Recall corpus | 07-07 off-air (`20260706_live_run_2308`), 4,075 per-slot 12 kHz WAVs + WSJT-X ALL.TXT |
| FP corpus | Synthetic S5 (noise, 120 slots) + S7 (co-channel, 105 slots / 215 signals), seeded/reproducible |
| Harness | `qa/rr-study/d001-param-sweep-2026-07-22/` (C# decode driver + `sweep_driver.py` scorer) |
| Aggregate data | `sweep_grid.csv` (this directory) — the 45-row grid |
| Status | **COMPLETE — verdict delivered below** |

> **NFR-021 handling.** Every raw artefact (WSJT-X/OpenWSFZ ALL.TXT, S5/S7 `truth.csv`,
> per-point decode output, the WAV corpora) stayed local under the harness's git-ignored
> `_work/` tree. Only this report and the aggregate `sweep_grid.csv` (coordinates + counts +
> rates, no callsigns or message text) are committed.

---

## Section 1 — Study Hypothesis

**Question (spec §1, pre-committed before any decode ran).** Across the three
runtime-configurable decode parameters exposed by `ft8_set_decode_params`
(`k_min_score_pass2`, `osd_corr_threshold`, `osd_nhard_max`), does any operating point recover a
meaningful fraction of the D-001 low-SNR recall gap — measured as agreement with WSJT-X on the
07-07 off-air corpus — **without** regressing the D-009-calibrated false-positive rate (measured
on the synthetic S5 noise-only and S7 co-channel scenarios) beyond the shipped baseline
`(k=10, corr=0.10, nhard=60)`?

**Null hypothesis.** No runtime operating point Pareto-dominates the baseline: for every point
either the recall gain is ≤ 0, or achieving a positive recall gain requires regressing S5 and/or
S7 false-positive rate above the baseline.

**Two-sided win rule (spec §3.4/§3.5, D-009-origin rigour).** A point counts as a candidate win
only if it *both* gains recall (`Δpp > 0`) *and* holds *both* S5 and S7 false-positive rates at or
below the baseline. A recall gain purchased with an FP regression is reported as a trade-off, never
as a win, and the two arms are never averaged into a single blended score — this mirrors the exact
two-sided discipline D-009 itself was calibrated under.

**Why this matters now.** The Captain is holding the H7 (MMSE joint demodulation, 3–6 months' cost)
go/no-go open until three bounded groundwork passes are done; this is the only one of the three that
can *directly* recover recall rather than merely describe or localise the gap, and it costs no
rebuild — a genuine free look before committing to (or ruling out) an expensive architectural
change.

---

## Section 2 — Data Summary

### 2.1 Inputs

| Input | Detail |
|---|---|
| Runtime parameter setter | `Ft8Decoder.SetDecodeParams(k, corr, nhard)` → `ft8_set_decode_params` (shim 20260030+); driven through the public decoder API only — no `IFt8NativeInterop`, no `InternalsVisibleTo`. |
| Recall corpus | `20260706_live_run_2308/save/*.wav` — 4,075 files. Decoded: 2,037; skipped (not exactly 180,000 samples / unreadable): **0**. |
| Recall reference | WSJT-X `ALL.TXT` for the same session; low-SNR bands `< −15 dB` and `−15…−10 dB`, non-hashed, per `classify_cochannel.py`. |
| FP corpus | S5 (`s5-noise.json`, 4 parts × 30 = 120 slots) and S7 (`s7-compounding.json`, 21 parts × 5 = 105 slots, 215 injected signals), rendered once via `run_scenario.py --dry-run --dump-wav-dir` and reused across all 45 points. |
| Grid | 5 × 3 × 3 = **45 points**: `k ∈ {5,7,10,15,20}`, `corr ∈ {0.10,0.15,0.25}`, `nhard ∈ {40,60,80}`. Baseline `(10,0.10,60)` is an ordinary enumerated point. |
| Scorers (reused verbatim) | Recall: `classify_cochannel.py` (`parse`/`sig_key`/`freq_bin`/`is_hashed`/`classify_delta`/`BANDS`). FP: `harness/matcher.py` unmodified. |

### 2.2 Method (how each number is produced)

- **Decode.** For each grid point, `SetDecodeParams(k,corr,nhard)` then `DecodeAsync` every WAV,
  writing one WSJT-X-`ALL.TXT`-format line per decode (byte-for-byte `AllTxtWriter.cs:99`).
  Decodes are pure w.r.t. `(PCM, params)` (spec §3.2), so the harness loads each WAV once and
  decodes it under all 45 points in-process; parallelism is by **separate processes** only
  (each with its own native globals — never a shared-global race).
- **Recall (per point, pooled over both low-SNR bands).**
  `recall = (WSJT-X low-SNR decodes also produced by OpenWSFZ) / (WSJT-X low-SNR decodes)`,
  computed with `classify_cochannel`'s exact keying (`sig_key` = `(ts, 50 Hz-freq-bin, msg)`).
  `Δpp` is against the **offline baseline point**, so every comparison runs the identical code
  path (work-order acceptance criterion 3).
- **Per-class recovery.** The baseline point's miss set is classified Tight/Partial/Isolated via
  the shared `classify_delta` at the 15 Hz primary cutoff. For every other point, the per-class
  figure is the fraction of *those same baseline misses* the point now decodes — i.e. "which knob
  recovers which class of the baseline gap" (spec §1, §3.3). It is 0 % at the baseline by
  construction (a point cannot recover its own gap).
- **False positives.** Each synthetic slot is assigned a unique canonical 15 s cycle boundary
  (the offline analogue of the distinct boundaries a live playback lands each slot on), carried
  identically into `truth.csv` and the decode timestamps, so `matcher.py` buckets one slot per
  cycle. `matcher.py` runs unmodified per point per scenario; FP = OpenWSFZ decodes matching no
  injected truth. S5 FP/slot and S7 FP/slot are the two D-009 gates; S7 recovery = matched /215.

### 2.3 Tune/validate split (overfitting guard, spec §4.4a)

The 4,075 WAVs are sorted by embedded timestamp and split at the midpoint into a **tune** half
(first 2,037) and a **validate** half (last 2,038). The full 45-point grid
runs on **tune** only; the chosen candidate (plus baseline) is then scored out-of-sample on
**validate**. The FP arm is synthetic and fully reproducible, so it is not split.

### 2.4 Offline-baseline anchor (read before interpreting any recall number)

The recall arm can only run on the one session with retained WAVs (07-07). Re-decoding a slot's
WAV **offline** is not identical to the original live cycle (no live AGC/soft-limiter history, no
exact sample-clock/cycle-boundary alignment) — the same Gate-R caveat the isolated-miss pipeline
spec raises. Consequently the offline baseline's absolute recall is **not** expected to reproduce
the live-captured OpenWSFZ figure, and is **not** compared to it. Every recall delta in this report
is measured against the *offline* baseline point decoded through the identical harness path, which
is the only apples-to-apples reference. Absolute offline baseline recall on the tune half:
**36.14 %** (`wsjt_total=17,339`, `miss=11,073`); baseline miss
classes Tight **3,405** / Partial **5,537** / Isolated **2,131**.

---

## Section 3 — Results

### 3.1 The 45-point grid (tune half; FP arm synthetic)

Every recall figure sits next to its paired S5/S7 false-positive figures from the **same** point —
the D-009-origin two-sided rigour rule (spec §4.1). Baseline row is **bold**. `recall Δpp`, `S5 Δ`,
`S7 Δ` are versus the baseline `(10,0.10,60)`.

| k | corr | nhard | recall % | Δpp | S5 fp/slot | S5 Δ | S7 fp/slot | S7 Δ | S7 rec% | win |
|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 0.10 | 40 | 36.132 | -0.006 | 0.00833 | 0.0 | 0.00952 | -0.06667 | 87.442 | — |
| 5 | 0.10 | 60 | 36.132 | -0.006 | 0.21667 | 0.20834 | 0.49524 | 0.41905 | 87.442 | — |
| 5 | 0.10 | 80 | 36.132 | -0.006 | 0.25 | 0.24167 | 0.54286 | 0.46667 | 87.442 | — |
| 5 | 0.15 | 40 | 36.132 | -0.006 | 0.00833 | 0.0 | 0.00952 | -0.06667 | 87.442 | — |
| 5 | 0.15 | 60 | 36.132 | -0.006 | 0.16667 | 0.15834 | 0.40952 | 0.33333 | 87.442 | — |
| 5 | 0.15 | 80 | 36.132 | -0.006 | 0.175 | 0.16667 | 0.41905 | 0.34286 | 87.442 | — |
| 5 | 0.25 | 40 | 36.132 | -0.006 | 0.00833 | 0.0 | 0.00952 | -0.06667 | 87.442 | — |
| 5 | 0.25 | 60 | 36.132 | -0.006 | 0.08333 | 0.075 | 0.18095 | 0.10476 | 87.442 | — |
| 5 | 0.25 | 80 | 36.132 | -0.006 | 0.08333 | 0.075 | 0.18095 | 0.10476 | 87.442 | — |
| 7 | 0.10 | 40 | 36.127 | -0.012 | 0.0 | -0.00833 | 0.00952 | -0.06667 | 87.442 | — |
| 7 | 0.10 | 60 | 36.127 | -0.012 | 0.18333 | 0.175 | 0.53333 | 0.45714 | 87.442 | — |
| 7 | 0.10 | 80 | 36.127 | -0.012 | 0.20833 | 0.2 | 0.57143 | 0.49524 | 87.442 | — |
| 7 | 0.15 | 40 | 36.127 | -0.012 | 0.0 | -0.00833 | 0.00952 | -0.06667 | 87.442 | — |
| 7 | 0.15 | 60 | 36.127 | -0.012 | 0.15 | 0.14167 | 0.45714 | 0.38095 | 87.442 | — |
| 7 | 0.15 | 80 | 36.127 | -0.012 | 0.15833 | 0.15 | 0.46667 | 0.39048 | 87.442 | — |
| 7 | 0.25 | 40 | 36.127 | -0.012 | 0.0 | -0.00833 | 0.00952 | -0.06667 | 87.442 | — |
| 7 | 0.25 | 60 | 36.127 | -0.012 | 0.09167 | 0.08334 | 0.2 | 0.12381 | 87.442 | — |
| 7 | 0.25 | 80 | 36.127 | -0.012 | 0.09167 | 0.08334 | 0.2 | 0.12381 | 87.442 | — |
| 10 | 0.10 | 40 | 36.138 | 0.0 | 0.0 | -0.00833 | 0.0 | -0.07619 | 84.651 | — |
| **10** | **0.10** | **60** | **36.138** | 0.0 | 0.00833 | 0.0 | 0.07619 | 0.0 | 84.651 | — |
| 10 | 0.10 | 80 | 36.138 | 0.0 | 0.00833 | 0.0 | 0.07619 | 0.0 | 84.651 | — |
| 10 | 0.15 | 40 | 36.138 | 0.0 | 0.0 | -0.00833 | 0.0 | -0.07619 | 84.651 | — |
| 10 | 0.15 | 60 | 36.138 | 0.0 | 0.00833 | 0.0 | 0.07619 | 0.0 | 84.651 | — |
| 10 | 0.15 | 80 | 36.138 | 0.0 | 0.00833 | 0.0 | 0.07619 | 0.0 | 84.651 | — |
| 10 | 0.25 | 40 | 36.138 | 0.0 | 0.0 | -0.00833 | 0.0 | -0.07619 | 84.651 | — |
| 10 | 0.25 | 60 | 36.138 | 0.0 | 0.00833 | 0.0 | 0.00952 | -0.06667 | 84.651 | — |
| 10 | 0.25 | 80 | 36.138 | 0.0 | 0.00833 | 0.0 | 0.00952 | -0.06667 | 84.651 | — |
| 15 | 0.10 | 40 | 35.954 | -0.185 | 0.0 | -0.00833 | 0.0 | -0.07619 | 81.395 | — |
| 15 | 0.10 | 60 | 35.954 | -0.185 | 0.00833 | 0.0 | 0.04762 | -0.02857 | 81.395 | — |
| 15 | 0.10 | 80 | 35.954 | -0.185 | 0.00833 | 0.0 | 0.04762 | -0.02857 | 81.395 | — |
| 15 | 0.15 | 40 | 35.954 | -0.185 | 0.0 | -0.00833 | 0.0 | -0.07619 | 81.395 | — |
| 15 | 0.15 | 60 | 35.954 | -0.185 | 0.00833 | 0.0 | 0.04762 | -0.02857 | 81.395 | — |
| 15 | 0.15 | 80 | 35.954 | -0.185 | 0.00833 | 0.0 | 0.04762 | -0.02857 | 81.395 | — |
| 15 | 0.25 | 40 | 35.954 | -0.185 | 0.0 | -0.00833 | 0.0 | -0.07619 | 81.395 | — |
| 15 | 0.25 | 60 | 35.954 | -0.185 | 0.00833 | 0.0 | 0.00952 | -0.06667 | 81.395 | — |
| 15 | 0.25 | 80 | 35.954 | -0.185 | 0.00833 | 0.0 | 0.00952 | -0.06667 | 81.395 | — |
| 20 | 0.10 | 40 | 35.884 | -0.254 | 0.0 | -0.00833 | 0.0 | -0.07619 | 80.465 | — |
| 20 | 0.10 | 60 | 35.884 | -0.254 | 0.00833 | 0.0 | 0.04762 | -0.02857 | 80.465 | — |
| 20 | 0.10 | 80 | 35.884 | -0.254 | 0.00833 | 0.0 | 0.04762 | -0.02857 | 80.465 | — |
| 20 | 0.15 | 40 | 35.884 | -0.254 | 0.0 | -0.00833 | 0.0 | -0.07619 | 80.465 | — |
| 20 | 0.15 | 60 | 35.884 | -0.254 | 0.00833 | 0.0 | 0.04762 | -0.02857 | 80.465 | — |
| 20 | 0.15 | 80 | 35.884 | -0.254 | 0.00833 | 0.0 | 0.04762 | -0.02857 | 80.465 | — |
| 20 | 0.25 | 40 | 35.884 | -0.254 | 0.0 | -0.00833 | 0.0 | -0.07619 | 80.465 | — |
| 20 | 0.25 | 60 | 35.884 | -0.254 | 0.00833 | 0.0 | 0.00952 | -0.06667 | 80.465 | — |
| 20 | 0.25 | 80 | 35.884 | -0.254 | 0.00833 | 0.0 | 0.00952 | -0.06667 | 80.465 | — |

*S5 FP/slot and S7 FP/slot are false positives per rendered slot (S5: /120, S7: /105). `S7 rec%`
is per-signal recovery (matched/215). Full precision + raw counts in `sweep_grid.csv`.*

### 3.2 Pareto frontier (spec §3.4/§3.5)

A point counts as a candidate **win** only if it gains recall (`Δpp > 0`) **and** neither FP arm
regresses (`S5 FP/slot ≤ baseline` **and** `S7 FP/slot ≤ baseline`). A recall gain bought with an
FP regression is a **trade-off**, never a win, and is never averaged into a blended score.

**Zero Pareto wins — the baseline is Pareto-optimal.** Of the 45 points, **33** hold *both* FP
arms at or below the baseline (S5 ≤ 0.00833/slot **and** S7 ≤ 0.07619/slot), but **none of those 33
gains any recall** — their `recall Δpp` is `0.00` at best (the entire `k=10` family, which decodes
the identical low-SNR set as the baseline) and negative for `k=15`/`k=20`. The only points that
raise sensitivity at all are `k≤7`, and every one of those with a loose Hamming gate
(`nhard ∈ {60,80}`) **regresses both FP arms** (e.g. `k=5,corr=0.10,nhard=80`: S5 +0.242, S7 +0.467
per slot) while *still not gaining recall* (`Δpp = −0.006`). The recall surface is essentially
**flat**: the full spread across all 45 points is a **0.25 pp band**, monotone-decreasing in `k`,
with the maximum already at the baseline's `k=10`. No operating point dominates `(10,0.10,60)`; the
baseline sits on the frontier alone.

Read the two levers separately:

- **`k_min_score_pass2` (candidate admission).** Recall is flat-to-slightly-negative below 10
  (`k=5`→36.13 %, `k=7`→36.13 %, vs `k=10`→36.14 %) and falls above it (`k=15`→35.95 %,
  `k=20`→35.88 %). So `k=10` is *already* the recall optimum; admitting more pass-1 candidates
  recovers nothing, and admitting fewer costs a little. In the synthetic S7 arm, lower `k` does buy
  more co-channel recovery (87.4 % at `k≤7` vs 84.7 % at `k=10`) — but at a false-positive cost that
  fails the two-sided rule, and with **no** transfer to real off-air recall.
- **`osd_corr_threshold` and `osd_nhard_max` (OSD acceptance).** These move **only** false
  positives: recall is *identical* across all nine `(corr,nhard)` combinations at every fixed `k`
  (e.g. all nine `k=10` points read exactly 36.138 %). The OSD gates never admit a *new true*
  low-SNR decode on this corpus — only noise CRC-14 coincidences, which is exactly what D-009
  calibrated them to suppress.

### 3.3 Per-class recovery of the baseline gap (Tight / Partial / Isolated)

The baseline gap decomposes (tune half, 15 Hz primary cutoff) into **Tight 3,405 / Partial
5,537 / Isolated 2,131** misses. For each point, "recovery" is the fraction of *those* baseline
misses the point now decodes:

| Point | recall Δpp | Tight recov | Partial recov | Isolated recov |
|---|---|---|---|---|
| `k=5, 0.10, n40` (max candidate admission, tight OSD) | −0.006 | 0.0 % (0/3405) | 0.02 % (1/5537) | 0.09 % (2/2131) |
| `k=7, 0.10, n40` | −0.012 | 0.0 % (0) | 0.0 % (0) | **0.14 % (3/2131)** |
| **`k=10, 0.10, n60` (baseline)** | 0.0 | 0.0 % | 0.0 % | 0.0 % |
| `k=15, 0.10, n40` | −0.185 | 0.0 % | 0.0 % | 0.0 % |
| `k=20, 0.10, n40` | −0.254 | 0.0 % | 0.0 % | 0.0 % |

The **grid-wide maximum** recovery in any class is: Tight **0.0 %**, Partial **0.02 %** (1 miss),
Isolated **0.14 %** (3 of 2,131 misses, at `k=7`). Every non-zero cell belongs to a point that
also regresses the FP arms.

This arm empirically probes the isolated-miss pipeline spec's candidate-generation question:
lowering `k_min_score_pass2` is the candidate-admission lever, so **if** low-`k` recovered Isolated
misses, candidate admission would have been a bottleneck for them.

**Finding (cross-referenced to the isolated-miss pipeline spec).** Lowering
`k_min_score_pass2` all the way to 5 recovers **≈0 %** of the Isolated class (2 of 2,131 misses).
Candidate admission is therefore **not** the bottleneck for Isolated misses — this empirically
*refutes* the candidate-generation hypothesis for that class and points the isolated-miss diagnosis
at the other two outcomes it names (LDPC-convergence, or a live-path/timing difference), neither of
which any runtime knob in this sweep can touch. The Tight class is likewise untouched, consistent
with the 2026-06-17 probe's finding that candidate generation is not the Tight-class bottleneck
either.

### 3.4 Out-of-sample validation (tune → validate, spec §4.4a)

No candidate operating point emerged on the tune half (baseline dominated), so there is
**no candidate recall gain to hold out** — the overfitting guard is moot by construction here (you
cannot overfit a gain that does not exist). The validate half was decoded at the baseline point
alone to confirm the harness reproduces coherently out-of-sample: **baseline validate recall
52.85 %** (`wsjt_total=4,694`, `miss=2,213`; miss classes Tight 471 / Partial 721 / Isolated 1,021).

The tune (36.14 %) and validate (52.85 %) baseline recalls differ substantially because the two
halves are *different time spans* of the same ~17 h session (first ~8.5 h vs last ~8.5 h — different
bands and propagation), not different parameter points. This is exactly the single-session
limitation the spec flags (§4.4): absolute offline recall is corpus-dependent and is **not** the
measured quantity — the measured quantity is the per-point Δ against the baseline decoded through the
identical path, and that Δ is ≤ 0 for every point on the tune half regardless of the absolute
level.

### 3.5 FP-arm sanity (baseline reproduces the D-009 operating point)

The offline harness reproduces the shipped D-009 operating point on the synthetic arm,
confirming the FP measurement is trustworthy: at the baseline `(10,0.10,60)`, **S5 = 1 FP / 120
slots** (0.83 %/slot) and **S7 = 8 FP / 105 slots** with **84.7 % co-channel recovery** — the same
near-zero noise-floor false-positive rate shim 20260029 calibrated (`K=10` cut S5 FP by 94 % vs the
pre-gating `K=1` baseline). Loosening any knob reproduces the D-009 tension in the expected
direction (e.g. `k=5,corr=0.10,nhard=80` drives S5 to 30/120 and S7 to 57/105), and tightening it
suppresses FP — the arm is responding correctly, so the "no recall gain within the FP budget"
result is not an artefact of an insensitive FP oracle.

---

## Section 4 — Verdict Table

| Item | Result |
|---|---|
| Headline outcome (spec §3.5) | **Baseline dominates** (spec §3.5, outcome 3) — the runtime knobs are provably exhausted. |
| Pareto-dominating runtime point? | No. 0 of 45 points beat `(10,0.10,60)`. Maximum recall Δ over the whole grid is **0.00 pp**; every recall-positive lever is absent. |
| Recall recoverable at zero FP cost | **0.00 pp.** No runtime operating point recovers any D-001 low-SNR recall at or below the baseline FP budget. |
| Which knob moved which class | `k_min_score_pass2` moves recall ≤ 0.25 pp (optimum already at 10) and S7 co-channel recovery monotonically (87 %→80 % as k 5→20); `osd_corr_threshold`/`osd_nhard_max` move **only** false positives — recall is identical across all nine gate combos at every k. |
| Out-of-sample (validate) confirmation | N/A — no candidate emerged to hold out; baseline recall reproduces coherently on the validate half (52.85 %). |
| Recommendation | **No change to the shipped defaults.** The residual D-001 gap is not runtime-addressable — it is a compile-time (Phase 2) or H7 question. (Formal recommendation: QA, §5.) |

**In plain terms.** OpenWSFZ already exposes the three decode knobs that a settings change could
turn, and this sweep turned all of them, jointly, across their full documented ranges, against the
real D-001 recall corpus and the D-009 false-positive scenarios — 45 operating points, ~106,000
offline decodes, zero rebuilds. **Nothing beat the shipped baseline.** The recall surface is flat to
within a quarter of a percentage point and already peaks at the shipped `k=10`; the two OSD gates
move only false positives, never a single additional true low-SNR decode. There is no cheap
settings-change win hiding in the runtime parameters.

This is the **cleanest possible input to the H7 (MMSE) go/no-go**: the low-cost option is not
merely untried, it is *tried and exhausted*. The residual low-SNR gap that remains after the runtime
knobs are tapped out is, by elimination, a **compile-time** question (LDPC iteration depth, OSD
`ndeep`, pass-0 candidate limits `K_MIN_SCORE`/`K_MAX_CANDIDATES` — all constants requiring a
rebuild, i.e. a scoped Phase 2) or an **H7** question. The Captain can now weigh H7 knowing the
runtime lever is genuinely empty, not merely unexplored.

**Two honest observations recorded but explicitly *not* recommended here (out of scope — this is a
D-001 recall pass, not a D-009 re-calibration):**

1. *The Isolated-class answer.* Lowering `k` to 5 recovered ≈ 0 % of the 2,131 Isolated misses.
   Candidate admission is not their bottleneck — this refutes the candidate-generation hypothesis
   for that class (cross-referenced in §3.3) and redirects the isolated-miss diagnosis at LDPC
   convergence or a live-path/timing difference.
2. *An FP-side bycatch.* On the **synthetic** arm only, tightening the OSD gates at the baseline
   `k`/`corr` (e.g. `nhard` 60→40, or `corr` 0.10→0.25) eliminates *all* residual S5/S7 false
   positives at **zero** recall cost (`Δpp = 0.00`). That hints the shipped gates may be marginally
   loose against pure synthetic noise — but this is a D-009 question on synthetic data, must not be
   read as a shippable change from a single synthetic arm, and is flagged only so QA/Captain can
   decide whether it warrants its own pass.

---

## Section 5 — Recommendations

**Formal recommendation: no change to the shipped defaults.** The null hypothesis stands — of the
45 enumerated operating points (baseline included, as an ordinary point, per acceptance criterion
3), zero Pareto-dominate `(k=10, corr=0.10, nhard=60)`. The 33 points that hold both FP arms at or
below baseline gain no recall (best case `Δpp = 0.00`, i.e. the `k=10` family reproducing the
baseline exactly); every point that gains any sensitivity (`k ≤ 7`) does so by regressing both S5
and S7 false positives. There is no candidate here to carry forward to a live A/B (spec §4.4b) —
that confirmatory step only applies when a point clears the Pareto bar on the offline sweep, and
none did.

**This is the clean trigger the spec anticipated (§3.5, outcome 3).** With the runtime knobs now
provably exhausted rather than merely untried, the residual D-001 gap is, by elimination, one of:

1. A **compile-time (Phase 2)** question — LDPC iteration depth, OSD `ndeep`, or the pass-0
   candidate limits `K_MIN_SCORE`/`K_MAX_CANDIDATES`, all of which require a native shim rebuild and
   are explicitly out of scope for this pass (spec §4.6, guardrails §3).
2. An **H7 (MMSE joint demodulation)** question — the Captain can now weigh that go/no-go knowing
   the zero-cost option has been tried and closes nothing, not merely that it was never attempted.

I do **not** recommend widening this pass to chase either of the two side-observations recorded in
§4 (the Isolated-class candidate-generation refutation, or the hint that the OSD gates may be
marginally loose against pure synthetic noise). Both are informative bycatch of a D-001 recall
pass, not D-009 re-calibration evidence in their own right — the second in particular rests on a
single synthetic arm and must not be read as a shippable finding. Either is a legitimate candidate
for its own narrowly scoped follow-up pass if the Captain wants it pursued, but neither should be
folded into this change's no-rebuild guarantee after the fact.

**Process note.** The harness, scoring reuse, and reporting all satisfy this work order's
acceptance criteria (§4 below) and the mechanical pre-merge gate (HK-006) passes clean on a fresh
checkout of this branch (one WARN — the pre-existing local AOT toolchain gap, environmental, not
code). Approved for merge; see the QA verdict delivered alongside this report.

---

## Appendix A — Reproduction

```
# From qa/rr-study/. Recall corpus + WSJT-X ALL.TXT are local/git-ignored (main working tree).
cd qa/rr-study/d001-param-sweep-2026-07-22
dotnet build -c Release D001ParamSweep.csproj
NSHARDS=12 bash run_sweep.sh            # phases A-F: split, FP corpora, FP decode+score,
                                        # recall tune decode+score, assemble+verdict, validate
```

- **Harness (C#):** `D001ParamSweep.csproj` / `Program.cs` — drives `Ft8Decoder` via public API
  only (`SetDecodeParams` + `DecodeAsync`); links `tests/OpenWSFZ.Ft8.Tests/WavReader.cs` verbatim.
- **Scorer (Python):** `sweep_driver.py` — reuses `classify_cochannel.py` (recall) and
  `harness/matcher.py` (FP) unchanged; `run_sweep.sh` is the end-to-end orchestrator.
- **`run_scenario.py` change:** one additive flag, `--dump-wav-dir`, gated and independent of the
  playback path. Verified unaffected: a `--dump-wav-dir` on/off pair of `--dry-run` runs produced
  byte-identical `truth.csv` in columns 1–8; the only difference was the inherently wall-clock
  `cycle_utc` column (the two runs crossed a 15 s boundary), which varies between *any* two
  `--dry-run` invocations regardless of the flag. (work-order step 8.)
- **`classify_cochannel.py` change:** additive only — a module-level `classify_delta(...)` extracted
  from the existing inner closure (behaviour-identical; the closure now delegates to it) plus an
  optional `session_dir` parameter on `classify_session`. Regression-checked: the modified
  `classify_session` reproduces the committed Option B 07-07 numbers exactly (tight=3879,
  partial=6295, isolated=3688).
