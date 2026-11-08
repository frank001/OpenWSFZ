# GAP-RELOCATE: item 1 RESULT, and item 2 STOPPED at the pilot (Amendment 3 requested)

**To:** Architect · **From:** QA · **Date:** 2026-10-28T14:34:43Z (`date -u`) · **Run:** PC, the Captain's go ("do GAP-RELOCATE now", station daemon stopped, nothing else running)
**Build:** `main` `95e69e87`, `libft8.dll` `1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914` (start and end of every arm: OK), shim 20260071, Replay81 built with `-p:HasInternals=true` (assembly `Ft8.FitProbe`, a counting pass-through interop; `src/` and `native/` untouched). Settings: mode three1 (Deep), `nhard` 24, OSD sign fix 1, 8 threads, multi-set ON, `coherentFallbackAudio` Both. Counts only (HK-037); the per-message working files are in `D:\Projects\claude\_qa-scratch\gap-relocate\` and are deleted at job close.
**Population:** night `20260925_2010`, first 400 cycles of the frozen selection (`selection400.json` regenerated from the frozen whole-night selection; its SHA differs from B2's only by the file's note text; row 0b shows the cycles are the same). I did not list other `artefacts/` folders for a different night: no new selection was asked for.

## ROW 0 so far

| row | result |
|---|---|
| 0a identity | PASS: DLL pin at the start and end of both arms and in the forced-leg loader; all exports resolve (loaded and called) |
| **0b replay = B2** | **PASS, exact:** batch-4 published **1,350**; WSJT-X decodes corroborated 9,931 of 12,124 = **81.91 %** (B2: 1,350 and 81.91 %); `n_ref` = 12,124 = B2's W |
| 0e item 1 chain | PASS in the BOTH arm (below); the OFF arm has no fallback rows (every stage is 0) |
| 0f no abandonment | PASS: BOTH arm fallback abandoned 0, residual pass ran 400 / abandoned 0 / contained 0, exceptions 0; OFF arm exceptions 0, residual pass abandoned 0 |
| **0c control** | **PILOT STOPPED (see below). Not run beyond the pilot.** |
| 0d audio | not yet reached |

## Item 1 (A1-A4): the ~130 is duplicate text, and nothing was lost

Units stated per line. BOTH arm, 400 cycles; run 0 = fallback on the residual audio, run 1 = on the original audio.

| stage | count | unit |
|---|---:|---|
| S1 NEW_GATED rows, run 0 / run 1 | 2,717 / 1,961 | candidate-run rows |
| S1d distinct payloads, run 0 / run 1 / merged | 1,353 / 855 / **1,610** | payloads |
| S2 after `CoherentFallbackSelector.Select` (= unpack calls; asserted equal to the merged distinct count in all 400 cycles) | 1,610 | payloads |
| S3 unpacked to non-empty text (1 empty, 0 access violations) | 1,609 | payloads |
| S4 after per-cycle text de-duplication (= S5 + implausible fallback drops) | 1,350 | messages |
| S5 published batch 4 | 1,350 | messages |

- **A1:** 1,610 → 1,609 → 1,350 adds up exactly (1 empty, **259** duplicate text, **0** implausible). Run 1's 855 and run 0's 1,353 are the "publishable" figures B2 gave for Original and Residual, so the ~130 per run is the same mechanism.
- **B2's 563 vs 725 explained (QA error Q25, now corrected in B2's report):** the log's `gated=` counts NEW_GATED rows (new payload, F1b **at or below** T1). B2's table labelled it "gated out (F1b above T1)". So 1,961 are the rows that passed T1 (855 distinct payloads), and F1b above T1 is 2,524 − 1,961 = 563. The chain is 1,961 rows → 855 payloads → 725 published (Original); nothing mixes rows with payloads once the label is right.
- **A2:** empty unpack 1, duplicate text 259, implausible **0**.
- **A3 = 0** (0.00 pp of `n_ref`): no fallback payload was dropped by `IsPlausibleMessage`. The plausibility filter dropped 12 messages in the whole cycle set in the BOTH arm and the same 12 in the OFF arm, none from the fallback. Both attribution methods agree (position and the BOTH minus OFF text difference: 0 and 0).
- **A4:** all 259 duplicate-text drops duplicate a **batch 2/3** decode (162 residual pass, 97 third pass), **0** duplicate a batch-1 decode, 0 duplicate within the fallback. As predicted, this is CPU spent, not decodes lost.
- **P class size:** the 12 implausible drops can only matter to class P (at most 12 of 2,193 misses).

## Item 2 STOPPED at the pilot (the stop rule in A1.2 worked)

Population: `n_ref` 12,124; BOTH hits 9,931; **M = 2,193 misses**; K = 2,000 hits drawn with seed 20261028; K by tag (A1.1 as written): batches 1-3 1,759, fallback on the original audio 133, fallback on the residual only 108 (1,892 original-path, so no extension of the draw was needed). Pilot = the K rows of the first 40 cycles (200 original-path rows per A1.1). δ frozen from the pilot (median of production minus REF dt): δ_p 0.6 (196 pairs), δ_c 0.7 (17 pairs). Both are on a 0.1 s grid because both the published `Dt` and the REF `dt` are rounded to 0.1 s; the mean is 0.646, close to GAP-LOCATE's 0.653.

**Pilot `P_ctrl` (FP ∪ FC ∪ walk, original-path rows as A1.1 defines them): 0.77 < 0.90, STOP.** `P_ctrl,p` (FP alone) 0.705. No M row was forced.

**Diagnosis (descriptive, pilot K rows only, from the same forced calls):**

| K tag in the pilot | n | union | FP alone |
|---|---:|---:|---:|
| **batch 1** (pass-0, original audio) | 143 | **0.993** | 0.979 |
| batch 2 (residual pass, after subtraction) | 45 | 0.133 | 0.022 |
| batch 3 (third pass, after subtraction) | 5 | 0.000 | 0.000 |
| batch 4 (fallback), original or residual path | 16 | 0.438 | 0.062 |

- The mapping is right: batch-1 rows come back at 0.993 (FP 0.979, GAP-LOCATE had 0.96 for the primary alone).
- **The population definition is wrong, and the error is mine (Q26).** A1.1 tags "batches 1-3" as original-audio-reachable. Batches 2 and 3 are decoded after subtraction, so the forced legs on the original audio cannot reach them, exactly like the fallback-on-residual rows K1 excluded. My K1 named one such population and missed its siblings.
- The result does not depend on δ: re-forcing the pilot at δ 0.60 / 0.65 / 0.70 gives identical rates (the 9-cell neighbourhood and the 0.08 s lattice step absorb a 0.05 s shift).

## Requested: Amendment 3 (population only; no new instrument, no bar chosen from data)

1. **Original-audio path = batch 1, plus the fallback rows found by the original run** (`fb_orig`). Batches 2 and 3 and `fb_res` are reported as `P_ctrl,sub` (descriptive), beside `P_ctrl,res`.
2. Row 0c's 0.90 applies to the original-path rows (K tags batch 1 and `fb_orig`). The pilot value on that definition is **0.993 (batch 1 alone) / 0.98 (with the 7 `fb_orig` rows)**; I quote it so the Architect can see it, but the bar stays at the registered 0.90 and the bar's source is unchanged (GAP-LOCATE 0c′ 95.96 %).
3. A1.3's per-band rule keeps its form and is evaluated on the same definition. Pilot per-band values on batch 1 are on file (A 1.0, B 0.985, C 1.0, D 1.0, n 47/67/17/12), so no band is marked "not established" on the pilot, and the 0.80 may be frozen.
4. N's reading becomes sharper, not weaker: the blind spot of the forced legs is **batches 2, 3 and the residual fallback**, and the study should say so in the first paragraph on N.
5. δ stays as frozen (0.6 / 0.7); the diagnostic shows the choice does not matter between 0.60 and 0.70.

Because the pilot re-force is already on file for the new definition, I can proceed on your amendment without a re-run of the replay arms. **Waiting on:** your Amendment 3. Then I run the K rows of cycles 41-400 and all 2,193 M rows (about ten minutes on the PC) and write the report.

*QA error ledger: 26 rows (Q25 B2 mislabel, found by the stage chain; Q26 this population miss, caught by the pilot).*
