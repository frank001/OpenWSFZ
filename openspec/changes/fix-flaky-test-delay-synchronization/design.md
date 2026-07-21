## Context

A repo-wide audit (`grep -rn "Task\.Delay([0-9]" tests/ --include="*.cs"`) found 172 fixed-numeric
`Task.Delay` call sites in test code. ~20 are safe — inside an existing `while (deadline)` poll
loop, the correct pattern this codebase already uses in a few places
(`QsoAnswererServiceTests.WaitForStateAsync`/`WaitForKeyingAsync`/`WaitForKeyDownAsync`, and the
`WaitForPublishCountAsync` added today in PR #94). ~150 are the risky shape: a single bare delay
used as the entire synchronization mechanism before an assertion. Four confirmed flakes have come
from this exact mechanism so far (`WaitReport`/`WaitRr73` retry-bracket tests, fixed in PR #94;
`PttWatchdogTests.Disarm_BeforeTimeout_CallbackNeverInvoked`, found but not yet fixed).

There is no shared test-infrastructure project anywhere in the solution's 9 test projects.
`QsoAnswererServiceTests.cs` and `QsoCallerServiceTests.cs` each independently hand-duplicate
near-identical private `WaitForStateAsync`/`WaitForKeyingAsync` methods. Every other affected file
has no polling helper at all. This is treated as a root-cause contributor, not just a symptom: with
no low-friction shared alternative, a fixed delay is the path of least resistance when writing a
new async test, and it passes reliably on an idle dev machine, so the debt accumulates invisibly
until a loaded CI runner exposes it — usually attributed after the fact to "flaky CI" rather than
"this test's synchronization is wrong."

Separately, this same investigation independently discovered (2026-07-20, while diagnosing a
different CI failure on PR #93) that `dotnet test --no-build` can silently skip test execution
entirely on this solution's SDK (exit 0, zero tests run) if MSBuild's `IsTestProject` evaluation
doesn't resolve — a distinct SDK/tooling risk, unrelated to this change, already logged in memory
(`hk006-run-mechanical-gates-before-declaring-ready.md`). It's mentioned here only because it
directly informs one design decision below (§ Decision 2): the new shared library must never be
mistaken for, or evaluated as, a test project.

## Goals / Non-Goals

**Goals:**
- One shared, dependency-light polling primitive that every test project can reference, covering
  every synchronization shape already observed in the audited code (state equality, boolean flag,
  "at least one call received," "at least N calls received").
- Migrate all ~150 audited risky sites onto it, in independently-shippable phases.
- Fix the one live, already-identified flake (`PttWatchdogTests`) as part of the same effort rather
  than leaving it as a separate loose end.
- A mechanical, CI-enforced gate that makes it structurally impossible to add a 151st untracked
  instance, from the moment the gate lands — not after the migration finishes.

**Non-Goals:**
- Fixing `N8` or `F-003` — different root causes (assertion-design flaw; native-decoder margin
  sensitivity), require individual judgement, explicitly out of scope per `proposal.md`.
- A compile-time Roslyn analyzer. This repo's existing quality gates (`tools/check_version_docs.py`,
  `tools/TraceabilityCheck`, the UDP-capture-margin lint, the screenshot-order lint) are all
  post-build/pre-merge scripts wired into `tools/pre_merge_check.py`, not IDE-time analyzers. This
  change follows that existing convention rather than introducing a new tooling category.
- Migrating `Thread.Sleep`-based synchronization — none were found in this audit; if any turn up
  during migration, handle case-by-case, don't expand this change's scope retroactively.

## Decisions

### Decision 1 — One primitive, four thin convenience wrappers, built from what's already proven

A single core primitive:

```csharp
public static class Poll
{
    public static async Task UntilAsync(
        Func<bool> condition,
        TimeSpan? timeout = null,
        TimeSpan? pollInterval = null,
        Func<string>? timeoutMessage = null)
    {
        var deadline = DateTime.UtcNow + (timeout ?? TimeSpan.FromSeconds(5));
        var interval = pollInterval ?? TimeSpan.FromMilliseconds(10);
        while (DateTime.UtcNow < deadline)
        {
            if (condition()) return;
            await Task.Delay(interval);
        }
        throw new TimeoutException(timeoutMessage?.Invoke() ?? "Condition not met within timeout.");
    }
}
```

This is not a new invention — it's the exact shape `WaitForStateAsync`/`WaitForKeyingAsync`/
`WaitForKeyDownAsync`/`WaitForPublishCountAsync` already independently converged on, generalized
into one place. Default timeout 5s (the majority convention already in use; the one 3s outlier,
`WaitForStateAsync`'s original default, is a caller-supplied override, not a behavior change).
Default poll interval 10ms, matching every existing instance with no exceptions found in the audit.

Four typed convenience wrappers cover every shape actually observed in the audited files — no
speculative API surface beyond what's proven needed:
- `WaitForEqualAsync<T>(Func<T> actual, T expected, ...)` — generalizes `WaitForStateAsync`/
  `WaitForKeyingAsync` (state-equality and boolean-flag polling are the same shape).
- `WaitForCallAsync(Func<IEnumerable<NSubstitute.Core.ICall>> calls, string methodName, ...)` —
  generalizes `WaitForKeyDownAsync` ("at least one call").
- `WaitForCallCountAsync(Func<IEnumerable<NSubstitute.Core.ICall>> calls, string methodName, int
  expectedCount, ...)` — generalizes `WaitForPublishCountAsync` ("at least N calls").

**Correction (found during Phase 0 implementation, before any code was written):** both call-count
wrappers take a `Func<IEnumerable<ICall>>` factory, **not** a plain `IEnumerable<ICall>` as
originally drafted here. Verified empirically (throwaway probe project, not committed):
`NSubstitute`'s `ReceivedCalls()` returns a snapshot at call time, not a live view over the
substitute's growing call log — capturing `sub.ReceivedCalls()` once, before entering a poll loop,
freezes the list at zero calls and the wrapper would poll that frozen snapshot forever, always
timing out. This is exactly *why* the existing hand-written `WaitForKeyDownAsync`/
`WaitForPublishCountAsync` call `ptt.ReceivedCalls()` / `eventBus.ReceivedCalls()` **fresh, inside**
the `while` loop, every iteration — not once outside it. The factory shape lets the wrapper
re-invoke `ReceivedCalls()` on each poll tick, matching that already-correct pattern. Callers pass a
lambda: `WaitForCallAsync(() => ptt.ReceivedCalls(), nameof(IPttController.KeyDownAsync))`.

All three wrappers are one-line implementations calling `Poll.UntilAsync` — the value is in not
re-deriving the deadline-loop-timeout boilerplate at each of the ~150 call sites, not in a large
new API.

**Alternative considered**: a fluent/builder API (`Poll.For(() => x).ToEqual(y).WithTimeout(...)`).
Rejected — more code to review across 150 mechanical call-site edits for no behavioral gain over
plain static methods; this codebase's existing style is plain static helper methods, not fluent
builders.

### Decision 2 — New project: `tests/OpenWSFZ.TestSupport/OpenWSFZ.TestSupport.csproj`, deliberately not a test project

Location: under `/tests/` in `OpenWSFZ.slnx` (conceptually it only exists to serve test projects),
but its `.csproj` is a plain `Microsoft.NET.Sdk` library — **no** `Microsoft.NET.Test.Sdk` package
reference, so `IsTestProject` is never set and `dotnet test`/VSTest never touch it. Its name
deliberately does **not** end in `.Tests`, for two concrete, previously-hit reasons:

1. Gate **G3** (`tools/TraceabilityCheck`) globs `**/bin/Release/net10.0/*.Tests.dll` to discover
   assemblies to check. A `.Tests`-suffixed shared library would be pulled into traceability
   scanning and (having no `[Fact]`s carrying `FR-###:`/`NFR-###:` prefixes) would need spurious
   debt-file entries or dummy tests to pass G3 for no reason.
2. `pre_merge_check.py`'s own test-assembly discovery uses the same glob. Keeping the library
   outside it means it's built via ordinary `dotnet build` project-reference resolution, with no
   special-casing needed anywhere in existing tooling.

Referenced via `<ProjectReference>` from `OpenWSFZ.Daemon.Tests`, `OpenWSFZ.Web.Tests`,
`OpenWSFZ.Ft8.Tests`, and `OpenWSFZ.Audio.Tests` (the four projects with audited sites). `NSubstitute`
is added as a normal `PackageReference` (version already centrally pinned in
`Directory.Packages.props`, no new version to reconcile).

**Alternative considered**: put the helpers in `OpenWSFZ.Abstractions` (already referenced
everywhere). Rejected — that project is production code shipped in the daemon; test-only helpers
(and a test-only `NSubstitute` dependency) don't belong in a runtime assembly.

### Decision 3 — `Poll.UntilAsync` itself gets real tests, not just trust

Ironic given the subject matter, but necessary: a new `OpenWSFZ.TestSupport.Tests` project (a
genuine, small `IsTestProject`) proves `Poll.UntilAsync`'s own timeout/success/interval behavior
deterministically — e.g. a condition that becomes true after a controlled number of poll
iterations, and a timeout case bounded tightly enough to run fast without itself being flaky (a
condition that's designed to *never* become true, asserted against a short explicit timeout, is not
timing-sensitive the way the code under test was). This is the one new test file in the whole
change that's allowed to contain small literal delays, by construction — it's testing the polling
primitive itself, not using delays as a substitute for polling.

### Decision 4 — Gate G10: debt-file allowlist, not a binary warn/fail switch

The proposal posed this as "hard-fail immediately" vs. "warn-only until migration is complete."
Neither is right in isolation. This codebase already has the correct answer, in use for exactly
this kind of situation: Gate **G3**'s `traceability-debt.md` mechanism — pre-existing gaps are
explicitly enumerated and tolerated, anything **not** enumerated is a hard failure from day one.

`G10` (`tools/check_test_delay_sync.py`, wired into `pre_merge_check.py` and
`.github/workflows/ci.yml` on the Linux leg, matching G3/G5/G7/G8's placement) works the same way:

1. Scan every `.cs` file under `tests/**` **except** `tests/OpenWSFZ.TestSupport/**` (the one place
   a literal-delay implementation legitimately lives, per Decision 1) for
   `Task\.Delay\(\s*\d` (a bare numeric-literal delay — polling delays use a variable/parameter,
   e.g. `Task.Delay(interval)` or `Task.Delay(10)` only inside `Poll.UntilAsync` itself, never a
   raw literal elsewhere once migrated).
2. A companion `openspec/changes/fix-flaky-test-delay-synchronization/test-delay-debt.md` file
   enumerates every currently-known site as `file:line` at authoring time (the ~150 from the
   audit), one per line, each phase's migration PR removing its own entries as it lands.
3. Any match found in step 1 **not** present in the debt file is a **hard failure**, immediately,
   from the moment this gate lands — including on files not yet migrated, if a *new* bare delay is
   added to them. Any match that **is** in the debt file passes (pre-existing, tracked, scheduled).

This means G10 is never "advisory" in the sense of being ignorable — it's fully blocking from day
one, but only blocks *regressions*, not the pre-existing, already-tracked debt. That's a materially
stronger guarantee than the proposal's "advisory until migration completes" framing, and it costs
nothing extra to build since the debt-file mechanism already exists as a template (`TraceabilityCheck`
+ `traceability-debt.md`) to copy.

**Alternative considered**: an inline suppression comment (`// test-delay-ok: reason`) instead of a
central debt file. Rejected in favor of one mechanism (matches G3's precedent) rather than two
different suppression conventions in the same repo.

### Decision 5 — Migration order

Ordered by concentration and by what's already proven:

- **Phase 0**: `OpenWSFZ.TestSupport` (+ its own tests, Decision 3), wire G10 with the full ~150-line
  debt file seeded, land in `pre_merge_check.py` + CI. Zero test-file migration in this phase — pure
  infrastructure, ships alone, immediately blocks new regressions.
- **Phase 1**: fix the live flake (`PttWatchdogTests`, 8 sites, small and already fully diagnosed) +
  migrate `QsoAnswererServiceTests.cs` (58) and `QsoCallerServiceTests.cs` (45) together, since
  their existing hand-duplicated helpers get deleted and replaced by the shared library in the same
  pass — the biggest single win (103 of ~150 sites, 69%) in one phase.
- **Phase 2**: `ExternalReportingServiceTests.cs` (18), `CatPollingServiceTests.cs` (14) +
  `CatPollingServiceFreqPersistTests.cs` (3), `CatPttControllerTests.cs` (4).
- **Phase 3**: the remaining small files — `SerialRtsDtrPttControllerTests.cs` (3),
  `DaemonStartupTests.cs` (2), `QsoAnswererServiceExternalReplyTests.cs` (2),
  `GracefulStopDelegationTests.cs` (2), `Web.Tests/SystemRestartEndpointTests.cs` (4),
  `Web.Tests/AuthMiddlewareTests.cs` (1), `Ft8.Tests/LoggingPipelineTests.cs` (3), and
  `Audio.Tests/CaptureManagerTests.cs` (5, reviewed case-by-case — see Open Questions).

Each phase is its own PR, independently reviewable, independently revertable, each gated by the
same `pre_merge_check.py` + full three-OS CI run as any other change.

## Risks / Trade-offs

- **[Risk]** Mechanically migrating 150 sites by hand across large files could subtly change what a
  test actually waits for (reading the surrounding code wrong). → **Mitigation**: each phase is
  reviewed as its own PR; the replacement condition for each site must be justified by what
  production code path the original comment/timing was actually waiting on (same standard PR #94
  was already held to); each phase's affected test files run locally 10× consecutively clean
  (matching the bar already established by `f-003-ap-assist-flaky-decode-test.md`) before merge,
  not just once.
- **[Risk]** The debt-file allowlist could itself go stale/inaccurate (line numbers shift as
  unrelated edits touch the same files between phases). → **Mitigation**: `check_test_delay_sync.py`
  matches on file **and** the literal delay text, not line number alone, tolerating line drift the
  same way `traceability-debt.md` already does for G3.
- **[Trade-off]** A regex/text-scan lint (not a real C# parser) can't perfectly distinguish "bare
  literal delay used as a sync barrier" from some hypothetical legitimate literal delay. → Accepted:
  no legitimate case was found in this audit (every hit was a synchronization barrier), and the
  debt-file mechanism gives a safety valve if one turns up — add it to the debt file with a comment
  explaining why it's intentional, same as any other tracked exception.
- **[Risk]** Adding a new project increases solution build time marginally. → Not mitigated, accepted
  as negligible (a handful of small static classes, no heavy dependencies beyond NSubstitute which
  every consuming project already references).

## Migration Plan

Phase 0 ships first and stands alone — it's safe to merge immediately (blocks only new regressions,
not existing debt) without waiting on any subsequent phase. Phases 1–3 ship independently afterward,
each shrinking `test-delay-debt.md`; the change is "complete" (all `tasks.md` items done) when the
debt file is empty. No rollback complexity beyond normal PR revert, since phases touch disjoint
files and G10's behavior (only blocking new/untracked instances) never depends on a phase being
"in progress" vs. "done."

## Open Questions

- Exact library name/namespace (`OpenWSFZ.TestSupport` proposed here, not yet confirmed with the
  Captain).
- Whether `CaptureManagerTests.cs`'s `Task.WhenAny(Task.Delay(10), deadline)` shape (Audio.Tests)
  needs migration to `Poll.UntilAsync` at all, or is already an acceptably different, safer pattern
  — deferred to Phase 3's own task rather than decided here without reading that file in full.
- Whether G10 should eventually also scan for `Thread.Sleep` — none found in this audit; revisit
  only if one turns up during migration.
