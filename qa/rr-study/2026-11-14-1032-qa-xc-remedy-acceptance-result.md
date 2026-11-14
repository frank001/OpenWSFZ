# XC-BUILD remedy build `4b70e418`: acceptance arms, two nights (QA, 2026-11-14T10:31:35Z `date -u`)

**To:** Architect. **From:** QA. Branch `qa/same-chain`, local, nothing pushed. **Counts only** (NFR-021, HK-037). Result files: `qa/xc-build/results/xc_remedy_{T,N}_*.json`, `xc_te_v2_full_2026-11-14.json`.

## 1. Reading by the A6.5 decision table (QA's mechanical reading; the ruling is the Architect's)

**ACCEPT-2N (row 4).** On **both** nights CI_lo(NET) >= 0.4 pp and LATE holds; no earlier row fires: V-OFF PASS (TEST), V-STORE PASS, V-WIRE PASS, V-TE PASS (exact), V-TR-P PASS, SHADOW PASS and **XC-SUP PASS on both nights**. Cite the two nights separately, never pooled. The TEST night is no longer naive (XC-PARITY used its rows to size the gate); **the 40 m night is the clean one.**

## 2. Provenance (HK-020, HK-022)

- **Host:** the PC, Windows, 8 threads read back in every arm, `clock=system`; one build for every arm: the harness build of `4b70e418` (Ft8 library of that commit, `bin_remedy`), `libft8.dll` SHA-256 `bbde6eb66af4cd429ffc46f67291ba718c1ae36ae39665faac24629bcb6e6528` (the pin; checked before every arm and at the end, "END new-build libft8.dll pin OK"). HK-039 record `2026-11-14-0256-qa-code-review-xc-build-remedy-4b70e418-APPROVED.md` (`70584a5d`).
- **Chain:** `qa/xc-build/xc_pc_chain_remedy.sh`, started 2026-11-14T02:56:22Z, ended 10:30:55Z, `halted=0`, no hibernate. No filter (every arm ran its full selection; 500 rows for TR2, 1,000 for each night arm). **Not run: the other nine test projects** (the Developer's counts, not QA's).
- **Frozen values (te_v2, committed before any OFF/ON arm):** T_E 3.076041980658299, **T_P 2.2220253019230114** (TRAIN, A6.3's rule), K 36, FA\* 0.000583. The R14 veto was ON in every OFF/ON arm and OFF only in TR2 (readbacks `xcveto=` and `xctp=` asserted per arm).
- **Selections:** TEST `20260808_0016` first 1,000 cycles (sha `d12be505…`, the 75 s hole before cycle 1 as before); 40 m night `20261028_2233`, first 1,000 contiguous cycles after the warm-up (sha `1eaadbc0…`, registered at `d30637e1` before any data).
- **Load:** nothing else ran on the PC during the arms (my CPU-heavy work waited); late round abandoned 0 of 1,000 cycles in all four arms.

## 3. TR2 (TRAIN `20261110_1817`, 500 cycles, veto OFF, T_E +inf)

V-TE **exact**: T_E 3.076041980658299 and 23,219 shadow tests, bit-identical to TR1. K1 join 927 of 927 unique; K3 offset 0.610 s; classes (units) COR-like 264, SUP-like 342, FREE-like 321; V-TR-P true; T_P 2.222025 keeps 89.8 % of COR-like and removes 96.5 % of SUP-like and 38.0 % of FREE-like on TRAIN (descriptive).

## 4. The rows, per night

| Row | **TEST night (20 m, not naive)** | **Night N (40 m, clean)** |
|---|---|---|
| V-OFF (OFF against `f82b6432`'s TEST OFF) | **PASS**: matchedbatch 0 of 1,001, testb 0 of 21,001 (b6 rows zero), per-cycle 0 of 1,000, nc.tsv 0 of 21,051 | no reference exists for this night (A6.4: V-OFF is OFF-T only) |
| V-STORE | PASS (ages 2/4/6 and 1/3/5) | PASS |
| V-WIRE | PASS (ON differs in 706 cycles) | PASS (874 cycles) |
| n_ref / corroborated OFF / ON | 25,493 / 20,335 / 21,191 | 33,861 / 27,788 / 28,739 |
| **NET** | **+3.358 pp [3.131, 3.572]** (+856 rows, all batch 6) | **+2.809 pp [2.631, 2.995]** (+951 rows, all batch 6) |
| cycles ON > OFF / ON < OFF | 521 / 0 | 607 / 0 |
| batch-6 publishes | 1,661 | 2,110 |
| classes COR / SUP-W / SUP-O / FREE | 856 / **6** / 1 / 798 | 951 / **7** / 2 / 1,150 |
| SUP-W sharing the sender token | 1 | 0 |
| SHADOW | 5 events = 0.005 per cycle [0.0016, 0.0117], bar 0.042: PASS | 4 events = 0.004 [0.0011, 0.0102]: PASS |
| **XC-SUP** n(SUP-W) + shadow events <= 29 | **11: PASS** | **11: PASS** |
| LATE: publishes after the 13 s budget | 0 (batch-6 publish p95 7.26 s, max 8.52; cycle p95 7.28 s ON vs 7.05 OFF) | 0 (batch-6 p95 7.55 s, max 8.29; cycle p95 7.66 ON vs 7.47 OFF) |
| ABANDON (live / shadow tested) | 0 of 33,360 / 0 of 42,482 | 0 of 43,612 / 0 of 57,952 |
| DT offset check (K3) | median 0.600 s, p05 to p95 [0.600, 0.700] | median 0.600 s, [0.600, 0.600] |
| R14 veto cost if it were the only gate (descriptive) | 0.020 pp | 0.004 pp |

For comparison, the build before the remedy (`f82b6432`) on the TEST night: NET +3.546 pp, 2,579 publishes of which SUP-W 641, shadow 25 events (XC-SUP 666, fail). **No ungated arm exists on the 40 m night**, so the gate's own effect there is not measured; its NET cost on the TEST night is 0.19 pp.

## 5. What this does not say (stated, as in A6.5)

- **SUP-W sees only stale templates where WSJT-X decoded the real message.** FREE (798 on TEST, 1,150 on N: 48.0 % and 54.5 % of publishes) is unseen by it. FREE fell by 21.6 % from the ungated TEST arm, near XC-PARITY's 23.7 %, so the gate acts there, but QA cannot count false decodes inside FREE.
- **The chance co-location rate** (ordinary matched decodes against a different-text WSJT-X row in the window) is 1.9 % on TEST and 2.8 % on N; at those rates 7 SUP-W of 2,110 is below chance expectation, which is consistent with the stale class being gone, not a measurement of the remaining false rate.
- **Descriptive U' on the remedy arms is not computed** (angle A's blindness stands beside any U' row: U' on O is blind under burial, 0.742 against 0.993).
- **Two nights, two bands**; TRAIN is 40 m, so night N is on TRAIN's band; TEST is the cross-band night. The gain is smaller on 40 m (2.81 against 3.36 pp).
- **macOS and Linux CI have not run this commit** (not pushed); the numeric fixtures use a relative tolerance of 1e-3.

## 6. Owed before any default-ON (not QA's to rule)

PSK Reporter template tag (Architect); `BatchesPerCycleFallbackOn = 4` (Architect); the Captain's go. **QA's own:** confirm that mutant R05 dies on the Developer's `a88dd402` (tests only; the arms ran on `4b70e418`) and write its short review record; `pre_merge_check` on the exact commit before any push (HK-006). Text-bearing working files (`nc.tsv`, `matched.csv`) stay under `_qa-scratch\xc-chain\` until the Architect says they may go; they are deleted before the PC hibernates.
