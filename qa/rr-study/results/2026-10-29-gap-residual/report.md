# GAP-RESIDUAL: how much of GAP-RELOCATE's class N can be decoded on the audio after subtraction?

**Date:** 2026-10-29T17:42:33Z (`date -u`) · **From:** QA · **Spec:** `arch/gap-residual` `74a38158` + Amendment 1 section 9 `ea7496d1` · **Captain's go:** "run the pilot first", then "go" (2026-10-29)
**Build:** `main` `c2c85c45` (v0.67), R-F4 setting absent (OFF); an ON arm (`decoder.coherentFallbackResidualUngated` = 1) tags rows only. `libft8.dll` SHA-256 `1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914` = the station pin, at the start and end of both arms (and by the forced-leg loader).
**Corpus:** night `20260925_2010`, GAP-RELOCATE's 400 cycles in its order (`selection400.json`, sha `42e09239…`), n_ref = 12,124. Populations M (2,193), N (1,860), K and U are GAP-RELOCATE's, frozen. PC; the station daemon stopped.
**Forced legs:** GAP-RELOCATE's own code (`gr_forced.force_cycle`, frozen δ_p 0.6 s, δ_c 0.7 s, the same comparator); only the PCM argument changed (the captured R2 and R3 buffers). Capture: a `qa/`-only extension of Replay81 (`StageProbe.cs`); nothing under `src/` or `native/` changed.
Aggregates only. No callsign or message text in this report. Working files (buffers, native dumps) are in `D:\Projects\claude\_qa-scratch\gap-residual\` and are deleted at job close.

## Result in one paragraph

**ROW 0 passes in full, so the study stands.** Of the 1,860 class-N rows (15.341 pp), **271 (2.24 pp) are decodable on a buffer the product itself produces**: RC 133 (1.097 pp), RG 51 (0.421 pp), RW 77 (0.635 pp) and RP-search 10 (0.082 pp); RP-native is 0. **1,589 rows (13.106 pp [12.49, 13.71]) are NR**: not decodable by any extractor we have, at the right place, on the original audio or on R2 or R3. **R-RC and R-NR fire; R-RP does not.** Of the 261 RC + RG + RW rows, **153 (58.6 %) were never offered to the fallback** a candidate within its search window (55.2 % at the wider window), so the lever question is the one the spec names. NR is not a floor (section 5).

## ROW 0 (strict order; all pass)

| row | check | result |
|---|---|---|
| 0a | DLL pin at start and end of each arm and of the forced legs | PASS (`1ba8dc3d…`) |
| 0b | OFF arm with the capture on reproduces GAP-RELOCATE's BOTH arm | **PASS, exact: `matchedbatch.csv` and the full decode dump are byte-identical** (10,133 lines each); batch 4 published **1,350**; corroborated **9,931 / 12,124**; run counts per cycle identical. One process, GAP-RELOCATE's order |
| 0c(i) | `DecodeAll` call count per cycle, from `RunCore` | PASS: O in 400 / 400. 3 calls in the 382 cycles where the third pass ran, 2 in the 18 `skipped-no-new` (no third `DecodeAll` when nothing is re-encodable). Third-pass outcomes: ran 382, skipped-no-new 18, abandoned 0, failed 0. R3 is taken only where the outcome is `ran` |
| 0c(ii) | `F`'s PCM is byte-identical to the product selector's choice | PASS in 400 / 400: level R3 in 382, R2 in 18, O in 0. In all 400 `Both` cycles the **second** `CohFallbackRun` reads O byte for byte |
| 0c(iii) | offline `DecodeAll` on the captured buffers reproduces the native results | PASS: separate process, hash state restored; 400 O + 400 R2 + 382 R3 = 1,182 calls, **0 mismatches** (freq, dt, SNR, count and text compared inside the function, exact) |
| 0d | `P_ctrl,R` per stratum, non-pilot 360 cycles, bar 0.90 | PASS, see below. Pilot first (40 cycles): (i) 50 / 50, (ii) 9 / 9, no STOP |
| 0e | original buffer | **Implied**: O is byte-identical to the WAV PCM in 33 / 40 pilot cycles, the other 7 differ by under 1.2e-7 relative; the forced legs on O give GAP-RELOCATE's class for **221 / 221** (1.000, bar 0.98) |
| 0f | no abandonment, both arms | PASS: 0 residual abandoned, 0 contained, 0 third-pass abandoned or failed, 0 fallback lines with `abandoned>0` (OFF and ON) |

**One adaptation, stated:** the native `DecodeAll` result carries freq, dt, SNR and text but no payload bytes, so 0c(iii) compares those and the count exactly (the hash state is restored, so the text is deterministic) instead of payload bytes. It is stricter in the fields it has and no looser in any.

### 0d in detail (K rows, 360 non-pilot cycles; legs on R2 ∪ R3)

| stratum | validates | n | recovered | P | Wilson 95 % |
|---|---|---:|---:|---:|---|
| (i) batch 2 / 3 K rows | primary leg | 284 | 273 | **0.961** | [0.932, 0.978] |
| (ii) residual-only fallback K rows | coherent legs (V3 any gate ∪ walk) | 92 | 84 | **0.913** | [0.838, 0.955] |

Both strata are at or above 0.90, so no leg family is "not established". Descriptive, not judged (all rows of the tags in the 360 cycles, not only K): (i) 1,243 / 1,277 = 0.973 [0.963, 0.981]; (ii) 404 / 460 = 0.878 [0.845, 0.905]. **Stratum (ii) is the thinnest** in both views; its K figure clears the bar by 1.3 pp with a lower interval bound of 0.84.
- Bands (union of legs): A 0.938 (n 16), B 0.937 (126), C 0.955 (111), D 0.984 (123); no band with n ≥ 50 is below 0.80.
- REF-SNR terciles (cut points **frozen from the N rows before any forcing**: −18 and −12 dB): 1 (≤ −18) 0.989 (n 91), 2 0.965 (115), 3 0.935 (170); none below 0.80, none empty. Control SNR range −24 to +13 dB, N rows −24 to +17 dB (the control has no row above +13 dB; terciles 1 to 3 are all covered).
- ⇒ **NR? = 0**: no NR row is marked "not established".

## Positive control for the RP-native check (HK-026)

The RP-native predicate reads the captured `DecodeAll(R2 / R3)` output. To show the check is not blind, I ran it on rows the product certainly decoded there: **334 of 334 K batch-2/3 rows are found in the captured native results**, while 11 of 225 sampled batch-1 rows are (batch-1 signals are mostly subtracted away). The check discriminates, so RP-native = 0 is a real zero.

## D1-R: the split of class N (adds to 1,860), pp of n_ref = 12,124

| class | rows | pp | 95 % CI (bootstrap of the 400 cycles) |
|---|---:|---:|---|
| RP-native (in the product's own `DecodeAll(R2/R3)` output, lost afterwards) | 0 | 0.000 | [0.000, 0.000] |
| RP-search (primary decodes it on R2/R3 at the right place, the product's search did not) | 10 | 0.082 | [0.034, 0.136] |
| RC (V3 matches, F1b ≤ T1, publishable) | 133 | 1.097 | [0.910, 1.277] |
| RG (V3 matches, F1b > T1, gated out) | 51 | 0.421 | [0.309, 0.540] |
| RW (walk only) | 77 | 0.635 | [0.505, 0.777] |
| **NR** | **1,589** | **13.106** | **[12.488, 13.708]** |
| RC + RG + RW | 261 | 2.153 | [1.914, 2.407] |

**Whole map restated (adds to M = 2,193):** P 8, FP 10, FC 26, G 87, FCw 38, U 164 (GAP-RELOCATE), plus N split as above (RP-native 0, RP-search 10, RC 133, RG 51, RW 77, NR 1,589).

- **D2-R:** the 10 RP-search rows: 4 centre cell, 6 neighbour only.
- **D3-R (band A, B, C, D):** RP-search 0, 1, 2, 7; RC 0, 10, 28, 95; RG 4, 32, 12, 3; RW 3, 27, 22, 25; NR 67, 381, 405, 736.
- **D4-R (load quintiles, edges 23 / 28 / 33 / 37):** NR 163, 231, 275, 350, 570; RC 11, 17, 24, 25, 56; RG 2, 1, 10, 15, 23; RW 9, 3, 19, 22, 24; RP-search 0, 0, 2, 4, 4. NR rate q1 to q5, standardised: 0.117, 0.122, 0.126, 0.137, 0.142. **Descriptive; not a DENSITY result** and not re-scored.
- **D5-R, `F_wrong`:** R2: primary 9, V3 19, walk 9; R3: primary 8, V3 18, walk 7. **W rows** (N rows with `F_wrong` on the original audio, 95): 31 recovered here (32.6 %), against 240 of the other 1,765 N rows (13.6 %). So the "another transmission dominated the cell, subtraction exposed it" reading holds directionally.
- **D6-R (candidate offered, window ±2 Hz / ±0.12 s around the candidate's lattice position; constants asserted against `coherent_fallback.c:68` and `:70` in code):**

| class | n | offered | never offered |
|---|---:|---:|---:|
| RC | 133 | 19 | **114** |
| RG | 51 | 44 | 7 |
| RW | 77 | 45 | 32 |
| all | 261 | 108 | **153 (58.6 %)** |

  At the wider window (±2.5 Hz / ±0.17 s) the figure is 144 of 261 (55.2 %). Both are at least half. The 153 never-offered rows are **1.262 pp** of n_ref (descriptive).
- **D7-R (RG rows' F1b against T1 = 17.552 dB):** 51 rows, median 20.34 dB; 10 within 1 dB above T1, 26 within 3 dB.
- **Per-station clustering** (rows / distinct senders / top sender share / top-5 share): RC 133 / 90 / 4.5 % / 17.3 %; RG 51 / 36 / 9.8 % / 31.4 %; RW 77 / 55 / 5.2 % / 19.5 %; RP-search 10 / 9 / 20 % / 60 %; NR 1,589 / 341 / 2.1 % / 9.6 %. No class is a few senders' output, except the very small RP-search.

## D8: the ON arm (R-F4 setting on), tag only

The ON arm (400 cycles, 17:18Z to 17:42Z; every fallback line carries `ungated=`; 0 abandoned) **publishes, outcome-matched, 90 of the 1,860 N rows: RG 44, RW 25, RC 6, NR 15.** D1-R with those rows removed: RP-search 10, RC 127, RG 7, RW 52, NR 1,574 (RP-native 0).
- RG 44 of 51 equals the 44 RG rows that D6-R finds "offered": R-F4 already collects the gated-out rows the fallback is offered.
- **Fifteen rows this study classes NR are published by the ON arm.** The forced legs at REF + δ miss rows the product does publish (75 of the 90 ON-published N rows are in RC / RG / RW; 83 %). NR is therefore an upper bound on "undecodable", not a measure of it.

## Routing rows (section 5, as amended; BAR_L = 0.5 pp; 95 % bootstrap of the 400 cycles, B = 2000, seed 20261029; no multiplicity adjustment)

| row | predicate | measured | fires |
|---|---|---|:---:|
| **R-RP** | CI_lo(RP-search) ≥ 0.5 pp | 0.082 pp, CI_lo 0.034 | **no** |
| **R-RC** | CI_lo(RC + RG + RW) ≥ 0.5 pp | 2.153 pp, CI_lo **1.914** | **yes** |
| **R-NR** | CI_lo(NR − NR?) ≥ sum of the point estimates of RP, RC, RG, RW | NR 13.106 pp, CI_lo **12.488** (NR? = 0) against a sum of 2.235 pp (RP-native + RP-search + RC + RG + RW) | **yes** |
| R-0 | none of the above | | no |

- **R-RC wording (A1.3):** "never offered" is 153 of 261 (58.6 %; 55.2 % at the wider window): at least half in both windows, so the lever question is **give the fallback's residual run a candidate list from the residual buffers** (today it reuses the original audio's list). By class, the never-offered rows are mostly RC (114 of 133 = 86 %); RG (7 of 51) is largely collected by R-F4 already, and RW is 32 of 77. **Upper bound** on what such a lever could buy: the 153 never-offered rows, **1.262 pp** (all 261: 2.153 pp). It is an upper bound: the product also needs the candidate, and a looser path admits wrong payloads (U′ watch in any lever arm; `F_wrong` is non-zero on both buffers).
- **R-NR:** most of N (13.1 of 15.3 pp) is not reachable by any extractor we have on any buffer the product produces. 🛑 **Not a floor:** better subtraction would produce different buffers, and this instrument cannot see them (HK-026); the D8 fifteen rows show it also misses rows the product publishes. The Captain decides: stop the decode-rate programme, or commission an oracle-subtraction instrument (named, not specified).
- **R-RP not fired:** the product's residual search misses only 10 rows (0.08 pp) that the primary decoder can decode there; RP-native is 0 (no post-decode loss of a row the product's `DecodeAll` already had).

## Architect predictions (facts only; scoring is the Architect's at ruling time)

RR-1 ROW 0 passed; the one adaptation is the 0c(iii) field set above. RR-2 `P_ctrl,R` ≥ 0.90 on the pilot: yes (50 / 50, 9 / 9). RR-3 R-RP fires: no. RR-4 R-RC fires: yes. RR-5 R-NR fires: yes. RR-6 never offered ≥ half: yes (58.6 %). RR-7 W rows recovered at a higher rate: yes (32.6 % against 13.6 %).

## What this study does not say

- It forces at WSJT-X's position (REF + δ), so it is an upper bound for every routed class.
- 0d's stratum (ii) is the weakest validation (0.913, lower bound 0.84): the coherent-leg classes (RC, RG, RW, NR for those legs) rest on it.
- No lever is specified or built. Whether to ask for a residual-candidate lever, or to stop, is the Captain's question.
- `F_wrong` is non-zero (R2: 9 / 19 / 9; R3: 8 / 18 / 7), counted per leg and never a success.

## Reproduction

`qa/rr-study/gap-residual-run/`: `gres_arm.sh` (arms; the OFF arm needs `CAPARG=1`, the ON arm `BIN=…\bin_on EXTRA="--ungated 1"`), `gres_row0.py`, `gres_pilot.py`, `gres_main.py force|analyse`; Replay81 `StageProbe.cs` / `Program.cs` (`--cap-dir`, `--cap-recheck`). Filtered-suite note (HK-022): there is no test suite here; the pins are the DLL SHA-256 pair above and the selection sha.
