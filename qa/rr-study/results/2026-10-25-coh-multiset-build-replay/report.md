# COH-MULTISET-BUILD — decision replay (spec §6, Amendments 1–4)

**QA, 2026-10-25.** Numbers only; no message text leaves the working files (HK-037); no callsigns (NFR-021).
Build under test: Developer `d7750bde` (shim 20260071). Replay81 `14f7ad6f`. Night `20260925_2010` WHOLE, 2,882 cycles (frozen selection `81372df5`, SHA-256(LF) `53d9ba4e…331c4`), owsfz/wav (direct-USB, pre-Voicemeeter Windows chain: the sol WAV taint does not apply).
Settings, identical on both machines: Deep, subtraction ON, nhard 24, OSD sign fix 1, 8 threads, coherent fallback ON in every arm; REF `cohms=0`, MS `cohms=1`.
Pins: sol `libft8.so` `488bfa0b90a570ad0bc9f285d871147f62f4a71165fcf6dc39bd31eb584f58d0`; PC `libft8.dll` `1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914`. Both re-hashed at the start and end of every arm.
Bars (the Captain's, frozen before any decode, HK-038 source: his decision 2026-10-24, relayed in Amendment 3): **D_bar 0.5 pp** (D-GO if CI_lo ≥ 0.5; D-STOP if CI_hi < 0.5), **U′_bar 0.021 per cycle** (U′-OK if CI_hi ≤ 0.021; U′-FAIL if CI_lo > 0.021). Block bootstrap, blocks of 40, B 10,000, seed 20261025.

## 1. Verdict (sol, 2,882 cycles; 2,880 with WSJT-X decodes)

| | Result | Bar | Row |
|---|---|---|---|
| **NET** (Test B, MS − REF, ratio estimator) | **+1.449 pp [1.339, 1.568]** (ΔM = +1,116 of W = 76,999; REF 76.28 % → MS 77.73 %) | CI_lo ≥ 0.5 | **D-GO** |
| **ΔU′** (paired, per cycle, ws > 0) | **+0.00486 [0.00208, 0.00799]** | CI_hi ≤ 0.021 | **U′-OK** |

Both bars are cleared with the whole interval on the right side; neither is near its edge (D by 0.84 pp, U′ by 0.013 per cycle).

## 2. Validity rows

| Row | Result |
|---|---|
| V1 pin start = end, every arm (sol and PC) | PASS (`preflight_end_ok=1`, pin in the status files; both orphan checks clean) |
| V2 readbacks start and end (Deep, nhard 24, sign fix 1, shim 20260071, cohfb True, cohms False/True) | PASS, sol REF/MS/MS-repeat and PC REF/MS |
| V3 exceptions | 0 / 0 / 0 |
| V4 batches 1–3 identical MS vs REF | PASS: 0 differing cycles, no ordinary-pass abandonment exceptions |
| V5 cycles with abandoned work (limit 1 % sol, 5 % PC) | PASS: sol REF 0/2,882, sol MS 0/2,882 (Wilson upper 0.13 %); PC REF 0, PC MS 0 |
| V6 MS-repeat vs MS, first 320 cycles | PASS: 0 differing, 0 unexplained |
| **V7′** every REF batch-4 decode is in MS | **PASS**: 0 cycles with a REF batch-4 decode missing in MS; 32 same-text-on-another-candidate exceptions, listed one by one in `sol_analysis.json` (stamp, freq, dt, snr); 0 abandonment-explained cycles. MS-only batch-4 decodes: 1,239 |
| **V8 PC outcomes = sol outcomes, per cycle** | **PASS**: REF 2,882 of 2,882 cycles equal, MS 2,882 of 2,882 equal, 0 unexplained, 0 abandonment-explained (`v8.json`) |

V7′ limit, stated as the spec requires: the replay carries no per-decode provenance, so "MS has no *new* V3-provenance decode" is not checked here. It rests on the P1 cross-check (product walk == export walk, 20,980 real rows, 150 cycles) and on V4 (batches 1–3 identical).

Because V1–V8 all pass on sol and V8 shows the PC reproduces sol exactly, the sol verdict is the verdict; the PC run is the confirming build of record (Amendment 3), and no MS-repeat on the PC was needed.

## 3. U′ detail (REF note, owed since the REF arm)

- **U′0 (REF) = 0.1309 per cycle** (377 of 2,880 cycles' worth: tested-absent 73, hashed/unencodable 302, untestable class 2; tested-present 346; 723 not-confirmed decodes). MS: 0.1358 (tested-absent 77, hashed/unencodable 312, untestable 2; tested-present 423; 814 not-confirmed).
- Instrument: `cf_uprime.py` with `cf_fbid.py` @ `ecc4c5e7`, T 0.276; this night's own null p99 0.2759 (|Δ| 0.0001, no flag to the Architect); class list frozen from REF alone and applied unchanged to MS. Calibration: 73 of 80 controls with sync hit ≥ 0.6.
- **Where the extra not-confirmed decodes go:** MS adds 91 not-confirmed decodes; 77 of them (85 %) are shown present in the audio at their position by the instrument, 4 are tested absent, 10 are hashed/unencodable. U′ counts only the 14 not shown present: +14 / 2,880 = +0.00486.
- §6.5 lines from the REF stage: U′_max = 0.30 × U′0 = 0.0393 ≤ 0.042: true; 2 × projected half-width 0.0205 ≤ U′_max: true. Projected paired half-width 0.0187 (A11.2) against the observed 0.0030: the instrument is far tighter than projected.
- **Descriptive only, not a bar:** the older Test-B ΔU (all not-confirmed decodes, nothing shown present subtracted) is +0.0316 [0.0257, 0.0375], above 0.021. It is reported because it is the number one would get by counting every not-confirmed decode as unwelcome; the ruled bar is U′, which counts only those not shown present. By band, the change in not-confirmed decodes is A 0, B +2, C +4, **D +85**: it is almost entirely the weakest band.

## 4. Cost (descriptive)

| | REF | MS |
|---|---|---|
| Fallback wall time per cycle, median / p95 / max | 457 / 691 / 1,007 ms | 586 / 849 / 1,217 ms |
| Cycles publishing batch 4 | 1,987 | 2,281 |
| Batch-4 publish time, median / p95 / max | 6.92 / 9.15 / 10.40 s | 7.06 / 9.28 / 11.31 s |
| Minimum margin to the 13 s budget | 2.60 s | **1.69 s** |

MS-repeat timing agrees with MS (median 605 ms). The tightest cycle leaves 1.69 s to the budget on sol (8 cores); the PC (16 logical cores) ran each arm in roughly 40 % of sol's time.

R10 counters, MS: walk entered 359,853 of 456,185 attempted; CRC-valid counts by set C1 13,856, J2 3,914, J3 2,161, N1 8,456 (these are CRC hits at the walk, not wins; many are the same message already known); fallback published 4,927.

## 5. Not done, and limits

- **§6.7 per-set split**: see §7 below (run after the ruling, descriptive, no rebuild). The "FP-watch on U′ by provenance" and the provenance clause of V8 are unobtainable from the replay and dropped (Architect, ledger E63).
- One night, one band (40 m), one corpus. NET here (+1.449 pp) is smaller than the arm's +2.115 pp [1.937, 2.302]; they are different instruments (the arm re-decoded at WSJT-X's positions in a 975-cycle sample; this is the whole product pipeline over 2,882 cycles, where earlier passes already take part of the gain). Never difference them.
- The PC run had no U′ stage (not required); V8 is the PC's contribution.
- Nothing is pushed. **Default ON** would need D-GO and U′-OK (both met here) and the Captain's decision. Before any push: `pre_merge_check.py` from a clean checkout of the exact commit, and the Linux/macOS binary refresh chore (HK-006).

## 6. Files

`sol_analysis.json` (all rows), `v8.json`, `sol_desc.json` and `pc_desc.json` (§7a, §7b), `split_full.json` (§7c), `sol/` (U′ stages, per-cycle and by-band CSVs, class list, chain and arm status), `pc/` (chain and arm status, hibernate log). Scripts: `qa/rr-study/coh-multiset-build/` (`mb_analysis.py` `f7ffefd3`, `mb_desc.py` `d17db18c`, `mb_split.py` `0daab602`, `sol_chain.sh` `51701eb2`, `pc_chain.sh` `f813d5ff`).

## 7. Follow-ups owed by the ruling (descriptive; no bar on any of it)

**(a) NET and ΔU′ by Test-B band, sol.** Bands are Replay81's SNR bands of the OpenWSFZ decode (A ≥ 0 dB, B ≥ −10, C ≥ −15, D below). Same bootstrap as the verdict.

| Band | Δ matched decodes | NET, pp [CI] | ΔU′ per cycle [CI] |
|---|---|---|---|
| A | 0 | 0.000 [0, 0] | 0.0000 |
| B | +20 | +0.026 [0.016, 0.037] | +0.00035 [0, 0.0010] |
| C | +289 | +0.375 [0.332, 0.420] | +0.00035 [0, 0.0010] |
| D | +807 | +1.048 [0.959, 1.143] | +0.00417 [0.0017, 0.0069] |

The band changes sum to the verdict's +1,116 (and ΔU′ to +14 / 2,880 = +0.00486): the gain and almost all of the U′ cost sit in band D. The PC run has no U′ stage, so there is no PC ΔU′ by band.

**(b) PC cost lines (`coh.csv`, through the verdict's definitions).** Fallback wall time median / p95 / max: REF 203 / 328 / 495 ms → MS 237 / 373 / 583 ms. Batch-4 publish time median / p95 / max: REF 2,777 / 3,622 / 4,256 ms → MS 2,798 / 3,650 / 4,360 ms. Minimum margin to the 13 s budget: REF 8,744 → MS 8,640 ms. These equal the Architect's own reading of `coh.csv`. (Sol, same lines: §4; margin 2,601 → 1,686 ms.) The tight margin is the 8-core sol's, not the product's.

**(c) Per-set split (Amendment 4.2).** `mb_split.py` calls the native run export (`ft8_coherent_fallback_run`, the product's own per-candidate body) on the frozen 2,882 cycles with the Stage 2 pin (`1ba8dc3d…db914`), flags 0 and `FT8_COH_RUN_MULTISET`, no deadline. Limit: candidates and the ordinary-decode snapshot come from ONE `ft8_decode_all` pass, not the replay's Deep multi-pass pipeline, so the counts describe the sets, not the replay's totals. Check against the replay: the first-success counts per set are identical to the replay's R10 counters (C1 13,856, J2 3,914, J3 2,161, N1 8,456; 28,387 in all); rows entering the walk 359,851 here against 359,853 in the replay (2 of about 360,000).

Rows where V3 found nothing and a set found a CRC-valid payload, by the set that won first (C1 > J2 > J3 > N1) and what happened to it:

| Set | First successes | KNOWN (already decoded) | Gated out (new, F1b > T1) | Publication candidates (new, F1b ≤ T1) | Distinct new payloads per cycle, summed |
|---|---|---|---|---|---|
| C1 | 13,856 | 13,647 (98.5 %) | 87 (0.6 %) | 122 (0.9 %) | 33 |
| J2 | 3,914 | 2,028 (51.8 %) | 431 (11.0 %) | 1,455 (37.2 %) | 638 |
| J3 | 2,161 | 446 (20.6 %) | 350 (16.2 %) | 1,365 (63.2 %) | 676 |
| N1 | 8,456 | 7,891 (93.3 %) | 213 (2.5 %) | 352 (4.2 %) | 147 |
| **All** | **28,387** | **24,012 (84.6 %)** | **1,081 (3.8 %)** | **3,294 (11.6 %)** | **1,494** |

- Walk entered on 359,851 rows; on 331,464 of them (92.1 %) no set found anything.
- Distinct new payloads that MS publishes beyond OFF's own publication candidates: **1,438** (the per-set column sums to 1,494 because one message can be found by more than one set; the per-cycle text dedup admits each once).
- **J2 and J3 together produce 1,314 of the 1,494 (88 %) distinct new payloads**, N1 10 %, C1 2 %. C1 wins the most rows (49 %) but almost all of them are messages the ordinary decode already has, which is why the earlier "C1 wins 743 of 1,316" observation did not mean C1 matters.
- OFF baseline on the same rows (V3 alone): 84,263 KNOWN, 2,783 gated out, 9,286 publication candidates.
- Not obtainable and dropped: provenance per replay decode (the replay has none), hence no FP-watch on U′ by provenance.
