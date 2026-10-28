# COH-GATE-G: TRAIN result (the 400 seen cycles). TEST NOT TOUCHED.

Written 2026-10-28T16:19:56Z (`date -u` at the last data copy). Spec `1b7445e7` + Amendment 1 `47294d4d` (`arch/coh-gate-g`, Architect), QA review `51c52b5a`. Counts only (HK-037 / NFR-021); per-message files are in `D:\Projects\claude\_qa-scratch\coh-gate-g\` and are deleted at job close. Order of work: TRAIN record and analysis (this file) → the `U_bar_G` table for the Captain (section 4) → freeze commit → only then the TEST replay.

## 1. What was run
PC, station daemon stopped (Captain 13:29:51Z; "don't worry about the daemon"). Build `main` `95e69e87`, `libft8.dll` `1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914` re-hashed at the end of both arms (OK), shim 20260071. Replay81 with the recording extension (`StageProbe.cs`, `--gate-record 1`; assembly `Ft8.FitProbe`, `src/` and `native/` untouched). Night `20260925_2010`, first 400 cycles of the frozen selection (`selection400.json`). Settings: Deep, `nhard` 24, OSD sign fix 1, 8 threads, multi-set ON. Arms: BOTH 15:30:52-15:54:50Z, ORIGINAL (`--cohaudio Original`, only to freeze the U′ classes as B2 did) 15:54:50-16:16:35Z, both `preflight_end_ok=1`, 400 rows. Every attempted row in state GATED_OUT or NEW_GATED was recorded per run with `f1b`, SNR, edge, provenance, output-minus-anchor frequency and dt, pass, candidate index and the payload's `i3`/`n3`; the texts of GATED_OUT payloads were unpacked after each cycle inside a hash-table save and restore, so later cycles saw the table the product would have had. An earlier recording (15:08Z-15:30Z) lacked the candidate index the product's merge sorts by; V2 failed on ORDER only (82 cycles), the corroborated count matched. It was repeated with the index; only the repeat is used.

## 2. Validity rows (all PASS)
| row | result |
|---|---|
| V1 replay | PASS exact: batch 4 published **1,350**, corroborated 9,931 of 12,124 = **81.91 %** |
| V2 record complete | PASS exact: offline admission with the existing gate reproduces the product's batch 4 in **all 400 cycles** (same messages, same frequencies, same order); corroborated 9,931 = 9,931 |
| V3 identity | PASS: DLL pin equal at the start and end of both arms and in the analysis build |
| V4 no abandonment | PASS: fallback abandoned 0; residual pass ran 400, abandoned 0, contained 0 |
| V5 label sanity | PASS exact: U′ per cycle, Original arm **0.1275**, Both arm **0.2100** (tested_absent 38, hashed/unencodable 46, untestable class 0; tested_present 118); both equal B2. Classes frozen from the Original arm alone (`grid`, `grid CQ`, `report`, `RR73/73/RRR` testable); the night's null p99 0.2759 vs T 0.276 (no flag) |

## 3. The ceiling and the search (TRAIN, descriptive; the selection is chosen here and nothing is joined to TEST)
- **Rows recorded (BOTH arm):** NEW_GATED 2,717 (residual run) + 1,961 (original run); GATED_OUT 1,263 + 563. (Same row counts as GAP-RELOCATE.)
- **Ceiling (admit every GATED_OUT row, through the product's merge, text de-duplication and plausibility filter): NET_all = +1.930 pp** (234 more WSJT-X decodes corroborated, of 12,124). **STOP-CEIL does not fire** (bar 0.5 pp, point value).
- **What the ceiling publishes:** 258 outputs with a new text, **234 corroborated (90.7 %)**, against batch 4's current 1,227 of 1,350 (**90.9 %**). 255 of the 258 come from the run on the residual audio. 71 come from walk sets, 187 from V3. 1 edge row, 257 non-edge.
- **Cost of the ceiling in U′ (per cycle, 400 cycles):** tested_absent **+4 outputs = +0.010**; hashed/unencodable **+10 = +0.025**; tested_present (unconfirmed but present in the audio) **+12 = +0.030**; untestable class 0. (The instrument counts 2 existing outputs whose frequency moved when a residual row replaced an original one, so these are slight overcounts.)
- **D3:** the ceiling newly corroborates **86 of GAP-RELOCATE's 87 class-G rows**.
- **D2 (admitted outputs with new text, 258):** by band A / B / C / D: 1 / 53 / 118 / 86 (corroborated 1 / 49 / 108 / 76); by `i3`: type 1 241 (222 corroborated), **type 4 16 (11 corroborated = 68.8 %)**, type 2 1; by run: residual 255, original 3; hashed text 31 (22 corroborated).
- **Per-station clustering of the 234 corroborated additions:** 114 distinct senders, top sender 5.1 %, top five 18.8 %.
- **Rule family:** 5,565 rules (at most two conditions from f1-f8, thresholds on every 5th percentile of the TRAIN G rows). Selection used an additive per-row proxy; the best 300 by the proxy were re-evaluated EXACTLY (full offline publication, one-to-one match). Subject to `ΔU′_tested_absent ≤ 0.021` (point):
  - **Chosen: `|out_freq − freq| ≤ 2 Hz`** (f7, one condition): NET +1.930 pp, ΔU′_ta +0.010, ΔU′_hu +0.025, 284 admitted outputs (including the 26 moved-frequency ones).
  - **This rule admits every GATED_OUT row** (the fallback's search window is ±2 Hz, so every row satisfies it): it is "no gate", not a separator. Single-condition alternatives, all within 0.01 pp: `no_edge` +1.922 pp, `|out_dt − dt| ≤ 0.08 s` +1.922 pp. No second condition improved on it. **The best any rule can do on TRAIN is the ceiling, and a rule exists that reaches it.**
  - **f1 alone at its best T2** (D1 baseline, "just widen it"): `F1b ≤ 31.18 dB` NET **+1.872 pp** (97 % of the ceiling), ΔU′_ta +0.010, ΔU′_hu +0.025.
- **H-SHARE inputs (KG1):** hashed/unencodable share of the admitted outputs **12.0 %** (31 of 258 by text; 10 outputs by the U′ instrument) against `h` = 0.5; type-4 admitted rows 16, corroborated 68.8 % against 90.9 % for batch 4. H-SHARE would not fire on TRAIN.

Limits: one night, one band, 400 seen cycles, no CIs on TRAIN (descriptive; the bootstrap is a TEST row), the proxy search ranks single rows, so a rule that only pays when its rows are the only admitted ones for a payload could rank low (the exact re-evaluation covers the top 300 only).

## 4. The Captain's table for ratification (KG2): what each reading of `U_bar_G` does
`BAR_G` = 0.5 pp is stated with its source (`BAR_L`, ratified 2026-10-24 12:50:57Z). The open choice is how `U_bar_G` = 0.021 per cycle is applied. TEST has 800 cycles; the bar is per cycle.

| | per cycle on TRAIN | reading A: tested_absent only (proposed) | reading B: whole ΔU′ (tested_absent + hashed/unencodable + untestable class), the original use |
|---|---|---|---|
| gate removed (the ceiling, = the chosen rule) | ta +0.010, hu +0.025, untestable 0 | **0.010 ≤ 0.021: within the bar** | **0.035 > 0.021: over the bar by 0.014** (about 5.6 outputs per 400 cycles) |
| `F1b ≤ 31.18` (f1 alone) | ta +0.010, hu +0.025 | 0.010: within | 0.035: over |
| for comparison, B2 Both − Residual (shipped, Captain picked Both with no bar) | ta +1 per 400 = +0.0025, hu 0 | 0.0025: within | 0.0025: within |
| for comparison, B2 Residual − Original (shipped, no bar) | ta +22 = +0.055, hu +10 = +0.025 | 0.055: over | 0.080: over |

Does it matter? **Yes: it decides the verdict.** On TRAIN's point values, reading A passes this gate change and reading B fails it, and the difference is the hashed/unencodable outputs (10 per 400 cycles), the class the instrument cannot test. For scale: the audio-choice change the Captain approved without a bar added more tested_absent than this one would, under either reading. TEST can move all of this; these are TRAIN points. Reading A is the Architect's proposal and my KG1 added the safeguard (H-SHARE: not reachable by the cost bar alone if more than half the admitted rows are hashed/unencodable; here 12 %).

What the Captain is asked to ratify before the freeze commit: (1) `BAR_G` 0.5 pp; (2) `U_bar_G` 0.021 as reading A or reading B; (3) `h` = 0.5 for H-SHARE, whose TRAIN source is the 12.0 % above. I have not frozen anything.

## 5. Architect's prediction rows, for scoring at the ruling
GG-1 V1-V5 pass without a change: they pass, but V2 needed the candidate index (one re-record); GG-2 STOP-CEIL does not fire: **true** (NET_all 1.93 pp); GG-3 the chosen rule uses f3 or f7: f7 chosen, but it is the vacuous "no gate" bound (see section 3). GG-4/GG-5/GG-6 are TEST rows, not yet.

## 6. Next
On the Captain's ratification: freeze commit (rule `|out_freq − freq| ≤ 2 Hz` which is "admit all", with its TRAIN figures, `BAR_G`, `U_bar_G` in his form, `h`); then the TEST replay (cycles 401-1,200, about 45 minutes) and the TEST rows. If he prefers to freeze the plain widening (`F1b ≤ 31.18`) instead of "no gate", say so before the freeze.
