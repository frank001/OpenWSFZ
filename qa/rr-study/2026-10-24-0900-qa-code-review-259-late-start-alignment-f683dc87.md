# QA code review (HK-039): #259 late-start time alignment, Developer commit f683dc87

Reviewer: QA. Written 2026-10-24 (`date -u` 08:47Z at the start of the resumed review).
Branch `fix/late-start-time-align`, VERSION 0.62, local, not pushed.
Change artefacts read first: OpenSpec change `late-start-time-alignment` (`qa/refset` `f8056031`), Architect spec Amendment 1 (A1.2 clamp logs the samples it cuts; A1.4 raised-cosine ramp, 240 samples).

Reviewed-commit: f683dc8727c9d697e9b800e89f0906f3ce52c63e

Verdict: APPROVED (code and tests), subject to `pre_merge_check.py` passing on the exact tip; its result is appended below. No required changes.

## What QA verified (clean detached tree `D:\Projects\claude\_qa-scratch\259-review\tree`, exactly `f683dc87`)

1. **Source against the spec.** Helper arithmetic exact: whole-clip edge 2.36 s, cut-off 11.25 s, half-up rounding, the skip works on a copy, ramp `0.5 x (1 - cos(pi x i / 239))` over 240 samples. Both services read `_timeProvider` once for the skip and the clamp. The three fire sites retain at >= 11.25 s. Information log lines carry no message text (a test asserts this).
2. **Helper tests:** 11 of 11 pass.
3. **Mutation 1** (skip forced to 0, tail truncation restored): T2, T3, T4 and the boundary test FAIL; T1 passes (it is the unchanged full-clip case, as it should).
4. **Mutation 2** (fade-in a no-op): T2, T3, T4 FAIL.
5. **Wall-clock experiment** (both services defaulted to a clock FIXED at 12 s into a slot): Daemon project 809 of 810; the single failure is `S3(g)`, which waits for the real wall clock to be 1 to 9 s into the cycle, so it is not exposed in practice. At 0.5 s into the slot: 810 of 810. The Developer's fixed-clock defaults are therefore the exposed ones and are right.
6. **Test-churn hunks, read in full today** (`QsoCallerServiceTests.cs`, `QsoAnswererServiceTests.cs`):
   - Every service constructed without a clock now gets a `FakeTimeProvider` fixed at the START of a slot, matching the standing rule (no real-clock dependence; about one run in four would otherwise land in the last 3.75 s).
   - Expected lengths are recomputed correctly and checked by hand: caller 9 s in: skip round((9-0.5) x 48 000) = 408 000, load 606 720 - 408 000 = 198 720; answerer 8 s in: skip 360 000, load 246 720; 4.9 s in: skip 211 200, load 395 520; log "skipping 4400 ms, loading 8240 ms" (12.64 - 4.4 = 8.24).
   - The two "zero remaining time" tests were rewritten to the new rule (not keyed at >= 11.25 s, responder/target retained and still armed) rather than weakened; they wait on a positive condition (`ObservedDecodeChannel.IsProcessedThroughLastDequeue`, `WaitForBatchDrainedAsync`), not a delay.
   - New tests T3/T7 (content equality of the loaded buffer from sample 241 on, first sample 0), T5 (not keyed, one Information line, no PTT), T6 (retained, then fires in the next correct-phase window; responder, target and jump-in).
   - No fixed delays, no no-op delay seams, no platform-dependent numerics.

## Notes (not required changes)

- N1. A start at or after 11.25 s still advances the state machine to `WaitReport` and counts toward retry accounting (the tests state this). That is the pre-#259 behaviour for the zero-remaining skip and the spec accepted it; flagged so the live L-1/L-2 observer knows the retry budget is consumed by an un-keyed answer.
- N2. In the T5 answerer theory the decode batch carries `DateTimeOffset.UtcNow` rather than a slot-relative time. It is harmless (phase comes from the CQ's own slot via `Make`), but a fixed value would be tidier.
- N3. Any future test that arms a pending target, jump-in or responder with the real clock has a one-in-four exposure. To be told to the Architect.

## Not done by QA

The full unfiltered suite was not run by QA outside `pre_merge_check.py`; the Developer reports 2122/0/0, Daemon 810, G9a/G9b OK, `native/` diff empty.

## pre_merge_check.py (result)

Run from a clean detached checkout of exactly `f683dc87` (`D:\Projects\claude\_qa-scratch9-review	ree`, log `...9-review\pmc259.log`): **READY, every gate passed.** Native freshness (Windows, Linux, macOS all 20260069), G9a, G9b, solution build, UDP margin lint, G10, full Release suite (Windows: Daemon 810, Ft8 580, Web 402, Config 170, Rig 41, Audio 40, Traceability 34, License 24, TestSupport 12, E2E 9; 0 failed), G3, WSL Debian compile and test (Linux: Daemon 778, Ft8 580; Windows-only tests excluded there; 0 failed), G8, self-contained publish, AOT publish.

Next: the Captain's push go (HK-033), then the `sol` offline grid and live L-1/L-2.
