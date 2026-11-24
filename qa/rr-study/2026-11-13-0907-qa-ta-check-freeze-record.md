# TA-CHECK freeze record under Amendment 1: FROZEN before any present rate of T exists. V-CTRL read on B1 and B1m only.

**Written:** 2026-11-13, `date -u` read 09:06:13Z at the code commit. **To:** Architect. **Spec:** `arch/accept-gate` `4336a281` (§1–§8). **Code:** `qa/same-chain` `980ce3a7`: `tc_lib.py` blob `e5776a5d`, `tc_groups.py` `cdacbc5a`, `tc_score.py` `0882845e`, `tc_analyse.py` `e92c330d`, `tc_selftest.py` `7ee9e6a9`. Local, docs and QA tooling only; no `src/` or `native/` change.

## 1. What is frozen

| item | frozen as |
|---|---|
| instrument | `cf_fbid.py` imported through `cf_uprime.load_instrument` (git blob asserted against `ecc4c5e7`; the blob printed in the groups file); `T_FROZEN` 0.276, `MIN_PRESENT_RATE` 0.80, `NULL_P99_TOLERANCE` 0.03 asserted equal to `cf_uprime`'s; `OVERLAP_HZ` 50 asserted equal to `nrtax_defs`; `band_of` asserted equal to `gr_common`'s on −30…14. Encoder DLL = `libft8.dll`, SHA-256 pinned `1ba8dc3d…db914` (asserted, fail closed) |
| position convention | WSJT-X's frequency and dt (our own are not recoverable, (k) §1); calibration = the instrument's procedure on the first 80 confirmed controls sorted by (stamp, freq): **70 of 80 with sync hit ≥ 0.6, median start − dt = 0.48 s** (`tc_calib.json`) |
| population | the 500 cycles of arm B; WSJT-X-confirmed rows (matchedbatch) of the testable classes (`report`, `report CQ`, from `uprime_arm_a_classes.json`), not hashed, encodable. Confirmed by first-publishing batch: 1: 8,098; 2: 1,215; 3: 103; 4: 2,048; 5: 190. **Not scored** (hashed / untestable class / unencodable): batch 4: 347 / 1,211 / 7; batch 5: 0 / 137 / 0; batch 1: 889 / 5,153 / 21 |
| T_bur (K2, E179) | a T row with another n_ref row of the cycle at \|Δf\| < 50 Hz and SNR ≥ its own (strict, `strongest_neighbour`); T_iso = T minus T_bur |
| groups | **B1** 1,000 random batch-1 rows (seed 20261112, band mix A 326 / B 396 / C 157 / D 121); **B1m** 536 rows band-matched to T by seeded draw per band (A 51, B 162, C 127, D 196; pool A 671 / B 824 / C 318 / D 222); **T4** 483, **T5** 53, **T** 536; **T_bur 267** (A 15, B 90, C 64, D 98); **T_iso 269** (A 36, B 72, C 63, D 98). V-N holds: n(T) 536 ≥ 400, n(T_bur) 267 ≥ 100. Groups file sha256 prefix `c1bb7612dc2ddbbe` (rows carry stamp, index, band, batch, flags; no text) |
| readout / decision | `tc_analyse.py main`: cycle bootstrap B = 2000 seed 20261112 over the 500 cycles, B1 / B1m / T resampled jointly; PR_std(T_iso) over the bands where both T_iso and T_bur have ≥ 10 rows, weights = T_bur's band mix; decision `tc_lib.decide` = Amendment 1's A1.2 table, first match wins (VOID, BLIND, BLIND-BURIED, WEAK-ROW, SOUND, BETWEEN); a replicate with an empty band in the contrast is NaN and counted |
| self-test | `tc_selftest.py`: 6 behaviour tests, **22 of 22 mutations killed** (overlap strictness, "stronger" direction, weaker-neighbour, strongest pick, band edge, draw sorting and seed, short pool, empty replicate, cell floor, weight mix, NaN as 0, every A1.2 row's condition, V-N, the 0.80 bar) |

## 2. V-CTRL and V-NULL, read before any T score (allowed by A1.1)

| row | result |
|---|---|
| **V-CTRL (B1)** | PR = **1.000 [1.000, 1.000]**, 1,000 rows; every band 1.000. CI_lo ≥ 0.80: **passes** (TC-1: yes) |
| **B1m (SNR-matched control)** | PR = **0.998 [0.994, 1.000]**, 536 rows; band A 1.000, B 0.994, C 1.000, D 1.000. CI_lo ≥ 0.80 (TC-6: yes) |
| **V-NULL** | the night's null p99 = 0.2759 against 0.276 (|diff| 0.0001, within 0.03), 100 rows × 20 mismatched sequences |

**So the instrument reads WSJT-X-confirmed batch-1 rows as present at every strength down to band D, at WSJT-X's position.** Note for the reading to come: a control at ceiling (1.000) has no variance, so the control CIs are degenerate; the contrasts (CI_lo of PR(B1m) − PR(T), and of T_iso_std − T_bur) are then driven by T's own variance.

## 3. What was run for plumbing, and what was not

- Analysis plumbing: run once on **random fake target scores** for the target rows (not data), then the fake file and its result were deleted; nothing of it was read as a result.
- **No target row of T4, T5, T_bur or T_iso has been scored.** Next: `tc_score.py tgt` (the batch 2–5 rows, about 900), then `tc_analyse.py main`, each once.
- Not PC-exclusive (no timing); the ctrl stage took 81 s.
