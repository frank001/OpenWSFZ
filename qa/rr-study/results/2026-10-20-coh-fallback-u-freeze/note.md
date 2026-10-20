# COH-FALLBACK step 3: the OFF arm and the frozen U budget (QA dated note, written BEFORE any ON decode)

- **Stamped:** 2026-10-20, OFF arm 17:25:55Z to 18:20:15Z by `date -u`. No ON decode exists; the Stage 2 build does not exist.
- **Rule (spec section 8 A1.6, confirmed by the Captain 2026-10-20 ~17:25Z, relayed in the Architect's window and recorded in the spec at `3bbfdb4f`):** `U_max` = 0.30 x `U0`, `U0` = the OFF arm's Test-B not-confirmed decodes per cycle, rounded to 3 decimals, frozen here. Rows: U-OK `CI_hi(DeltaU)` <= `U_max`; U-FAIL `CI_lo(DeltaU)` > `U_max`; U-OPEN otherwise. The bar does not move after any DeltaU is seen.

## The OFF arm (full frozen selection)

| item | value |
|---|---|
| Corpus / selection | `20261009_1752`, 1-in-3, 1,211 cycles, selection SHA-256 (LF) `9c20b921240e51f5b4cb28f751d782f78705f155e121ce74ae314e6875d1f4d6` |
| Build | `main` `5229beec` (Replay81 built against it), shim 20260062, OFF (no fallback exists); mode `three1` (batches 1, 2 and the third pass) |
| Settings read back at start and end | subtraction ON, 8 threads of 16 cores, `nhard` 24, `kMinScorePass2` 10, `osdCorrThreshold` 0.10, OSD sign fix 1/1, `decodingDepth` Deep |
| Health | 1,211 cycles, 0 exceptions, 0 abandoned or contained passes |
| Matching | Test B as implemented in `Replay81` (same text, same cycle, |df| <= 10 Hz, one-to-one nearest-first), in-process; counts per batch kind and SNR band A to D |

## `U0` and the frozen `U_max`

- **Not-confirmed per cycle** = for each cycle the sum over batch kinds b1, b2, b3 and bands A to D of (decodes minus corroborated decodes). WSJT-X rows (`ws`) are references, not decodes.
- **One cycle is excluded:** the first selected cycle `261009_175215` has **no WSJT-X reference at all** (`ws` = 0): WSJT-X's own `ALL.TXT` begins at `261009_175245`, so its 27 decodes cannot be corroborated by construction. Every other cycle has a WSJT-X reference (median 26 rows). The same cycle must be excluded from the ON arm and from DeltaU (it is a paired design).

| basis | cycles | `U0` per cycle | `U_max` = 0.30 x `U0` |
|---|---:|---:|---:|
| **FROZEN: cycles with a WSJT-X reference** | 1,210 | **0.2603** | **0.078** |
| for the record: all 1,211 cycles | 1,211 | 0.2824 | 0.085 |

The frozen figure is the smaller (stricter) one. By kind, per cycle: b1 0.2231, b2 0.0322, b3 0.0050. By band (decodes / not confirmed): A 3,354 / 48, B 9,543 / 127, C 5,620 / 71, D 3,032 / 69. Decodes per cycle 17.81; confirmed share 98.5 % of these (not-confirmed 1.46 %).

## Projected DeltaU half-width (A2.4(a)), and the rule it triggers

DeltaU is a PAIRED difference (ON minus OFF per cycle), so the OFF arm alone cannot give its variance. Two bounds, both stated:

| projection | half-width | 2 x half-width | vs `U_max` 0.078 |
|---|---:|---:|---|
| (i) CONSERVATIVE upper bound: the OFF arm's own block-bootstrap CI of the MEAN of `U_off` (blocks of 40 consecutive selected cycles, B 10,000, seed 20261007): [0.2024, 0.3250] | **0.0613** | 0.1226 | `U_max` < 2 x half-width |
| (ii) PAIRED, count-like: the added not-confirmed outputs per cycle are rare events; at the acceptable limit DeltaU = `U_max`, half-width = 1.96 x sqrt(`U_max` / n) with n = 1,210 | **0.0157** | 0.031 | `U_max` >= 2 x half-width |
| (reference) Q-GATE-2's UPC half-width at n = 931 cycles, where the figure was 0.014 | 0.008 | 0.016 | for scale only |

**This note does NOT decide which projection is the right one.** Read literally with (i), A2.4(a) triggers (`U_max` < 2 x half-width) and the matter goes to the Captain before any ON decode; with (ii) it does not. (i) ignores that the pairing cancels almost all of `U_off`'s variance, so it overstates the width; (ii) assumes Poisson-like counts, so it may understate it. QA's reading: the realistic width lies between, and the clean answer is the ON arm itself. The decision of which projection governs the trigger, and whether to take it to the Captain now, is the Architect's. Nothing is run until then, and nothing about the bar changes whichever he rules.

## Limits

One night, one chain (direct USB CODEC); replay, not live; Test B's not-confirmed count is an upper bound on false decodes (hashed `<...>` texts cannot match, so they count as not confirmed in both arms); `U0` is the main-build OFF arm, and the Stage 2 ON arm will be a different build in other respects only through the fallback.

Files (numbers only): `testb_OFF.csv`, `run_OFF.csv`, `third_OFF.csv`, `abandon_OFF.csv`, `outcomes_OFF.csv` (numeric per-decode fields; needed later for A3'), `log_OFF.log`, `u0_freeze.json`.
