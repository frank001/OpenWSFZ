# GAP-RELOCATE: where does today's build lose what WSJT-X decodes? (map, descriptive routing)

Written 2026-10-28T14:39:02Z (`date -u`). Spec `690e8cb5` (Architect, `arch/gap-relocate`) with Amendment 1 (`825cc235`), Amendment 2 (row DENS, `a6ac792f`) and Amendment 3 (section 11, population). Counts only (HK-037 / NFR-021); per-message working files are in `D:\Projects\claude\_qa-scratch\gap-relocate\` and are deleted at job close.

## 0. What was run (HK-022)
- **Machine and state:** the PC; the station daemon stopped on the Captain's word (13:29:51Z); the Captain's go for this run was "do GAP-RELOCATE now" (13:29Z), which overrides the spec's "after the first FB-AUDIO night". The station's FB-AUDIO era therefore ended after about 1 h 32 min.
- **Build:** `main` `95e69e87` (v0.66), `libft8.dll` SHA-256 `1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914` (the station pin), shim 20260071; re-hashed at the start and end of both replay arms and by the forced-leg loader (final hash after the last leg: `1ba8dc3d6a7d0327…`, equal). Settings: Deep, `nhard` 24, OSD sign fix 1, 8 threads, multi-set ON, `coherentFallbackAudio` Both.
- **Replay:** Replay81 (`qa/refset`) built with `-p:HasInternals=true` (assembly name `Ft8.FitProbe`, already in OpenWSFZ.Ft8's `InternalsVisibleTo`), a counting pass-through wrapper of the production interop; **no change under `src/` or `native/`**. Chain `gr_arms.sh`: BOTH 13:44:11-14:04:31Z, OFF (`--cohfb 0`) 14:04:31-14:21:45Z, both `preflight_end_ok=1`, 400 rows each, orphan check clean. (A first attempt at 13:42Z was stopped after 30 cycles to add payload-level recording; nothing from it is used.)
- **Population:** night `20260925_2010`, the first 400 cycles of the frozen whole-night selection (regenerated as `selection400.json`; its SHA differs from B2's only by the file's note text; row 0b shows the same cycles). `n_ref` = **12,124** WSJT-X decodes (= B2's W). BOTH hits 9,931, **M = 2,193 misses** (18.09 pp). K (control) = 2,000 hits drawn with seed 20261028; K on original-audio paths 1,558 (Amendment 3: batch 1 and the fallback's original-audio run), no extension needed. Different nights were not added (no new selection was asked for).
- **Forced legs:** `gr_forced.py` (forced primary at 9 lattice cells, `ft8_extract_llrs_at` + `ft8_ldpc_decode_llrs`; forced coherent V3 with `FT8_COH_FLAG_FORCE_C3`; the multi-set walk `ft8_coherent_fallback_sets_at`), comparator and v* from GAP-LOCATE Amendment 4 (`(0, 32373)`). δ frozen from the 40 pilot cycles before any M row was forced: δ_p **0.6 s** (196 pairs), δ_c **0.7 s** (17 pairs) (both are on a 0.1 s grid because the published and REF `dt` are rounded; the mean is 0.646). Pilot re-forcing at δ 0.60 / 0.65 / 0.70 gave identical rates. Classes (first match wins, as code in `gr_item2.py`): P, FP, FC (V3 payload, `gated` 1), G (V3 payload, `gated` 0), FCw (walk payload), N. Bootstrap: 400 cycles resampled, B = 2000, seed 20261028, percentile 95 % CI.

## 1. ROW 0

| row | result | value |
|---|---|---|
| 0a identity | PASS | DLL pin equal at all hash points |
| **0b replay = B2** | **PASS, exact** | batch 4 published 1,350; corroborated 9,931 / 12,124 = 81.91 % (B2: 1,350 and 81.91 %) |
| **0c mapping** | **PASS** | `P_ctrl` (FP ∪ FC ∪ walk) on original-path K rows of the 360 non-pilot cycles: **0.964** (n = 1,348); `P_ctrl,p` (FP alone) 0.876; `P_ctrl,c` (coherent, any gate) 0.953; pilot 0.987 (n = 150). By band A / B / C / D: 0.963 / 0.951 / 0.980 / 0.989 (n 356 / 566 / 249 / 177); no band is below 0.80, so none is marked "undecodable not established" (A1.3). By tag: batch 1 0.967 (n 1,228), fallback-original 0.942 (n 120). |
| **0d audio / exclusions** | **FAIL** | every WAV used is 180,000 samples (asserted); but **164 of 2,193 M rows (7.48 %) cannot be encoded for comparison**, against the bar ≤ 1 %. 148 of them carry a hashed callsign (`<…>`), 16 are other forms. The same happens to K (67 of 2,000, 3.35 %). The forced legs need the true codeword; a hashed-call message cannot be re-encoded without the process hash table. |
| 0e item 1 chain | PASS | section 2 |
| 0f no abandonment | PASS | BOTH arm: fallback abandoned 0, residual pass 400 ran / 0 abandoned / 0 contained, exceptions 0; OFF arm: exceptions 0 |

**Under the spec ("any failure ⇒ every section-5 row VOID") the failure of 0d voids the routing rows.** Everything below is reported as measured; the routing lines carry the VOID label. The Architect/Captain may rule on 0d (for example, restate its bar on the encodable population and carry the 7.48 % as a named class). I did not.

## 2. Item 1: the ~130 fallback payloads per run
Units stated. BOTH arm, 400 cycles; run 0 = fallback on the residual audio, run 1 = on the original audio.

| stage | count | unit |
|---|---:|---|
| S1 NEW_GATED rows, run 0 / run 1 | 2,717 / 1,961 | candidate-run rows |
| S1d distinct payloads, run 0 / run 1 / merged | 1,353 / 855 / 1,610 | payloads |
| S2 after `CoherentFallbackSelector.Select` (= unpack calls; equal to the merged count in all 400 cycles) | 1,610 | payloads |
| S3 non-empty text (1 empty, 0 access violations) | 1,609 | payloads |
| S4 after text de-duplication (= S5 + implausible drops) | 1,350 | messages |
| S5 published batch 4 | 1,350 | messages |

- **A1** the chain adds up exactly. **B2's 563 ≠ 725** was a QA mislabel (Q25): the log's `gated=` counts NEW_GATED rows (F1b **at or below** T1), not rows rejected by the gate. 1,961 rows are 855 distinct payloads, 725 published (Original); F1b above T1 = 2,524 − 1,961 = 563 rows. B2's report is corrected.
- **A2** empty 1, duplicate text 259, implausible 0.
- **A3 = 0** (0.00 pp of `n_ref`). The plausibility filter dropped 12 messages in the whole cycle set in BOTH and the same 12 in OFF; none from the fallback. Both methods (log position; BOTH-minus-OFF text difference) agree at 0.
- **A4** all 259 duplicate-text drops duplicate a **batch 2/3** decode (162 residual pass, 97 third pass); 0 duplicate batch 1; 0 within the fallback. CPU spent, not decodes lost.

## 3. Item 2: the stage map (D1 to D7)

**N is an upper bound, and by a lot.** The forced legs read the ORIGINAL audio. The product also decodes after subtraction (batches 2 and 3) and runs the fallback on the residual buffer. The controls show how little of that the forced legs can reach: of K rows the product found in batch 2 or 3, **0.099** are recovered by the forced legs (`P_ctrl,sub`, n = 284 outside the pilot); of rows found only by the fallback on the residual, **0.022** (`P_ctrl,res`, n = 92). So the N class below contains every miss that is decodable only on subtracted audio, and this map cannot say how many.

**D1** (counts of the 2,193 misses, pp of `n_ref` 12,124):

| class | rows | pp | 95 % CI (cycle bootstrap) |
|---|---:|---:|---|
| P (decoded, then filtered) | 8 | 0.066 | [0.025, 0.115] |
| FP (forced primary succeeds) | 10 | 0.082 | [0.033, 0.140] |
| FC (V3 payload, passes T1) | 26 | 0.214 | [0.140, 0.298] |
| G (V3 payload, rejected by the gate) | 87 | 0.718 | [0.570, 0.866] |
| FCw (walk payload only) | 38 | 0.313 | [0.217, 0.420] |
| **N** | **1,860** | **15.341** | [14.670, 15.993] |
| excluded (cannot be encoded, 0d) | 164 | 1.353 | n/a |
| total | 2,193 | 18.088 | |

- **D2** FP: centre cell 4, neighbour only 6.
- **D3** by band A / B / C / D: P 0/5/2/1; FP 0/2/2/6; FC 1/4/7/14; G 40/41/5/1; FCw 13/19/2/4; N 74/451/469/866.
- **D4** by cycle-load quintile (edges 23 / 28 / 33 / 37 REF decodes): N 185 / 252 / 330 / 416 / 677; G 7 / 14 / 21 / 17 / 28; FC 1 / 7 / 6 / 2 / 10; FCw 4 / 6 / 8 / 9 / 11; FP 1 / 3 / 2 / 2 / 2; P 1 / 3 / 1 / 2 / 1.
- **D5** `F_wrong` (a CRC-valid different payload at the REF position), all in class N: forced primary 59, V3 44, walk 14.
- **D6** not attributed (the harness has no cheap candidate-list export for this; no native export was built).
- **D7** G: 87 rows; 7 within 1 dB above T1 (17.552 dB); median F1b 21.43 dB; none without a usable reference. Most G rows sit well above T1, in bands A and B (40 and 41 rows).
- **Per-station clustering** (distinct senders; share of the top sender): G 61 senders in 87 rows (6.9 %); FCw 35 in 38 (5.3 %); FC 24 in 26 (7.7 %); FP 10 in 10 (10 %); P 4 in 8 (62.5 %); N 366 in 1,860 (2.0 %).

## 4. Routing rows (section 5): all **VOID by the 0d failure**; the predicates, as measured
Bar `BAR_L` = 0.5 pp (Captain, 2026-10-24 12:50:57Z, COH-MULTISET, same night); no multiplicity adjustment; each class tested on its own.
- R-P no (CI_lo 0.025); R-FP no (0.033); R-FC no (0.140); R-FCw no (0.217).
- **R-G fires** (CI_lo **0.570** ≥ 0.5). Route (question for the Captain): T1 was chosen on original audio (Q-GATE `7313db6f`); a re-tune needs its own arm with the U′ watch. D7 shows only 7 of the 87 within 1 dB above T1, so a small re-tune would not reach most of them.
- **R-N fires** (CI_lo 14.670 ≥ the sum of the other classes' point estimates 1.39). Route: N is not decodable by any extractor we can force on the ORIGINAL audio. This map cannot separate interference-limited loss from subtraction-recoverable loss (B2 showed the audio matters: +3.60 pp from the residual; here `P_ctrl,sub` is 0.099 and `P_ctrl,res` 0.022). The blind spot is batch 2, batch 3 and the residual-run fallback. The Captain decides whether to commission a forced export on the residual buffer (a native change: Developer, HK-011, then QA's HK-039 review) or to stop.
- R-0 not applicable.

## 5. DENS (section 10, registered before any class datum; confirmatory)
Groups q1..q5 = 80 cycles sorted by `n_ref`. Rates standardised to the 400-cycle band mix (no band dropped; any band cell under 30 REF rows is pooled toward A by the code). Standardised N rate q1 → q5: 13.28 %, 13.47 %, 15.01 %, 16.10 %, 16.93 %; **dN = +3.65 pp [1.68, 5.51]**. W (misses where any forced leg returns a CRC-valid different payload): 0.27 %, 0.33 %, 0.75 %, 0.80 %, 1.27 %; **dW = +1.00 pp [0.54, 1.48]**. **DENS-YES** (both CI_lo > 0). `P_ctrl,res` q1 vs q5: 0.00 (n 15) vs 0.04 (n 25); `P_ctrl,sub` q1 vs q5: 0.167 (n 24) vs 0.090 (n 100). The control counts are small in q1, so the blind-spot size is not shown to be equal across load. The 0d failure puts this row under the same VOID until ruled otherwise.

## 6. Limits
One night, one machine, 400 cycles, forced legs on the original audio only. The 7.48 % exclusion (mostly hashed-call messages) is a structural limit of the instrument; those messages are the same "hashed / unencodable" class as in U′. The WSJT-X and production `dt` are rounded to 0.1 s; δ is therefore a 0.1 s-grid median, and the diagnostic shows it does not matter between 0.60 and 0.70.
