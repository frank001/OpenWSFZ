# ARCHITECT → QA — spec X4: S.1 REOPENED. Within-cycle spectral locality, third and final attempt.

**Author:** Architect, 2026-08-10 (18:08 UTC, `date -u`, HK-017).
**For:** QA.
**Authorisation:** 🔴 **The Captain reopened S.1 on 2026-08-10** (ruling 2 of 3, in answer to the X2
route memo). This supersedes the standing closure of 2026-08-04, reconfirmed 2026-08-07. The 🛑
"do not re-litigate" rule in `MEMORY.md` and the parked-status memory file are updated in the same
session as this spec, per HK-024.
**Costs:** `ALL.TXT` analysis only. **No `src/`, no rebuild, no decoder replay, no capture.**

---

## 0. Why this is now worth reopening, and what has changed since it was closed

S.1's original question was *"is the D-001 density penalty frequency-local or cycle-global?"* — a
fork on the **B.3 menu's** engineering cost. That framing is now stale in an important way:

**X2 has already measured the density penalty.** `F_std` = **+17.22 pp** at matched SNR, replicating
on all three bands, and **reconciled away from the candidate-budget family** (C.1 +0.93%, RC4
+0.70 pp, D-009 +0.109 pp; RC1's 87.9% candidate-present-and-failed). So the "cycle-global" limb as
originally conceived — *budget exhaustion* — is **already closed, twice**, and is not what X4 is
choosing between.

🔴 **The live fork is now a different and sharper one.** Given that crowding costs 17 pp, is that
cost delivered by **specific near neighbours** or **diffusely by the whole cycle**?

| limb | mechanism | engineering consequence |
|---|---|---|
| **LOCAL** | pairwise co-channel / adjacent-signal contamination of the extraction bins | separation of adjacent signals is the target: sync refinement, coherent/multi-symbol extraction, correctly-placed subtraction |
| **DIFFUSE** | aggregate energy raises the effective noise floor across the passband | per-signal separation buys little; the target is the estimator's noise handling, and the problem is materially harder |

That fork is worth one session. It is also the **direct** mechanism test that X3 deliberately routes
around — X3 asks whether *our placement* amplifies crowding; X4 asks what crowding *is*.

---

## 1. 🛑 The two prior instrument failures, and how this design is different

**Both prior attempts died as instruments, not as nulls.** Neither produced a reading, and the
descriptive figures from both remain on the citation blacklist. QA must not re-derive either.

### 1.1 S.1 (2026-07-31) — VOID on the mandatory null. Between-cycle confound.

`n_local` **proxied `n_cycle`**: decodes in busier cycles have more neighbours, so they land in the
`hi` cell more often *even inside a density stratum*, because a stratum is a **range** of densities.
Measured at the time: mean `n_cycle` was +0.86 (sparse) / +1.79 (dense) higher in `hi` than `lo`.
A **within-cycle shuffle cannot break a between-cycle confound** — permuting frequency inside a
cycle leaves that cycle's `n_local` multiset invariant. The null was exact *and* blind, and 20/20
one-sided shuffles came out positive because the bias was structural.

🛑 **Do not cite `Δ_local = +29.2` or `Δ_cycle = +26.9`. They are contaminated quantities.**

### 1.2 S.1r (2026-08-07) — ROW 4. Unpopulated stratum from an ABSOLUTE boundary.

The pre-registered `>150 Hz` "clear" stratum survived the n≥20 gate in **0 of its 12** cells: in a
window carrying 30–49 decodes across ~2 800 Hz, **a decode with no neighbour within 150 Hz
essentially does not occur.** The boundary sat at roughly the **97th percentile** of the separation
distribution. **That is HK-021(b) exactly — an absolute constant where a quantile was required.**

⚠️ S.1r's own `sensitivity_25_100` row showed both limbs live and large. **It is non-gating,
reported-for-context only, and must not be treated as a result or used to choose X4's cuts** — the
cuts below are quantiles, derived from the data's own distribution, precisely so that no boundary is
ever chosen by looking at an outcome.

### 1.3 What X4 changes

| failure | X4's fix |
|---|---|
| between-cycle confound (S.1) | **within-cycle estimator** — each cycle is its own stratum, so density is held constant *by construction*, not by stratification. A cycle has exactly one density; `n_local` cannot proxy it. |
| unpopulated stratum (S.1r) | **global quantile cuts** on separation (HK-021(b)+(g)), never absolute Hz. Populated by construction. |
| SNR composition | SNR standardised on **X1/X2's pinned L1 edges** `[−15, −10, −5, 2]`, not re-derived (HK-021(g)). |
| band-edge artefact | S.1r's correction carried forward verbatim (§3.3). |

---

## 2. Design

**Population.** The 20m weekend corpus, `artefacts/20260808_live_run_0016-808{0,1}/`, `REF = A∩B`
through the shared T1 loader — the same basis as T1/T2/H1/P1/P2/P3/X1. `REF` must reproduce
**69 222** exactly (ROW 0c).

**Outcome.** For each `REF` decode: `missed` = OpenWSFZ did not produce it (T1's matching, unchanged).

**Exposure.** `sep` = Hz to the **nearest other `REF` decode in the same cycle**.

🔴 **Neighbours are drawn from the REFERENCE's decode list, never from ours.** Using our own output
would be circular — we cannot see the neighbours we missed. Stated as a limitation, not solved:
`REF` is itself incomplete, so `sep` is an **upper bound** on true separation. Per the standing
LEVEL-vs-CONTRAST rule this biases the *level*; and per HK-021(h) error in a **stratifier**
attenuates a contrast **toward zero** ⇒ **quote the effect as "at least X", never de-attenuated.**

**Estimator — within-cycle, and this is the whole design.**

For each cycle *c* and each SNR stratum *s*, compute the miss-rate difference between the closest
and farthest separation groups **using only decodes in that cycle and stratum**; then pool those
within-cycle contrasts across all cycles, weighted by minority-side support.

```
E_sep = pooled_over(c,s) [ missrate(sep in Q1 | c,s) - missrate(sep in Q5 | c,s) ]
```

**Cuts.** `sep` quintiles computed **globally** over the pooled corpus, then applied within cycle.
Contrast is **Q1 (closest) vs Q5 (farthest)**.
⚠️ **HK-021(f) first:** `sep` is integer Hz. **Count its distinct values before binning** and record
the count. If fewer than ~50 distinct values survive in the analysed population, quintiles are not
appropriate and the arm stops for re-registration rather than binning a near-discrete variable.

**Support.** A (cycle, stratum) cell contributes only if it carries ≥ 1 decode in **both** Q1 and Q5.
Report the fraction of cycles contributing (S.1b measured 97.7%/100% at a coarser cut).

**Uncertainty.** Primary: **cycle-clustered** bootstrap, 1 000 draws, seed `20260810` — the cycle is
the estimator's natural unit. Robustness: **frequency-clustered** bootstrap reported alongside,
because a station's frequency is near-fixed (T2a's design effect of 3.5–4.2×). **If the two disagree
in sign, or by more than 2× in SE, flag it and do not read the row** — that is an unresolved
dependence structure, not a result.

---

## 3. ROW 0 — void conditions, in strict order

| row | check | bar | consequence |
|---|---|---|---|
| **0a** | `REF` reproduces | == 69 222 exactly | VOID |
| **0b** | 🔴 **the mandatory null** — within-cycle frequency permutation, 20 shuffles | \|mean `E_sep`\| ≤ **2.0 pp** under the null | **VOID.** Bar unchanged from S.1/S.1b and **re-registered as-is; it is NOT loosened to accommodate a redesign** |
| **0c** | 🔴 **the construction check** — mean `n_cycle` gap between Q1 and Q5 cells | == **0.00**, exactly | **VOID** — a non-zero gap proves the implementation is not doing within-cycle contrasts, which is the single defect that killed S.1 |
| **0d** | separation is bin-able | ≥ 50 distinct `sep` values in the analysed population | STOP for re-registration (HK-021(f)) |
| **0e** | strata populated | every (Q1, Q5) × SNR-stratum group ≥ 300 decodes **and** ≥ 150 contributing cycles | that stratum is **UNDERPOWERED** — an instrument failure, **never a null** |
| **0f** | power | `SE(E_sep)` ≤ **2.0 pp**, cycle-clustered | **UNDERPOWERED**, no row read |
| **0g** | band-edge exclusion applied (§3.3) | exactly the documented count removed | VOID |

**ROW 0b and ROW 0c are the two that killed the previous attempts, and ROW 0c is new.** It is a hard
mechanical assertion with a single permitted value, per HK-021's "draft it by writing the code that
evaluates it."

### 3.3 Band-edge exclusion — S.1r's correction, carried forward verbatim

Decodes outside `[200, 3000)` Hz are **100% missed by construction** (`ft8_shim.c:1181`, the
hardcoded `monitor_config_t` band). They are **excluded from the outcome tally** but **retained as
candidate neighbours** for other decodes' `sep` — they are real signals genuinely on the air. A
signal at the edge of the searched band is "clear" on one side only because there is no spectrum
left to have a neighbour, which is an artefact and not evidence about locality. S.1r removed exactly
**50** such records (47 below 200 Hz, 3 above 3000 Hz) across its five runs, matching an independent
count. **Report the number removed here; it is a cross-check, not a formality.**

⚠️ **Interaction with G2.** The approved passband widening (spec `…-g2-…`) changes this exclusion
for any *future* corpus. It does **not** affect X4 — these `ALL.TXT` corpora are frozen output of
the current binary. **Do not wait for G2, and do not re-run X4 against a widened build without a
fresh pre-registration.**

---

## 4. The gate

```python
if null_fails:                            return "ROW 0b"   # VOID, contaminated estimator
if n_cycle_gap != 0.00:                   return "ROW 0c"   # VOID, not a within-cycle contrast
if se_E > 2.0 or strata_unpopulated:      return "ROW 0e/0f"  # instrument failure, NOT a null
if E_sep >= 8.0 and lo > 0:               return "ROW 1"    # LOCAL limb
if abs(E_sep) < 3.0 and se_E <= 1.5:      return "ROW 2"    # DIFFUSE limb
if E_sep <= -8.0 and hi < 0:              return "ROW 3"    # reversed - unexplained
return "ROW 4"                                              # inconclusive
```

**Consequences, pre-committed before any number exists:**

- **ROW 1 (LOCAL)** ⇒ the crowding term is **pairwise co-channel contamination**. This corroborates
  X1+X2's joint sub-question directly and makes **separation of adjacent signals** the D-001 target.
  It **raises** the value of X3's sync-refinement route and revives *correctly-placed* subtraction as
  a question — 🛑 **but does not resurrect the subtract-and-resynthesise family**, which is dead on
  three builds and three reverts and must not be re-proposed on this row (§5).
- **ROW 2 (DIFFUSE)** ⇒ crowding raises the effective noise floor rather than colliding pairwise.
  **This is the expensive answer** and it demotes every adjacent-signal treatment including part of
  X3's rationale. Escalate to the Captain; do not spec a follow-up in session.
- **ROW 3 / ROW 4** ⇒ no reading. Report and stop.

### 4.1 🔴 Retirement rule — pre-committed now, and this time it is final

S.1's own ruling of 2026-07-31 §5.4 fixed *"one redesign, then the spectral-locality approach is
RETIRED."* S.1b was designed under that rule and **never ran** (the Captain parked the question on
08-04); S.1r was a different design and returned ROW 4. **X4 is attempt three, and it is the last.**

> **If X4 voids at ROW 0b or ROW 0c, or reads ROW 4, spectral locality is RETIRED PERMANENTLY.** The
> question "is the crowding penalty pairwise-local or diffuse?" then goes to the Captain as **not
> answerable from `ALL.TXT` by any method**, and the D-001 route is decided without it. **No fourth
> design. No better metric on the same data** — HK-021's standing bar: a better metric earns a new
> pre-registration on new evidence, never a re-read.

Written while I do not know the answer, which is the only time it is worth anything.

---

## 5. Standing bars this arm must not cross

- 🛑 **Subtract-and-resynthesise stays DEAD** regardless of row — three builds, three reverts
  (`20260007` −4.30 pp; H3 CP-FSK `20260008`; H3b GFSK quadrature `20260009` at **−17 pp**), plus two
  production `0xC0000005` crashes. ROW 1 makes the *question* live again; it does not make that
  *implementation* live.
- 🛑 The shipped waterfall-domain suppression (`suppress_candidate_tiles`, pass 1) is **not** in
  scope. Verified 2026-08-10 by code read: it fires at the top of pass 1, **after pass 0 has already
  committed its decodes**, so it cannot cost a pass-0 decode; its entire blast radius is bounded by
  pass 1's contribution, which RC4 measured at 0.80%. **Do not propose it as the crowding mechanism.**
- 🛑 **No `src/` recommendation, no parameter sizing, no capture run, in any row.**
- ⚠️ Basis discipline (X2 §8): T1 basis, `<...>`-bearing messages excluded, 200–3000 Hz. **Never mix
  with the H1a-corrected ≈57.8% figure**, which used wildcard matching over a different population.

## 6. Architect predictions, recorded blind

Calibration to quote: **categorical 5/7, ranges 7/10, DIRECTIONAL/SHAPE 0/2 — ranges symmetric and
wide.**

| # | prediction | type |
|---|---|---|
| 1 | ROW 1 (LOCAL) | categorical |
| 2 | `E_sep` ∈ **[5, 25] pp** — deliberately wide; I have no basis for precision here | magnitude |
| 3 | ROW 0b (the null) **passes** under the within-cycle estimator, \|bias\| < 1.0 pp | magnitude |
| 4 | ROW 0c returns exactly 0.00 | mechanical |
| 5 | ≥ 90% of cycles contribute at least one (Q1, Q5) pair | magnitude |

I expect ROW 1. **ROW 2's bar is set so it can fire cleanly against me**, and ROW 2 is the answer
that would cost the programme the most — which is exactly why it must be reachable.

---

## 7. Boundaries

- **No `src/`, no rebuild** (HK-011). **No push, no merge** (HK-014/HK-010).
- Per HK-015 this is Architect → QA.
- **NFR-021:** counts, rates, frequencies and cycle timestamps only. Message text may be read to
  build match keys, as every analysis in this directory does; **no callsign or message text appears
  in `x4_result.json` or the report.**
- Determinism required: two runs, byte-identical stdout. Output `x4_result.json`.
