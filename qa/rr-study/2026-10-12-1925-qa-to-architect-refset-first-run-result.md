# First reference-set run on `sol`: result, and the residual pass is slower than the cycle with no deadline (QA)

- **To:** Architect, cc Captain. **From:** QA. **Date:** 2026-10-12 19:25Z (`date -u`). **Go:** the Captain, in the QA window: "do all three" (copy the results, update the board, tell the Architect).
- **Descriptive baseline, not a ruling.** A NEW SERIES (Linux, FX-8350, replay-only budget override). Never pool with Windows or with any other series. Nothing filed, nothing pushed.

## What ran (HK-022 pins)

| item | value |
|---|---|
| Driver | `qa/refset` `ec49cd4c` (local), `run_refset.py --tier standard --legs A,D,B --d-scope quick --pass first-run-76aa48cd-standard`, via the unattended queue `queue_first_run.sh` |
| Build | `main` `76aa48cd` (v0.57) + replay-only budget override (Developer `f6a1aa79`; managed patch SHA-256 `af42583b33fb9869adfda8dc86fbe157c612fcd36e90e20f473d2cd2063ec1bf`), Linux `.so` built on sol with gcc 14.3.1 |
| Native pin | actual `dc517dc9ba88b78618535fcf9da4ad8bcf3db18cfd4a68e186459520bd618e6c` = pinned (`--expect-native-sha`) |
| Corpus | `rr-s6-refset-corpus`, 15,704 files verified at start |
| Settings | `nhard` 24, OSD sign fix on, 8 threads, `OPENWSFZ_SUBTRACTION_BUDGET=unlimited`; banner "budget override = unlimited (replay only)" |
| Span | 2026-10-12 00:59:24Z to 18:40:07Z, 33 of 33 blocks, one decode process at a time, abandonments A 0 / B 0 / D 0 |
| Label | "first run, baseline: main 76aa48cd + replay-only subtraction budget override (unlimited), Linux .so built on sol, sol FX-8350" |

## Numbers (from `aggregate.json`)

| measure | value |
|---|---|
| Leg A vs live OWS, non-hashed reproduction | 0.9814 [0.9789, 0.9837] (13,313 of 13,566 live rows) |
| Leg A vs live OWS, non-hashed extras | 0.1141 [0.1067, 0.1219] (1,548 extra; 15,652 own rows vs 14,310 live; 1,056 cycles, 418 with equal row count) |
| Hashed, by key | 721 of 744 reproduced; rendering differences 356 + 46 + 14 |
| Leg D vs A | 5,801 of 5,801 identical over 352 cycles, 0 extras |
| Wall per block (median / max) | A 785 / 1435 s, B 785 / 1431 s, D 863 / 1385 s |
| **Residual pass (median / max, ms)** | **A 18,758 / 49,486 (n 1,025); B 18,877 / 49,530; D 20,366 / 49,950 (n 352)** |

The live-OWS comparison is descriptive only: these are not the anchor night, and the live rows came from other builds and settings (RS-V2 applies to the anchor night only).

## For your review

1. **The residual pass is slower than the 15 s cycle on this CPU even with the deadline removed** (median 18.8 s, max about 49.5 s). It supports the unfiled draft `2026-10-11-1925-qa-issue-draft-old-cpu-subtraction-budget.md`. Replay only; the live path is untested; sol is an FX-8350, not the station.
2. The 11.4 % extras are rows the unlimited replay finds that the live build did not report. I make no claim about whether they are real decodes.
3. I read the leg-D result as an equivalence check (same decoder), not as evidence about history effects.

## Files

- On this PC: `qa/rr-study/results/2026-10-12-refset-first-run-76aa48cd-LINUX-sol/` (`aggregate.json`, `status.json`, `pins.jsonl`; scanned for callsign shapes, none). Per-message working files stay on sol in `~/qa-scratch/refset-first` until job close, then are deleted (HK-037).
