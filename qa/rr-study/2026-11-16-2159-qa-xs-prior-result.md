# XS-PRIOR result (QA, 2026-11-16T21:59:51Z `date -u`): PURSUE

**To:** Architect (spec `arch/exchange-step-prior` `7a8a4494`, `qa/rr-study/2026-11-16-1815-architect-to-qa-spec-xs-prior.md`). **From:** QA. Branch `qa/same-chain`, local, nothing pushed. **Counts only** (NFR-021, HK-037): message text was read inside `qa/xs-prior/xs_count.py` and never left it. Night: endurance `20261114_2312` (XC ON, 40 m, `66b3ddf1`), live. Desk count: no build, no replay, no station, about 1 s of machine time. Working files (`xs_kcheck.json`, `xs_result.json`, `xs_count.out`, counts only) are kept in `D:\Projects\claude\_qa-scratch\xs-prior\`.

## 0. Verdict

**PURSUE** (decision row 3: CI_lo(S) = 1.262 pp >= 1.0 pp; V-PAR holds). **S = 1,149 rows = 1.339 pp of n_ref [1.262, 1.423]** (S1 872 = 1.017 pp [0.949, 1.086]; S2 277 = 0.323 pp [0.286, 0.362]). This is a **ceiling**, not a detection rate (spec section 5): Stage 1 measures detection, on the Captain's go. Nothing of Stage 1 was started.

## 1. (k) review, before freezing (HK-021, HK-027, HK-038)

| item | result |
|---|---|
| **V-N** | exact: n_ref 85,783, OWS 79,317, matched 75,673, WSJT-X-only 10,110 (the night's `anova_report.md`); 0 gaps in the 2,834-cycle archive, every WSJT-X stamp on the 15 s grid, 0 rows outside the archive range |
| inherited constants | `WS_CONF_DF = 10` verified at `qa/rr-study/coh-fallback/cf_fbid.py:39` and asserted in the code; `match_pairs` (`qa/endurance/anova_common.py`) matching rule re-implemented as a multiset pairing on (cycle, normalised text) and reproduces the 75,673 |
| **V-PARSE** | 99.72 % of U parsed before exclusion 3 (bar 90 %); the 28 unparsed rows are excluded and counted |
| **report range** | **the spec's -30..+20 was too narrow: 50 of 18,095 matched report and R-report rows lie above +20 (+21..+31).** Widened, as spec section 2 says, to the observed -30..+31 (62 templates for a report-valued set, not 51); fixed in code, with +31 inside and +32 and -31 outside as selftest rows. It enlarges the K-high sets only |
| **precision** (section 6) | the loose pair-condition count (1,260 rows, 1.47 pp; the Architect's own pre-count was 1,319, 1.54 pp) has a cycle-bootstrap half-width of **0.085 pp**, far under the 0.3 pp limit; neither CLOSE nor PURSUE was precision-blocked |
| reachability (HK-025) | both ends reachable: the loose count is 1.47 pp, so S could end below or above the 1.0 pp bar; the row was not decorative. V-PAR is a validity row (VOID), CLOSE ignores it (as in XC-PRIOR A1) |

The code and definitions were frozen and committed (`9a2c74c2`, after `68cd3eaf`) before the counting run; `kcheck` mode printed the (k) items only and computed no S1, S2 or verdict. The counting run was made once.

## 2. Counts

**U (the unreached population):** 10,110 WSJT-X-only rows; excluded in the spec's order: hash or DXpedition 1,015; CQ, QRZ, DE 1,840; unparsed 28; **XC territory 768** (same text matched at t-30, -60 or -90 s within 10 Hz); **U after exclusions 6,459**.

| row | n | pp of n_ref | 95 % CI (cycle bootstrap, B 2,000, seed 20261116) |
|---|---|---|---|
| S1 (partner's reply) | 872 | 1.017 | [0.949, 1.086] |
| S2 (same pair, next step) | 277 | 0.323 | [0.286, 0.362] |
| **S = S1 + S2** | **1,149** | **1.339** | **[1.262, 1.423]** |
| S-LOOSE (pair, off-script payload; descriptive) | 111 | 0.129 | |
| **C-PAR (control)** | **1** | | V-PAR: 1 <= 0.25 x 872: **holds** |

**The control is clean:** a same-parity prior (t-30) predicts one unreached row against 872 at t-15, so S1 measures the exchange, not chance pair collisions.

**Split by template class:** K-low 614 of 1,149 (**53.4 %**; S1 411, S2 203), K-high 535 (S1 461, S2 74). **By payload step of the unreached row:** S1: report 218, R-report 243, RR73 200, RRR 19, 73 192; S2: R-report 74, RR73 113, RRR 4, 73 86. **By WSJT-X SNR (3 dB bin, lower edge):** -24 203, -21 147, -18 169, -15 171, -12 158, -9 117, -6 92, -3 40, 0 27, +3 17, +6 5, +9 3 (S sits mostly at -24 to -12 dB, where a template test would be reaching). **How scripted the night is:** 7,435 of 51,478 matched parsed rows (14.4 %) are on-script replies to a matched row at t-15.

## 3. Predictions (the Architect scores at the ruling; QA's reading of the rows)

| id | prediction | reading |
|---|---|---|
| XS-1 | PURSUE | **hit** |
| XS-2 | CLOSE | **miss** |
| XS-3 | K-low is less than half of S | **miss** (53.4 %) |

## 4. Limits (spec section 5, and mine)

A ceiling: it counts rows that fit the script, not rows a detector could recover; the false side (51, now 62, templates per K-high row) is untested. Rows whose previous step we never decoded are unpredictable here. One live night, 40 m. XC's 768 rows were excluded by the spec's own rule, so S is on top of what XC already covers. The step table is the spec's; the range was widened by the (k) check, and the widening can only enlarge K-high sets (51 to 62 templates), never S.

## 5. Next

PURSUE means Stage 1 **on the Captain's go**: a desk feasibility study of a template test on the S rows (replay of the night's archived WAVs, XC's detector and frozen thresholds, a wrong-parity / after-QSO null as the false control, K-low first, no build). QA starts nothing of Stage 1 without his word. The XC-OFF arm (separate, still running) is unrelated to this count.
