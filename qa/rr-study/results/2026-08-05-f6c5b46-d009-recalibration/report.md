# D-009 — Parameter Recalibration: Results Report

| Field | Value |
|---|---|
| Defect ID | D-009 (false-positive guard calibration); triggered by the S1-S8 repeat's Finding 1 (`ddcc455`) |
| Type | Offline decode sweep (no `src/` product or native-code change — QA tooling only) |
| Governing spec | `qa/rr-study/2026-08-05-2003-architect-to-qa-spec-d009-recalibration.md` |
| Task breakdown | `qa/rr-study/2026-08-05-2018-qa-tasks-d009-recalibration.md` (QA-authored, HK-015) |
| Analysis date | 2026-08-05 / 2026-08-06 (spans UTC midnight) |
| Repo HEAD at analysis time | `f6c5b46` (native shim unchanged — this sweep drives runtime `ft8_set_decode_params` only) |
| Recall corpus | `20260803_live_run_1713/owsfz`, decisive epoch only (`260803_185914` onward), WSJT-X `ALL.TXT` same epoch |
| FP corpus | Synthetic S5 (`s5-noise-wide.json`, 120 slots) + S7 (`s7-compounding.json`, 105 slots / 215 signals), seeded/reproducible |
| Harness | `qa/rr-study/d001-param-sweep-2026-07-22/` (C# decode driver, **unmodified**) + `sweep_driver.py` (**unmodified**) + two new QA scripts (`density_stratify.py`, `apply_row_rule.py`) for spec Sec.5.4/5, which had no `2026-07-22-ea88d12` precedent |
| Aggregate data | `sweep_grid.csv` (45-row grid), `fp_by_density.csv` (Sec.5.4 stratification), both this directory |
| Status | **COMPLETE — ROW 1 fired. Recommendation NOT shipped — awaiting Captain sign-off (spec Sec.6.2).** |

> **NFR-021 handling.** All raw artefacts (WAVs, per-point `ALL.TXT`, `truth.csv`, per-point decode
> output, shard logs) stayed local under the harness's git-ignored `_work_recal/`. Only this
> report, `sweep_grid.csv`, `fp_by_density.csv`, and `orchestration.log`/`row_verdict.txt`
> (phase timestamps and the mechanical rule evaluation — no callsigns, no message text) are
> committed.

---

## Section 1 — Study Hypothesis

**Question (spec Sec.5, pre-committed before any decode ran).** Across the three D-009
runtime-configurable OSD-gate parameters (`k_min_score_pass2`, `osd_corr_threshold`,
`osd_nhard_max`), does any operating point on a current, post-`be5960a` corpus dominate the
shipped baseline `B = (10, 0.10, 60)` — gaining recall against WSJT-X while holding both the S5
(pure-noise) and S7 (co-channel) synthetic false-positive rates at or below baseline?

**Pre-registered rule (spec Sec.5, transcribed mechanically into `apply_row_rule.py`, not
re-derived here):**

- `WIN(p) := rec(p) > rec(B) AND s5(p) <= s5(B) AND s7(p) <= s7(B)`
- `RELIEF(p) := s5(p) <= 0.50*s5(B) AND s7(p) <= s7(B) AND rec(p) >= rec(B) - 1.00`
- `B_on_frontier := no p != B with rec(p) >= rec(B) AND s5(p) <= s5(B) AND s7(p) <= s7(B)`
- ROW 1 (`exists p, WIN(p)`) fires before ROW 2/3/4 are even evaluated — strict order, first
  match wins.

**Why now.** The S1-S8 repeat on `3bd4cd0` (six weeks / 104 `src/` commits after the last D-009
check) found OpenWSFZ false-positive decodes correlating with simultaneous-candidate density, not
SNR — a leak the managed structural filter (`IsPlausibleMessage`) cannot close because the leaking
shape (3-token `CALL CALL GRID`) is syntactically well-formed. The native OSD gate swept here is
the only lever in scope that can move it (spec Sec.2.3).

**Corpus caveat carried forward from Sec.7 of the spec.** This harness bypasses `CycleFramer`
entirely (per-slot WAVs are decoded directly) — it recalibrates the parameters against a
post-`be5960a`-framed corpus, but cannot itself confirm the drift fix moved the optimum; that
stays open. The FP arm is synthetic; the recall arm is real off-air audio; the two are never
blended into one score.

---

## Section 2 — Data Summary (framing; full method in the spec Sec.3)

- **Recall arm**: `owsfz/wav` restricted to filename `>= 260803_185914` — **4,551** WAVs (index
  420 of 4,971 onward; the 420 WAVs before that timestamp belong to a separate process instance
  per the daemon's own log split and are excluded, not part of the "one contiguous 18.96 h
  decisive epoch" the spec names). Reference: `wsjt-x/ALL.TXT`, same restriction. No tune/validate
  split — the decision rule is evaluated directly on the full restricted corpus (unlike
  `ea88d12`; this spec has no held-out arm).
- **FP arm**: S5 = 120 pure-noise slots, S7 = 105 co-channel slots / 215 injected signals,
  regenerated from seed via `run_scenario.py --dry-run --dump-wav-dir`. **Generated and decoded
  strictly sequentially, S5 then S7, never concurrently** (spec Sec.4 constraint 1 — the June
  `d009-k10-confirm-s5`/`-s7` `CONTAMINATED.md` precedent). Decoded **with `--debug-log`** (FP arm
  only, per spec Sec.4.5) to support Sec.5.4.
- **Grid**: 45 points, `k in {5,7,10,15,20} x corr in {0.10,0.15,0.25} x nhard in {40,60,80}`,
  identical to `ea88d12` so the two are cell-for-cell comparable. `B = (10, 0.10, 60)` is an
  ordinary enumerated point.
- **Execution note**: the recall arm (4,551 WAVs x 45 points, ~600 ms/decode) is the dominant
  cost. Ran sharded across 12 processes (75% of this box's 16 logical cores, throttled mid-run at
  the Captain's request — the first attempt at 16 shards had already restarted cleanly with no
  data loss, see `orchestration.log`). Total Phase D wall-clock: ~2h58m.

---

## Section 3 — Results

### 3.1 Baseline anchor

`B = k10_c0.10_n60`: **recall = 41.508%** (17,469 WSJT-X low-SNR decodes in-epoch, 10,218 missed),
**S5 FP/slot = 0.00833** (1 FP / 120 slots), **S7 FP/slot = 0.07619** (8 FP / 105 slots), **S7
signal recovery = 84.651%**.

### 3.2 ROW 1 fired — the optimum has moved

`apply_row_rule.py` (mechanical, spec rule transcribed verbatim): **6 WIN(p) candidates**, **15
RELIEF(p) candidates** (superseded — ROW 1 fires first), baseline **not** on the naive
dominance frontier (13 points dominate it outright).

**All 6 winners** (every one has `nhard=40`; `corr` has no measurable effect at `nhard=40` for
either `k`):

| point | k | corr | nhard | recall % | Δpp vs B | S5 fp/slot | S7 fp/slot | S7 fp Δ | S7 recovery % |
|---|---|---|---|---|---|---|---|---|---|
| **k5_c0.10_n40** | 5 | 0.10 | 40 | **41.617** | **+0.109** | 0.0 | 0.00952 | −0.06667 | 87.442 |
| k5_c0.15_n40 | 5 | 0.15 | 40 | 41.617 | +0.109 | 0.0 | 0.00952 | −0.06667 | 87.442 |
| k5_c0.25_n40 | 5 | 0.25 | 40 | 41.617 | +0.109 | 0.0 | 0.00952 | −0.06667 | 87.442 |
| k7_c0.10_n40 | 7 | 0.10 | 40 | 41.605 | +0.097 | 0.0 | 0.00952 | −0.06667 | 87.442 |
| k7_c0.15_n40 | 7 | 0.15 | 40 | 41.605 | +0.097 | 0.0 | 0.00952 | −0.06667 | 87.442 |
| k7_c0.25_n40 | 7 | 0.25 | 40 | 41.605 | +0.097 | 0.0 | 0.00952 | −0.06667 | 87.442 |

Nominee per spec Sec.5 ("argmax rec(p) among winners"): **`k5_c0.10_n40`** — +0.109 pp recall,
S5 FP eliminated entirely (58 → 0 across the whole arm), S7 FP down 87.4% (8 → 1).

### 3.3 The global Pareto frontier differs from the WIN set — reported per spec Sec.5

`WIN(p)` is defined strictly relative to `B`; it is **not** the same set as the points no other
point dominates. Computed directly (any `p` with no `q` weakly-better-on-all-three-and-
strictly-better-on-one): **frontier size 6/45**, but it swaps the `k7` triple for a `k10` triple:

| point | recall % | Δpp vs B | S5 fp/slot | S7 fp/slot | note |
|---|---|---|---|---|---|
| k5_c0.10_n40 | 41.617 | +0.109 | 0.0 | 0.00952 | argmax-recall WIN nominee |
| k5_c0.15_n40 | 41.617 | +0.109 | 0.0 | 0.00952 | — |
| k5_c0.25_n40 | 41.617 | +0.109 | 0.0 | 0.00952 | — |
| k10_c0.10_n40 | 41.508 | 0.000 | 0.0 | **0.0** | ties B's recall exactly; **zero FP on both synthetic arms** |
| k10_c0.15_n40 | 41.508 | 0.000 | 0.0 | 0.0 | — |
| k10_c0.25_n40 | 41.508 | 0.000 | 0.0 | 0.0 | — |

The `k10_*_n40` points don't qualify as `WIN(p)` — `recall_dpp = 0.000`, and the rule requires
`rec(p) > rec(B)` strictly — but they Pareto-dominate `B` (identical recall, strictly fewer FPs
on **both** arms, `S7 fp/slot = 0.0` — 0 of 105 slots, vs baseline's 8) and change only **one**
parameter from the shipped config (`nhard` 60→40; `k` and `corr` unchanged). Flagged for the
costed menu below — the rule correctly excluded it from "winner," but the Captain should see it.

**Every point on both sets shares `nhard = 40`.** `corr` (0.10/0.15/0.25) has zero measurable
effect on recall or FP at `nhard = 40` for any `k` tested — its effect (visible at `nhard=60/80`,
e.g. `k5_c0.25_n60` more than halves `k5_c0.10_n60`'s FP rate) is fully saturated away once
`nhard` drops. `k` is the only recall lever (monotonic: 41.617% at k=5 down to 41.348% at k=20);
`nhard` is overwhelmingly the FP lever.

### 3.4 Section 5.4 — density stratification (reported, not gated)

Per-cycle candidate load (pass-0 + pass-1 count from `--debug-log`) bucketed
`0-9/10-24/25-49/50-99/100+`, FP-per-slot within bucket. Baseline vs. the two frontier
candidates above:

| point | scenario | bucket | slots | FP | FP/100 slots |
|---|---|---|---|---|---|
| **k10_c0.10_n60 (B)** | S5 | 10-24 | 82 | 0 | 0.0 |
| | S5 | 25-49 | 38 | 1 | 2.63 |
| | S7 | 25-49 | 77 | 7 | **9.09** |
| | S7 | 50-99 | 27 | 1 | 3.70 |
| k5_c0.10_n40 | S5 | 100+ | 120 | 0 | 0.0 |
| | S7 | 100+ | 105 | 1 | 0.95 |
| k10_c0.10_n40 | S5 | 10-24 | 82 | 0 | 0.0 |
| | S5 | 25-49 | 38 | 0 | 0.0 |
| | S7 | 25-49 | 77 | 0 | 0.0 |
| | S7 | 50-99 | 27 | 0 | 0.0 |

Full 450-row table in `fp_by_density.csv` (all 45 points x 2 scenarios x 5 buckets).

Two things worth the Captain's attention, neither part of the gated rule:

1. **Baseline's leak is concentrated exactly where Finding 1 predicted** — the 25-49 and 50-99
   candidate buckets, i.e. the co-channel/dense regime, not the sparse one. This is the same
   mechanism `ddcc455`'s Finding 1 described, now reproduced under controlled synthetic
   conditions rather than inferred from a live daemon log.
2. **The bucketing variable is confounded with `k` itself.** `k_min_score_pass2` gates how many
   raw candidates get counted as "found" before OSD — at `k=5` every single slot in both arms
   falls in the `100+` bucket (vs. baseline's spread across 10-24/25-49). The stratification is
   real and reproducible, but it cannot be read as "the same operating point behaves differently
   at different densities" across different `k` rows — only within a fixed `k` (which this sweep
   didn't vary density for, since S5/S7 each have one candidate-load profile). A future
   density-varying corpus (§5.4's own stated purpose) would need to hold `k` fixed and vary
   density directly to separate the two effects.

---

## Section 4 — Verdict Table

| Row | Fired? | Consequence |
|---|---|---|
| ROW 1 (`WIN` exists) | **YES** | Optimum MOVED. Captain sign-off required before any value ships. |
| ROW 2 (`RELIEF`, no `WIN`) | N/A (ROW 1 fired first) | — |
| ROW 3 (`B_on_frontier`) | N/A | — |
| ROW 4 (contradiction) | N/A | — |

Full machine output: `row_verdict.txt` (this directory).

---

## Section 5 — Recommendations (costed menu — Captain decision required, spec Sec.6.2)

QA does not ship or recommend a default. Per spec Sec.6.2, expect a menu, not a winner — and
per the June D-009 investigation's own precedent, the shipped baseline already fails one of its
own gates (`co_channel_sweep` 86.67% < 89%), so "no change" is not a neutral default either.

| Option | Change from shipped | Recall | S5 FP | S7 FP | Trade |
|---|---|---|---|---|---|
| **A — argmax-recall winner** | `k` 10→5, `nhard` 60→40 | +0.109 pp | 58→0 | 8→1 | Two parameters move; small but real recall gain, near-total FP elimination on both synthetic arms. |
| **B — minimal-change, zero-FP tie** | `nhard` 60→40 only | +0.000 pp (tied) | 58→0 | 8→**0** | One parameter moves; recall unchanged, **zero FP on both arms tested**; not a `WIN` under the strict rule (no recall gain) but Pareto-dominates B. |
| **C — no change** | none | 41.508% | 1/120 | 8/105 | Known to already fail `co_channel_sweep` (86.67%<89%, June precedent). Baseline is provably dominated (Sec.3.3) — "no change" is a choice to accept known-suboptimal FP behaviour, not a neutral default. |

QA's observation, not a recommendation: every winning and every frontier point shares
`nhard=40`; `corr` is inert at that setting. If the Captain wants the smallest possible change to
verify before wider adoption, **Option B changes exactly one constant** and was the cleanest
result in the grid (zero FP on 225 synthetic slots). Option A trades a second parameter change for
the paper recall gain, which is small (+0.1pp) against 17,469 WSJT-X reference decodes — real, but
modest.

**Not addressed here (out of spec scope, Sec.1):** bisecting which of the three flagged commits
moved the leak; the two managed-filter rule gaps (Sec.6.3 of the spec — recorded there for
whoever next touches `IsPlausibleMessage`, requires a Developer session); `K_MAX_CANDIDATES_PASS2`.
Whether `be5960a` itself moved the optimum remains open (Section 1 caveat) — only Arm A (spec
Sec.3.4, not authorised) or a live re-run would close that.

**QA does not ship, merge, or push any parameter value.** Awaiting Captain sign-off per spec
Sec.6.2 / HK-010 / HK-014.
