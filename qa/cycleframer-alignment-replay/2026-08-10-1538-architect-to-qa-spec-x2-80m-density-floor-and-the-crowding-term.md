# Architect → QA — spec X2: the 80m density floor, and whether crowding is a separate term

**2026-08-10 15:38Z** (filename and byline both from `date -u`, HK-017).
**Author:** Architect. **Audience:** QA (HK-015).
**Status:** execution spec for an existing QA pre-registration, plus two extensions.
**Commit this document before writing the harness.**

---

## 0. Standing on QA's own pre-registration

The governing pre-registration for this leg is **QA's**, written 2026-08-09 01:49Z before the
capture existed:
`qa/cycleframer-alignment-replay/2026-08-09-0149-qa-prereg-80m-dying-band-density-floor.md`.

🔴 **That document is not superseded and must not be rewritten to match anything.** Its ROW 0a–0e,
its §2 refusal to pre-commit density bin edges, and its §4 recorded prediction all stand. This
spec supplies what the pre-registration deliberately left open — the execution, the SNR control,
and the read logic — plus two extensions in §4 that the pre-registration does not cover.

✅ **QA's §4 prediction remains fully scorable.** It was recorded before any data existed; my
having seen the outcome (§0.1) does not retroactively de-blind QA's own call, and QA should score
it honestly on both **category** and **direction**.

### 0.1 🔴 ARCHITECT DE-BLINDING DISCLOSURE

While drafting I ran a scoping analysis of the 80m leg (HK-018). **I have seen the headline.**
Prediction-scoring by the **Architect** on the primary metric is **SUSPENDED**. What I saw:

| 80m regime | cycles | REF decodes | raw recovery |
|---|---:|---:|---:|
| floor, density ≤ 5 | 413 | 1 060 | **88.11%** |
| mid, density 6–13 | 464 | 4 308 | 78.23% |
| overlap, density 14–26 | 319 | 5 471 | 74.06% |

SNR-standardised floor-minus-overlap, cycle-clustered:
**`F_std` = +17.22 pp [+14.99, +19.38], SE 1.13.** Unstandardised: +14.05 pp.

🔴 **The SNR distributions of the two regimes are nearly identical** — floor p10/med/p90 =
−17/−5/+8, overlap = −17/−4/+10 — so **this is not SNR composition.** Per-stratum recovery at the
floor reaches **99.6%** and **100.0%** in the top two SNR strata, against 83.1% and 91.8% in the
overlap regime.

**Plainly: in an uncrowded cycle, OpenWSFZ recovers essentially every signal the reference hears.**

### 0.2 Why this is the most decision-relevant number of the weekend

The programme's current localisation is **demodulation capability** — no sync refinement,
non-coherent single-symbol extraction, `G` = 3.16 pp, `S_all` = 4.27 pp. That work is sound and is
not challenged here. But a capability deficit should be roughly **invariant to how busy the cycle
is**, once signal quality is matched. It is not. At matched SNR, the same decoder goes from ~74%
to ~88%, and to ~100% on strong signals, purely by emptying the cycle.

That is the signature of a **second, additive term: crowding.** The board has already named a
candidate mechanism for it — *"OpenWSFZ's candidate/pass budgets are **time**- not sample-bounded,
so denser cycles truncate"* (08-08 four-decoder entry). This arm is where that hypothesis either
earns a pre-registration of its own or dies.

🔴 **State the tension rather than papering over it:** budget-shaped treatments have already been
swept and produced almost nothing — **D-009 swept 45 grid points for +0.109 pp**, and **RC4
measured no effect from `K_MAX_PASSES` 2→3**. If crowding is real and binding, those nulls need an
explanation (the sweeps ran on dense corpora where a different constraint may bind; or the swept
parameters are not the binding budget). **The report must address this explicitly. A result that
cannot be reconciled with D-009 and RC4 is not yet a finding.**

---

## 1. ROW 0 — run QA's pre-registration first, verbatim

Evaluate every row of the pre-registration's §3 and record the outcome of each, in order, before
reading anything else. Facts measured while drafting, given so QA can **check** them rather than
inherit them:

| pre-reg row | what it requires | measured while drafting |
|---|---|---|
| **0a** population floor | ≥ 150 cycles post-decline | 1 196 REF cycles — **expected pass** |
| **0b** new floor reached | min density < 3, or bottom decile < 9.7 | min density **1**; 413 cycles at ≤ 5 — **expected pass, comfortably** |
| **0c** self-consistency | 8081 vs 8080 agreement ≥ 90% pre-decline | **not measured by me — genuinely open** |
| **0d** band label | ALL.TXT frequency consistent with 80m | dial `3.573` in gather metadata; **verify per-line** |
| **0e** reference validity into the tail | reference must not die first | 🔴 **FIRES.** WSJT-X's last decode is `260809_072815`; OpenWSFZ archived to `101100`. |

🔴 **ROW 0e fires and its consequence is mandatory:** every cycle after `260809_072815` has **no
reference** and therefore **no recovery figure**. Per the pre-registration's own wording that tail
is **descriptive only** — raw OpenWSFZ decode counts, flagged, not silently dropped. All recovery
analysis in this spec ends at `260809_072815`.
**Mechanical check:** the REF population is *identical* for window ends `072815` and `101100`
(no reference decodes exist between them). Assert it; a difference means the window logic is wrong.

**Additional ROW 0 conditions this spec adds:**

- **ROW 0f — reference repair.** X1's §2 repair (the 80m `wsjt-x` legs are the **same inode**;
  FT991A was gathered into both folders) must be complete, because `REF = A ∩ B`. Without it the
  80m reference is one instance. **Shared prerequisite with X1 — do it once.** Otherwise **VOID**.
- **ROW 0g — selection control (a named threat, not a formality).** `REF` conditions on *both*
  WSJT-X instances decoding a message. If that agreement is itself easier in an empty cycle, part
  of `F_std` is selection, not decoding. **Recompute `F_std` with an A-only reference.** If the two
  differ by **more than 3.0 pp**, the selection channel is material ⇒ report `F_std` as
  **confounded by reference selection** and read no row. (I have not run this check.)

---

## 2. Definitions

Reuse `t1_frequency_quantisation.load` unmodified; fields are 0-based, `[4]` SNR, `[5]` DT, `[6]`
freq Hz. Population, exclusions and the `REF = A ∩ B` key are **identical to X1** — the two arms
must be on one basis.

**Density regimes, fixed here and applied identically to every band** (they are not derived from
any band's own quantiles, so the three legs remain comparable — HK-021(g)):

- **FLOOR** = cycles with density ≤ 5
- **MID** = 6–13
- **OVERLAP** = 14–26

⚠️ This is a deliberate, disclosed departure from the pre-registration's §2 ("bin edges derived
from this leg's own quantiles at analysis time"). The reason: §4's replication legs require the
*same* regimes on 20m and 17m, and leg-derived edges would make the three incomparable — T1 §4.1's
defect exactly. The pre-registration's intent (do not gate on a central-tendency statistic; gate
on **range coverage**) is preserved in ROW 0b, which is what it was protecting.

**SNR strata:** X1's **global, pooled three-band** edges, computed once and shared. Always the
**reference's** SNR, never ours — ours carries a band-dependent gain error
(`DEFECT-snr-reported-gain-error.md`, slope 0.687 pooled, 0.563 on 80m).

**Primary metric:**

```
F_std(band) = SNR-standardised recovery(FLOOR) − SNR-standardised recovery(OVERLAP)
```

standardised over the shared global SNR strata, strata with fewer than 30 rows on either side
dropped, remaining strata equally weighted; **cycle-clustered bootstrap**, 1 000 draws, fixed seed,
resampling whole cycles (HK-021(i) — a binomial SE is forbidden).

Report `F_raw` beside it, always.

---

## 3. The gate — 80m primary

Mutually exclusive, strict order, boundary values fall to the inconclusive row.

```python
f, (lo, hi) = F_std("80m"), clustered_ci_F_std("80m")
if se_F_std("80m") > 2.0:            return "ROW 0h"   # UNDERPOWERED, instrument failure
if abs(f) >= 5.0 and not (lo <= 0 <= hi):  return "ROW 1"
if abs(f) <= 1.5:                    return "ROW 2"
return "ROW 3"
```

- **ROW 1 ⇒ crowding is a separate, first-order term in the D-001 deficit**, distinct from
  demodulation capability and not explained by signal quality. Consequences: (a) every recovery
  figure in the programme must be understood as *conditional on the density of the corpus it was
  measured on* — including the headline ≈57.8%; (b) **the time-bounded candidate/pass budget
  earns its own pre-registration**, with the D-009/RC4 nulls of §0.2 confronted head-on as part of
  the design; (c) 🛑 **no `src/` change and no parameter recommendation may be drawn from this arm**
  — it measures a phenomenon, it does not size a treatment (HK-011).
- **ROW 2 ⇒ the floor is unremarkable once SNR is matched**, recovery-vs-density is composition,
  and 🛑 the "denser cycles truncate" candidate mechanism is **dead** and may not be re-proposed
  without new evidence.
- **ROW 3 ⇒** inconclusive; report the ladder and the regimes, draw no mechanism.

**Direction is reported, never gated.** My directional calls are **0 for 2** (HK-021); the bars
above are magnitudes only.

---

## 4. Extensions — the genuinely blind part

### 4.1 Replication: is this "the 80m dying band", or is it low density generally?
Compute `F_std` **within 20m and within 17m**, same regimes, same strata, same estimator. Those
legs have their own low-density cycles (20m min density 4, 17m min 3), so the question is
answerable without new capture.

🔴 **Power check first, and it is a real risk:** both bands are thin at FLOOR. **If a band's FLOOR
regime yields fewer than 300 REF decodes or `SE(F_std) > 3.0 pp`, that leg is UNDERPOWERED and
reads as an instrument failure, not a null** — quote the SE and stop. Where FLOOR is too thin,
substitute **MID vs OVERLAP** (populated on all three bands) and say so explicitly rather than
silently.

Reading, stated in advance:
- crowding effect present on **all three** bands ⇒ it is a **decoder** property, and the strongest
  possible version of a ROW 1;
- present on **80m only** ⇒ it is entangled with the dying band, and the honest reading is that
  crowding and channel cannot be separated in this corpus.

### 4.2 Shape: threshold or gradient?
Report SNR-standardised recovery against **exact integer density** across the full range, with
clustered CIs and per-point n. A sharp knee implies a budget/cap that binds beyond a count; a
smooth gradient implies progressive contention. **Descriptive — no row turns on it**, and 🛑 do not
fit or quote a slope: the recovery-vs-density slope was **retracted** as a non-parameter on
2026-08-08 (−0.42 / −0.27 / −0.88 across windows of the same band).

### 4.3 🛑 What is barred
**S.1 (spectral locality) is CLOSED** — do not re-litigate, re-derive, or approach "are misses
concentrated near neighbouring signals in frequency" from any direction. S.1r ran and returned
ROW 4 on an unpopulated boundary; that is an instrument failure, not an invitation. **Density here
is a per-cycle count, not a spectral-neighbourhood measure, and it must stay that way.** If the
analysis starts reaching for frequency separation between decodes, stop and escalate.

---

## 5. Predictions

**Architect:** suspended on `F_std` for 80m (§0.1). Still blind, recorded for calibration:
1. ROW 0g selection control — `|F_std(A∩B) − F_std(A-only)|`: **0–2.5 pp** (i.e. I expect the
   selection channel to be immaterial, but it is a real threat and I have not measured it).
2. ROW 0c self-consistency on 80m: **≥ 95%**.
3. §4.1 — the crowding effect replicates on **at least one** of 20m/17m at MID vs OVERLAP with
   `|F_std| ≥ 2.0 pp`.

**QA:** score the pre-registration's §4 prediction on **both** category and direction, and record
the result in the report. It is one of the few genuinely pre-data predictions in the programme.

⚠️ Architect calibration, quoted because bounds appear above: categorical ROW calls 5/7, ranges
7/10, **directional 0/2**. Ranges are **symmetric and wide**; the "asymmetric / too pessimistic"
advice is falsified and deleted.

---

## 6. Citation limits

- 🔴 **Basis:** T1 basis (`A∩B`, `<...>` excluded, 200–3000 Hz). 🛑 **Not comparable** with the
  H1a-corrected **≈57.8%** 20m figure. Never mix bases in one comparison.
- 🔴 **`F_std` is conditional on the reference.** It measures recovery of what WSJT-X heard, in
  cycles where WSJT-X heard little. It is **not** a claim that OpenWSFZ decodes ~100% of signals
  present on the air.
- 🔴 The post-`072815` tail is **descriptive only** — raw counts, no recovery, never a percentage.
- ⚠️ 80m at dawn is one band, one morning, one propagation mode. Any statement about "sparse
  conditions" in general rests on §4.1's replication, not on this leg alone.
- 🛑 No `src/` recommendation, no parameter sizing, no capture-run proposal in any row.

---

## 7. Deliverables

1. `x2_density_floor.py` in `qa/cycleframer-alignment-replay/`, importing
   `t1_frequency_quantisation.load` unmodified and **sharing X1's strata code** — one basis, one
   implementation.
2. A report, HK-017 timestamps, carrying: the pre-registration's ROW 0a–0e trace **row by row**,
   this spec's ROW 0f–0h, `F_std`/`F_raw` with **clustered** CIs, the §4.1 replication with its
   power verdict, the §4.2 shape plot data, **the §0.2 reconciliation against D-009 and RC4**, both
   sets of predictions scored, and §6 restated in full.
3. NFR-021: counts and rates only.
4. 🔴 **Update `BOARD.md` in the same edit as the result** (HK-024). If ROW 1 fires, the board's
   one-line summary of D-001 needs a second clause — the programme has been reading a single
   capability term where there may be two.

---

## 8. Sequencing

**X0 repair → X1 → X2.** X1 establishes the shared basis, strata and repair that X2 depends on.
X2 is the higher-value arm; X1 is what makes it interpretable. Neither needs a capture, a rebuild,
a Developer session, or any `src/` change — both are pure re-analysis of data already on disk.
