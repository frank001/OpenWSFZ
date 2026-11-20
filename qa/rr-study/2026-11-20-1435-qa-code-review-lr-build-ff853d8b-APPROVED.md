# HK-039 code review: LR-BUILD, X1 and X2 as product settings, `ff853d8b` (QA, 2026-11-20 14:35Z `date -u`)

Reviewed-commit: ff853d8bf7d3be23a6d8df74a91a6a2099cf77ab
Verdict: APPROVED

Developer branch `feat/lr-full`, one commit off `66b3ddf1`; 23 files, +1438/-20; `src/` 8 files; `native/` diff empty (verified). Counts only; no message text. Review done on QA's own clean detached worktree `D:\Projects\claude\_qa-scratch\qa-lrbuild-review\ff853d8b` (HEAD verified `ff853d8b…`).

## 1. Test runs (reproduced, per project; HK-022)
`dotnet test OpenWSFZ.slnx -c Release -m:1` printed ONLY restore lines and exit 0: it ran no tests, so it is NOT counted. Each project was run alone: `dotnet test tests/<Project> -c Release` (no filter):
Audio 40, Config 206, Daemon 985, Ft8 849 (4 m 16 s), Web 452, E2E 9, Rig 41, TestSupport 12, TraceabilityCheck 34, LicenseInventoryCheck 24: all passed, 0 failed, 0 skipped, equal to the Developer's counts.
`openspec validate --all --strict`: 84/84. `check_version_bump.py origin/main`: OK (User-facing = no).

## 2. Read line by line (OFF paths)
Both defaults false; ctor parameters appended; setters wired at start and on every save in `Program.cs`. OFF: `x1On`, `x2On`, `provOn` false; the lists and dictionaries are allocated only when ON; `captureCohSnapshot: x2On` is false (base passed the default); `MapNative` adds one null test per mapped row; the three consumers go through the helper with the same result for Path 0-3. No new log text OFF. The "X1 on, v2 off" line is once per process. UDP untouched (D7a). Scope fence: kept, except `README.md` (version line 0.72 to 0.73, one line; harmless, noted).

## 3. Mutation pass (filter `FullyQualifiedName~LrFull`, Daemon and Ft8 projects, one mutant at a time, source restored after each)
KILLED: helper without Path 5; helper without Path 4; PSK engine without `continue` after LateProvenance; answerer and caller back to `PathTemplate` only; X1 gate always dropping; X1 without the Path 4 tag; per-row override ignored; X2 budget check removed; X2 admission off (`Merge(..., false)`); X2 rows not appended to batch 5; abandoned run not published; `PathLateFallback` 5 to 6; X2 rows left at Path 1; snapshot always captured; no-snapshot skip not counted; provenance line while both OFF-gated condition widened; `x2Admitted` not counted.
SURVIVED: (a) X2's `seen.Contains` check removed: EQUIVALENT (`MapNative` de-duplicates against `seen` itself). (b) `_lateRoundDecodes` incremented by `batch5.Count` instead of `primaryCount`: no test asserts that L1' counter keeps its meaning while X2 rows share batch 5.
Not mutated (read only): the in-exchange keep branches (covered by `Answerer_WaitReport_KeepsTheRow`, one case per path value; the caller's in-exchange case is not separately tested).

## 4. Minor notes (none blocks approval)
1. Add one assertion that `LateRoundDecodes` (the L1' counter) excludes X2 rows (mutant b).
2. The OFF-identity goldens cannot compile against the base (they use the new setters), so identity against `66b3ddf1` rests on the Developer's recording on a pristine base plus QA's V-OFF replay (next step, authoritative).
3. `check_version_bump.py` says no bump is required while VERSION went to 0.73; harmless, the Architect's call.

## 5. Next (not started)
V-OFF (20 cycles against the base), V-EQ (first 200 TEST cycles of night 2 against `80bbd74b` diag ON), V-LIMITS (own routes, not UDP), PC TIMING, then `pre_merge_check.py` BEFORE any push. `dotnet build-server shutdown` was run before this review.
