# Revisit R&R-009 — the S5 false-positive gate's population, sizing, and threshold

**From:** Architect
**For:** QA (execution), and the Captain (the population ruling and threshold ratification in §8)
**Date:** 2026-09-06 19:41 UTC
**Concerns:** `STUDY-SPEC.md` §10 (R&R-004 gate), §"S5 default-battery part restriction" (R&R-009),
`scenarios/s5-noise.json`, `harness/analyse.py`'s FP verdict path, and Section 6's `S5 FP` column.

**Trigger:** the PO, reviewing the 2026-09-06 sweep (`4c7d5ad`, S5 FAIL at 3/60), asked why S7 jumped
at 2026-08-30/31 while an FP increase persisted, then asked whether **R&R-009** should be revisited
instead — and, finally, whether both candidate designs could be tested "to see what delivers the most
progress."

---

## §0 — The PO's last question, and the one form of it that must be refused

The question was: *can we test both options to see what delivers the most progress?*

**Two readings, and they must not be conflated.**

✅ **Measuring both is free and is specified below.** Parts 0/1 are a *subset* of the 4-part battery,
so a single 4-part run yields the mixed-population rate **and** the AWGN-only sub-rate from the same
slots. No second run, no extra bench time. §4 goes further and compares the candidate designs as
**instruments**, which is pure arithmetic and needs no runs at all.

🛑 **Selecting which population gates, on the basis of which one produces more PASSes, is refused.**
That is **HK-021 sibling (y)** — a criterion chosen by inspecting the outcome it will be scored on —
applied to a gate definition rather than to a change point. The gate is the pre-registered standard
the sweeps are judged against; picking it for its verdicts destroys the thing that makes a PASS mean
anything, in exactly the way that produced the retired `4.88×` figure.

🔴 **And "progress" needs guarding.** A gate that passes more often is not progress. The FP rate
falling, or coverage rising, is progress. Of the three defects in §1, **not one is fixed by any
choice of gate** — §7 states plainly what this document does not change.

⚠️ **Disclosure, because it is already too late for blinding.** In answering the PO earlier today I
computed and showed what the last three sweeps read under the reverted design (FAIL / PASS / FAIL,
§1.1). The comparison is therefore **unblinded**, which is one more reason the population must be
settled on grounds (§8), not on verdicts.

---

## §1 — What is actually wrong with R&R-009

R&R-009 (implemented 2026-08-23, effective from the 2026-08-27 sweep) restricted S5's default battery
to parts 0/1, taking the §10 denominator from **N=120 to N=60**. Its finding — that parts 2/3
produced 1 of 53 all-time FP events — is correct and is not disputed here. Three consequences were
not carried through.

### 1.1 It broke the ratified gate's stated precondition, and reverted R&R-006

R&R-004's ratification text does not merely set 6%. It names the sample size and writes out the
tolerance as part of the definition:

> *"at the study's N (**120 signal-free slots** — 4 parts × 30 trials)… At N = 120 this tolerates
> **≤ 2 FP events** (k = 2 → UB 5.15% PASS; k = 3 → UB 6.33% FAIL)."*

Both worked examples reproduce exactly. **At N=60 the tolerance is zero** — one false positive in 60
slots fails a gate labelled 6%:

| k / 60 | 95% UB | | k / 120 | 95% UB |
|---|---|---|---|---|
| **0** | **4.87% PASS** | | 0–2 | 2.47 / 3.89 / **5.15% PASS** |
| 1 | 7.66% FAIL | | 3 | 6.33% FAIL |
| 2 | 10.12% FAIL | | 4 | 7.47% FAIL |

This is the **second** time this scenario has been out of sync with its own gate. R&R-006
(GitHub #39, 2026-07-04) found `s5-noise.json` sized at 12 slots against a gate needing 120, raised
`trials` 3→30 *explicitly* "rather than inventing a new, undocumented sample size", and booked the
cost as *"accepted as the cost of the routine suite ever producing a real S5 verdict at all."*
**R&R-009 undid that sizing seven weeks later on the runtime argument R&R-006 had already heard and
rejected, without re-ratifying the threshold it was a precondition of.**

Consequence, stated before the design discussion so it cannot be mistaken for a benefit: reverting
would have made the last three sweeps read **FAIL (4/120, 7.47%) / PASS (2/120, 5.15%) /
FAIL (3/120, 6.33%)**. Two of three still fail.

### 1.2 It removed coverage of a distinct failure mode — and the justification violates HK-026

Parts 2 (steady carrier) and 3 (birdies) exercise hallucination on **narrowband interference**, a
different failure mode from parts 0/1's AWGN CRC-14 false accepts. Their near-zero event history was
read as "not earning their runtime." But **a control that never fires is passing, not idle.**

🔴 **The inference is HK-026 exactly:** parts 2/3's flat, zero-event output was used to bound parts
2/3's own future usefulness. An instrument reading zero on healthy code tells you nothing about
whether it would read non-zero on a regression — that is the definition of a flat response being
used to bound its own blind spot. The routine battery can no longer detect a birdie-hallucination
regression at all, and no amount of the data that motivated R&R-009 could have shown otherwise.

### 1.3 It redefined the metric without relabelling it

§10's quantity is *P(a signal-free slot emits ≥1 false decode)* across a representative interference
mix. R&R-009 narrowed it to an AWGN-only quantity on a **~2× different scale**, keeping the name and
the threshold. `STUDY-SPEC.md` already records the arithmetic: both eras contain **60 AWGN slots**;
pre-R&R-009 gated on 120 slots of which 60 were "denominator with no numerator." This is the
denominator-redesign trap in **HK-031**, and it is why the apparent post-08-30 FP step dissolves
under normalisation (§2).

---

## §2 — The corrected FP series, normalised per AWGN slot

Event counts taken from **each run's own gate line / confusion matrix**, never Section 6's `S5 FP`
column (HK-031: that column mixes rates and 95% UBs). Every run carries 60 AWGN slots.

| Date | SHA | FP events / 60 AWGN slots | Era |
|---|---|---|---|
| 08-15 | `8d6e1b1` | 1 | N=120 |
| 08-21 | `7d36038` | 1 | N=120 |
| **08-22** | **`f5dec23`** | **4** | N=120 |
| 08-27 | `22b749c` | 0 | N=60 |
| 08-29 | `872ba65` | 1 | N=60 |
| 08-30 | `2e60949` | 2 | N=120 (resume artefact) |
| 09-02 | `3b52608` | 4 | N=60 |
| 09-03 | `35378b9` | 2 | N=60 |
| 09-06 | `4c7d5ad` | 3 | N=60 |

**Pooled 18/540 = 3.33% per AWGN slot.** Dispersion **χ² = 8.00, df = 8, p = 0.43** — a near-textbook
fit to a single constant rate. Trend across all nine runs ρ = 0.479, **p = 0.19**.

**Split provenance, declared per HK-021(y):** the 2026-08-30/31 boundary is **mechanism-derived** —
the introduction of the capped/batched harness, dated from the S7 re-run — not chosen by inspecting
the FP series. Across it: pre 9/360 = 2.50%, post 9/180 = 5.00%, **Fisher one-sided p = 0.10**.

🔴 **The "FP increase carried along since 08-30" is not established once normalised.** `f5dec23`
recorded 4 events on 08-22, equalling the worst post-cap sweep, weeks before the S7 event. Most of
the apparent step is R&R-009 landing three days earlier and making an unchanged propensity read ~2×
higher.

🛑 **This is not an all-clear.** Power to detect a true doubling (2.5%→5.0%) at this sample size is
**35.6%**. "Not established" is not "ruled out," and must not be reported as "no effect"
(HK-021(y) corollary).

---

## §3 — Two figures I issued earlier today, corrected before they travel

1. 🛑 **WITHDRAWN — "the S5 gate is mis-specified at N=60."** The threshold was never mis-specified.
   The *battery* drifted out from under a threshold that was ratified against N=120 (§1.1). The
   defect is mis-application, not mis-specification, and the remedy is correspondingly different.

2. 🛑 **DOWNGRADED — the S7/S5 coupling, `ρ = 0.737, p = 0.037` (n=8).** Paired with
   leave-one-unit-out as HK-021(y) requires, it **loses significance on seven of eight runs**
   (worst: dropping `3b52608` → p = 0.129). **The significance claim is unavailable and may not be
   cited.** What survives is direction only — ρ stays positive and stable, 0.63–0.82, in every
   leave-one-out. The coupling is a **hypothesis worth a designed test**, and was reported to the PO
   with a firmer p-value than it can carry.

---

## §4 — The legitimate "test both": the designs compared as instruments

No bench time. `P(FAIL)` as a function of the true per-AWGN-slot FP rate — only AWGN slots can emit
events, so exposure is the AWGN count, while the *gate* is evaluated on the full denominator N.

| Design | AWGN slots | N | tol | 0.5% | 1% | 2% | **3.33%** | 5% | Runtime |
|---|---|---|---|---|---|---|---|---|---|
| **A** revert R&R-009 (4 parts) | 60 | 120 | 2 | 0.00 | 0.02 | 0.12 | **0.32** | 0.58 | ~30 min |
| **B** today (R&R-009, 2 parts) | 60 | 60 | 0 | 0.26 | 0.45 | 0.70 | **0.87** | 0.95 | ~15 min |
| **D** parts 0/1 × 60 trials | 120 | 120 | 2 | 0.02 | 0.12 | 0.43 | **0.77** | 0.94 | ~30 min |
| **E** hybrid 0/1×60 + 2/3×30 | 120 | 180 | 5 | 0.00 | 0.00 | 0.03 | **0.21** | 0.56 | ~45 min |

`tol` = maximum events that still PASS the ratified UB ≤ 6% gate at that N.

**What this shows, and none of it is about which design passes more:**

- 🔴 **B (today) has the worst false-alarm behaviour of all four: it fails 26% of the time against a
  near-perfect 0.5% decoder,** and 45% at 1%. Most of its FAILs carry little information. This is the
  quantitative form of "at N=60 only zero passes."
- 🔴 **Inert slots cost detection power, not just labelling accuracy.** A and D cost the same 30
  minutes and have the same gate arithmetic, yet A reaches **0.32** power at the current rate against
  D's **0.77** — the difference is 60 slots that cannot emit events but do loosen the tolerance.
  **E makes it worse still (0.21) despite costing the most**, because 60 more inert slots raise `tol`
  from 2 to 5. Dilution is not free.
- ✅ **D dominates A and B on every column at or below A's runtime.**

⚠️ **This table ranks the designs as *gates*. It says nothing about coverage** — D and B are blind
to the parts 2/3 failure mode, and per §1.2 no existing data can price that blindness.

---

## §5 — Recommended design: one gate per failure mode, each with its own denominator

The original fault is a **single gate spanning two failure modes with different base rates.** That is
what forces the choice between sensitivity and coverage, and the choice is unnecessary.

**Recommendation:**

1. **Gate the AWGN false-accept rate on AWGN slots only** — parts 0/1 at 60 trials each
   (120 AWGN slots, `tol` 2 under the unchanged 6% threshold). Design D. Best power available at
   this runtime, and no inert slots in the denominator.
2. **Restore parts 2/3 to the battery as a separate, independently reported narrowband-hallucination
   check with its own denominator** — not folded into the AWGN gate's denominator, which is what cost
   power in A and E. Trials may be trimmed for cost; its job is coverage, not precision.
3. **Report both, gate them separately, and never pool them into one rate again.**

This keeps R&R-009's correct insight (parts 2/3 do not belong in the AWGN gate's denominator), repairs
what it broke (coverage, and an N its threshold was never ratified for), and needs no new threshold —
6% still applies, to a population it now actually describes.

---

## §6 — What QA is asked to do

**Nothing until the Captain rules on §8.** When ratified:

1. `scenarios/s5-noise.json` — restore parts 2/3 to the default battery; set parts 0/1 trials per the
   ratified design.
2. `harness/analyse.py` — emit the AWGN-only gated verdict and the parts 2/3 coverage check as
   **two separate rows** with their own denominators; keep `MIN_N_FOR_FP_GATE` semantics intact.
3. `STUDY-SPEC.md` — amend §10 and the R&R-009 section to record this revision and its rationale.
4. **Section 6 footnote** — the `S5 FP` column spans **three** denominators (N=120 4-part, N=60
   2-part, and the new design). It needs the same class of footnote the table already carries for the
   S1/S3 redesigns. Cross-era rate comparisons must be normalised per AWGN slot first.
5. Re-verify §2's event counts independently from each run's gate line before the series is cited.

✅ **No `src/` or `native/` involvement** — scenario config, harness analysis, and specs only.
**HK-011 is not engaged**; QA verifies with `git diff --stat -- src/ native/` and says so.

---

## §7 — What this does NOT do

- 🛑 **It does not lower the false-positive rate.** No gate redesign changes decoder behaviour.
- 🛑 **It does not reopen `FP-PARITY` P4b.** ROW 3 fires, `F − T = 5.378 dB` against the 6.0 dB bar,
  **PARKED — not closed**, no dev-task. Nothing here softens that.
- 🛑 **It does not make the board green.** Under every candidate design, recent sweeps still fail
  (§1.1). WSJT-X's 0 events across seventeen sweeps against OpenWSFZ's ~3.3% per AWGN slot is a real,
  unexplained gap and remains the substantive open question.
- 🛑 **It does not license the S7 jump as progress.** `82.79%` stays out-of-family high for
  instrument reasons (2026-08-31 ruling); the suspended S7 gap figures stay suspended.

---

## §8 — Decisions for the Captain

1. 🔴 **The population question — to be settled on grounds, not verdicts (§0).** Should the S5 gate
   measure *AWGN false-accept sensitivity* (recommended, §5) or *operational false-decode risk across
   a representative interference mix*? The current state — the second population judged against the
   first's threshold — is the one option that is not defensible.
2. 🔴 **Threshold.** Under §5's recommendation, 6% carries over unchanged and needs no
   re-ratification. Any AWGN-only design at N=60 would instead require a re-derived and re-ratified
   threshold, since 6% was calibrated against the diluted denominator.
3. ⚠️ **Runtime.** ~30 min/sweep for the gate, plus parts 2/3 coverage. R&R-006 accepted ~27 min for
   this same gate's validity; R&R-009 reclaimed ~15 min of it. The trade is being made explicitly
   this time.
4. ⚠️ **Optional, separable:** the §3.2 S7/S5 coupling hypothesis. The cheap discriminator is the
   **offline replay path**, which has no playback chain at all — if FP tracks playback delivery, the
   offline rate should be flat across the window where the live rate moved. Needs no bench time. Not
   proposed for arming here; flagged so it is not lost.

---

**Architect commits locally and stops (HK-014).** Not pushed, no PR. QA may take, push, or PR this
commit at its own discretion with no discussion (PO-directed 2026-09-06); **merge still requires the
Captain's sign-off every time (HK-010).**
