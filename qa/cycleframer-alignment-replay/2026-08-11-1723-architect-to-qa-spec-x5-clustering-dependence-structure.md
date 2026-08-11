# ARCHITECT → QA — spec X5: which dependence structure governs `E_sep`? (X4's unresolved robustness flag)

**Author:** Architect, 2026-08-11 (17:23 UTC, `date -u`, HK-017).
**For:** QA.
**Authorisation:** 🔴 **The Captain ruled 2026-08-11: do NOT retire spectral locality; run the fourth
registration.** This is that registration. It supersedes X4 §4.1's retirement trigger *only* to the
extent the Captain's ruling does — the rule is **re-armed below at §4.1 and can still fire.**
**Costs:** `ALL.TXT` analysis only. **No `src/`, no rebuild, no decoder replay, no capture.**
Extension of an existing harness, not a new one (§2.4).

---

## 0. 🔴 Read first — why this is a new pre-registration and not a re-read

HK-021's standing bar is *"a better metric earns a new pre-registration, never a re-read."* The
obvious objection to X5 is that it is a re-read wearing a new hat: the Architect did not like the
stopping rule he wrote, so he is writing another one. **That objection is legitimate and is the
reason this section exists.** Five constraints make X5 a registration rather than a re-read, and QA
should hold me to every one:

1. **The gate is X4's gate, verbatim, unchanged** (§4). Not one bar is moved. `E_sep >= 8.0`,
   `lo > 0`, `se_E <= 2.0`, ROW 2's `< 3.0` — all exactly as committed on 2026-08-10, *before* any
   number existed.
2. **The new quantity is a variance estimator, registered before it is computed** — not a new
   contrast, not a new population, not a new outcome, not a new stratifier.
3. **The retirement rule is re-armed and can fire** (§4.1). If the two-way SE exceeds 2.0, the arm
   voids at ROW 0f and spectral locality retires — and §3.4 establishes that void would be
   **terminal**, not curable by more data.
4. **Prediction scoring on `E_sep` is SUSPENDED** (§6), the P1a precedent. The point estimate is
   fully de-blinded and I have seen it.
5. **The Captain authorised it explicitly**, knowing my interest. I stated that interest on the
   record before the ruling.

🛑 **What X5 does NOT do:** it does not read ROW 1 off X4's numbers. X4's `E_sep` = +46 pp remains
uncitable until a gate is evaluated under a registered SE. If X5 voids, X4 stays unread and the
number stays dead.

### 0.1 Full de-blinding disclosure

I have read `x4_result.json` and the X4 report. **Everything below was written knowing:**

- `E_sep` = **+46.039 pp** (n_contributing_cells 4 570, total_weight 5 631.0)
- `SE_cycle` = **0.653 pp**, 95% CI [+44.733, +47.348]
- `SE_freq` = **1.371 pp**, 95% CI [+44.027, +49.261]; ratio 2.102
- Every ROW 0 result: 0a 69 222, 0b −0.248 pp, 0c 0.000000, 0d 540 distinct, 0e 5/5 strata, 0g 868

⚠️ **This also means `SE_2way` is partially predictable from published numbers** — see §6, where I
show the arithmetic rather than hide it. **The genuinely blind quantity in X5 is `V_intersection`,
and therefore whether `SE_2way` lands under or over the 2.0 bar.** QA should read my §6 prediction
as informed, not blind, and weight it accordingly.

---

## 1. What X4 settled, and the one thing it did not

**X4 validated the instrument.** For the first time in three attempts, every ROW 0 condition passed,
including the two that killed its predecessors:

| check | killed | X4 |
|---|---|---|
| ROW 0c — within-cycle construction (`n_cycle` gap) | **S.1** (between-cycle confound) | **0.000000 exactly** |
| ROW 0b — mandatory null, 20 within-cycle shuffles | **S.1** (20/20 one-sided positive) | **−0.248 pp**, no directional bias |
| ROW 0e — stratum population | **S.1r** (0 of 12 cells) | **5 of 5 strata**, wide margins |

**What it did not settle is a variance question.** The cycle-clustered and frequency-clustered
bootstraps disagreed by 2.102× against a 2.0 bar, and X4's own rule stopped the arm before the gate.

🔴 **The drafting defect is mine, and it is HK-021's founding failure in a new costume: I placed an
unconditional robustness precondition ahead of a gate whose verdict is invariant to it.** Under
*either* clustering assumption, `E_sep` clears the ROW 1 magnitude bar by ~38 pp and its lower CI
bound clears zero by ~44 pp. The precondition could not inform the row it blocked. This is the same
family as P1's ROW 0d — a check that stopped an arm without being able to change its answer — and
the P1 precedent governs the remedy: **it licenses a fresh registration, never a re-read.**

⚠️ **The one place clustering IS load-bearing, and it is why X5 is worth running rather than
waived:** ROW 0f voids at `se_E > 2.0`. Frequency-clustering already gives 1.371. A more
conservative dependence structure crossing 2.0 is **not** far-fetched. The row is robust to the
clustering choice; **whether the arm is powered at all is not.** That is the real open question.

---

## 2. Design

### 2.1 The estimator — two-way (multiway) cluster-robust variance

Decodes are clustered along **two non-nested dimensions**: the cycle (X4's estimator unit; ROW 0c
makes each contributing cell single-cycle by construction) and the station frequency (T2a's
convention — a station's audio frequency is near-fixed, design effect 3.5–4.2×). Neither dimension
nests inside the other, so neither one-way bootstrap is correct on its own — which is exactly what
the 2.102× ratio is reporting.

The standard estimator for crossed clustering (Cameron–Gelbach–Miller) is:

```
V_2way = V_cycle + V_freq - V_intersection
```

where the intersection clusters are the distinct `(cycle, freq_hz)` pairs. All three are computed as
bootstrap variances through **the same `compute_E_sep()` point-estimate path** already exercised by
X4, via its existing `weight_of` reweighting hook.

```
SE_2way = sqrt(V_2way)
```

🔴 **`SE_2way` replaces `se_E` everywhere in the gate. `SE_cycle` and `SE_freq` become reported
context only.** No gate row consumes them after this spec.

### 2.2 Degeneracy handling — pre-registered, because CGM is known to misbehave in finite samples

`V_2way` can come out non-positive or below the larger marginal. **Both fallbacks are conservative
and neither may reduce the SE below the marginals:**

```python
if V_2way <= 0:                                  # CGM_DEGENERATE_NONPOSITIVE
    SE_2way = max(SE_cycle, SE_freq)
elif sqrt(V_2way) < max(SE_cycle, SE_freq):      # CGM_DOMINATED
    SE_2way = max(SE_cycle, SE_freq)
else:
    SE_2way = sqrt(V_2way)
```

**Record which branch fired in `x5_result.json` as `se_2way_branch`.** A fallback is a disclosed
result, not a failure — but it must never be silent.

### 2.3 Seeds, pinned now so they cannot be chosen later

| bootstrap | seed | draws |
|---|---|---|
| cycle-clustered | `20260810` (X4's `SEED`, unchanged) | 1 000 |
| frequency-clustered | `20260810 + 1` (X4's, unchanged) | 1 000 |
| **intersection-clustered (new)** | **`20260810 + 2`** | 1 000 |
| coarsened-block diagnostic (§5.1) | `20260810 + 3` | 1 000 |

### 2.4 Reuse, not rewrite (HK-004)

`x4_spectral_locality.py` already carries everything needed:
`compute_E_sep(records, weight_of=...)` accepts a per-record reweighting callback, which is precisely
how `freq_clustered_bootstrap()` reweights by a cluster's draw multiplicity. The new
`intersection_clustered_bootstrap()` is the same function over `(cycle, freq_hz)` keys.
**Extend the existing harness as `x5_clustering_dependence.py`, importing from X4's module rather
than copying it** — a copy would drift, and the point estimate must be bit-identical to X4's.

🛑 **Do not modify `x4_spectral_locality.py`'s own outputs.** X4's result file is the pre-registration
record of what was computed on 08-10 and must remain reproducible as-is.

---

## 3. ROW 0 — void conditions, in strict order

| row | check | bar | consequence |
|---|---|---|---|
| **0a** | `E_sep` reproduces X4's point estimate | == **+46.039** pp (to 3 dp) and `REF` == 69 222 | **VOID** — a different point estimate means the import drifted |
| **0b** | 🔴 **determinism, ACTUALLY VERIFIED** — two independent runs, byte-identical `x5_result.json` **and** stdout, diffed mechanically | byte-identical | **VOID** (see §3.1) |
| **0c** | X4's own ROW 0b/0c/0d/0e/0g re-assert unchanged on import | all as published in §0.1 | **VOID** — the imported population is not X4's |
| **0d** | intersection clusters counted and reported | count + decodes-per-cluster distribution recorded | **STOP for re-registration** if the mean is < 1.05 (see §3.2) |
| **0e** | `se_2way_branch` recorded | one of the three named branches | **VOID** if unrecorded |
| **0f** | 🔴 **power** | **`SE_2way` ≤ 2.0 pp** | **UNDERPOWERED, no row read** — and per §3.4 the void is **TERMINAL**; retirement fires (§4.1) |
| **0g** | connected-component degeneracy computed (§3.3) | reported, non-gating | record only |

### 3.1 ROW 0b is not a formality — X4 found a real determinism bug here

X4 §1.1: `REF` is built from `set(a) & set(b)` over string-tuple keys, and Python randomises
string-hash seeding per process, so **the same seed produced different bootstrap SEs across runs**
until every such list was sorted at construction. X5 inherits the fix, and **must verify it rather
than assert it** — X4's own report notes that P2/P3/P1a asserted this requirement in their specs and,
as far as records show, **never actually ran two runs and diffed them.** Do not repeat that.

### 3.2 Why ROW 0d exists — the intersection clusters must not be near-singletons

If every `(cycle, freq_hz)` pair holds essentially one decode, `V_intersection` collapses toward the
iid variance and `V_2way → V_cycle + V_freq`, which makes the CGM correction cosmetic. That is a
*legitimate* outcome (it means the two dimensions really are near-independent) but it must be
**observed and reported, not assumed**. If mean decodes per intersection cluster is < 1.05, the
correction term is doing nothing and the arm stops for re-registration rather than dressing up
`sqrt(V_cycle + V_freq)` as a two-way estimator.

⚠️ **Compute this first, before the bootstraps.** It costs one pass and it is the check that decides
whether the rest of the arm means anything — HK-021's "draft the gate by writing the code."

### 3.3 The degenerate alternative, killed by computation rather than by argument

There is a third clustering one could propose: cluster on **connected components** of the bipartite
cycle ↔ frequency graph, which would dominate both dimensions exactly. **I believe this is degenerate
on this corpus** — with ~2 529 cycles sharing from ~2 593 distinct frequencies, the graph is almost
certainly one giant component, giving one cluster and an undefined SE.

🛑 **Do not take my word for it. Compute the largest component's share of decodes and record it.**
If it is ≥ 95%, the connected-component route is **formally closed** and may not be re-proposed. If
it is < 95%, that is a genuine surprise and QA should **stop and escalate** rather than proceed —
it would mean the corpus has a block structure nobody has noticed.

This is HK-021's "never estimate a confound in prose — compute it," applied to my own reasoning.

### 3.4 🔴 A ROW 0f void is TERMINAL — the structural-ceiling corollary

If `SE_2way` > 2.0, **do not report it as "needs a larger corpus."** T2a established the ceiling and
it binds here: over the hardcoded 200–3000 Hz passband there are ~2 801 possible integer frequencies;
20m alone already holds **2 593 (93%)**, and the three-band union reaches only **2 732 (97.5%)** —
80m contributes **9** frequencies not already present. Cycle clusters are similarly bounded by the
corpus's fixed span.

⇒ **More runtime adds decodes per cluster, not clusters.** Effective n is bounded by a structural
property of the instrument, not by how long we run. A ROW 0f void therefore means the question is
**not answerable from `ALL.TXT` at any runtime**, which is precisely the finding X4 §4.1's retirement
rule contemplated. **State it that way and close it; do not invite a capture run that cannot help.**

---

## 4. The gate — X4's, VERBATIM, with `se_E := SE_2way`

```python
if null_fails:                            return "ROW 0b"   # VOID, contaminated estimator
if n_cycle_gap != 0.00:                   return "ROW 0c"   # VOID, not a within-cycle contrast
if se_E > 2.0 or strata_unpopulated:      return "ROW 0e/0f"  # instrument failure, NOT a null
if E_sep >= 8.0 and lo > 0:               return "ROW 1"    # LOCAL limb
if abs(E_sep) < 3.0 and se_E <= 1.5:      return "ROW 2"    # DIFFUSE limb
if E_sep <= -8.0 and hi < 0:              return "ROW 3"    # reversed - unexplained
return "ROW 4"                                              # inconclusive
```

`lo`/`hi` are the 95% CI bounds computed from `SE_2way`. **Consequences are X4 §4's, unchanged and
un-restated here** — read them from that document so no drift is possible between the two.

🛑 **Not one threshold in this block may be edited.** They were committed on 2026-08-10 while nobody
knew the answer. Editing any of them now, knowing `E_sep` = 46, is fitting the gate to the data —
the exact sin HK-021 exists to prevent, and it would retroactively void X4 as well.

### 4.1 🔴 Retirement rule — RE-ARMED, with the gap closed

X4 §4.1's trigger list was **incomplete**: it named void-on-0b, void-on-0c and ROW 4, and X4 then
stopped in a fourth way nobody had enumerated. That gap is mine. It is closed here:

> **Spectral locality is RETIRED PERMANENTLY if X5 reaches ANY outcome other than a clean ROW 1,
> ROW 2 or ROW 3 read.** That includes, without limitation: any ROW 0 void; ROW 4; a stop for
> re-registration under 0d; an escalation under §3.3; or **any outcome not enumerated in this
> document.** There is no fifth design, no further metric on this data, and no sixth attempt.

**The catch-all clause is deliberate.** X4 died in a way its own rule did not anticipate, and the
lesson is that enumerating failure modes is not something I do reliably. **Anything that is not an
answer is a retirement.**

⚠️ QA: if X5 stops in yet another unanticipated way, **that fires the rule** — report and stop; do
not escalate for a fifth ruling.

---

## 5. Reported diagnostics — never gating

### 5.1 A conservative bound that runs AGAINST my prediction

Because `sep` is a statement about *neighbouring* frequencies, decodes at **nearby** frequencies may
be more dependent than exact-frequency clustering assumes. Compute a **coarsened frequency-block**
bootstrap: cluster on `floor(freq_hz / 50)`, i.e. 50 Hz blocks — physically motivated by FT8's ~50 Hz
occupied bandwidth, and close to X4's own median `sep` of 40 Hz. Report `SE_block` and its cluster
count.

**This is deliberately the direction that could kill the arm**, and I want it visible: if
`SE_block` > 2.0 while `SE_2way` ≤ 2.0, the row still reads (the gate is `SE_2way`'s) **but the
report must carry the conservative bound explicitly in its citation limits.**

🛑 **I considered making `SE_block` gating and deliberately did not.** The 50 Hz width is a parameter
*I* invented; the data did not supply it. Gating on an invented parameter is HK-021(d) — the C.5a
failure, where the choice of parameter became the answer. **It is reported so the reader can discount
the result; it does not decide it.** If QA judges this reasoning wrong, escalate rather than
promoting it to a gate in session.

### 5.2 Report alongside, non-gating

- `SE_cycle`, `SE_freq`, ratio (X4's, re-derived — must match §0.1 exactly).
- `V_intersection` and the implied correction term.
- Intersection-cluster count and decodes-per-cluster distribution (§3.2).

---

## 6. Architect predictions — and an honest statement of how much they are worth here

🛑 **Prediction scoring on `E_sep` is SUSPENDED.** I have seen +46.039 pp. The P1a precedent applies:
where a quantity is de-blinded, no credit may be claimed on it in either direction.

⚠️ **My `SE_2way` prediction is INFORMED, not blind, and here is the arithmetic so QA can discount it
rather than trust it:** from §0.1, `V_cycle` = 0.653² = 0.426 and `V_freq` = 1.371² = 1.879. If
intersection clusters are near-singletons, `V_intersection` is small (order 0.01–0.09), giving
`V_2way` ≈ 2.2–2.3 and `SE_2way` ≈ **1.48–1.52 pp** — under the 2.0 bar. **Anyone can do this sum
from X4's published numbers, which is exactly why I am showing it rather than presenting a
prediction as insight.**

Updated calibration, to be quoted wherever a gate turns on my judgement:

| | tally | movement |
|---|---|---|
| categorical ROW calls | **5/7** | unchanged — *neither X3 nor X4 produced a scorable row call* |
| point estimates / ranges | **8/14** | ⚠️ **was 7/10 — three fresh misses** (X3 #2, X3 #3, X4 #2), one hit (X4 #3) |
| DIRECTIONAL / SHAPE | **1/3** | X3 #5 hit, on an explicitly ungated call |
| mechanical | **2/2** | X3 0e, X4 0c |

🔴 **The pattern that matters: my last three magnitude calls all missed, and X4's missed by 6× on
the high side** (`E_sep` ∈ [5,25] predicted, +46.0 measured). X3's missed on **sign**. Read
everything below at that discount.

| # | prediction | type |
|---|---|---|
| 1 | `SE_2way` ∈ **[1.3, 1.8] pp** ⇒ ROW 0f passes | magnitude — **informed, see above** |
| 2 | `se_2way_branch` == `"CGM_OK"` (neither fallback fires) | categorical |
| 3 | mean decodes per intersection cluster ∈ **[1.0, 1.3]** ⇒ ROW 0d passes but the correction term is small | magnitude |
| 4 | largest connected component ≥ **99%** of decodes ⇒ §3.3's route formally closed | magnitude |
| 5 | `SE_block` ∈ **[1.5, 3.0] pp** — deliberately wide; I have no basis for precision | magnitude |

**I expect ROW 1 (LOCAL).** I expected it before X4 ran and I still do, which is worth very little
now that I have seen the point estimate. **The only bar that can fire against me is ROW 0f, and I
have left it at 2.0 exactly where I set it blind.**

---

## 7. Standing bars this arm must not cross

- 🛑 **Subtract-and-resynthesise stays DEAD** regardless of row — three builds, three reverts
  (`20260007` −4.30 pp; H3 CP-FSK `20260008`; H3b GFSK quadrature `20260009` at −17 pp). ROW 1 makes
  the *question* live; it does not make that *implementation* live.
- 🛑 The shipped waterfall-domain suppression (`suppress_candidate_tiles`, pass 1) is **not** in
  scope — it fires after pass 0 has committed its decodes and cannot cost a pass-0 decode.
- 🛑 **No `src/` recommendation, no parameter sizing, no capture run, in any row.**
- 🛑 **`E_sep`'s MAGNITUDE remains uncitable even on ROW 1.** ROW 1 licenses the **LOCAL limb**, not
  the number. +46 pp is 2.5× X2's headline crowding effect and 6× my predicted range; X4 §4.2's
  marginal cross-check rules out a coding defect but controls for nothing beyond SNR stratum.
  **Do not average it into any other figure. Do not quote it as the size of the crowding term.**
- ⚠️ Per X4 §2 and HK-021(h): `sep` is built from `REF`, which is itself incomplete, so it is an
  **upper bound** on true separation and the contrast is attenuated ⇒ **quote "at least X", never
  de-attenuated.**
- ⚠️ Basis discipline: T1 basis, `<...>`-bearing messages excluded, 200–3000 Hz. **Never mix with the
  H1a-corrected ≈57.8% figure**, which used wildcard matching over a different population.

## 8. Boundaries

- **No `src/`, no rebuild** (HK-011). **No push, no merge** (HK-014/HK-010).
- Per HK-015 this is Architect → QA. `dev-tasks/*.md` are QA's to author, not mine.
- **NFR-021:** counts, rates, frequencies and cycle timestamps only. Message text may be read to
  build match keys; **no callsign or message text in `x5_result.json` or the report.**
- Determinism: **two runs, byte-identical, mechanically diffed** — ROW 0b, not an assertion.
- Output `x5_result.json`. Report per the standing NFR-024 / HK-001 structure.
