# Developer handoff: SUB-FEAS merge branch, two gate failures in the Developer's tests (G10 delay lint, one Linux-only test) and the Linux native library

**Date:** 2026-10-01. **From:** QA. **To:** Developer. **Priority:** blocks the SUB-FEAS merge (the merge branch is otherwise ready).

## 1. Context

QA merged locally (not pushed) everything before Stage B into `merge/sub-feas-local` (`2c687768`): `feat/sub-feas-two-stage-publish` (native subtraction, Stage A speed-up, two-stage publish), `eng/config-save` (v0.52) and the managed-control harness, then bumped the release to **v0.53**. The mechanical gate run on that branch passed everything except **two gates that fail on tests this workstream added**, plus one stale binary:

| Gate | Result | Cause |
|---|---|---|
| G10, test-delay-synchronization lint | FAIL, 9 untracked bare-delay sites | New tests use fixed `Thread.Sleep`/`Task.Delay` as synchronisation (listed in section 3, Task A) |
| WSL Debian compile and test | FAIL, 1 test | `SubfeasNativeSpeedTests.Workspace_NoGrowthAfterWarmup_AndFreedAtShutdown` (display name 8.7) fails on Linux only (Task B) |
| Native freshness | The Linux `libft8.so` was **stale** (does not contain shim version 20260056); the gate script rebuilt it | The committed `src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so` was never rebuilt after the Stage A shim bump (Task C) |

Everything else passed: Windows full suite (all projects green, including 417 Ft8 tests), build, G3, G8 (63/63 OpenSpec), G9a, G9b, both publishes.
Log (QA's scratchpad, not in the repo): the failing lines are quoted below so you do not need it.

## 2. Branch

Cut **`fix/sub-feas-g10-and-linux-test`** from **`feat/sub-feas-two-stage-publish`** (`319911ee`). Do not work on `main`, `merge/sub-feas-local` or `feat/sub-feas-stage-b`. QA will merge your branch into the merge branch. (Stage B contains the same test files and will need your fix merged in; tell QA when the branch is ready and QA will say whether Stage B should rebase.)

Test-only changes and the one binary, **no change to product code**, with one allowed exception noted in Task B.

## 3. Actions

### Task A: G10, replace or justify 9 bare-delay sites (all in tests)

`python tools/check_test_delay_sync.py` is the lint. It reports these (matching is by file and matched text, and counts occurrences, so "3 occurrences found, 0 listed" means all three equal-text sites in that file):

| File | Line | Text | Occurrences |
|---|---:|---|---:|
| `tests/OpenWSFZ.Daemon.Tests/DecodePumpTests.cs` | 270 | `Task.Delay(300)` | 1 |
| `tests/OpenWSFZ.Daemon.Tests/TwoStageEngageCharacterisationTests.cs` | 74 | `Task.Delay(100)` | 1 |
| `tests/OpenWSFZ.Ft8.Tests/SubfeasNativeSpeedTests.cs` | 111, 267, 328 | `Thread.Sleep(300)` | 3 |
| same | 142, 227 | `Thread.Sleep(250)` | 2 |
| same | 180 | `Thread.Sleep(200 + 50 * w)` | 1 |
| `tests/OpenWSFZ.Ft8.Tests/SubtractionDeadlineTests.cs` | 293 | `Thread.Sleep(1)` | 1 |

(The lint also lists `SubtractionDeadlineTests.cs:117`, `Thread.Sleep(flagDue + TimeSpan.FromMilliseconds(150))`; it is not on the failing list, so leave it unless you touch that file for the line-293 site.)

For each site, in this order of preference:
1. **Replace with the shared polling helper** (`OpenWSFZ.TestSupport`, `Poll.UntilAsync` and its typed wrappers; see `test-delay-debt.md` for the convention). Most of these wait for a background fit to be **leased** or **started** before the test shuts the pool down or sets the cancel flag. The positive condition exists: poll `Pool().Leased` (the pool statistics the test already reads) for the expected count, with a generous timeout, instead of sleeping a guessed time.
2. If a site is a genuine "prove an absence" wait (nothing to poll for), add it to `test-delay-debt.md` with a one-line reason, in the same format as the existing entries (`path:line: matched-text`). **Do not** add an entry merely to silence the lint.
3. `Thread.Sleep(1)` at `SubtractionDeadlineTests.cs:293` is probably a spin-yield inside a loop, not a synchronisation barrier; if so prefer `Thread.Yield()`/`SpinWait` over a debt entry.

Keep the tests' meaning unchanged: every assertion stays, and a test must still fail if its behaviour regresses.

### Task B: fix the Linux-only failure of 8.7 (`Workspace_NoGrowthAfterWarmup_AndFreedAtShutdown`)

Failure (WSL Debian, line 311 of `SubfeasNativeSpeedTests.cs`):

```
Expected (beforeFree - PrivateBytes()) to be greater than 18729508L because the memory really goes back,
it is not just forgotten by the accounting, but found -102400L (difference of -18831908).
```

After `SubfeasPoolShutdown()` the pool statistics are correct (`Live`, `Idle` and `Leased` all 0 pass), but Linux private bytes did not fall at all (about −0.1 MB against the more than 18.7 MB the assertion requires). The same test passes on Windows.

QA's hypothesis, **not verified**: glibc's `free` does not necessarily return a freed 25–30 MB block to the OS (the dynamic mmap threshold rises after the first such free, so later blocks come from the heap, which is trimmed lazily). That would make this a property of the allocator, not of the pool.

Actions, in order:
1. Establish the cause (do not accept the hypothesis unchecked): for example, call `malloc_trim(0)` right after shutdown in a throwaway run, or print `/proc/self/status` `VmRSS`/`RssAnon` before and after, and see whether the memory comes back.
2. If it is the allocator: keep the accounting assertions (`Live`, `Idle`, `Leased` equal to 0) on **every** platform, and make the "memory really goes back" assertion **Windows-only** with a one-line comment giving the reason (or, if you can show `malloc_trim(0)` in the shutdown path is cheap and correct, add it behind the Linux build; that is a `src/`/native change, so state it explicitly in your report for QA and the Architect to approve). The assertion QA must keep is that the same fixture is **not** weakened on Windows.
3. If it is a real leak on Linux, report it to QA before changing anything else; that is a product defect, not a test fix.

### Task C: rebuild and commit the Linux native library

`src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so` is stale: it does not contain shim version **20260056** (the Stage A value; the Windows DLL is current). Rebuild it from the committed source with the repo's Linux build (`native/ft8_lib_build/build_linux.sh`, run in WSL Debian; see `src/OpenWSFZ.Ft8/Native/BUILD.md`) and commit it on your branch, then run `python tools/check_native_version.py <path-to-.so> 20260056` and quote its output in your report.

## 4. Acceptance criteria (what QA checks)

1. `python tools/check_test_delay_sync.py` reports **0 untracked bare-delay sites**. Any new `test-delay-debt.md` entry carries a reason and is justified in your report.
2. On Windows, the whole test suite is green, and test 8.7 still asserts the memory-returns-to-the-OS condition on Windows (not weakened).
3. In WSL Debian, the whole `OpenWSFZ.Ft8.Tests` project passes, test 8.7 included. Quote the exact filter and the pass counts, **unfiltered**; a filtered-out run is not a result (HK-022).
4. `check_native_version.py` accepts the committed `libft8.so` at 20260056, and `git diff --stat -- src/ native/` for your branch lists **only** the `.so` plus (if Task B takes the second option) the one declared native/`src` change. Say which.
5. No test is deleted or skipped. No assertion on the deadline, workspace-pool or two-stage behaviour is weakened.
6. Your report states the cause established in Task B step 1 (allocator or leak), with the evidence.

## 5. References

- OpenSpec changes: `sub-feas-native-subtraction` (the pool and its tests), `sub-feas-speed-redesign` (Stage A; design D4 for the workspace pool).
- Gate scripts: `tools/check_test_delay_sync.py`, `test-delay-debt.md`, `tools/check_native_version.py`.
- Tests: `tests/OpenWSFZ.Ft8.Tests/SubfeasNativeSpeedTests.cs`, `SubtractionDeadlineTests.cs`; `tests/OpenWSFZ.Daemon.Tests/DecodePumpTests.cs`, `TwoStageEngageCharacterisationTests.cs`.
- Merge branch for context: `merge/sub-feas-local` @`2c687768` (local, QA).
