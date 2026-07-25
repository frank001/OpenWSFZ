# Flaky test — `cycle-audio-archive: size cap deletes oldest files and retains newest`

**Date surfaced:** 2026-07-26, CI on PR #113 (`salvage/hashtablerejectcount-logging`) — a
docs/decoder-logging PR that does not touch this test, this service, or anything nearby.
**Test:** `tests/OpenWSFZ.Daemon.Tests/CycleArchiveServiceTests.cs:308`
`CycleArchiveServiceTests.Retention_SizeCap_DeletesOldestRetainsNewest`
**Owner area:** `OpenWSFZ.Daemon`'s `CycleArchiveService` (the `cycle-audio-archive` feature,
merged 2026-07-25 as PR #109, already on `main`).

## Symptom

```
Expected remaining {"260725_100000.wav", "260725_100015.wav"} to not have any items matching
f.Contains("260725_100000") because the oldest file must be the one deleted, but found
{"260725_100000.wav"}.
   at OpenWSFZ.Daemon.Tests.CycleArchiveServiceTests.Retention_SizeCap_DeletesOldestRetainsNewest()
   in CycleArchiveServiceTests.cs:line 323
```

Failed identically (same two filenames, same message) on two separate `windows-latest` CI runs
for the same PR:
- run `30174105246`, job `89719988250`
- run `30174114371`, job `89720011525`

## Why this is not PR #113's fault

PR #113's diff is exactly `src/OpenWSFZ.Ft8/Ft8Decoder.cs` (+19) and a new
`tests/OpenWSFZ.Ft8.Tests/HashTableRejectCountLoggingTests.cs` (+141) — the `Ft8` project, not
`Daemon`. **PR #112**, opened from the same `main` tree minutes earlier and touching zero `src/`
files at all, passed this exact test on `windows-latest` in its own CI run. Same code path, same
commit ancestry for this file, different outcome — the signature of a race, not a regression
introduced by either PR.

## Root cause, read from the code (not just inferred from symptoms)

`CycleArchiveService`'s retention logic itself is correct: `EnforceRetention`
(`CycleArchiveService.cs:396`) orders files by the cycle timestamp parsed from the filename, not
filesystem time — deliberately, per a comment there recording an earlier WSL-specific fix for
exactly this class of bug. The eviction loop evicts oldest-first exactly as the test expects. I
read it end to end and it is not the culprit.

The race is in the **test's polling condition**. The write pump
(`CycleArchiveService.cs:270-315`) is a single dedicated writer task: for each dequeued item it
writes the `.wav` file, appends the manifest, increments `_cyclesSinceSweep`, and (with
`retentionSweepInterval: 1`, as this test configures it) runs `EnforceRetention` after **every**
write. So the on-disk file count over time, for this test's three enqueued cycles, is a genuine
sequence:

```
0  →  1 (cycle0 written, sweep: 352 KB < 1 MB cap, no eviction)
1  →  2 (cycle1 written, sweep: 704 KB < 1 MB cap, no eviction)
2  →  3 → evict cycle0 → 2 (cycle2 written, sweep: 1.056 MB > 1 MB cap, evicts oldest)
```

The test's own wait condition is:

```csharp
await Poll.UntilAsync(() => CountWavFiles() == 2, ...);
```

**`CountWavFiles() == 2` is true at two different, non-equivalent points in that sequence**: the
transient state after only cycle0+cycle1 have landed (before cycle2 has even been enqueued by the
writer), and the settled state after cycle0 has been evicted following cycle2's write. The poll
has no way to distinguish "still climbing toward 3" from "settled back down to 2 after eviction"
— it just asserts on whatever set of files exists the instant the count first reads 2. On a fast
enough machine the three sequential `TryEnqueue` calls and their writer-task processing outrun the
poll's sampling interval and it only ever observes the settled state. Under a slower or more
I/O-contended CI runner (real disk I/O per write, real manifest append per write, real retention
sweep per write — this is not mocked), the poll catches the ascending path instead, and the
assertions then run against `{cycle0, cycle1}` — exactly the two filenames the CI failure reports,
with cycle2 not yet written and cycle0 not yet evicted. This matches the observed failure exactly,
not just plausibly.

This is the same *class* of defect TESTING_STRATEGY.md §11 already calls out under
"Threading / async waits" (never synchronize on an ambiguous condition), but it is not the
fixed-`Task.Delay` variant Gate G10 checks for — it is a `Poll.UntilAsync` on a condition
(`file count == N`) that is not monotonically settled, so G10 would not have caught it. Worth
naming as a second sub-pattern under that section if this is confirmed and fixed: **a poll
condition must characterize the terminal state uniquely, not just numerically** — here, polling
for the presence/absence of the *specific* expected filenames (as the assertions themselves
already do) rather than a raw count would not have this ambiguity.

## Disposition

**Status: OPEN, tracked here per TESTING_STRATEGY.md §11 — first occurrence.** Not fixed in this
session; PR #113's own diff is unrelated and should not carry this fix as a drive-by. The failed
CI jobs were re-run at the Captain's direction (§11 permits confirming a suspected flake this way;
it is not the same as muting or wrapping the *test* in retry) — see below for the outcome once
those land.

**Re-open / escalation bar, per §11.3:** a second occurrence of this same test failing (on any
PR) before a fix lands escalates to blocker — no merges to `main` until it's fixed or removed
(with QA + Product-Owner sign-off for removal). This document is that first occurrence.

**Suggested fix, for whoever picks this up:** change the poll to wait for the exact expected
terminal file set (e.g. poll until `CountWavFiles() == 2 && !File.Exists(oldestPath)`, or poll
for `File.Exists(newestPath) && !File.Exists(oldestPath)` directly) rather than a bare count. The
same shape may be worth auditing in sibling retention tests in this file
(`Retention_AgeCap_DeletesOlderThanConfiguredAge` and any other `CountWavFiles() == N` poll in
this file) since the ambiguous-count pattern isn't unique to the size-cap test if they share the
same three-enqueue setup.

## Cross-reference

- `TESTING_STRATEGY.md` §11 (Flaky Test Policy) — the policy this document exists to satisfy.
- `openspec/changes/archive/2026-07-21-fix-flaky-test-delay-synchronization/` — the prior flaky-test
  initiative that produced the `Poll` helper and Gate G10; this occurrence is a new sub-pattern
  neither of those covers (an ambiguous poll *condition*, not a fixed delay).
- PR #109 — where `CycleArchiveService` and this test were introduced.
- PR #113 — the unrelated PR whose CI surfaced this.
