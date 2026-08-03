# Dev-task — `Retention_SizeCap_DeletesOldestRetainsNewest` is time-bombed and has been failing since 2026-08-01

**Author:** QA, 2026-08-03 (15:46 UTC, `date -u`, per HK-017).
**Test:** `tests/OpenWSFZ.Daemon.Tests/CycleArchiveServiceTests.cs:308`
`CycleArchiveServiceTests.Retention_SizeCap_DeletesOldestRetainsNewest`
**Scope:** `tests/` only. No `src/` change — `CycleArchiveService` is behaving correctly.
**Severity:** blocker per `TESTING_STRATEGY.md` §11.3. `main` is red and will stay red.

> ### ⚠️ This is NOT the 2026-07-26 flake
> `dev-tasks/2026-07-26-flaky-cyclearchiveservice-retention-sizecap.md` describes an
> **intermittent CI** failure on this same test with a **different signature** — the oldest file
> was *retained* when it should have been deleted. This defect is **deterministic**, reproduces
> locally, and deletes *everything*. Filing it under the old task would bury it. Both may be open
> at once; fixing this one does not close that one.

---

## 1. Root cause

`EnforceRetention` applies the **age cap before the size cap** (`src/OpenWSFZ.Daemon/CycleArchiveService.cs:422-438`):

```csharp
var cutoffAgeUtc = DateTime.UtcNow - TimeSpan.FromHours(config.MaxAgeHours);   // line 422
foreach (var x in files.Where(x => x.CycleUtc < cutoffAgeUtc).ToList())        // line 424
{
    TryDelete(x.File);
    files.Remove(x);
}
                                                                               // line 430 onward:
var maxBytes = config.MaxSizeMb * 1024L * 1024L;                               // the size cap this
long total   = files.Sum(x => x.File.Length);                                  // test exists to
while (total > maxBytes && i < files.Count) { ... }                            // exercise
```

The fixture's cycle timestamps are **hardcoded to a fixed calendar date**
(`CycleArchiveServiceTests.cs:466-467`):

```csharp
private static DateTime CycleAt(int index) =>
    new DateTime(2026, 7, 25, 10, 0, 0, DateTimeKind.Utc).AddSeconds(15 * index);
```

and the test does not override `MaxAgeHours`, so it takes the default of **168 h** (7 days —
`CycleAudioArchiveConfig.cs:92`). Therefore:

```
2026-07-25 10:00:00 UTC  +  168 h  =  2026-08-01 10:00:00 UTC
```

**Since that instant, all three fixture files are older than the cutoff and are deleted by the age
cap before the size-cap loop is ever reached.** `CountWavFiles()` returns 0, the poll at line 327
never satisfies, and it times out with `currently 0`. It will fail every run from now on.

**Why only this test.** Its siblings leave `retentionSweepInterval` at the default 100, so
`EnforceRetention` never runs during three enqueues. This test sets `retentionSweepInterval: 1`
(line 312), so the sweep runs after every cycle and the age cap fires.

## 2. Evidence

Measured 2026-08-03, not inferred:

| check | result |
|---|---|
| Solo, on `fix/cycleframer-grid-realignment` | **3/3 FAIL** |
| Solo, on `main` at `6499538` (no branch changes) | **FAIL** |
| Caused by the drift branch | **No** — reproduces on `main`; the test has no `CycleFramer` reference |
| Flaky under load | **No** — deterministic solo |

The reported message is `expected retention to prune to 2 files (oldest evicted, newest retained),
currently 0`. The **`currently 0`** is the diagnostic: not "wrong file kept", but "no files at all".

## 3. What to build

### Preferred — remove the time bomb

Make `CycleAt` relative to the present rather than a fixed date, snapped to a 15-second cycle
boundary so the `yyMMdd_HHmmss` filenames stay well-formed and distinct.

**This pattern is already proven in this very file** — the two age-cap tests build their stamps
from `DateTime.UtcNow` (lines 346-347 and 370):

```csharp
var oldStamp = (DateTime.UtcNow - TimeSpan.FromHours(200)).ToString("yyMMdd_HHmmss");
var newStamp = (DateTime.UtcNow - TimeSpan.FromHours(1)).ToString("yyMMdd_HHmmss");
```

Callers that assert on literal filenames all derive them from `CycleAt` itself — lines 201, 325,
326, 331, 333 — so they stay self-consistent. **Check each of those before committing** rather than
trusting this list; that is the one risk in this option.

### Fallback — targeted

`MakeService` already exposes a `maxAgeHours` parameter (line 477, default 168). Pass a large value
in this one test so the age cap cannot fire:

```csharp
var service = MakeService(CycleAudioArchiveMode.All, maxSizeMb: 1,
                          retentionSweepInterval: 1, maxAgeHours: 999_999);
```

One line, no shared-fixture risk — but it leaves the same trap set for the next test that uses
`CycleAt` with a sweep enabled.

**Recommendation: the preferred option.** The fallback fixes today's failure; it does not stop this
recurring. If you take the fallback, say so and why, so the residual trap is on the record rather
than silently accepted.

### Either way

⚠️ **Do not "fix" this by changing `EnforceRetention`.** The service is correct: an age cap that
runs before a size cap is the right order, and deleting files older than `MaxAgeHours` is exactly
its job. The bug is entirely in the fixture. If your reading disagrees, **stop and escalate** — that
would be a finding about the service and a different task.

## 4. Acceptance

1. `Retention_SizeCap_DeletesOldestRetainsNewest` green **solo** and in the **full**
   `OpenWSFZ.Daemon.Tests` run.
2. The other `CycleArchiveServiceTests` still green — particularly the two age-cap tests, which
   depend on real elapsed time and must not be broken by a fixture change.
3. **A date-independence check:** the fix must not merely move the bomb. If you take the preferred
   option, state in the commit message why the test can no longer age out. A reviewer should not
   have to re-derive it.

## 5. Boundaries

- Per **HK-011**: `tests/` only here, but still a Developer session — local build/tests only, and
  **show the diff to the Captain before `git push`**.
- Per **HK-006**: do **not** run `python3 tools/pre_merge_check.py` — Captain's trigger only.
- Per **HK-010**: merge needs the Captain's explicit sign-off.
- Do not touch `src/OpenWSFZ.Daemon/CycleArchiveService.cs` (§3).
- Do not close or amend the 2026-07-26 flaky dev-task — different defect, still open.

## 6. Traceability

- `src/OpenWSFZ.Daemon/CycleArchiveService.cs:404-438` — `EnforceRetention`; age cap at 422-428.
- `src/OpenWSFZ.Abstractions/CycleAudioArchiveConfig.cs:92` — `MaxAgeHours = 168`.
- `tests/OpenWSFZ.Daemon.Tests/CycleArchiveServiceTests.cs:466-467` — `CycleAt`, the time bomb.
- `dev-tasks/2026-07-26-flaky-cyclearchiveservice-retention-sizecap.md` — the **separate**
  intermittent-CI defect on the same test.
- `flaky-cyclearchiveservice-manifest-test-todo.md` (QA memory) — a **third**, distinct issue:
  `Manifest_WritesOneRowPerArchivedCycle_InOrder` failing only under full-suite load.
