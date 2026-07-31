# Dev-task — align `windowDialFreq` snapshot timing with the lazy `cycleStart` resync

**Author:** QA, 2026-07-31 (13:03 UTC, `date -u`). Branch `fix-cycleframer-clock-drift-boundary-resync` at `5a90d85`.
**For:** a separate Developer-persona session (HK-011 — this touches `src/`, and per this
session's own precedent that fix must not be written and reviewed by the same session).
**Origin:** found during QA's structured code review of the `CycleFramer.cs` drift fix, prior
to push sign-off — not part of the original defect, a second-order consequence of that fix's
own design. Reported to the Captain, who asked for this dev-task.

## The finding

The drift fix (dev-task `2026-07-31-fix-cycleframer-clock-drift-boundary-resync.md`) made
`cycleStart` **lazy**: it is now re-derived from `_clock.UtcNow` at the instant the *next*
window starts accumulating its first sample, not eagerly at the previous window's close. That
is deliberate and correct — it's what makes the fix cover the dropped-chunk case, not just the
slow-crystal case.

`windowDialFreq` was not moved along with it. It is still captured **eagerly**, synchronously,
in the same code block that sets `needsResync = true`, immediately after the just-completed
window is emitted:

```csharp
// src/OpenWSFZ.Ft8/CycleFramer.cs, inside `if (filled == SamplesPerCycle)`:
output.TryWrite((window, cycleStart, windowDialFreq));
...
window         = new float[SamplesPerCycle];
filled         = 0;
windowDialFreq = _dialFreqProvider?.Invoke();   // <-- eager: fires at window-CLOSE
needsResync    = true;                          // cycleStart is deferred to window-OPEN
```

Before the drift fix, this was harmless: `cycleStart` was also computed eagerly at that same
instant (pure arithmetic), so "window-close" and "the next window's open" were the same moment
by construction. The drift fix broke that equivalence for `cycleStart` on purpose, but left
`windowDialFreq` behind.

**Consequence:** whenever a real gap opens up between window-close and the next window's true
open (exactly the dropped-chunk scenario this fix exists to handle), `cycleStart` correctly
reflects the post-gap time, but `windowDialFreq` reflects whatever the provider returned at the
pre-gap instant. If the operator changes bands during that gap, the emitted window carries a
`CycleStart` for after the change but a `DialFrequencyMHz` from before it — the two pieces of
metadata for the same window are no longer necessarily describing the same instant.

**Severity — bounded, not silent corruption.** The existing downstream check (documented on
`CycleFramer`'s own class summary) already discards a cycle when the decode pump finds this
snapshot disagrees with the live frequency at decode time. The worst outcome of this gap is an
extra cycle or two getting conservatively discarded around a drop-plus-band-change coincidence,
not a mislabeled one. This is why it is a follow-up dev-task and not a reason to hold the
original fix. It is still a real inconsistency worth closing, given this defect's whole history
is exactly this class of rare-and-quiet problem.

## What to build

**Move the `windowDialFreq` snapshot into the same lazy resync point as `cycleStart`**, so both
are captured at the identical instant — when the window actually begins accumulating its first
real sample, not when the previous one closed:

```csharp
if (needsResync)
{
    cycleStart     = _clock.UtcNow;
    windowDialFreq = _dialFreqProvider?.Invoke();
    needsResync    = false;
}
```

...and remove the now-redundant eager assignment from the emission block, leaving only:

```csharp
window      = new float[SamplesPerCycle];
filled      = 0;
needsResync = true;
```

The very first window (index 0) is unaffected — its `windowDialFreq` is still the one-time
snapshot taken before the loop starts, exactly as today; `needsResync` starts `false` and this
change only touches what happens once it becomes `true`.

**Do not touch anything else.** This is a one-instant-later move of an existing snapshot call,
not a redesign. In particular:
- Do not change what "discard on mismatch" does downstream — this fix makes the snapshot more
  accurate, which should make that check fire *less* often, not change its behaviour.
- Do not add a time parameter to `_dialFreqProvider` or otherwise change its signature.

## Oracle — write this first, confirm it fails against the current branch

Add to `tests/OpenWSFZ.Ft8.Tests/CycleFramerClockDriftOracleTests.cs` (or a new file in the same
directory — QA's call) a test shaped like this, reusing the one-window-at-a-time feed/drain
pattern the existing drift-oracle tests already use:

1. `FakeClock`, standard setup, boundary-aligned start.
2. A dial-freq provider backed by a simple mutable flag the test controls directly (not a call
   counter like the existing FR-032 tests use — call count can't distinguish "eager at close"
   from "lazy at open" because there's no real gap in those tests for the two to diverge over).
3. Feed window 0's samples (one `SamplesPerCycle`-sized write), `await` its emission being read
   back off the output channel — this is the synchronization point: the framer cannot have
   done anything for window 1 that depends on an `await` past this point yet.
4. **After** draining window 0's emission, flip the mutable flag (this is the simulated
   "operator changed bands during the gap").
5. **Then** feed window 1's samples.
6. Drain window 1's emission and assert its `DialFrequencyMHz` equals the **post-flip** value.

Under the current branch (eager snapshot), this assertion should **fail**: the eager
`_dialFreqProvider?.Invoke()` for window 1 runs synchronously immediately after window 0's
`TryWrite`, with no intervening `await`, so it necessarily executes before the test's own code
gets to flip the flag in step 4 — window 1 ends up carrying the **pre-flip** value. Confirm this
red result before writing the fix; that confirmation is what makes the fix's regression
protection real rather than assumed.

## Boundaries

- Per **HK-011**: this is `src/` implementation. Separate Developer session. Show the diff to
  the Captain for sign-off **before push**, same as the original drift fix — and note both are
  currently unpushed on the same branch (`fix-cycleframer-clock-drift-boundary-resync`), so this
  can land as a second commit on that branch rather than a new one, subject to the Captain's
  preference.
- Per **HK-006**: do not add `pre_merge_check.py` to this task's checklist or run it. Captain's
  trigger only, at merge time.
- Run the full `OpenWSFZ.Ft8.Tests` project after the fix: all 12 original `CycleFramerTests.cs`
  cases (including the three existing FR-032 dial-freq tests), both existing drift-oracle
  cases, and the new oracle above must all be green. No regression expected, but confirm rather
  than assume — in particular re-check `RunAsync_FrequencyChangesAfterWindowOpen_SnapshotIsWindowOpenValue`,
  since it's the existing test closest in shape to what's changing here.
- Do not run the full solution suite unless the `Ft8.Tests` run raises something — this is a
  narrowly-scoped, single-method change with no plausible reach outside `CycleFramer`.

## Task list

1. [x] Read `CycleFramer.cs` (current branch state) and the three existing FR-032 tests in
       `CycleFramerTests.cs` before writing anything.
2. [x] Write the new oracle test per "Oracle" above. Confirm it fails against the current
       branch. Do not write the fix first. (New file
       `tests/OpenWSFZ.Ft8.Tests/CycleFramerDialFreqLazyResyncOracleTests.cs`; confirmed RED
       against pre-fix `CycleFramer.cs` — window 1 carried 14.074 instead of the expected
       post-flip 7.074.)
3. [x] Move the `windowDialFreq` snapshot into the `needsResync` block per "What to build".
4. [x] Run `OpenWSFZ.Ft8.Tests` in full. All cases green, including the new oracle and all
       three FR-032 tests. (302/302 passed.)
5. [x] Add a short comment at the moved snapshot line noting why it's here now and not in the
       emission block (cite this dev-task and the defect this closes), so a future reader
       doesn't move it back "for tidiness."
6. [x] Stop. Present the diff to the Captain for sign-off before push.

## Cross-references

- `dev-tasks/2026-07-31-fix-cycleframer-clock-drift-boundary-resync.md` — the original fix this
  is a follow-up to; the lazy-resync design this dev-task extends to `windowDialFreq`.
- `src/OpenWSFZ.Ft8/CycleFramer.cs` — class summary's existing documentation of the discard-on-
  mismatch downstream behaviour that bounds this finding's severity.
- `tests/OpenWSFZ.Ft8.Tests/CycleFramerTests.cs` — the three FR-032 dial-frequency tests
  (`RunAsync_NullProvider_EmitsNullDialFrequency`,
  `RunAsync_WithProvider_EmitsSuppliedDialFrequency`,
  `RunAsync_FrequencyChangesAfterWindowOpen_SnapshotIsWindowOpenValue`) that must stay green.
- `tests/OpenWSFZ.Ft8.Tests/CycleFramerClockDriftOracleTests.cs` — the existing drift-oracle
  file this dev-task's new test joins, and the one-window-at-a-time feed/drain pattern it reuses.
