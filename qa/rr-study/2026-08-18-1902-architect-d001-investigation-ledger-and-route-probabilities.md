# Architect — the D-001 investigation ledger, and where the remaining probability sits

**Author:** Architect
**Date:** 2026-08-18 19:02Z (mechanically derived, HK-017; filename timestamp agrees)
**Repo state at authoring:** `qa/n1-ber-results` @ `5fa7fbb`, working tree clean
**Requested by:** the Captain — *"summarize all the investigations that we have done to find the
root cause of D-001 and estimate the probability of solving it per investigation."*

---

## 0. What this document is, and what it is not

**It is** a single consolidated ledger of every investigation the D-001 programme has run, grouped
by the pipeline stage it interrogated, with each arm's verdict and a stated credence that the line
of work it belongs to ends in a shipped fix. It is written to be readable by someone joining the
project today with no prior context.

**It is NOT:**

- 🛑 **a ruling.** No arm's status changes here. Where this document and an arm's own report or
  ruling disagree, **the report or ruling wins** and this document is the defect.
- 🛑 **a source of new numbers.** Every figure below is restated from a committed arm report, a
  ruling, or `memory/BOARD.md`. Nothing here was measured while writing it.
- 🛑 **a gate, or an input to one.** The probabilities in §7 are **subjective Architect credences**.
  🔴 **No pre-registration may cite, inherit, or gate on any probability in this document.** Any arm
  derives its own bar mechanically (HK-021).

**Genre precedent:** this is the successor to
`qa/cycleframer-alignment-replay/2026-08-11-1900-architect-route-memo-where-d001-lives-wsjtx-method-comparison.md`.
That memo lives in `cycleframer-alignment-replay/`; this one is filed in `rr-study/` because every
document from 2026-08-14 onward — the M-series, the N-series and P-LIVE — is filed there and that is
where the next round will look. Filed knowingly, not by drift.

**NFR-021:** counts, rates, statistics and file paths only. No callsigns, no message text. The repo
is public.

---

## 1. What D-001 is

On identical off-air audio our decoder reads roughly **460** messages where WSJT-X reads roughly
**750**.

| corpus | our recovery vs WSJT-X | basis |
|---|---|---|
| 20m | **57.8%** | H1a-corrected; supersedes the earlier `[55.5%, 57.8%]` bracket |
| 17m | **64.1%** | X1, standardised |
| 80m | **77.1%** | X0-repaired (the pre-repair 76.84% is void) |
| any band, SNR ≥ 0 dB | **83.2%** | replicates an independent 08-06 estimate to 0.2 pp — the firmest number in the programme |

⚠️ **Every recovery figure means "against WSJT-X at `NDepth = 3`"** — its deepest setting — while
OpenWSFZ runs `K_MAX_PASSES = 2`, candidate caps 140/200, and a hardcoded 200–3000 Hz window. **Part
of the gap is depth and budget asymmetry, not capability.** RC4 and C.1 bound that part small
(+0.70 pp and +0.93% respectively). They do not bound it at zero.

### 1.1 The three findings that localised it

1. **RC1's decomposition of 894 pooled misses:** **3.1%** out-of-band, **8.9%** no-candidate,
   **87.9% candidate-present-and-failed.** In nine misses out of ten we spotted the signal and
   failed to read it. 🔴 **Cite the decomposition; never "40% unexplained."**

2. **The bimodality (W1 / B.2 §5 calibration).** Three numbers that sat on the board separately for
   weeks: matched-hit control BER median **2.9%**; our BP+OSD corrects to `B50` = **11.3%** BER;
   the missed population's own BER median **44.0%** (p10 17.2%). That is bimodal, not a gradient —
   the misses sit at ~4× the correction threshold, where P(decode) ≈ 2%. `E = 4.28` of 135 is the
   complement: **~97% of the missed population was never correctable by any error-correction
   change.** ⚠️ THE 135 is a July corpus, n = 126 measured, and candidate mismatch inflates BER
   toward 50% — that cuts *toward* this reading but is not the same as measuring it cleanly.

3. **The architectural divergence (08-11 route memo §3.2).** For each surviving candidate WSJT-X
   goes back to the original audio and builds a **second, private, per-candidate front end** — a
   complex-baseband downconversion with phase retained, then fine frequency (±5 × 0.5 Hz), fine
   time (±4 × 5 ms), coherent Costas correlation, and 1-/2-/3-symbol **coherent** bit metrics.
   Final achieved resolution **≈0.5 Hz / 5 ms** against our **3.125 Hz / 0.08 s** — **≈6× coarser
   in frequency, ≈16× coarser in time.** 🔴 **We have no equivalent of this stage at all.** Fine
   refinement and coherent multi-symbol metrics are both *consequences* of holding complex
   baseband; neither can be bolted onto a `uint8_t` magnitude waterfall.

---

## 2. How to read the probability column

Each figure is my credence that **this line of work ends in a shipped change closing at least half
the remaining 20m gap** — 57.8% → **≥79%** recovery, measured on live off-air audio against WSJT-X
at `NDepth = 3`.

- **Closed arms score ~0% by construction.** Their value was localisation, not treatment, and that
  value is **already banked**. A 0% here is not a criticism of the arm — RC1 scores 0% and is the
  most valuable arm in the programme.
- 🔴 **Architect calibration, quoted because these are my numbers:** categorical **6/11**, ranges
  **9/16**, directional **2.5/5.5**, mechanical **3/4**. Nine of the defects found in the recent
  N/P series were **in my own specs**, not in QA's execution or the code under test.
- Treat every figure as a prior to be overwritten by the first real measurement.

---

## 3. Stage 1 — capture and framing

| arm | question | verdict | status | P |
|---|---|---|---|---|
| **Clock drift / CycleFramer** (07-24 → 08-04) | Does capture-clock drift misframe cycles? | **A real defect, found and fixed** — 48.0 ppm on the USB CODEC chain; the ~6 h FT-991A cap lifted at `be5960a`/PR #121. But 07-31 settled that **drift does not explain D-001**. | banked | ~0% |
| **X0 / G1** (08-10) | Is the 80m reference corpus sound? | Two 80m `wsjt-x/ALL.TXT` files were **the same inode**; `--wsjtx-link-from` used where two instances existed. Repaired, recovery moved +0.25 pp. **Data integrity, not a cause.** ⚠️ 1,968 WAVs in the 80m pair are still hardlinked — folded into G1 Amendment 1. | closed | ~0% |
| **Route A — live framing phase** (specced 08-11 memo §5, **never run**) | Do two instances of our own decoder sit at persistently different framing phase, and does that track decode disagreement? | **Open.** Two identical builds, one antenna, one device: self-consistency **94.2–94.4% on 20m** vs 99.6% on 17m. Density ruled out (flat across all five quintiles), run-length drift ruled out (flat across 11 hours). The decisive test landed **ROW C, inconclusive**, inside its own pre-declared dead band. `CycleFramer.cs:190` documents up to **2048 samples (171 ms)** of unconsumed chunk at resync, reduced but not eliminated. | **OPEN** | **12%** |

---

## 4. Stage 2 — candidate generation

**Exhaustively closed.** Six arms; every cheap lever measured and spent.

| arm | question | verdict | status | P |
|---|---|---|---|---|
| **RC1** (08-07) | Is the gap in candidate generation? | **ROW 2 — no.** `f_nocand` = 80/866 = **9.2%**, and never approaches 0.30 in any SNR band (max 0.210), density band (max 0.123) or spectral tercile. **The single most valuable arm in the programme.** | banked | ~0% |
| **RC2** | Is the candidate budget the constraint? | **Closed twice** — excluded by RC1's gate, and already bounded by C.1 six weeks earlier. Caps *are* saturated (95%/90%); **saturation is not loss.** 🛑 Do not re-propose. | dead | ~0% |
| **C.1** (07-25) | Does raising `K_MAX_CANDIDATES` help? | 140 / 300 / 600 swept: **+0.93% at 300, byte-identical at 600.** The family is bounded. Its own recommendation predicted RC1's ROW 2 six weeks early. | closed | ~0% |
| **D-009** (07-22) | Can a 45-point parameter grid close it? | **+0.109 pp** across the whole sweep. This is what "architectural, not parametric" looks like from the outside. | dead | ~0% |
| **RC3 / G2(a)** (sized 08-07, shipped 08-13 `9500e03`) | Does the hardcoded 200–3000 Hz passband cost decodes? | **Yes, small and known:** 28 out-of-band of 894 misses = **3.1%**. Passband + hash-table sizing shipped. ⚠️ The sub-200 Hz misses have a **certain** mechanism (`ft8_shim.c:1183`), not a "band-edge effect." | closed | ~1% |
| **X3 → X4 → X5** (08-10/11) | Is the failure spectrally local? | **Three consecutive arms, ZERO readings**, all three killed by Architect gate-drafting rather than by data. 🛑 **Spectral locality is RETIRED PERMANENTLY; LOCAL vs DIFFUSE is permanently UNANSWERED.** ✅ X1/X2 are unaffected — crowding as a first-order term stands; only the mechanism died. | retired | ~0% |

---

## 5. Stage 3 — position and lattice

Nine arms. The lattice demonstrably costs recall; refining position **inside the current
architecture** demonstrably does not recover it.

| arm | question | verdict | status | P |
|---|---|---|---|---|
| **T1** (08-08) | What does frequency quantisation cost? | **ROW 3 — real but small.** `G` = **3.16 pp** on 20m. 🔴 **Quote as a FLOOR, never a point estimate** — WSJT-X reports integer Hz, so the residual lives on a 13-rung ladder and non-differential error in a stratifier attenuates the contrast toward zero. Concentrated on marginal signals: **4.4–6.9 pp** in the three weak/moderate SNR quintiles, 1.2–1.4 pp in the two strong. 🛑 Never publish a "corrected `G`". 🛑 Do not extend T1 to the time axis — reference DT resolution (0.1 s) is coarser than our own 0.08 s step. | closed | ~0% |
| **T2** (08-08) | The midpoint question. | **ROW 3.** Unanswerable from `ALL.TXT`: the structural ceiling is distinct integer frequencies in 200–3000 Hz; 20m alone covers 93% of them and the three-band union 97.5%. | closed | ~0% |
| **P3** (08-09) | Does sub-lattice placement cost decodes? | **ROW 3.** `S_all` = **4.27 pp** — the **largest single-arm effect in the programme** — but the union of five decoder runs carries an **89.7% junk rate** (`X_guard` = 0.897). Its own conclusion: *refine inside the decoder, not by a union bolted outside it.* | closed | ~0% |
| **R0 / R1 / R1b** (08-13 → 08-14) | Is our sync refiner a trustworthy instrument? | Reproducible native build shipped (PR #123, `f164123`); refiner validated and one real method fault corrected. **Infrastructure, correctly built. No recall claim.** 🛑 The R0/R1/R1b ~1.1 ms / 0.5 Hz prohibition is unchanged. | banked | ~0% |
| **M1 – M5** (08-14 → 08-15) | Measure the refiner's positional capability by proxy. | 🛑 **The entire series is abandoned.** M1/M2 **VOID** — they handed the refiner a time anchor ~0.65 s outside the audio's own time base. **M3 ROW 1** confirmed the confound cleanly: HIT median `dt_win` **+0.450 s**, 91.3% within ±0.10 s, control 0.000 s. **M4 VOID** as a measurement of positional capability (my statistic, mis-specified). **M5 withdrawn before it ran.** | void | ~0% |
| **N1** (08-16) | Does reading bits at the **refined** position lower BER? | **ROW 2 — limb 1 is DEAD as a treatment.** `d_ber` = **−0.57 pp**, CI95 [−1.15, +0.00], p = 0.69, 67 clusters; `f_cross` = 0.0%. 🔴 **On the strong-candidate stratum refinement is actively HARMFUL: −4.02 pp, CI95 [−6.90, −2.30], p = 0.000.** THE 567 shows exactly zero. Neither stratum benefits. **⇒ R2 is EXCLUDED, not merely unscoped. The failure is in how the bits are formed, not where they are read.** | dead | ~0% |
| **Route C** — `K_FREQ_OSR`/`K_TIME_OSR` 2→4 | Just halve the lattice? | Still no refinement, still no phase, 4× waterfall cost, lands at 1.5625 Hz / 0.04 s — **nowhere near 0.5 Hz / 5 ms.** 🛑 Barred on P3's evidence: earns its own pre-registration with **false positives as the PRIMARY metric**, not recall. | held | **5%** |

---

## 6. Stage 4 — bit formation (the one stage never successfully tested)

This is where the remaining probability lives, and it is also where five consecutive rounds have
been spent fighting our own instruments rather than the defect.

| arm | question | verdict | status | P |
|---|---|---|---|---|
| **N2** (08-16) | Does a coherent multi-symbol LLR extractor fix the reading? | **Primary (V3 vs V0) never reached — ROW 0b, withdrawn as specced, not void.** 🔴 **The by-product outranks the gate it failed to reach: the two limbs are a CONJUNCTION, not alternatives.** Coherent extraction **requires** fine frequency as an *enabler* — tone spacing × symbol period = 1.0 makes per-symbol DFTs phase-continuous **for df = 0 only**; 2 Hz across a 3-symbol group is **346° of rotation**. Control-population ladder ran the wrong way with order: V0 2.87% < V1 5.75% < V2 6.90% < V3 8.05%. 🛑 **Do not cite that ladder as clean evidence of frequency sensitivity** — it is confounded with QA's cumulative combination rule and this run cannot separate them. 🛑 All N2 V-numbers are **control-population**, never D-001 recovery figures. | escalated | n/a |
| **N3** (08-16, ruled 08-17) | How much frequency accuracy does coherent extraction require? | ROW 0b fired on a **correctly-implemented row guarding a wrongly-defined statistic** — mine. Recomputed from the committed curves: the below-`B50` region is contiguous and strictly interior on all five variants; the width was fully determined the whole time. 🛑 Central-lobe widths recovered post-hoc are **NOT citable as the requirement** (12 clusters, no CI). ✅ QA's refusal to widen the grid and re-read was **correct** (HK-026). | superseded | ~0% |
| **N4** (08-17) | The same question, pre-registered on a **held-out** population. | 🔴 **ROW 4 — a straddle, and the most consequential single number on the board.** `CI95(H_3^cum)` = **[1.437, 1.687] Hz** against the **1.5625 Hz** lattice half-cell — **equal to within 0.41%**. Ruled 16:48Z: **not a power failure**; narrowing is **CLOSED as infeasible**. | ruled | ~0% |
| **N5** (08-17) | Does the coherent extractor convert rows the current one fails? | **ROW 2 — `f_cross` = 0/403, CI [0.00%, 0.00%]**, zero of 2,000 bootstrap resamples ever produced a cross. But the honest rule-of-three bound is **4.37%** on only **67 clusters**, clearing the 5% cut by **0.6 pp**. 🔴 **HELD, not confirmed.** | held | ~0% |
| **P-LIVE Stage 1** (08-18 15:50Z) | Replicate N5 on ~12,100 live clusters instead of 67. | 🛑 **WITHDRAWN 26 minutes after it reported** (ruling 16:16Z). My spec placed extraction at WSJT-X's **raw reported DT** and fed it to `ft8_extract_llrs_at`, whose third argument is **buffer-relative** — 5.6 lattice cells ≈ 2.8 FT8 symbols out. 🛑 **Uncitable in any form:** `f_cross` = 0/15,389, the 0.0765% bound, all four extension-corpus bounds, "N5 CONFIRMED", "both limbs close". ✅ QA's execution accepted in full and not at fault. | withdrawn | ~0% |
| **P-LIVE Stage 1R** (08-18 18:24Z) | Positive control — is the anchor broken, and by how much? | 🔴 **ROW A — broken, confirmed independently of M3.** Median `BER_V0` at the raw anchor = **49.43%** on rows **we ourselves decoded**: chance level. A 49-point sweep on M3's own grid found a sharp three-point trough — 13.22% (+0.60 s) → **5.75% (+0.65 s)** → 6.90% (+0.70 s) — flat at 45–50% everywhere else, `n_ok` = 556/556 at every offset. **Stage 1 is VOID, not null.** | **LIVE** | **20%** |
| **Route B** — per-candidate complex baseband (**not built**) | Reimplement the one architectural difference. | **B1** = refine position only, reuse magnitude extraction. **B2** = full coherent multi-symbol LLRs off the baseband. A new stage between `ftx_find_candidates()` and `ftx_decode_candidate()` (`ft8_shim.c:1314-1335`). | **OPEN** | **45%** (B2) / **8%** (B1) |

### 6.1 The knife-edge, stated plainly

N4 says coherent order-3 extraction requires frequency accuracy of about **1.56 Hz**. Our lattice
half-cell is **1.5625 Hz**. They agree to 0.41%.

Read one way that is encouraging — the requirement is not absurd. Read the other way it is the whole
problem in one number: **at our current resolution a coherent extractor has no margin at all.**
That is consistent with N5 converting nothing, and with N2's control ladder getting *worse* with
every coherent order added.

🔴 **The consequence for route selection: Route B is not "limb 2 after limb 1." It is the only
construction in which either limb has margin, because the per-candidate complex baseband supplies
its own fine frequency estimate rather than inheriting the lattice's.**

⚠️ **This paragraph is my reading of N2's and N4's rulings, not a new result.** It is consistent
with both and contradicts neither, but no arm has tested it.

### 6.2 The anchor-offset finding — flagged, not pursued

Two independent code paths now measure a real, positive, multi-symbol time-convention offset:

| measurement | value | path |
|---|---|---|
| M3 (08-15), ROW 1 | **+0.45 s** | through the sync refiner |
| P-LIVE Stage 1R (08-18) | **+0.65 s** | directly at `ft8_extract_llrs_at`'s entry point, no refiner |

⚠️ **These are NOT the same quantity.** M4 already flagged M3's correction as possibly short; the
~0.20 s gap is consistent with that flagged residual, not a contradiction.

🔴 **The question nobody has asked yet, and it is the only open one that could re-route the
programme rather than refine it:** is this purely a QA-harness convention mismatch, or does our
production decode buffer sit systematically offset from the UTC grid? If the latter, it is **Route A
wearing a different hat** — 0.65 s is **eight lattice cells**, against a framing curve
(`CycleFramer.cs:184`) that already measures −3.8% of decodes at 1 s of offset.

🛑 **Labelled a HYPOTHESIS, not a finding.** The harness anchoring is not the production framer, and
nothing in Stage 1R measures the production framer. 🛑 **P-LIVE must not be retro-fitted into this**
(ruling §7). It earns its own pre-registration.

---

## 7. Stage 5 — error correction

Closed on the strongest evidence in the programme. **The misses are not near-misses.**

| arm | question | verdict | status | P |
|---|---|---|---|---|
| **C.2 Phase 1** (07-26) | Is there a real discriminator between decoded and failed candidates? | **Yes**, score-controlled, `p = 9.1e-34`. This is what made every later BER measurement meaningful. | banked | ~0% |
| **C.2 Phase 2c** (07-26) | Does LLR shrinkage recover anything? | **0 of 135 recovered at every weight from 0.00 to 1.00**, and harm rises monotonically 0/0/1/2/5. **Closed on evidence, not argument.** | dead | ~0% |
| **W1 / B.2 §5 calibration** (07-26 and 08-07) | How many bit errors can this codebase's BP+OSD actually correct? | **The calibration that reframed the programme.** `E ≈ 4–6` of 135, cross-validated across two runs twelve days apart with different noise models, different synth paths and different DLLs. Gives `B50` = 11.3% and therefore §1.1's bimodality argument. | banked | ~0% |
| **RC4** (08-07) | Does a third decode pass help? | **ROW 2 — no.** `d` = +0.70 pp; pass 2 already converts at only 0.80%, so the null is *expected*. Recommend reverting `K_MAX_PASSES` to 2 and landing the test fix (root cause has broken twice). | closed | ~0% |
| **D-009 Option B** (awaiting the Captain) | Shallow OSD — `osd_nhard_max` 60 → 40? | **Recommend HOLD.** It makes OSD shallower at exactly the stage RC1 ruled out, and its "after RC2" sequencing is void. Live evidence cuts both ways: the ~4.24–4.90% false-positive rate argues weakly *for*, the recovery deficit argues *against*. Recall tied exactly on synthetic S5/S7 arms — never the live window. | held | **2%** |
| **C.5a** (08-07, retracted 90 min later) | Direct bit-flip injection to find the correction threshold. | 🛑 **`k_50 = 13/174 = 7.47%` IS NOT A DECODER PROPERTY. Do not cite.** It landed *below* the (174,91) hard-decision capacity limit, which a soft decoder cannot really do; its x-axis is not the corpus BER axis. ✅ The harness survives; the number does not. | void | ~0% |

---

## 8. Stage 6 and cross-cutting

| arm | question | verdict | status | P |
|---|---|---|---|---|
| **P2** (08-09) | Does the shipped PCM scale cost decodes? | **ROW 2** over **±18 dB in 6 dB steps**, points fixed from the waterfall's dB window before any recovery number was computed. 🛑 **Input scaling, normalisation, AGC and equalisation are CLOSED PERMANENTLY** and may not be proposed again without new evidence. | dead | ~0% |
| **X1** (08-10) | Is band a first-order term after standardising density **and** SNR? | **ROW 1 — yes.** `B_std` = **+5.70 pp** at quintile stratification, still **+4.83 pp** at 20 tiles — 85% survives the finest stratification the corpus supports; cluster CI [+3.91, +7.42]. Replicate agrees to 0.022 pp. 🔴 **`B_std` is an UPPER bound — quote "at most," never "at least."** Promotes channel characterisation (multipath / Doppler spread) to a named sub-question. | banked | ~0% |
| **X2** (08-10) | What does crowding cost at matched SNR? | **ROW 1 — `F_std` = +17.22 pp** [14.99, 19.38] between the density floor (≤5) and the crowded regime (14–26), with **near-identical SNR distributions** (p10/med/p90 −17/−5/+8 vs −17/−4/+10) — so this is not SNR composition. At the floor we recover **99.6% / 100.0%** in the top two SNR strata. 🔴 **Mechanism is NOT budget exhaustion** (Amendment 1) — the surviving family is **signal degradation in crowded cycles**, the same channel family X1 promoted ⇒ **one joint sub-question with X1**. | **OPEN** | **8%** |
| **H1 / H1a** (08-08) | Is the recovery figure contaminated by hash-token wildcards? | Recovery corrected to **≈57.8%**, bracket retired (`V` = 0.9968, `V_null` = 0.0000). **Best cross-validation in the programme:** mean \|Δf\| = **0.7452 Hz** against T1's independently measured `mean_r` = **0.7367** — agreement to **0.0085 Hz**, two harnesses, two populations ⇒ **we report the nearest lattice point**, never shown before. 🛑 Still never "new decodes." | banked | ~0% |
| **P1 / P1a** (08-09) | Is the `jt9 -d 3` reference bar sound? | 🛑 **`jt9 -d 3` offline is NOT a valid reference decoder** — +93.8% vs OpenWSFZ plus duplicate `(ts, message)` pairs; VOIDed Angle 1. Replacement is fresh WSJT-X on identically replayed audio. ⚠️ Open question 3: is its +11.2% overshoot a **batching** artefact (P1a measured batching at +8.8%) rather than a depth artefact? Hypothesis-generating only. | banked | ~0% |
| **subtract-and-resynthesise** (`subtractft8`, three attempts) | Complete WSJT-X's method with successive interference cancellation. | 🛑 **Three builds, three reverts, −17 pp at worst. BARRED.** Recorded explicitly because anyone reading WSJT-X's decoder end to end will find it and try to "complete the method." | barred | ~0% |

### 8.1 A trap worth naming before someone walks into it

X2 says crowding costs **17.22 pp** at matched SNR and points at co-channel / adjacent-signal
degradation. **The textbook remedy for exactly that is successive interference cancellation — which
is `subtractft8`, which we have built and reverted three times for as much as −17 pp.**

🔴 **The largest measured population effect on the board currently has no available treatment.**
That is not a reason to ignore it. It is a reason not to let it masquerade as a route, and it is why
its P is 8% and not 30%.

---

## 9. The five live routes, ranked

### 9.1 Route B2 — per-candidate complex baseband, full method — **45%**

Retain the cycle PCM; mix and decimate per candidate to complex baseband; correlate coherently
against the Costas arrays over a fine (Δf, Δt) grid; form coherent multi-symbol LLRs off that
baseband. New stage at `ft8_shim.c:1314-1335`.

**Why not higher:** nothing in our own build predicts the gain; N5 found zero conversions (on a thin
67-cluster bound); it is the largest piece of engineering the programme has contemplated; it is
native C; and it depends on `C:\Temp\ft8_lib_headers`, **outside version control** — a `C:\Temp`
clear makes the library unbuildable with no commit recording why.

**Why not lower:** every alternative has been measured and closed; the bimodality places the failure
upstream of correction; RC1 places it downstream of spotting; and WSJT-X's ~6×/~16× resolution
advantage is a *consequence* of this one stage.

🛑 **Three dead shortcuts, all re-verified — do not re-derive them.** (a) `WATERFALL_USE_PHASE` is a
dead switch, not a disabled feature — `grep USE_PHASE decode.c` returns **zero hits**. (b)
`ft8_decode_multi_symbols()` is dead code **and** adds dB magnitudes where WSJT-X sums complex
values — wiring it up does not buy the coherent gain. (c) framing offset alone cannot be a ~42 pp
effect; `CycleFramer.cs:184` measures −3.8% at 1 s.

**Cost:** weeks. Developer session + rebuilt DLL. HK-011 engaged. Licence policy binding —
**WSJT-X may be READ for method; not one line copied, transliterated, or ported.**

### 9.2 The anchor-offset question — **20%**

See §6.2. Cheap, re-analysis only, no `src/`, no capture run, and the only open question that could
**re-route** the programme rather than refine it.

### 9.3 Route A — live framing phase — **12%**

See §3. 🔴 **Its real value is not its own probability: if framing phase is a first-order term,
Route B's sizing changes.** That is why it is cheap-first, not likely-first. ⚠️ HK-021(i) applies —
the 08-08 test was already inconclusive once, so an underpowered repeat is an **instrument failure,
not a null**. Settle power before arming.

### 9.4 X1 + X2 — channel and crowding — **8%**

The largest measured population effects on the board, discounted hard by §8.1's treatment gap and by
the fact that the mechanism arm died three times over on spectral locality.

### 9.5 The cheap partial measures — **8% combined**

Route B1 position-only refinement (~8%), Route C lattice halving (~5%), D-009 Option B (~2%). All
three feed a magnitude-only single-symbol extractor that N1 showed is insensitive to position, and
none reaches WSJT-X's resolution class. **None recommended.**

### 9.6 Aggregate

These routes are **not independent** — B2 subsumes much of B1 and C, and the anchor-offset question
feeds Route A. Combining them by judgement rather than by multiplying:

| statement | credence |
|---|---|
| The root cause is now correctly identified as **the absence of a per-candidate complex-baseband front end** | **~65%** |
| We ship something closing **≥half** the 20m gap (57.8% → ≥79%), if the programme continues on its current route and Route B is authorised | **~55%** |
| We close a **material** fraction (≥5 pp) | **~85%** — T1, P3 and RC3 alone have measured that much in known, bounded, individually-small effects |

⚠️ **Against a stricter definition of "solve" — parity with WSJT-X — halve every figure above.**

---

## 10. What would move these numbers, cheapest first

1. **Pre-register the anchor-offset finding on its own terms** (§6.2). Hours. Currently awaiting an
   Architect ruling.
2. **Route A's power calculation** — not the arm, just whether the arm can resolve what it needs to.
   An afternoon, and it has blocked a first-order question since 2026-08-08.
3. **P-LIVE Stage 2, unblocked.** N5's whole verdict rests on 67 clusters and a bound clearing its
   cut by 0.6 pp; the live corpus offers ~12,100 clusters. A **correctly-anchored** replication
   either hardens the zero into something citable or overturns it — and it moves Route B2's number
   in whichever direction it lands. 🛑 Stage 2 stays **BLOCKED** per the 16:16Z ruling §6 unless the
   Captain rules otherwise.

---

## 11. Citation limits for this document

- 🛑 **No probability in this document may be cited in, inherited by, or gated on in any
  pre-registration.** They are Architect credences with a stated calibration of 6/11 categorical.
- 🛑 **§6.1 (the knife-edge) and §6.2 (the anchor-offset hypothesis) are READINGS, not results.**
  Both are labelled as such in place. Neither has been tested.
- 🛑 **No arm's status changes here.** Where this document disagrees with an arm's own report or
  ruling, the report or ruling wins.
- ✅ **The factual restatements in §1 and §3–§8 are citable** — but cite the originating report, not
  this document.
- ⚠️ **This document will go stale.** It is a snapshot at 2026-08-18 19:02Z. `memory/BOARD.md` is
  the live state.

---

## 12. Housekeeping

- No `src/` touched. No Developer session. No DLL rebuild. No capture run. **HK-011 not engaged.**
- No measurement run while authoring. Every figure restated from a committed report, ruling, or the
  board.
- HK-017: filename `2026-08-18-1902-…` and the byline `2026-08-18 19:02Z` both derive from a real
  `date -u` in the authoring session and agree.
- HK-014: **not committed, not pushed.** The Architect commits locally only on instruction and never
  pushes or merges.
- NFR-021: counts, rates, statistics and paths only. No callsigns, no message text.
