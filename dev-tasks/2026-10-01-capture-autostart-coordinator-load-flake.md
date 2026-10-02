# Developer handoff: two `CaptureAutoStartCoordinatorTests` scenarios fail intermittently under CPU load

**Date:** 2026-10-01. **From:** QA. **To:** Developer. **Priority:** medium. It can turn a mechanical gate red at random, as D-015 did, but nothing in SUB-FEAS touches this code.

## 1. Context

While fixing D-015 (`fix/qso-caller-d015-flake`, merged by QA into the local SUB-FEAS merge branch) you reported a **second, separate flake** in `tests/OpenWSFZ.Daemon.Tests/CaptureAutoStartCoordinatorTests.cs`, seen only under load (WSL Debian, Release, unfiltered `OpenWSFZ.Daemon.Tests`, 32 busy loops):

| Run set | Failures |
|---|---|
| `origin/main`, load | 1 of 10 runs |
| D-015-fixed build, load | 2 of 10 runs |
| any run without load | 0 |

The two tests (both named for the scenario in their `DisplayName`):
- `RunAsync_Ambiguous_NoStartNoSave_RecordsDeviceUnavailable`, line 173 ("Ambiguous name is never guessed")
- `RunAsync_NotFound_RecordsDeviceUnavailable`, line 198 ("Disabled-only match is not adopted")

Both build the coordinator with `delayAsync: (_, _) => Task.CompletedTask` and then, after `await sut.RunAsync(applyBackoffDelay: false)`, assert **`recovery.ConsecutiveCaptureFailures.Should().Be(1)`** and `LastCaptureError`.

**QA's hypothesis, not verified:** the coordinator **self-reschedules** a retry after a NotFound/Ambiguous outcome (design D4; the test comment says "avoid the self-rescheduled retry's real delay"). With the delay replaced by an already-completed task, that retry is a free-running background loop. If it runs one more iteration before the assertion, `ConsecutiveCaptureFailures` is 2, not 1 (and `LastCaptureError` may have been overwritten). That is a race the test itself creates, and CPU load changes who wins it. The sibling test at line 214 (FR-071 self-reschedule) avoids it by polling, which is the right pattern.

## 2. Branch

Cut **`fix/capture-autostart-coordinator-test-flake`** from **`origin/main`**. Test-only unless the mechanism turns out to be in product code, in which case stop and tell QA (HK-011).

## 3. Actions

1. **Capture the exact failure first.** Reproduce it in WSL Debian under load (the same 32 busy loops, whole `OpenWSFZ.Daemon.Tests` project, Release, unfiltered). Record the **exact assertion message** (which `Should()` failed and the actual value) for both tests. Your report to QA must quote it; this handoff does not know it. If you cannot reproduce it in 30 runs, say so and report the rate you saw.
2. **Establish the mechanism** from the assertion and the code (`CaptureAutoStartCoordinator.RunAsync`, its self-reschedule). Confirm or refute the hypothesis above; if refuted, say what it is.
3. **Fix the cause in the test.** If the background retry races the assertion, make the test deterministic without a bare delay: for example give the test coordinator a `delayAsync` that **parks** (a `TaskCompletionSource` the test never completes, or completes at the end) so no retry runs during the assertions, or poll for the state the test asserts. Do **not** add a `Task.Delay` or `Thread.Sleep` (Gate G10). Keep what the tests prove: no start, no save, one recorded failed attempt, `DeviceUnavailable`, the error text.
4. List any other test in this file with the same shape (a no-op `delayAsync` followed by an exact-count assertion on state the background loop also changes). Fix them in this branch only if the same change applies without extra risk; otherwise just list them.

## 4. Acceptance criteria (what QA checks)

1. Your report quotes the exact failing assertion for each test and states the mechanism with evidence.
2. After the fix: **0 failures in at least 30 unfiltered runs** of the whole `OpenWSFZ.Daemon.Tests` project in WSL Debian Release under the same load, and the same number of runs without load. State the failure rate before and after.
3. Both tests still assert everything they assert today (nothing weakened or removed); no new bare delay; `python tools/check_test_delay_sync.py` OK.
4. Unfiltered pass counts for **Windows** and **WSL Debian** `OpenWSFZ.Daemon.Tests` quoted (a filtered-out run is not a result, HK-022).
5. `git diff --stat -- src/ native/` is empty, or contains only a change QA approved in advance.

## 5. References

- `tests/OpenWSFZ.Daemon.Tests/CaptureAutoStartCoordinatorTests.cs` (lines 173, 198, and the self-reschedule test around 214); `src/OpenWSFZ.Daemon/CaptureAutoStartCoordinator.cs`.
- OpenSpec change `capture-device-reresolution` (#187), design D4 (the self-rescheduling retry loop).
- Gate G10: `tools/check_test_delay_sync.py`, `test-delay-debt.md`. The D-015 fix (`ada7b488`) for the pattern "poll the positive condition".
