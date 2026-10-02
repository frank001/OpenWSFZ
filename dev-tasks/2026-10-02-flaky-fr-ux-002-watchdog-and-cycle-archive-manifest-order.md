# Developer handoff: two recurring flakes, `FR-UX-002` watchdog expiry and `cycle-audio-archive` manifest order

**Date:** 2026-10-02. **From:** QA. **To:** Developer. **Priority:** high: TESTING_STRATEGY.md section 11 item 3 makes a repeat flake on the same test a **blocker** until it is fixed. **Scope:** `tests/` only (a `src/` change needs QA's say first, HK-011). **Only QA pushes.** The Captain lifted his hold on both on 2026-10-02. One fix commit per test, on one branch, tests only, **no mute, no skip, no retry** (section 11 item 2).

Issues: see the numbers QA gives in its message (filed 2026-10-02 per section 11 item 1; label `flake`).

## 1. FR-UX-002: watchdog expiry publishes Idle with "Watchdog timeout"

`tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs:2041`, `SafeAbortToIdleAsync_WatchdogTimeout_EmitsAbortReason`.

**Observed (two CI failures on 2026-10-02, identical message and line):**
- 07:29Z, `windows-latest`, push of `qa/onoff-replay` (run 36978495739), passed on rerun.
- 09:27Z, `macos-latest`, push to `main` (run 36989525079), passed on rerun.

```
System.TimeoutException : Expected value to be WaitReport but was Idle after 3.0s.
  at Poll.UntilAsync ... Poll.cs:line 77
  at QsoAnswererServiceTests.SafeAbortToIdleAsync_WatchdogTimeout_EmitsAbortReason() ... QsoAnswererServiceTests.cs:line 2060
```

Line 2060 is the first poll, `WaitForEqualAsync(() => sut.State, QsoState.WaitReport, 3 s)`. Both times the failure took 3 s, and the state it last read was already **Idle**.

**QA's hypothesis (unverified, HK-022; confirm or refute it):** the test builds the service with a **300 ms watchdog** and then waits for the **transient** state `WaitReport`. The watchdog is armed when the QSO engages, so `WaitReport` can last only about 300 ms before the watchdog drives the service to Idle. If the test thread, the poll interval or the runner's scheduling is delayed past that window, the poll never sees `WaitReport` and then reads Idle for the rest of its 3 s. The test waits for a state whose lifetime it has itself set shorter than a loaded CI runner's scheduling jitter. It passes on an idle machine and fails under load, which matches two failures in two platforms and 100% passes elsewhere.

**Required behaviour:** the test must not depend on observing a state that lasts less than scheduling jitter. Do not just lengthen 300 ms to a larger sleep. Make the intermediate state **observable deterministically**: for example inject a controllable clock or watchdog (the answerer's `watchdogDuration` seam already exists in `BuildIsolatedSut`), so the test arms the watchdog, observes `WaitReport` with the watchdog held, and only then lets it expire; or observe the transitions through the event bus instead of polling a transient property. State which you chose and why. The assertion at the end (an `Idle` publish with "Watchdog timeout") stays exactly as it is.

## 2. cycle-audio-archive: manifest row is written per archived cycle, in order

`tests/OpenWSFZ.Daemon.Tests/CycleArchiveServiceTests.cs:201`, `Manifest_WritesOneRowPerArchivedCycle_InOrder`.

**Observed:** on 2026-10-02 at about 11:5x local, inside QA's `tools/pre_merge_check.py` full-suite run on Windows (branch `qa/e2e-isolation-pr`, a tests-only change that touches nothing near this service), the test **timed out after 15 s** (its own widened poll for 5 manifest lines). It passed on the rerun and passed in every other full run that day. **QA deleted the log of that run before capturing the exception text, so QA cannot give the message; the Developer must reproduce it.** A **second flake on this file the same day** was reported by the Developer: the "dropped cycles appear as an explicit gap marker" test (`Manifest_RecordsGapMarker_AfterDroppedCycles`), which already has a closed flake issue (#177, 2026-09-14) and was seen again on Windows (passed on reruns).

**History (read it first, do not repeat it):** `dev-tasks/2026-08-30-flaky-cyclearchiveservicetests-manifestgapmarker-file-lock.md`, `2026-09-14-cyclearchiveservicetests-poll-swallows-no-exceptions.md`, `2026-09-14-cyclearchiveservicetests-manifestgapmarker-ioexception-repeat-flake.md`, and commit `233fb6ec` (widened the polls to 15 s: it treated the symptom). Three earlier fixes have each addressed one exception shape, and the class keeps returning: a test polling a **file that a background writer loop is writing**, under the full-suite's parallel load.

**QA's hypothesis (unverified):** the poll's condition reads the manifest with `File.ReadAllLines` while the service's writer loop has it open, so a transient `IOException` or a partly written file fails or confuses the poll, and a 15 s budget is spent against real disk I/O and thread-pool starvation. Widening a timeout does not remove a read race. **Required behaviour:** find the actual race with evidence (reproduce it by running the class under CPU load, for example `dotnet test --filter CycleArchiveServiceTests` several times alongside a busy process), then remove the cause: let the test wait on a **completion signal from the service** (a writer-loop "row flushed" seam or the drained-queue helper from `dev-tasks/2026-10-01-test-sync-settle-delays-and-batch-drained-helper.md`), or read the file with `FileShare.ReadWrite` inside a retry that is bounded by that signal, instead of polling a growing file. Fix **both** manifest tests in the class that share the shape, and say which.

## 3. Acceptance (QA checks)

1. For each test: the failure mechanism **reproduced** (a loop of N runs under load, N and the failure count quoted) before the fix, and the same loop **clean** after it. A fix with no reproduction is a guess.
2. No `Task.Delay`/`Thread.Sleep` added as a barrier, no retry attribute, no skip, no timeout simply widened. `check_test_delay_sync.py` OK.
3. Unfiltered `dotnet test OpenWSFZ.slnx -c Release` on Windows and on WSL Debian (exact commands and per-assembly counts, HK-022; WSL without `nohup`, with `/home/frank/.dotnet` on `PATH`). Bracket nothing special: the Web and E2E tests no longer touch the station config (PR #202).
4. `git diff --stat origin/main -- src native` is **empty** (if a `src/` seam is truly needed, stop and ask QA).
5. The closing commit message documents each root cause (section 11 item 4). No push.

## 4. Process

Cut `fix/flaky-fr-ux-002-and-cycle-archive-manifest` from `origin/main`. Ask QA before running the suite (CPU shared). macOS cannot be run locally: the FR-UX-002 failure came from a macOS runner, so QA will push the branch for a CI run when you are done.
