# QA review — dev-task 1b: fix + oracle patch independently verified, accepted

**Author:** QA, 2026-07-31 (10:13 UTC, `date -u`). Repo at `41b22bc`.
**Reviews:** `2026-07-31-1001-dev-task-1b-oracle-frozen-clock-gap-and-proposed-fix.md`.
**Verdict:** Accepted. Both the developer's frozen-clock finding and the proposed oracle patch
are correct — verified independently in this session, not taken on the write-up's word. One
correction to my own dev-task is owned below (§3). One minor residual observation is recorded
(§4), non-blocking.
**Status:** `src/` diff not yet pushed. Per HK-011 it needs the Captain's explicit sign-off
before that happens — nothing has been actioned beyond this review.

## 1. Independent verification of the frozen-clock claim

Confirmed by direct inspection: the oracle as I originally committed constructs `FakeClock` once
and never calls `.Advance()` in either test body. Since the *pre-fix* `CycleFramer` never
re-reads `_clock.UtcNow` after start-up anyway, this went unnoticed when I confirmed the oracle
red in `0925` — the frozen clock was irrelevant to demonstrating that bug. It only becomes a
problem once the fix under test actually depends on `_clock.UtcNow` reflecting elapsed real
time, which is exactly the case for any wall-clock-resync fix. This is a legitimate gap in the
oracle as I wrote it, not a misreading on the Developer's part.

## 2. Independent verification of the fix + patched oracle

Ran myself, not inferred from the write-up's tables:

| check | result |
|---|---|
| Full `OpenWSFZ.Ft8.Tests` against working tree (fix + patched oracle) | **301/301 PASS** |
| Patched oracle run against `src/CycleFramer.cs` reverted to unfixed (`git stash`) | **Both FAIL**, drift 4.1747517s / 2.0s — identical to the pre-patch oracle's numbers. Confirms the harness change did not launder the regression test; it still catches the original defect precisely |
| Fix restored, patched oracle re-run | **2/2 PASS** |
| `OpenWSFZ.Daemon.Tests` (spot check, CycleFramer is a consumer) | 600/601 — the one failure is `CycleArchiveServiceTests.Manifest_WritesOneRowPerArchivedCycle_InOrder`, the **pre-existing full-suite-load flake already on record** (memory: `flaky-cyclearchiveservice-manifest-test-todo.md`, 2026-07-28). Re-ran solo: **1/1 PASS**, matching that flake's documented signature exactly. Not a regression from this change |

The middle row is the one that matters most: it is the check that the oracle patch didn't
accidentally turn the regression test into something that would pass *any* fix regardless of
correctness. It doesn't — reverting only the `src/` fix reproduces the original failure exactly,
confirming the patched oracle is still discriminating on the actual defect.

## 3. My own dev-task's literal instruction was wrong — owned, not glossed over

Dev-task 1b's "What to build" told the Developer to *"re-anchor `cycleStart` to the nearest true
15-second UTC boundary."* The Developer deviated from that (raw `_clock.UtcNow`, no flooring)
and flagged the deviation prominently rather than silently overriding my spec. I tested my own
instruction directly rather than taking their word that it wouldn't have worked:

Patched `CycleFramer.cs` to floor via the existing `AlignToCycleStart` at the resync point
(`cycleStart = AlignToCycleStart(_clock.UtcNow);` in place of the raw assignment) and re-ran the
oracle. **Result: still fails, 4.1742017s / 2.0s — no material improvement over the unfixed
code.**

The reason is arithmetic, not a close call: 48.4 ppm over 24h accumulates only ~4.17s of drift,
which never crosses a full 15-second grid line. Flooring the true clock reading to the nearest
15s-of-minute boundary therefore returns the **same grid line every time** as the broken
arithmetic accumulation — the sub-15s residual this defect is entirely made of is exactly what
flooring throws away. Only a raw, unfloored timestamp — absorbing the residual in the gap
between consecutive `CycleStart` values rather than snapping it to a grid — actually corrects
it. The dropped-chunk case would only be correctly recoverable by flooring if the drop happened
to be large enough to cross a grid line by coincidence, which is not a property a fix should
depend on.

**Correction for the record:** dev-task 1b's "What to build" section is superseded on this
point. The shipped fix (raw `_clock.UtcNow`, residual absorbed in the timestamp, buffer size
untouched) is correct; my "re-anchor to the nearest 15-second boundary" instruction was not.

## 4. Residual observation — not a blocker

Neither the pre-existing 12 tests nor the oracle exercises a single incoming `chunk` spanning
**more than one complete window** (all use chunk sizes well under `SamplesPerCycle`, matching
`WasapiAudioSource`'s real buffer granularity). In that untested case, `needsResync` would fire
more than once inside the same synchronous `while` pass with no intervening wall-clock movement,
so several completed windows from one oversized chunk would be stamped with (near-)identical
`CycleStart` values rather than ~15s apart. Given real capture buffers are far smaller than
180,000 samples, I judge this low-likelihood and **not a blocker for this fix** — but it's
untested either before or after the change, so it's recorded here rather than silently assumed
fine. Candidate for a follow-up hardening test if it's ever worth the effort; not raising it as
a task on its own.

## 5. Disposition

- Oracle patch (§3 of the `1001` write-up) — **adopted as canonical.** I will commit
  `CycleFramerClockDriftOracleTests.cs` in its current (patched) form.
- `src/CycleFramer.cs` fix — **accepted on review.** Correct, minimal, doesn't over-engineer
  (no PLL/rate-estimation, as the handoff cautioned against), comment cites the defect, buffer
  handling explicitly documented rather than left implicit.
- Dev-task 1b document — **addendum needed** to correct §"What to build"'s flooring instruction
  per §3 above, so a future reader doesn't reintroduce it.
- Per **HK-011**: the `src/` diff still needs the **Captain's explicit sign-off before push** —
  not requested or assumed here.
- Per **HK-006**: `pre_merge_check.py` has not been run, and won't be unless the Captain asks
  for it at the point of merge.
