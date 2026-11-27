# KNOWN-ERASURE: ignore a decoded neighbour's tones when reading a weak signal's bits

**Date:** 2026-11-27 · **Author:** QA · **Spec:** `docs/decoder-rebuild/spec-known-erasure.md` (Architect, `arch/decoder-rebuild` `50c86605` and its correction), authorised by the Captain on 2026-11-27 · **Status:** a measurement, no bars; he decides whether it stays. Aggregates only (NFR-021): no message text is read by `ke_analyze.py`; `pf_oo_check.py` reads it inside one function as before.

## Summary

1. **KNOWN-ERASURE does not move the result.** The rate changes by **+0.03 / +0.06 / +0.03 pp** (S40, H40, H20: 88.20 to 88.23, 87.90 to 87.96, 86.28 to 86.31 %); matched **+2 / +5 / +3** decodes of 6,773 / 8,983 / 9,154. `ours_only` -0.04 / +0.01 / 0.00 pp. This is inside the run-to-run churn of the measurement (the run gained 11 / 9 / 7 matched decodes and lost 9 / 4 / 4).
2. **The mask is active, and K2 does not fall.** **64.6 %, 53.5 % and 45.4 %** of the tier-A candidates of rounds 1 to 3 (50 %, 40 %, 29 % in the XC round) had at least one erased bin, yet the K2 count goes **337 to 343, 450 to 444, 527 to 524** (+6 / -6 / -3), and only **6 / 8 / 7** of the baseline K2 targets T (1.3 to 1.8 %) are matched now. Of those 6 / 8 / 7, 5 / 6 / 7 sit in the strong-neighbour bands (3 to 10 and over 10 dB), the Architect's target: a handful of decodes, within the churn.
3. **The free check passes:** the round-0 CAND rows' numeric columns (position, score, a / b code and unsatisfied checks) are identical to the XC-ROUND confirmation runs in every cycle (23,800 / 33,600 / 33,598 rows, 0 cycles differing).
4. **Cost:** CPU per cycle +3.6 / +3.4 / +2.9 % (16.47 to 17.07, 17.31 to 17.90, 17.05 to 17.55 CPU-s); `last_p95` 2,424 / 2,494 / 2,564 ms (was 2,397 / 2,472 / 2,536); 0 abandoned, 0 native errors. The whole-process CPU is noisy (a few percent), so this is an upper-bound-looking figure for a small cost.
5. **QA's reading (the Captain decides): the change buys nothing measurable and costs about 3 % CPU plus an ABI extension (`out_tones`, the known arrays, two counters).** The mechanism the spec rested on (a strong neighbour's leftover tone wins the maximum in T's bin and T's bit is read from it) is either not the limiting factor of K2 or is not removed by erasing +-1 oversampled bin; the Developer's own bit-level test (b) had already shown a modest effect (the weak signal's raw bit errors 478 to 437 over 8 cases, worse when the weak signal is as strong as the known one). The Architect's §5 names the next candidate: subtraction depth for signals at -10 dB or stronger.

## 0. A first replay of this change was VOID (QA's harness, disclosed)

The first replay (run tag `ke`, 16:10 to 16:30 UTC) showed the rate **falling** by 0.40 / 0.59 / 1.02 pp. It was not a property of the change: **QA's harness wrapper (`StageProbeInterop.DecodeLeanXcRound`, four parameters) no longer implemented the interface method once KNOWN-ERASURE gave it a fifth `known` parameter, so every XC-round call landed on the interface's empty default body and the round silently never ran** (the xcRound log group read `fits=0`, 0 ms, 0 decodes, in 216 of 240 cycles; batch 4 was 0 against 51 / 140 / 187). The same hazard QA recorded in the XC-ROUND review, recurring through a signature change. QA fixed the wrapper (`HasXcKnown`), made `ke_analyze.py` refuse a replay whose XC round did no work, rebuilt and **re-ran** (tag `ke2`, 16:30 to 16:54 UTC). **Everything below is the valid replay `ke2`;** the void runs stay on disk as `ke_*` and are not used. The lesson for the record: after any interface or signature change, the first check of a replay is that the changed component did work (here: XC `fits` > 0), not only that the run finished.

## 1. What was run

- **Build:** `feat/known-erasure` `104bc426` (`main` `a1e1c84c` + the change), HK-039 record `qa/rr-study/2026-11-27-qa-code-review-known-erasure-104bc426-APPROVED.md`. Harness `Ft8.FitProbe` from a clean checkout of the sprint branch with `HasLean`, `HasProbe`, `HasXcRound`, `HasXcKnown` and the usual flags. **`libft8.dll` SHA-256 `12444634b1882c3634bc04d7c8e088a68a1c8ea7cb62e749270db7fe32a0bfc0` = the Developer's reported hash = the runner's pin** (asserted), shim 20260083. No `--filter` (a replay).
- **Arm and slices:** the XC-ROUND arm: lean, 16 threads, effort normal, `--lean-probe 1`, LC-BASE's L flags with the cross-cycle stage on; S40 (170 cycles), H40 and H20 (240 each), one after another on the otherwise idle PC. **Baseline: the XC-ROUND confirmation runs on disk** (`xn_*`, build `f9662335`, shim 20260082); the two `sel.json` files are equal.

## 2. Table 1

| Slice | Arm | matched | ours | rate % | ours_only % |
|---|---|---:|---:|---:|---:|
| S40 | lean with XC-ROUND (baseline `xn`) | 5974 | 6297 | 88.20 | 4.77 |
|  | **lean with KNOWN-ERASURE** | 5976 | 6296 | **88.23** | 4.73 |
|  | **effect** | +2 | -1 | **+0.03 pp** | -0.04 pp |
|  | lean minus classic (84.39) |  |  | +3.84 pp |  |
| H40 | lean with XC-ROUND (baseline `xn`) | 7896 | 8605 | 87.90 | 7.89 |
|  | **lean with KNOWN-ERASURE** | 7901 | 8611 | **87.96** | 7.90 |
|  | **effect** | +5 | +6 | **+0.06 pp** | +0.01 pp |
|  | lean minus classic (85.29) |  |  | +2.66 pp |  |
| H20 | lean with XC-ROUND (baseline `xn`) | 7898 | 8641 | 86.28 | 8.12 |
|  | **lean with KNOWN-ERASURE** | 7901 | 8644 | **86.31** | 8.12 |
|  | **effect** | +3 | +3 | **+0.03 pp** | 0.00 pp |
|  | lean minus classic (81.25) |  |  | +5.06 pp |  |

Batch 4 (the XC round, now with its own erased bins): 52 / 137 / 188 decodes (51 / 140 / 187 before). 0 abandoned cycles, 0 native errors, 0 XC-round errors.

## 3. K2 by dSNR band (CS-MAP's bands: the neighbour's SNR minus T's) and the baseline K2 T now matched

| Slice | band | K2 before | K2 after | baseline K2 T now matched |
|---|---|---:|---:|---:|
| S40 | weaker by > 3 dB | 4 | 4 | 0 |
|  | within +-3 dB | 42 | 42 | 1 |
|  | stronger by 3 to 10 dB | 121 | 125 | 1 |
|  | stronger by > 10 dB | 170 | 172 | 4 |
|  | **all** | **337** | **343** | **6** |
| H40 | weaker by > 3 dB | 9 | 9 | 0 |
|  | within +-3 dB | 62 | 60 | 2 |
|  | stronger by 3 to 10 dB | 199 | 196 | 5 |
|  | stronger by > 10 dB | 180 | 179 | 1 |
|  | **all** | **450** | **444** | **8** |
| H20 | weaker by > 3 dB | 10 | 10 | 0 |
|  | within +-3 dB | 85 | 85 | 0 |
|  | stronger by 3 to 10 dB | 281 | 280 | 2 |
|  | stronger by > 10 dB | 151 | 149 | 5 |
|  | **all** | **527** | **524** | **7** |

(The universe is the same definition each time: a crowded WSJT-X decode that lean missed, its nearest neighbour decoded, a failed candidate at T and none that decoded.) **Knock-on and losses:** matched gained **11 / 9 / 7**, lost **9 / 4 / 4**; of the gains **6 / 8 / 7** are baseline K2 cases and **5 / 1 / 0** are outside them.

## 4. Cost and the erased-bin share

| Slice | CPU-s per cycle (before, after, change) | `last_p95` ms (before, after) | tier-A candidates with an erased bin: rounds 1 / 2 / 3 / all of 1-3 | XC round | all residual rounds |
|---|---|---|---|---|---|
| S40 | 16.47, 17.07, **+3.6 %** | 2,397, 2,424 | 63.2 / 67.1 / 63.7 / **64.6 %** (of 42,801) | 50.0 % (of 3,177) | 63.6 % |
| H40 | 17.31, 17.90, **+3.4 %** | 2,472, 2,494 | 51.4 / 57.8 / 50.1 / **53.5 %** (of 59,106) | 40.3 % (of 6,788) | 52.1 % |
| H20 | 17.05, 17.55, **+2.9 %** | 2,536, 2,564 | 44.1 / 48.3 / 45.3 / **45.4 %** (of 54,666) | 29.2 % (of 8,572) | 43.2 % |

A candidate counts as erased when any of the 8 tone bins of any of its 58 data symbols is marked. The share is large because the candidates of a residual round are, by construction, those in the patch windows around signals that were just subtracted.

## 5. The decodes this change added (`pf_oo_check.py xn ke2`)

Too few to say anything: **3 / 3 / 5 unconfirmed** and **11 / 9 / 7 confirmed** additions (against 6 / 2 / 5 unconfirmed and 9 / 4 / 4 confirmed decodes of the baseline that disappeared). The repeat shares (0 of 3, 1 of 3, 4 of 5 for the unconfirmed) rest on a handful of decodes and carry no information.

## 6. The Architect's predictions, read mechanically (the ledger is his)

| # | Prediction | Result |
|---|---|---|
| ER-1 | S40 rate +0.20 pp or more | +0.03: **miss** |
| ER-2 | H20 rate +0.30 pp or more | +0.03: **miss** |
| ER-3 | K2 falls on all three slices | +6 / -6 / -3: **miss** (S40 rises) |
| ER-4 | `ours_only` rises by no more than 0.30 pp on every slice | -0.04 / +0.01 / 0.00: **hit** |
| ER-5 | CPU per cycle rises by no more than 5 % on every slice | +3.6 / +3.4 / +2.9 %: **hit** |
| ER-6 | the free check passes | 0 cycles differing: **hit** |

## 7. What this does and does not say

- It says the change, as specified (+-1 oversampled bin, -10 dB threshold, median replacement, tier A and CQ-AP, rounds 1 to 3 and the XC round), does not recover the missed weak signals: the K2 count is unchanged and the baseline K2 targets are decoded in 1.3 to 1.8 % of cases, with a mask that touches about half of the residual-round candidates.
- It does **not** say that no erasure design could work: the width (`FTZ_ERASE_FREQ_HALFWIDTH`), the -10 dB threshold and the median replacement were not varied (one run). The Developer's scratch trial of widths 2 and 3 on synthetic signals did not help either, which is evidence, not proof, for the real audio.
- It does **not** show why: the replay measures outcomes, not the bits. Two readings are open: the strong leftover is not what blocks T (the leak is wider, or T's own SNR is the limit), or T is blocked by something the mask does not remove (the noise, the other neighbours, the window leakage of T itself).
- **Remaining if the Captain drops it:** `feat/known-erasure` is not merged anywhere on `main`; QA's sprint branch carries a merge of it and would be rebuilt without it. The Architect's §5 lever is subtraction depth for signals at -10 dB or stronger (they stop 4 to 6 dB short of the noise ceiling).

**Reproduce:** `python -I qa/decoder-rebuild/ke_analyze.py ke2` (writes `ke_analyze.json`), `python -I qa/decoder-rebuild/pf_oo_check.py xn ke2` (`oo_check_xn_ke2.json`); the outputs are beside this note.
