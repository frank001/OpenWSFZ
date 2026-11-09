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

## §7. Amendment 1 (2026-11-09 17:30:31Z, `date -u`): QA (k) review adopted in full, before any freeze

QA's (k) review: **ACCEPT with two amendments**. These replace the named parts of §1–§3. Neither G_CS bar fires by construction, as QA checked: O★v2 reaches 58 of 700 CS rows (0.48 pp), so CI_lo ≥ 1.0 pp (≈ 121 rows) is high but reachable. L-CTRL can fire: against R3's batch-1 share (2.87 %, 200 of 6,978, on file), a 2.2 % failure to subtract exceeds +2.0 pp.

**A1.1 R3 exists for 382 of 400 cycles (ledger E145, mine).** The third pass ran in 382 of the 400 cycles (it was on the board: "third pass ran 382/400"). §1 assumed a stored R3 everywhere.
- **L-REPRO:** bit-identical or ≤ 1e-5 × peak on the **382** stored R3 buffers.
- **In the 18 cycles without R3, the reference is R3 := R2, in every row that needs R3.** The product subtracted only batch 1 there, so **the subtraction set for S and I in those cycles is batch 1 only**. The set stays "exactly what the product subtracted".
- For those 18 cycles QA reports the builder's batch-2 candidate count (the R2-buffer natives hold 36 entries in them) as descriptive, not used.

**A1.2 The R3 baseline is run on all rows.** On file, R3 forced records cover 11,573 rows: 164 unmatched rows have no record in any buffer, and the 18 cycles have no R3. **QA runs the forced legs on the R3 baseline (R3 := R2 in the 18 cycles) for all 12,124 rows**, so the baseline and the legs are paired on the same rows by the same code. About 5 min more machine time.

**A1.3 NET_all and L-LOSS exclude the subtraction set (ledger E144, mine).** As written, NET_all counted the set's own incompletely subtracted hits:
- 246 of them still decode on R3: batch 1, 200 of 6,978 (2.87 %); batch 2, 46 of 1,339 (3.44 %). That is 2.03 pp of n_ref.
- A **better** fit would lose those rows (up to ≈ −2 pp) and a **worse** one would gain them. So CI_lo(NET_all) > 0 worked against the lever's purpose, which is the bar not meaning what it says.
- **New definition:** NET_all and L-LOSS are computed over the rows **not in the subtraction set**: batch-3/4 hits, misses, NR. The subtracted-set hits are judged by **L-CTRL only**.
- Batch-3/4 hits decodable on R3 (124 of 126 batch 3, 756 of 1,170 batch 4) are real product decodes. Losing them is real damage, and it stays in.
- §3's BUILD-WORTH reads with this NET_all; the bar itself is unchanged (CI_lo > 0).

**A1.4 Time row.** QA's fit pool runs 8 workers, not the product's `Parallel.For`, so only the **ratio** of sequential to parallel time on the same machine and pool is reported. It stays descriptive.

**Cost (QA):** effort ≈ 3–3.5 h, machine ≈ 40 min. Under the 4 h line.

**Predictions:** unchanged (no pre-data revision; A1.3 changes NET_all's population, and none of CR-1..5 is about NET_all).

**QA may freeze with this text.**

## §8. Amendment 2 (2026-11-09 17:41:08Z, `date -u`): L-REPRO stopped as registered; the batch-2 set corrected; one re-run of L-REPRO

**What happened** (QA stop report `qa/rr-study/2026-11-09-1741-qa-cs-refit-stop-report.md`, `da9f6ab3`):
- R2 reproduces bit-identically in 400 of 400 cycles.
- R3 reproduces bit-identically in **363 of 382**. The other **19 differ by 0.6–12 % of the buffer peak** (bar 1e-5).
- **No freeze exists; there is no S or I output and no forced-leg output.** The stop fired as §2 registered it.

**Cause, which I checked in the code (ledger E147, mine; QA Q44 on the review side):**
- §1 defined the batch-2 set as "the batch-2 decodes R3 subtracted", and A1.1 let it be read as every re-encodable native of the R2 buffer. **The product's set is narrower.**
- The third pass fits the residual pass's **new** decodes (`SubtractionPass.cs:299–302`).
- The residual pass keeps a decode as new only if its 77-bit payload is **not** `SameQso` with any batch-1 candidate's payload (Step 5, `:457–490`).
- `SameQso` (`SubfeasPayload.cs:152–168`) is an exact payload match, or the RR73-aware match: the reference is an RR73 standard message and the candidate has the same call1/call2, `ir` = 0 and the on-air RR73 grid value.
- The stored R2-buffer natives are the list **before** that dedup, so the spec fitted signals the product never fits.

**A2.1 The batch-2 set, corrected (for the reproduction and for S and I alike):** the R2-buffer natives that
1. `EncodeMessage` accepts (`:476–483`), and
2. are **not** `SameQso` with the payload of **any batch-1 candidate**, the re-encodable batch-1 decodes that were fitted (`originalPayloads` = the candidates' payloads, `:459`), and
3. then pass the third pass's own `IsReencodable` + `EncodeMessage` filter (`:331–343`, as for any fit set).

QA ports `SameQso`, including the standard-field extraction and the RR73 sentinel, from `SubfeasPayload.cs` without change.

**A2.2 Why one re-run is allowed, and only one.** §2's "no retries" protects the result from a builder tuned until it passes. **This re-run is not that:**
- the correction comes from the product's code, read **after** the failure, not from the 19 cycles' numbers;
- no study output (S, I, forced legs) exists that it could be tuned toward;
- L-REPRO's bar is unchanged (bit-identical or ≤ 1e-5 × peak on all 382) and is re-run in full, **including the 363 that already passed**.

**If it fails again, the study stops for good**, as QA proposed, and I report that to the Captain.

**A2.3 Disclosure.** The freeze record states that L-REPRO failed once, the cause, this amendment, and the re-run's result.

Cost: about 8 min of machine time plus the port. Predictions: **CR-1 ("L-REPRO and L-CTRL pass on the first run") is scored MISS now**, at the stop. The re-run does not rescue it. CR-2..5 are unchanged.
