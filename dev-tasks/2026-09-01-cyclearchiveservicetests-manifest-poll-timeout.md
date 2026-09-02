# Developer handoff: `CycleArchiveServiceTests` manifest-poll flake under full-suite load

**Authored by:** QA, 2026-09-01 (per HK-000/HK-015), timestamp per `date -u` at commit time (HK-017).
**Status:** ✅ Root-caused, fix applied (commit `233fb6e` on `fix/cyclearchiveservicetests-poll-timeout`,
off `main`@`2c1a71e`, not pushed), QA-verified. 🟡 **Fix is PARTIAL, not complete — Captain ruling
2026-09-01: ACCEPT AS DOCUMENTED, for now.** Across 3 full-load runs at the widened 15s budget, the
target test still timed out once (see "Developer session result" below) — the widened poll reduces
the flake, it does not eliminate it. This is one observation, not a rate (HK-021(v) — a 1-in-3 sample
is not a measured frequency and must never be cited as one, e.g. "~33%"). The Captain was offered
three options — widen further, accept as documented, or investigate a deeper mechanism — and chose
**accept as documented**. Nothing further is authorised on this defect right now: no further timeout
widening, no deeper investigation, unless a future session reopens it. This branch is otherwise ready
for the same diff review / merge ruling as `FR-020` (HK-010) — "accept as documented" resolves the
residual-flake question, it is not itself a merge instruction.

### Developer session result (2026-09-01, agent-implemented, QA-verified independently)

Diff: `tests/OpenWSFZ.Daemon.Tests/CycleArchiveServiceTests.cs`, 26 insertions, 1 file — 5 manifest-poll
`Poll.UntilAsync` calls widened 5s→15s with citing comments (the named target plus 4 siblings sharing
the identical real-disk-I/O-behind-a-default-timeout shape); 3 different `DequeuedCountForTests`-based
polls correctly left unwidened (they poll an in-memory counter set before the writer loop's real disk
I/O, not the same mechanism — verified, not assumed). `src/CycleArchiveService.cs` untouched, as
required. Gate G10 passed. Test evidence: `OpenWSFZ.Daemon.Tests` in isolation 621/621 ×2; full-solution
run 1 — target test timed out at the new 15s budget under real contention (`OpenWSFZ.Ft8.Tests`
concurrently running ~1m36s); full-solution runs 2 and 3 — clean. QA independently confirmed the diff
matches this report exactly.
**Branch:** create a fresh short branch off `main`@`2c1a71e` — do not combine with the
`BroadcastSpectrum` or `FR-020` fixes; three independent defects, three independent diffs.
**Discovered:** twice now — once in the FR-064 developer session's own full-suite run ("seen on run
1 did NOT reproduce on run 2"), once independently in a Captain-run `pre_merge_check.py` pass on
`fix/fr064-heartbeat-race` (post-merge, so on `main`@`2c1a71e` in effect). Neither branch's diff
touches this test or `CycleArchiveService.cs`.

---

## 0. The failing test

`tests/OpenWSFZ.Daemon.Tests/CycleArchiveServiceTests.cs:182-206`,
`Manifest_WritesOneRowPerArchivedCycle_InOrder`. Enqueues 4 items, then polls for the manifest file
to reach 5 lines (1 header + 4 rows):

```
System.TimeoutException : manifest line count
  at OpenWSFZ.TestSupport.Poll.UntilAsync(...)
  at OpenWSFZ.Daemon.Tests.CycleArchiveServiceTests.Manifest_WritesOneRowPerArchivedCycle_InOrder()
```

Reproduced 0/3 in isolation (`dotnet test --filter`), 0/1 on a same-day full-`Daemon.Tests`-assembly
re-run — i.e. it clears on retry every time it's been re-checked. This is the same shape as the other
three flakes surfaced today: fails only under full-solution parallel load, never in isolation.

## 1. Root cause — resource contention against a fixed poll budget, not a functional defect

**Not a dropped item.** `CycleArchiveService`'s queue is a bounded `Channel<ArchiveItem>`
(`CycleArchiveService.cs:123`) with `DropWrite` full mode, capacity checked explicitly before write
(`:205`, `channel.Reader.Count >= _queueCapacity`). The test's `MakeService(CycleAudioArchiveMode.All)`
call uses the default `queueCapacity: 8` (`CycleArchiveServiceTests.cs:557`) and enqueues exactly 4
items — half of capacity. No drop path can fire; `RecordDrop` (`:221`) is never reached at this
volume. Confirmed by reading the guard, not assumed from the symptom.

**Not the free-space floor.** `HasEnoughFreeSpace` (`:377-388`) falls back to a real
`DriveInfo`-style check (`DefaultFreeBytesProvider`, `:390`) against a 500 MB floor
(`FreeSpaceFloorMb`, `:45`) whenever the test doesn't supply an override — and this test doesn't. 500
MB free on a real development drive is not a plausible intermittent trip point.

**What's left: real disk I/O, scheduled on the .NET thread pool, racing a fixed 5-second poll
budget.** `TryEnqueue` (non-blocking, `:176-212`) hands work to a background `Task.Run`-scheduled
`WriterLoopAsync` (`:132`, `:236-259`), which processes each item through `ProcessItemAsync`
(`:261-`) — real `Directory.CreateDirectory`, `CycleWavWriter.Encode`, and file writes, not
in-memory work. The test then polls for the result via `Poll.UntilAsync` with **no explicit
`timeout` argument** (`CycleArchiveServiceTests.cs:191`), so it uses `Poll.DefaultTimeout` — **5
seconds** (`tests/OpenWSFZ.TestSupport/Poll.cs:23`). Under `dotnet test OpenWSFZ.slnx`'s default
full-solution parallelism, several other assemblies run concurrently — `OpenWSFZ.Ft8.Tests` alone
took 1m13s–1m34s across today's runs, real CPU-bound FT8 decode work, not idle. Thread-pool
scheduling delay for a background `Task.Run` item, plus contended disk I/O from many parallel test
processes writing temp files simultaneously, is a completely ordinary way for 4 small writes to
occasionally miss a 5-second budget that was sized for uncontended conditions.

This is **not the same category** as today's other two findings. `N6` and `FR-020` are correctness/
isolation bugs — wrong behavior regardless of timing. This one is a **poll already using the correct
idiom** (content-based, via `Poll.UntilAsync`, exactly what `fix-flaky-test-delay-synchronization`
and Gate G10 want) whose fixed budget is occasionally too tight for this repository's own heaviest
local full-suite parallel load. The mechanism, not the pattern, is what's under-provisioned.

## 2. Ruled out

- **Not a channel-capacity drop.** §1, capacity 8 vs. 4 enqueued items — not close to the limit.
- **Not the free-space floor.** §1, 500 MB floor against a real drive.
- **Not specific to this one test.** The same `MakeService` → `TryEnqueue` → poll-for-manifest-lines
  shape appears at `CycleArchiveServiceTests.cs:220` (`Manifest_RecordsOffGridOffset`) and elsewhere
  in the file with the same unwidened default timeout — this test is simply the one that has been
  seen to lose the race so far, not the only one exposed to it. Worth the Developer session checking
  whether any sibling test in this file should get the same treatment rather than just this one.

## 3. Recommended fix

Widen this test's (and, per §2, its siblings') `Poll.UntilAsync` call to an explicit, more generous
timeout — e.g. 15s — with a one-line comment citing this dev-task and the contention mechanism, so a
future reader doesn't mistake a widened budget for carelessness. This is **not** a new fixed-duration
delay (Gate G10 concern) — it's the same content-based poll already in use, just budgeted for this
repository's own observed worst-case parallel load instead of an unexamined inherited default. No
`src/` change is needed or appropriate — `CycleArchiveService`'s actual behavior isn't wrong.

Do not "fix" this by disabling test parallelism at the solution level, disabling it for
`OpenWSFZ.Daemon.Tests` specifically, or increasing `Poll.DefaultTimeout` globally — all three have a
much larger blast radius than this one file's polls and are not authorised by this dev-task. If the
Developer session concludes one of those is actually warranted, stop and escalate rather than take it
unilaterally, same rule as the other two dev-tasks today.

## 4. Definition of done

- [x] `Manifest_WritesOneRowPerArchivedCycle_InOrder`'s `Poll.UntilAsync` call given an explicit,
      wider timeout (15s) with a comment citing this dev-task
- [x] Sibling polls in the same file reviewed per §2 — 4 more widened (same shape), 3
      `DequeuedCountForTests`-based polls correctly left unwidened with reasoning recorded
- [x] `dotnet test OpenWSFZ.slnx -c Release` — full suite, run 3 times — 2 clean, 1 still timed out
      at the new budget (see status box above; this is the residual risk the Captain has now ruled on)
- [x] Gate G10 (`tools/check_test_delay_sync.py`) still passes
- [x] `git diff main --stat` — confirmed limited to `CycleArchiveServiceTests.cs`
- [x] NFR-021 / callsign scan — clean (manual review, no dedicated general-purpose scanner exists)
- [x] Commit message states the structural argument, not "N green runs ⇒ fixed"

🛑 **Developer session stopped correctly** — no push, no merge, no `pre_merge_check.py` run
(HK-010/HK-014/HK-006). ✅ **Captain ruling recorded above: accept the residual flake as documented,
for now.** Branch `fix/cyclearchiveservicetests-poll-timeout` is ready for the Captain's own diff
review and merge ruling (HK-010) whenever convenient — same footing as `FR-020`.
