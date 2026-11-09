# `CS-REFIT` instrument spec: does a better subtraction of the strong neighbours recover the CS rows? Offline, small, no build

**From:** Architect · **To:** QA · **Date:** 2026-11-09 17:20:40Z (`date -u`) · **Branch:** `arch/cs-refit`
**Authority:** the Captain, 2026-11-09: "yeah, lets do the study" (option 1 of my CS proposal: an offline refit study, no build). His standing size rule (2026-11-08): "keep the verification tests small".
**Base:** `origin/main` `ef2fc84b`. **QA-only tooling, no `src/` or `native/` change, no replay, no station.** Docs only. This reuses SUB-COVER's builder and GAP-RESIDUAL's stored buffers.

🟢 **Size rule.** The same 400 stored cycles of `20260925_2010`, two new subtraction legs built from the stored O, and GAP-RELOCATE's frozen forced legs. **No replay, no new night, no pilot.** Target: QA effort ≈ 2–3 h (two builder variants on v2's code), machine ≈ 30 min. If QA's (k) estimate is over 4 h of effort, it says so and the Captain decides.

---

## §0. The question

**CS** (NR-TAX, frozen `cebd2acf`) is the unreached WSJT-X rows that have a **stronger overlapping neighbour we did subtract**: **700 rows, 5.77 pp [5.33, 6.22]**, enrichment 1.77, loss rate 22 %. NR-TAX's hypothesis is **residue from imperfect subtraction of strong signals**. CS-NR neighbours are stronger (median 12 dB vs 8 dB) and closer (25 Hz vs 30 Hz) than CS-hit neighbours. That is an association, not a cause.

**What is on file:**
- SUB-FEAS Stage 1 (2026-09-28, ruling `2026-09-28-0040`): our fitter's median residual X = 8.75 dB above noise, against 3.46 dB in empty bands. The ≈ 5.3 dB gap is **descriptive only**. Median removal D = 19.25 dB.
- SUB-FEAS Stage 2: the shorter envelope window (W = 0.16 s) did **worse** than 0.32 s (8.47 vs 10.07 pp). The window is not the cheap fix.
- **O★v2** (SUB-COVER v2, same fitter, everything subtracted at once): CS rows decodable 58 of 700. Coverage barely moves CS.
- **The product fits every signal of a pass on the same buffer, at once:**
  - residual pass: every batch-1 fit on the analytic signal of O (`SubtractionPass.cs:352`, `:392–398`), all subtracted together (`:425–431`) → R2;
  - third pass: batch-2 fits on R2 (`:242`) → R3.
  - So a strong signal is fitted with its overlapping neighbours still present in the buffer. A CS row's neighbour fit sees the CS row's own signal, and every other overlapping signal, as interference.

**This study asks:** if the same decodes are subtracted with a **better fitting procedure** (two candidates that need no new model), do the CS rows become decodable? It is a **lever measurement at the forced legs**, not an oracle. Both procedures could be built in `src/` on top of the existing native fitter.

## §1. The legs

**Common to all legs:**
- **The subtraction set is exactly R3's:** the batch-1 decodes R2 subtracted plus the batch-2 decodes R3 subtracted. The product's `IsReencodable` + `EncodeMessage` from our own text, and natives from `cap/off/native/<stamp>.tsv` (SUB-COVER v1 Amendment 2).
- **The set does not change, only how it is fitted.** So the comparison isolates the fit procedure from coverage.
- Same fitter (`SubfeasFitSignal` through the interop), same analytic-signal routine. Hash state bracketed as before.

| leg | buffer | procedure |
|---|---|---|
| **R3** (reference) | stored R3 | as the product: batch 1 fitted on O all at once → R2; batch 2 fitted on R2 all at once → R3 |
| **S** (sequential, strongest first) | `S` | order the whole set by our published SNR, descending (ties by freq ascending, then batch). Start from O. For each signal in turn: recompute the analytic signal of the **current** residual, fit that signal on it, subtract. |
| **I** (one refit on the residue) | `I` | start from stored R3. Fit **every** signal of the set again on R3's analytic signal, at the same tones and natives (the fitter's own dt/freq search runs again), all at once. Subtract every correction together: `I = R3 − Σ fit_R3(k)`. |

- Fit return codes are counted per leg (`fit-zero` = −3, as SUB-COVER). A signal that fit-zeros is not subtracted on that step.
- **Builder check first (row L-REPRO):** the same code with the procedure set to "as the product" must reproduce the stored R3.

**The forced legs** (GAP-RELOCATE's `gr_forced.force_cycle`, unchanged; frozen δ_p 0.6 s, δ_c 0.7 s, same comparator) run on S and on I for **every row of n_ref (12,124)**. Running on all rows, not only NR, is needed for the loss row. NR-TAX B4(b) ran 35,493 records in 848 s, so 2 × 12,124 ≈ 10 min. "Decodable" = primary found **or** coherent `v3_match`, as SUB-COVER.

## §2. Rows

**Freeze:** the builder, both procedures, the ordering rule and these predicates are committed before any S or I output exists.

| row | predicate (mechanical) | where its bar comes from |
|---|---|---|
| **L-REPRO** | with the procedure "as the product", the builder reproduces stored R3 for all 400 cycles: bit-identical, or max \|diff\| ≤ 1e-5 × the buffer's peak (observed figure stated). **Fails ⇒ stop and report, no retries.** | SUB-COVER v1 A2: O-BUILD reproduced R2 bit-identically, 400/400; this extends it to the batch-2 step |
| **L-CTRL** (HK-026: the leg still removes the strong signals) | for each leg, the subtracted hits that still decode at their own position, paired against R3 on the same rows: **CI_hi(share_leg − share_R3) ≤ +2.0 pp**, separately for batch-1 and batch-2 hits | the derivation of SUB-COVER v1 A2.1, from the on-file shares: an unsubtracted hit still decodes ≈ 93 % (O 93.12 %), a subtracted one ≈ 2.8–3.4 % (R2 2.82 %, R3 batch-2 3.44 %), so +2.0 pp ≈ a failure to subtract ≥ 2.2 % of hits. Legitimate drift on file: R3 − R2 +0.10 pp |
| **L-LOSS** (the U-side: does a better fit damage others?) | for each leg, the rows decodable on R3 but **not** on the leg, counted and reported with **NET_all** below | no bar of its own; it enters the decision through NET_all's CI_lo |
| **L-FZ** (report only) | fit-zero share per leg, beside R3's own (R2's on file: 160 of 6,877 = 2.33 %) | descriptive. A sequential refit on a cleaner buffer can fit-zero more or less often; the report says which |

**Readout (cycle bootstrap B = 2000, seed 20261109; pp of n_ref = 12,124), for each leg:**
- 🔴 **G_CS(leg):** CS rows (700) decodable on the leg, not decodable on O ∪ R2 ∪ R3. **The decision number.**
- **NET_all(leg):** rows decodable on the leg minus rows decodable on R3, over all n_ref rows. It counts L-LOSS against the gains.
- G by NR-TAX category (CS, CU-d, CU-u, CW, NC, IW, IS, E) and by CS's neighbour gap (Δ-SNR quartiles), descriptive.
- Wrong payloads at NR positions on the leg (as SUB-COVER).
- **Time:** per-cycle wall time of each leg's fitting on the PC, beside the product's parallel fit time on the same cycles (descriptive). Sequential fitting gives up the product's per-signal parallelism (`:392–398`), and a build must fit within the 13 s cycle.

## §3. Decision rule (pre-registered)

Applied to **each leg separately**. Two legs means two chances; I accept that mild multiplicity and state it rather than correct for it, because the legs are two different builds, not two readings of one.

| outcome | condition | consequence |
|---|---|---|
| **BUILD-WORTH** | for at least one leg: CI_lo(G_CS) ≥ 1.0 pp **and** CI_lo(NET_all) > 0 | I write a build spec for that procedure (the Captain's go first) |
| **CLOSE** | for both legs: CI_hi(G_CS) < 0.5 pp | the CS block is closed for fit-procedure levers; this study goes on record |
| **BETWEEN** | otherwise | to the Captain with the numbers |

**Where the bars come from (HK-038):**
- They are SUB-COVER v1's bars, for the same reason. A forced-leg gain converts to built decodes at about COH-RES-CAND's 0.405 (62 of 153 ceiling rows; PC, `20260930_1930`; a different night and lever, **indicative only**, the one figure on file).
- 1.0 pp at the legs ≈ 0.4 pp built. That is about what one 400-cycle arm resolves (COH-RES-CAND's NET CI_lo 0.29, half-width ≈ 0.2 pp). **A BUILD-WORTH here would be acceptance-testable in one normal arm.** That is the lesson of #273, where the gain was real but too small to accept.
- 0.5 pp ≈ 0.2 pp built, which one arm cannot separate from 0.
- The ceiling is 5.77 pp, so all three outcomes are reachable. NET_all's "> 0" is not a margin: it only requires the leg not to do net harm.

## §4. What this does not measure

- **A new signal model** (per-symbol complex amplitude, multipath). Both legs use today's fitter unchanged. If both CLOSE, the CS block's remaining lever is a new model, which is a bigger study.
- **Time in the product.** The wall time is descriptive, on the PC, outside the daemon.
- **Product positions.** Forced legs at WSJT-X's position are an upper bound on what a build at its own positions reaches.
- **One night.** `20260925_2010` only. A BUILD-WORTH would be accepted on a different night, by its own arm.

## §5. Predictions (Architect; scored at the ruling)

| # | prediction | P | class |
|---|---|---:|:---:|
| CR-1 | L-REPRO and L-CTRL (both legs) pass on the first run | 0.65 | C |
| CR-2 | G_CS(S) point ≥ 0.5 pp | 0.40 | H |
| CR-3 | G_CS(I) point ≥ 0.5 pp | 0.30 | H |
| CR-4 | outcome CLOSE | 0.45 | H |
| CR-5 | outcome BUILD-WORTH | 0.20 | H |

**Reasoning:**
- Removal is already ≈ 19 dB (SUB-FEAS D), so the residue of a neighbour 12 dB stronger sits ≈ 7 dB **below** the CS row. That is not obviously masking.
- CS's loss rate is only 22 %, and most CS rows are in the weak band D anyway. Both point at the rows being weak, more than masked.
- Sequential fitting is the more plausible of the two: CS neighbours overlap (25 Hz median) and are fitted today with the CS row present. So CR-2 > CR-3.

🔴 **Bias check:** HYPOTHESISED calls lean toward "a findable gain". BUILD-WORTH is held at 0.20 and CLOSE is the modal outcome.

## §6. Order and cost

1. QA's (k) review, rows and bars. QA confirms that stored R3 and the batch-2 natives are on disk (`_qa-scratch\gap-residual\`).
2. Freeze, with the L-REPRO run (it needs no S or I output).
3. Run: S and I builds; forced legs on all n_ref rows for each.
4. Short report: rows, G_CS, NET_all, L-LOSS, strata, time.
5. My ruling.

Working files: `_qa-scratch\cs-refit\` (HK-037: no message text leaves the functions that read it). Aggregates only in the report.
