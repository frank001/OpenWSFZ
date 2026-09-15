# Developer handoff: tolerate transient `IOException` in `CycleArchiveServiceTests` manifest polls

**Authored by:** QA, 2026-09-14 18:36Z (per HK-000/HK-015), timestamp per `date -u` (HK-017).
**Status:** Proposed. Per HK-011, needs the Captain's explicit sign-off before pickup; the Developer
session implementing this does not run `pre_merge_check.py` or push/merge on its own initiative (QA
verifies, Captain signs off the merge, HK-010).
**Tracking:** [GitHub issue #177](https://github.com/frank001/OpenWSFZ/issues/177), label `flake`
(label created 2026-09-14 — did not exist for the first occurrence).
**Branch:** new short branch off `main`, name at the Developer's/Captain's discretion. Do not combine
with any other fix.

---

## 0. Why this is a blocker, not a routine cleanup item

`TESTING_STRATEGY.md` §11 item 3: **"A repeat flake on the same test before the issue is fixed
escalates to blocker — no merges to `main` until the test is fixed or removed."** This test has now
failed with the **identical** stack and message twice:

| # | Date | Context | Branch (unrelated diff both times) |
|---|---|---|---|
| 1 | 2026-08-30 | `pre_merge_check.py` on `qa/nbr-a-2026-08-29` | docs/QA-only, 61 files, no `src`/`native`/`openspec` |
| 2 | 2026-09-14 | CI `push`-leg of PR #175 | `feat/passband-140-ship` — touches only `OpenWSFZ.Ft8`/native shim |

```
System.IO.IOException : The process cannot access the file
'...\cycle-archive.csv' because it is being used by another process.
   at ... File.ReadAllLines(String path, Encoding encoding)
   at CycleArchiveServiceTests.<>c__DisplayClass13_0.<Manifest_RecordsGapMarker_AfterDroppedCycles>b__4()
   at OpenWSFZ.TestSupport.Poll.UntilAsync(...)
```

Full detail: `dev-tasks/2026-08-30-flaky-cyclearchiveservicetests-manifestgapmarker-file-lock.md`
(first occurrence, root-cause hypothesis) and GitHub issue #177 (both occurrences, this task's scope).

## 1. Not the same defect as the other two `CycleArchiveServiceTests` dev-tasks

Do not conflate this with either prior fix in the same file — both are already applied and merged,
and neither covers this failure mode:

- **`dev-tasks/2026-07-26-flaky-cyclearchiveservice-retention-sizecap.md`** (fixed, PR #114): a
  genuine poll *terminal-state* race in `Retention_SizeCap_DeletesOldestRetainsNewest` — a bare
  `CountWavFiles() == 2` matched a transient intermediate state, not just the settled one. Different
  test, different mechanism (assertion mismatch, not an exception).
- **`dev-tasks/2026-09-01-cyclearchiveservicetests-manifest-poll-timeout.md`** (fixed, branch
  `fix/cyclearchiveservicetests-poll-timeout`, Captain-accepted with a documented residual): widened
  five `Poll.UntilAsync` calls in this file — including this very test's two poll sites — from 5s to
  15s, because real disk I/O under full-solution parallel load occasionally missed the default
  budget. **This fix is already live in the source** (`CycleArchiveServiceTests.cs:293,314` both
  already read `timeout: TimeSpan.FromSeconds(15)`). It addresses `TimeoutException` (the budget
  expiring), not what's failing now.

**This occurrence is a raw `IOException` thrown immediately inside the polled predicate, not a
timeout.** `Poll.UntilAsync` lets an exception thrown by its condition delegate propagate rather than
treating it as "not yet true, try again" — so a transient sharing violation on the manifest file
(most likely Windows Defender or the search indexer briefly opening the just-`StreamWriter`-closed
file non-shared, per the August dev-task's hypothesis) aborts the whole poll instantly, regardless of
how much of the 15s budget remains. Widening the timeout further does nothing for this failure mode.

## 2. Recommended fix

In `tests/OpenWSFZ.TestSupport/Poll.cs`'s `UntilAsync` (or at the two call sites in
`CycleArchiveServiceTests.cs:274` and `:314` if a shared-helper change is judged too broad-blast-radius
for this ticket — Developer's call, state which was chosen and why): catch `IOException` raised by
the condition delegate and treat it the same as a `false` result (loop again until the bounded
timeout), rather than letting it escape the poll. Do **not**:

- Wrap the *test* in retry (§11 item 2 prohibits this — this is the poll tolerating a transient
  external condition on the resource it is already polling, not the test being re-run).
- Widen the timeout again (§1 — orthogonal mechanism, already addressed).
- Swallow `IOException` globally across all of `Poll` for every caller without checking whether any
  other `Poll.UntilAsync` use in the codebase relies on an `IOException` propagating as a real
  failure signal (grep first).

## 3. Scope

- `tests/OpenWSFZ.TestSupport/Poll.cs` (preferred, if the shared-helper change is judged safe) **or**
  `tests/OpenWSFZ.Daemon.Tests/CycleArchiveServiceTests.cs:274`/`:314` (localised, if not).
- No `src/CycleArchiveService.cs` change — the July task already confirmed
  `EnforceRetention`/the writer loop are correct; this is a test-harness-only defect, same posture as
  both prior fixes in this file.

## 4. Definition of done

- [ ] Transient `IOException` from the polled file read no longer aborts `Manifest_RecordsGapMarker_
      AfterDroppedCycles` (and, if the fix is at the `Poll.UntilAsync` level, confirm no other caller's
      contract changes in a way that would mask a real, non-transient `IOException`).
- [ ] Repro attempt: run the target test repeatedly (isolation and full-solution) — note this flake
      has never reproduced on demand (0/several manual re-runs in both prior occurrences), so absence
      of a fresh reproduction does not itself validate the fix; state this plainly in the closing
      commit rather than claiming "N green runs ⇒ fixed" (§11 item 4 requires the root cause
      documented, not a run count standing in for it).
- [ ] Gate G10 (`tools/check_test_delay_sync.py`) still passes.
- [ ] `git diff main --stat` confirmed limited to the file(s) named in §3.
- [ ] Close GitHub issue #177 in the merge commit/PR description.
- [ ] NFR-021 / callsign scan — not applicable (no decode data touched), state so explicitly.

🛑 **Developer session must stop after implementing and self-verifying — no push, no merge, no
`pre_merge_check.py` run** (HK-010/HK-014/HK-006). QA reviews the diff against this task; the Captain
rules on merge.
