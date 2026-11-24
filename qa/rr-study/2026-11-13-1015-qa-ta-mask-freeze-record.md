# TA-MASK freeze record (Amendments 1 and 2): FROZEN; T_M = 0.480 committed before any acceptance-row S_M exists.

**Written:** 2026-11-13, `date -u` read 10:13:32Z at the null stage. **To:** Architect. **Spec:** `arch/accept-gate` `104f197f` + A1 `0777c9b9` + A2 (§10). **Code:** `qa/same-chain`: `tm_lib.py` blob `09c77d49`, `tm_run.py` `1efd965d`, `tm_analyse.py` `2f168a46`, `tm_selftest.py` `5c34e2bb` (**23 of 23 mutations killed**, incl. the paired-difference row). Local; QA tooling only; no `src/` or `native/` change.

## 1. What is frozen

| item | frozen as |
|---|---|
| mask (§2, A1.2) | neighbours = every other `n_ref` row of the cycle with \|Δf\| < 50 Hz (any SNR); tone track and timing from `EncodeMessage` and WSJT-X dt + 0.48 s; a bin is masked if a time-overlapping neighbour tone is within **6.25 Hz inclusive**; Costas search and data score over unmasked bins only; scorable = own tone bin not masked; **n_s < 20 ⇒ unscorable ⇒ not present**; unencodable neighbours stay unmasked and counted (A1.4) |
| position | WSJT-X frequency and dt, TA-CHECK's frozen calibration 0.48 s; DF grid ±3.125, dt ±0.12 s in 0.01 s steps, as `cf_fbid` (asserted equal at start) |
| groups | TA-CHECK's frozen lists (`tc_groups.json` sha prefix `c1bb7612dc2ddbbe`); **the 60 pilot rows excluded everywhere** (`tm_pilot_rows.json`, seed 20261113) |
| **T_M (A1.1)** | **max(pooled p99 over B1m ∪ T, T_bur-only p99) = max(0.4091, 0.4800) = 0.480**; 20,240 null sequences over 1,012 acceptance rows (181 unscorable nulls excluded; K_NULL 20, ≤ 0.3 data-tone agreement, other confirmed rows of other cycles, shared position and mask with the row). `frozen\tm.json` sha256 prefix `0e093506dbef7585` |
| A-GHOST (A2.1) | CI_hi(PR_M(ghost) − PR_U(ghost)) ≤ 0.05, paired by row on the T_bur acceptance rows whose strongest overlapping neighbour is encodable; PR_U = unmasked `locate_and_score` at 0.276; cycle bootstrap, B = 2000, seed 20261113 |
| decision | `tm_lib.decide` = §5 with A2.1: 1 VOID (A-KEEP fails: CI_lo(PR_M(B1)) or CI_lo(PR_M(B1m)) < 0.80; or n(T_bur) < 100) → 2 CREDULOUS (A-GHOST fails) → 3 REPAIRED (CI_lo(PR_M(T_bur)) ≥ 0.80) → 4 NOT-REPAIRED |
| reported beside | PR_M and PR_U for the ghosts (absolute, and within ΔSNR ≥ 20 dB), the second ghost's rates, PR_M by band and by ΔSNR / \|Δf\| quartile beside the unmasked rule, n_s per group, masked bins per symbol, PR_M(T_bur) with / without an unencodable neighbour |

## 2. Checks run (no acceptance S_M read)

- Self-test 23 of 23. Analysis plumbing run on random fake scores for the acceptance rows, then deleted (nothing read as a result).
- **T_M moved from the pilot's 0.445 to 0.480** with the acceptance nulls (T_bur-only p99); the pilot's PR_M therefore understates nothing of what the acceptance set will see.
- **Next:** `tm_run.py own` (acceptance rows B1, B1m, T and the ghosts of T_bur), then `tm_analyse.py` once.
