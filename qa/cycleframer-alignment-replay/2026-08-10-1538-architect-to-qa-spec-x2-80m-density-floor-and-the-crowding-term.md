# Architect → QA — spec X2: the 80m density floor, and whether crowding is a separate term

**2026-08-10 15:38Z** (filename and byline both from `date -u`, HK-017).
**Author:** Architect. **Audience:** QA (HK-015).
**Status:** execution spec for an existing QA pre-registration, plus two extensions.
**Commit this document before writing the harness.**

---

## 🔴 AMENDMENT 1 — 2026-08-10 16:44Z, made BEFORE the arm ran. Read this first; it WINS over the body wherever they disagree.

**Two triggers: X1 ran and returned ROW 1, and — more seriously — I failed HK-018 when drafting
§0.2.** The crowding mechanism is not unexplored territory. The programme has investigated it
hard, and one of its central claims was **already bounded and closed twice.** Had QA executed the
body of this spec verbatim, it would have been sent at a closed question with a mis-stated
tension. The defect is the Architect's drafting, not QA's execution.

### A1.1 Prior art §0.2 should have cited and did not

| finding | source | bearing |
|---|---|---|
| **C.1 swept `K_MAX_CANDIDATES` 140 / 300 / 600 → +0.93% at 300, byte-identical at 600** | 2026-07-25 | 🔴 **The candidate-cap family is already BOUNDED.** Raising the cap does not convert. |
| **RC1 → ROW 2: misses decompose 3.1% out-of-band / 8.9% no-candidate / 87.9% candidate-present-and-FAILED** | 2026-08-07 | 🔴 Misses are **not** mostly "never looked at". We saw the signal and could not read it. |
| **RC2 (candidate budget), "the leading treatment hypothesis" → CLOSED TWICE** | queue §3, l.367 | excluded by RC1 **and** already bounded by C.1. 🛑 **Do not re-propose it.** |
| Candidate caps **are** saturated — pass 1 (140) on 95/100 cycles, pass 2 (200) on 90/100 | RC1/RC4 spec §0.2 | Saturation is real, but per C.1 the surplus is **not decodable**. Saturation ≠ loss. |
| Budget allocated backwards — pass 1 yields 16.42%, pass 2 yields 0.80% | RC1/RC4 spec §0.3 | why a third pass cannot help |
| **"Our failure scales with density at fixed SNR"** | 2026-08-06 2323 note §3 | 🔴 **Already established. X2 does NOT discover this.** |

### A1.2 §0.2's "tension" was wrong in both directions — REPLACED

- 🛑 **D-009's null is not evidence about crowding at all.** D-009 **explicitly excluded**
  `K_MAX_CANDIDATES_PASS2` from its grid by construction. Citing its +0.109 pp as a puzzle for
  the crowding reading was my error. **Strike that half of the tension.**
- 🛑 **RC4's null is expected, not puzzling.** Pass 2 already converts at 0.80%, so a third pass
  works an even more depleted residual. Nothing to reconcile.
- ✅ **The real reconciliation, and it is much sharper:** `F_std` = +17.22 pp at the floor must be
  squared with **C.1's +0.93% ceiling on the cap family** and **RC1's 87.9% candidate-present-and-
  failed**. Those two together say the crowding cost is **not** budget exhaustion. **That is the
  reconciliation the report must perform.**

### A1.3 The ROW 1 consequence is REPLACED

§3's ROW 1 currently says the time-bounded candidate/pass budget "earns its own pre-registration."
🛑 **Delete that. RC2 is closed twice and C.1 bounded the family at +0.93%.**

**Replacement ROW 1 consequence:** crowding is a real, first-order term that is **not** explained
by candidate-budget exhaustion (A1.1). Since candidates are present and attempted and still fail
in dense cycles, the surviving explanation family is **degradation of the signals themselves when
the cycle is crowded** — co-channel and adjacent-signal interference — which is the *same channel
family* X1's ROW 1 just promoted. **ROW 1 therefore promotes ONE joint sub-question with X1, not a
budget arm**, and it needs its own pre-registration. 🛑 Still no `src/` recommendation, no
parameter sizing, no capture run, in any row.

### A1.4 🛑 The S.1 hazard, stated because A1.3 points straight at it

The natural next measurement after a co-channel reading is a spectral one, and **S.1 is CLOSED —
do not re-litigate or re-derive** (Captain, 08-04, reconfirmed 08-07; S.1r ROW 4 on an unpopulated
boundary). **X2 measures the phenomenon and stops.** Any mechanism arm must confront the S.1 bar
explicitly in its own pre-registration and take the Captain's ruling — **QA must not settle it in
session** (§4.3 already says this; A1.3 makes it live, so it is repeated here deliberately).

### A1.5 Check data that already exists before proposing any new measurement

**S.2a — "does the candidate cap bind harder when the band is busy?"** was recorded as *blocked
for want of instrumentation*, and **that was WRONG**: `ft8_get_last_candidate_counts()` per-cycle
getters **were logged in the 5 runs already on disk**. If the report wants
saturation-versus-density, **the data exists — go and look before recommending anything**
(HK-004, HK-018).

### A1.6 What X1's result changes

X1 ran 2026-08-10 16:22Z → **ROW 1**
(`2026-08-10-1622-qa-to-architect-x1-cross-band-recovery-decomposition-results.md`).

1. **`ROW 0f` is satisfied — the X0 repair is DONE.** Verify it (distinct inodes, repaired `A∩B`
   = 10 913 raw / 10 839 clean); **do not redo it.**
2. **Pin the SNR strata to X1's published edges** rather than recomputing — identical by
   construction, but pinning removes a drift path:
   - L1 `[−15, −10, −5, 2]`
   - L2 `[−19, −15, −13, −10, −8, −5, −2, 2, 7]`
   - L3 `[−21, −19, −17, −15, −14, −13, −12, −10, −9, −8, −7, −5, −4, −2, 0, 2, 4, 7, 11]`
   X2's primary metric uses **L1**, as the body specifies.
3. **§4.1's reading is sharpened.** A band term is now confirmed (80m−20m `B_std` +5.70 pp L1 →
   +4.83 pp L3, CI [+3.91, +7.42]). So "crowding appears on 80m only" **no longer means
   "inseparable"** — it means crowding and band **interact**, and the interaction is the finding.
   Report it as such rather than as a failure to separate.

### A1.7 One claim in §0.2 is withdrawn

§0.2 says this "points somewhere the programme has NOT been looking." **False, and withdrawn** —
see A1.1. **What is genuinely new is narrower and should be stated that way:** the **floor regime**
(density ≤ 5, unreachable in any prior corpus), the **magnitude** (+17.22 pp), and **near-100%
recovery at the floor in the top SNR strata**.

### A1.8 Unchanged

**The gate thresholds in §3 are NOT touched** (`|F_std| ≥ 5.0` ⇒ ROW 1, `≤ 1.5` ⇒ ROW 2, SE bar
2.0 pp). They were pre-registered against a disclosed point estimate; moving them now would be
fitting the gate to the data. Everything in §1, §2, §4 and §5 stands except as amended above.

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
> 🔴 **SUPERSEDED IN PART BY AMENDMENT 1 (A1.1, A1.2, A1.7). Do not act on this section alone.**
> Its "the programme has not been looking here" framing is **withdrawn**, and its D-009/RC4
> tension is **wrong in both directions**. Kept unedited as provenance — it is what was believed
> when the spec was written.

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
  measured on* — including the headline ≈57.8%; (b) 🔴 **REPLACED BY AMENDMENT 1 (A1.3)** —
  ~~the time-bounded candidate/pass budget earns its own pre-registration, with the D-009/RC4
  nulls of §0.2 confronted head-on~~ 🛑 **the candidate budget is CLOSED TWICE (RC2) and bounded
  at +0.93% (C.1); do NOT re-propose it.** The replacement consequence is a **single joint
  sub-question with X1** on signal degradation in crowded cycles — see A1.3, and A1.4's S.1 bar;
  (c) 🛑 **no `src/` change and no parameter recommendation may be drawn from this arm** — it
  measures a phenomenon, it does not size a treatment (HK-011).
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
