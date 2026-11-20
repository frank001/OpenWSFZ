# HK-039 code review: LR-BUILD follow-up, test-only commit `c23aa7e9` (QA, 2026-11-20)

Reviewed-commit: c23aa7e92d38f946d85c36c507ac5be4497026f4
Verdict: APPROVED

Developer branch `feat/lr-full`, one commit on top of the approved `ff853d8b` (`2026-11-20-1435-qa-code-review-lr-build-ff853d8b-APPROVED.md`). It answers QA's minor note 1 (the late round's decode counter excluding X2's rows). Counts only; no message text.

- `git diff --stat ff853d8b c23aa7e9`: 1 file, `tests/OpenWSFZ.Ft8.Tests/LrFullTests.cs`, +7/-2. `git diff --stat ff853d8b c23aa7e9 -- src native`: empty, so the `src/` and `native/` trees are byte-identical to the approved commit.
- Change: `X2_LateRoundLine_Unchanged_ByX2` now compares `GetLateRoundCounters()` with X2 ON against X2 OFF and asserts `Decodes == 1` (the primary row only).
- QA's own run, clean detached worktree `_qa-scratch\qa-lrbuild-review\ff853d8b` at `c23aa7e9` (HEAD verified), `dotnet test tests/OpenWSFZ.Ft8.Tests -c Release --filter "FullyQualifiedName~LrFull"`: 27 of 27 passed.
- Mutant M18 (`_lateRoundDecodes` incremented by `batch5.Count` instead of `primaryCount`), same filter: now KILLED (1 failed, 26 passed). It survived at `ff853d8b`.

The full-suite counts of the approval of `ff853d8b` stand (src unchanged). Next steps as before: V-OFF, V-EQ, V-LIMITS, PC TIMING, `pre_merge_check.py` before any push, each with the Captain's go. Nothing pushed.
