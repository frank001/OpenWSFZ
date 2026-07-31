# Dev-task — fix `CycleFramer` clock-drift / dropped-chunk boundary desync

**Author:** QA, 2026-07-31 (09:25 UTC, `date -u`). Repo at `41b22bc`.
**For:** a separate Developer-persona session (HK-011 — this is `src/` implementation and must
not run in the QA session that authored the oracle).
**Origin:** dev-task 1b of
`qa/cycleframer-alignment-replay/2026-07-31-0910-architect-to-qa-consolidated-handoff-post-measurements-abc.md`
§3 task 1, itself downstream of `DEFECT-capture-clock-drift-silent-decode-loss.md` and the
`2026-07-31-0029` ruling's §2 (root cause established in code).

**Gate — already satisfied, do not re-derive:** dev-task 1a (the oracle) is committed at
`tests/OpenWSFZ.Ft8.Tests/CycleFramerClockDriftOracleTests.cs` and is confirmed **red against
current `main`**:

- `RunAsync_24hAt48ppmSlowClock_BoundaryDriftsWellBeyondTolerance` — measured drift **4.17 s**
  against a 0.2 s tolerance, simulating the measured 48.4 ppm slow capture-device crystal
  (11 999.42 Hz effective) over a 24 h session.
- `RunAsync_DroppedChunkMidStream_PermanentlyShiftsAllSubsequentBoundaries` — measured drift
  **exactly 2.0 s**, permanently, after a single simulated dropped chunk, independent of any
  clock-rate error.

All 12 pre-existing `CycleFramerTests.cs` cases still pass unchanged. **Your task is to make
both new oracle tests go green without regressing any of the 12 existing ones.** Do not edit
the oracle tests to make them pass — if you believe an oracle assertion or tolerance is wrong,
stop and raise it with QA rather than loosening it.

## The defect, in the code

`src/OpenWSFZ.Ft8/CycleFramer.cs`, `RunAsync` (lines ~69-148):

```csharp
var startUtc = _clock.UtcNow;                       // read ONCE
...
DateTime cycleStart = AlignToCycleStart(startUtc);  // set ONCE
...
// inside the emission block, once per completed window:
cycleStart = cycleStart.AddSeconds(CycleDurationSecs);  // pure arithmetic, never re-reads _clock
```

`_clock.UtcNow` is never consulted again after start-up. The framer's only notion of elapsed
time thereafter is the count of samples it has been handed, on the assumption that samples
arrive at exactly 12 000 Hz with none lost. Two independent field conditions defeat that:

1. **Crystal rate error.** The affected capture device runs at 48.4 ppm slow (measured). Over
   any long session this accumulates without bound — the framer has no way to notice.
2. **Dropped samples.** `WasapiAudioSource`'s buffer-overrun branch and its channel-write-failure
   branch are both **warn-only** (do not fix those branches as part of this task unless a
   dropped-chunk case specifically requires it — the framer-side fix should make the boundary
   self-correcting regardless of *why* samples were lost upstream). A single dropped chunk
   permanently shifts every subsequent window boundary, with no recovery, because the framer's
   arithmetic has no way to detect the gap.

**This is a framer design defect, not only a hardware-clock defect** — do not aim the fix at
rate compensation alone (see below).

## What to build

> **Addendum, QA, 2026-07-31 11:13 UTC — the flooring instruction below is wrong; corrected in
> `qa/cycleframer-alignment-replay/2026-07-31-1013-qa-review-dev-task-1b-verified-and-accepted.md`
> §3. Left in place, struck through in spirit, so a future reader sees what was tried and
> rejected rather than a silently-edited history. Do not re-anchor to the 15-second grid — use
> the raw `_clock.UtcNow` reading and absorb the residual in the timestamp gap between
> consecutive `CycleStart` values instead. Verified empirically: flooring to the grid gives
> ~4.17s drift over 24h at 48.4 ppm, materially indistinguishable from the unfixed code, because
> that much drift never crosses a full 15-second grid line for flooring to correct.**

**Re-derive each window boundary from the wall clock rather than accumulated sample count,
absorbing the residual per cycle.** Concretely: on every completed window (i.e., wherever
`cycleStart = cycleStart.AddSeconds(CycleDurationSecs)` currently happens by pure arithmetic),
re-read `_clock.UtcNow` and ~~re-anchor `cycleStart` to the nearest true 15-second UTC boundary
(the same alignment `AlignToCycleStart`/`ComputeLeadingSamples` already compute at start-up)~~
— **superseded, see addendum above: use the raw reading, do not floor** — rather than trusting
the running total.

Constraints on the fix:

- **Resync every cycle.** The acceptance tolerance is 0.2 s (an order of magnitude inside the
  measured 2.34–2.48 s DT cliff). At 48 ppm, per-cycle resync gives roughly three orders of
  magnitude of margin against that cliff — this is not a guess, it's derived, and it means
  **per-cycle resync is trivially sufficient.**
- **Do not over-engineer.** Rate estimation, adaptive resampling, or a PLL are not warranted.
  Treat any such design as scope creep unless the simple per-cycle resync is *measured* to fail
  against the oracle — it should not be, given the margin above.
- **Handle the leading-window case correctly** — `ComputeLeadingSamples`/`AlignToCycleStart`
  behaviour for the first window must be preserved; the 12 existing tests cover this and must
  stay green.
- **A window's samples may now span a slightly different real-time interval than exactly
  15.000 s** (that's the whole point — the source doesn't actually run at exactly 12 000 Hz).
  Decide, and document in a code comment, what happens to the sample buffer itself when the
  wall-clock-derived boundary doesn't land exactly on a 180 000-sample count (e.g., a small
  per-cycle over/under-fill). This is a design decision the fix must make explicitly, not one to
  paper over silently.

## Boundaries (do not deviate)

- Per **HK-011**: this is `src/` implementation. Run local build/tests only. **Show the diff to
  the Captain for sign-off before `git push`** — not just before merge.
- Per **HK-006**: **do not** put `python3 tools/pre_merge_check.py` anywhere in this task's
  checklist or run it yourself. It runs only on the Captain's explicit trigger, at merge time.
- Per **HK-010**: merge to `main` needs the Captain's explicit sign-off regardless of green CI.
- Do not touch `WasapiAudioSource`'s warn-only branches as part of this task — out of scope
  unless you find the oracle's dropped-chunk case cannot be satisfied without it, in which case
  stop and raise it rather than expanding scope unilaterally.
- Do not edit `CycleFramerClockDriftOracleTests.cs` to relax tolerances or assertions.

## Task list

1. [ ] Read `CycleFramer.cs` in full and `CycleFramerClockDriftOracleTests.cs` in full before
       writing any code.
2. [ ] Implement per-cycle wall-clock resync in `RunAsync`, per "What to build" above.
3. [ ] Run the full `OpenWSFZ.Ft8.Tests` project. All 12 pre-existing `CycleFramerTests.cs`
       cases and both new oracle cases must be green.
4. [ ] Run the full solution test suite (not just `Ft8.Tests`) to check for regressions
       elsewhere the change might touch (e.g. anything consuming `CycleStart` downstream).
5. [ ] Add a short code comment at the resync point explaining why (cite
       `DEFECT-capture-clock-drift-silent-decode-loss.md`) so a future reader doesn't mistake
       the resync for redundant/dead code.
6. [ ] Stop. Present the diff to the Captain for sign-off before pushing. Do not run
       `pre_merge_check.py`.

## Traceability

- `DEFECT-capture-clock-drift-silent-decode-loss.md` — the Critical defect this closes.
- `qa/cycleframer-alignment-replay/2026-07-31-0029-architect-ruling-measurements-abc-and-drift-root-cause.md`
  §2 — root cause established in code.
- `qa/cycleframer-alignment-replay/2026-07-31-0910-architect-to-qa-consolidated-handoff-post-measurements-abc.md`
  §3 task 1, §4.3 — the pitfalls (three prior live-test rounds burned on this exact defect
  without an oracle; do not repeat that).
- `tests/OpenWSFZ.Ft8.Tests/CycleFramerClockDriftOracleTests.cs` — the oracle this task must
  satisfy.
