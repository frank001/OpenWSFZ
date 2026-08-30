# Flaky test — `cycle-audio-archive: dropped cycles appear as an explicit gap marker on the next archived row`

**Date surfaced:** 2026-08-30, `tools/pre_merge_check.py` run on the Captain's initiative (HK-006)
against `qa/nbr-a-2026-08-29` — a docs/QA-only branch (61 files, no `src/`, `native/` or `openspec/`
path in `git diff --name-only main...HEAD`) that does not touch this test, this service, or anything
nearby.

**Test:** `tests/OpenWSFZ.Daemon.Tests/CycleArchiveServiceTests.cs:239-281`
`CycleArchiveServiceTests.Manifest_RecordsGapMarker_AfterDroppedCycles`
**Owner area:** `OpenWSFZ.Daemon`'s `CycleArchiveService` (the `cycle-audio-archive` feature).
**Policy:** TESTING_STRATEGY.md §11 (Flaky Test Policy) — filed per item 1, "first flake on any test
files an issue tagged `flake`." **This is a first observation** (grepped the repo for
`Manifest_RecordsGapMarker` and for `cycle-archive.csv`-plus-`another process`; no prior doc, dev-task
or commit message names this test or this failure mode). Distinct from the **already-documented**
`Retention_SizeCap_DeletesOldestRetainsNewest` flake in this same class/file
(`dev-tasks/2026-07-26-flaky-cyclearchiveservice-retention-sizecap.md`) — different test, different
failure shape (assertion mismatch there vs. a raw `IOException` here).

## Symptom

```
Failed cycle-audio-archive: dropped cycles appear as an explicit gap marker on the next archived row [49 ms]
Error Message:
 System.IO.IOException : The process cannot access the file
 'C:\Users\Frank\AppData\Local\Temp\openwsfz-cycle-archive-test-00rn1bfc.pbg\cycle-archive.csv'
 because it is being used by another process.
Stack Trace:
   at ... SafeFileHandle.CreateFile(...)
   at ... FileStreamHelpers.ChooseStrategyCore(...)
   at System.IO.StreamReader.ValidateArgsAndOpenPath(String path, Int32 bufferSize)
   at System.IO.File.ReadAllLines(String path, Encoding encoding)
   at CycleArchiveServiceTests.<>c__DisplayClass13_0.<Manifest_RecordsGapMarker_AfterDroppedCycles>b__4()
   at OpenWSFZ.TestSupport.Poll.UntilAsync(...)
   at CycleArchiveServiceTests.Manifest_RecordsGapMarker_AfterDroppedCycles() ...CycleArchiveServiceTests.cs:line 274
```

1 failure out of 621 tests in `OpenWSFZ.Daemon.Tests.dll` (Windows, Release, single run — this is the
only Windows execution `pre_merge_check.py` performs; it does not re-run automatically). The
subsequent WSL Debian run of the same suite (589 of that platform's applicable tests) passed clean,
which rules out a logic regression on Linux but says nothing about Windows, since the two runs cover
different test subsets and different filesystems.

## Root cause — plausible, not confirmed

Read `CycleArchiveService.cs:353-366`: each manifest row append opens a **fresh**
`new StreamWriter(manifestPath, append: true)`, which per the two-argument `StreamWriter` constructor
opens the underlying `FileStream` with `FileShare.Read` — compatible in principle with the test's
concurrent `File.ReadAllLines(manifestPath)` (line 274, inside `Poll.UntilAsync`'s polled condition),
which itself opens for read with a compatible share mode. On paper the two sides should never collide.

Unlike the July `Retention_SizeCap` flake (a genuine logic race in the poll's *terminal-state*
condition — `retentionSweepInterval: 1000` here means the sweep essentially never runs in this test,
so that mechanism is not in play), this looks like the more familiar Windows-CI-runner symptom: a
**transient external lock** on a just-closed file — Windows Defender's real-time scan or the search
indexer briefly opening a newly-written file non-shared immediately after the writer's
`StreamWriter` disposes it, in the narrow window before the poll's next read attempt. This is a
known class of Windows flake outside the application's own `FileShare` control, not a defect in
`CycleArchiveService`'s or the test's synchronization logic as far as I can read it. **Flagged as a
hypothesis, not a conclusion** — I have not instrumented a repro to confirm it, and do not have
`src/`/`tests/` write authorization on this QA-only branch to do so (HK-011: needs a separate
Developer session).

## Disposition

**Not resolved here — reported per TESTING_STRATEGY.md §11 item 1, escalated rather than decided
unilaterally**, same posture as the July precedent (`dev-tasks/2026-07-26-flaky-cyclearchiveservice-retention-sizecap.md`),
which itself notes a confirmation re-run needs the Captain's authorization, not a QA unilateral
call. This is a **first occurrence** of this specific test/failure — §11 item 3's "repeat flake ⇒
blocker" threshold is not yet crossed, so this document alone does not assert a merge block. Whether
to re-run `pre_merge_check.py` to distinguish flake from regression, and whether this branch's
(docs/QA-only, unrelated diff) merge should proceed pending that, is for the Captain/Architect per
HK-010/HK-006.

**Suggested fix, for whoever picks this up (not proposed as a change here):** if the transient-lock
hypothesis holds, the fix belongs in `Poll.UntilAsync`'s condition at this call site — catch
`IOException` from a transient sharing violation and treat it as "not yet true, poll again" (in scope
of what `Poll` already exists to do) rather than letting it propagate as a test failure. This is not
the same as wrapping the *test* in retry (§11 item 2's prohibition) — it is the poll tolerating an
external, transient condition on the resource it's already polling.

## Cross-reference

- TESTING_STRATEGY.md §11 (Flaky Test Policy) — the policy this document exists to satisfy.
- `dev-tasks/2026-07-26-flaky-cyclearchiveservice-retention-sizecap.md` — the prior flake in this
  same test class, different test, different mechanism.
- `qa/rr-study/2026-08-30-1204-architect-to-qa-TODO-pre-merge-nbr-a-branch.md` — the branch this
  `pre_merge_check.py` run was clearing for merge when this surfaced.
