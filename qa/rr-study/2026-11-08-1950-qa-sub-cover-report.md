# SUB-COVER (#273): QA report (2026-11-08T19:49:38Z `date -u`). By the registered rule: **BETWEEN** (G273 +0.544 pp [0.422, 0.678]). O-ENC fires, so the bound reads as ">=", and the #273-proper stratum was NOT tested

Spec `arch/sub-coverage` `4f3a477a` (§0 to §7). Freeze record `074e8132` (code `aa8ceda5`), written before any O* output. Corpus: GAP-RELOCATE's 400 cycles of `20260925_2010`, n_ref 12,124, NR 1,589, `libft8.dll` `1ba8dc3d…` (pin). Offline, no replay, no station. Result file `_qa-scratch\sub-cover\sc_result.json` (SHA-256 prefix `810a972bde39050c`), working files in the same folder (text never leaves the functions that read it).

## Rows

| row | predicate | result | |
|---|---|---|---|
| O-REPRO | forced legs on the stored R2 u R3 give RC 133, RG 51, RW 77, RP-search 10 | exact (NR 1,589) | **PASS** |
| O-BUILD | builder on the batch-1 natives = stored R2, max abs diff <= 1e-5 x peak | **bit-identical in 400 of 400 cycles** (6,877 fits) | **PASS** |
| O-ROUND (freeze) | rounding dt to 0.1 s changes the batch-1 hits' still-decoded share by > 0.5 pp | -0.014 pp [-0.042, 0.000] | does not fire |
| O-CTRL | CI_hi(share_O* - share_ref) <= +2.0 pp | batch-1 vs R2: +0.04 pp [0.00, 0.10] (2.82 % -> 2.86 %, 7,239 rows); batch-2 vs R3: +0.75 pp [0.29, 1.26] (3.44 % -> 4.18 %, 1,339 rows) | **PASS**; batch 3 (126 rows) 1.59 % [0.0, 4.07] and batch 4 (1,227 rows) 1.47 % [0.84, 2.16] still decoded, reported only |
| **O-ENC** | (unencodable + fit-zero) / decodes <= R2's fit-zero share 2.33 % | 537 + 251 of 10,133 decodes = **7.78 %** | **FIRES**: the bound reads as ">=" only |

## Readout

- **Signals subtracted:** O* subtracts **9,596** signals against R2's **6,877**: **+2,719, a factor of 1.40** (O*: batch 1 6,876, batch 2 1,342, batch 3 128, batch 4 1,250). Not subtracted: 537 unencodable and 251 fit-zero.
- **G*** (NR rows decodable on O* by any leg): **187 of 1,589 rows = +1.542 pp [1.322, 1.762]** of n_ref.
- **G273** (G* minus the L1'-territory stratum): **+0.544 pp [0.422, 0.678]**. Decision rule: CI_lo < 1.0 and CI_hi >= 0.5, so **BETWEEN** (goes to the Captain). O-REPRO, O-BUILD and O-CTRL pass, so the rule applies; O-ENC fired, so every figure here is a lower bound on the oracle.

| NR-TAX stratum | NR rows | decodable on O* | gain, pp of n_ref [CI] | rows with a wrong-payload output |
|---|---:|---:|---|---:|
| CU-d with a batch-3/4 neighbour (L1' territory) | 221 | 121 | +0.998 [0.818, 1.178] | 6 |
| CS | 700 | 47 | +0.388 [0.283, 0.506] | 6 |
| CW | 103 | 16 | +0.132 [0.074, 0.199] | 1 |
| CU-u | 228 | 1 | +0.008 [0.000, 0.025] | 5 |
| IS / IW | 54 / 73 | 1 / 1 | +0.008 / +0.008 | 2 / 0 |
| NC / E | 89 / 9 | 0 / 0 | 0 | 0 |
| **CU-d with only non-re-encodable batch-1/2 neighbours (#273 proper)** | **112** | **0** | **0.000 [0.000, 0.000]** | 7 |
| **all NR** | **1,589** | **187** | **+1.542 [1.322, 1.762]** | **27** |

**Wrong payloads** on O* at NR positions: 27 of the 1,589 NR rows (1.7 %) have a forced leg that returned a wrong payload (the same legs, the same comparator as GAP-RESIDUAL); the 187 decodable rows are payload matches.

## Why O-ENC fires, and what it does to the #273-proper stratum (the finding)

- The spec's oracle part (§1) re-encodes a non-re-encodable decode "from the matched WSJT-X text". **That text is the same string by construction:** the matching requires text equality. QA checked it on the data: of **501** published decodes that fail `IsReencodable` (380 hashed `<...>`, 121 with fewer than 3 tokens), **455 match a WSJT-X line and in all 455 the WSJT-X text is identical to ours.** `oracle_text_used` = 0. A further 36 decodes pass `IsReencodable` but `EncodeMessage` refuses them. So 537 decodes are never subtracted, 5.3 % of the 10,133.
- **The #273-proper stratum is exactly the rows whose stronger neighbours are among those unsubtractable decodes** (112 rows). O* never subtracted them, so its 0 of 112 is **not evidence about #273 proper**: the instrument did not test it. Recovering the tones would need the 77-bit payloads (the native holds them for every decode); the spec's text route cannot give them.
- The L1' stratum (+0.998 pp, 121 rows) is what L1' already subtracts when ON: its night gave +0.77 pp NET against this ceiling of +1.0 pp (a ratio of about 0.77, indicative only: a different night).
- The gain outside L1''s territory is **CS** (+0.388 pp) and **CW** (+0.132 pp): rows next to signals we already subtract, which become decodable once the batch-3/4 signals are also removed; a build for them is the L1' mechanism extended, not a new one.

## What QA does not conclude

- Not "#273 is closed" and not "worth building": the rule says BETWEEN, and the one stratum the question was about is untested.
- The 537 + 251 unsubtracted decodes make every number a lower bound on a true oracle.
- Fits are on O's analytic signal for every batch (the spec's design), unlike the product's incremental fits for batches 2-3; O-CTRL batch-2 shows this costs +0.75 pp of residue (still inside the +2.0 pp bar).

## Options for the Architect and the Captain (QA states, does not choose)

1. Accept **BETWEEN** as it stands (G273 +0.54 pp, a lower bound; #273 proper untested) and decide on that.
2. A bounded **v2 of the builder only**: get the 77-bit payloads from the stored natives' own decodes (native `DecodeAll` plus the fallback snapshot's payload list, on the stored O/R2/R3, offline) and encode tones from payload bits for the 537; re-run the forced legs on the new O*. QA's cost: a few hours of coding and tests, about 20 minutes of machine time; no `src/` or `native/` change; needs the Captain's word (it adds a step to a "small" test).

QA ledger: Q39, Q40 recorded earlier on this arm (40 rows); no new row for this report. Aggregates only (HK-037).
