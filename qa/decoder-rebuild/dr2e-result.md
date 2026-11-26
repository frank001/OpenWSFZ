# DR-2 step 2e: the replay of the cheaper lean engine (arm L1, Slice 40)

**Run:** 2026-11-25, started 19:37Z (`date -u`), wall 882 s. Runner `qa/decoder-rebuild/dr2d_run.py L1 170 --tag run --bin <bin_lean2> --pin bb930897…`; output `_qa-scratch\dr2e\run_L1_n170\` (gitignored; `nc.tsv` holds text, kept, HK-037).
**Build under test:** `feat/lean-2e` `57bda0eb` (HK-039 record `qa/rr-study/2026-11-25-qa-code-review-dr2e-fit-cost-ungated-57bda0eb-APPROVED.md`), `libft8.dll` SHA256 `bb930897849ee1f4…` (the pin, equal to the Developer's, re-hashed before and after), shim 20260077. Harness `Ft8.FitProbe.exe` = Replay81 with `HasLean` over a clean checkout of that commit.
**Configuration:** exactly as `dr2d-result.md` (lean, `--lean-threads 2`, effort normal, A6's other flags; same 170 cycles from `261115_072930`, warm-up `261115_072915`). Filter: none; 170 `lean:` rows parsed, 0 parse failures, 0 native error cycles.
**What changed since the first replay (`6c746029`):** the fit is 1.5 times cheaper and bit-identical (D2), a fit-skip rule is on (D3), ungated residual rows are admitted (D4). **All three changed together, so this run cannot say which of them moved which number.**

## The four bars (targets, reported not gated; the Captain decides)

| Bar | Lean 2e | Lean 2d (first replay) | A6 baseline (DR-0) | Bar | Result |
|---|---|---|---|---|---|
| T1 `cpu_net` | **9.896 CPU-s per cycle** | 16.345 | 25.247 | ≤ 6.31 | **missed** (61 % less than A6; 1.57 times the bar) |
| T2 `rate` | **81.515 %** (5,521 of 6,773) | 77.691 % | 84.39 % | ≥ 83.39 % | **missed** by 1.88 pp (2.88 pp below A6) |
| T3 `ours_only` | **3.824 %** (259 of 6,773) | 3.248 % | 3.77 % | ≤ 4.27 % | **met** (0.05 pp above A6, 0.45 pp inside the bar) |
| T4 `last_p95` and `abandoned` | **7,597 ms**, **0** abandoned | 11,111 ms, 4 | 7,332 ms | ≤ 3,000 ms and 0 | p95 **missed**, abandoned **met** |

## Where the time goes (the `lean:` line, per cycle, means over 170)

| Stage | 2d | 2e |
|---|---|---|
| S3 total CPU-s | 14.36 | **8.12** |
| of which fits | 12.16 | **6.31** |
| of which decode (tier A, B, CQ-AP, unpack) | 2.19 | 1.80 |
| Round 0 and everything else | 1.98 | 1.78 |
| S3 wall, seconds | 7.51 | **4.29** |

Fits are still 64 % of the total CPU. Cycles by rounds run: 2 rounds: 73, 3 rounds: 97 (in the first replay 109 and 60: more cycles now run the third round; the cause was not checked, a cheaper loop and the recovered 4 abandoned cycles are the obvious candidates). Results per cycle: median 32, maximum 46.

## What the other numbers say (aggregates only)

- **Fit-skip rule (D3) fired:** 705 fits skipped in 170 cycles (4.1 per cycle). The Developer expected close to zero on real audio; it is not zero. This run does not say what those skips cost in decodes.
- **Ungated rows (D4):** 119 published (was 0). Matched by batch: batch 1: 4,025; batch 2 (rounds 1 to 3): 1,353 (was 1,042); batch 3 (XC): 143 (was 197). XC ran in all 170 cycles (was 167; skipped for no residual: 0) and published 243 detections (was 290).
- **Abandoned cycles: 0** (was 4): the cheaper fits keep the loop inside the budget.
- **The decode-rate gain (+3.82 pp) cannot be split** between D4's 119 ungated rows, the 4 recovered cycles, and the effect of D3's skips (which can only have cost decodes). The false side rose 0.58 pp with it (3.248 % to 3.824 %), inside the bar.

## What the wall time means for T4

The 7.6 s p95 is the latest batch's time at **2 worker threads** (`decoder.threads` default 2, spec §2.4); the S3 wall is 4.29 s per cycle. CPU does not change with the thread count, wall does. The harness machine has 16 logical processors and A6 ran at 8 threads. This run did not measure a higher thread count (one replay only), so how much of the 7.6 s a larger default would remove is **not measured**.

## Addendum: the same build at 8 worker threads (arm L3, the Captain's option 2)

**Run:** 2026-11-25, started 19:55Z (`date -u`), wall 351 s; the same binary (`bb930897…`, pin re-hashed), the same 170 cycles and flags, `--lean-threads 8` (A6 ran at 8). Output `_qa-scratch\dr2e\run_L3_n170\`.

| | L1: 2 threads | L3: 8 threads | A6 | Bar |
|---|---|---|---|---|
| T1 `cpu_net` | 9.896 | **12.238** | 25.247 | ≤ 6.31 |
| T2 `rate` | 81.515 % | 81.515 % | 84.39 % | ≥ 83.39 % |
| T3 `ours_only` | 3.824 % | 3.824 % | 3.77 % | ≤ 4.27 % |
| T4 `last_p95` | 7,597 ms | **2,706 ms** | 7,332 ms | ≤ 3,000 ms |
| T4 abandoned cycles | 0 | 0 | | 0 |
| last batch, median / maximum | 5,015 / 8,616 ms | 1,976 / 3,051 ms | | |
| S3 wall per cycle | 4.29 s | 1.71 s | | |

- **The decodes are identical** at 2 and 8 threads (5,521 matched of 6,773 and 259 false-side in both; the same 119 ungated rows, 705 skipped fits, rounds per cycle and matched-by-batch counts 4,025 / 1,353 / 143), as the determinism tests promise.
- **T4 is met at 8 threads** (p95 2,706 ms against 3,000 ms, 0 abandoned); the maximum, 3,051 ms, is just over the bar.
- **CPU rose by 2.34 CPU-s per cycle** (9.896 to 12.238): the fit CPU went from 6.31 to 7.77 and the S3 total from 8.12 to 10.02. T1 is therefore worse at 8 threads (1.94 times the bar) and better at 2 (1.57 times). The cause was not examined (see the 4-thread run below, which weakens the first guess).

### 4 threads (arm L4, run 2026-11-25 at 20:11Z (`date -u`), wall 536 s) and the three together

The machine is an 8-core, 16-logical-processor desktop (SMT; `Win32_Processor` reads `NumberOfCores` 8, `NumberOfLogicalProcessors` 16). The same build, cycles and flags; the decodes are identical in all three runs.

| Threads | `cpu_net` (CPU-s per cycle) | fit CPU | S3 wall | `last_p95` | `last` median / maximum |
|---|---|---|---|---|---|
| 2 | 9.896 | 6.31 | 4.29 s | 7,597 ms | 5,015 / 8,616 ms |
| **4** | **10.888** | 6.94 | 2.63 s | **4,374 ms** | 3,073 / 5,222 ms |
| 8 | 12.238 | 7.77 | 1.71 s | 2,706 ms | 1,976 / 3,051 ms |

- **T4 (3,000 ms) is missed at 4 threads (4,374 ms) and met at 8 (2,706 ms)**; T1 (6.31) is missed at all three, by 1.57, 1.73 and 1.94 times.
- **CPU grows steadily with the thread count** (+10 % from 2 to 4, +12 % from 4 to 8; the fit CPU too). The first explanation, two workers sharing one core under SMT, is **not** supported cleanly: 4 workers on 8 cores should mostly not share a core, yet CPU already rose 10 %. Cache or memory contention, clock behaviour and the scheduler's placement are equally possible; none was examined.
- 16 threads cannot be measured on this build: the lean engine clamps workers to 8 (`ftz_decoder.h:33`, `ftz_decoder.c:673`, `DecoderConfig.cs:106`). The thread-cap raise is part of the operator-threads task (D7).

### 16 threads (arm L5, run 2026-11-26, wall 272 s)

Build `feat/threads-setting` `fc4fb788` (cap raised to 16, shim 20260078), harness built from it with `-p:HasLean=true` in `_qa-scratch\dr2d-replay\tree3` / `bin_lean3`; `libft8.dll` SHA256 `eab11ec9a456169b96bde734ef319e8b74555acea4c09f9096661f6082190ea2` = the pin = the tracked `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` of `fc4fb788` (actual = pinned, asserted by the runner). Command: `dr2d_run.py L5 170 --tag threads16 --bin ...\bin_lean3 --pin eab11ec9...`; same 170 cycles and flags as L1; no `--filter` (not a test run). Output `_qa-scratch\dr2e\threads16_L5_n170`.

| Threads | `cpu_net` (CPU-s per cycle) | fit CPU | `last_p95` | wall (170 cycles) | matched / ours |
|---|---|---|---|---|---|
| 2 | 9.896 | 6.31 | 7,597 ms | 882 s | 5,521 / 5,780 |
| 4 | 10.888 | 6.94 | 4,374 ms | 536 s | 5,521 / 5,780 |
| 8 | 12.238 | 7.77 | 2,706 ms | 351 s | 5,521 / 5,780 |
| **16** | **13.405** | **8.55** | **2,053 ms** | **272 s** | **5,521 / 5,780** |

- **Decodes identical** to the 2, 4 and 8 thread runs (5,521 matched, 5,780 ours, `rate` 81.515 %, `ours_only` 3.824 %, 705 skipped fits, 0 lean errors, 0 abandoned).
- **`last_p95` 2,053 ms** (T4 met with more margin than at 8: 2,706). **CPU +9.5 % over 8 threads** (+35 % over 2); T1 (6.31) missed by 2.12 times. Each doubling cost +10 %, +12 %, +9.5 %.
- The machine has 8 physical cores and 16 logical processors, so 16 workers fill every logical processor: this is the proposed auto default on this PC. Memory at 16 workers was not measured in this run.

## Not claimed

- One run, one night, one band (40 m); no confidence interval was computed (the minimal-test rule).
- The CPU figure is the harness process CPU, as DR-0's was.
- The warm-up cycle runs through the classic path (the harness sets the engine after it); it primes the same callsign table.
