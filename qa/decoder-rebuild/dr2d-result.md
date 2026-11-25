# DR-2 step 2d: the one Slice 40 replay of the lean engine (arm L1)

**Run:** 2026-11-25, started 17:47Z (`date -u`), wall 1,446 s. Runner `qa/decoder-rebuild/dr2d_run.py L1 170 --tag run` (commit `671d302b`), output `_qa-scratch\dr2d\run_L1_n170\` (gitignored; `nc.tsv` holds text, kept, HK-037).
**Build under test:** `feat/lean-2d` `6c746029` (HK-039 record `qa/rr-study/2026-11-25-qa-code-review-dr2d-lean-batches-xc-effort-6c746029-APPROVED.md`), `libft8.dll` SHA256 `7f0e36d2da93d299…` (the pin, re-hashed before and after the run), shim 20260076. Harness `Ft8.FitProbe.exe` = Replay81 built with `HasLean` over a clean checkout of that commit.
**Configuration:** `--engine lean --lean-threads 2 --effort normal`; every other flag as DR-0's A6 (`--cohaudio Both --ungated 1 --cohrescand 1 --cq-ap 1 --cohms 1 --nhard 24 --kmin 5 --osd-corr 0.05 --xc-prior 1 --xc-shadow 0 --xc-defaults 1`; the classic keys are accepted and ignored by the lean engine). Warm-up cycle `261115_072915`, then 170 cycles from `261115_072930`, as DR-0.
**Scoring:** the same code as DR-0 (`nc.tsv` matched against the 6,773 WSJT-X decodes of the window; `cpu_net` = process CPU / 170; `last_p95` = the 95th percentile of each cycle's latest batch time). Filter: none (a full harness run; 170 `lean:` rows parsed, 0 parse failures, 0 native error cycles).

## The four bars (targets, reported not gated; the Captain decides)

| Bar | Lean L1 | A6 baseline (DR-0) | Bar | Result |
|---|---|---|---|---|
| T1 `cpu_net` | **16.345 CPU-s per cycle** | 25.247 | ≤ 6.31 | **missed** (35 % less than A6, 2.6 times the bar) |
| T2 `rate` | **77.691 %** (5,262 of 6,773) | 84.39 % | ≥ 83.39 % | **missed** (6.70 pp below A6) |
| T3 `ours_only` | **3.248 %** (220 of 6,773) | 3.77 % | ≤ 4.27 % | **met** (0.52 pp below A6) |
| T4 `last_p95` and `abandoned` | **11,111 ms**, 4 cycles abandoned | 7,332 ms | ≤ 3,000 ms and 0 | **missed** (both) |

## Where the time goes (the `lean:` line, per cycle, means over 170)

| Stage | CPU-s per cycle |
|---|---|
| S3 total (rounds 1 to 3) | 14.36 |
| of which fits (`ft8_subfeas_fit_signal`) | **12.16** |
| of which decode (tier A, B, CQ-AP, unpack) | 2.19 |
| of which candidate search | 0.006 |
| of which sum and re-spectrogram | 0.01 |
| Round 0 (S1 and S2) and everything else | about 1.98 |

S3 wall 7.51 s per cycle. Cycles by rounds run: 1 round: 1, 2 rounds: 109, 3 rounds: 60. Results per cycle: median 30, maximum 42. The Architect's watch item is confirmed: **fitting is 74 % of the total CPU**; searching is nothing.

## What the other numbers say (aggregates only)

- Matched WSJT-X decodes by batch: batch 1: 4,023; batch 2 (rounds 1 to 3): 1,042; batch 3 (XC): 197. XC ran in 167 cycles (skipped, no residual: 3) and published 290 detections.
- **Ungated rows published: 0** in all 170 cycles. This is the 2c ruling at work: with `--cohrescand 1` (the baseline's setting) the lean accept rule drops every residual tier-B row that failed the F1b gate (QA review of `0c2db3b2`, "Ruling on the Developer's item 1"). The 2c ruling named this as the first lever if T2 missed.
- I cannot attribute the 6.70 pp T2 gap to that rule from this run alone: the run has no second arm, and A6's own ungated contribution is not in `dr0-result.md`. Other candidates are the lean engine's single candidate list in place of classic's separate residual, third-pass and late-round candidate sets, and the 4 abandoned cycles.

## Not claimed

- One run, one night, one band (40 m); no confidence interval was computed (the minimal-test rule).
- The CPU figure is the harness process CPU, as DR-0's was; the lean engine used 2 threads, A6 used `--threads 8`, which does not change CPU totals but does change wall time and so T4.
- The warm-up cycle ran through the classic path (the harness sets the engine after it); it primes the same process-global callsign table.
