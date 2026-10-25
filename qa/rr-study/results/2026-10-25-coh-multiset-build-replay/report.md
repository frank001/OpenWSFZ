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

- **§6.7 per-set split (published / KNOWN / gated out)**: the offline companion through the native run export on the frozen selection (same pin) is NOT yet run; descriptive only, no rebuild (Amendment 4).
- One night, one band (40 m), one corpus. NET here (+1.449 pp) is smaller than the arm's +2.115 pp [1.937, 2.302]; they are different instruments (the arm re-decoded at WSJT-X's positions in a 975-cycle sample; this is the whole product pipeline over 2,882 cycles, where earlier passes already take part of the gain). Never difference them.
- The PC run had no U′ stage (not required); V8 is the PC's contribution.
- Nothing is pushed. **Default ON** would need D-GO and U′-OK (both met here) and the Captain's decision. Before any push: `pre_merge_check.py` from a clean checkout of the exact commit, and the Linux/macOS binary refresh chore (HK-006).

## 6. Files

`sol_analysis.json` (all rows), `v8.json`, `sol/` (U′ stages, per-cycle and by-band CSVs, class list, chain and arm status), `pc/` (chain and arm status, hibernate log). Scripts: `qa/rr-study/coh-multiset-build/` (`mb_analysis.py` `f7ffefd3`, `sol_chain.sh` `51701eb2`, `pc_chain.sh` `f813d5ff`).
