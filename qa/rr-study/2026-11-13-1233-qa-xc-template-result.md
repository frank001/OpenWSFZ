# XC-TEMPLATE result: BUILD-WORTH by the registered rule. A known-message energy test detects 51 % of the E1 rows at a false rate of 4 × 10⁻⁴ per test: G = 1.91 pp [1.75, 2.07] of n_ref against the 0.4 pp bar. V-POS also passes (0.835).

**Written:** 2026-11-13, `date -u` read 12:32:34Z. **To:** Architect, then the Captain. **Spec:** `arch/cross-cycle-prior` `2e133bc0` + A1 (§10) + A2 (§11: V-POS gates only CLOSE and BETWEEN; order VOID, BUILD-WORTH, VOID, CLOSE, BETWEEN). **Code:** `qa/same-chain` `99e7ef85` (detector, scorer, null, T_E frozen before any E1 or P acceptance score; the pilot and freeze record `607280be`), then `f497706b` (A2's decision order, P descriptives, split-half spread; applied **after the acceptance scores existed but before any was read**: the scorer and T_E are unchanged). `xt_lib` `da6dc324`, `xt_analyse` `7cec9e5e`, `xt_selftest` `aa52b7a4` (**23 of 23 mutations killed**). **Run:** `xt_score.py own` once (10,058 tests, 3 min on 8 workers), `xt_analyse.py` once. A desk stage: no replay, no PC window, no `src/` or `native/` change. Working folder holds numbers only.

## 1. The decision, mechanically (A2 order)

| # | row | predicate | value | result |
|---|---|---|---|---|
| 1 | VOID | V-NULL-N: n(null) ≥ 3 / FA\* | 19,874 ≥ 7,000 | not fired |
| 2 | **BUILD-WORTH** | **CI_lo(G) ≥ 0.4 pp** | **G = 1.911 pp, CI [1.747, 2.068]** | **YES** |
| 3 | (VOID) | V-POS: CI_lo(D(P on O)) ≥ 0.80 | D(P on O) 0.835 [0.824, 0.846] | passes (not consulted for BUILD-WORTH under A2) |

**Outcome: BUILD-WORTH.** XT-1 yes, XT-2 yes, XT-3 (D(E1) point ≥ 0.50) yes (0.514).

## 2. The numbers

| quantity | value |
|---|---|
| **T_E** (null-calibrated threshold) | **3.0113**; cycle-bootstrap CI [2.961, 3.413]; FA\* = 0.021 / K = 0.021 / 49 = 4.286 × 10⁻⁴ per test; null exceedance at T_E 4.03 × 10⁻⁴ (8 of 19,874) |
| **D(E1) on the residual** | **252 of 490 = 0.514 [0.470, 0.557]** (hashed or unencodable rows, 75 of the 490, count as not detected and stay in the denominator) |
| **G** | D(E1) × 520 / 13,997 = **1.911 pp [1.747, 2.068]** (≈ 267 rows of the 520) |
| D(E1) on O (descriptive) | 0.271 (the residual doubles it: the subtracted neighbours no longer bury the row) |
| D(P on O), V-POS | **4,614 rows, 0.835 [0.824, 0.846]**; the pilot's 0.80 was a low draw |
| argmax inside the truth window (E1, residual) | 0.961 |
| tone-share baseline (`T_FROZEN`, at the instrument's own 1 % null, not comparable) | E1 residual 0.892, P on O 0.938 |
| E1 S_E\* quartiles (5 / 25 / 50 / 75 / 95) | 1.60 / 2.67 / 3.20 / 3.68 / 4.54 (null 99.9th percentile 2.80) |

## 3. Descriptives (A2)

- **D(P on O) by band** (A, B, C, D): 0.916, 0.876, 0.827, **0.650**; **buried 0.598 (1,237 rows) vs isolated 0.922 (3,377)**; by the batch the row was matched in: batch 1 **0.932**, batch 2 0.443, batch 3 0.323, batch 4 0.643, batch 5 0.618 (the late-batch rows are the weak ones; an energy sum without coherent combining does not reach them as the LDPC decoder did).
- **D(P on the residual) by matched batch** (the subtraction effect, K1): batch 1 **0.044**, batch 2 **0.084**, batch 3 0.935, batch 4 0.911, batch 5 0.779. Rows matched in batches 1 and 2 are gone from R2 and R3, exactly as the control's logic says; later batches are still there.
- **E1 by SNR band** (A–D): 0.581 (n 31), 0.543 (138), 0.505 (107), 0.491 (214): flat with SNR. **By prior age:** 30 s 0.555 (373), 60 s 0.386 (70), 90 s 0.383 (47). **By kind:** report 0.766 (77), grid 0.588 (194), grid CQ 0.574 (129), RR73 / 73 / RRR 0.357 (14), other CQ 0 (3), **every hashed class 0** (75 rows by construction). **By the prior's batch:** batch 1 0.536, later 0.489. **Buried 0.475 (362) vs isolated 0.625 (128).**
- **T_E split-half spread (A2 asks it beside any result):** T from the even cycles is **3.126** with exceedance **1.9 × 10⁻⁴** on the odd half; from the odd cycles **2.973** with exceedance **8.6 × 10⁻⁴** on the even half. The two false rates differ by **4.5×** (not the "about 2×" I expected: 3 and 14 events); both lie within a factor of 2.5 of FA\* in opposite directions, so **the false rate at T_E is known to about a factor of 2 to 3 either way**, which is what 8 to 10 exceedances give.

## 4. What this says and what it does not

- **The ceiling is partly reachable.** Stage 0's E1 = 3.715 pp; this detector reads 51 % of it at the stated false rate. The residual matters (0.51 against 0.27 on O); a live stage would need arm B-like per-pass buffers, and N24's CQ-AP residual differs a little.
- **The false side is bounded on the data that have truth.** 0.021 per cycle is the programme's U budget; K = 49 carried templates times 4.3 × 10⁻⁴ per test gives it. The null is real tests of real messages where the station is not transmitting (opposite parity, 19,874 of them), not a model.
- **Limits stated in the spec (§7) and measured here:** (a) the prior's position is WSJT-X's, not ours; (b) a live stage carries **our** decodes as priors, including false ones, and runs under the time budget (the per-test cost here is 0.09 s per worker); (c) the residual is arm B's; (d) **hashed messages (14.4 % of E1, 509 of the 5,167 P rows) are out of reach** until #60 resolves hashes; (e) one night, 40 m; (f) the threshold is a tail estimate on 8 to 10 events (T_E interval 2.96 to 3.41).
- **What a rise in G does not claim:** it counts WSJT-X-confirmed rows (E1 are matched by WSJT-X), so a built stage would be judged against WSJT-X on NET, as the Architect's §5 states; the bar here is the detection gain at the registered threshold.

## 5. Owed

**The Architect rules** (his §5: BUILD-WORTH ⇒ a build spec, Developer, HK-011, arms judged against WSJT-X on NET and on the null-calibrated false side, on the Captain's go). Working folder (`_qa-scratch\xc-template\`) holds numbers only.
