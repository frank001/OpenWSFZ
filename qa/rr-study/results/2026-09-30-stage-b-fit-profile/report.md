# Stage B step 1: per-phase fit profile at 1, 4 and 14 concurrent workers (plus a supplementary 8 and 12)

| Field | Value |
|---|---|
| Run | 2026-09-30, 18:42Z to 18:58Z, quiet machine (WSJT-X closed, nothing else running; a browser open) |
| Tool | Developer's `feat/sub-feas-stage-b` @`ef7e765c` (`Ft8.FitProbe fitprofile`, test-only: nothing under `src/` or `native/` changed; shipped fits go through `Ft8LibInterop.SubfeasFitSignal` and the real pool sized by `ft8_subfeas_pool_configure(W)`; phases from a timed COPY of `subfeas_fit.c`) |
| Shipped `libft8.dll` | `ee00d118523ee2160750736225c67d8a056193908d168ed9a6ec3375ff990e4c` (unchanged); timed copy `273f3a4f…` (scratch, never shipped) |
| Signals | the pass-0 decodes of **5 real cycles** spread evenly over the 161 E1 cycles (`e1_selection.json` SHA `f58c0c7bd3ed34855f5db24277b941202813831b0f088a34944f5ba97c6879e2`), 4 fits per worker |
| Machine | Ryzen 7 7800X3D: **8 physical cores, 16 logical processors**; workers **not pinned** |
| Equivalence | `fitcompare`: **EQUIVALENT, 111 single-worker fits, rc and sha256(out_shat) identical** between the timed and shipped DLLs |

> **Bottom line.** **Step 1 (the time-offset search) is 71 % of a fit and steps 1 + 2 together are 96 %**; everything else is about 4 %. **The per-fit slowdown from
> concurrency is 1.09× at 4 workers and 1.85× at 14.** **Throughput stops improving past about 12 workers on this 8-core CPU** (14 is slightly worse than 12).
> Descriptive measurements; no decode-rate claim; no change to what ships.

## Main run (1, 4, 14 workers; milliseconds, medians; p95 and max in the tool output)

| Phase | W=1 | W=4 | W=14 | share of a W=1 fit |
|---|---:|---:|---:|---:|
| **whole fit (wall)** | **1 560.9** | **1 707.4** | **2 893.9** | |
| smoothed track | 10.2 | 13.0 | 19.6 | 0.7 % |
| **step 1 (Δt search, 201 candidates)** | **1 104.0** | 1 198.5 | 2 123.2 | **70.7 %** |
| **step 2 (ḟ search, 41 candidates)** | **390.1** | 419.4 | 645.5 | **25.0 %** |
| final template | 6.2 | 7.3 | 7.6 | 0.4 % |
| step 3 (Δt refine) | 30.0 | 31.9 | 40.4 | 1.9 % |
| envelope | 21.7 | 26.5 | 40.9 | 1.4 % |

Per-fit concurrency penalty (median wall at W over W=1): **W=4 1.09×, W=14 1.85×**; per phase at W=14: step 1 1.92×, step 2 1.65×, envelope 1.89×, step 3 1.34×.
Per cycle (5 cycles): the analytic call 10.9 ms; **one residual `DecodeAsync` decode 626 ms** (well inside the 1 500 ms reserve); pass-0 decode 795 ms in this harness (not the whole-call figure, see below).
Throughput (batch wall per fit): **W=1 1 509 ms, W=4 434 ms (3.5× the single worker), W=14 220 ms (6.9×)**.

## Supplementary run, stated as EXPLORATORY (8 and 12 workers were not in the registered 1/4/14; measured because the main run suggested it)

Same tool, same 5 cycles, workers 4, 8, 12, 14 (W=4 and W=14 repeat the main run within about 3 %: 1 759 vs 1 707 ms and 2 853 vs 2 894 ms).

| Workers | per-fit wall (ms) | penalty vs W=4 | throughput, ms per fit | speed-up over W=4 |
|---:|---:|---:|---:|---:|
| 4 | 1 759 | 1.00× | 449 | 1.00× |
| **8** | **1 904** | 1.08× | **242** | 1.86× |
| **12** | 2 282 | 1.30× | **198** | 2.27× |
| 14 | 2 853 | 1.62× | 209 | 2.15× |

**Throughput peaks at 12 workers and 14 is slightly worse; 8 workers gives about 82 % of the 12-worker throughput** at a per-fit wall of only 1.9 s. On an 8-core, 16-thread CPU, the extra workers beyond the physical cores mostly share cores and cache; the measured cause is **not separated** (8 cores with hyperthreading and about 28 MB of workspace per worker against a 96 MB L3 are both candidates).

**Prediction, not a measurement (waves × per-fit wall, for the fits alone; the decode and subtraction add about 1 s):**

| Signals in the cycle | W=14 | W=12 | W=8 |
|---|---:|---:|---:|
| ≤ 24 | 2 × 2.85 = 5.7 s | 2 × 2.28 = 4.6 s | 3 × 1.90 = 5.7 s |
| 25-28 | 2 × 2.85 = 5.7 s | 3 × 2.28 = 6.8 s | 4 × 1.90 = 7.6 s |
| 29-32 | 3 × 2.85 = 8.5 s | 3 × 2.28 = 6.8 s | 4 × 1.90 = 7.6 s |

The W=14 row matches what the acceptance run saw (about 5.5 s typical, 7.1-8.4 s at 29-31 signals). **Against the 11.0 s fit deadline, 8 and 12 workers both look viable up to 32 signals.**

🔴 **A correction to my own earlier advice.** I told the Captain and the Architect that halving the threads would "probably" abandon the heaviest cycles. That estimate was extrapolated from the 4-worker run (55.7 % abandoned, where 7 waves × 1.7 s exceeds the deadline). **This profile does not support it for 8 workers:** the predicted fit time at 8 workers is about 7.6 s for up to 32 signals, inside the deadline. It is still a prediction, made from isolated fits, not a run of the real pass at 8 workers.

## What it says for Stage B (the order the profile supports)

1. **Steps 1 and 2 are 96 % of a fit**, and both are the frequency search (201 + 41 searches, each an FFT of 262 144 points). Any item that does not touch them cannot matter much.
2. **B3 (coarse-to-fine Δt) attacks step 1 directly:** cutting its 201 candidates to about 50 would remove up to about three quarters of step 1, **an upper bound of about 53 % of the whole fit** (0.75 × 71 %). It is the simplest change with the largest single effect.
3. **B2 (pruned frequency search, about ±44 of 262 144 bins) attacks both steps 1 and 2 (96 %)** and, by replacing a 262 144-point FFT with a small one, would also shrink the per-worker working set, which is the plausible driver of the concurrency penalty. It is the larger potential win and the more complex change.
4. **B1 (faster FFT)** helps everything FFT-shaped but adds a third-party dependency and licence work; the profile does not **separate the FFT from the rest of a step**, so its share is unknown. A cheap follow-up would split FFT and non-FFT time inside steps 1 and 2.
5. **T′ arithmetic (rough, from this profile):** at 4 workers a fit is about 1.7 s; a 28-signal cycle is 7 waves, about 12 s against the 11.0 s fit deadline, so T′ needs roughly a 10-15 % cut in fit time at 4 workers. Either B2 or B3 alone should clear that by a wide margin. It is an estimate, not a measurement.
6. **A separate, cheaper lever appeared: the default thread count.** `ProcessorCount − 2` is 14 here, past the point where throughput stops improving. Whether the default should follow physical cores is a question for the Architect; it needs a run of the real pass at 8 and 12 workers first.

## Limits (HK-026)

5 cycles, 4 fits per worker, so the W=4 cell is 16 fits and the W=14 cell 56; unpinned workers; one machine; **the concurrency penalty is measured, its cause is not**; the pass-0 decode figure (795 ms) comes from this harness and is **not** the 492 ms whole-call median of the first-pass profile; **no decode-rate claim**. Integers and stamps only, no message text. Artefacts committed: this report, the two summary outputs.
