# H1a results — the wildcard matches are genuine. ROW 1. The bracket is retired.

**Author:** Architect, 2026-08-08 (23:10 UTC, from `date -u`, per HK-017 — local time had rolled to
08-09; UTC governs, so filename and byline both read 08-08).
**Spec:** `2026-08-08-2156-architect-to-qa-spec-h1a-wildcard-frequency-validation.md`, **committed
`c1fe9b6` before any data was touched.**
**Harness:** `qa/cycleframer-alignment-replay/h1a_wildcard_frequency_validation.py`.
**Status:** pure re-analysis of `ALL.TXT` on disk. `qa/artefact_inventory.py --check` ran clean before
starting. No `src/` change, no capture, no rebuild. NFR-021: counts, rates and frequency statistics
only — no message text or callsign appears in this document or in the harness's output.

🔴 **Role caveat, stated because it matters and not because it changes the result.** The Captain
directed the Architect to execute this one. **I wrote the gate and recorded ROW 1 as my prediction, so
the QA/Architect independence HK-021 leans on is absent here.** What survives is the safeguard HK-021
itself names as the one that actually works: **the spec, its gate code and the prediction were
committed at `c1fe9b6` before the harness existed** — anyone can diff prediction against outcome. The
gate was run verbatim; the one thing added beyond spec (§2.2b) is a *stricter* null that makes the
result harder to reach, not easier, and it is reported separately and not gated on.

---

## 1. Bottom line

**`V = 0.9968` (1 558 of 1 563) → ROW 1.** The wildcard matches are genuine.
**`R_wild` is promoted from an upper bound to an estimate, and the `[55.5%, 57.8%]` bracket is
retired: 20m recovery is `≈ 57.8%`.**

The discriminator turned out to be close to perfect. **Not one of 1 563 randomly re-paired rows landed
within tolerance** (`V_null = 0.0000`), and under a stricter, token-compatible null it was 1 in 1 520.

## 2. Gate trace (ordered, from the harness)

```
0a: 1500 <= n_gained(1563) <= 1620    PASS   -- reproduces H1's 1 563 exactly
0b: V_null(0.0000) <= 0.10            PASS
0c: V(0.9968) >= V_null(0.0000)       PASS
>>> ROW 0 CLEAR <<<
V = 0.9968  vs  ROW 1 bar 0.95
>>> ROW 1 <<<
```

## 3. The `Δf` distribution — cleaner than the gate required

| `Δf` (Hz) | n | share |
|---:|---:|---:|
| 0 | 541 | 34.6% |
| 1 | 876 | 56.0% |
| 2 | 138 | 8.8% |
| 3 | 3 | 0.2% |
| 4–20 | **0** | **0.0%** |
| > 20 | 5 | 0.3% |

**The population is bimodal with an empty gap**: 1 558 rows inside 3 Hz, **nothing at all** between
4 and 20 Hz, and 5 outliers beyond 20. That is the signature of a genuine population plus a handful of
truly spurious pairs — not a continuum with an arbitrary cut. Had the tolerance been set anywhere from
3 Hz to 20 Hz, `V` would be identical, so **the result does not depend on the tolerance choice at all.**

The 5 outliers are 0.32% of the gained set and are consistent with the spurious mechanism the spec
predicted a priori (§0.1: `CQ <...> <grid>` with two same-grid stations in one cycle) — the mechanism
was right, it is just rarer than I expected.

### 3.1 🔴 An unplanned cross-validation that I did not design for, and it is the strongest evidence here

Mean `|Δf|` over the 1 558 validated pairs = **0.7452 Hz**.
T1's independently measured `mean_r` — the reference frequency's distance to the nearest 3.125 Hz
lattice point, computed on a different population by a different harness — = **0.7367**.

**They agree to 0.0085 Hz.**

These are the same physical quantity reached two different ways, and the agreement establishes three
things at once:

1. **Our decoder reports the *nearest* lattice point**, not merely *a* lattice point — which no
   previous measurement had actually shown.
2. **The wildcard matches are genuine**, because a population containing meaningful numbers of
   spurious pairs could not reproduce T1's residual mean to eight thousandths of a hertz.
3. T1's instrument control and H1a's validation are measuring one consistent physical system.

This was not a check the spec asked for. It fell out of the histogram, and it is a bound that ran
against my own prediction and passed (HK-021(e)).

## 4. The corrected figures

| quantity | value |
|---|---:|
| `R_base` | 55.53% |
| `R_wild` | 57.79% |
| **`R_wild_val`** (validated pairs only) | **57.78%** |

The correction is **0.01 pp** — two orders of magnitude below anything anyone quotes this figure to.
**Recovery on the 20m leg is `≈ 57.8%`.**

## 5. §4 deliverable — the FP level's previously unstated uncertainty

Recomputed from source, reproducing H1's classes exactly:

| | value |
|---|---:|
| implausible | 1 813 |
| denominator `\|A∪B\|` | 42 722 |
| silently excluded (280 = 86 corroborated + 194 single-only) | 280 |
| **`F_lo`** — all 280 legitimate (as published) | **4.24%** |
| **`F_hi`** — all 280 fabricated | **4.90%** |
| `F_mid` — class-rate weighted (**an estimate, not a measurement**) | 4.68% |

Class implausibility rates used for the weighting: corroborated **0.133**, single-only **0.909** —
each class's own measured rate, so the midpoint is not an invented parameter. Expected fabricated
count among the 280 = **187.8**.

**The FP level is `4.24–4.90%`, best estimate ≈ 4.7%.** 🛑 **This does not revise Gate B** — that
gated `ΔF`, a *difference*, and is untouched. This is the *level*, a different quantity.

## 6. Predictions scored (spec §5)

| # | prediction | outcome | scored |
|---|---|---|---|
| 1 | `n_gained` = 1 563 | 1 563 | ✅ hit |
| 2 | `V_null` < 0.03 | 0.0000 | ✅ hit |
| 3 | `V` = 0.95–0.99 ⇒ **ROW 1** | 0.9968 ⇒ ROW 1 | ⚠️ **categorical HIT, range MISS** — 0.9968 sits above my own upper bound |
| 4 | `Δf` spiked 0–2 Hz with a thin **flat tail** | spiked (99.4% in 0–2) but the tail is **empty then 5 outliers**, not flat | ⚠️ **partial** — shape better than predicted |
| 5 | class-weighted FP midpoint ≈ 4.7% | 4.68% | ✅ hit |

**Updated calibration.** Categorical ROW calls now **2 of 4** (T1 miss, H1-A hit, H1-B miss, H1a hit).
Ranges **3 of 5**. ⚠️ **A pattern worth naming: both range misses (#3 here, `ΔF` in H1) are in the
direction of my ranges being too PESSIMISTIC about how cleanly an effect separates.** I under-predict
discriminator quality. That is the opposite failure from the one HK-021 was written for — but it is
still a mis-calibration, and it means my ranges should not be read as symmetric.

## 7. Consequences of ROW 1 — applied

Per the spec's §3 consequence column, which makes these **required, not optional**:

- ✅ **The bracket is retired.** 20m recovery is `≈ 57.8%`, not `[55.5%, 57.8%]`.
- ✅ **H1 §8's citation limit on `R_wild` is SUPERSEDED and has been edited, not merely annotated** —
  `R_wild` may now be cited without the ambiguity fraction attached.
- ✅ 1942 report §8, H1 §8 and `BOARD.md` updated in the same edit (HK-024).

### 7.1 🔴 One thing the spec's consequence got wrong, and I am not executing it blindly

The spec said to restate the **"~55–64% three-estimate band"** accordingly. **Doing that literally
would be an error, and I am flagging it rather than performing it.**

That band pools three numbers: 20m **55.5%**, 17m **62.6–63.7%**, and the 08-06 replay **59.6%**.
**Only the 20m figure has been corrected for `<...>`.** The other two were measured the same way, on
the same exact-match basis, and are therefore depressed by the same mechanism — by an unknown amount.
Restating only the 20m member would produce a band that silently **mixes corrected and uncorrected
estimates**, which is worse than leaving it alone.

> **The band stays as published, with a new warning attached: its 20m member is now known to be
> ~2.3 pp low on an uncorrected basis, and the other two members have not been checked.** Correcting
> them is a separate piece of work, not authorised here. **Do not compare a corrected figure against
> an uncorrected one.**

## 8. Citation limits

**May be cited:** `V = 0.9968`, `V_null = 0.0000`, the stricter null 1/1 520, seed `20260808`; the
`Δf` histogram and its empty 4–20 Hz gap; **20m recovery `≈ 57.8%`** (`R_wild_val` 57.78%); the §3.1
cross-validation (0.7452 vs T1's 0.7367); `F_lo`/`F_hi` = **4.24–4.90%** as bounds on the FP level.

🛑 **May not be cited:** `F_mid` = 4.68% as a measurement — it is a class-rate-weighted **estimate**
and must be labelled as one; any claim that §5 revises Gate B; **the "~55–64% band" as if uniformly
corrected** (§7.1); any restatement of `M`, `ΔF`, T1's `G`, or T2's metrics; the hash table as an
*approved* treatment — it remains a recommendation with a number, pending the Captain (HK-011).
