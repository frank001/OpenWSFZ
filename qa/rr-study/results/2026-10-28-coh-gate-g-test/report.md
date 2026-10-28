# COH-GATE-G: TEST result (cycles 401-1,200, joined once after the freeze commit): verdict G-BUILD

Written 2026-10-28T17:16:12Z (`date -u`). Frozen record `36df15b1` (rule R-F4, `BAR_G` 0.5 pp, `U_bar_G` 0.021 on tested_absent only, `h` 0.5), analysis code `d77f3257` (committed before any TEST outcome was read). Spec `1b7445e7` + Amendments 1-2 (`arch/coh-gate-g`). Counts only (HK-037 / NFR-021). Ratification: the Captain's word "go with your recommendations" as quoted by the Architect in section 9 (relayed).

## 1. What was run
PC, station daemon stopped. Build `main` `95e69e87`, `libft8.dll` `1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914` (equal at the start and end), shim 20260071. Replay81 with `--gate-record 1`, Deep, `nhard` 24, OSD sign fix 1, 8 threads, multi-set ON, `coherentFallbackAudio` Both. Night `20260925_2010`, cycles 401-1,200 of the frozen selection `81372df5` (`selection_test.json`, with the warm-up key): **800 cycles, 23,158 WSJT-X decodes (`n_ref`)**, 16:29:07-17:15:14Z, `preflight_end_ok=1`, orphan check clean. Offline admission, matching and the frozen U′ instrument (classes from the TRAIN Original arm) exactly as on TRAIN. **Same night as TRAIN, same band: this is a held-out slice, not a second night.**

## 2. Validity rows
| row | result |
|---|---|
| V2 record complete | PASS exact: offline admission with the existing gate reproduces the product's batch 4 in all 800 cycles |
| V3 identity | PASS: DLL pin at the start and end |
| V4 no abandonment | PASS: fallback abandoned 0; residual pass ran 800, abandoned 0, contained 0 |
| (V1, V5) | TRAIN rows, PASSED (`c75d97f9`) |

Baseline on TEST (the product as it runs): batch 4 published 2,891; WSJT-X decodes corroborated 18,844 of 23,158 = 81.37 %.

## 3. The rows, for R-F4 (admit a GATED_OUT row iff from the residual-audio run; the original run keeps T1)
| quantity | value | 95 % CI (cycle bootstrap, N = 2000, seed 20261028) |
|---|---|---|
| **NET** | **+2.103 pp** (487 more corroborated of 23,158) | **[1.919, 2.299]** |
| ΔU′ tested_absent per cycle | +0.00375 | [0.000, 0.00875] |
| ΔU′ hashed/unencodable per cycle (reported, not barred) | +0.025 | [0.015, 0.036] |
| ΔU′ tested_present per cycle | +0.015 | [0.006, 0.024] |
| ΔU′ untestable class | 0 | |

- **N-GO** (`CI_lo(NET)` 1.919 ≥ 0.5): TRUE. N-STOP false.
- **U-OK** (`CI_hi(ΔU′_ta)` 0.00875 ≤ 0.021): TRUE. U-FAIL false.
- **H-SHARE** (hashed share of admitted 18.4 % ≤ h 0.5): does NOT fire.
- **Verdict: G-BUILD.** (Under reading B, the whole ΔU′ would be +0.029; not adopted by the Captain.)

## 4. Descriptive (gating nothing)
- **Admitted by R-F4:** 522 outputs with a new text, **487 corroborated (93.3 %)**, against the product's own batch-4 corroborated share (about 91 %); all 522 from the residual run. By band A / B / C / D: 3 / 72 / 238 / 209. By `i3`: type 1 453, **type 4 68 (50 corroborated = 73.5 %)**, type 2 1. Hashed text 96 admitted (77 corroborated = 80 %). Non-type-4 admitted rows: 454, 437 corroborated (96.3 %).
- **Per-station clustering of the 487 corroborated additions:** 179 distinct senders, top sender 5.7 %, top five 18.1 %.
- **D1 (the three rules on TEST):**

| rule | NET pp [CI] | ΔU′_ta [CI] | ΔU′_hu | admitted | corroborated |
|---|---|---|---|---|---|
| **R-F4** | +2.103 [1.919, 2.299] | 0.00375 [0.000, 0.00875] | 0.025 | 522 | 487 |
| F1b ≤ 31.18 dB (frozen from TRAIN) | +2.055 [1.872, 2.246] | 0.005 [0.00125, 0.01] | 0.025 | 512 | 476 |
| no gate (= D4, the TEST ceiling) | +2.112 [1.926, 2.307] | 0.005 [0.00125, 0.01] | 0.025 | 527 | 489 |

  The three are within 0.06 pp of each other: the original-audio run adds almost nothing beyond R-F4 (5 outputs more with no gate, 2 more corroborated).
- **D5 shrinkage:** TRAIN NET +1.905 pp, TEST +2.103 pp, ratio 1.10 (no shrinkage; GG-6 "TEST NET ≤ 0.8 × TRAIN NET" is FALSE).

## 5. Reading, limits, and what the verdict authorises
- The gain is established well above the bar on a held-out slice of the same night, and the cost on the barred class is small. Gain and cost are the same order on TRAIN and TEST.
- **It is one night, one band, one machine, one slice split.** The bars are on tested_absent only; the 0.025 per cycle hashed/unencodable cost is not testable by the instrument and is shown, not barred. The type-4 admitted rows are less often corroborated (73.5 %) than the rest (96.3 %); there are 68 of them in 522.
- **A G-BUILD verdict authorises only a build spec for R-F4 (Developer, HK-011), whose acceptance includes the R-F4 rows on one second night (A2.4).** No default change.
- **Second-night candidate (QA's proposal):** `20261022_1949_endurance_run-gathered` (2,927 WAVs, WSJT-X `ALL.TXT` present). Neither T1's tuning night (`20261004_1634`) nor Q-GATE-2's (`20261019_1905`), and it is the most recent night in the inventory. Other nights with WSJT-X `ALL.TXT` and WAVs: `20260922_2056`, `20260923_1730`, `20260930_1930`, `20261009_1752` (the latter two were not checked for a WSJT-X reference of the same band). The residual fallback audio is a decoder feature and is available offline on any night.
- Scratch `D:\Projects\claude\_qa-scratch\coh-gate-g\` and `\gap-relocate\` hold message text and are deleted at job close.
