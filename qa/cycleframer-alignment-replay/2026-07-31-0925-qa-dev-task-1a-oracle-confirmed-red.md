# QA — dev-task 1a (drift oracle) landed and confirmed red against `main`

**Author:** QA, 2026-07-31 (09:25 UTC, `date -u`). Repo at `41b22bc`.
**Responds to:** `2026-07-31-0910-architect-to-qa-consolidated-handoff-post-measurements-abc.md`
§3 task 1a.
**Status:** Task 1a done. Task 1b (the fix) handed to a separate Developer session as
`dev-tasks/2026-07-31-fix-cycleframer-clock-drift-boundary-resync.md`, per HK-011/HK-015 — no
`src/` change made in this session.

## What was built

`tests/OpenWSFZ.Ft8.Tests/CycleFramerClockDriftOracleTests.cs`, two cases, both test-only
(`FakeClock` + in-memory `Channel`, no real audio/radio/live session):

1. **`RunAsync_24hAt48ppmSlowClock_BoundaryDriftsWellBeyondTolerance`** — drives `CycleFramer`
   from a synthetic source at the measured effective rate (11 999.42 Hz, i.e. 48.4 ppm slow),
   simulates a 24 h session by total sample count (no `Task.Delay`), and asserts the emitted
   `CycleStart` for the final complete window stays within 0.2 s of the true UTC time computed
   from first principles (`k × 180 000 / effectiveHz` seconds after start).
2. **`RunAsync_DroppedChunkMidStream_PermanentlyShiftsAllSubsequentBoundaries`** — three clean
   windows at nominal rate, then a simulated dropped chunk (24 000 samples / 2 true-UTC seconds
   that never reach the channel), then three more clean windows. Asserts each post-drop window
   recovers to within 0.2 s of true UTC.

Tolerance (0.2 s) is the value derived in the handoff §3, not a guess: the DT cliff is bracketed
at 2.34–2.48 s and 0.2 s is an order of magnitude inside it.

## Result

Both go red, as required before any fix is written:

| case | measured drift | tolerance | result |
|---|---|---|---|
| 24 h @ 48.4 ppm | **4.1747517 s** | 0.2 s | FAIL (as expected) |
| dropped chunk (post-drop window 1) | **2.0000000 s** | 0.2 s | FAIL (as expected) |

Both figures match hand-derived expectations from first principles almost exactly (24 h case:
predicted ≈4.17 s from `k × (15 − 180000/11999.42)` at the last window index; dropped-chunk
case: predicted exactly 2.0 s, the dropped duration). Nothing was tuned to hit these numbers —
the test computes its own ground truth rather than hard-coding an expected drift value.

All 12 pre-existing `CycleFramerTests.cs` cases still pass unchanged (14 total, 12 pass / 2 fail
as designed). Full run: `dotnet test tests/OpenWSFZ.Ft8.Tests/OpenWSFZ.Ft8.Tests.csproj --filter
"FullyQualifiedName~CycleFramer"` — 2 s wall time.

## Boundary check

Per HK-011, whether this task itself required a separate Developer session was checked before
starting, not assumed: 1a is test-only, lives under `tests/`, and makes zero change to `src/`
behaviour — HK-011 exists to stop one session writing a fix *and* reviewing it, which a failing
regression test does not create. Confirmed with the Captain before proceeding. 1b (re-deriving
the boundary from the wall clock in `CycleFramer.cs`) does touch `src/` and has been routed to a
separate Developer session as required.

## Next

- Task 1b: `dev-tasks/2026-07-31-fix-cycleframer-clock-drift-boundary-resync.md`, ready for a
  Developer-persona session. Gate (1a red) already satisfied — do not re-derive it.
- Once 1b lands, both oracle cases above must go green with no regression to the 12 existing
  `CycleFramerTests.cs` cases, and the diff needs the Captain's sign-off before push (HK-011).
- Tasks 2 (Measurement D), 3 (Measurement A escalation) and 4 (489135a recompute) remain queued
  per the handoff's priority order — none of them wait on this.
