# #122 gate 4a: offline truncation replay. Engineer's report to the Architect

> **Every figure below is: Descriptive. From gate 4a, whose V2 failed on P (1 074/1 075; R, X17, X80 N/N); released by the Captain's decision, not a gate PASS.**

- **From:** Engineer (owner). **To:** Architect. cc QA, Captain. **Written:** 2026-10-03 ~14:40Z (`date -u`).
- **Spec:** `qa/rr-study/2026-10-03-1015-architect-to-qa-spec-122-gate4a-truncation-replay.md` with Amendment 1 (`45c1d016`). **Ruling:** `…-1420-architect-122-gate4a-v2-fail-ruling.md` (§4a: the Captain's release, 14:22Z).
- **Branch:** `eng/122-gate4a`, local, not pushed. Harness `9dd89f3f` (pre-registration, before the first decode), Amendment 1 code `4badd599`, TR5 wording `7690689d`, diagnostic code `c390681d` (not run). `git diff --stat -- src/ native/`: empty. Built on `main` `e2fdd446` (merge `6e055079`).
- **Run:** 11:39:10Z to before 14:17Z (`date -u`). Eight arms, one process each, all exit 0. Outputs: `artefacts/20261003_1139_122_gate4a_truncation_replay/`. Analyser output: `…/analysis_released.txt` (command `python analyse_trunc.py --released`, then `python analyse_trunc.py`, which stops at V2, as registered).
- **Aggregates only (HK-037).** No message text was written anywhere.

## 1. Verdicts as registered (not rewritten)

| Row | Result |
|---|---|
| V0 inputs | PASS. `libft8.dll` SHA-256 `ee00d118…ff990e4c` read back at the start and end of all eight arms (`dllMatch=True` ×16). Flag OFF and `nhard` 40 read back. List SHAs equal the frozen SHAs. Parent SHA `55a951c8…53c977cf` |
| V1 cut placement | PASS. Asserted in-process before every cut decode; a failure would have exited 3. All exits 0 |
| **V2 final decode undisturbed** | **FAIL on P: 1 074 of 1 075 cycles identical.** R 720/720, X17 464/464, X80 497/497. The one cycle: `261001_112700`, list position 956; F has 16 decodes, T has 15; the single difference is 1 731 Hz, DT 0.9, SNR −11, present in F and absent in T |
| V3 stability | PASS. 0 exceptions, 0 non-zero exits, 0 warnings in all eight runs |
| V4′ (Amendment 1) | **PASS on all four corpora** (table in §2) |
| V4 as first registered | FAIL on all four, labelled *superseded by Amendment 1; reported, not used* |
| V5 window alignment | PASS on all four. Median DT(OpenWSFZ − WSJT-X) of corroborated pairs: P 0.7, R 0.7, X17 0.6, X80 0.7 s |
| **TR5** | **MISS** (V2 on P; and on the original V4 as well). Scored by the Architect, as registered |

## 2. V4′ per corpus (positive control)

| Corpus | C(0.5) | C(4.0) | D = C(0.5) − C(4.0), 95 % CI | (i) C(4.0) ≤ 0.98 | (ii) CI lower bound > 0 | V4′ | old V4 (≥ 0.20 gap) |
|---|---:|---:|---|:--:|:--:|:--:|:--:|
| P | 0.995 | 0.843 | 0.152 [0.145, 0.160] | yes | yes | PASS | FAIL (gap 0.152) |
| R | 0.994 | 0.828 | 0.166 [0.156, 0.175] | yes | yes | PASS | FAIL (gap 0.166) |
| X17 | 0.993 | 0.843 | 0.150 [0.140, 0.161] | yes | yes | PASS | FAIL (gap 0.150) |
| X80 | 0.996 | 0.868 | 0.128 [0.110, 0.147] | yes | yes | PASS | FAIL (gap 0.128) |

The instrument sees a loss at the 4.0 s control on every corpus. The signature V4′ guards against (C(x) = 1.000 at every x) is absent.

## 3. Catch C(x) and spurious decodes (per corpus; 95 % block-bootstrap CIs, blocks of 10 cycles, B = 10 000, seed 20261003)

`S_corr` / `S_unc`: unmatched early decodes, per 100 arm-F decodes, that the live WSJT-X did / did not also decode in that cycle.

**P (1 075 cycles, 20 175 arm-F decodes)**

| x (s) | C(x) [CI] | S_corr /100 [CI] | S_unc /100 [CI] | median SNR shift (dB) | t(x) med / p95 (ms) | G(x) (s) |
|---:|---|---|---|---:|---|---:|
| 0.5 | 0.995 [0.994, 0.996] | 0.45 [0.36, 0.55] | 0.31 [0.24, 0.39] | 0 | 538 / 602 | 0.50 |
| 1.0 | 0.991 [0.990, 0.993] | 0.87 [0.75, 0.99] | 0.27 [0.20, 0.35] | 1 | 545 / 606 | 0.99 |
| 1.5 | 0.989 [0.987, 0.990] | 1.29 [1.12, 1.47] | 0.35 [0.28, 0.43] | 2 | 549 / 607 | 1.49 |
| 2.0 | 0.984 [0.982, 0.986] | 0.96 [0.81, 1.11] | 0.30 [0.22, 0.38] | 1 | 527 / 601 | 2.01 |
| 2.5 | 0.963 [0.959, 0.967] | 0.53 [0.43, 0.64] | 0.22 [0.16, 0.29] | −2 | 434 / 573 | 2.60 |
| 4.0 (control) | 0.843 [0.835, 0.850] | 0.54 [0.43, 0.66] | 0.06 [0.03, 0.10] | −10 | 284 / 412 | n/a |

Full decode `t(0)` median / p95: 534 / 602 ms.

**R (720 cycles, 13 018 arm-F decodes)**

| x (s) | C(x) [CI] | S_corr /100 [CI] | S_unc /100 [CI] | median SNR shift (dB) | t(x) med / p95 (ms) | G(x) (s) |
|---:|---|---|---|---:|---|---:|
| 0.5 | 0.994 [0.992, 0.995] | 0.42 [0.32, 0.53] | 0.26 [0.18, 0.34] | 0 | 539 / 615 | 0.48 |
| 1.0 | 0.992 [0.991, 0.994] | 0.64 [0.49, 0.79] | 0.25 [0.18, 0.33] | 1 | 543 / 617 | 0.98 |
| 1.5 | 0.990 [0.988, 0.992] | 0.75 [0.58, 0.94] | 0.22 [0.14, 0.30] | 2 | 544 / 616 | 1.48 |
| 2.0 | 0.983 [0.981, 0.985] | 0.58 [0.45, 0.73] | 0.22 [0.15, 0.30] | 1 | 513 / 600 | 2.01 |
| 2.5 | 0.957 [0.953, 0.961] | 0.33 [0.25, 0.42] | 0.17 [0.10, 0.24] | −2 | 383 / 556 | 2.64 |
| 4.0 (control) | 0.828 [0.819, 0.838] | 0.54 [0.41, 0.67] | 0.10 [0.05, 0.16] | −10 | 252 / 348 | n/a |

Full decode `t(0)`: 524 / 587 ms.

**X17 (464 cycles, 6 793 arm-F decodes; 17 m, 2026-08-08, older build and USB CODEC device; cross-band). ⚠️ Timing figures carry the label in §5.**

| x (s) | C(x) [CI] | S_corr /100 [CI] | S_unc /100 [CI] | median SNR shift (dB) | t(x) med / p95 (ms) | G(x) (s) |
|---:|---|---|---|---:|---|---:|
| 0.5 | 0.993 [0.991, 0.995] | 0.40 [0.25, 0.57] | 0.19 [0.10, 0.29] | 0 | 528 / 610 | 0.52 |
| 1.0 | 0.993 [0.991, 0.995] | 0.53 [0.36, 0.71] | 0.29 [0.18, 0.42] | 1 | 530 / 612 | 1.01 |
| 1.5 | 0.990 [0.987, 0.992] | 0.72 [0.52, 0.93] | 0.43 [0.29, 0.57] | 2 | 536 / 609 | 1.51 |
| 2.0 | 0.988 [0.985, 0.990] | 0.68 [0.47, 0.90] | 0.41 [0.29, 0.55] | 1 | 488 / 586 | 2.06 |
| 2.5 | 0.960 [0.955, 0.966] | 0.38 [0.22, 0.59] | 0.24 [0.11, 0.39] | −2 | 351 / 528 | 2.69 |
| 4.0 (control) | 0.843 [0.832, 0.853] | 0.31 [0.18, 0.45] | 0.06 [0.01, 0.12] | −10 | 201 / 298 | n/a |

Full decode `t(0)`: 543 / 699 ms.

**X80 (497 cycles, 1 927 arm-F decodes; 80 m, 2026-08-09, older build and USB CODEC device; cross-band; a thin corpus, so wide CIs)**

| x (s) | C(x) [CI] | S_corr /100 [CI] | S_unc /100 [CI] | median SNR shift (dB) | t(x) med / p95 (ms) | G(x) (s) |
|---:|---|---|---|---:|---|---:|
| 0.5 | 0.996 [0.993, 0.999] | 0.10 [0.00, 0.26] | 0.36 [0.14, 0.63] | 0 | 88 / 513 | 0.50 |
| 1.0 | 0.994 [0.990, 0.997] | 0.26 [0.05, 0.53] | 0.47 [0.22, 0.73] | 1 | 85 / 524 | 1.01 |
| 1.5 | 0.992 [0.986, 0.996] | 0.31 [0.07, 0.61] | 0.47 [0.18, 0.80] | 1 | 81 / 519 | 1.51 |
| 2.0 | 0.987 [0.981, 0.992] | 0.26 [0.06, 0.48] | 0.36 [0.07, 0.78] | 1 | 77 / 469 | 2.01 |
| 2.5 | 0.960 [0.947, 0.971] | 0.05 [0.00, 0.17] | 0.05 [0.00, 0.17] | −2 | 66 / 302 | 2.53 |
| 4.0 (control) | 0.868 [0.848, 0.887] | 0.21 [0.05, 0.40] | 0.00 [0.00, 0.00] | −11 | 42 / 174 | n/a |

Full decode `t(0)`: 91 / 508 ms.

`G(x) = x + t(0) − t(x)` from medians: a design estimate for this CPU, one process, no other load. It is not a live figure.

**Context for `S_unc`** (the arm-F final decodes' own rate against WSJT-X, so the early decodes' rate can be read against it): arm-F decodes that WSJT-X did not corroborate, per 100 arm-F decodes: P 1.45, R 3.28, X17 2.37, X80 1.82.

## 4. Who is missed (SNR bands and DT bins)

Matched early decodes ÷ arm-F decodes, per band. DT bins carry the label *"OpenWSFZ DT convention, ≈ +0.65 s against WSJT-X's"*. Full tables for x = 1.0 and 2.0 are in `analysis_released.txt`. Highlights:

| Corpus, x | A (≥ 0 dB) | B (−10…−1) | C (−15…−11) | D (≤ −16) |
|---|---:|---:|---:|---:|
| P, 1.0 | 6264/6276 = 1.00 | 7673/7741 = 0.99 | 3381/3414 = 0.99 | 2679/2743 = 0.98 |
| P, 2.0 | 6258/6276 = 1.00 | 7637/7741 = 0.99 | 3344/3414 = 0.98 | 2608/2743 = 0.95 |
| R, 2.0 | 3149/3154 = 1.00 | 5077/5129 = 0.99 | 2690/2733 = 0.98 | 1881/2002 = 0.94 |
| X17, 2.0 | 2026/2029 = 1.00 | 2508/2527 = 0.99 | 1188/1200 = 0.99 | 988/1037 = 0.95 |

At x = 2.0 the weakest band loses the most (D: 0.93 to 0.95 across the corpora). By DT, the late starters lose the most: P at x = 2.0 is 0.80 for DT > 2.5 s (76/95) and 0.90 for 2.0–2.5 s, against 0.99 for the bulk (0.5–1.0 s). Those bins hold few decodes (95 and 205 of 20 175 on P; 14 on X17 at DT > 2.5 s).

## 5. The timing overlap (Architect's point 2, 2026-10-03 ~13:57Z)

- **Overlap:** my 6 unit tests, an analyser dry-run and two commits ran **13:54:17Z to 13:55:48Z** (conservative window), about 90 s of one core on a 16-core machine, during X17-T. Two lighter overlaps earlier: QA's hook-control runs at 11:41:10Z, 11:41:21Z and 11:41:33Z (about 1 s each, arm P-F), and a 5 s CPU probe of Replay81 that I took (before 12:49Z, arm P-F or P-T).
- **Matched check** (X17-T, per call type, inside the window versus the 10 minutes before and after it; `timing_window.py --by-x`), n / median / p95 in ms:

| x | inside | around |
|---:|---|---|
| 4.0 | 27 / 230 / 312 | 292 / 204 / 289 |
| 2.5 | 27 / 371 / 542 | 292 / 362 / 507 |
| 2.0 | 26 / 524 / 593 | 293 / 503 / 576 |
| 1.5 | 27 / 573 / 608 | 293 / 541 / 599 |
| 1.0 | 27 / 557 / 633 | 293 / 535 / 597 |
| 0.5 | 27 / 560 / 626 | 293 / 532 / 596 |
| 0 (final) | 27 / 559 / 610 | 293 / 529 / 587 |

- **Reading:** inside the window the median is higher at every call type, by +9 to +32 ms (+2 % to +13 %). The pattern is consistent in direction, with 26 to 27 samples per cell, so I do not call it noise. Per the Architect's scope ruling, **X17's `t(x)` and `G(x)` are labelled "measured while a ~90 s light overlap ran; medians up to +32 ms inside it"**. `G(x)` is a difference of two medians that rise together, so it moves by less. C(x), S_corr, S_unc and V0–V4′ do not depend on timing and are unaffected. The other corpora (P, R, X80) had only the ~1 s hook controls, on P's arms.

## 6. x* and what the figures say (descriptive)

- **x\*** (largest grid x with C ≥ 0.90 **and** S_unc ≤ 0.10 per 100): **none on P, R or X17**; **2.5 s on X80**. On P, R and X17 the C condition holds at every x up to 2.5 s, and what fails is `S_unc`: its lowest grid value is 0.22 (P), 0.17 (R) and 0.24 (X17) per 100. It is below 0.10 only at the control cut (x = 4.0). On X80, `S_unc` at 2.5 s is 0.05 [0.00, 0.17] on 1 927 decodes, so it is not a firm point.
- **The 0.10 threshold is the spec's, not mine.** For scale, the early decodes' `S_unc` (0.2 to 0.4 per 100) is small against the final decode's own uncorroborated rate (1.45 to 3.28 per 100).
- **Catch:** C ≥ 0.98 for x ≤ 2.0 s on every corpus, 0.96 at 2.5 s, 0.83 to 0.87 at 4.0 s. An early decode at 15 − x s finds nearly everything the full window finds, down to x = 2.0 s.
- **Gain:** `t(x)` is close to `t(0)` for x ≤ 2.0 s (the decode time barely drops until the cut is deep), so `G(x)` is about `x`. The early batch would appear about x seconds earlier.
- **TR1–TR4 and TR6** (for the Architect's scoring, against these figures): C_P(1.0) = 0.991; C_P(2.0) = 0.984; S_unc_P(1.0) = 0.27 per 100; |C_P(1.0) − C_R(1.0)| = 0.001; |C_X17(1.0) − C_P(1.0)| = 0.002 and |C_X80(1.0) − C_P(1.0)| = 0.003 (both pass V5).

## 7. Limits (carried with every figure)

- **V2 failed on P.** One decode in one cycle of 1 075. The cause is not known (§8).
- **Replay is not the live path:** one process, no capture, no residual pass competing for the CPU. A zero-filled window is not a live partial window: noise floor and candidate scores near the cut may differ.
- **Two 40 m nights on the standard chain; one 17 m and one 80 m session on older builds and the USB CODEC device** (cross-band, descriptive, X17/X80's WSJT-X `ALL.TXT` may be contaminated: their S_corr/S_unc split is descriptive only). Every fourth cycle. One station, one decoder build.
- **`C(x)` is a fraction of OpenWSFZ's own final decodes**, not of WSJT-X's and not of what is on the band.
- **Not tested:** the early decode's cost when it runs alongside the previous cycle's residual pass (flag ON).

## 8. Diagnostics D1–D3 (post-registration): NOT RUN

Code committed as `c390681d` and accepted by the Architect. Waiting for the Captain's slot (14:40Z decision). D1 (arm F re-run on P, about 10 min) first; D2 (arm T, about 65 min). When they run, the report will say that D2 compares the early decodes by aggregates and the final decodes by multiset, that D3 cannot separate a native decode difference from a dedup collision unless an early call shows one, and that the harness binary differs from the main run's (additions inactive, same DLL), so a failed D1 is first checked by rebuilding `9dd89f3f`.
