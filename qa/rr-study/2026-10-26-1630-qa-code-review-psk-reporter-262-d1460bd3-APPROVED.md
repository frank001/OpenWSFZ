# QA code review (HK-039): #262 PSK Reporter follow-up round, Developer `d1460bd3`

Reviewed-commit: d1460bd374386796e32d70eaed804bdc464cc75c
Verdict: APPROVED (no required changes; five advisories below). Next gate: `pre_merge_check.py` on a clean checkout of this exact commit (HK-006).

**Date:** 2026-10-26 16:29Z (`date -u`). **Branch:** `feat/psk-reporter-262` (`b3458c68` openspec refresh, `d1460bd3` code), on top of the approved `6ef0b33b`. **Spec:** OpenSpec `psk-reporter-upload` as amended by `1af1f5a6`; Architect A2.3 F-a to F-e.

## What QA did

1. Read the whole `src/` diff `6ef0b33b..d1460bd3` (engine, locator rules, endpoint, DTO, config, wiring, overlay validation). `git diff --stat origin/main -- native` is empty (Developer's statement; QA's `pre_merge_check` repeats it).
2. Clean detached worktree at exactly `d1460bd3` (`D:\Projects\claude\_qa-scratch\psk-fu-review`).
3. Ran `dotnet test tests/OpenWSFZ.Daemon.Tests --filter "FullyQualifiedName~PskReporter"`: **99 passed, 0 failed** (a filtered run: it covers the PSK Reporter classes only, NOT the full suite; the full unfiltered suite is the Developer's report, re-run by `pre_merge_check`).
4. Mutation set, each applied alone to the clean tree, same filter, project in the table, then reverted:

| # | Mutation | Result |
|---|---|---|
| M1 | window counters not reset at window close | KILLED (Daemon, 2 fail) |
| M2 | locator used without the `tx.grid` match | KILLED (Daemon, 2 fail) |
| M3 | locator sent as typed, not normalised | KILLED (Daemon, 1 fail) |
| M4 | server 400 for an invalid locator removed | KILLED (Web, 4 fail) |
| M5 | status reason always `region` | KILLED (Daemon, 1 fail) |
| M6 | accounting line only when records are pending (silent empty window) | KILLED (Daemon, 10 fail) |

Not mutated by QA: the status endpoint reading its own counters (the Developer's design makes it structurally impossible: `GetStatus` reads the `_window`/`_lastWindow` objects the log line uses); the box position (checked by the Developer's Playwright, 40 checks, which QA has not re-run: `pre_merge_check` runs the Web suite, and QA will run the Playwright script once if the Captain wants the screenshot).

## Findings

None required. Advisories (A), none blocking:

- **A-1.** The window line has no `unparseable` figure (the Developer's choice 1): correct per the spec wording (decision 15 lists six reasons), but `seen` is then not the sum of `reported` and the six reasons. A reader doing that sum will be puzzled. Acceptable; say so in the Captain's note.
- **A-2.** The locator Warning is skipped under a placeholder identity (choice 2): agreed, nothing is uploaded then.
- **A-3.** The first window of an enabled period is the 0 to 60 s offset window, so its line is short (choice 3): expected, matches R-1's design.
- **A-4.** Status `refused` is judged over the window in progress plus the last closed one. Reasonable (a fresh window with 0 decodes does not flip the page back to waiting); it does mean the page can say "refused" for up to one window after the cause is fixed. Acceptable.
- **A-5.** `MatchesGrid` compares the first 4 characters of both sides, so a 6-character `tx.grid` still matches on its square (choice 5). Fine.

Process notes: tasks.md left unticked as QA's (correct). The Developer dropped the `qa/rr-study/` copy of the new fixture in favour of the test project's own `Fixtures/` copy; byte equality with QA's `t1_receiver_locator6.hex` is asserted by T19 and rechecked by `pre_merge_check` G3/the suite.

## Not done by this review (named, so no one reads more into it)

Full unfiltered suite, Playwright, G3/G9/G10, WSL build and publish: **not run here**; they are `pre_merge_check.py`'s job. No live run: HK-039 is satisfied by this record, and no acceptance run is planned before the Captain's push go. NFR-021: no callsign in any new log line or in the endpoint body by inspection; the tests use Q-prefix calls.
