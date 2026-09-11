# Developer handoff: `RepeatedCycleLabel_ProducesTwoDistinctFiles` fails deterministically during UTC hours 20-23

**Authored by:** QA, 2026-09-11 (per HK-000/HK-015), timestamp per `date -u` at authoring time (HK-017).
**Status:** 🔴 Root-caused, NOT fixed. First occurrence of this specific test's failure — per
`TESTING_STRATEGY.md` §11.1 this files the issue; it is not yet a repeat flake and does not by itself
block other merges (§11.3), but it **will fail again, deterministically, every day between roughly
20:00 and 23:59 UTC**, so it should not be left open past the next occurrence.

## 0. How this was found

Not chased from a "is the suite reliable" question — found investigating a live CI failure the Captain
reported on `arch/permission-rule-wildcards` / PR #152. That PR's diff is `tools/wsl-noconv.sh` only
(`git diff --stat` confirmed, `gh pr diff 152 --name-only`) — a Bash wrapper script, zero `src/`/`tests/`
touch. CI run `34525161840` failed `Build & Test` on **all three OSes** (windows-latest, ubuntu-latest,
macos-latest) with the identical failure:

```
Failed cycle-audio-archive: repeated cycle label produces two files, neither overwritten
Error Message:
   Expected files to contain a single item matching f.Contains("_2") because exactly one of the two
   colliding-label files must carry the collision suffix, but 2 such items were found.
   at OpenWSFZ.Daemon.Tests.CycleArchiveServiceTests.RepeatedCycleLabel_ProducesTwoDistinctFiles()
     in tests/OpenWSFZ.Daemon.Tests/CycleArchiveServiceTests.cs:line 119
```

All three legs started within the same minute (20:14-20:19Z), which is the tell — this is a wall-clock
window defect, not a per-OS or per-PR one. **Confirmed not caused by PR #152** and confirmed reproducible
purely by wall-clock time, independent of any branch: re-ran the exact same CI job (`gh run rerun 34525161840
--failed`) later the same day once past the window; see status box for the result.

## 1. Root cause — a substring assertion collides with the filename format during hours 20-23 UTC

`CycleArchiveService.ProcessItemAsync` (`src/OpenWSFZ.Daemon/CycleArchiveService.cs:297`) builds the base
filename as `item.CycleStart.ToString("yyMMdd_HHmmss") + ".wav"` — **one literal underscore**, between the
date and time components. `ResolveCollisionFreeFilename` (`:330-`) appends `_2`, `_3`, … only on an actual
collision, so a colliding pair is `{stamp}.wav` (untouched) and `{stamp}_2.wav` (second write).

The test (`CycleArchiveServiceTests.cs:100-123`) distinguishes the two files with a raw substring check:

```csharp
files.Should().ContainSingle(f => f!.Contains("_2"), "... must carry the collision suffix");
files.Should().ContainSingle(f => !f!.Contains("_2"), "... must keep the unsuffixed base name");
```

This assumes `"_2"` can only ever appear as the collision suffix. It can't: the base filename's own
literal underscore is immediately followed by `HH`, the two-digit hour. **Whenever the fixture's hour is
20, 21, 22, or 23, the unsuffixed base filename itself contains the substring `"_2"`** (e.g.
`260910_201745.wav` contains `_20`). At that point both files match the first predicate (2 matches, not
1 — exactly the observed error) and neither matches the second (0 matches, not 1).

The fixture's timestamp is real wall-clock time, not injected: `CycleAt`/`FixtureEpochUtc`
(`CycleArchiveServiceTests.cs:565-576`) resolves `DateTime.UtcNow.AddMinutes(-5)` once per test run,
snapped to the 15s cycle grid. This is itself a direct violation of `TESTING_STRATEGY.md` §11.2's own
named pre-emption for this exact failure class — *"Time: all time-dependent code uses `IClock`, never
`DateTime.Now` directly. Tests inject a deterministic clock."* — the fixture was deliberately re-anchored
to real time in `b34c017` (2026-08-03) to defuse a **different** time bomb (an absolute fixed date aging
out against `MaxAgeHours`), and that fix is correct for *that* problem, but it left the assertion in this
one test exposed to a new, narrower time-of-day window it was never checked against.

**Probability:** 4 of 24 UTC hours, so this test has roughly a 1-in-6 chance of failing on any given CI
run, independent of load, OS, or branch — not a resource-contention flake (the usual shape logged in
`flaky-cyclearchiveservice-manifest-test-todo.md`), a deterministic function of the wall clock at the
moment `FixtureEpochUtc` is resolved.

## 2. Ruled out

- **Not caused by PR #152's diff.** `tools/wsl-noconv.sh` only; confirmed via `gh pr diff 152 --name-only`.
- **Not OS-specific.** Identical failure, same assertion, same line, on Windows, Linux, and macOS legs of
  the same run.
- **Not the already-tracked manifest-poll flake** (`flaky-cyclearchiveservice-manifest-test-todo.md`,
  `Manifest_WritesOneRowPerArchivedCycle_InOrder`) — different test, different mechanism (poll timeout
  under load vs. a deterministic wall-clock substring collision), different fix shape.
- **Not a real product defect.** `CycleArchiveService`'s collision handling is correct — it is the test's
  own assertion that cannot tell its own base filename apart from a suffixed one during 4 hours a day.

## 3. Recommended fix

Make the two predicates check the suffix's actual position, not an anywhere-substring. Two ways, either
acceptable:

- Compare against the literal expected stems: `f == $"{sameLabel:yyMMdd_HHmmss}.wav"` for the unsuffixed
  file and `f == $"{sameLabel:yyMMdd_HHmmss}_2.wav"` for the suffixed one — exact, no ambiguity, and also
  strengthens the assertion (today it would pass even if the suffix were `_3` or `_99`, which is not what
  the test claims to verify).
- Or anchor the check to the filename's end: `f!.EndsWith("_2.wav")` / `!f!.EndsWith("_2.wav")` — cheaper
  diff, still eliminates the hour-collision since `HHmmss` is never the last four characters before
  `.wav`.

The first option is preferred — it matches what the test's own `DisplayName` and reasoning strings already
claim to check (the exact suffix on the exact colliding stamp), not just "some file has `_2` somewhere in
it." `src/CycleArchiveService.cs` needs no change — this is a `tests/`-only fix, same footing as the
sibling dev-tasks in this file's neighbourhood.

Do not fix this by changing `FixtureEpochUtc` to avoid hours 20-23, by adding a `Skip`/retry, or by
widening the assertion to tolerate 2 matches — all three would hide the bug rather than fix it (`TESTING_
STRATEGY.md` §11.2: "The test is not muted, skipped, or wrapped in retry").

## 4. Definition of done

- [ ] `RepeatedCycleLabel_ProducesTwoDistinctFiles`'s two `ContainSingle` predicates changed to exact
      (or end-anchored) filename checks, with a comment citing this dev-task and the hour-20-23 mechanism
- [ ] Verify the fix actually distinguishes the two files when `FixtureEpochUtc`'s hour is deliberately in
      20-23 — inject or fake the clock for this one test if that is the only way to exercise the failing
      branch under test, since the bug will not otherwise reproduce outside that window
- [ ] `dotnet test tests/OpenWSFZ.Daemon.Tests` — full project, run at least once
- [ ] Gate G10 (`tools/check_test_delay_sync.py`) still passes (no delay-sync change expected)
- [ ] `git diff main --stat` — confirmed limited to `CycleArchiveServiceTests.cs`
- [ ] NFR-021 / callsign scan — clean (no callsigns in this file)
- [ ] Commit message states the structural argument (substring collision with `HH`), not "N green runs"

🛑 **No `src/` change authorised or needed.** No push, no merge, no `pre_merge_check.py` run by the
Developer session (HK-010/HK-014/HK-006) — stop after the fix and hand back for QA review/merge ruling.

---

## Status box detail — CI rerun after the window closed

`gh run rerun 34525161840 --failed`, triggered 2026-09-11 ~13:4xZ (safe hour, outside 20-23Z): result
recorded by QA once complete, see the accompanying BOARD.md entry for the outcome and whether PR #152
itself is otherwise clear to merge.
