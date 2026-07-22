# Flaky test — FR-060 `IsSeedData becomes false after a successful SaveAsync`

**Date surfaced:** 2026-07-21 (during the `fix-flaky-test-delay-synchronization` closeout pre-merge run)
**Test:** `tests/OpenWSFZ.Daemon.Tests/CallsignRegionStoreTests.cs:418`
`FR-060: engagement-target-validation 1.5: IsSeedData becomes false after a successful SaveAsync`
**Owner area:** `engagement-target-validation` (PR #81) — NOT the delay-sync work.

## Symptom

Failed once in a full `dotnet test -c Release` run on **Windows** (1 of 567 in
`OpenWSFZ.Daemon.Tests`), duration 4 ms. In the **same** pre-merge run:
- Passed 535/535 on the WSL Debian leg (this test included).
- Re-ran in isolation on Windows immediately after — passed (`--filter DisplayName~"IsSeedData
  becomes false"` → 2/2; `--filter FullyQualifiedName~IsSeedData_` → 8/8).

So this is an order-/parallelism-dependent flake, not a regression, and is **unrelated** to the
delay-synchronization change (which touches zero C#). It reproduces only under full-suite parallel
execution, not in isolation — pointing at shared state (seed-data/`IsSeedData` flag or a store file)
bleeding between fixtures rather than a `Task.Delay` sync-barrier of the kind G10 covers.

## Suggested next step (not done here)

Investigate `CallsignRegionStore` seed-data state isolation between `CallsignRegionStoreTests`
fixtures — likely a shared on-disk store path or a static/`IsSeedData` flag not reset per test.
This is a state-isolation flake, a different root cause from the `Task.Delay` barriers Gate G10
addresses, so it is out of scope for that change and tracked separately here.

## QA follow-up investigation (2026-07-21, same day, post-closeout)

Reviewed `CallsignRegionStoreTests.cs` and `src/OpenWSFZ.Daemon/CallsignRegionStore.cs` end to
end. The originally suspected mechanisms do **not** hold up:

- Each `CallsignRegionStoreTests` instance gets its own `Guid.NewGuid()` temp directory in the
  constructor (xUnit creates a fresh class instance per `[Fact]`), so there is no shared on-disk
  path between fixtures.
- `_isSeedData` and `_entries` are per-instance `volatile` fields on `CallsignRegionStore`, not
  static; `CallsignRegionDefaults.Entries` is a `static readonly` list that is never mutated, only
  read.
- `IsSeedData_AfterSuccessfulSave_BecomesFalse` (line 419) is single-threaded, fully sequential
  `await`-then-assert — there is no in-test race window where `_isSeedData` could be read before
  `SaveAsync`'s continuation sets it.

So a genuine state-isolation race in this class's own logic looks **ruled out**. Revised
hypothesis: this is an **infrastructure-level Windows flake**, not a code defect —

`WriteAsync` (the write-to-temp-then-atomic-rename helper shared by `LoadAsync`'s seed-write path
and `SaveAsync`) closes its `FileStream` and then calls `File.Move(tmp, _path, overwrite: true)`
immediately after. On Windows, a just-closed, just-written temp file is a classic target for
real-time antivirus/indexer scanning to grab a transient handle in the instant before the rename —
producing an intermittent `IOException`/sharing-violation on `File.Move`, which `SaveAsync` does
not catch (only `LoadAsync`'s seed-write branch catches `IOException`/`UnauthorizedAccessException`
and falls back gracefully; `SaveAsync`'s `WriteAsync` call has no such catch, so the exception would
propagate out of `await store.SaveAsync(...)` in the test). This fits every observed characteristic:
Windows-only (WSL has no Defender), full-suite-only (more parallel file churn across other test
classes raises the odds of the scan window being hit), fails fast (4 ms — an exception thrown
immediately on the rename, not a timing/assertion delay), and unreproducible in isolation or on a
lightly-loaded run.

**Not proven** — no `.trx`/console capture of the original failure survived to confirm the actual
exception type/message, so this remains a hypothesis, not a confirmed root cause. Attempted
reproduction today: 3/3 full `dotnet test -c Release` runs of `OpenWSFZ.Daemon.Tests` (567/567
each) — did not reproduce, consistent with a rare (~1/567-per-run) probabilistic race rather than
a deterministic bug.

**Notable for the Captain:** the same write-to-temp-then-rename pattern, with the same lack of a
retry/backoff around `File.Move`, is shared verbatim by `FrequencyStore.SaveAsync` (and by
extension likely `CallsignGrammarStore`) — none of them currently guard against a transient
Windows file-lock on rename. If this hypothesis is right, any of those `SaveAsync` paths could in
principle flake the same way; `CallsignRegionStore` has just been the one to draw the short straw
so far. A proportionate fix, if the Captain wants one, would be a small shared retry-on-`IOException`
wrapper (2–3 attempts, short backoff) around the `File.Move` call in the shared write helper(s) —
not a change to `CallsignRegionStore` in isolation.

**Verdict:** low severity, not a blocker. Rate (1 in 567, Windows-only, self-resolves on rerun)
does not currently justify emergency action; recommend leaving as a tracked, accepted flake unless
it recurs, at which point the retry-wrapper fix above should be scoped as a proper dev-task.

## Captain's decision (2026-07-21)

Accepted as a known, tracked flake — no code change for now. **Status: OPEN, monitor only.**
Re-open active investigation (and scope the shared retry-on-`IOException` wrapper as a proper
dev-task) if either of these is observed:

- `IsSeedData_AfterSuccessfulSave_BecomesFalse`, or any other `CallsignRegionStoreTests`/
  `FrequencyStoreTests` `SaveAsync`-path test, fails again on a Windows CI or local
  `dotnet test -c Release` run — capture the console/`.trx` output this time (none survived
  from the original occurrence), so the exception type/message can confirm or refute the
  antivirus/rename-race hypothesis above rather than relying on it unconfirmed a second time.
- The same failure signature turns up in a *different* store's `SaveAsync` test (e.g.
  `FrequencyStoreTests`), which would corroborate the "shared write-then-rename helper" theory
  rather than something specific to `CallsignRegionStore`.
