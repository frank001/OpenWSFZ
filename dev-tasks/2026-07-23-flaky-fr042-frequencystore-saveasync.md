# Flaky test — FR-042 `SaveAsync updates in-memory list and persists to file`

**Date surfaced:** 2026-07-23, during a full `python3 tools/pre_merge_check.py --skip-wsl` gate
run (D-001 housekeeping session — verifying the AOT-toolchain WARN was actually resolved, per
the Captain's report that fresh Developer/Architect sessions had said so). Unrelated to that
verification; this test failure surfaced incidentally in the same run.
**Test:** `tests/OpenWSFZ.Daemon.Tests/FrequencyStoreTests.cs:111`
`FR-042: SaveAsync updates in-memory list and persists to file`
(`FrequencyStoreTests.SaveAsync_UpdatesEntriesAndPersistsFile`)
**Owner area:** `OpenWSFZ.Daemon` config-store layer — unrelated to whatever else is in flight
at the time; this occurrence's triggering session touched zero `.cs` files.

## Symptom

```
System.UnauthorizedAccessException : Access to the path is denied.
   at System.IO.FileSystem.MoveFile(String sourceFullPath, String destFullPath, Boolean overwrite)
   at OpenWSFZ.Daemon.FrequencyStore.SaveAsync(IReadOnlyList`1 entries, CancellationToken cancellationToken) in FrequencyStore.cs:line 72
   at OpenWSFZ.Daemon.Tests.FrequencyStoreTests.SaveAsync_UpdatesEntriesAndPersistsFile()
```

Full `.trx`-equivalent console capture survived this time (see below) — the first of the three
related occurrences to have one.

Verified:
1. Passes in isolation on Windows — 1/1, 31 ms.
2. Passes on WSL Debian (Linux/glibc) — **3/3 consecutive runs**, isolated to
   `FrequencyStoreTests` (`dotnet test tests/OpenWSFZ.Daemon.Tests -c Release --no-build --filter
   "FullyQualifiedName~FrequencyStoreTests"` via `wsl -d Debian`). Confirms this occurrence is,
   so far, Windows-only — consistent with FR-060 and FR-025, and a stronger corroboration of the
   AV/indexer-handle hypothesis than either of those got, since this is the first of the three
   with a full exception capture to examine.

## Root-cause hypothesis — third occurrence of the FR-060 pattern, exactly as predicted

`FrequencyStore.SaveAsync` (`src/OpenWSFZ.Daemon/FrequencyStore.cs:53-72`) uses the identical
write-to-temp-then-`File.Move(tmp, _path, overwrite: true)` pattern (line 72) as
`CallsignRegionStore` (FR-060) and `JsonConfigStore` (FR-025), with no retry-on-exception wrapper
around the `File.Move` call. `FrequencyStore` does have its own `_saveLock` `SemaphoreSlim`
(line 54) serialising its own concurrent callers, same limitation as `JsonConfigStore`'s
equivalent — it does nothing against an external process transiently holding a handle on the
file.

**This is not a new theory landing on a fourth store — it is the exact scenario FR-060's own
dev-task named as its second-bullet re-open condition, by name, on 2026-07-21:**

> The same failure signature turns up in a *different* store's `SaveAsync` test (e.g.
> `FrequencyStoreTests`), which would corroborate the "shared write-then-rename helper" theory
> rather than something specific to `CallsignRegionStore`.

It happened in `JsonConfigStoreTests` first (FR-025, 2026-07-23 earlier today), not
`FrequencyStoreTests` as guessed — but now `FrequencyStoreTests` has failed too, exactly as
named. Three of the five stores sharing this helper shape
(`JsonConfigStore`, `FrequencyStore`, `CallsignRegionStore`, `CallsignGrammarStore`,
`PropModeStore` — see FR-025's file for the full grep-confirmed scope) have now independently
shown the identical symptom.

**Exception type is more specific than either prior occurrence.** FR-060 and FR-025 both lost
their exception detail before it could be captured (`.trx` not retained). This is the first of
the three with a full stack trace, and it is `UnauthorizedAccessException` on `File.Move` — the
canonical .NET-on-Windows signature for a target path transiently held open by another process
(AV real-time scan, Windows Search indexer) rather than a generic sharing-violation
`IOException`. That is corroborating, not conclusive — a single capture doesn't rule out other
causes — but it is the most specific evidence yet for the original hypothesis.

## Re-open trigger status

FR-060's original condition (a second store) was hit by FR-025. FR-025 raised the bar to a
**third occurrence (any store) or a captured exception**. This occurrence satisfies **both**
of those simultaneously — third independent store, and a captured, specific exception.

**Captain's decision (2026-07-23):** logged for the record; continue monitoring, no code change
at this time. Consistent with the disposition on FR-060 and FR-025. Re-open condition carried
forward: **QA flagged that the stated bar has technically been cleared** (third store + captured
exception, both at once) — recorded here for the next review rather than re-litigated
unilaterally. If a fourth occurrence, a second captured exception, or a Windows-only-vs-WSL
split repeats on a store *outside* this list of five, that should be treated as materially new
evidence rather than a fourth instance of the same monitoring cycle.

**Status: OPEN, monitor only** — same disposition as FR-060 and FR-025. Not fixed here — no
`src/` change made; this is a tracking/cross-reference write-up only.

## Cross-reference

- `dev-tasks/2026-07-21-flaky-fr060-isseeddata-saveasync.md` — original hypothesis,
  state-isolation theory ruled out, first Captain accept-as-tracked-flake decision, and the
  second-bullet re-open condition this occurrence fulfils by name.
- `dev-tasks/2026-07-23-flaky-fr025-audiodevicefriendlyname-roundtrip.md` — second occurrence
  (`JsonConfigStore`), five-store pattern scope confirmed by grep, and the
  third-occurrence-or-captured-exception re-open bar this occurrence clears.
