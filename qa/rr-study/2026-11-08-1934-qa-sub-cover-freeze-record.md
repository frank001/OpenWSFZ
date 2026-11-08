# SUB-COVER (#273): FREEZE RECORD (2026-11-08T19:34:00Z `date -u`), written BEFORE any O* output exists

Spec: `arch/sub-coverage` `4f3a477a21298c6a04f5c53df01e0c4ea525b4b6` (§0 to §5, Amendment 1 §6, Amendment 2 §7). Authority: the Captain, 2026-11-08, "go with your recommendations, move on to #273"; size rule: one offline pass over GAP-RELOCATE's 400 cycles, no replay, no station, no second night, no pilot.

## Frozen inputs and code

| item | value |
|---|---|
| Code (predicates are the code) | `sc_build.py`, `sc_force.py`, `sc_analyse.py` in `qa/rr-study/gap-residual-run/`, QA commit `aa8ceda542ae9564b1caec115f9c73791f5ca244`; SHA-256 `02ba7fc8…` (build), `3a84c7f1…` (force), `6321d609…` (analyse) |
| Corpus | night `20260925_2010`, GAP-RELOCATE's 400 cycles in order, `selection400.json` SHA-256 `42e092395dd5cf8b606c0b411b47f03cfe02fddef6e8d4087d0a5aab40168938`, `population.json` `c54b98b748c432d5c80f27e752580ef1bb62a68f415eaef03a2b1337e4f34fa5`, n_ref 12,124 (9,931 hits, 1,589 NR) |
| Stored buffers | `_qa-scratch\gap-residual\cap\off`: 1,182 files (400 O + 400 R2 + 382 R3), every SHA-256 equal to `capture_index.tsv` (checked 2026-11-08, 0 mismatches) |
| Natives | the product's OWN, stored per buffer in `cap/off/native/<stamp>.tsv` (frequency, unrounded dt, snr, text, production order); nothing is re-decoded (Amendment 2 replaces A1.1's re-decode) |
| Forced legs | GAP-RELOCATE's `gr_forced.force_cycle`, unchanged; `delta_p` 0.6, `delta_c` 0.7 (asserted against `deltas.json`); only the PCM argument changes. `libft8.dll` SHA-256 `1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914` (pin) |
| On-file forced records | `forced_all.jsonl` SHA-256 `4521a8c4888d609244808d76c1b95f5fb24a9bb8477b0c31f694458a5dd3b385` (35,493 records: O, R2, R3) |
| Fitter | the product's own native fitter through ctypes: `ft8_subfeas_compute_analytic` once per cycle, `ft8_subfeas_fit_signal(xaRe, xaIm, tones, native dt, native freq)` per signal, subtracted in float32 candidate by candidate, exactly as `SubtractionPass.RunCoreUnguarded` |
| Bootstrap | B = 2000 cycle resamples, seed 20261108, paired indices across every readout |
| Freeze-time figures | `_qa-scratch\sub-cover\freeze_figures.json`, SHA-256 `049bb8aefa1523ffa5b37da548f2a54799258c1a7e7bb5da2357782eacfafefc` |
| Frank-path check (A1.6) | `grep` for `Users\Frank` over `sc_build.py`, `sc_force.py`, `sc_analyse.py`, `gr_forced.py`, `gr_common.py`, `gr_item2.py`, `gres_main.py`, `nrtax_force.py`, `gap-locate/*.py`, `r2-coherent-llr-instrument/*.py`, `n1-extract-llrs-at-position/*.py`, `coh-fallback/cf_uprime.py`: **no match** |

## Freeze-time results (all before any O* output)

- **O-BUILD: PASS.** The builder, given only the batch-1 re-encodable natives, reproduces the stored R2 **bit-identically in 400 of 400 cycles** (max relative difference 0.0; 6,877 fits; 160 of them fit-zero, rc -3). Tolerance in the code: 1e-5 x peak; the observed figure is 0.
- **O-REPRO: PASS.** The forced legs on the stored R2 u R3 give GAP-RESIDUAL's classes exactly on its N rows (the misses GAP-RELOCATE's legs classed N on the original audio): RC 133, RG 51, RW 77, RP-search 10 (NR 1,589).
- **O-ROUND: does not exceed 0.5 pp.** The same batch-1 build with dt rounded to 0.1 s (frequencies are already integers in the natives): 391 of 400 cycles bit-identical to the stored R2; the share of the 7,239 batch-1 hits that the forced legs still decode (either leg) is 2.818 % on the stored R2 and 2.804 % on the rounded rebuild, **difference -0.014 pp [-0.042, 0.000]**. The batch-4 stratum, placed from published rounded values, is therefore not read as a lower bound on this ground.
- **O-ENC bar (A1.5): the fit-zero share of R2's own fits = 160 / 6,877 = 2.33 %.** The bar is that figure (the spec's 2 % would have failed R2 itself).
- **O-CTRL basis, on file, keyed by (stamp, idx)** (the review's figures keyed by `idx` alone were wrong: QA ledger Q40): batch-1 hits, either-leg share still decoded: O 93.12 %, R2 2.82 %, R3 2.87 % (6,978 rows with an R3 record); R3 - R2 = **+0.10 pp [+0.03, +0.18]**; batch-2 hits on R3: 3.44 %. Bar (Amendment 2): CI_hi(share_O* - share_ref) <= **+2.0 pp** for batch-1 vs R2 and batch-2 vs R3; a builder that failed to subtract a fraction f of the hits would show about 2.8 + 0.9 f pp, so +2 pp catches a failure on about 2 % of the hits or more.

## Registered rows and decision (as in `sc_analyse.py`)

O-REPRO, O-BUILD (done above), O-CTRL (paired, stratified, +2.0 pp), O-ENC (<= 2.33 %; if it fires the bound reads ">=" only). Readout: G* (NR rows decodable on O* by any leg: primary found, coherent v3_match any gate, or walk match, pp of n_ref), G273 = G* minus the CU-d stratum with a batch-3/4 stronger overlapping decoded neighbour (L1' territory), strata by NR-TAX category, wrong payloads. **BUILD-WORTH** if CI_lo(G273) >= 1.0 pp, **CLOSE** if CI_hi(G273) < 0.5 pp, otherwise BETWEEN (to the Captain). Valid only if O-REPRO, O-BUILD and O-CTRL pass. The report states how many more signals O* subtracts than R2 (Amendment 2).

## Choices stated while freezing

- O* subtracts **every published decode** (batches 1-4) from O in one pass, all fits on O's analytic signal (the spec's design): batches 2-3 are fitted on O, not on R2/R3 as the product does; a decode whose own text does not re-encode is re-encoded from the matched WSJT-X text (the oracle part); batch 4 is placed from the published (rounded) values.
- Message text is read in memory in the builder and never written (HK-037); outputs are float32 buffers and counts under `_qa-scratch\sub-cover`.
- QA errors on this arm, recorded before this freeze: Q39 (natives were stored; no re-decode needed) and Q40 (the review's shares were mis-keyed); both reported to the Architect before any O* output.

## Order from here

`sc_build.py ostar` (O* buffers, about 7 min) -> `sc_force.py ostar` (forced legs on 11,520 rows, about 5 min) -> `sc_analyse.py main` -> a short report (rows, G*, G273, strata, wrong payloads, signals subtracted vs R2) -> the Architect's ruling.
