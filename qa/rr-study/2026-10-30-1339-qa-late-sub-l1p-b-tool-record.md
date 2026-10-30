# LATE-SUB L1′ build spec: B-TOOL (F5) record: Replay81 carries batch 5

**From:** QA · **Date:** 2026-10-30T13:38:39Z (`date -u`) · **Spec:** build spec `1322` §7 Amendment 1 (F5) · `qa/` code only, no `src/`/`native/` change.

## What changed (`qa/rr-study/sub-feas/replay81/`)

- **`Replay81.csproj`:** new define `HAS_LATEROUND` (`-p:HasLateRound=true`), for builds of the product that can deliver a batch 5. Needs `HasCohFb4`.
- **`Program.cs`, `DecodeThree`:** with the define, the staged callback accepts `n == 5` (before this, any batch number above 4 hit `throw "unexpected batch number"` and the cycle was logged as an exception: the instrument would have dropped the very batch it must measure). Batch 5 is counted in `decodes`, written to the outcomes file as `b5`, scored by test B as its own kind, and tagged `5` in `matchedbatch.csv` and in the `nc_dump` kind column.
- **`run.csv`:** two columns `b5_n,tb5_ms` appended **only with the define**. Without it the file is exactly as before.
- **`ScoreTestB`:** an optional `b5` parameter (own kind 5, rows `b5`); `b5 == null` leaves the output as it was.
- **Self-test (`--selftest-batch3 true`):** four new checks (batch 5 rows by band, never folded into b1-b4, matched-batch tag 5, no b5 row without a batch 5). ALL PASS in both builds.

## Regression (refset cycles 1-40, setting-less product, same arguments as the V7 run `reg40`)

| build | outcomes, testb, matched, matched-batch, abandon, nc_dump, impl_dump | run.csv content columns (`decodes`, `b1_n`..`b4_n`, `exception`) | third.csv, coh.csv excluding millisecond columns |
|---|---|---|---|
| **without** `HasLateRound` | byte-identical to `reg40` | equal; same 16 columns | equal |
| **with** `HasLateRound` | identical, except `testb.csv` gains 160 `b5` rows, all `0,0` | equal; 18 columns, `b5_n` = 0 and `tb5_ms` = -1.0 in all 40 cycles | equal |

So the older output is unchanged by the edit, and with the define the only additions are the empty batch-5 columns and rows.

## What this does NOT yet show

- No product exists that delivers a batch 5 (it arrives with the Developer's commit); the callback branch and the end-to-end columns are exercised first at the HK-039 review, and B-EQ-2 will exercise them for real. What is tested now is the scoring, the columns and the unchanged old output.
- The setter for `decoder.lateSubtractionRound` (the harness argument that turns the round ON/OFF) is added when the Developer's commit and its property name exist; it is a few lines under `#if HAS_LATEROUND`. The OFF-setting arm needs no setter (absent = OFF).
- The B-EQ-1/B-EQ-2 comparison scripts (hash-token-aware, per Amendment F3) are written against real batch-5 output, after the commit.

Build used for the regression: `_qa-scratch\late-sub\bin_f5` (without) and `bin_f5lr` (with), Replay81 against `main` `c2c85c45`, `libft8.dll` SHA-256 `1ba8dc3d…` (the pin, unchanged).
