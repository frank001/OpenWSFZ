# DEV TASK — `JsonConfigStore` concurrent-save race causes 500 on `/api/v1/tx/abort`

**Date:** 2026-07-10
**OpenSpec change:** none — this is a defect fix, not a spec change. No requirement describes
`/tx/abort`'s error behaviour, so nothing to update.
**Branch:** continue on `feat/decode-status-control-merge` (found during the Captain's live
verification pass of that branch's `Keying` work; not caused by it — see "Not caused by this
branch" below — but blocking a clean sign-off of the session's live testing).
**Status:** New.
**Found by:** QA, reading `logs/openswfz-20260710T204450Z.log` after the Captain reported "several
things went very wrong" during manual live testing.

---

## Evidence

Two identical incidents in one ~3-minute session, both HTTP 500 on `POST /api/v1/tx/abort`:

| Time | Service / state at time of abort | Log lines |
|---|---|---|
| 22:46:22.472 | `QsoAnswererService`, state `WaitReport` | 601–627 |
| 22:47:31.700 | `QsoCallerService`, state `WaitAnswer` | 961–988 |

Both throw the identical exception from the identical place:

```
[ERR] An unhandled exception has occurred while executing the request.
System.UnauthorizedAccessException: Access to the path is denied.
   at System.IO.FileSystem.MoveFile(String sourceFullPath, String destFullPath, Boolean overwrite)
   at OpenWSFZ.Config.JsonConfigStore.SaveAsync(AppConfig config, CancellationToken ct) in ...JsonConfigStore.cs:line 61
   at OpenWSFZ.Web.WebApp.<>c__DisplayClass0_0.<<Create>b__30>d.MoveNext() in ...WebApp.cs:line 1012
```

`Request finished ... POST /api/v1/tx/abort - 500 ...` follows in both cases. **The QSO state
machine itself recovers correctly in both incidents** — the very next log lines show `"...aborted
to Idle"` and (for the caller case) `"caller QSO ended — reverting active role to Answerer"`. The
abort *works*; only the HTTP response lies about it.

A third abort in the same session (22:47:12.131, line 867, `QsoCallerService` state `TxCq` — i.e.
mid-transmission rather than a `Wait*` state) returned 200 cleanly. That's the diagnostic clue —
see root cause below.

## Root cause

`POST /api/v1/tx/abort` (`src/OpenWSFZ.Web/WebApp.cs:1004-1019`) does, in order:

1. `await qsoController.AbortAsync(ct)` — this only cancels a `CancellationTokenSource` (and does
   a best-effort `KeyUpAsync`) and returns immediately. It does **not** wait for the service's
   background loop to actually finish unwinding the aborted session.
2. Its own explicit `await store.SaveAsync(store.Current with { Tx = currentTx with { AutoAnswer =
   false } }, ct)` at line 1012, with a comment noting this is "idempotent with the save in
   `SafeAbortToIdleAsync` — both write the same value; no conflict."

Meanwhile, cancelling the token wakes the affected service's own background loop
(`BackgroundService.ExecuteAsync`), which calls `SafeAbortToIdleAsync`
(`QsoAnswererService.cs:1145`, `QsoCallerService.cs:949`) — and *that* method performs its own,
completely independent `_configStore.SaveAsync(... AutoAnswer = false ...)`
(`QsoAnswererService.cs:1198-1208`, `QsoCallerService.cs:~999`).

When abort lands while the service is parked in a `Wait*` state (`WaitReport`/`WaitAnswer`), the
background loop is already blocked on a channel/`TaskCompletionSource` read that the cancellation
unblocks essentially instantly — so `SafeAbortToIdleAsync`'s save runs concurrently with
`WebApp.cs`'s own save. When abort lands mid-transmission (`TxCq`/`TxAnswer`), the background loop
is blocked inside `KeyDownAsync`/audio playback and takes measurably longer to unwind, so
`WebApp.cs`'s save completes and returns *before* the background save starts — no race, no crash.
This exactly matches the observed pattern (both crashes on `Wait*`-state aborts; the one
mid-transmission abort in the same session was clean).

`JsonConfigStore.SaveAsync` (`src/OpenWSFZ.Config/JsonConfigStore.cs:35-72`) has **no locking**.
Both callers independently: write to their own randomly-named temp file, then
`File.Move(tmp, _path, overwrite: true)` onto the *same* destination path. Windows transiently
denies a second `File.Move` targeting a path while another `File.Move`/replace onto that same path
is in flight — hence `UnauthorizedAccessException: Access to the path is denied`. The developer
comment at `WebApp.cs:1009-1010` reasoned correctly about *value* conflict (both saves write
`AutoAnswer = false`, so no logical disagreement) but missed the *mechanical* file-I/O conflict of
two concurrent renames onto one path.

**Not caused by this branch.** `git diff -- src/OpenWSFZ.Web/WebApp.cs` shows this branch's only
change to the `/tx/abort` handler is adding the new `Keying` field to the response — the
save-then-save sequence at lines 1004-1019 is pre-existing code. It surfaced now because this
session did unusually heavy manual abort-cycling while live-verifying the `Keying` signal.

**This is a structural gap, not a one-off bad call site.** `JsonConfigStore` has at least one other
independent concurrent writer: `CatPollingService.cs:438` fire-and-forget-saves
`Cat.LastPolledFrequencyMHz` on its own polling cadence whenever CAT is connected. CAT was not
connected this session (no `CAT:` log lines), so it isn't implicated in these two incidents, but it
confirms any concurrent pair of `SaveAsync` calls — not just these two abort-path callers — can hit
the same crash. Fix the store, not just the call site.

## Recommended fix

1. **Primary/structural:** serialize writes inside `JsonConfigStore.SaveAsync` with a
   `SemaphoreSlim(1, 1)` (or equivalent) held across the temp-write + `File.Move`, so concurrent
   callers queue instead of racing on the rename. This protects every current and future caller,
   not just the two in this report.
2. **Secondary/cleanup (optional, only after (1) lands and is verified):** the explicit
   `store.SaveAsync(...)` at `WebApp.cs:1012` becomes genuinely redundant once (1) makes concurrent
   saves safe — `SafeAbortToIdleAsync` in both services already performs the same write. Consider
   removing it to eliminate the double-write entirely (simpler, one fewer file I/O per abort), but
   only as a follow-on — don't skip (1) in favour of just deleting this call, since that leaves the
   underlying store still unsafe for the `CatPollingService` case and any future concurrent caller.
3. Do **not** simply wrap `WebApp.cs:1012`'s call in a try/catch to swallow the exception — that
   would hide the 500 without fixing the underlying race, and would leave `JsonConfigStore` unsafe
   for every other concurrent-write scenario.

## Tests required

- A regression test on `JsonConfigStore` (or wherever its tests live) firing two concurrent
  `SaveAsync` calls at the same store instance and asserting neither throws and the file ends up
  valid/parseable afterward. This is the test that would have caught this before it ever reached
  live testing.
- Confirm existing `/tx/abort` tests in `QsoAnswererServiceTests.cs` / `QsoCallerServiceTests.cs`
  still pass unchanged (they mock `IConfigStore`, so they wouldn't have caught the race — that's
  expected and fine, the new test above is what covers this).

## Verification

1. `dotnet build OpenWSFZ.slnx -c Release` / `dotnet test OpenWSFZ.slnx -c Release --no-build` —
   expect unchanged pass count plus the one new regression test, green.
2. Live re-check: repeat the Captain's abort-cycling pattern from this session (enable TX, let it
   reach a `Wait*` state, hit abort — repeat several times back-to-back) against a locally built
   daemon and confirm no 500s and no `[ERR]` lines in the log for `/api/v1/tx/abort`.
3. `openspec validate --strict --all` — expect unchanged pass count (no spec touched).

## References

- `logs/openswfz-20260710T204450Z.log` lines 601-627, 961-988 (the two incidents), line 867 (the
  clean abort that pinpoints the timing condition).
- `src/OpenWSFZ.Config/JsonConfigStore.cs:35-72` (`SaveAsync` — where the fix belongs).
- `src/OpenWSFZ.Web/WebApp.cs:1004-1019` (`/api/v1/tx/abort` handler).
- `src/OpenWSFZ.Daemon/QsoAnswererService.cs:1145-1208` (`SafeAbortToIdleAsync`).
- `src/OpenWSFZ.Daemon/QsoCallerService.cs:949-1003` (`SafeAbortToIdleAsync`).
- `src/OpenWSFZ.Daemon/Cat/CatPollingService.cs:425-443` (the other independent concurrent writer,
  cited as evidence this is structural, not local to `/tx/abort`).

## QA re-review

QA will check the new concurrent-save regression test directly (not just "tests pass") and will
re-run the abort-cycling live check described above before sign-off.
