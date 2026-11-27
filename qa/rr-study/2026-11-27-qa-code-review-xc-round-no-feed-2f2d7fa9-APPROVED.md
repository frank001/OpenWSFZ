# QA code review (HK-039): XC-ROUND without the prior-store feed (follow-up to 65bca805)

**Reviewed commit:** `2f2d7fa9fb3c37a1c3001be69824b87446edc3fb` (`feat/xc-round`, one commit on `65bca8056887294f5cce64fef242f0a6dd3a472c`, not pushed)
**Reviewed-commit:** 2f2d7fa9fb3c37a1c3001be69824b87446edc3fb
**Verdict:** APPROVED, no required changes
**Reviewer:** QA, 2026-11-27. Read: the whole diff (`Ft8Decoder.cs`, `REQUIREMENTS.md` by word diff, the OpenSpec delta and tasks, `LeanEngineXcRoundManagedTests.cs`) against `dev-tasks/2026-11-27-xc-round-no-prior-store-feed.md` and the Captain's decision (option 2, 2026-11-27).

## Tests and checks QA ran (clean worktree at the commit, Release, whole projects, no `--filter`, HK-022)

- OpenWSFZ.Config.Tests **Passed: 237**, OpenWSFZ.Web.Tests **Passed: 464**, OpenWSFZ.Daemon.Tests **Passed: 963**; `DOTNET_PROCESSOR_COUNT=4`, OpenWSFZ.Ft8.Tests (6 m 34 s) **Passed: 928** (unchanged: the follow-up flips one test and adds no test); JavaScript **131 / 131**. All equal the Developer's figures.
- `libft8.dll` SHA256 `fa0b96c1c8a220b363db80977c0f741b6b7898a89bce3b98fe56e51691442504`: unchanged from the reviewed `65bca805`; `git diff 65bca805 2f2d7fa9 -- src/OpenWSFZ.Ft8/Native` is empty. **From the Developer's report, not re-run:** `check_version_bump.py` (no bump), `check_version_docs.py`, `openspec validate lean-decoder --strict`, G3 (QA runs G3 in `pre_merge_check` at the sprint PR).

## What was checked and found sound

- **The code change is the two lines asked for:** batch 4 is mapped with `xcBatch: 0` (the value that means "never stored in the prior store: no chaining", `Ft8Decoder.cs` mapping, as batch 3), and the comment above it says so. Nothing else about batch 4 changed (the same mapping, text de-duplication, delivered only when non-empty and after batch 3). No native file is touched.
- **The wording is in step everywhere:** the code comment, `REQUIREMENTS.md` FR-108 ("the priors SHALL be recorded from batches 1 and 2 only"; batch 4 "NOT stored in the prior store (no chaining, as batch 3)"), changelog row 1.80 added and row 1.79 no longer contradicts it, the OpenSpec delta (with a new scenario "A batch-4 decode is not stored") and tasks 14.5. QA read the word diff of `REQUIREMENTS.md`: only those fragments changed.
- **The test is a real test of the property:** the store count after the cycle with a detection is now 3 (M and Other from cycle 1, Other2 from cycle 2; neither the batch-3 M nor the batch-4 Fresh), and a third cycle 30 s later with Fresh's signal in its audio shows no batch 3, no Fresh row, no second round call, and `priorsLive=3` in the stage's log line, so Fresh is not a template. It fails if batch 4 is stored (the count would be 4 and the stage would find Fresh). No delays; synthetic `Q`-prefix content only.

## Minor notes (none blocks)

1. **No replay of the shipped build was run** (the Captain accepted the Architect's arithmetic: rate about -0.06 / -0.09 / -0.19 pp, `ours_only` about 0 / -0.15 / -0.29 pp against the measured run, section 10 of `xc-round-result.md`). The process-wide callsign hash table still learns from batch 4, so a hashed-call text can still resolve differently in a later cycle (the one batch-2 swap seen on H20); this is outside the prior store and not changed by this commit.
2. The earlier review's minor notes on `65bca805` stand unchanged (the native duplicate rule sees only the call's own results; dangling `else` without braces; tone above 7 reported as `FTZ_ERR_NOMEM`; a pinned probe handle can leak on an exception).

## Next (QA)

Merge `origin/main` into `qa/sprint-xc-round`, take `feat/xc-round` (`2f2d7fa9`), run `pre_merge_check` once from a clean checkout, then ask the Captain for the push go (one sprint PR).
