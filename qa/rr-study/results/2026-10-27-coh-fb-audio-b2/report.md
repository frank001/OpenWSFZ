# COH-FB-AUDIO: probe (PC) and B2 (Original / Residual / Both), DESCRIPTIVE ONLY

No bar, no verdict, no default change (Architect spec `bc9abc8f` with Amendments 1-3, `fc642fe2` and later; the Captain's decisions of 2026-10-27). Counts only (HK-037): per-decode rows exist only in `D:\Projects\claude\_qa-scratch\coh-fb-residual\`. Written 2026-10-27 21:13Z (`date -u`).

## Set-up (HK-022: what was run)
- **Corpus:** night `20260925_2010`, the first 400 cycles of the frozen selection `81372df5` (`selection400.json`, SHA-256 `66d5af9b…`, warm-up key kept); 400 cycles with WSJT-X rows, sum of WSJT-X decodes W = 12,124. PC, the station daemon stopped, nothing else running (checked before each chain).
- **Settings:** Replay81 `--mode three1 --nhard 24 --osd-sign-fix 1 --threads 8 --cohfb 1 --cohms 1` (Deep, multi-set ON); `libft8.dll` SHA-256 `1ba8dc3d…db914` re-hashed OK at the start and end of every arm.
- **Probe:** build `e5b90320` (`dev/coh-fb-residual`), HK-039 `5e706f65`, R0 PASS; REF = switch unset, RES = `OPENWSFZ_COHFB_AUDIO=residual`. Chain script `probe_chain.sh`.
- **B2:** build `9ef703d0` (`dev/coh-fb-audio`, v0.66), HK-039 `881518b8`, R0 PASS for Original (vs `453d3d02`) and Residual (vs `e5b90320`), Both not covered by R0; built by QA from a clean detached tree; `OpenWSFZ.Ft8.dll` SHA-256 `73f7f2ba…`; arms via `--cohaudio Original|Residual|Both`, mode read back at start and end. Chain script `b2_chain.sh`, all three arms `preflight_end_ok=1`, 0 exceptions, orphan check clean.
- **Instruments:** `cfr_b2.py`, `cfr_desc.py`, `cfr_union.py`, `cfr_uprime_delta.py` (qa/rr-study/coh-multiset-build), mb_analysis's bootstrap unchanged (blocks of 40, B 10,000, seed 20261025); full U' by `cf_uprime.py` (instrument blob `ecc4c5e7`, T 0.276), classes frozen from the Original arm alone and applied unchanged to Residual and Both; no class flag raised.

## Reproducibility
The B2 Original and Residual arms reproduce the earlier probe's REF and RES: 0 of 400 cycles with a different batch-4 payload set, decode counts per cycle equal. The Both arm's batch-4 payloads (1,350) equal the union of the Original and Residual arms' payloads exactly (0 payloads either way).

## B2 table (batch 4 unless stated)
| | Original | Residual | Both | Res − Orig | Both − Res |
|---|---|---|---|---|---|
| batch-4 decodes | 725 | 1,218 | 1,350 | +493 | +132 |
| cycles with a batch-4 publication | 333 | 378 | 386 | +45 | +8 |
| confirmed by WSJT-X | 674 | 1,108 | 1,227 | +434 | +119 |
| not confirmed (Test-B proxy) | 51 | 110 | 123 | +59 | +13 |
| WSJT-X decodes corroborated (all batches), % of W | 77.33 | 80.93 | 81.91 | +3.60 | +0.98 |
| NET pp, difference, with the tool's CI | | | | +3.60 [3.07, 4.13] | +0.98 [0.74, 1.25] |
| NET pp Both − Original | | | | | +4.59 [4.26, 4.92] |
| Bands (n / confirmed / not) B | 15/13/2 | 16/15/1 | 23/21/2 | | |
| C | 125/124/1 | 294/278/16 | 339/323/16 | | |
| D | 585/537/48 | 908/815/93 | 988/883/105 | | |
| A | 0 | 0 | 0 | | |

**Reading Both against the offline union estimate (Amendment 2):** estimate +4.56 pp [4.24, 4.88] (QA, 19:31Z); the build gives +4.59 pp [4.26, 4.92], a gap of 0.03 pp (the estimate's own 3-decode reconciliation gap, 553 vs 556 confirmed). The two agree; there is no large gap.

## Full U' (all batches, cycles with WSJT-X rows, n = 400), the two parts apart (Amendment 3)
| per arm (totals) | Original | Residual | Both |
|---|---|---|---|
| U' per cycle | 0.1275 | 0.2075 | 0.2100 |
| tested_absent (tested against the audio and not found; the only part that may mean false decodes; limited power on the weakest signals, HK-026) | 15 | 37 | 38 |
| hashed / unencodable (cannot be tested) | 36 | 46 | 46 |
| untestable class | 0 | 0 | 0 |
| tested_present (not confirmed by WSJT-X, present in the audio) | 82 | 106 | 118 |

| differences | Res − Orig | Both − Res | Both − Orig |
|---|---|---|---|
| dU' per cycle (paired, tool's bootstrap) | +0.0800 [0.0425, 0.1175] | +0.0025 [0.0000, 0.0075] | +0.0825 [0.0450, 0.1200] |
| tested_absent | +22 | +1 | +23 |
| hashed / unencodable | +10 | 0 | +10 |
| tested_present | +24 | +12 | +36 |

By band (differences; tested_absent / hashed-unencodable / tested_present): Res − Orig: A 0 / −2 / 0; B 0 / −1 / −1; C +4 / +5 / +6; D +18 / +8 / +19. Both − Res: A 0/0/0; B 0/0/+1; C 0/0/0; D +1 / 0 / +11. (Per-arm band totals are in `b2.json`.) For context only, the multi-set's U' bar was 0.021 per cycle; no bar applies here.

## Gate (T1, borrowed on residual audio, not retuned) and the Both contribution
| | Original | Residual | Both |
|---|---|---|---|
| candidates eligible | 64,368 | 64,368 | 64,368 |
| fallback attempts (candidate-runs) | 64,368 | 64,368 | 128,736 |
| CRC-valid | 18,060 | 5,295 | 23,355 |
| F1b computed | 2,524 | 3,980 | 6,504 |
| gated out (F1b above T1) | 1,961 | 2,717 | 4,678 |
| passed T1 and published | 725 | 1,218 | 1,350 |

Both's payload contributions (summed over 400 cycles, publishable payloads before the mapping step): only on the original audio 257, only on the residual 755, on both 598. These sum to 1,610, against 1,350 published; the original run alone shows 855 (725 published), the residual run alone 1,353 (1,218 published). The difference of about 130 per run is consistent across the arms; its cause (the mapping step's plausibility filter and per-cycle text de-duplication) was not separately verified.
Against the earlier offline payload comparison (Original 593 + 132 only, Residual 593 + 625 only): in the build, only-original 257 includes payloads that the residual run gated out (the build publishes them from the original run), so the numbers are not the same quantity.

## Abandonments, cost, margin
- Residual-pass abandoned 0, contained 0, fallback abandoned candidates 0, exceptions 0, in all three arms. Level used (Residual and Both): residual3 382 cycles, residual2 18, residual-unavailable 0.
- Fallback wall time, median / p95 / max (ms): Original 236 / 372 / 552; Residual 308 / 463 / 552; Both 584 / 835 / 1,097.
- Batch-4 publish time max (ms): 4,312 / 4,253 / 4,762. **Minimum margin to the 13 s budget: Original 8,688 ms, Residual 8,747 ms, Both 8,238 ms.** Both runs the fallback twice, and the margin cost against Original is about 0.45 s on this machine and corpus.

## Limits
400 cycles of one night on one machine; no repeat arm; Test-B "not confirmed" is a proxy (the full U' is given above); the zero-power region of the tested_absent test on the weakest signals is not bounded by this run. The sol probe arms were cancelled at the Captain's word and nothing from sol is reported. The 3-decode text-level reconciliation gap in the offline estimate (0.7 %) is carried.
