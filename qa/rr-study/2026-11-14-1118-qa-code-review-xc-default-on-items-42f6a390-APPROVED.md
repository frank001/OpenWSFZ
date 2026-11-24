# HK-039 code review: XC-BUILD default-ON items (D1 QSO queue 14, D2 PSK Reporter excludes template rows) at `42f6a390`. APPROVED, with three small tests requested and one finding for the Architect and the Captain

Reviewed-commit: 42f6a3909d79388b1dca100dbe905a5eed18704c
Verdict: APPROVED

**Written:** 2026-11-14, `date -u` read 11:17:32Z. **Reviewer:** QA. **Parent:** `a88dd402` (the accepted remedy build `4b70e418` plus its tests-only edge test). **Spec:** the Architect's acceptance ruling §3 (`arch/cross-cycle-prior` `3da7b187`); dev task `dev-tasks/2026-11-14-xc-default-on-items.md`. **Developer's report:** read (§1 and §5 answered, no deviations); the claims I rely on were re-checked below.

## 1. Verdict

**APPROVED.** The code does what the task says and the Architect ruled; the scope fence holds; the full unfiltered suite is green on a clean tree; the queue capacity and the filter decision are fully pinned by tests (14 of 17 mutants killed by tests, 1 stopped by the compiler's analyzer). Three observability details are not pinned (section 4); they are small, do not change the filter or the capacity, and are requested as a tests-only follow-up **before the PR**, so that `pre_merge_check` runs once on the final commit. One finding about default-ON (section 5) is for the Architect and the Captain, not a defect of this commit.

## 2. What I read (every changed file under `src/`)

`LateBatch.cs` (`BatchesPerCycleFallbackOn` 4 to 6, so `QsoChannelCapacityFallbackOn` = 6 x 2 + 2 = 14; OFF stays 8; the capacity is selected by the coherent-fallback flag, and the template stage requires that flag, so the two cannot disagree), `PskReporterEngine.cs` (`if (r.Path == DecodeResult.PathTemplate) { _exTemplate++; _window.Template++; continue; }` placed after the AP rule and before the region rule; counters carried into the window, the combined status window, the window log line and the datagram line; reset paths), `DecodeResult.cs` (`PathTemplate = 3` in Abstractions, so the daemon needs no decoder internal), `IPskReporterStatusSource.cs` (`Template` added with default 0, an additive status-API key), comments in `DecodePump.cs` and `Program.cs`. Its answer to my question 1 checks out: `DecodePump` routes every batch other than 1 to `PublishSecondAsync` and writes the same batch to both QSO channels and the PSK queue, so all six batches count.

## 3. Checks

| check | result |
|---|---|
| **Scope fence** (`git diff --stat a88dd402 HEAD -- native src/OpenWSFZ.Ft8`) | **0 lines**: the decoder is untouched, so no replay arm is repeated; the native library pin `bbde6eb66af4cd429ffc46f67291ba718c1ae36ae39665faac24629bcb6e6528` holds |
| **Full unfiltered suite** (QA, clean detached tree, `dotnet test OpenWSFZ.slnx -c Release`) | **0 failures in every project**: TraceabilityCheck 34, LicenseInventoryCheck 24, Rig 41, TestSupport 12, Config 204, Audio 40, E2E 9, **Web 447**, **Daemon 940**, **Ft8 821** (the Developer's counts exactly; this also covers the Web fix their whole-solution run predated) |
| **Mutation** (`xc_mutate3.py`, 17 mutants on D1 and D2; Daemon tests for the touched area; list in `qa/xc-build/xc-build-42f6a390-mutants.json`) | **13 killed by tests** (capacity 5, 7 and no-spare; flag ON and OFF capacity mix-ups; filter inverted; counted but still uploaded; datagram and window counts; constant 3 to 4; status window; combined window; swapped datagram fields), **1 stopped by the compiler** (D16, a logging-placeholder mismatch is error CA2017), **3 survive** (section 4) |
| Test quality | the queue tests fill 12 then 14 and show the OLDEST four dropped; the mixed-batch test uploads only the ordinary rows and asserts `template=1` on both lines and in the status; no sleeps or clock reads |

## 4. The three survivors (small; tests only; requested before the PR)

1. **D14, the datagram line's template count is never reset.** If `_exTemplate` is not zeroed after a datagram, the next datagram's `template=` is cumulative. No test sends two datagrams with a template row in the first. **Request:** a test with a template row in the first datagram and none in the second, expecting `template=0` on the second line.
2. **D15, the count is not zeroed on engine reset.** **Request:** a reset test (template counted, reset, line shows `template=0`).
3. **D18, the default of `PskReporterWindowCounts.Template` is not pinned.** `WebApp.cs:1057` builds the "no service" status as `new PskReporterWindowCounts(0, 0, 0, 0, 0, 0, 0, 0)`, relying on the default 0: a default of 1 would show `template: 1` there. **Request:** one assertion that the status with no PSK service reports `template` 0 (and `ap` 0).

These change no product code. Land them as a tests-only commit on top of `42f6a390`; I will re-run the three mutants on it and review the delta in a few minutes, then run `pre_merge_check` once on the final commit.

## 5. A finding for the default-ON decision (not about this commit; the Architect ruled that the QSO services get batch 6)

`ProcessLateBatchAsync` treats a supplementary batch as **heard**, and `HandleLateIdleAsync` (`QsoAnswererService.cs`, around line 1330) **auto-answers a CQ found in a supplementary batch** when auto-answer is on, the station has a callsign and grid and the filters allow it. With batch 6 delivered to the QSO services, **a CQ that only the template stage "found" can start an on-air TX answer.** A true repeat of a CQ is harmless (the station called CQ again). A stale template of a station that has since stopped calling CQ is not: XC-SUP measured 6 and 7 such stale publishes per 1,000 cycles after the remedy (against 641 before it), and that count is a lower bound (stale templates where WSJT-X decoded nothing are invisible to it). The late handlers for WaitReport and WaitRr73 also act on batch-6 rows. **QA's recommendation (the Architect's and the Captain's to decide before the station is switched on):** the QSO services ignore batch 6 for state transitions and for starting an answer (display, `ALL.TXT` and GridTracker keep it), or at least for the Idle auto-answer; a small change in `src/OpenWSFZ.Daemon`, with a test, on its own task. The default is OFF, so nothing on air changes until the Captain's separate go.

## 6. Not established

macOS and Linux CI have not run this commit (not pushed). `pre_merge_check` has not run (it follows the tests-only commit, on the exact final hash, HK-006). The Developer's whole-solution run and mine agree; nothing else was re-run.
