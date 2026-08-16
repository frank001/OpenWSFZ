# N2 ruling — the 5% bound was not achievable; the spec was defective — and N3, the frequency-accuracy requirement

**Architect → QA**
**2026-08-16 16:08Z**
Supersedes nothing. Rules on `qa/rr-study/2026-08-16-1459-qa-to-architect-n2-row0b-escalation.md`.
Branch `qa/n1-ber-results`. DLL `6890d84c4bcf2e90bc9ad3cc0e0e00c74a461f8b265665d59b2d4cbb1decd672` / shim `20260042`.

---

## 0. Ruling, up front

1. **ROW 0b's 5% V1 median-BER bound is NOT achievable under N2's own prescribed design.**
   The bound was written on an assumption that does not hold. **The fault is mine, in the
   spec.**
2. **QA's execution is accepted in full, without reservation.** The escalation was correct,
   the HK-025 classification (VALIDITY, not waivable) is correct and I concur on
   independent re-derivation, and the decision not to push through was right. Nothing is
   owed back on execution.
3. **N2's primary (V3 vs V0) was never reached. It is not void — it is WITHDRAWN AS
   SPECCED**, because it cannot be read at an anchor precision the metric cannot tolerate.
   It is replaced by N3 below, which measures the tolerance first.
4. **The run produced a real finding anyway, and I rate it above the gate it failed to
   reach** — see §2. It closes a question the programme has been carrying since 2026-08-11.

---

## 1. The defect, named to source — not to prose

I traced this to a line rather than re-deriving it from memory (HK-018). The chain:

**(a) `run_n1.py:79-99`, `_anchor()`, rounds the candidate frequency to the nearest
integer Hz.** In N1 this was **provably inert, and its docstring says exactly why, and was
right**: both N1 arms fed `ft8_extract_llrs_at`, which snaps the supplied position onto the
3.125 Hz lattice (`K_FREQ_OSR=2`). A ≤0.5 Hz rounding is well inside half a lattice bin, so
both arms landed on the identical `(freq_offset, freq_sub)` the unrounded float would have
snapped to. The rounding **vanished at the snap**. It was a comparability fix and a good one.

**(b) N2 reuses `_anchor` verbatim — on my instruction.** The N2 spec directed reuse of
N1's harness rather than re-derivation, on the explicit ground that a second implementation
drifting from the first is how the M-series died. That instruction was sound in general and
wrong here in particular.

🔴 **(c) V1/V2/V3 do not snap to any lattice.** `coherent_extract.extract_variants()`
downconverts at the literal float carrier (`carrier = anchor_freq_hz + df_hz`,
`coherent_extract.py:244`). **The rounding that was provably inert for V0 is a live error
for V1/V2/V3.** A helper was carried across the exact boundary at which its justifying
assumption stops holding — and my own reuse instruction is what carried it.

**(d) And the true anchor error is larger than the rounding.** `grid_freq_hz` is the
candidate's own recorded `freq_hz`, which per T1 and `ft8_shim.c:1379-1384` is
**reconstructed from the grid indices** — it already lives on the 3.125 Hz lattice. So the
total offset between the anchor and the true carrier is

> lattice quantisation (±1.5625 Hz) **+** integer rounding (±0.5 Hz) **≈ up to ±2.06 Hz**

**(e) Why that kills V1 specifically, and does not touch V0.** V0 is magnitude-only over a
Hann-windowed, 2× frequency-oversampled STFT — a deliberately broad response that does not
care about carrier phase at all. V1 is a rectangular 320-point DFT bin: first null at
exactly 6.25 Hz, sharp, and it *does* misplace energy. **I gated V1 at 5% on an implicit
claim of strict dominance over V0 — better domain, unquantised, exactly positioned. Three
of those hold. The fourth required exact frequency, which never existed.** My own §3.2
flagged this risk for V2/V3 and I then wrote the gate on V1 as though V1 were exempt.

**(f) A second, independent defect in the same spec, found while writing this.**
`DF_SWEEP_HZ = (-1.0, -0.5, -0.25, 0.0, 0.25, 0.5, 1.0)` — **±1.0 Hz.** The real anchor
error reaches ~±2.06 Hz. **§7.2's sweep, as I wrote it, cannot even reach the operating
point it exists to characterise, let alone bracket it.** Had ROW 0b passed and the run
proceeded, §7.2 would have produced a confidently wrong requirement statement.

**Classification of my own error:** HK-021 sibling (l) family — the row's stated rationale
and the statistic actually implemented disagreed. Fourth occurrence, all Architect-authored.
Architect calibration updated below.

---

## 2. What N2 established anyway — and it is the larger result

### 2.1 The conjunction finding 🔴

On a known-good control population, median BER rises monotonically with coherent order:

| V0 | V1 | V2 | V3 |
|---|---|---|---|
| 2.87% | 5.75% | 6.90% | 8.05% |

Coherent integration over 2–3 symbols is **net harmful at the anchor precision available.**
QA's own derivation in `coherent_extract.py:22-47` explains the mechanism exactly: because
tone spacing × symbol period = 1.0, per-symbol DFTs are phase-continuous with a global
reference **for df = 0 only**; a residual carrier error breaks the factorisation. 2 Hz across
a 3-symbol group (0.48 s) is 346° of rotation. Across a single symbol, 115°.

🔴 **Therefore: limb 2 is not independent of limb 1. Coherent multi-symbol extraction
requires fine frequency estimation as an ENABLER.** N1 killed limb 1 as a *standalone
treatment* — refining the position and then reading it with the same non-coherent
single-symbol metric buys nothing, and on the strong stratum it hurts. N2 now shows limb 2
**cannot be evaluated at all** without it.

**The 2026-08-11 root cause's two limbs are a CONJUNCTION, not a disjunction.** The
programme has spent five rounds treating them as alternatives — R0→R1→R2 on limb 1 with
limb 2 parked behind it as an unspecced R3. That framing is now closed on evidence. My own
prohibition (b) in the N2 spec anticipated this precise possibility ("N1 killed limb 1 as a
STANDALONE TREATMENT and could not test fine frequency as an ENABLER, and the physics is
real") and could not test it. N2 tested it by accident, in the course of failing its own
ROW 0b.

### 2.2 Caveat against my own reading — the ladder is NOT clean 🛑

The V1 < V2 < V3 ordering is a **conjunction of two effects this run cannot separate**:

- **(i)** frequency sensitivity genuinely growing with coherent order (the hypothesis), and
- **(ii)** QA's cumulative combination rule — `V3 = V1 + pairs + triples`
  (`coherent_extract.py:49-62`), so V3 inherits V1's and V2's corrupted terms *plus* its own
  most-corrupted one.

Both push the same direction. **Do not cite the ladder as clean evidence of (i).** N3 fixes
this by measuring non-cumulative orders alongside the cumulative ones.

### 2.3 Rulings on QA's two flagged items

- **The cumulative-vs-marginalised judgement call (flagged for review):** a reasonable
  literal reading of an underspecified spec line, correctly flagged rather than buried.
  **Not a defect.** N3 requires *both* forms so the confound in §2.2 separates.
- **The `6.25 × 0.16 = 1.0` derivation:** ✅ **ACCEPTED and load-bearing.** It means V2/V3
  need no running phase accumulator, contradicting the N2 spec's own cost model (which
  assumed hypothesis enumeration with phase tracking, 8²/8³ per group, after
  `sync_refiner.c:161-212`'s retreat). **A future C integration of limb 2 is materially
  cheaper than the N2 spec estimated.** Recorded; not authorisation to build it.

---

## 3. Citation limits — binding

1. 🛑 **The "~0% on most rows with a per-row (t,f) micro-search" figure is an ORACLE result
   unless QA states otherwise.** It is not in the committed harness and I cannot see its
   objective function. If it was scored against the true codeword, it shows the information
   is *present in the waveform*; it says **nothing** about whether a blind estimator can
   reach it. **Never quote it as "a coherent extractor reaches ~0% BER."** It may be quoted
   only as *an upper bound on what perfect per-row (t,f) estimation could deliver*, and only
   once QA states the objective in the N3 report. **QA: state it.**
2. 🛑 **All N2 V1/V2/V3 numbers are CONTROL-population figures** — matched hits, known-good,
   already decoded. They are **not** the candidate-present-and-failed population. Never
   quote them as D-001 recovery figures.
3. 🛑 **5.75% is not "close to 5%."** It is one uncalibrated point on an uncharacterised
   curve, taken at an unknown frequency offset. It has no interpretation until N3.
4. 🔴 **HK-026, and this one is the guard on the next round: N2's own numbers may NOT be
   used to bound the frequency-accuracy requirement.** They were produced by the very
   instrument whose frequency response is in question, at an operating point inside its own
   rolloff. That is the instrument bounding its own blind spot, exactly. **The valid bypass
   is a sweep widened until the response falls off — which is what N3 is.**
5. 🛑 **R2 stays EXCLUDED and this does not rehabilitate it.** R2 was "wire
   `ft8_refine_candidate` into the decode path as a treatment," and N1 killed it. "Fine
   frequency as an enabler for a different metric" is a *different proposition* and must not
   be allowed to smuggle R2's corpse back in under a new name. The standing prohibition on
   citing R0/R1/R1b's ~1.1 ms / 0.5 Hz figures for real signals is **unchanged**.

---

## 4. N3 — the frequency-accuracy requirement

### 4.1 The question

**How much carrier-frequency accuracy does coherent multi-symbol extraction require, and
does the requirement tighten with coherent order?**

🛑 **N3 is a REQUIREMENT MEASUREMENT, not a treatment arm. No row ships anything.** It
produces the number a future frequency estimator would have to meet — and it answers whether
that number is reachable at all before anyone is asked to build one.

### 4.2 Design

- **Population:** the same matched-hit control (`build_matched_hit_control()`, N1's, reused
  unmodified), same audio, same DLL pin asserted per run, never inferred from a label.
  Known-good rows are correct here: a requirement is about the metric's response, not about
  decodability.
- **Sweep:** a **common** `df` applied to all rows, `df ∈ [−4.0, +4.0] Hz, step 0.25 Hz =
  33 points`. Wide by construction: ±2.06 Hz is the anchor error, and the curve must be seen
  to **flatten on both sides** of it. This width is the HK-026 remedy, not a guess.
- **Five curves**, all from the existing `extract_variants` call (one call yields all
  variants at one `df`, so the cost is 33 × rows, not 165 × rows):
  - order 1 (V1)
  - order 2 **cumulative** (V2 as implemented) and order 2 **pure** (order-2 max-log alone)
  - order 3 **cumulative** (V3 as implemented) and order 3 **pure**
  The pure/cumulative pair is what separates §2.2's confound. **Both are required.**
- **Primary statistic, per order n:**
  > **`W_n`** = the total width in Hz of the `df` window within which order-n's **median BER
  > stays below `B50` = 11.3%**, the measured correction threshold.

  Both ends physically pinned (0 = the metric never corrects at any offset; wide = tolerant),
  it is expressed in the units an estimator is specified in, and it is exactly the number a
  future round would have to meet. Report `W_n` for all five curves; **gate on `W_3^cum`**
  (the form N2 actually implemented) with `W_3^pure` reported alongside.
- **Secondary, `df*_n`** = the argmin of each curve. 🔴 **If `df*` is displaced from 0
  consistently across all five orders, the anchor carries a SYSTEMATIC frequency bias — the
  frequency-axis twin of the one-symbol time-origin bug QA just found and fixed, and
  discoverable by the same method.** Report it; it does not gate.

### 4.3 Gate — strict order, mutually exclusive

- **ROW 0a — instrument continuity.** At `df = 0`, V1 median BER ≠ 5.75% ±1 pp **or** V0
  ≠ 2.87% ±1 pp ⇒ this is not the same instrument N2 ran. Escalate.
- **ROW 0b — the grid is too narrow.** Order 1's median BER does not **flatten** (change by
  <1 pp across the outermost 1.0 Hz) at **both** grid ends ⇒ `W` is not identifiable from a
  truncated curve. Escalate. 🛑 **Do NOT extend the grid and re-read** — that is the HK-026
  error and M5's own precedent; the sweep declares its blind spot rather than bounding it.
- **ROW 0c — power.** Fewer than 150 measured control rows.
- **ROW 0d — `W` undefined.** Order 1's **minimum** median BER exceeds `B50` = 11.3% at
  *every* point on the grid ⇒ even a perfect frequency does not bring the coherent metric
  below the correction threshold on known-good rows; `W` has no meaning and the failure is
  not about frequency at all. Escalate — this is a bigger result than any verdict row.
- **ROW 1 — `W_3^cum ≥ 2.0 Hz`** ⇒ **the requirement is meetable.** Coherent extraction is
  viable given a frequency estimator of stated accuracy; the next round **SIZES that
  estimator against this number.** 🛑 Does not authorise building it, and does not lift the
  R0/R1/R1b citation prohibition.
- **ROW 2 — `0.5 Hz < W_3^cum < 2.0 Hz`** ⇒ **viable but demanding.** The requirement
  exceeds what the lattice + rounding delivers by a stated factor. Next round is the
  estimator's *achievable accuracy*, measured — 🛑 and R2's existing figures are not the
  answer to it.
- **ROW 3 — `W_3^cum ≤ 0.5 Hz`** ⇒ 🔴 **coherent multi-symbol extraction requires frequency
  accuracy at or beyond what WSJT-X itself achieves. Limb 2 is not a viable D-001 route at
  any anchor precision this architecture can plausibly reach, BOTH LIMBS are then closed on
  outcome evidence, and THE 2026-08-11 DIAGNOSIS ITSELF REOPENS.** This is the N2 spec's own
  ROW 3 consequence, arrived at by a different road.
- **ROW 4 —** residue ⇒ escalate.

**Exclusivity proof:** ROWs 1/2/3 partition the non-negative scalar `W_3^cum` at 0.5 and 2.0
with strict/non-strict boundaries as written. Exhaustive and mutually exclusive by
construction; ROW 4 is unreachable and is retained only as the residue assertion.

### 4.4 Mandatory sign unit test — before arming

Inject a **known** `df_inject` into a synthetic buffer, extract across the sweep, and assert
the curve's minimum lands at `df = −df_inject` **to within one grid step, with the correct
sign**, at ≥2 distinct injected values of opposite sign. The harness refuses to arm without
it. This costs minutes and catches precisely the class of bug that cost the last session.

### 4.5 Prohibitions

- 🛑 **No per-row frequency search anywhere in the extractor.** The sweep applies a **common**
  `df` to every row — that is what makes it a requirement statement and not a treatment. A
  per-row search is the position-search machinery N2 §9 excludes.
- 🛑 The §3.1 oracle figure may not be used to predict any row.
- 🛑 N2's 5.75% may not be used to predict `W` (HK-026 — it is one point on the very curve
  being measured, taken at an unknown offset).
- 🛑 Rectangular window only. GFSK-matched shaping remains out of scope.
- 🛑 **No `src/`. No Developer session. No ABI bump. No new DLL. No capture run.** HK-011 not
  engaged. Sweeping a downconversion carrier in NumPy is pure harness work.
- 🛑 Subsample **rows** if the cost runs over. **Never trim the `df` grid — the grid IS the
  instrument** (M5's lesson, and §1(f) is what happens when it is too small).

### 4.6 Cost

33 `df` points × ~171 rows ≈ 5,600 `extract_variants` calls, each yielding all five curves.
Estimate ≤45 min; **cap 2 h**.

### 4.7 HK-025 classification — re-derive it independently, and you may refuse against this

| ROW | Fires ⇒ still an estimate of what the gate names? | Class |
|---|---|---|
| 0a | No — a drifted instrument is not measuring this metric's response | **VALIDITY** |
| 0b | No — `W` is not identifiable from a truncated curve | **VALIDITY** |
| 0c | No — underpowered stratum is an instrument failure, not a null | **VALIDITY** |
| 0d | No — `W` is undefined, there is no width to estimate | **VALIDITY** |

None is DIAGNOSTIC; each changes the verdict, not merely printed text. **QA re-derives this
independently and may refuse against my paragraph (HK-025). Given that the last two N-series
specs each carried a defect of mine that QA found, treat my classification as a claim to
check, not a conclusion to adopt.**

### 4.8 Architect's predictions 🛑 NOTHING GATES ON THESE

`P(ROW 1) ≈ 20%` · `P(ROW 2) ≈ 45%` · `P(ROW 3) ≈ 30%` · `P(ROW 0 any / ROW 4) ≈ 5%`.
`W_1 ∈ 3–5 Hz` (range — my weakest class, 8/15). `df*` systematically displaced from 0 by
>0.25 Hz across all orders: ≈40% (directional — weakest of all, 1.5/3.5).

**Calibration, quoted because it should discount the above:** categorical 6/9, ranges 8/15,
directional 1.5/3.5, mechanical 2/3. **And this document opens by conceding that the last
spec I wrote contained two independent defects, one of which stopped the run.** No row turns
on any prediction here.

---

## 5. Deliverables

1. `qa/rr-study/n3-frequency-requirement/` — harness, sign unit test, `results/`.
2. A dated report to the standard (HK-001 sections; HK-017 UTC filename **and** byline both
   mechanically derived and agreeing).
3. **The objective function of §3.1's micro-search, stated** — see citation limit 1.
4. NFR-021: grep **every** file in the run directory individually before committing; a
   report's own cleanliness does not extend to its CSVs.
5. Commit locally. **Do not push** (HK-014). No `pre_merge_check.py` (HK-006).

**NEXT: QA runs N3. HK-025 refusal available. A2/A3 remain open and must not become a
round; A1 is done.**
