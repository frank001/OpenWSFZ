# QA → Architect: B-pos-A results (the lattice-position arm)

**Author:** QA
**Date:** 2026-08-21 13:51 UTC (`date -u`, HK-017)
**Spec:** `qa/rr-study/2026-08-21-1330-architect-to-qa-spec-b-pos-a-lattice-position-arm.md`
**Script:** `qa/rr-study/r2-coherent-llr-instrument/b_pos_a_lattice_position.py`
**Artefacts:** `qa/rr-study/r2-coherent-llr-instrument/results/b_pos_a_report.json`,
`.../b_pos_a_run.log`
**Binary under test:** current merged `main` (`a420016`), shim 20260043, DLL SHA256
`1889408787...` — pin verified before running.

🔴 **DIAGNOSTIC ONLY, per spec Sec.0.** No ROW, no PASS/FAIL, no `f_net`, no gate defined or
read. **ROW 0g is unchanged: FIRED, task 4.3 stays VOID, ROW 3 is not declared, Route B2 is
not dead.** No `src/`/`native/` edit, no rebuild, no push, no merge — HK-011 not engaged, as
specced (the arm is a caller-side loop over the existing two-float export). This does **not**
authorise changing design.md D1 — that ruling (1201 spec §5) is still the Captain's and still
owed.

---

## 0. Preconditions (spec §4) — both mechanical, both clear

- **P1 — control cell reproduces ROW 0g-2 exactly.** `n_delivered=193`, `n_clusters=190`,
  `d_control=-67.000` — **all three exact**, `abs(d_control - (-67.0)) < 1e-9`. The harness is
  calling what 0g-2 called; every other cell is interpretable.
- **P2 — chosen optimum interior (HK-026).** Grid's global best sits at `m=0` (dead centre);
  coherent's at `m=-2`. Neither touches the swept boundary `m=±3` — **no widening needed**,
  `widen_steps=0`.

Sample: 200-row deterministic draw (seed 20260821, verbatim from ROW 0g-2), 7 dropped
(`no_true_codeword`), 193 control-delivered, 190 distinct clusters — identical to 0g-2's own
numbers, as required by P1.

---

## 1. §5.2 SECONDARY — does an own-best global offset close the gap?

| | cell (m,n), quanta | cluster-median `n_err` | `n_clusters` |
|---|---|---:|---:|
| grid, own best | (0, 0) | 11.0 | 190 |
| coherent, own best | (**-2**, 0) | 20.0 | 190 |

```
d_global (grid@best - coh@best) = -6.000   CI95 [-7.000, -4.000]   n_rows=193  n_clusters=190
d_control (shared m=0,n=0)       = -67.0   CI95 [-71.0,  -65.0]    (reference, ROW 0g-2)
```

**The gap collapses from -67 to -6 — CI95 excludes -67 by a wide margin (blind prediction #3,
~70% confidence: CONFIRMED).** Coherent does not reach parity with grid — `d_global`'s CI95
`[-7,-4]` still excludes 0, `p_two_sided=0.000` — so at its OWN best lattice cell, coherent is
still measurably worse than grid at grid's own best cell (blind prediction #4, coherent reaching
parity, ~30% confidence: **NOT confirmed**, but the residual gap is ~9% of the original
magnitude, not the ~50%+ "partial recovery" the prediction's framing suggested).

**Coherent's own best cell is `m=-2`: exactly 2 time quanta = 0.16 s = one full FT8 symbol
period, in the direction opposite grid's.** This is the same displacement Phase A's A2 read
(`~0.12-0.15s`, now precisely identified as one symbol) and is consistent with §2.2's ruled-out
benign causes leaving a real, as-yet-unexplained one-symbol convention gap between the two
paths.

---

## 2. §5.1 PRIMARY — is the displacement CONSTANT or SCATTERED?

Per-row argmin over the full 21-cell grid, both axes jointly (so the null below is the spec's
own `1/21`). **Winner's-curse bias named per spec §3.2/§5.1: this is a per-row argmin, and the
bias runs toward whichever path varies more across position — expected to be coherent.**

| path | modal cell (m,n) | `frac_at_mode` | null (1/21) | m-axis marginal mode | marginal `frac` |
|---|---|---:|---:|---|---:|
| **coherent** | **(-2, 0)** | **0.544** (105/193) | 0.048 | **-2** | 0.617 |
| grid | (0, 0) | 0.606 (117/193) | 0.048 | 0 | 0.674 |

Full per-cell histograms in the JSON (`argmin_shape`). Coherent's mass is concentrated, not
diffuse: `m ∈ {-2, -1, -3}` together account for 192/193 rows (`m_counts`: -2→119, -1→52,
-3→21, 0→1), i.e. essentially every row's own-best time offset sits in the same direction and
mostly at the same one-symbol displacement.

**Reading against the interpretation aid (spec §5.1 table):** `frac_at_mode=0.544` at a
**non-zero** mode is on the **high** side, not diffuse and nowhere near the `0.048` null — over
**11×** the null rate. It falls just short of the blind prediction's own `≥0.6` bar (blind
prediction #2, ~55% confidence) on the strict joint-cell statistic, but **clears it on the
m-axis marginal (0.617)**, which is the axis the one-symbol-displacement hypothesis is actually
about. I read this as **substantially closer to CONSTANT than to SCATTERED** — a plurality
result, not a knife-edge one, and I would not want the shortfall on the strict 21-cell number to
be read as "diffuse."

---

## 3. Blind-prediction scoring (spec §6)

| # | prediction | stated | result |
|---|---|---:|---|
| 1 | P1 reproduces exactly | ~90% | **CONFIRMED** |
| 2 | coherent `frac_at_mode ≥ 0.6` at non-zero mode | ~55% | **PARTIAL** — 0.544 joint-cell, 0.617 marginal-m |
| 3 | `d_global` CI95 excludes -67 | ~70% | **CONFIRMED** ([-7,-4]) |
| 4 | `d_global ≥ 0` (parity) | ~30% | **NOT CONFIRMED** (-6.0, CI excludes 0 too) |
| 5 | P2 fires (boundary, needs widening) | ~15% | **DID NOT FIRE** |

---

## 4. What this does and does not establish

- **Established, mechanically:** letting each path read at its own best lattice cell (no native
  change) recovers ~91% of ROW 0g-2's `d_real` magnitude (-67 → -6). The recovery is
  concentrated on the coherent path moving to `m=-2` — the SAME one-symbol displacement A2 (and
  now this arm, independently) both read — while grid barely moves off its already-corrected
  anchor. The displacement is **directionally and quantitatively consistent across two separate
  measurements now** (Phase A's continuous sweep and this arm's quantised grid).
- **Not established:** *why* the one-symbol offset exists. §2.2 ruled out the two obvious benign
  causes (symbol-index mapping, FIR group delay) by code-read; this arm adds a third
  measurement of the same displacement's magnitude and shape but does not locate its source in
  the code.
- **Not established:** full parity. A residual, statistically real gap remains at each path's
  own best cell (-6.0, CI95 excludes 0) — position is the dominant lever but not the whole
  story; something (fusion, residual-frequency handling within a symbol, or channel) still costs
  coherent ~6 bit-errors even when position is no longer shared.
- **Not re-litigated:** ROW 0g's own verdict, gate status, or Route B2's standing. Task 4.3
  stays VOID; ROW 3 is not declared.

---

## 5. For the Architect (§7 branches, not mine to call)

The result sits closest to spec §7's first branch — **"constant displacement, §5.1 high at a
non-zero mode"** — on the marginal-m statistic and the concentrated `m_counts` histogram, though
the strict joint-cell `frac_at_mode` (0.544) is short of the pre-registered `0.6` bar. Per §7
that branch reads as: *"a narrow, D1-compatible fix becomes the candidate, and B3 likely stays
held. I bring the Captain the ruling with numbers."* The remaining ~-6 residual gap (not fully
closed by position alone) is the one piece of evidence pulling toward §7's third branch
("`d_global` barely moves ⇒ position is not the lever... B3 earns its Developer session") — but
a 91% reduction is not "barely," so I read the overall shape as favouring the first branch with
an acknowledged residual, not the third.

I make no ruling here — §7's branches are the Architect's to weigh, and design.md D1's amendment
remains the Captain's (1201 spec §5).

---

**No `src/`/`native/` edit, no rebuild, no push, no merge.** Full per-cell tables (all 21 cells
× both paths, cluster-median and per-row argmin histograms) are in `b_pos_a_report.json`.
