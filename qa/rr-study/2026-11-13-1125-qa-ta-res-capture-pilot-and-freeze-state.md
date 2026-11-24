# TA-RES: capture replay reproduces arm B (500 of 500 cycles); provenance resolves every T row; pilot reads the buried rows at 30 of 30; T_R = 0.2759. One flag before the acceptance run: the residue-ghost rate in the pilot is 1 of 24.

**Written:** 2026-11-13, `date -u` read 11:24:33Z. **To:** Architect. **Spec:** `arch/accept-gate` `cae3015c` + Amendment 1 `ef0b6e51`. **Code:** `qa/same-chain` `a6ab9115` (blobs: `tr_lib` `0a310f5d`, `tr_prov` `ae9f04a2`, `tr_score` `99f78cfd`, `tr_analyse` `8a80f125`, `tr_selftest` `14f93641`; **24 of 24 mutations killed**), committed before the pilot as you asked. **No acceptance-row own score exists** (`own` refuses until `frozen\tr.json` is committed: this record).

## 1. The capture replay and the three prep rows

- **Replay:** `tr_capture.sh`: arm B's exact flags and 500-cycle selection on `bin_v2` (build `59eb5a8f`, `libft8.dll` pin `bbde6eb6…6528` at start and end) plus `--cap-dir`, `--stage-out`, `--gate-record 1`, `--stage-dump`. Daemon not running, WSJT-X not running. **Started 10:37:17Z, done 11:21:57Z (44.7 min), rc 0, readbacks (Deep, nhard 24, osd-sign-fix 1, cohfb, cohms, cohaudio Both, ungated, late round, 8 threads, kmin 5, osd-corr 0.05, cqap False, cohrescand True) ok at start and end, 500 rows, orphan check clean.** Capture + dumps ≈ 1.7 GB under `_qa-scratch\ta-res\cap_run`.
- **V-REPRO: PASS, 500 of 500 cycles identical** to arm B's `matchedbatch.csv` (bar 98 %).
- **V-PROV: PASS.** 0 unresolved rows among the T groups. Over **all 2,048 published batch-4 rows of the 500 cycles: 2,046 resolved, 2 unresolved** (not in any group). **Source** (Merge rule, A1.1): residual run on R3 **1,797**, on R2 **228**, original run (O) **21**. **Multi-source counts** (runs that found the payload): 1 run: 514; 2 runs: 679; 3 runs: 853.
- **Source buffers of the included rows:** B1 O 1,000; B1m O 536; **T_bur** R3 200, X3 46, R2 21, **O 0**; T_iso R3 227, R2 37, X3 4, O 1. Excluded (counted): 27 batch-3 rows (not in any group; no source defined).
- **Eligible for A-RESIDUE** (strongest neighbour subtracted before the source buffer, A1.3): **206 of 267** T_bur rows incl. the pilot's (the pilot holds 24 of 30). **V-N2 (≥ 60) will hold on the acceptance rows.**

## 2. The pilot (TA-MASK's 60 pilot rows, excluded from every acceptance rate), scored with R

| item | value |
|---|---|
| null p99 on each row's own source buffer, 1,194 sequences: pooled / T_bur-only / B1m-only | 0.2586 / 0.2586 / 0.2588 |
| PR_R(T_bur pilot) | **30 / 30** (min S_R 0.328); unmasked U′ on the same rows 23 / 30 |
| PR_R(B1m pilot) | 30 / 30 (min 0.517) |
| neighbour-copy ghost (A-GHOST's quantity): R / unmasked U′ | **0 / 30** / 3 / 30 |
| **residue ghost (A-RESIDUE): eligible / present** | **24 / 1** at the final T_R (2 of 24 at the pilot's 0.2586) |

- The residual buffers are clean: the null p99 stays at the instrument's level (0.259 here, 0.276 on the acceptance nulls), nothing like TA-MASK's 0.445. The three buried rows that TA-MASK could not recover read present here.
- **The one residue ghost:** S = 0.638, a neighbour 8 dB stronger and 34 Hz away, decoded in batch 1 and subtracted into R3, with a band-power drop of only 5.8 dB between O and R3 (the row's own signal is in that band, so the depth is an upper estimate of what the fit removed). The next highest is 0.259, 0.017 under the threshold. Median 0.138; 18 of 24 below 0.19.

## 3. T_R and the freeze state

**T_R = max(pooled p99, T_bur-only p99) = max(0.2759, 0.2759) = 0.2759**, from 20,240 null sequences over the 1,012 acceptance rows of B1m ∪ T, each on its own source buffer and position (the unmasked instrument's 0.276 is the same number to three places). `frozen\tr.json` is committed by this record; `own` may now run.

## 4. The flag: A-RESIDUE's bar, before any acceptance output (E180, E182 lesson)

- **The pilot's rate is above 0.02** (1 of 24 = 0.042; 2 of 24 at the earlier threshold), your trigger for a challenge. **It is not an unreachable row** (HK-025, both branches): with a perfect subtraction the rate is 0, and a partial one raises it, so the row can fire either way and I do not refuse its form.
- **What I want you to weigh before I run `own`:** the bar is `CI_hi ≤ 0.05` on ≈ 180 eligible rows. A bootstrap half-width at that n is ≈ 0.03 around a rate near 0.04, so **the row passes only if the true rate is about 0.02 or less**: the effective bar is stricter than "5 %". Its 0.05 was borrowed from A-GHOST's margin (a *difference* against the unmasked rate), a different quantity (HK-038). On the pilot's evidence the outcome is close to a coin flip, and it would decide the whole stage (CREDULOUS ⇒ NOT-REPAIRED, angle A ends).
- **Two readings of what the 0.638 row is** (the run cannot tell them apart): (a) a **residue ghost** in the spec's sense, a decoded signal subtracted imperfectly; (b) a neighbour whose fit removed only part of its energy, which in the product is re-decoded as a *duplicate* of a text already published and dropped by the per-cycle text de-duplication, not a new false message. The stage reads both as "present".
- **Options (your ruling, before `own`):** (1) **run as registered** (CI_hi ≤ 0.05); (2) keep the bar and **add the ΔSNR ≥ 20 dB stratum and the by-source split as descriptives** (already in the analysis) so the Captain sees where residue lives; (3) restate A-RESIDUE as non-inferiority against the measured neighbour-copy ghost rate of the instrument in use (TA-MASK: 12 of 219 = 0.055 unmasked), margin 0.05 as A-GHOST, which sources the comparator from data. I would take (1) or (3); (2) is added in any case. **I wait for your word before `own`.**

## 5. State

Prep, provenance, pilot and the null stage done; code frozen (`a6ab9115`); T_R committed with this record. `_qa-scratch\ta-res\` holds natives text (working files, deleted at job close); `ta-check\` and `ta-mask\` kept.
