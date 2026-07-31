# Developer handoff: rebase `fix-cycle-audio-archive-null-config-crash` onto current `main`

**Authored by:** QA (per HK-011/HK-015/HK-000), following review of the existing branch.
**Branch:** `fix-cycle-audio-archive-null-config-crash` (already exists, already pushed, tip
`031fb37`). **Do not create a new branch** and do not re-derive the fix from scratch — rebase this
exact branch onto current `main`.
**Status:** the fix itself (all three layers) has already been reviewed by QA against
`dev-tasks/2026-07-28-fix-cycle-audio-archive-null-config-crash.md` and **approved on its
merits** — correctness, resource/threading (n/a), test quality all checked out, and QA independently
built + ran the touched test assemblies green (37/37) in an isolated worktree. **Nothing about the
design, the guard patterns, or the test approach is open for reconsideration in this task.** The
only problem is that the branch was cut from `main` at `7a44b2c` (28 July) and `main` has since
moved past it, producing one merge conflict.
**Do not run `pre_merge_check.py`** — per HK-006/HK-011 that gate is Captain-initiated only, not a
step in this task.

---

## 1. What's stale and why

The branch predates `e9600ed` (`feat(external-reporting-single-connection)`, currently on
`origin/main`), which added an `InstanceId`/`Role`/`LeaderUrl`/`FollowerUrls` re-guard block to
`src/OpenWSFZ.Web/WebApp.cs` at the **same insertion point** — immediately after the
`config.ExternalReporting is null` guard — where this branch's `CycleAudioArchive` guard also
lands. Everything else rebases clean; this is the one manual resolution required.

Rebase target: `origin/main` (current tip `693c5ba` at time of writing — use whatever `origin/main`
actually is when you start, don't hardcode this hash). Confirmed via `git diff origin/main..main --
src/` that no other local-only commits touch `src/`, so `origin/main` is the correct, complete
rebase target — no need to reconcile against anything else.

## 2. The rebase

```
git fetch origin
git checkout fix-cycle-audio-archive-null-config-crash
git rebase origin/main
```

This will stop with a conflict in `src/OpenWSFZ.Web/WebApp.cs`. All other files (including the
three test files this branch touches) rebase automatically — confirmed via `git merge-tree` ahead
of time; if your rebase reports a conflict anywhere else, stop and flag it, since that would mean
something changed on `main` after this document was written.

## 3. Resolving the one conflict

After the guard block for `ExternalReporting`, current `main` reads (abbreviated):

```csharp
if (config.ExternalReporting is null)
    config = config with { ExternalReporting = new ExternalReportingConfig() };
// InstanceId (fix-external-reporting-appid-collision) needs a guard of its own, ...
if (!instanceIdExplicitlyProvided)
{
    ...
}
// external-reporting-single-connection (task 1.2): ...
if (!roleExplicitlyProvided) { ... }
if (!leaderUrlExplicitlyProvided) { ... }
if (!followerUrlsExplicitlyProvided) { ... }
// Ptt gets a different fallback than the four guards above: ...
if (config.Ptt is null)
    config = config with { Ptt = store.Current.Ptt ?? new PttConfig() };
```

Resolve the conflict by inserting this branch's `CycleAudioArchive` guard (and its full comment,
unchanged from the branch) **between** the `followerUrlsExplicitlyProvided` block and the `// Ptt
gets a different fallback...` comment — i.e. immediately before the `Ptt` guard, exactly where it
sat relative to `Ptt` on the original branch. Do not alter the InstanceId/Role/LeaderUrl/
FollowerUrls blocks in any way; they are unrelated to this fix.

The branch's other `WebApp.cs` insertion — the `RemoteAccess` guard, which sits right after the
`DecodeLog is null` guard and before `DecodeNoiseSuppression is null` — is in a part of the file
`main` hasn't touched, so it will rebase automatically with no manual step. Only the
`CycleAudioArchive` insertion point needs hand resolution.

No other file needs manual attention:
- `src/OpenWSFZ.Config/JsonConfigStore.cs` — untouched by `main` since `7a44b2c`, rebases clean.
- `src/OpenWSFZ.Daemon/CycleArchiveService.cs` — same, rebases clean.
- `tests/OpenWSFZ.Config.Tests/JsonConfigStoreTests.cs`,
  `tests/OpenWSFZ.Daemon.Tests/CycleArchiveServiceTests.cs`,
  `tests/OpenWSFZ.Web.Tests/ConfigApiNullGuardTests.cs` — all additive relative to `main`, rebase
  clean.

## 4. Verification before handing back to QA

- `dotnet build OpenWSFZ.slnx` — must be 0 warnings / 0 errors.
- Run the full assemblies (not just the filtered regression tests — the rebase touched a shared
  file other tests exercise too):
  ```
  dotnet test tests/OpenWSFZ.Config.Tests
  dotnet test tests/OpenWSFZ.Daemon.Tests
  dotnet test tests/OpenWSFZ.Web.Tests
  ```
  All must pass. (QA's own review already confirmed the specific regression tests pass in
  isolation; this step is to catch anything the rebase itself might have disturbed.)
- Confirm `git diff fix-cycle-audio-archive-null-config-crash origin/fix-cycle-audio-archive-null-config-crash`
  (i.e. old branch tip vs. new, post-rebase) shows **only** the expected shape: same content,
  rebased onto a new base, with the `WebApp.cs` conflict resolved as above. No incidental changes.

## 5. Before pushing

This rewrites the branch's history (rebase, not merge), so the push will need `--force-with-lease`,
not a plain push. Per HK-011 §2, **do not push** until the diff has been shown to the Captain and
he has signed off — this applies here exactly as it would to a fresh implementation, since the
conflict resolution is itself a `src/` edit. Show:
- The resolved `WebApp.cs` hunk.
- Confirmation of the green build/test results from §4.

On approval: `git push --force-with-lease origin fix-cycle-audio-archive-null-config-crash`, then
await CI. Merge to `main` still requires the Captain's explicit sign-off per HK-010, independent of
green CI.
