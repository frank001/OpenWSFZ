# Artefact inventory -- what has already been collected

**GENERATED FILE -- do not hand-edit.** Regenerate with
`python qa/artefact_inventory.py`. Hand-written notes live in that
script's `NOTES` dict and survive regeneration.

Read this **before** concluding that data for a question does not
exist, and before proposing any capture run (HK-018, HK-004).

Every column except **notes** is measured from disk on each run and
cannot go stale silently. **notes** is interpretive and hand-written --
treat it as a claim to verify, not a fact.

Scanned: 2026-08-06 22:58 UTC | 29 runs | 106,156 total WAVs

| run | UTC span | legs (distinct cycles) | WAVs | notes *(interpretive)* |
|---|---|---|---|---|
| `20260613_live run 1h40_items` | - | - | `save` 406 |  |
| `20260614 WSJT-X Direct to OpenWSFZ` | 260614_173915 -> 260614_174530 | `(root)` 13 | - |  |
| `20260614_live_run` | - | - | `save` 2,171 |  |
| `20260615_live_run` | - | - | `save` 2,291 |  |
| `20260706_live_run_2308` | - | - | `save` 4,075 |  |
| `20260723_live_run_2223` | 260723_222330 -> 260724_061730 | `openwsfz` 1,897<br>`wsjtx` 1,886 | `wsjtx` 1,884 |  |
| `20260724_live_run_0821` | 260724_082145 -> 260724_143645 | `(root)` 1,501 | `wav` 1,501 |  |
| `20260724_live_run_1607` | 260724_082145 -> 260724_163845 | `(root)` 1,627 | `wav` 126 |  |
| `20260724_live_run_2227` | 260724_202800 -> 260725_081705 | `(root)` 1,789 | `wav` 2,827 |  |
| `20260725_live_run_1806` | 260725_180615 -> 260725_182645 | `c2_phase1/k10_c0.10_n60` 68<br>`c4_min_score/k10/k10_c0.10_n60` 68<br>`c4_min_score/k4/k10_c0.10_n60` 68<br>`c4_min_score/k4_cap2000/k10_c0.10_n60` 68<br>`c4_min_score/k6/k10_c0.10_n60` 68<br>`c4_min_score/k6_cap2000/k10_c0.10_n60` 68<br>`c4_min_score/k8/k10_c0.10_n60` 68<br>`c4_min_score/k8_cap2000/k10_c0.10_n60` 68<br>`c4_min_score/shipped_check/k10_c0.10_n60` 68<br>`owsfz` 94<br>`wsjt-x` 93 | `owsfz` 152<br>`wsjt-x` 143 |  |
| `20260726_live_run_2106` | 260726_210630 -> 260727_085215 | `owsfz` 2,685<br>`wsjt-x` 2,707 | `owsfz` 2,760<br>`wsjt-x` 2,798 |  |
| `20260727_live_run_2048` | 260727_204845 -> 260728_091545 | `owsfz` 1,999<br>`wsjt-x` 741 | `owsfz` 2,971<br>`wsjt-x` 2,970 |  |
| `20260728_live_run_1319` | 260728_111915 -> 260728_205730 | `owsfz` 1,823<br>`wsjt-x` 1,712 | `owsfz` 2,315<br>`wsjt-x` 2,313 |  |
| `20260728_live_run_1812` | 260728_161245 -> 260728_205730 | `owsfz` 1,140 | `owsfz` 1,141 |  |
| `20260728_live_run_2354-8080` | 260728_235400 -> 260729_145115 | `owsfz` 3,492<br>`wsjt-x` 3,555 | `wsjt-x` 3,575 |  |
| `20260728_live_run_2354-8081` | 260728_235400 -> 260729_145115 | `owsfz` 2,494 | - |  |
| `20260729_live_run_1831-8080` | 260729_183130 -> 260730_183945 | `owsfz` 3,926<br>`wsjt-x` 5,757 | `owsfz` 5,795<br>`wsjt-x` 5,783 | Pre-drift-fix. Superseded by the 07-31 run for D-001 work. |
| `20260729_live_run_1831-8081` | 260730_092815 -> 260730_154030 | `owsfz/10m` 1,490<br>`owsfz/20m` 1,364<br>`owsfz/80m` 1,932 | `owsfz` 5,773 |  |
| `20260731_live_run_2004-8080` | 260731_200430 -> 260802_155200 | `owsfz` 10,475<br>`wsjt-x` 10,470<br>**HARDLINKED** `wsjt-x` = `20260731_live_run_2004-8081`/`wsjt-x` | `owsfz` 10,489<br>`wsjt-x` 10,469 | **D-001 Angle 1 corpus.** One WSJT-X instance (hardlinked into the -8081 folder too -- one capture, not two). Feeds legs A/B/C and null N3, which needs exactly this: jt9 over WSJT-X's own WAVs vs its own live count. N3 runnable offline, no capture needed. T4 unauthorised as of 2026-08-02. |
| `20260731_live_run_2004-8081` | 260731_200430 -> 260802_155200 | `owsfz` 10,467<br>`wsjt-x` 10,470<br>**HARDLINKED** `wsjt-x` = `20260731_live_run_2004-8080`/`wsjt-x` | `owsfz` 10,512<br>`wsjt-x` 10,469 | Same WSJT-X capture as -8080 (hardlinked ALL.TXT + wav/). The owsfz leg IS distinct. Do not treat the two wsjt-x legs as independent captures. |
| `20260803_live_run_1713` | 260803_171330 -> 260804_135645 | `owsfz` 4,614<br>`wsjt-x` 4,531 | `owsfz` 4,971<br>`wsjt-x` 4,963 | **D-001 replication corpus -- DO NOT PROPOSE A CAPTURE RUN FOR D-001.** Answers project-state-2026-07-31 S5.4, which named the WSJT-X same-family control 'the single most decision-relevant unknown for the menu' and assumed the capture had not been run. It had -- two days later, into this folder. 20m (14.074), ONE contiguous 18.96h decisive epoch from 260803_185914, drift screen ROW 5 PASS (+0.0 ppm), post-be5960a. Both decoders on ONE verified audio path (median |r|=0.987 over 8 WAV pairs, lags <=34ms) -- unlike the split -8080/-8081 runs, so re-verify per corpus rather than inheriting either way. Density contrast 6.54x. Consumed by Tasks 1/3/5 and by Arm R.D (specced 2026-08-05, not run, not authorised). |
| `20260806_cross_decode_replay_2009` | 260806_200930 -> 260806_223330 | `wsjtx-all-time` 212 | - |  |
| `d001_b1b_second_corpus` | 260724_160730 -> 260724_163845 | `our_offline/k10_c0.10_n60/k10_c0.10_n60` 126 | - | Second corpus for the B.3 costed menu (2026-07-27). Menu decision still open. |
| `d001_c2_phase2c` | 260725_180615 -> 260725_182645 | `ber/k10_cap140/k10_c0.10_n60` 68<br>`ber/k4_cap2000/k10_c0.10_n60` 68<br>`selfcheck/new_weight0/k10_c0.10_n60` 68<br>`selfcheck/pristine/k10_c0.10_n60` 0<br>`selfcheck/revert_check/k10_c0.10_n60` 68<br>`sweep/w0.00/k10_c0.10_n60` 68<br>`sweep/w0.25/k10_c0.10_n60` 68<br>`sweep/w0.50/k10_c0.10_n60` 68<br>`sweep/w0.75/k10_c0.10_n60` 68<br>`sweep/w1.00/k10_c0.10_n60` 68 | - |  |
| `d001_r4_sensitivity_gap` | - | - | `buffers` 51 |  |
| `d001_r5_hybrid_ladder` | - | - | `buffers` 80 |  |
| `d001_wav_source_cross_decode_2026-07-30` | 260730_064015 -> 260730_064730 | `ours_on_owsfz/k10_c0.10_n60` 30<br>`ours_on_wsjtx/k10_c0.10_n60` 30 | `owsfz_wav` 30<br>`wsjtx_wav` 30 | Capture-chain cross-decode; source of the ~10-13% capture-chain effect. |
| `p10-decoder-ground-truth_items` | 260528_235730 -> 260529_000800 | `(root)` 43 | `save` 42 |  |
| `p12-ft8lib-port_UAT-01_items` | 260530_154500 -> 260530_165315 | `(root)` 274 | `save` 280 |  |

## How to read the `legs` column

`owsfz` is our daemon's `ALL.TXT`; `wsjt-x` is the comparison decoder's.
**HARDLINKED** means two leg paths resolve to the same inode -- one
capture gathered into two folders, not two independent captures. That
is fine for anything needing a single instrument and fatal for anything
assuming two.
