# `CycleArchiveServiceTests` flake, recurred — sharper root cause: `Poll.UntilAsync` doesn't tolerate a transient exception from its own condition

**Authored by:** QA, 2026-09-14 18:08Z (`date -u`, HK-017). Filed per TESTING_STRATEGY.md §11 item 1
(first observation of *this exception shape* on this test, even though the test itself was already
subject to a prior, Captain-accepted residual-flake ruling — see below). **Not a blocker** for
whatever PR surfaced it (per policy item 3, escalation to blocker needs a *repeat* flake on the same
test before its issue is fixed — the prior issue's fix, and the Captain's "accept as documented"
ruling on it, addressed a different exception type than this one).

**Context this was found in:** `pre_merge_check.py`-equivalent CI (`Build & Test (windows-latest)`,
one of two duplicate runs) on PR #175 (`feat/passband-140-ship`) — a branch that touches only
`ft8_shim.c`, `ft8_shim.h`, `Ft8LibInterop.cs`, `BUILD.md`, and one `openspec` spec file. Nothing in
`CycleArchiveService` or its tests. The *other* duplicate CI run's `windows-latest` passed clean
(621/621), and QA's own local full-suite runs (twice, independently, Windows Release) were clean
(1459/1459) — this is confirmed unrelated to that PR's content, same pattern as every prior flake in
this file.

## 0. The failing test, and how this differs from the already-documented flake on it

`tests/OpenWSFZ.Daemon.Tests/CycleArchiveServiceTests.cs:202`,
`Manifest_WritesOneRowPerArchivedCycle_InOrder`. This exact test already carries a prior finding
(`dev-tasks/2026-09-01-cyclearchiveservicetests-manifest-poll-timeout.md`, Captain ruling: "accept
as documented" a residual flake after widening its poll timeout 5s→15s) — that dev-task's own
symptom was `System.TimeoutException : manifest line count`, i.e. the poll ran out its full 15s
budget without the condition ever returning `true`.

**Today's failure is a different exception type, from a different location, and the prior fix does
nothing for it:**

```
System.IO.IOException : The process cannot access the file '...\cycle-archive.csv' because it is
being used by another process.
   at ... File.ReadAllLines(String path, Encoding encoding)
   at CycleArchiveServiceTests.cs:216   <- INSIDE the Poll.UntilAsync condition lambda itself
   at OpenWSFZ.TestSupport.Poll.UntilAsync(...)
```

Line 216 is the poll's own condition: `() => File.Exists(manifestPath) &&
File.ReadAllLines(manifestPath).Length == 5`. The background writer (`CycleArchiveService`'s
`WriterLoopAsync`) had the manifest file open for writing, without `FileShare.Read`, at the exact
instant this one poll tick's `File.ReadAllLines` call landed.

## 1. Root cause — `Poll.UntilAsync` has no exception tolerance in its own loop

Read directly (`tests/OpenWSFZ.TestSupport/Poll.cs:42-54`):

```csharp
public static async Task UntilAsync(Func<bool> condition, ...)
{
    var deadline = DateTime.UtcNow + (timeout ?? DefaultTimeout);
    var interval = pollInterval ?? DefaultPollInterval;
    while (DateTime.UtcNow < deadline)
    {
        if (condition()) return;      // <-- no try/catch here
        await Task.Delay(interval);
    }
    throw new TimeoutException(...);
}
```

`condition()` is called with **no exception handling whatsoever**. Any exception it throws —
including a purely transient one, like a file being momentarily exclusively locked by a concurrent
writer, which is precisely the condition this helper exists to poll past — propagates immediately
out of `UntilAsync` and fails the test on the spot, **regardless of how much timeout budget
remains.** Widening the timeout (the 2026-09-01 fix) helps the "condition legitimately takes a while
to become true" case; it does nothing for "one unlucky tick's read collided with the writer's
exclusive lock," because that tick doesn't get a retry — it's a hard failure the instant it happens,
even on poll tick 1 of a 15-second budget.

This is a **shared test-infrastructure gap**, not specific to `CycleArchiveServiceTests`:
`Poll.UntilAsync` is used across the test suite (`Poll.cs`'s own doc comment names
`QsoAnswererServiceTests`/`QsoCallerServiceTests` as prior art it generalized). Any test polling a
condition that can throw transiently under contention — a file another writer has open, a
not-yet-fully-initialized resource, anything with a narrow "busy" window — is exposed to this same
shape, whether or not it has been *observed* yet. This test is simply the one that has hit it so far.

## 2. Recommended fix (not implemented here — scoping only)

`Poll.UntilAsync`'s condition call should tolerate a caller-specified set of transient exception
types (at minimum `IOException`) by treating them as "condition not yet true, keep polling" rather
than letting them abort the loop — e.g. wrap `condition()` in a `try/catch` for an opt-in exception
allowlist, defaulting to none (so existing callers whose condition legitimately should never throw
keep today's fail-fast behavior unless they opt in). This is shared infrastructure
(`tests/OpenWSFZ.TestSupport/Poll.cs`) used well beyond this one test file — a change here has a
wide blast radius and needs its own scoped Developer session, not a fix folded into whatever PR next
happens to trip over it.

**Do not,** as a substitute: retry the whole test (masks the mechanism), open the manifest file with
`FileShare.ReadWrite` from the test side only (treats the symptom in one call site, not the shared
primitive), or further widen this one test's timeout again (already tried 2026-09-01; does not
address this exception shape at all, per §1).

## 3. Disposition

- **Not authorised to fix right now.** The Captain's 2026-09-01 ruling on this same test was
  explicit: "accept as documented... nothing further is authorised on this defect right now...
  unless a future session reopens it." This dev-task is that reopening — informational, with a
  sharper diagnosis, not a unilateral decision to act on it.
- **Does not block PR #175** or any other in-flight work. Confirmed unrelated by an independent
  clean CI run and two independent clean local runs, same corpus of evidence every prior flake in
  this file has been confirmed against.
- Captain's call whether to scope a `Poll.cs` fix now, fold it into a future test-infrastructure
  pass, or leave it accepted-as-documented alongside the 2026-09-01 finding.

## References

| Reference | Content |
|---|---|
| `dev-tasks/2026-09-01-cyclearchiveservicetests-manifest-poll-timeout.md` | The prior finding on this same test — different exception type (`TimeoutException`), Captain-accepted residual flake |
| `dev-tasks/2026-08-30-flaky-cyclearchiveservicetests-manifestgapmarker-file-lock.md` | A sibling flake in the same file, same `IOException`-on-`cycle-archive.csv` shape, different test method |
| `tests/OpenWSFZ.TestSupport/Poll.cs:42-54` | `UntilAsync`'s own loop — no exception handling around `condition()` |
| `TESTING_STRATEGY.md` §11 | Flaky Test Policy this filing satisfies |

---

*Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>*
*Claude-Session: https://claude.ai/code/session_015X7EER7oMZEPcUjDSKgbuy*
