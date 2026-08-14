# Architect → QA: spec H1a — validate the wildcard matches by frequency, and retire the bracket if they hold

**Author:** Architect, 2026-08-08 (21:56 UTC, from `date -u`, per HK-017). Repo `main` at `c0af3fb`.
**Addendum to:** `2026-08-08-2121-…-spec-h1-hash-token-contamination.md` and its result
`2026-08-08-2135-qa-to-architect-h1-hash-token-contamination-results.md` (A-ROW 1, `M = 2.26 pp`).
**Status:** pure re-analysis of `ALL.TXT` already on disk, 20m leg, same window and population as H1.
No `src/` change, no capture, no rebuild, no Developer session. ~10 min. NFR-021: counts, rates and
frequency statistics only — **no message text, no callsign, in output or in the harness.**

---

## 0. Why this is worth ten minutes now rather than never

H1 fired A-ROW 1 and its consequence is already propagating: **`[55.5%, 57.8%]` is now the mandated
form of the recovery figure** in the 1942 report §8 and on the board, and it will be carried into
every downstream citation from here on. A bracket is the right call given what H1 measured — but
`R_wild` was only ever declared an *upper* bound because **a wildcard match is a claim that cannot be
verified from text alone.**

**It can be verified from frequency.** Every wildcard-gained pair carries a reported frequency on
both sides, and H1 already loads both. If the matches are genuine, the bracket is spurious precision
and should be retired before it hardens into a dozen documents.

### 0.1 This tests a different failure mode than H1's ambiguity count

H1 reported `n_ambiguous / n_wild_gained = 0.5%`. That measures how often a `<...>` row had **two or
more** candidate reference rows. **It says nothing about whether the single candidate was the right
one.** Those are different failures, and only the second one biases `R_wild`.

The realistic spurious case is concrete and not exotic: a message of the form `CQ <...> <grid>`, where
**two stations sharing a grid square both call CQ in the same cycle.** One candidate, wrong partner,
counted as unambiguous.

### 0.2 Why frequency discriminates cleanly, with the tolerance derived rather than chosen

Our reported frequency is **on the 3.125 Hz lattice** (H1/T1: `mean_r_ours` ≈ 0.24, the closed-form
value for an on-grid quantity rounded to integer Hz is 0.250). The reference is refined and reported
to integer Hz. So for a **genuine** pair the worst case is

```
1.5625 (our max lattice offset)  +  0.5 (our rounding)  +  0.5 (reference rounding)  =  2.5625 Hz
```

⇒ **tolerance `|Δf| ≤ 3 Hz`, supplied by the lattice, not picked by me** (HK-021(d)). For a
**spurious** pair the partner is some other signal in the same cycle, scattered across the
200–3000 Hz passband — landing inside ±3 Hz by chance is a sub-percent event.

🛑 **But do not take that last sentence on trust — §2.2 measures the null from the data.**

---

## 1. Scope

**In scope:** the **1 563 wildcard-gained pairs** from H1, 20m leg, same window
(`260808_004000`..`260808_111500`), same sources (`artefacts/20260808_live_run_0016-808{0,1}/`).

🛑 **1.1 Do not recompute `M`, `R_base`, `R_excl`, `ΔF`, or re-read either H1 gate.** H1 is closed at
A-ROW 1 / B-ROW 2. H1a validates one input to `R_wild`; it does not revisit the result.

🛑 **1.2 Frequency from the reference is WSJT-X FT991A's**, consistently, exactly as H1 and T1 did.
T1 showed the instance choice is not load-bearing (`G` 3.16 vs 3.13); do not re-litigate it.

🛑 **1.3 No time axis.** Reference DT resolution is 0.1 s, coarser than our 0.08 s step — not
identifiable (HK-021(c)). `Δf` only.

🛑 **1.4 17m out of scope**, as in H1.

---

## 2. What to compute

### 2.1 The validation fraction

For each of the `n_wild_gained` pairs, `Δf = |f_ours − f_ref|` (both integer Hz, field `[6]`).

```
V = fraction of gained pairs with |Δf| <= 3
```

Report the **`Δf` histogram at 1 Hz resolution, 0..20 Hz plus an overflow bin.** A genuine population
should show a sharp spike in 0–3 Hz and a flat, thin tail; the shape is more informative than `V`
alone and is the thing to eyeball if anything looks wrong.

### 2.2 The null — measured, not assumed 🔴 this is the part that makes `V` readable

**Within-cycle permutation.** For each gained reference row, draw a *different* OpenWSFZ 8080 row
**from the same cycle** (excluding its own wildcard partner) and compute `Δf` the same way. Repeat
over the whole gained set to get

```
V_null = fraction of permuted pairs with |Δf| <= 3
```

**This is the spurious-match rate the corpus itself produces**, at that corpus's real density and its
real passband occupancy. It is not a number I invented, and it is the denominator of the whole
argument: `V` means nothing unless `V_null` is small.

Use a fixed random seed and record it, so the run reproduces.

### 2.3 The corrected upper end

```
R_wild_val = 100 * (n_exact_matched + n_gained_within_tolerance) / n_ref_pop
```

Report it under **every** row, including ROW 1 — it is the number the bracket's upper end becomes if
the correction turns out to matter.

---

## 3. Pre-registered gate (HK-021)

Rows mutually exclusive, strict order, boundaries explicit, **ROW 0 first**.

```python
def h1a_row0(n_gained, v, v_null):
    if not (1500 <= n_gained <= 1620):
        return "ROW 0a"   # did not reproduce H1's gained population (1 563) -- wrong window/sources
    if v_null > 0.10:
        return "ROW 0b"   # the discriminator has no power on this corpus: V is unreadable
    if v < v_null:
        return "ROW 0c"   # genuine pairs match worse than random ones -- instrument failure
    return None

def h1a_gate(v):
    if v >= 0.95:
        return "ROW 1"
    if v <= 0.75:
        return "ROW 2"
    return "ROW 3"
```

### Consequences, as assertions

| row | consequence |
|---|---|
| **ROW 0a–0c** | **Instrument failure, not a null.** Report the failing check and its value. **The bracket `[55.5%, 57.8%]` STANDS UNCHANGED** — H1's citation limits remain exactly as published. Draw no conclusion about match validity. |
| **ROW 1** (`V ≥ 0.95`) | **The wildcard matches are genuine and `R_wild` is promoted from an upper bound to an estimate.** 🔴 **Retire the bracket:** the recovery figure becomes **`≈ 57.8%`** (state `R_wild_val` and `V` beside it), and the 1942 report §8, the board, and the "~55–64% three-estimate band" are all restated accordingly **in the same edit** (HK-024). The residual spurious share is ≤ 5% of 1 563 ⇒ ≤ **0.11 pp**, below the precision anyone quotes this figure to. `R_wild` may then be cited without the ambiguity fraction attached — H1's §8 limit on that point is **superseded**, and must be edited rather than left to contradict. |
| **ROW 2** (`V ≤ 0.75`) | **A material share of wildcard matches are spurious**, so `R_wild` is not merely an upper bound but a **biased** one. **Replace the bracket's upper end with `R_wild_val`** and keep it a bracket. Assert into the board that `R_wild` as published (57.79%) **overstates** and must not be cited bare. |
| **ROW 3** (`0.75 < V < 0.95`) | **Bracket stands**, now with `V` and `R_wild_val` attached wherever it is quoted. No promotion, no restatement of the headline. |

⚠️ **ROW 1 is the only row that deletes text from other documents.** If it fires, the edits in its
consequence column are **required**, not optional — a citation limit left in place after it has been
superseded is exactly the stale-record defect HK-024 exists to prevent.

---

## 4. Second, unrelated deliverable — close the FP uncertainty H1 left open

H1 §3.4 bounded the silent exclusion at **280 rows** but never converted it into its effect on the
headline. Those rows sit in the `|A∪B|` denominator (42 722) and contribute **zero** to the
implausible numerator (1 813), because every callsign-shaped token in them was hashed.

**Compute and report both ends:**

```
F_lo = 1813 / 42722                = 4.24%   (as published -- all 280 assumed legitimate)
F_hi = (1813 + 280) / 42722        = 4.90%   (all 280 assumed fabricated)
```

and the class-rate-weighted midpoint, using each class's own measured implausibility rate (the 194
from the novel-single-only class at its rate, the 86 from novel-corroborated at its rate).

**Then update the FP citation limit** in H1 §8 and in the 1942 report §8: the ~4% figure carries an
**upper uncertainty of about +0.66 pp** that has never been stated. ⚠️ **This does not touch Gate B**
— B-ROW 2 gated `ΔF`, a difference, and is unaffected. It touches the *level*, which is a different
quantity. **Do not describe this as revising Gate B.**

⚠️ **It does bear on D-009 Option B**, whose case rests on the FP level: the true rate is somewhere in
**4.24–4.90%**, which moves the evidence slightly *toward* Option B. Record that in the §7.3 decision
item; do not resolve it — that is the Captain's.

---

## 5. Architect's recorded predictions (HK-021)

| # | prediction | tested by |
|---|---|---|
| 1 | `n_gained` reproduces **1 563** | ROW 0a |
| 2 | `V_null` **< 0.03** | ROW 0b |
| 3 | `V` = **0.95–0.99** ⇒ **ROW 1** | the gate |
| 4 | the `Δf` histogram is **spiked in 0–2 Hz** with a thin flat tail | §2.1 |
| 5 | class-weighted FP midpoint ≈ **4.7%** | §4 |

⚠️ **Calibration note, recorded because it should temper how much weight my predictions carry.**
Across T1, T2 and H1 my **point estimates** have landed 2 of 3, but my **categorical row calls** have
landed **1 of 3** (T1: predicted ROW 1, got ROW 3; H1 Gate A: hit; H1 Gate B: predicted ROW 3/1, got
ROW 2 — off by an order of magnitude). **Prediction 3 above is a categorical call. Weight it
accordingly, and score it plainly either way.**

---

## 6. Deliverables

1. Harness `qa/cycleframer-alignment-replay/h1a_wildcard_frequency_validation.py` — **import H1's
   matcher rather than reimplementing it**, so the gained set is provably the same 1 563 rows.
2. Report `…-qa-to-architect-h1a-wildcard-frequency-validation-results.md`, filename and byline both
   from real `date -u` and in agreement (HK-017): `V`, `V_null`, the seed, the `Δf` histogram,
   `R_wild_val`, the gate trace, §4's `F_lo`/`F_hi`/midpoint, predictions scored, citation limits.
3. **If ROW 1 fires:** the §3 consequence edits to the 1942 report §8, H1 §8, and `BOARD.md` — **same
   edit** (HK-024).
4. **No push, no merge, no `src/` change** (HK-011/HK-014). Committing is the Captain's call (HK-010).

## 7. Citation limits set in advance

**May be cited:** `V`, `V_null` and the seed; the `Δf` histogram; `R_wild_val`; the gate row;
`F_lo`/`F_hi` as **bounds** on the FP level.

🛑 **May not be cited:** `R_wild` bare under ROW 2 or ROW 3; the §4 midpoint as a measurement (it is a
class-rate-weighted **estimate** — label it); any claim that §4 revises Gate B (it does not — different
quantity); any restatement of `M`, `ΔF`, T1's `G`, or T2's metrics.
