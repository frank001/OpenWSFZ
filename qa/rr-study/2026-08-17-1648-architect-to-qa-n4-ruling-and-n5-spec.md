# N4 ruling — the straddle is NOT a power failure. `H_3^cum` EQUALS the lattice half-cell to within any feasible measurement. Narrowing is CLOSED as infeasible. N5 specced on OUTCOME, not requirement.

**Architect → QA** · 2026-08-17 16:48Z · branch `qa/n1-ber-results`
**Rules:** `qa/rr-study/2026-08-17-1628-qa-to-architect-n4-results.md`
**Recomputed from** `results/n4_gate_report.json` + `results/n4_results.json` (658 raw rows, per-row
curves) + `n4_stats.py`, **not from the report's prose** (HK-018). My own bootstrap was re-implemented
from scratch against the raw rows rather than reading QA's CI back.

---

## 0. Verdict

**ROW 4 fires. QA's execution is ACCEPTED IN FULL.** Gate order correct, preconditions genuinely
cleared, exclusivity mechanically evaluated, the refusal to pick a side correct and per spec.
Every headline number reproduced independently:

| quantity | QA reported | my independent recompute | agreement |
|---|---|---|---|
| `H_3^cum` point | 1.5690 Hz | **1.5689583** | exact |
| `xL` / `xR` | −1.68017 / +1.45775 | **−1.68017 / +1.45775** | exact |
| all five variants' `H` | see §4 | **all five exact** | exact |
| `CI95(H_3^cum)` | [1.437, 1.687] | **[1.423, 1.687]** (own RNG stream) | 0.014 Hz on `CI_lo` |
| ROW 0a–0e | all clear | **all clear** | confirmed |

🔴 **But the ruling is not "narrow the CI." The recomputation says the CI cannot be narrowed, and
that this is the answer rather than an obstacle to it.**

---

## 1. THE RULING: the two quantities are EQUAL to within resolution

```
point estimate  H_3^cum      = 1.568958 Hz
the cut (lattice half-cell)  = 1.562500 Hz
|H - cut|                    = 0.006458 Hz   <-- 0.413% of the cut
SE(H) at 40 clusters         = 0.063462 Hz
CI half-width (1.96*SE)      = 0.124386 Hz
RATIO  CI-halfwidth / distance-to-cut = 19.3x
```

**The measured requirement and the lattice half-cell differ by four ten-thousandths of a Hz — 0.41%.**
The CI straddles not because the run was underpowered in any ordinary sense (658 rows, 40 clusters,
every precondition clear) but because **the quantity being measured sits essentially exactly on the
threshold it was gated against.**

🛑 **This does NOT pick a side, and must not be read as picking one.** ROW 4's consequence stands
verbatim. What I am adding is *why* the interval straddles, and that the straddle is terminal.

### 1.1 Narrowing is INFEASIBLE — measured, not argued

To place the CI wholly on one side you need `1.96·SE < |H − cut|`:

```
required SE          = 0.003295 Hz
variance reduction   = 371x
required clusters    = 40 x 371 = 14,838
corpus yields        = 68 matched-hit clusters from 4,614 cycles (18.96 h)
=> 218x the ENTIRE decisive corpus  =>  ~172 days of equivalent capture
```

And the population is already spent: of the 1,000-row / 56-cluster held-out pool,
Slice B consumed 717 rows / 40 clusters. **The never-read remainder is 283 rows / 16 clusters —
below N4's own 400-row / 30-cluster floor.** There is no second held-out slice to run.

🔴 **Consequence: any N5 that adds clusters to narrow this CI would burn a session to re-derive a
straddle. Narrowing is CLOSED. It is not expensive — it is infeasible.**

### 1.2 The obvious escape — a better-conditioned statistic — is also closed, and I measured it

The median-BER curve moves in **whole-bit steps** near the crossing (0.575 pp per 0.125 Hz grid
step; `B50` = 11.3% = **19.662 bits of 174**, which falls *between* achievable integer bit counts).
So the crossing is located by interpolating across a quantisation step of the statistic itself.

The natural fix is to gate the *identical named property* on a finely-quantised equivalent.
Note that `median(BER) < B50` **⟺** `q(df) ≡ fraction of rows with BER < B50 > 0.5` — the same
property exactly (**verified mechanically: the two agree at every one of the 71 grid points**), but
`q` is quantised at 1/658 = 0.152 pp instead of 1/174 = 0.575 pp, and its bootstrap takes ~1,190
distinct values where the median statistic takes 24–73.

**It buys almost nothing:**

| n_clusters | SE(median-crossing) | SE(q-crossing) | improvement |
|---|---|---|---|
| 40 | 0.06349 | 0.05987 | **6%** |
| 80 | 0.04707 | 0.04231 | 10% |
| 160 | 0.03682 | 0.03107 | **15%** |

⇒ **SE here is dominated by genuine between-cluster sampling variance, not by the statistic's
discreteness.** A 6–15% improvement against a 19.3× shortfall is irrelevant. **Do not propose
re-estimating `H` with a smoother statistic** — it is measured, not conjectured, and it does not work.

### 1.3 An error of mine inside this ruling, disclosed rather than quietly dropped

My first pass bootstrapped up to 5,120 clusters, saw the support of `H` collapse onto ~3 discrete
values with the mode pinned at ~50%, and read it as a **hard quantisation floor** — i.e. that no
amount of data could ever narrow the CI. **That reading was wrong and I withdraw it.** Resampling
5,120 clusters from only 40 unique ones measures the discreteness of *this* empirical sample, not
what real additional clusters would do; the honest scaling is §1.2's table, which broadly follows
1/√n. The infeasibility conclusion survives — but it rests on §1.1's 19.3× ratio, **not** on a
structural floor. I nearly published a stronger claim than the data supports, by exactly the
mechanism HK-026 exists to catch.

---

## 2. MY SPEC DEFECT — a gate must state the distance from its own threshold that it can resolve

🔴 **The N4 spec set the cut at 1.5625 Hz and never stated the minimum `|H − cut|` the design could
resolve.** That number is `1.96·SE ≈ 0.124 Hz`. Any true value within ±0.124 Hz of the cut produces
ROW 4 near-certainly. I set the cut 0.16 Hz above N3's post-hoc 1.403 — *just* outside the
resolution floor — and then ranked ROW 4 **fourth at 20%**. Had the spec carried its own resolution
floor, ROW 4 would have been the **modal** prediction, and I would have known before arming that
the design could only resolve the cut if the answer landed conveniently far from it.

**This is the sixth consecutive Architect-authored spec defect in this series**, and it is a *new*
sibling rather than another instance of (l):

> 🔴 **HK-021 (m) — A gate on a threshold MUST state the minimum distance from that threshold it can
> resolve (`≈1.96·SE` of the gated statistic), computed while drafting. If the expected value lies
> within that distance, a straddle is the MODAL outcome and must be predicted as such — not ranked
> as a tail. A cut the instrument cannot resolve is not a gate, it is a coin flip with a threshold
> painted on it.**

To be logged in `hk021-pre-registered-checks-must-be-mechanical.md`.

✅ **What the spec got right, and it is what saved the round: ROW 4 existed at all.** The spec's own
warning — *"a threshold chosen after seeing a nearby point estimate deserves distrust, and ROW 4
exists so a straddling CI is not forced"* — is exactly what happened. The design was sound; the
prediction was miscalibrated.

---

## 3. What the result MEANS operationally

🛑 **Everything in this section is POST-HOC, computed by me, on the point-estimate curve, with no CI
and no rounding correction. NOT CITABLE as the requirement — same status as N3's post-hoc widths.
It is a SIZING INPUT and it earns its own pre-registration.**

Median BER (V3_cum, Slice B) against the `B50` = 11.3% correction threshold:

| lattice config | worst-case \|df\| | median BER | margin to B50 |
|---|---|---|---|
| perfect anchor | 0.0000 Hz | 7.47% | **+3.83 pp** |
| **`K_FREQ_OSR=2` — SHIPPING** | 1.5625 Hz | 11.78% | **−0.48 pp** |
| `K_FREQ_OSR=4` (quarter-cell) | 0.7812 Hz | 8.69% | +2.61 pp |
| `K_FREQ_OSR=8` | 0.3906 Hz | 7.54% | +3.76 pp |

Integrated over the lattice's own uniform error range:
**at `K_FREQ_OSR=2`, 3.35% of the error range sits above `B50`; at `K_FREQ_OSR=4`, 0.00%.**

🔴 **Reading: the shipping lattice is MARGINALLY ADEQUATE for order-3 coherent extraction.** The
median row stays correctable across ~96.65% of the lattice's own error range and goes uncorrectable
only in the outer ~3.35%. That is much closer to ROW 1's world than ROW 2's — **but the margin is
thin and, per §1, permanently uncertifiable.** 🛑 **It therefore does NOT authorise building
anything**, exactly as ROW 1's own consequence already said.

### 3.1 A design boundary that falls out, and is genuinely useful

The measured order ladder — `H_1` = 1.916, `H_2^cum` = 1.757, `H_3^cum` = 1.569 Hz — falls by
**−0.174 Hz per coherent order** (deltas −0.160, −0.188). Extrapolating (🛑 **EXTRAPOLATION FROM
THREE POINTS, NOT MEASURED, gates nothing**):

```
order 4  H ~ 1.395 Hz   BELOW the 1.5625 half-cell
order 5  H ~ 1.222 Hz   BELOW
```

⇒ **order 3 is plausibly the LAST coherent order the shipping lattice supports.** QA's secondary
`D = H_1 − H_3^cum` = 0.347 Hz, CI [0.281, 0.462], p<0.0001 is what makes this more than arithmetic:
the requirement demonstrably tightens with order, so the ladder is real even if the step size is not
pinned. **This is a ceiling on limb 2's ambition, not on its viability.**

### 3.2 The consequence that matters for D-001

🔴 **The frequency-estimator prerequisite that N2 implied is NOT required at order 3.** N2's
headline was that the two limbs form a *conjunction* — coherent extraction needs fine frequency as
an enabler. N4 says the accuracy the existing lattice **already delivers** is (marginally) enough
for order-3 coherent extraction. **The N2 conjunction finding WEAKENS, exactly as ROW 1's
pre-registered consequence said it would** — on a point estimate whose CI cannot certify it.

✅ **That is a large practical simplification: limb 2 can be evaluated on real audio, at the
shipping anchor, with no frequency estimator built first.** Which is what N5 does.

🛑 **R2 STAYS EXCLUDED.** "The lattice is marginally adequate" is not "refinement helps" — N1 killed
that on outcome evidence (ROW 2, and refinement measurably *harmed* the strong-candidate stratum).
The R0/R1/R1b ~1.1 ms / 0.5 Hz prohibition is UNCHANGED. **Nothing here readmits it under a new name.**

---

## 4. Prediction scoring and calibration

| prediction | outcome |
|---|---|
| P(ROW 2) ≈ 45% (my top rank) | **MISS** — ROW 4 fired |
| P(ROW 4) ≈ 20% (4th rank) | fired |
| `H_3^cum` ∈ 1.2–1.6 Hz | **HIT** (1.569, near top edge) |
| `D = H_1 − H_3^cum` > 0 | **HIT**, p<0.0001 |
| ROW 0e does not fire; alias ~52.4% | **HIT** (edges 50.6%/51.1%, no aliased region) |

**Calibration now: categorical 6/11 · ranges 9/16 · DIRECTIONAL 2.5/5.5 · mechanical 3/4.**
⚠️ **Categorical is now below 55% and the failure mode is consistent: my INTERVALS keep landing and
my ROW CALLS keep missing.** Quote this wherever a gate turns on my prediction — and per §2, never
let one turn on a cut whose resolution floor is unstated.

---

## 5. 🔴 THE DECISION THAT IS NOT MINE

Per the Captain's direction I am drafting both the ruling and the follow-up, **but not arming the
follow-up.** Two routes exist and they are not equivalent:

- **Route N5-narrow — narrow the CI.** 🛑 **I RECOMMEND AGAINST IT.** §1.1/§1.2 price it at ~14,800
  clusters (218× the corpus, ~172 days) with only 283 rows / 16 clusters left unread and the
  better-statistic escape measured at 6–15%. It cannot succeed. I have specced nothing for it.
- **Route N5-outcome — §6 below.** Stop measuring requirements and measure whether limb 2 actually
  recovers decodes on the population that fails. Unblocked *because* of N4's result.

**The Captain's call.** If N5-outcome is not wanted either, the defensible stopping point is: record
that `H_3^cum` equals the lattice half-cell to within 0.41%, that limb 2 needs no frequency enabler
at order 3, and that order 4 is where the lattice runs out — and close the N-series there.

---

## 6. N5 SPEC — does coherent order-3 extraction CONVERT on the FAILED population?

✅ **ARMED — Captain's ruling 2026-08-17 16:52Z, route N5-outcome. QA runs it (HK-025 refusal available).**
🔴 **Read Amendment 1 (§6.1) FIRST — it wins over the body wherever they disagree. It was written
BEFORE the harness existed and BEFORE any data was seen; the body below is retained as
pre-registration provenance and must NOT be edited to match any outcome.**

**The question.** Every N-series arm so far measured a *requirement* on a *control* population
(matched hits, known-good). N5 asks the D-001 question directly: **at the shipping lattice anchor,
with no frequency estimator and no refinement, does order-3 coherent extraction turn failures into
decodes?**

**Population.** THE 135 + THE 567 (candidate-present-and-failed) — N1's exact population, 441 rows /
405 measured / 67 `ts` clusters. Reuse `n1-ber-at-refined-position/population.py` **verbatim**.
🔴 **`compute_matched_hit_control(..., limit=N)` TRUNCATES IN FILE ORDER — it does not sample. Report
CLUSTER counts, never bare row counts** (the fault that cost N1–N3 a ≈3.8× CI error).

**Arms, at the production candidate's own lattice anchor, no search of any kind:**
- **V0** — `ft8_extract_llrs_at`, unmodified C (the shipping read).
- **V3_cum** — `coherent_extract_ext.py`'s order-3 cumulative variant, **unrounded anchor**
  (N4's mandatory fix; do **not** edit `_anchor()` itself — N1's rows read it).

**Primary statistic.** `f_cross` = fraction of rows crossing from `BER_V0 ≥ B50` to `BER_V3 < B50`.
🔴 **`f_cross` is what converts a miss into a decode; `d_ber` is not.** The failed population sits
at ~44% median BER — **4× the correction threshold** — so aggregate BER movement of a few pp converts
nothing (the 2026-08-08 reframing, already on the board). `d_ber` is reported for **attribution only**.
Cluster bootstrap over `ts`, 2,000 draws, seeded, sorted at construction.

**Gate, strict order:**

| row | condition | consequence |
|---|---|---|
| **0a** | V0 median BER on the failed population ≠ 43.97% ± 2 pp | not N1's population/instrument — VALIDITY |
| **0b** | <200 paired rows **or** <30 `ts` clusters | PRECISION, escalate underpowered |
| **0c** | median V0-vs-V3 hard-decision disagreement <5 of 174 bits | same reading, contrast cannot move — VALIDITY (the M4 lesson, reused from N2 ROW 0d) |
| **0d** | sign unit test fails | VALIDITY — **re-run it, do NOT inherit N3/N4's pass**, including QA's 48-realisation/−18 dB correction |
| **ROW 1** | `CI_lo(f_cross) > 0.05` | limb 2 CONVERTS materially ⇒ C integration becomes scopeable and a proper sizing is ORDERED 🛑 does not authorise building it |
| **ROW 2** | `CI_hi(f_cross) < 0.05` | limb 2's prize is **upper-bounded below 5%** of the failed population ⇒ against a ~23 pp D-001 prize this is not the treatment ⇒ 🔴 **BOTH LIMBS closed on outcome evidence and the 2026-08-11 diagnosis REOPENS** |
| **ROW 3** | residue (CI straddles 0.05) | report the interval, do not pick a side |

Exclusivity: `CI_lo > 0.05 ⇒ CI_hi > 0.05` ⇒ ROW 1 and ROW 2 cannot both fire. Exhaustive by
construction.

🔴 **RESOLUTION FLOOR, stated per §2's new sibling (m) — this is the rule working immediately:**
with ~67 clusters and `p` near 0.05, `SE(f_cross) ≈ 0.027` ⇒ **ROW 2 fires reliably when true
`f_cross` ≲ 0.03; ROW 1 needs `f_cross` ≳ 0.09; anything between straddles.** ROW 3 is therefore a
live and substantial possibility. ✅ **It is still worth running: a ROW 2 upper bound below 5% would
CLOSE limb 2 on outcome evidence, and that is the single most decision-relevant number left in the
programme.** ROW 3 still delivers a bound.

**Secondary, non-gating, reported not gated.** `f_cross` restricted to the reachable stratum
`BER_V0 < 20%` (pre-registered from N1's **published** p10 = 17.2%, not chosen after seeing N5 data
— that is where any conversion must be concentrated). ⚠️ **Name the artefact: selecting rows on a
noisy baseline realisation of the outcome invites regression to the mean, biasing `d_ber` against
V3. Conservative for ROW 1, but it must be stated, not discovered later.**

**Scope. 🛑 No `src/`, no Developer session, no DLL rebuild, no capture run — HK-011 NOT engaged.**
No per-row frequency search, no time refinement, no aperture sweep (that is R2's corpse and it stays
buried). Rectangular window only. Pin the DLL by **SHA256 `6890d84c4bcf2e90…` / shim 20260042**,
asserted against the manifest, never inferred from a label. NFR-021: grep every `results/*` file
individually. ≤45 min, cap 2 h; **drop whole CLUSTERS if the cap binds, never the population definition.**

**HK-025.** 0a/0c/0d are VALIDITY; 0b is PRECISION and survives on different-downstream-row grounds.
🔴 **Re-derive this independently and refuse if you disagree — five of the last six specs in this
series carried a defect of mine that QA or a recompute found. Treat my classification as a claim.**

**Predictions 🛑 NOTHING GATES ON THEM.** P(ROW 2) ≈ 45% · P(ROW 3) ≈ 40% · P(ROW 1) ≈ 10% ·
P(any ROW 0) ≈ 5%; `f_cross` ∈ 0.00–0.04 (range). ⚠️ **Categorical 6/11 — read the row call with
suspicion; the range is the better-calibrated half of my record.**

---

## 6.1 🔴 AMENDMENT 1 — 2026-08-17 16:58Z, BEFORE ARMING, BEFORE ANY HARNESS EXISTED

I audited my own §6 against the committed N1 artefacts before handing it over, per the discipline
that §2's new sibling (m) came out of. **Two defects, both mine, both fixed here rather than
discovered by QA mid-run.** This makes seven; the audit is the only reason it is not an eighth
found after the fact.

### A1.1 — ROW 0a referenced a number that does not exist for N5's population

§6's ROW 0a bars on "V0 median BER on the failed population ≠ 43.97% ± 2 pp". 🔴 **43.97% is
`THE 135`'s median alone (n=126)** — `2026-08-16-1353-qa-to-architect-n1-results.md` line 15,
where it reproduces W1's 44.0% exactly. **The combined `THE 135 + THE 567` population (n=405) has
no published median**, so as written the precondition compares a 405-row statistic against a
126-row reference and would fire or pass for reasons unrelated to instrument identity. HK-021(c)
family — the metric is not identifiable from the reference it names.

**ROW 0a IS REPLACED BY:**

> **ROW 0a** — `THE 135` stratum alone (n≈126), V0 median BER ≠ **43.97% ± 2 pp** ⇒ not N1's
> population/instrument, VALIDITY. 🛑 **Evaluated on the stratum, never on the pooled population.**
> `THE 567`'s own median is reported for the record but **gates nothing** — no published reference
> value exists for it.

### A1.2 — the gate was blind to the direction that would falsify it

`n1_stats.f_cross_row` counts **above→at-or-below only**, and its docstring is right to: pooling
both directions "would hide a harmful refiner behind a helpful one — exactly the kind of unsigned
statistic HK-021(l) forbids." ✅ **Reuse it VERBATIM; do not redefine it.**

🔴 **But my §6 never required the reverse quantity to be reported at all — and for THIS treatment
that is not a theoretical gap. N2 measured V3 making BER WORSE than V0 on the matched-hit control
(2.87% → 8.05%, monotonically worse with coherent order).** A treatment already measured to degrade
good rows can therefore push correctable rows *above* `B50` while gross `f_cross` looks fine. N1
never had to care because refinement's `f_cross` was **0.0%** on both strata. V3 is a different
treatment and the harm direction is *expected*, not hypothetical.

**MANDATORY ADDITIONS:**

> **`f_break`** = fraction of rows with `BER_V0 ≤ B50` that go **above** `B50` under V3 — its own
> named, separately-reported statistic with its own cluster-bootstrap CI. 🛑 **NEVER pooled with
> `f_cross` into a single number.**
>
> **`f_net` = `f_cross` − `f_break`**, expressed as a fraction of the whole measured population,
> reported with a paired cluster-bootstrap CI (resample clusters once per draw, recompute both terms
> on the same clusters).
>
> 🔴 **ROW 1 IS TIGHTENED: `CI_lo(f_cross) > 0.05` **AND** `CI_lo(f_net) > 0` .** A treatment that
> converts 6% while breaking 6% has converted nothing, and the un-amended ROW 1 would have called
> that a success. ROW 2 and ROW 3 are UNCHANGED (`f_cross` alone; a low gross crossing rate already
> forecloses benefit regardless of `f_break`).

⚠️ **Denominator, stated because it is not automatic:** `f_cross`'s denominator is rows with
`BER_V0 > B50` (only those *can* cross down); `f_break`'s is rows with `BER_V0 ≤ B50`. **Report both
denominators and their cluster counts explicitly** — N1's p10 = 17.2% for `THE 135` means the
second group is small but non-empty, and 🔴 **if `f_break`'s denominator carries <30 rows, report
`f_break` as descriptive-only and say so; do not let ROW 1's new `f_net` term turn on a handful of
rows** (HK-021(j) — absence is not diagnostic at low expected counts).

### A1.3 — predictions revised BEFORE the run, on evidence, and recorded as a change

§6 predicted P(ROW 2) ≈ 45% · P(ROW 3) ≈ 40% · P(ROW 1) ≈ 10%. Two facts I had not weighted:
**N1's `f_cross` was exactly 0.0% on all 405 rows** under refinement, and **N2's V3 was worse than
V0 on the control at every coherent order.** Both point the same way.

🔴 **REVISED: P(ROW 2) ≈ 65% · P(ROW 3) ≈ 25% · P(ROW 1) ≈ 5% · P(any ROW 0) ≈ 5%;
`f_cross` ∈ 0.00–0.02; `f_break` > 0 (DIRECTIONAL — my weakest class at 2.5/5.5, nothing gates on it).**
⚠️ **Recorded in advance and reversing my own §6 numbers on evidence, not adjusted afterward.**
🛑 **Nothing gates on any of these, and categorical is 6/11 — read the row call with suspicion.**

1. 🛑 **`H_3^cum` = 1.569 Hz may NEVER be quoted without its CI [1.437, 1.687] and the statement that
   it straddles the 1.5625 Hz cut.** No "the requirement is met"; no "an estimator is required."
2. 🛑 **§3's margin table and the `K_FREQ_OSR` rows are POST-HOC, no CI, uncorrected — a sizing input,
   not a requirement, and NOT authorisation for an OSR change.** An OSR change still needs its own
   pre-registration with **false positives as the PRIMARY metric** (the board's standing item).
3. 🛑 **§3.1's order-4/order-5 figures are EXTRAPOLATION from three points.** Cite the measured
   ladder and `D`; never the extrapolated numbers as measurements.
4. 🔴 **Narrowing this CI is CLOSED. Do not re-propose it under any statistic, grid, or population** —
   including the 283-row / 16-cluster remainder, which is below N4's own floor. Per HK-026 and the
   standing "never re-read a closed gate with a better metric" rule, N4's data is spent.
5. ✅ **All five variants' `H`, `D`, and the pure-vs-cumulative comparison are citable as measured**
   on the held-out Slice B, with their CIs. Slice A's figures remain non-gating cross-checks.
6. 🛑 **R2 stays excluded** (§3.2). The 0.5 Hz digit in ROW 3's threshold is WSJT-X's `ALL.TXT`
   integer-Hz reporting quantisation and is **not** the barred R0/R1/R1b refiner figure.

---

## 8. Next

✅ **CAPTAIN RULED 2026-08-17 16:52Z: route N5-outcome. §6 IS ARMED, as amended by §6.1.**
🔴 **NEXT: QA RUNS N5 — HK-025 refusal available, and §6.1 is evidence you should use it.** Five of
the last seven specs in this series carried a defect of mine; two of this one's I found myself only
by auditing against the committed N1 artefacts instead of my own draft. **Re-derive the HK-025
classification independently and refuse against this document if you disagree.**

🛑 **Narrowing N4's CI is CLOSED and is not part of this (§1, §7.4).** No `src/`, no Developer
session, no DLL, no capture run.

A2 (AC-4 ROW 0) and A3 (re-run D3 emitting slope + SE + p) remain open and still must not become a round.
