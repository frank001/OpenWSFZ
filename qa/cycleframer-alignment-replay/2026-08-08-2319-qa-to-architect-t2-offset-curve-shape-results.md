# QA → Architect: T2 results — offset-curve shape is ROW 3, pooled `U` clears the bar but the halves disagree

**Author:** QA, 2026-08-08 (23:19 UTC, `date -u`, per HK-017). Repo `main` at `162bd44`.
**Scope:** executes the spec at
`qa/cycleframer-alignment-replay/2026-08-08-2102-architect-to-qa-spec-t2-offset-curve-shape.md`
in full — same population as T1, native 13-rung resolution, pre-registered gate, verbatim.
**Status:** pure re-analysis of `ALL.TXT` already on disk and inventory-verified
(`qa/artefact_inventory.py --check` clean before starting). No `src/` change, no capture, no rebuild,
no Developer session. Harness `qa/cycleframer-alignment-replay/t2_offset_curve_shape.py`, currently
untracked; committing is the Captain's call (HK-010). NFR-021: no message text or callsign appears
anywhere below — every figure is a count, a rate, or a frequency statistic.

**Per spec §1.1: this does not recompute or restate T1's `G` and does not re-read T1's gate. T1 stays
ROW 3, final.** Per §1.2: `D_int` below is a different, newly-pre-registered metric and is never
substituted into T1's gate.

---

## 1. Bottom line

**ROW 3 — inconclusive at this corpus size, specifically because `U ≥ 1.5 pp` on the pooled population
but the two cycle-parity halves disagree in sign.** Pooled `U = 1.85 pp` clears the 1.5 pp bar on its
own — the magnitude the two-candidate mechanism (spec §0.2) predicted is there — but the replication
requirement fails: `half0` reads `U = −0.01 pp` (no midpoint recovery at all) while `half1` reads
`U = 3.38 pp` (nearly double the pooled figure). That is a 3.4 pp swing between two halves whose own
noise floor is ≈0.87 pp (spec §4 power note) — a genuine disagreement, not a rounding margin. Per the
gate's own ROW 3 row: **report the curve, make no mechanism claim in either direction, do not spend
further effort on the midpoint question without a materially larger corpus, and do not propose a
capture run to get one.**

`D_int = 4.03 pp` (reported, not gated, per §1.2) — inside the Architect's predicted 4–6 pp range, at
its bottom edge, and stable across both halves (3.95 / 4.13 pp, same sign, well within noise of each
other). **The interior region is genuinely the worst case; that part of the mechanism is well
supported.** What is not supported at this corpus size is the sharper claim that recovery ticks back
up specifically at the midpoint rungs — `U` is real on the pooled figure but does not replicate.

Your recorded prediction (§6 item 7) was **ROW 1, `U ≥ 1.5 pp`.** The point estimate landed exactly
where you predicted (1.85 pp, inside the two-candidate magnitude the mechanism implies) but the
categorical call misses on the replication requirement, not the magnitude — worth recording precisely
that way, since it is a different kind of miss than T1's (T1's point estimate sat under its own bar;
here the point estimate clears the bar and the *split-half* check is what fails).

## 2. Method, exactly as specced

- **Population identical to T1**, reused by importing `load()`, `residual()`,
  `has_unresolved_hash()`, `quintile_edges()`, `assign_quintile()` from
  `t1_frequency_quantisation.py` (not copied) and rebuilding it verbatim: 20m leg, window
  `260808_004000`..`260808_111500`, reference = intersection of WSJT-X FT991A and FT991A-Copy on
  `(ts, message)`, `r` and SNR always from FT991A for both matched and missed groups, exclusions
  (unresolved `<...>`, out-of-band 200–3000 Hz) applied symmetrically before any statistic.
- **Population check (spec §2): kept 67 243 — exact match to the expected figure and to T1's own
  population.** Reference population 69 222; excluded 1 113 unresolved-hash, 866 out-of-band.
  Matched by OpenWSFZ 8080: 37 779/67 243 = 56.2%.
- **13-rung resolution, no quantiles**: `r` snapped to its canonical 1/8 Hz rung
  (`round(round(r/0.125)*0.125, 3)`) as a float-noise guard; all 13 rungs came back non-empty with
  no snapping actually needed (the raw `residual()` values landed exactly on-rung to begin with).
- **Fixed rung groups, declared before any per-rung data was seen (§3.2)**: `CEN = {0, 0.125, 0.25}`,
  `INT = {0.875, 1.0, 1.125}`, `MID = {1.375, 1.5}` — identical across every stratum, the fix for
  T1's per-stratum quintile re-derivation (§0.3).
- **Split-half by cycle parity (§3.4)**: `half = (secs // 15) % 2` from each decode's own timestamp,
  not a time-based split — balanced in time, density and SNR by construction, though it also partly
  separates FT8's alternating-slot station populations, so it is a stronger replication than a pure
  noise split but not a pure one either (as flagged in the spec).

## 3. Instrument checks (the gate's ROW 0 conditions) — all pass

| check | bar | value | verdict |
|---|---|---:|---|
| smallest fixed group (`MID`) | ≥ 2 000 | 7 936 | pass |
| distinct rungs with `n > 0` | == 13 | 13 | pass — the integer-Hz ladder premise holds |
| `mean_r_ours` (OpenWSFZ, matched subset, this population) | 0.20–0.30 | **0.2404** | pass — matches T1's own 0.2404 on this same population exactly |
| `D_int` plausibility bound | −2.0 – 15.0 | 4.03 | well inside |
| split-half `D_int` sign agreement | same sign both halves | **3.95 / 4.13, both positive** | pass |

All five ROW 0 checks cleared on the first run; no instrument failure.

## 4. Primary result — the 13-rung curve

| `r` (Hz) | n | matched | recovery | group |
|---:|---:|---:|---:|---|
| 0.000 | 2 994 | 1 797 | 60.0% | CEN |
| 0.125 | 6 323 | 3 676 | 58.1% | CEN |
| 0.250 | 5 887 | 3 334 | 56.6% | CEN |
| 0.375 | 5 509 | 3 085 | 56.0% | — |
| 0.500 | 5 689 | 3 314 | 58.3% | — |
| 0.625 | 5 307 | 2 884 | 54.3% | — |
| 0.750 | 5 393 | 3 164 | 58.7% | — |
| 0.875 | 5 205 | 2 662 | **51.1%** | INT |
| 1.000 | 5 729 | 3 188 | 55.6% | INT |
| 1.125 | 5 921 | 3 234 | 54.6% | INT |
| 1.250 | 5 350 | 3 017 | 56.4% | — |
| 1.375 | 4 253 | 2 265 | 53.3% | MID |
| 1.500 | 3 683 | 2 159 | 58.6% | MID |

This is the resolution T1's quintiles discarded (2/3/2/2/4-rung groupings of unequal width). At
native resolution the curve is visibly non-monotone in more than one place — it is not a clean
staircase from bin-centre to bin-edge, and the single lowest point (51.1%) sits at `r = 0.875`, the
first INT rung, not at the theoretical bin-edge (`r = 1.5625`, between the last two rungs).

### 4.1 Fixed-group contrasts

| group | rungs | n | matched | recovery |
|---|---|---:|---:|---:|
| CEN | 0, 0.125, 0.25 | 15 204 | 8 807 | 57.9% |
| INT | 0.875, 1.0, 1.125 | 16 855 | 9 084 | 53.9% |
| MID | 1.375, 1.5 | 7 936 | 4 424 | 55.7% |

```
D_int = recovery(CEN) - recovery(INT) = 57.9 - 53.9 = 4.03 pp
U     = recovery(MID) - recovery(INT) = 55.7 - 53.9 = 1.85 pp
```

## 5. Split-half replication, by cycle parity

| half | n | `D_int` | `U` | CEN | INT | MID |
|---|---:|---:|---:|---|---|---|
| 0 (even) | 34 679 | 3.95 pp | **−0.01 pp** | 57.8% (n=8 067) | 53.9% (n=8 528) | 53.9% (n=3 580) |
| 1 (odd) | 32 564 | 4.13 pp | **3.38 pp** | 58.0% (n=7 137) | 53.9% (n=8 327) | 57.3% (n=4 356) |

`D_int` replicates cleanly — both halves land within 0.18 pp of each other and of the pooled figure.
`U` does not — half0's `INT` and `MID` recovery are statistically indistinguishable (53.9% vs 53.9%)
while half1's `MID` sits 3.4 pp above its own `INT`. **This is exactly what ROW 0e is built to catch
for `D_int`, and the substantive gate's own both-halves-positive requirement catches the equivalent
failure for `U`.** The interior-worst-case claim survives; the midpoint-recovery claim does not.

## 6. Reading against the gate

```
n_min_group        = 7936    >= 2000                       -> not ROW 0a
n_distinct_rungs    = 13     == 13                          -> not ROW 0b
mean_r_ours         = 0.2404 in [0.20, 0.30]                -> not ROW 0c
d_int               = 4.03   in [-2.0, 15.0]                -> not ROW 0d
d_int half0/half1   = 3.95 / 4.13  (same sign)               -> not ROW 0e
u = 1.85 >= 1.5, but u_half0 = -0.01 (not > 0)               -> not ROW 1
u = 1.85, not <= 0.5                                          -> not ROW 2
                                                               -> ROW 3
```

**ROW 3 consequence, per the spec's own table: "Inconclusive at this corpus size... Report the curve.
Make no mechanism claim in either direction. Do not spend further effort on the midpoint question
without a materially larger corpus — and do not propose a capture run to get one."** That is what
this document does. Per §1.2, this row is **not** read back into T1's gate under any framing.

## 7. Reported but not gated

### 7.1 §5.1 — where the observed minimum actually falls

`argmin` over the 13 rungs (restricted to `n ≥ 2 000`, all 13 qualify) is **`r = 0.875`, recovery
51.1%, inside `INT`.** Matches prediction 6. Diagnostic only, per the spec's own caution that the
minimum of 13 noisy estimates is biased downward by roughly 1σ ≈ 1 pp — it is reported as a mechanism
check against §0.2's prediction, not as independent evidence for `U`.

### 7.2 §5.2 — SNR strata on globally fixed rung groups (the §0.3 fix, and whether it worked)

| SNR quintile | n | `mean_r` | `D_int` | `U` |
|---|---:|---:|---:|---:|
| 1 (weakest) | 11 532 | 0.7342 | 4.01 pp | −0.83 pp |
| 2 | 14 173 | 0.7246 | 4.73 pp | 1.47 pp |
| 3 | 14 424 | 0.7315 | 6.45 pp | 1.16 pp |
| 4 | 12 920 | 0.7472 | 2.21 pp | 2.43 pp |
| 5 (strongest) | 14 194 | 0.7465 | 3.31 pp | 1.95 pp |

**The reconciliation the §0.3 fix was for: the n-weighted mean of the five `D_int` values is
4.19 pp against the pooled `D_int` of 4.03 pp — a 0.16 pp gap**, against T1's 0.81 pp gap (3.97 vs
3.16) under per-stratum quintile re-derivation. **The fixed-rung-group method resolves the arithmetic
tell that flagged T1's defect** — the strata are now genuinely comparable to the pooled figure and to
each other. The equivalent check on `U` (weighted mean 1.30 pp vs pooled 1.85 pp, a 0.55 pp gap) is
looser, consistent with `U` being the noisier of the two contrasts (`MID` is the smallest fixed group
at every stratification level).

**`mean_r` spread across the five SNR quintiles = 0.0226 Hz** (max 0.7472 at Q4, min 0.7246 at Q2).
Per spec §5.2 this is **on the wrong side of the pre-registered 0.02 Hz bar**, by 0.0026 Hz — a
narrow, but real, miss of the prediction. Reading it honestly rather than rounding it away: this
crosses into "`r` and SNR are genuinely correlated in this population," which the spec says needs its
own write-up before either figure is quoted on that basis. **Recording it, not resolving it**: the
correlation, if real, is tiny relative to the 1.5625 Hz range of `r` itself (1.4% of the range) and
the five quintile means are not monotone in SNR (0.7342 → 0.7246 → 0.7315 → 0.7472 → 0.7465, not a
trend), which is not the shape a genuine physical SNR–offset relationship would obviously produce.
The more parsimonious reading is that this is residual per-quintile sampling noise landing just over
a bar set to two significant figures — but per §5.2's own instruction this is flagged rather than
silently classified as an artefact, and neither reading is asserted as settled here.

### 7.3 §5.3 — corpus-wide confirmation that no finer frequency instrument exists

Scanned all 16 WSJT-X-authored `ALL.TXT` files under `artefacts/` (excludes `ours_on_*` paths, which
are OpenWSFZ's own output decoding WSJT-X-sourced audio, not a WSJT-X-authored log) —
1 295 204 `Rx FT8` lines corpus-wide. **Zero contain a decimal point in the frequency field.** The
integer-Hz limit is a property of the corpus, not of one file or one leg; §0.4's premise (no finer
instrument exists to de-attenuate `G` or `D_int` against) is confirmed mechanically, no modelling
involved.

## 8. Architect's predictions, scored against the outcome (spec §6)

| # | prediction | result | verdict |
|---|---|---|---|
| 1 | exactly 13 distinct `r` values | 13 | **hit** |
| 2 | `mean_r_ours` in 0.24–0.25 | 0.2404 | **hit** |
| 3 | kept population = 67 243 | 67 243 | **hit** |
| 4 | `mean_r` SNR-quintile spread < 0.02 Hz | 0.0226 Hz | **miss** — narrow, see §7.2 |
| 5 | `D_int` = 4–6 pp | 4.03 pp | **hit**, bottom edge |
| 6 | §5.1 argmin falls inside INT | `r = 0.875` | **hit** |
| 7 | `U ≥ 1.5 pp`, i.e. ROW 1 | pooled 1.85 pp, but ROW 3 on replication | **miss on the categorical call, hit on the pooled magnitude** |

**5 of 7 straightforward hits.** The two misses are both instructive rather than simply wrong:
prediction 4 missed by a margin (0.0026 Hz) smaller than the precision the bar itself was stated to
(two significant figures), and prediction 7's point estimate landed inside the predicted range while
the categorical row call failed specifically on the replication requirement the gate added on top of
the magnitude bar. Recording plainly, as asked: on T1 the prediction was ROW 1 and the result was
ROW 3 with the point estimate under the bar; here the prediction is ROW 1 again and the result is
again ROW 3, but this time with the point estimate over the bar and the half-sample check failing
instead. Two ROW-1 predictions, two ROW-3 outcomes, for two different reasons.

## 9. What this does and doesn't change

- **Does not reopen T1.** T1 stays ROW 3, `G = 3.16 pp`, final (§1.1). Nothing here recomputes or
  restates it.
- **`D_int` is not `G` and is not substituted into T1's gate** (§1.2) — it answers a different,
  newly-registered question (is the interior the worst case?) and the answer to that question is
  yes, replicated cleanly across both halves.
- **The interior-worst-case mechanism (spec §0.2) is supported; the two-candidate midpoint-recovery
  half of the same mechanism is not confirmed at this corpus size.** `U` is real on the pooled figure
  (1.85 pp, matching the predicted magnitude) but fails its own replication check. This is
  meaningfully different from T1's Q4→Q5 "tick-up" being outright killed (ROW 2 territory) — it
  remains a live but unresolved possibility, not a closed one.
- **T1's §4.1 SNR-stratum arithmetic gap is now understood and the fixed-rung-group recomputation in
  §7.2 above is the correction §0.3 called for** — the reconciliation gap shrinks from 0.81 pp (T1,
  per-stratum quintile edges) to 0.16 pp (`D_int`, fixed rungs). T1 §4.1's "4.4–6.9 pp across three
  weak/moderate-SNR quintiles" wording should be treated as not directly comparable to any figure
  above; this document's §7.2 table is the like-for-like version, on `D_int`/`U`, not on `G`.
- **Per §8 of the spec: no restatement of `G`, no claim that this changes T1's row, `D_int` is never
  described as "what `G` should have been," and no de-attenuated `G` appears anywhere above — none of
  those prohibitions were tested by anything found here, so none required judgment calls.**

## 10. Artefacts

- Harness: `qa/cycleframer-alignment-replay/t2_offset_curve_shape.py` (untracked), imports
  `t1_frequency_quantisation.py` for population construction so the two are provably comparable.
- Inputs: `artefacts/20260808_live_run_0016-808{0,1}/{owsfz,wsjt-x}/ALL.TXT` (20m only, per §1.3 —
  17m is out of scope entirely and was not read by this harness). §5.3 additionally scanned all
  WSJT-X `ALL.TXT` files under `artefacts/` corpus-wide, read-only, counts only.
- No files written outside `qa/`; no message text or callsign logged anywhere in script output.

## 11. Citation limits

**May be cited once this document lands:** the 13-rung curve (§4); `D_int = 4.03 pp` as "the
worst-case offset penalty measured on fixed rung groups," replicated across both cycle-parity halves;
the ROW 3 read on `U` with its specific cause (pooled magnitude clears the bar, half-sample sign
disagreement fails replication); the §7.2 corrected SNR-stratified `D_int`/`U` table; the §7.3 corpus
fact (zero decimal-Hz frequency lines in 1 295 204 WSJT-X `Rx FT8` lines, corpus-wide).

🛑 **May not be cited, under any row:** any restatement of `G`; any claim that this result changes T1's
row (T1 stays ROW 3); `D_int` described as "what `G` should have been"; the §7.1 `argmin` used alone
as evidence for the mechanism; any de-attenuated or error-corrected `G` or `D_int`; and — new to this
document — **`U`'s pooled 1.85 pp figure cited on its own without the split-half disagreement**, since
the gate's own ROW 3 read exists specifically because the two do not agree.
