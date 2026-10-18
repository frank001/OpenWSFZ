# Spec: third decode pass (#240), step 1 = build flag-gated, then offline yield and timing (Architect → QA)

- **To:** QA. cc Captain. **From:** Architect. **Date:** 2026-10-18 12:05Z (`date -u`).
- **Captain's word (2026-10-18, Architect's window):** "spec it". His earlier word (2026-10-17): "I'm planning to implement the 3rd pass anyhow". This spec does **not** decide whether to build it. It defines **what the third pass is**, **how it ships (off by default)**, and **how we measure it** before anyone talks about turning it on.
- **QA's (k) review** (HK-021/025) applies before anything runs. QA may refuse rows on (k) grounds.
- **Docs only.** `src/` and `native/` diff empty.

## 0. Facts this spec rests on (checked 2026-10-18)

| fact | source |
|---|---|
| The residual pass fits and subtracts **every re-encodable pass-0 signal** from the exact normalised PCM, decodes the residual, and returns only new decodes (payload dedup, RR73-aware). Any failure ⇒ the whole pass is dropped (pass-0 only) | `src/OpenWSFZ.Ft8/Subfeas/SubtractionPass.cs` on `main` `f52f8c4b`, class summary |
| Cycle budget **13 s** from cycle decode start; fits cancel at `deadline − 1500 ms` (`SubtractionResidualDecodeReserve`); the residual decode never starts with less than 1.5 s left | `Ft8Decoder.cs:108`, `SubtractionPass.cs:43` |
| Live two-stage publishing: batch 1 = pass 0, batch 2 = the residual pass's new decodes, empty if abandoned | `Ft8Decoder.cs:331–337, 749–763` |
| sol timing, B2 build, refset 60 cycles, 8 threads: pass 0 median 1.1 / p90 1.4 / max 1.5 s; residual pass 3.1 / 5.5 / 6.5 s, 0 abandoned; residual found 123 decodes in 60 cycles | #240 body (F1′ block) |
| The reference WSJT-X, on the station AND in sol's R&R, is **2.7.0, Decode = Deep (`NDepth=3`), AP off (`FT8AP=false`)** | Captain's screenshot + `.ini` read 2026-10-18 |
| B2 is on `main` (`f52f8c4b`) and on `decoding_improvement` (`c4867dae`, station since 11:40:40Z) | board |
| No yield bar exists anywhere for a third pass | board, programme to-do; HK-038 |

## 1. What the third pass is (the definition the build must implement)

**"Deep" = one more subtract-and-decode round, incremental, with the same thresholds:**

1. Run only when the residual pass **returned ≥ 1 new decode** and was not abandoned. Otherwise skip it: on an unchanged residual it would only repeat the residual pass. Record the skip as `skipped-no-new` or `skipped-abandoned`.
2. Start from the **residual buffer the residual pass already produced** (pass-0 signals already subtracted). Fit and subtract **only the residual pass's new signals** from it. **Do not refit pass-0 signals.** This is what keeps its cost near one decode (§5 estimate).
3. Decode that buffer with **the same decoder settings** as the residual decode: same thresholds, same nhard/OSD, same AP constraints.
4. Return only decodes that are new against pass 0 AND the residual pass (the same payload dedup, RR73-aware).

🛑 **Out of scope for #240:** a lower sync threshold, more OSD, AP, extra candidates. Those are separate levers with their own false-decode risk. A build that changes any of them is not this arm.

If the incremental form (step 2) proves infeasible, the Developer **stops and reports**. A "refit everything" variant is a different cost model and needs a spec amendment (§5 changes).

## 2. How it ships (build requirements: QA → dev-task, or the Captain codes it)

| # | requirement |
|---|---|
| B1 | Config `decoder.decodingDepth`, values `"Normal"` / `"Deep"`, **default `"Normal"`**. Config POST overlay semantics, as for the other decoder keys (HK-035). Read back in `/api/v1/status` (or the decoder-params page): the value the decoder is actually using |
| B2 | **Normal is inert:** with `"Normal"` the decoder output is bit-for-bit today's (checked by V1) |
| B3 | **Additive only:** with `"Deep"`, pass 0 and the residual pass are untouched; the third pass only appends (checked by V2) |
| B4 | **Budget:** it shares the 13 s cycle budget and its cancellation/reserve mechanism. All-or-nothing: an abandoned or failed third pass publishes nothing and keeps batches 1 and 2. **Never time-gated or load-gated in any other way** (determinism: the R&R relies on it) |
| B5 | **Live publishing:** its decodes go out as **batch 3**, mapped exactly like batch 2 |
| B6 | **Counters in status:** third-pass runs, skips (by reason), abandons, failures, decodes. Separate from the residual pass's counters |
| B7 | **Per-cycle log line** in the same shape as the residual pass's (ms, new decodes, outcome), so QA's parsers can read it |
| B8 | **Preferred: managed code only, no native change** (reuse the existing fit on the residual buffer). If a native change is needed: next free shim at work time (20260064 if nothing lands first), HK-011 |
| B9 | Tests: Normal = today (golden); Deep additive; skip rules; abandon and failure paths publish nothing |
| B10 | **Not in step 1:** the Settings-page UI from #240. Config/API is enough to measure |

The build lands on a branch, **not merged**, until §4 has been read. Whether the merge goes to `decoding_improvement` or `main` is the Captain's call (HK-010).

## 3. The measurement (QA, offline, no station time)

### 3.1 Corpus

- **First list every `artefacts/` folder with WAVs** (Captain's rule, 2026-10-03), with band, date and whether the live WSJT-X `ALL.TXT` of the same session exists.
- **Primary (Y-40):** one live 40 m station session with its WAVs and the live WSJT-X `ALL.TXT`, from the OSD-fix era if one exists with WAVs kept (`20261009_1752` was planned "keep every WAV"). Otherwise `20260930_1930` (the 2026-10-01 subtraction OFF/ON replay night). The replay sets nhard and OSD itself, so never pre-filter audio by era (Captain's rule).
- **Secondary (Y-2):** one session on another band, if one exists. Descriptive only.
- **Timing (T-REF):** the sol refset 60 WAVs, the same audio as #240's 1.1 s / 3.1 s figures, so timings compare directly.
- QA states its choice and the reason **before** any Deep-ON decode is read.

### 3.2 Arms and settings

- **Two arms, same build, same process settings:** `Normal` vs `Deep`. Both have subtraction ON, nhard 24, OSD sign fix on, 8 threads. Same cycles, in the same order.
- **Yield runs (Y-40, Y-2):** budget **unlimited** (no abandon), so yield does not depend on the machine. Any machine.
- **Timing runs (T-REF):** on **sol, exclusive** (nothing else running: two settings' timings are compared, Captain 2026-10-03), with **the production 13 s budget**.
- **Harness:** the 2026-10-01 subtraction OFF/ON replay tooling, re-pointed from flag OFF/ON to Normal/Deep (QA's choice of the exact script, named in the run note).
- **Data handling:** aggregates only out of the reading functions (HK-037; per-message working files only under `_qa-scratch\<job>\`, deleted at close).

### 3.3 Validity rows (all must PASS; mechanical; exclusive)

| row | predicate | bar and where it comes from |
|---|---|---|
| V0 | DLL/.so SHA-256 of the build recorded at start and end, equal; nhard 24, sign fix 1, subtraction ON, threads 8 read back | identity of the instrument |
| V1 | `Normal` on the new build vs `main` `f52f8c4b` on Y-40 (DI-sync identity method, `di_sync_identity.py` with its OSD-sign-OFF control): **0 cycles differ**, and the control moves ≥ 1 cycle | B2 requires exact equality; the method and control come from DI sync 5/6 (control moved 5 of 430 both times) |
| V2 | Within `Deep`, the pass-0 + residual-pass decode set per cycle equals `Normal`'s: **0 cycles differ** | B3 is additive by definition: any difference is a defect |
| V3 | `Deep` yield run repeated once: **0 cycles differ** | unlimited budget ⇒ deterministic; the decoder gave 180/180 identical on S6 |
| V4 | Yield runs: **0 abandoned** passes (any pass) | unlimited budget; a non-zero count means the budget wasn't actually unlimited |

Any V-row FAIL ⇒ the measurement rows for **that corpus** are withheld (HK-021 (ab): scope the stop to what the row guards). V1 or V2 failing ⇒ report to the Architect before anything else; it is a build defect.

### 3.4 Measurement rows (reported with 95 % cycle-clustered bootstrap CIs; descriptive, no pass/fail)

| row | what | how |
|---|---|---|
| M1 | **NET_3** on Y-40 | (WSJT-X-matched OWS decodes, Deep) − (same, Normal), in pp of the WSJT-X decodes in those cycles. Matched = the same rule as the 2026-10-01 OFF/ON replay |
| M2 | Gross third-pass decodes per cycle; split into **WSJT-X-matched** / **OWS-only** | OWS-only = an **FP upper bound**, never "proven false" or "proven real" (SUB-FEAS §8.2 still open) |
| M3 | Third-pass **wall time** per cycle (T-REF, sol): median / p90 / max, for cycles where it ran; also pass 0 and residual on the same run | the B7 log line |
| M4 | **Budget** (T-REF, 13 s): share of cycles with the third pass abandoned; share skipped by reason; total cycle decode time median / p90 / max, Deep vs Normal | B6 counters |
| M5 | Yield under the production budget (T-REF): third-pass decodes kept vs the unlimited-budget count on the same cycles | how much of M2 survives the budget on sol, the slowest machine |
| M6 | Y-2: M1 and M2, descriptive | |

🛑 **Citation guards (from the first report):** never add NET_3 to SUB-FEAS's +8.89 pp or the offline +11.73 pp, and never difference them. Cite NET_3 only with its corpus and its CI. Sol timings are for **sol** (an FX-8350): never quote them as the station's.

## 4. What the result decides, and what it does not

- **This spec has no ship bar,** and none may be imported (HK-038). Whether `Deep` should ever be the default is a later decision. Its bar comes from M1's own CI and M4's budget figures, and a station-machine timing that this spec does not include.
- **The result answers three questions:** how many extra confirmed decodes, how much time per cycle, and how often the third pass misses the budget on the slowest machine.
- **F2 interaction** (live only; not part of this offline arm): every clamp episode on sol followed a residual pass of about 6 s. Before `Deep` runs on sol or the station, count clamped windows (see the B2CAPR ruling §3, Amendment 1). Never pool Deep-ON sweeps with Deep-OFF sweeps.

## 5. Predictions (registered now, before any build or data; HYPOTHESISED)

- **TP-1:** M1 NET_3 on Y-40 has a point estimate in **[+0.3, +2.0] pp** of WSJT-X decodes. **0.55.** Reasoning: the residual pass found about 2 per cycle on crowded audio; the third pass subtracts only those ~2 signals, so the new residual differs little. VOID if any V-row fails on Y-40.
- **TP-2:** M3 third-pass median wall time on T-REF (sol, 8 threads) is **≤ 2.0 s.** **0.60.** Reasoning: one decode (~1.1 s) plus ~2 fits. VOID if the incremental form (§1 step 2) is not what was built.
- **TP-3:** M4 share of cycles with the third pass abandoned on T-REF is **≤ 5 %.** **0.60.** Reasoning: pass 0 + residual max 8 s leaves ≥ 5 s in most cycles. VOID as TP-2.

## 6. Order and owners

1. QA (k)-reviews this spec.
2. Build per §2: QA writes the dev-task for a Developer, unless the Captain says he codes it.
3. QA's build review (V1/V2 can run as soon as the build exists).
4. Measurement §3.
5. Architect's ruling, which scores TP-1..3.

Open for the Architect (non-blocking): confirm from WSJT-X 2.7.0's documentation what Deep does for FT8, for context only (GPL: facts, never code).
