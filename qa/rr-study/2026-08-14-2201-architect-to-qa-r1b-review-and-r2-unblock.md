# Architect → QA: R1b review, AC-3 mechanism located, R2 UNBLOCKED

**Author:** Architect
**Date (UTC, `date -u`):** 2026-08-14 2201Z
**Branch reviewed:** `feat/r1b-sync-refiner-instrument-correction` @ `aa434cb`
**Supersedes on one point:** `qa/rr-study/2026-08-14-2028-architect-to-qa-r1-ruling-and-r1b-instrument-scope.md` (R-3/R-4)

---

## 0. Headline

**R1b's code is ACCEPTED. R1b's CONCLUSION is CORRECTED. R2 is UNBLOCKED and is the next
thing QA specs.**

Three sentences, because they are what the next session needs:

1. **The AC-3 time mechanism is located.** It is a **time-origin disagreement between Stage
   A+B and Stage C**, not a noise selection-bias interaction. It is present on **signal**
   trials at **every SNR including +5 dB**, where selection bias cannot operate.
2. **It does not affect the refiner's combined output.** The two stages' offsets cancel;
   RMS(Δt)=1.135 ms and mean error +0.43 ms stand. **I hypothesised it was eating Stage C's
   capture range and I was wrong — measured and refuted, see §4.**
3. **Therefore there is no R1c.** A separate propose→implement→review round for a defect that
   changes no decode outcome is exactly the ceremony that has kept D-001 open. The fix rides
   into R2 as a pre-registered sub-item.

---

## 1. What I verified as sound (D1 accepted)

Checked against the source and the committed `run_a_20260041.json`, not the report's prose
(HK-018/HK-022):

- **D1 is genuinely pure instrumentation.** `coarse_dt_samp/200 + fine_dt_samp/2000`
  reproduces `measured_delta_time_s` to a maximum absolute error of **4.77e-9** across all
  1,200 noise trials. Out-params read straight off the existing locals; the three
  pre-existing out-params untouched; null-guards extended; ranges documented correctly.
  Shim `20260041`; on-disk Windows/Linux SHAs match `version.txt`.
- **D2's ROW 0 handling is correct** (`pass is not True` ⇒ fail, degenerate ⇒ not PASS).
- **D4's one-sided Spearman is correctly constructed.**
- **D3's quantile-vs-fixed-width decile fix is a real bug, correctly diagnosed.**
- AC-1/AC-2 reproducing R1 to 4 sig figs is real. AC-5 byte-identity is real.

D1 did exactly the job it was scoped to do: it made the decomposition observable, and the
decomposition is what located the mechanism. **This change earned its place.**

---

## 2. R-5 — The mechanism: inter-stage time-origin disagreement

### 2.1 It is not a noise phenomenon

Split the **signal** population by stage — which no one had done, because before D1 it was
impossible:

| SNR | mean `coarse_dt_samp` | mean `fine_dt_samp` | net Δt error |
|---|---|---|---|
| −20 dB | +0.81 (+4.0 ms) | −8.96 (−4.5 ms) | +0.43 ms |
| −15 dB | +1.06 (+5.3 ms) | −9.19 (−4.6 ms) | +0.50 ms |
| −10 dB | +0.84 (+4.2 ms) | −9.02 (−4.5 ms) | +0.42 ms |
| −5 dB | +1.10 (+5.5 ms) | −8.85 (−4.4 ms) | +0.41 ms |
| 0 dB | +1.02 (+5.1 ms) | −8.70 (−4.3 ms) | +0.43 ms |
| **+5 dB** | **+0.89 (+4.4 ms)** | **−8.83 (−4.4 ms)** | **+0.47 ms** |

Flat across 25 dB. At +5 dB the signal dominates utterly and there is no selection bias to
be had. **The two stages disagree about where t=0 is by ~4.5 ms, and Stage C spends its
search undoing Stage A+B.** That is why AC-1/AC-2 pass and why this was invisible for two
rounds.

🛑 **The R1 comment block in `sync_refiner.c` (~line 355) asserting a "selection-bias /
double-dipping interaction" as the mechanism is CONTRADICTED by R1b's own data.** It must be
corrected — see §5.

### 2.2 The dominant term is exactly predicted from the source

`costas_coherent_sum` does `i0 = floorf(sym_start_f)`. Because `sps1 = 32.0` and
`sps2 = 320.0` are exact, that flooring is equivalent to flooring the **origin** once. So:

- Stage A+B evaluates windows at bb1 index `floor(t0·200) + d` — i.e. up to one 200 Hz
  sample (**5 ms**) earlier than the requested anchor. Write `φ = frac(t0·200)`.
- Stage C rebuilds its origin as `base_origin2 = (t0 + best_dt_samp/200)·fs2` — from the
  **un-floored** `t0`, in seconds.
- Stage C therefore starts `φ/200` seconds **late** and searches back by exactly that.

Prediction: `fine_dt_samp` slopes **−5.000 ms per unit cell position**. Measured:

```
fine   slope = -4.692 ± 0.226 ms per unit cell position   r=-0.515  p=2.7e-82   (1.4 SE)
coarse slope = -4.464 ± 3.897 ms per unit cell position   r=-0.033  p=0.252
combined     = -9.156 ± 3.928 ms                          r=-0.067  p=0.0199
```

A **constant ~−4.5 ms pedestal** remains on top of the φ-dependent term. I have a hypothesis
(`ref_phase += phase_step` increments *before* use, costing one sample **at each stage's own
rate** — 5 ms at 200 Hz vs 0.5 ms at 2000 Hz, a 4.5 ms disagreement) but **I have not tested
it.** 🛑 **It is DIRECTIONAL, my calibration there is 1.5/3.5, and it must not gate anything.**
R2 measures the residual after the origin fix and only then decides.

### 2.3 HK-026 self-check

This uses the refiner's own exports to characterise the refiner. It is **not** the forbidden
pattern: I am not deriving a bound on the instrument's blind spot from its own output. I
derived an **exact numeric prediction (−5.000 ms) from the source independently** and tested
the instrument against it. Valid.

---

## 3. R-6 — "Stage A+B is clean" is NOT established

The board records R1b's biggest claimed win as localisation to Stage C. **Withdraw that.**

`coarse` slope is **−4.464 ± 3.897 ms** — *same sign, same magnitude* as `fine`. Its SE is
17× larger only because Stage A+B's own search spread is 38 ms against Stage C's 2.6 ms.
`p=0.252` is **not a null — it is an instrument failure** (HK-021): D2's marginal symmetry
test cannot see a 4.5 ms effect against a 38 ms spread.

Compounding it: `reflection_symmetry_test` calls `ks_2samp(x, -x)` — two **maximally
dependent** samples into a test that assumes independence, both heavily tied (25 and 41
support points at n=1200). Both violations push the same way: **conservative**. The FAILs are
safe; **the `coarse_stage` PASS is a doubly-conservative non-result.**

✅ **Reporting `coarse_stage PASS (clean)` invites precisely the wrong inference. Both stages
are implicated. The defect is in the seam between them, which is why neither marginal owns it.**

---

## 4. R-7 — My own capture-range argument, RAISED AND REFUTED

Recorded because a discarded hypothesis is evidence too.

I argued the −4.5 ms bias eats half of Stage C's ±10 ms one-sided margin and would clip on
candidates near a coarse-cell edge — which would have made this a live D-001 defect. **I
measured it. It is false:**

```
SIGNAL fine_dt_samp at -20: 0/2400 (0.0%)    at +20: 0 (0.0%)
                  |fine|>=18: 0 (0.0%)      <=-15: 5 (0.2%)
```

Zero saturation. Worst case is ~2.5 ms of coarse rounding residual plus the ~4.5 ms bias ≈
7 ms against a 10 ms half-window — **~3 ms of margin left, never exhausted.**

**Consequence, stated plainly: the defect costs robustness margin, not accuracy and not
capture. It changes no decode outcome today.** That is the whole reason there is no R1c.

---

## 5. R-8 — D3's conclusion is a false negative; correct the record

`stratify_noise.py` computed the *right* variable (`cell_position = mod(t0/0.005, 1)`) and
drew the *wrong* conclusion, for two compounding reasons:

1. **It reports bare `r` with no p-value and no slope.** `cell_position_vs_dt = −0.067` was
   called "negligible". Its actual **p = 0.0199** — significant at 5%, and it is the largest
   of the three correlations it reports by 2×. The `r` is small only because the denominator
   is Stage A+B's own ±60 ms search variance. **The slope is −9.156 ms per unit cell
   position — nearly two whole coarse cells.**
2. **It was never re-run after D1 landed.** It ran on pre-D1 committed data — correctly, per
   the 2028Z ruling's own "do this first" instruction — but nothing re-pointed it at the
   per-stage exports that D1 shipped *precisely to make this visible*. Same statistic against
   `fine_dt_samp`: **r = −0.515, p = 2.7e-82.**

🔴 **This is MEMORY.md's own LEVEL-vs-CONTRAST warning firing.** A correlation coefficient
judged without its slope or its p, against a denominator dominated by an unrelated variance
component, will call a two-coarse-cell effect "negligible" every time.

**Standing instruction, all future gates:** report **slope + CI + p**, never a bare `r`.

---

## 6. R-9 — AC-4 has no ROW 0 (latent, did not bite)

`evaluate_ac4` drops underpowered strata with `continue`, reports them in
`underpowered_strata`, then returns `pass: trend["pass"]`. **A partially-underpowered run
returns PASS.** AC-3 gets this right; AC-4 does not. `underpowered_strata` was `[]` this run
so no harm was done, but it is a gate that can pass on a broken instrument. Fix it.

---

## 7. Ruling: no R1c. Do these three cheap things, then spec R2.

### 7.1 Immediate, QA-tooling + docs only — NO Developer session

| # | Item | Where |
|---|---|---|
| **A1** | Correct the stale mechanism comment in `sync_refiner.c` (~line 355). Comment-only, no logic, no rebuild needed — it rides R2's rebuild. State: inter-stage origin disagreement; present on signal at all SNRs; selection-bias explanation refuted. | `native/ft8_lib_vendor/refine/sync_refiner.c` |
| **A2** | Give AC-4 a ROW 0: any non-empty `underpowered_strata` ⇒ NOT PASS, same shape as AC-3's. | `evaluate_acs.py` |
| **A3** | Re-run D3's statistic against `coarse_dt_samp`/`fine_dt_samp`; emit **slope + SE + p**, not bare `r`. Record the corrected conclusion, superseding "rules out a position-dependent cause". | `stratify_noise.py` |

A1 is a comment in a native file. Per the Captain's R0 precedent (HK-011 exists to protect
`src/` **logic**), a comment correction does not need a Developer session. If QA judges
otherwise, it rides R2 instead — **do not spend a round on it.**

### 7.2 R2 — UNBLOCKED, QA authors the OpenSpec proposal next

The 2028Z ruling blocked R2 on "the Stage-C mechanism". **That block is lifted:** the
mechanism is known (§2), characterised (§2.2), and shown not to affect the combined output
(§4). R2 proceeds.

**Design inputs R2 MUST carry:**

1. 🔴 **NO sub-0.5 Hz frequency capability exists** (R-1, still binding). `REFINE_FREQ_STEP_HZ
   0.5f`, no fine-frequency stage in the code. 0.5 Hz is 6.25× finer than the 3.125 Hz
   lattice and **may** suffice — that is an **open design question, not an established
   property.** R2 must state which it is assuming and why.
2. ✅ **Time is strong and trustworthy:** RMS(Δt) 1.135 ms against an 80 ms lattice — 70×
   finer. This is the lever D-001 needs.
3. **Fold in the origin fix** as a pre-registered sub-item, not a separate round. Sketch:
   carry Stage A+B's *actual floored* window forward
   (`base_origin2 = (floorf(base_origin1) + best_dt_samp) · fs2/fs1`) **and** subtract the
   flooring residue from the reported Δt so AC-2 is not broken by moving the bias into the
   answer. **My prediction, for scoring (mechanical, calibration 2/3): `fine_dt_samp`
   re-centres near 0 and RMS(Δt) improves below 1.135 ms.**
4. **Then, and only then, measure the residual pedestal** (§2.2) and decide whether the phase
   convention needs touching. Do not pre-judge it.
5. 🔴 **Cost is a real constraint:** 21.5 ms/candidate, 1.5–5.1 h full corpus. R2 **cannot
   refine every candidate** and must budget this explicitly.
6. 🛑 **HK-021/HK-025 apply to every R2 gate.** Explicit ROW 0; both branches evaluated;
   slope + CI + p, never bare `r`; cluster your SEs (frequency is integer Hz ⇒ `r` is a
   station-level constant).

---

## 8. What this means for D-001

Honest framing, because it is the only thing that matters:

- D-001's cause is architectural: **no sync refinement; phase discarded at the `uint8_t`
  waterfall**; misses arrive at **44% median BER ⇒ reading in the WRONG PLACE.**
- R0/R1/R1b have built and validated an instrument that **locates a signal to ~1.1 ms and
  0.5 Hz**. That instrument now has **no production call site.**
- 🔴 **Nothing in R1b's findings blocks using it. R2 — wiring it into the decode path — is
  the whole remaining job, and it is now the only thing standing between here and D-001.**

Everything in §7.1 is cleanup that must not be allowed to become a round of its own.

---

## 9. Prediction register (HK-021, score the consequence)

| Prediction | Type | Calibration | Status |
|---|---|---|---|
| φ-dependent term slopes −5.000 ms/unit cell | mechanical | 2/3 | ✅ measured −4.692 ± 0.226 (1.4 SE) |
| Bias eats Stage C capture range ⇒ clipping | directional | 1.5/3.5 | ❌ **REFUTED**, §4 |
| Pedestal is the `ref_phase` before-use convention | directional | 1.5/3.5 | ⏳ untested, must not gate |
| Origin fix re-centres `fine` near 0, RMS(Δt) improves | mechanical | 2/3 | ⏳ R2 scores it |
