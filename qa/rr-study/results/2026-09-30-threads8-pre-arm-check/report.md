# Pre-arm check: the real residual pass at subtractionMaxThreads = 8 on the 161 E1 cycles

| Field | Value |
|---|---|
| Run | 2026-09-30, 19:00:13Z to 19:19:11Z (harness), analysed 19:20Z |
| Build | `feat/sub-feas-two-stage-publish` @`247ac391`; `libft8.dll` `ee00d118523ee2160750736225c67d8a056193908d168ed9a6ec3375ff990e4c` = pinned |
| Path | production path: flag ON, `DecodeTwoStageAsync`, one call per cycle, `decoder.subtractionMaxThreads = 8` via `SetSubtractionMaxThreads` (harness mode `two1 --threads 8`) |
| Script / bar | `qa/rr-study/sub-feas/threads8_run.py`, commit `6620c201`, **bar committed before the run** (Architect, 2026-09-30): PASS iff 0 deadline abandons over the 161 cycles AND max whole call ≤ 13 000 ms (and 0 AV / contained exceptions / exceptions). Two analysis-only slips (a wrong dictionary key, twice) were fixed after the harness runs and before any result was read (`f53af028` and the commit after); the bar and thresholds were not touched |
| Cycles | the 161 E1 cycles (`e1_selection.json` SHA `f58c0c7bd3ed34855f5db24277b941202813831b0f088a34944f5ba97c6879e2`), three runs |
| Machine | Ryzen 7 7800X3D, 8 cores / 16 logical. **Not perfectly quiet:** WSJT-X and `jt9` were started at **19:07:41Z**, partway through run 2 (runs 2 and 3 overlapped them; CPU so far 43 s and 2 s, so low). Run 1 (ended 19:05:43Z) was quiet. See "Load" below |

> **Bottom line: PASS on the pre-registered bar.** 0 of 161 cycles abandoned; **max whole call 12 001 ms (bar 13 000)**; 0 AV, 0 contained exceptions.
> **The margin at the tail is thin:** 5 of 161 cycles (3 %) took more than 11 s, all with 27-30 signals, and the slowest residual pass (11 404 ms) ended within
> about 0.4 s of the point at which the fits would have been cut off. **Not a decode-rate claim.**

## Result (161 cycles, 8 workers)

| Quantity | p50 | p95 | max |
|---|---:|---:|---:|
| whole call (ms) | 6 729.7 | 9 246.1 | **12 001.1** |
| time to batch 1 (ms) | 520.3 | 684.5 | 798.8 |
| residual pass `elapsedMs` | 6 203 | 8 805 | 11 404 |

- Deadline abandons **0**; contained exceptions 0; AV 0; CSV rows with an exception 0; log lines equal cycles.
- **Sanity check passed:** the residual-decode total is **795, equal to the Stage A baseline** (14 workers). The fits are bit-identical to Stage A at any thread count, so with no abandons the decodes must be identical; they are.
- Most signals fitted in any cycle: 30.

## Against 14 workers, same cycles (descriptive; 14-worker numbers from the E3 baseline run)

| Run | 8 workers: p50 / p95 / max (ms) | 14 workers: p50 / p95 / max (ms) |
|---|---|---|
| 20260922_2056 (49 cycles) | 6 587 / 8 340 / 9 392 | 5 591 / 6 071 / 6 473 |
| 20260923_1730 (77) | 6 906 / 11 635 / **12 001** | 6 100 / 8 620 / 10 010 |
| 20260925_2010 (35) | 6 611 / 8 038 / 8 147 | 5 163 / 5 683 / 5 848 |

Eight workers is about 1 s slower at the median and about 2 s slower in the tail than 14, on this CPU.

## The tail (what the bar does not show)

Pass time by number of signals fitted (8 workers): 16-17 signals about 4-5 s; 18-25 about 5.4-6.7 s; 26 about 7.7 s; **27-28 about 8.8-9.0 s (max 11.0 s); 29-30 about 11.0-11.4 s.**
The five cycles over 11 s in whole-call time: two at 12.0 s (30 signals) and three at 11.4-11.6 s (27, 27 and 29 signals). All five are in run 2.

- **The prediction was optimistic.** The Stage B profile predicted about 7.6 s for up to 32 signals at 8 workers (waves × per-fit wall). The real pass takes **9-11.4 s** for 27-30 signals, about 2-4 s longer. The wave model misses something. A plausible but **unverified** cause is uneven work distribution: `Parallel.For` hands out iterations dynamically, and with only about 4 long iterations per worker one worker can end up with a fifth. A per-fit completion log would settle it.
- **It is not WSJT-X.** By position in the run, the two 12.0 s cycles started before WSJT-X did (about 19:06:32Z and 19:07:27Z, against a WSJT-X start at 19:07:41Z); the other three (11.4-11.6 s) started after it. Position is approximate (reconstructed from durations).
- **Margin to the abandon point.** The fits are cut off at about 11.0 s of the pass; a pass that ends with less than 1.5 s left does not run its residual decode. A residual pass of 11.4 s with its decode still completed means its fits ended about 10.8 s in, **within 0.2-0.4 s of the cutoff**. Live load (WSJT-X decoding, a browser, the operator) on the 27-30 signal cycles could push some of them over: those cycles would be abandoned and lose their extras. They were 11 of 161 (7 %) of these busy E1 cycles.

## Limits (HK-026)

161 cycles, three runs, one machine, flag ON only; busy cycles only; WSJT-X started during runs 2 and 3; a **pass on the pre-registered bar is not a claim that 8 workers is safe under live load**; no cycle above 30 signals was tested at 8 workers (the corpus has up to 31 at most). No decode-rate claim. Integers and stamps only. Artefacts committed: this report, `rows.json`, `preflight.json`.

## Decision inputs (Architect and Captain)

- The registered bar is met, so **8 workers is not refused on this evidence.**
- The tail is thinner than predicted, so **12 workers may be the better compromise**: the profile's throughput peak, four logical processors left free, and (predicted, not measured) about 3 waves for up to 36 signals. The same check would take about 20 minutes on the quiet machine.
- A cheaper lever may exist independent of the thread count: the work distribution in `SubtractionPass` (see above). It is a `src/` change and needs a Developer session and the Architect's scoping.
