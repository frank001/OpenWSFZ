# DENSITY-SUB — result (QA to Architect)

**Verdict row (as pre-registered, Amendments 1 and 2): INVALID.** The ON arm's ROW 0a and ROW 0b fire, so no DS-REMEDIED / DS-PERSISTS / DS-OPEN is read. Read-out time 2026-10-09 15:40Z. Data: `artefacts/rr_2026-10-09_density_sub/`, rows `results/2026-10-09-density-sub/rows.json`, script `qa/rr-study/density-sub/density_sub_rows.py` (17 tests).

**V1 as pre-registered FAILED (75/430 OFF), amended after the OFF arm's validity data and before any ON-arm number.** Under Amendment 2: V1 on the 163 cycles with no hashed W line passes in both arms (163/163 OFF; ON 162 equal plus 1 explained by an abandonment in exactly one of the two runs, 0.6 % of 163, 0 unexplained). Hashed-cycle residue (stated limit): OFF 75 cycles differ, sum −39 of 8,007, range −2 to +2; ON 58 cycles differ, sum −28, range −11 to +1. The DLL pin equals the 10-01 run's: `ee00d118523ee2160750736225c67d8a056193908d168ed9a6ec3375ff990e4c`, matched at the start and end of both arms. Filter and build: selection `S10` (430 cycles, LF SHA-256 `04bb0818…e58e5f`), harness commit `c2a4e95e` plus the two script fixes, build checkout `247ac391`, `--nhard 40`, `--threads 8`, orphan check empty.

## Validity rows
| Row | All 430 cycles | 163 no-hashed cycles |
|---|---|---|
| V2 (partition) | PASS | PASS |
| V3 (EXPOSED ≥ 200) | PASS, 854 | PASS, 299 |
| ROW 0a, OFF: CI of D(PL,PF) in [−0.05, +0.05] | **FIRES**, D 0.037, CI [0.010, 0.063] | **FIRES**, D 0.083, CI [−0.002, 0.175] |
| ROW 0a, ON | **FIRES**, D 0.053, CI [0.027, 0.077] | **FIRES**, D 0.090, CI [0.016, 0.173] |
| ROW 0b: standardisation drops ≤ 5 % of EXPOSED and of PL | **FIRES**, EXPOSED 83/854 (9.7 %), PL 122/1,283 (9.5 %), both arms | **FIRES**, EXPOSED 194/299 (65 %), PL 266/432 (62 %) |

Bars: ROW 0a and ROW 0b come from DENSITY-LIVE (2026-09-18, a different corpus, 60,239 rows); this sample has 8,151 population rows, so 21 SNR cells with a minimum of 20 rows per cell leave too many cells thin. That is the mechanism of 0b, and 0a's wider interval follows the same sample size. The rows did what they are for.

## Descriptive figures (NOT a verdict; the validity rows fired; one 40 m night, offline replay, 1-in-10 sample, the 10-01 build)
- D(EXPOSED,PL), all 430: OFF 0.684 [0.649, 0.718], ON 0.330 [0.287, 0.374]; ΔD = −0.354 [−0.393, −0.314]. The 0.170 bar is DENSITY-LIVE's, carried over from a different population.
- Live-cost equivalent (C = D·n_EXPOSED/n_W·100): OFF 4.35 pp, ON 2.10 pp.
- Matched rate, EXPOSED: OFF 9.0 % (n=854), ON 50.4 %. PL: 83.9 % → 87.2 %. CLEAR: 90.6 % → 93.1 %.
- NET per stratum (pp of that stratum's rows): EXPOSED +41.3, GAP +12.2, PL_TRANS_STRONG +34.9, TRANSITION +17.2, PF +6.4, PL +3.3, CLEAR +2.5.
- 163-cycle subset (also invalid): D_on 0.320 [0.138, 0.571], ΔD −0.319 [−0.465, −0.150]; same direction, much wider.
- Robustness row (Amendment 2 iii as refined): not applicable, both rows INVALID; the subset is inconclusive.

## What this means, and what it does not
The point estimates say the subtraction pass roughly halves the near-neighbour cost on this night, but D_on (0.33) is still about twice the 0.170 bar, so if the validity rows had passed the reading would have been DS-PERSISTS. QA does not read that row: it did not pass. Nothing here is cited as a finding.

## Options (the sample size is the only thing wrong)
1. **Leave it as INVALID** with the descriptive figures above on record.
2. **Re-run on a larger sample** with the same rows and bars frozen now: 1-in-3 (about 1,433 cycles; ON arm about 2.7 h, OFF about 13 min) or the full 4,298 (ON about 8 h, OFF about 40 min). Size needed for 0b: the dropped fraction scales roughly with the thin cells; 1-in-3 would be expected to land near 3 % but that is a prediction from this sample's cell counts, not a measurement. Hashed-cycle limit applies as before.
