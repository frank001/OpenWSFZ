# Architect → QA: spec T2 — the shape of the offset-vs-recovery curve

**Author:** Architect, 2026-08-08 (21:02 UTC, from `date -u`, per HK-017). Repo `main` at `d0e9f63`.
**Follows:** `2026-08-08-2030-architect-to-qa-spec-t1-frequency-quantisation.md` (spec) and
`2026-08-08-2046-qa-to-architect-t1-frequency-quantisation-results.md` (results, ROW 3, `G = 3.16 pp`).
**Status:** pure re-analysis of `ALL.TXT` already on disk and inventory-verified. No `src/` change, no
capture, no rebuild, no Developer session. NFR-021: no message text and no callsign may appear in any
output, report, or committed harness — every figure is a count, a rate, or a frequency statistic.

---

## 0. Why this exists

T1 is closed at ROW 3 and **this document does not reopen it.** T1 asked *"does frequency
quantisation cost decodes?"* and answered yes, small. T2 asks a different question that T1's own
result raised and could not answer: **what SHAPE does that cost have, and where is the worst case?**

Three things came out of reading T1's results and its harness that make this worth one QA pass.

### 0.1 The residual lives on a 13-rung ladder, and that is the whole instrument

`STEP = 3.125 Hz = 25/8`. WSJT-X reports frequency as an **integer** Hz (verified directly against
`artefacts/20260808_live_run_0016-8080/wsjt-x/ALL.TXT`). For integer `f`, write `f mod 25 = m`; then
`f mod 3.125 = (8m mod 25)/8`, and since `gcd(8,25) = 1` that takes every value `j/8` for
`j = 0..24`. Folding to the residual gives

```
r ∈ {0, 0.125, 0.250, 0.375, 0.500, 0.625, 0.750, 0.875, 1.000, 1.125, 1.250, 1.375, 1.500}
```

— **exactly 13 distinct values, and nothing else is representable.** Under a uniform null, `r = 0`
carries weight 1/25 and every other rung 2/25, giving a mean of exactly **0.780**. The T1 spec's §0.3
control measured the uniform null at **0.781**. The ladder model is confirmed against an independent
number to three digits.

**This is why T1's quintiles came out at n = 9 317 / 17 085 / 10 700 / 10 934 / 19 207 rather than
five equal fifths.** `quintile_edges()` does nearest-rank cuts and `assign_quintile()` uses a strict
`<`, so every tied rung lands whole in one bucket. The five "quintiles" are in fact groupings of
2 / 3 / 2 / 2 / 4 ladder rungs, of unequal width in `r`-space.

**The rule I should have applied when drafting T1 was HK-021(d) — let the physical system supply the
parameter.** I reached for (b) "stratify by quantiles," but (b) governs continuous variables of
unknown scale. Here the lattice hands us 13 natural bins with ~5 400 decodes each. Quintiles
discarded that resolution and created the ambiguity in §0.2. **This drafting error is mine, not QA's.**

### 0.2 The Q4→Q5 tick-up, and a mechanism that predicts it

T1's curve is not monotone: Q4 is the low point at 53.5% and Q5 recovers to 55.6%. There is a
physical reason this might be real rather than noise.

At residual `r`, the nearest candidate-grid point is `r` away and the next is `3.125 − r` away. As
`r → 1.5625` (the exact midpoint) the signal becomes **equidistant between two lattice points**, so
`ftx_find_candidates()` can plausibly return both and the decoder gets two attempts at equal — bad —
offset. At `r ≈ 1.0` the signal is firmly assigned to one bin, badly offset, and the neighbour is
2.1 Hz away and useless.

**The mechanism therefore predicts the worst case is INTERIOR, not at the bin edge** — around
`r ≈ 0.875–1.25`, where the nearest-candidate penalty is near maximum but the second-chance benefit
has not yet arrived.

⚠️ **Disclosure, and it matters — this prediction is not blind.** It coincides with T1's observed Q4
minimum, which I have already seen. The mechanism argument stands on its own physics, but QA must
record that the group boundaries in §3.2 were chosen by someone who had seen the T1 curve. Treat the
*direction* as known and only the *magnitude* and *sign-stability* as being tested. (Same disclosure
discipline as the board's 17m-vs-20m entry of 08-08.)

### 0.3 A method defect in T1 §4.1 that needs correcting, not re-measuring

`t1_frequency_quantisation.py:214` calls `recovery_by_quintile()` **inside each SNR stratum**, which
**re-derives the `r`-quintile edges from that stratum's own population.** So "Q1" and "Q5" denote a
different set of ladder rungs in every SNR band, and the five `G_sub` values are not comparable to
each other or to the pooled `G`.

That accounts for the arithmetic gap I found: the SNR-weighted mean of the five `G_sub` values is
**3.97 pp** against a pooled `G` of **3.16 pp**, which under common edges and independence should
agree. **No new measurement is needed to explain it — the code explains it.** What is needed is a
recomputation on globally fixed rung groups so the SNR strata become comparable. §5.2 covers it.

### 0.4 One framing consequence that is reasoning, not measurement — label it as such

`r` is measured with ±0.5 Hz of reporting quantisation over a total range of 1.5625 Hz: roughly
**three resolution elements per lattice cell**. Non-differential measurement error in a stratifying
variable biases a contrast **toward zero**. It follows that `G = 3.16 pp` is a **floor**, not a point
estimate.

🛑 **QA must NOT attempt to de-attenuate this, model the error, or produce a corrected `G`.** Any such
attempt requires inventing an error model, and inventing a parameter means measuring that parameter —
HK-021(d), the exact failure this project has already paid for. The floor reading is an inference the
Architect carries in framing, explicitly labelled as reasoning. The only thing QA measures here is
the mechanical fact in §5.3 that no finer instrument exists in the corpus.

---

## 1. Scope, and four hard prohibitions

**In scope:** the 20m leg only, same window, same population, same exclusions as T1, re-analysed at
ladder-rung resolution.

🛑 **1.1 Do not recompute or restate `G`, and do not re-read T1's gate.** T1 is ROW 3. Final.

🛑 **1.2 `D_int` (§3.3) is NOT `G` and may never be substituted into T1's gate.** It is a different
metric, answering a different question, pre-registered for the first time in this document. Any
sentence of the form "using the interior minimum instead, T1 would have been ROW 1" is forbidden —
that is re-reading a pre-registered gate against a metric chosen after seeing the curve, which is
precisely the sin HK-021 exists to prevent.

🛑 **1.3 The 17m leg is out of scope entirely.** It is VOID under its own ROW 0b and contributed only
confusion to T1 §5. The split-half in §3.4 provides replication *inside* the citable leg, which is
strictly better than a void one. Do not run it, do not report it, do not use it to adjudicate `U`.

🛑 **1.4 Do not extend anything here to the time axis.** Reference DT resolution is 0.1 s, coarser
than our own 0.08 s grid step; the time residual is not identifiable from `ALL.TXT` and an attempt is
an HK-021(c) failure by construction. Unchanged from T1 §3.5.

---

## 2. Population — identical to T1, verbatim

Reuse `load()`, `residual()`, and the exclusion logic from `t1_frequency_quantisation.py` unchanged,
so that T2's population is provably the same one T1 read.

- **Leg:** 20m, `artefacts/20260808_live_run_0016-808{0,1}/`.
- **Window:** `260808_004000` .. `260808_111500`.
- **Reference:** intersection of WSJT-X FT991A and FT991A-Copy on `(ts, message)`.
- **Matched:** reference decode for which OpenWSFZ 8080 produced the identical `(ts, message)`.
- **`r` and SNR always from the reference (WSJT-X FT991A), for BOTH matched and missed groups,
  without exception.** OpenWSFZ's own frequency is on-grid by construction and enters only the
  `mean_r_ours` instrument check. This is T1's trap and it is unchanged.
- **Exclusions, applied before any statistic, both groups symmetrically:** unresolved `<...>` token;
  frequency outside 200–3000 Hz.
- **Expected kept population: 67 243.** If it differs, stop and report — the populations have
  diverged and nothing below is comparable to T1.

Run `python qa/artefact_inventory.py --check` clean before starting.

---

## 3. Metrics — all mechanical

### 3.1 The primary deliverable: the full 13-rung curve

For each of the 13 ladder rungs, report `n`, `matched`, and `recovery %`. No binning, no quantiles.
This is the natural resolution of the instrument and it is what T1 threw away.

### 3.2 Fixed rung groups (declared here, before the per-rung data is seen)

```
CEN = { 0.000, 0.125, 0.250 }            bin centre        expect n ≈ 13 400
INT = { 0.875, 1.000, 1.125 }            interior          expect n ≈ 16 100
MID = { 1.375, 1.500 }                   near midpoint     expect n ≈ 10 800
```

Rungs `{0.375, 0.500, 0.625, 0.750, 1.250}` belong to no group; they appear in the §3.1 curve only.
Group boundaries are fixed by the mechanism in §0.2 and are **identical across every stratum** —
this is the fix for §0.3.

### 3.3 The two contrasts

```
D_int = recovery(CEN) − recovery(INT)     the true worst-case offset penalty
U     = recovery(MID) − recovery(INT)     the size of the midpoint recovery ("two-candidate" effect)
```

`D_int` is **reported, not gated** (see §1.2 and the plausibility bound in §4). `U` is the gated
metric — it is what distinguishes a real non-monotone curve from a T1 binning artefact.

### 3.4 Split-half replication — by cycle parity, not by time

For each decode, from its timestamp `ts` (format `YYMMDD_HHMMSS`):

```
secs   = int(ts[7:9])*3600 + int(ts[9:11])*60 + int(ts[11:13])
half   = (secs // 15) % 2          # 0 = "even" cycles, 1 = "odd" cycles
```

Compute `D_int` and `U` independently within each half.

**Parity, not a time split, deliberately.** A first-half/second-half split would confound shape
against the density drift the board has already measured across this leg. Cycle parity is balanced in
time, density and SNR. ⚠️ Note in the report that FT8 stations transmit on alternating slots, so
parity also partly separates the station populations — that makes this a *stronger* replication than
a pure noise split, not a weaker one, but it is not a pure noise test and should not be described as
one.

---

## 4. Pre-registered gate (HK-021)

Drafted as the code that evaluates it. Rows are mutually exclusive and evaluated in **strict order**;
boundary values are assigned explicitly. **ROW 0 is explicit and is evaluated first.**

```python
def t2_row(n_min_group, n_distinct_rungs, mean_r_ours,
           d_int, d_int_half_0, d_int_half_1,
           u, u_half_0, u_half_1):

    # ---- ROW 0: instrument failure, NOT a null. Evaluated first, in this order. ----
    if n_min_group < 2000:
        return "ROW 0a"      # a rung group is too small to read
    if n_distinct_rungs != 13:
        return "ROW 0b"      # the integer-Hz ladder premise (S0.1) is false
    if not (0.20 <= mean_r_ours <= 0.30):
        return "ROW 0c"      # our on-grid model is wrong
    if not (-2.0 <= d_int <= 15.0):
        return "ROW 0d"      # outside a bound already believed; instrument failure
    if (d_int_half_0 > 0) != (d_int_half_1 > 0):
        return "ROW 0e"      # shape unstable across split-half: too noisy to read shape at all

    # ---- substantive rows, mutually exclusive, strict order ----
    if u >= 1.5 and u_half_0 > 0 and u_half_1 > 0:
        return "ROW 1"
    if u <= 0.5:
        return "ROW 2"
    return "ROW 3"
```

**Consequences, as assertions.**

| row | condition | consequence — this is what the row COMMITS us to |
|---|---|---|
| **ROW 0a–0e** | as above | **Instrument failure, not a null.** Report the failing check and its value. Draw no conclusion about curve shape in either direction. Do not repair-and-rerun in the same session without a fresh pre-registration. |
| **ROW 1** | `U ≥ 1.5 pp` and both halves positive | **The curve is non-monotone and the two-candidate mechanism in §0.2 is supported.** The worst case is interior, not at the bin edge. Assert into the board: T1's `Q1 − Q5` was the wrong contrast, and the worst-case offset penalty is `D_int`, larger than `G`. Any future sizing of frequency-refinement work uses `D_int` and the §5.2 SNR table, not `G`. **Still no Developer session on this alone** — T1's ROW 3 governs that, and this row does not overturn it. |
| **ROW 2** | `U ≤ 0.5 pp` | **The T1 Q5 tick-up was a binning artefact.** The curve is monotone at rung resolution. The two-candidate hypothesis is **dead — close it, do not revisit.** `Q1 − Q5` was an acceptable contrast after all and T1's `G` needs no shape caveat. |
| **ROW 3** | `0.5 < U < 1.5`, or `U ≥ 1.5` with a half-sample sign disagreement | **Inconclusive at this corpus size.** Report the curve. Make no mechanism claim in either direction. Do not spend further effort on the midpoint question without a materially larger corpus — and do not propose a capture run to get one. |

**Power note, so the bars are not mistaken for arbitrary.** At `R ≈ 56%` the binomial SE is ≈ 0.39–0.48 pp
per group, so `SE(U) ≈ 0.62 pp` pooled and ≈ 0.87 pp per half. Allowing a conservative ×1.5 for
clustering (repeat decodes of the same station), `SE(U) ≈ 0.93 pp`. The 1.5 pp bar plus a
both-halves-positive requirement puts the false-positive rate around 4–5%. The consequence of ROW 1
is framing and future sizing, not code — that risk level is proportionate to that consequence.

---

## 5. Reported but NOT gated

### 5.1 Where does the observed minimum actually fall?

Report `argmin` over the 13 rungs, restricted to rungs with `n ≥ 2000`. **Diagnostic only.** It is
not gated because the minimum of 13 noisy estimates is biased downward by roughly 1σ ≈ 1 pp, which
would manufacture a positive `U` if it were fed into the metric. Report it as a mechanism check
against §0.2's prediction, nothing more.

### 5.2 SNR strata, on globally fixed rung groups — the §0.3 fix

Recompute `D_int` and `U` within each reference-SNR quintile using **the §3.2 group definitions,
unchanged in every stratum.** SNR always from the reference, per `DEFECT-snr-reported-gain-error.md`.

Also report **`mean_r` within each SNR quintile.** Mechanical read:

- **`max − min` of `mean_r` across the five SNR quintiles `< 0.02` Hz** ⇒ `r` and SNR are
  independent, and T1's 3.16-vs-3.97 gap is **confirmed** as an artefact of per-stratum edge
  re-derivation. T1 §4.1's cross-band comparison must then be re-stated on fixed rungs, and its
  "4.4–6.9 pp across three bands" wording corrected as not like-for-like.
- **`≥ 0.02` Hz** ⇒ `r` and SNR are genuinely correlated in this population. That is a population
  fact, not a method artefact, and it needs its own short write-up before either figure is quoted.

### 5.3 Confirm no finer frequency instrument exists in the corpus

Mechanically scan every gathered WSJT-X `ALL.TXT` in `artefacts/` for a frequency field containing a
decimal point. Report the count. If it is zero corpus-wide, the integer-Hz limit is confirmed as a
property of the corpus and not of one file — which closes §0.4's premise without any modelling.

---

## 6. Architect's recorded predictions (HK-021 — a bound that runs against my own prediction)

Recorded before QA runs anything. Landing outside these is my error, and where a prediction is itself
a ROW 0 bar, my being wrong voids the run rather than producing a finding.

| # | prediction | tested by |
|---|---|---|
| 1 | exactly **13** distinct `r` values | ROW 0b |
| 2 | `mean_r_ours` in **0.24–0.25** (theory: on-grid + integer rounding = **0.250** exactly) | ROW 0c |
| 3 | kept population = **67 243** | §2 |
| 4 | `mean_r` spread across SNR quintiles **< 0.02 Hz** ⇒ the 3.16/3.97 gap is a method artefact | §5.2 |
| 5 | `D_int` = **4–6 pp** | ROW 0d ceiling |
| 6 | the §5.1 `argmin` rung falls inside **INT** `{0.875, 1.000, 1.125}` | §5.1 |
| 7 | **`U ≥ 1.5 pp`, i.e. I predict ROW 1** | the gate |

On T1 I predicted ROW 1 and the result was ROW 3 — the point estimate landed on the edge of my range
and the categorical call missed. **Record prediction 7 against the outcome the same way, plainly,
whichever way it goes.**

---

## 7. Deliverables

1. Harness `qa/cycleframer-alignment-replay/t2_offset_curve_shape.py`, importing from
   `t1_frequency_quantisation.py` where possible so the population is provably identical.
2. Report `qa/cycleframer-alignment-replay/<UTC>-qa-to-architect-t2-offset-curve-shape-results.md`,
   filename and byline both from real `date -u` and in agreement (HK-017), carrying:
   the §3.1 13-rung table; `D_int`, `U`, and both split-halves; the gate read printed as a strict
   ordered trace like T1 §6; the §5.1/§5.2/§5.3 diagnostics; prediction 7 scored against the outcome;
   and its own **citation-limits section**.
3. **No push, no merge, no `src/` change.** Committing is the Captain's call (HK-010/HK-014).
4. Update `BOARD.md` in the **same edit** as the result, per HK-024.

## 8. Citation limits set by this spec in advance

**May be cited once the run completes:** the 13-rung curve; `D_int` as *"the worst-case offset
penalty measured on fixed rung groups"*; `U` and its row; the §5.2 corrected SNR table; the §5.3
corpus fact.

🛑 **May not be cited, under any row:** any restatement of `G`; any claim that T2 changes T1's row;
`D_int` described as *"what `G` should have been"*; the §5.1 `argmin` as evidence for the mechanism
on its own; and any de-attenuated or error-corrected `G` (see §0.4 — it must not exist).
