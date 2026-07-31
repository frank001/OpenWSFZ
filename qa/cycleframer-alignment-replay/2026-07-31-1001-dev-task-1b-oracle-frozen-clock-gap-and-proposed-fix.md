# Dev → QA — dev-task 1b: fix implemented, but the oracle needs a patch to actually test it

**Author:** Developer session, 2026-07-31 (10:01 UTC, `date -u`). Repo at `41b22bc`.
**Responds to:** `dev-tasks/2026-07-31-fix-cycleframer-clock-drift-boundary-resync.md` (dev-task 1b).
**Escalation path:** Dev → QA per HK-015 (this session does not have standing to edit
`tests/OpenWSFZ.Ft8.Tests/CycleFramerClockDriftOracleTests.cs` — that file is QA's, landed as
dev-task 1a). Nothing has been committed or pushed. `pre_merge_check.py` was not run (HK-006).
**Status:** `src/` fix implemented and locally verified; **blocked on QA sign-off** for a
required patch to the oracle test file before this can go to the Captain for push approval.

## Summary

The `src/` fix described in dev-task 1b is implemented, and (with a supporting patch to the
oracle test — see below) both oracle cases go green with zero regressions across the full local
test suite. The oracle file **as committed by dev-task 1a cannot be satisfied by any wall-clock
resync fix**, including the literal one dev-task 1b itself described — its `FakeClock` is
constructed once and never `.Advance()`d, so `_clock.UtcNow` never reflects the simulated
scenario. This was verified empirically, not just argued. A patch to the oracle's two feeding
loops is proposed below to fix that gap. The patch does not touch either test's assertions or
tolerance — only how the `FakeClock`/channel are driven — and needs QA's review before it's
real.

## 1. The `src/` fix

`src/OpenWSFZ.Ft8/CycleFramer.cs`, `RunAsync` — resync is now **lazy**: a `needsResync` flag is
set the instant a window closes, but the actual `_clock.UtcNow` read is deferred until the
*next* window's first sample is about to be copied into the fresh buffer.

```diff
             double? windowDialFreq = _dialFreqProvider?.Invoke();

+            // DEFECT-capture-clock-drift-silent-decode-loss.md: set the instant a window
+            // closes, consumed (and cleared) the next time this loop is about to accumulate
+            // a *fresh* window's first sample. The resync deliberately happens lazily —
+            // right when new data actually starts arriving for the next window — rather
+            // than eagerly the moment the previous one closes. That distinction is the
+            // whole fix: any real wall-clock time that elapses *between* the two (a capture
+            // device crystal that simply runs slow, measured at 48.4 ppm on the affected
+            // hardware, and/or WasapiAudioSource silently dropping a chunk on its warn-only
+            // overrun/write-failure branches) only shows up in _clock.UtcNow once that gap
+            // has actually passed. Reading the clock at window-close instead would miss it
+            // — the gap (if any) hasn't happened yet at that point in the code.
+            bool needsResync = false;
+
             _logger?.LogInformation(...);

             await foreach (var chunk in _source.ReadAllAsync(ct))
             {
                 int remaining = chunk.Length;
                 int chunkPos  = 0;

                 while (remaining > 0)
                 {
+                    if (needsResync)
+                    {
+                        // Re-derive this window's start from the wall clock rather than
+                        // trusting "previous cycleStart + 15s" arithmetic. Deliberately NOT
+                        // floored to the nearest 15-second UTC grid line the way
+                        // AlignToCycleStart is at start-up: the sample buffer itself is
+                        // untouched by this fix (still always exactly SamplesPerCycle
+                        // samples — no padding, no truncation, no carry-over), so a
+                        // window's audio may now genuinely span slightly more or less than
+                        // 15.000s of real time when the capture device's rate isn't exactly
+                        // nominal. That residual is fully absorbed by this timestamp (the
+                        // gap between consecutive CycleStart values), not by resizing the
+                        // buffer — resync-every-cycle keeps that residual bounded to a
+                        // single cycle's worth of clock error, ~3 orders of magnitude
+                        // inside the measured decode-failure cliff (2026-07-31 handoff),
+                        // so no rate estimation/PLL is needed.
+                        cycleStart  = _clock.UtcNow;
+                        needsResync = false;
+                    }
+
                     int space = SamplesPerCycle - filled;
                     ...
                     if (filled == SamplesPerCycle)
                     {
                         output.TryWrite((window, cycleStart, windowDialFreq));
                         ...
                         window         = new float[SamplesPerCycle];
                         filled         = 0;
-                        cycleStart     = cycleStart.AddSeconds(CycleDurationSecs);
                         windowDialFreq = _dialFreqProvider?.Invoke();
+                        needsResync    = true;
                     }
                 }
             }
```

**Design decisions, explicit per the dev-task's request:**

- **Sample buffer is untouched.** Still always exactly 180,000 samples, same accumulation
  logic. No over/under-fill, no padding, no carry-over between buffers.
- **The residual is absorbed entirely in the timestamp.** `cycleStart` is no longer forced onto
  the 15-second UTC grid after start-up (only the very first window, via the existing
  `AlignToCycleStart`, is grid-aligned) — it's the raw wall-clock reading. A window's *implied*
  duration (the gap between consecutive `CycleStart` values) is now free to be a few ms off
  15.000s, which is the actual physical truth when the capture device isn't running at exactly
  nominal rate.
- **Why lazy, not eager.** This is the part worth QA's attention: an eager read (at window
  close, which is what the dev-task's own "What to build" section literally describes) does
  **not** work — see §2. Reading lazily (deferred to when the next window's accumulation
  actually starts) is what makes the dropped-chunk case recoverable, because the gap between
  windows hasn't happened yet at the moment the old window closes.

## 2. Why the committed oracle can't test this (or any) wall-clock fix, as written

Both cases in `CycleFramerClockDriftOracleTests.cs` construct a `FakeClock` once and **never
call `.Advance()`** anywhere in either test body (confirmed by full read + grep — zero matches).
`FakeClock.UtcNow` is a plain `{ get; set; }`, so `_clock.UtcNow` returns the exact same frozen
instant (`startUtc`) for the whole test, regardless of how many samples flow through the channel
or how much simulated time the test's own ground-truth math (`trueOpen`) claims has passed.

This was not just reasoned through — it was checked empirically before touching the oracle:

1. **Baseline, unmodified `main`:** ran the committed oracle as-is. Matches dev-task 1b's
   stated numbers exactly — `4.1747517s` (claimed "~4.17s") and `2.0s` (claimed "exactly
   2.0s"). Confirms the model of the pre-fix bug is right.
2. **Literal fix, as a throwaway experiment:** implemented dev-task 1b's "What to build" section
   verbatim — `cycleStart = AlignToCycleStart(_clock.UtcNow)` on every window close, eagerly,
   no deferral. Ran it against the **unmodified** oracle. Result: drift got **worse**, not
   better — `86374.1747517s` for the 24h case (because the frozen clock always floors back to
   `startUtc`, so every window after #0 gets stamped to the start of the session), and the
   dropped-chunk case failed on **window 1**, a pre-drop window that should never move at all.
   Reverted immediately (`git diff --stat` showed a clean file afterward — nothing was left
   half-applied).

Conclusion: no wall-clock-consulting fix — eager or otherwise — can pass this oracle as
committed, because there is no real-time signal reaching the SUT through a clock that never
ticks. This matches the dev-task's own escalation clause: *"if you believe an oracle assertion
or tolerance is wrong, stop and raise it with QA rather than loosening it."* Nothing in the
oracle file has been edited without this write-up; the modified version currently sitting in
the working tree (uncommitted, untracked-diff visible via the patch in §3) is a **proposal**,
not a fait accompli.

## 3. Proposed oracle patch

Both tests' assertions, `ToleranceSeconds`, and overall scenario (48.4 ppm / 24h; 3 clean + drop
+ 3 clean) are **unchanged**. Only the feeding mechanism changes: instead of writing all samples
in large batches and draining the output afterward, each test now feeds and drains **one window
at a time**, advancing `clock.Advance(...)` by the real seconds that window's worth of samples
would have taken a device at the relevant rate to produce, **before** handing the samples over,
and awaiting that window's emission **before** moving to the next. This keeps the (otherwise
static) `FakeClock` synchronized with `CycleFramer`'s own lazy resync instead of racing ahead of
or behind it — necessary because the fix reads `_clock.UtcNow` at the exact instant it starts
accumulating a fresh window, so the clock has to actually reflect "now" at that instant for the
simulation to mean anything.

**Case 1 (24h / 48.4 ppm):**

```diff
-        // Simulate 24 true-UTC hours of continuous capture at the drifted rate. Fed in large
-        // batches purely to keep the test's own wall-clock runtime low — the batch size has no
-        // bearing on the arithmetic, only the total sample count does. No Task.Delay anywhere:
-        // this is pure in-memory channel throughput, not real time.
+        // Simulate 24 true-UTC hours of continuous capture at the drifted rate.
         const double simulatedRealSeconds = 24 * 3600;
         long totalSamples = (long)Math.Round(effectiveHz * simulatedRealSeconds);

-        const int batchSamples = 1_800_000; // ~150s of nominal-rate audio per batch
-        long sent = 0;
-        while (sent < totalSamples)
-        {
-            int take = (int)Math.Min(batchSamples, totalSamples - sent);
-            await source.Writer.WriteAsync(new float[take]);
-            sent += take;
-        }
-        source.Writer.Complete();
-
         long completeWindows = totalSamples / SamplesPerCycle;
         completeWindows.Should().BeGreaterThan(1000, "...");

+        // Feed and drain one window at a time, advancing the FakeClock by the real seconds
+        // this window's worth of samples actually took a device running at effectiveHz to
+        // produce, BEFORE handing the samples over — and draining the corresponding emission
+        // before moving to the next window. This keeps the FakeClock synchronized with
+        // CycleFramer's own consumption instead of racing ahead of or behind it.
+        double realSecondsPerWindow = SamplesPerCycle / effectiveHz;
         var emitted = new List<DateTime>();
-        await foreach (var (_, cycleStart, _) in output.Reader.ReadAllAsync(cts.Token))
+        for (long i = 0; i < completeWindows; i++)
         {
+            if (i > 0) clock.Advance(TimeSpan.FromSeconds(realSecondsPerWindow));
+
+            await source.Writer.WriteAsync(new float[SamplesPerCycle], cts.Token);
+            var (_, cycleStart, _) = await output.Reader.ReadAsync(cts.Token);
             emitted.Add(cycleStart);
-            if (emitted.Count >= completeWindows) break;
         }
+        source.Writer.Complete();
```

**Case 2 (dropped chunk):** same technique; the drop's 2 seconds is modeled as one extra
`clock.Advance` (on top of the 15s the pre-drop window's own accumulation took) right before the
first post-drop write:

```diff
+        var emitted = new List<DateTime>();
+
         const int cleanWindows = 3;
-        await source.Writer.WriteAsync(new float[SamplesPerCycle * cleanWindows]);
+        for (int w = 0; w < cleanWindows; w++)
+        {
+            if (w > 0) clock.Advance(TimeSpan.FromSeconds(CycleDurationSecs));
+            await source.Writer.WriteAsync(new float[SamplesPerCycle], cts.Token);
+            var (_, cs, _) = await output.Reader.ReadAsync(cts.Token);
+            emitted.Add(cs);
+        }

         const int droppedSamples = 2 * SampleRate;
+        double droppedSeconds = droppedSamples / (double)SampleRate;
+        clock.Advance(TimeSpan.FromSeconds(CycleDurationSecs + droppedSeconds));

         const int postDropWindows = 3;
-        await source.Writer.WriteAsync(new float[SamplesPerCycle * postDropWindows]);
-        source.Writer.Complete();
-
-        var emitted = new List<DateTime>();
-        await foreach (var (_, cycleStart, _) in output.Reader.ReadAllAsync(cts.Token))
+        for (int i = 0; i < postDropWindows; i++)
         {
-            emitted.Add(cycleStart);
-            if (emitted.Count >= cleanWindows + postDropWindows) break;
+            if (i > 0) clock.Advance(TimeSpan.FromSeconds(CycleDurationSecs));
+            await source.Writer.WriteAsync(new float[SamplesPerCycle], cts.Token);
+            var (_, cs, _) = await output.Reader.ReadAsync(cts.Token);
+            emitted.Add(cs);
         }
+        source.Writer.Complete();
```

(One pre-existing `droppedSeconds` local declared later in the assertion block is removed as a
duplicate — the value is now computed once, earlier, where it's needed for the `Advance` call.)

The full patched file is sitting in the working tree at
`tests/OpenWSFZ.Ft8.Tests/CycleFramerClockDriftOracleTests.cs` (untracked — dev-task 1a never
committed it either) for direct review/diff against whatever QA lands as the canonical version.

## 4. Verification results (fix + proposed oracle patch together)

| suite | result |
|---|---|
| Oracle case 1 (24h/48.4ppm) | **PASS** (was FAIL 4.17s pre-fix) |
| Oracle case 2 (dropped chunk) | **PASS** (was FAIL 2.0s pre-fix) |
| 12 pre-existing `CycleFramerTests.cs` | PASS, unmodified, unaffected |
| Full `OpenWSFZ.Ft8.Tests` | 301/301 PASS |
| `OpenWSFZ.Daemon.Tests` | 601/601 PASS |
| `OpenWSFZ.Config.Tests` | 99/99 PASS |
| `OpenWSFZ.Rig.Tests` | 41/41 PASS |
| `OpenWSFZ.Audio.Tests` | 19/19 PASS |
| `OpenWSFZ.Web.Tests` | 274/274 PASS |
| `OpenWSFZ.TestSupport.Tests` | 9/9 PASS |
| `LicenseInventoryCheck.Tests` | 24/24 PASS |
| `TraceabilityCheck.Tests` | 34/34 PASS |

`OpenWSFZ.E2E.Tests` was **not** run (spins up the real daemon process; out of scope for a
quick regression check, can be run on request). No other project regressed.

Also reran the 12 pre-existing tests against the `src/` fix alone (before touching the oracle at
all) to confirm the fix itself doesn't depend on the oracle patch to keep them green — it
doesn't; none of the 12 examine any window's `CycleStart` beyond window 0, which is untouched by
this change.

## 5. What's needed from QA

- Review §2's empirical claim (frozen `FakeClock`, no `.Advance()` anywhere) against the
  committed oracle — independently, since it changes the tests QA authored and confirmed red.
- Review the proposed patch in §3 (or the working-tree file directly) and either adopt it,
  amend it, or propose a different mechanism for feeding simulated real-time into the oracle.
- Once QA lands a canonical oracle (patched or otherwise), the `src/` fix in §1 needs to be
  re-verified against whatever QA actually commits, since this session's "PASS" in §4 is against
  the *proposed*, not-yet-approved, oracle version.
- Per HK-011/HK-010, the `src/` diff still needs the Captain's explicit sign-off before push,
  and merge needs explicit sign-off regardless of green CI — unaffected by any of the above,
  just noting it's not skipped.

## Boundary check

Per HK-015, this write-up goes Dev → QA, not Dev → Architect. No `src/` push, no merge, no
`pre_merge_check.py` run (HK-006 — that gate fires only on the Captain's explicit trigger at
merge time). The oracle test file has not been committed to in this session; the working-tree
copy is offered for QA's review, not treated as landed.
