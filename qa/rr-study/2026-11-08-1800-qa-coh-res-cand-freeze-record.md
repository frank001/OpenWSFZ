# COH-RES-CAND (#272) acceptance: FREEZE RECORD (written 2026-11-08T17:59:58Z `date -u`, BEFORE any arm output exists)

Spec: `arch/coh-res-cand` `14f4e28d72e5e91fed42edef99b47d3e57d3ed11` (build spec §0 to §5, Amendment 1 §9, Amendment 2 §10, Amendment 3 §11). The Captain's go for the arms: 2026-11-08 ("go"). Size rule (the Captain's): two 400-cycle arms on the PC and one 40-cycle B-OFF; no second night, no sol, no pilot, no Original arm.

## What is frozen

| item | value |
|---|---|
| **Build of record (the build under test)** | `b0d01f4f1335cd5f98c2d43d9b67a4afea0dbd1e` (`feat/coh-res-cand`, off `origin/main` `e3db42cf`, v0.69, local, unpushed). **`pre_merge_check.py` will be run on exactly this SHA after the arms (Captain's order, Architect's request).** |
| QA's HK-039 review of that commit | `qa/rr-study/2026-11-08-1750-qa-code-review-coh-res-cand-b0d01f4f-APPROVED.md` (`a2ebaabb`), `Reviewed-commit: b0d01f4f1335cd5f98c2d43d9b67a4afea0dbd1e`, Verdict APPROVED |
| B-OFF reference build | `main` `fe1454c1` (v0.68), source clone `_qa-scratch\same-chain\src` |
| `libft8.dll` (both builds) | SHA-256 `1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914` (= the pin), re-hashed by the arms script at the start and end of every arm |
| Harness | Replay81 / `Ft8.FitProbe` from QA commit `9140304e38b0d0e363abb31c37503f4de6a8b2d7` (`--cohrescand 0\|1`, the regex tail); `bin_new` `Ft8.FitProbe.dll` SHA-256 `927e8f2baf6bf3d93e7db9d8d519b11b1a921b9391c5952d43f6cb475244a6e2`, `bin_main` `Ft8.FitProbe.dll` `105b85ff79270e7b15f66e395282402c279db874af43342209f27e0d4f0a1f56` |
| Arms script | `qa/rr-study/gap-residual-run/crc_arms.sh`, SHA-256 `4c6267778db0cd15fd185ed600f47d2aa39761018cd0b8873fc5814a1d2671fb`, QA commit `87c5486a9091d4d4ff770d26c785d8ec1715e742` |
| **Analysis code** | `qa/rr-study/gap-residual-run/crc_analyse.py`, SHA-256 `1352e4dd563011f8f51862f92239a37db96cb20edf308b10619b891f32c4af9c`, QA commit `87c5486a9091d4d4ff770d26c785d8ec1715e742`; adapted from `tn_analyse.py` at `d50a98fe` (same scoring, same instrument, same bootstrap; B = 2000, **seed 20261108**) |
| Night and selection | `20260930_1930`; frozen selection `selection_3n.json` SHA-256 `2575e115378c71c068cd250d26dd002a17d7d365366cd00e6aaa3a99d2329c4f` (L1' third night, 800 cycles); the arms use its **first 400** cycles in order, one process from the first (`sel_400.json` SHA-256 `7691e33b6949ffc354781724c90c1aeb9df0e2d5bc76285c92b9a86bc6007f01`) and its first 40 for B-OFF (`sel_40.json` `1bcd283f951db30e8031ac75f1da16313c8aaa2b97668f1ed7680d08e18b05dc`) |
| Classes (reused as they are) | `u3_800/orig800_classes.json` SHA-256 `8046a4be4b806fcd08b90d376ece7c1203f86446a0476cc98167f8f4a2fc38c1`, passed on the command line to the analysis and asserted |
| Reference lines | the night's WSJT-X `ALL.TXT` in `artefacts\20260930_1930_endurance_run-gathered\wsjt-x\` |
| Settings (arms A and B; identical but one) | Deep (`three1`), `nhard` 24, OSD sign fix 1, 8 threads (as the L1' PC arms), multi-set ON, `coherentFallbackAudio` Both, R-F4 OFF, late round OFF; **only `--cohrescand` differs: A = 0, B = 1**. Read back at start and end of every arm and checked by the script. |
| Sol records for V1-3N | `_qa-scratch\late-sub\sol3n\scratch\off\nc_dump.tsv` (sol OFF arm, `b1d8a06e`, `libft8.so` `488bfa0b…`), first 400 cycles |

## Registered rows (the code of `crc_analyse.py` is the predicate)

B-NAT, B-OFF (40 of 40 cycles, every published field), B-WIRE with Amendment 3's denominator (arm-B cycles whose fallback line shows `audio=both(residual2|residual3)`; a residual-level cycle logged `fallback-orig` stays in it; (i) `resCand=residual-*` in >= 95 %, (ii) `resEligible` != `origEligible` in >= 1; `resEligible`/`origEligible` only, never `eligible=`), B-DUP, N-GO (CI_lo > 0 pp), N-STOP (CI_hi <= 0), U-OK (CI_hi <= 0.021), U-FAIL (CI_lo > 0.021), B-AB, V1-3N (A against the sol OFF arm, 400 of 400; read after arm A and BEFORE arm B starts; if it forces the fallback, arm A is re-run on `20261022_1949` and the Captain is told). Verdict: ACCEPT iff B-NAT, B-OFF, B-WIRE, B-DUP, N-GO, U-OK, B-AB all pass; FAIL iff N-STOP or U-FAIL; OPEN otherwise (to the Captain, no second night automatically).

## Choices made while freezing (stated, HK-038)

- **dU'_ta** is taken over the **batch-4 (fallback) outputs** of B whose text is absent from A's rows of that cycle and that WSJT-X did not corroborate, classified by the frozen instrument: `tn_analyse.py` did this for batch 5, and this lever's new rows are fallback rows. Any other kind's new text is not in dU' (reported only in the descriptive B-only/A-only counts).
- **B-AB** is evaluated on the combined `abandoned` figure of the fallback line (cycles with `abandoned > 0`, B <= A). The line carries one number for both runs; the per-run split of A1.2 cannot be read from the log, and the build was not changed for it. A1.2's bar is A itself.
- **Threads:** 8, as the L1' PC arms and the sol records V1-3N compares against (the daemon's own auto setting on this PC is 14; the §7 reference used 14 to match the daemon).
- **Dry run, disclosed:** one plumbing run of 3 cycles OUTSIDE the selection (`selection_3n_dry.json`: `260930_193115`, `193130`, `193200`), OFF and ON, on the build under test, to prove the new log fields reach the log and the read-backs and row counts work; its outputs were deleted. QA SAW its numbers (a 3-cycle NET and counts, meaningless at that size) while smoke-testing the analysis script. It is not a pilot of the measure.
- The analysis script was smoke-tested on that dry set (and its `boff` path on copies of it); `v1` was read in code only (the dry stamps are not in the sol records).

## Order from here

1. `crc_arms.sh stage1`: B-OFF (`bo_main` on `fe1454c1`, `bo_new` on `b0d01f4f` with the setting OFF, 40 cycles each), then arm A (400 cycles). Detached, logged, orphan-checked.
2. Read `crc_analyse.py boff` and `crc_analyse.py v1 8046a4be…` (full SHA above). STOP if either fails and tell the Captain.
3. `crc_arms.sh stage2`: arm B (400 cycles).
4. `crc_analyse.py main 8046a4be…`, then QA's short report (rows table, the descriptive lines, nothing else) to the Architect for the ruling.
5. After the ruling: `pre_merge_check.py` on a clean checkout of `b0d01f4f1335cd5f98c2d43d9b67a4afea0dbd1e`, then the Captain's push go and merge sign-off.
