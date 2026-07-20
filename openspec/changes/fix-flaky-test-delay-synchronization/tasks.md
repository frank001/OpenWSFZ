## 1. Phase 0 — Shared polling library and Gate G10 infrastructure

- [x] 1.1 Create `tests/OpenWSFZ.TestSupport/OpenWSFZ.TestSupport.csproj` — plain
  `Microsoft.NET.Sdk` class library, `net10.0`, `Nullable=enable`, `TreatWarningsAsErrors=true`,
  matching the style of `src/OpenWSFZ.Abstractions/OpenWSFZ.Abstractions.csproj`. **No**
  `Microsoft.NET.Test.Sdk` reference (must not become `IsTestProject=true`, per design.md Decision 2).
  Add `NSubstitute` as a `PackageReference` (version already centrally pinned in
  `Directory.Packages.props`). Add the project to `OpenWSFZ.slnx` under the `/tests/` folder.
- [x] 1.2 Implement `Poll.UntilAsync` (the core primitive, design.md Decision 1) in
  `tests/OpenWSFZ.TestSupport/Poll.cs`.
- [x] 1.3 Implement the three convenience wrappers (`WaitForEqualAsync<T>`, `WaitForCallAsync`,
  `WaitForCallCountAsync`) built on `Poll.UntilAsync`, in the same project.
  (Amended during implementation: `WaitForCallAsync`/`WaitForCallCountAsync` take a
  `Func<IEnumerable<ICall>>` factory, not a plain `IEnumerable<ICall>` — see design.md Decision 1's
  "Correction" note, found and empirically verified before any code was written.)
- [x] 1.4 Create `tests/OpenWSFZ.TestSupport.Tests/OpenWSFZ.TestSupport.Tests.csproj` — a genuine
  `IsTestProject`, matching the standard test-project template used elsewhere in `tests/`. Add it to
  `OpenWSFZ.slnx`.
- [x] 1.5 Write `Poll.UntilAsync`'s own deterministic tests (design.md Decision 3): a
  returns-promptly-on-success case and a times-out-on-never-true case, neither relying on an
  unrelated fixed delay to determine pass/fail. Cover the `test-synchronization-reliability`
  capability's "Primitive returns as soon as its condition becomes true" and "Primitive times out on
  a condition that never becomes true" scenarios. (9 tests total: also covers `WaitForEqualAsync`
  and, as regression coverage for the Decision-1 correction, `WaitForCallAsync`/`WaitForCallCountAsync`
  observing calls made after polling has already started.)
- [x] 1.6 Audit and finalize the ~150-site inventory: re-run
  `grep -rn "Task\.Delay([0-9]" tests/ --include="*.cs"` against current `main` (line numbers may
  have drifted since the original audit) and write the confirmed list to
  `openspec/changes/fix-flaky-test-delay-synchronization/test-delay-debt.md`, one `file:line` entry
  per site (excluding the ~20 already-safe polling-loop sites), grouped by the phase that will
  migrate them (Phase 1 / Phase 2 / Phase 3, per design.md Decision 5).
  (Corrected during implementation: re-audit found 172 sites, zero line-count drift from the
  original audit's totals per file. The ~20 already-safe polling-loop-internal sites — the existing
  `WaitForStateAsync`/`WaitForKeyingAsync`/`WaitForKeyDownAsync`/`WaitForPublishCountAsync` helpers'
  own `await Task.Delay(10);` lines — are included in the debt file after all, not excluded: Gate
  G10 (task 1.7) matches mechanically on any bare-delay text regardless of whether it sits inside an
  already-correct poll loop, so excluding them would make G10 fail immediately on Phase 0 landing,
  before Phase 1 ever deletes the helper methods that contain them. Tracked under the Phase 1
  section with a note explaining why. Also added: 3 sites in the new `PollTests.cs` (permanently
  exempt by construction, design.md Decision 3, tracked in their own section) and 1 comment-text
  false-positive in `CatPollingServiceTests.cs:224` (a code comment mentioning `Task.Delay(0, ...)`,
  not real code) — both handled via the same debt-file mechanism rather than special-cased in the
  script.)
- [x] 1.7 Implement `tools/check_test_delay_sync.py` (Gate G10 lint): scans `tests/**/*.cs` excluding
  `tests/OpenWSFZ.TestSupport/**`, matches bare `Task\.Delay\(\s*\d` literals, fails on any match
  whose `file:line`-or-matching-text is not present in `test-delay-debt.md`, matching
  `traceability-debt.md`'s tolerance for line-number drift (design.md Decision 4, Risk mitigation).
  Exit non-zero with a clear message listing every offending, untracked site on failure.
  (Matching is by (file, matched-call-text) count, not file:line — see the script's own docstring.)
- [x] 1.8 Wire `check_test_delay_sync.py` into `tools/pre_merge_check.py` as a new gate step
  (`G10 — test-delay-synchronization lint`), same placement style as the existing UDP-capture-margin
  lint.
- [x] 1.9 Wire the same script into `.github/workflows/ci.yml` on the Linux matrix leg only, matching
  G3/G5/G7/G8's existing placement.
- [x] 1.10 Run `python3 tools/pre_merge_check.py` clean (per HK-006) and confirm Gate G10 passes with
  the full pre-existing debt file in place and fails when a throwaway untracked
  `Task.Delay(999)` is temporarily added to a test file (manual negative-path check, then revert the
  throwaway line before committing).
- [x] 1.11 Ship Phase 0 as its own PR. Per design.md's Migration Plan, this is safe to merge alone —
  it blocks only new regressions, not the existing tracked debt. (PR #95, branch
  `fix/flaky-test-delay-synchronization`.)

## 2. Phase 1 — Live flake fix + the two dominant files (Answerer/Caller)

- [x] 2.1 Fix `PttWatchdogTests.Disarm_BeforeTimeout_CallbackNeverInvoked`
  (`tests/OpenWSFZ.Daemon.Tests/PttWatchdogTests.cs`) and its 7 sibling `Task.Delay` sites in the
  same file, using the shared library. Remove these sites from `test-delay-debt.md`.
  (Root cause: a fixed 30ms delay between `Arm(200, ...)` and `Disarm()` raced the watchdog's own
  200ms timer under CI load. Fixed by removing the injected gap — `Disarm()` now runs back-to-back
  with `Arm()` — plus converting the "must never fire" trailing waits to the
  poll-and-expect-timeout idiom via `Poll.WaitForEqualAsync`/`ThrowAsync<TimeoutException>`.)
- [x] 2.2 Migrate `tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs`'s 58 audited sites to the
  shared library. Delete the file's private `WaitForStateAsync`/`WaitForKeyingAsync`/
  `WaitForKeyDownAsync`/`WaitForPublishCountAsync` methods and replace call sites with the shared
  `OpenWSFZ.TestSupport` equivalents (design.md Decision 1 — these four already match the shared
  wrappers' shapes exactly, this is close to a mechanical rename plus import). Remove these sites
  from `test-delay-debt.md`.
  (52/58 migrated; 6 left as permanent, justified debt-file exceptions — a background feeder-loop
  throttle (2 sites) and a wall-clock stray-wakeup settle margin with no observable condition to
  poll for (4 sites), neither of which is a synchronization-barrier guess. Also added a private
  per-file `WaitForBatchDrainedAsync` helper (polls `_channel.Reader.Count == 0`) for the ~50
  "pace between decode-batch sends" sites that aren't one of the four helper-call shapes. Found and
  fixed a real regression during migration: two skip/retry cycle-sequencing tests need the precise
  `KeyUpAsync`-count signal, not channel-drain alone — see test-delay-debt.md's note on this file
  for the full root-cause writeup. 106/106 tests, 5/5 consecutive clean runs.)
- [ ] 2.3 Migrate `tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs`'s 45 audited sites the same
  way, deleting its own independently-duplicated `WaitForStateAsync`/`WaitForKeyingAsync`. Remove
  these sites from `test-delay-debt.md`.
- [ ] 2.4 Full local regression: `dotnet test tests/OpenWSFZ.Daemon.Tests -c Release`, 10 consecutive
  clean runs (matching the bar set by `f-003-ap-assist-flaky-decode-test.md`), before considering
  Phase 1 done.
- [ ] 2.5 Run `python3 tools/pre_merge_check.py` clean.
- [ ] 2.6 Ship Phase 1 as its own PR.

## 3. Phase 2 — External reporting and CAT polling/PTT files

- [ ] 3.1 Migrate `tests/OpenWSFZ.Daemon.Tests/ExternalReportingServiceTests.cs` (18 sites). Remove
  from `test-delay-debt.md`.
- [ ] 3.2 Migrate `tests/OpenWSFZ.Daemon.Tests/CatPollingServiceTests.cs` (14 sites) and
  `CatPollingServiceFreqPersistTests.cs` (3 sites). Remove from `test-delay-debt.md`.
- [ ] 3.3 Migrate `tests/OpenWSFZ.Daemon.Tests/CatPttControllerTests.cs` (4 sites). Remove from
  `test-delay-debt.md`.
- [ ] 3.4 Full local regression on the affected files, 10 consecutive clean runs.
- [ ] 3.5 Run `python3 tools/pre_merge_check.py` clean.
- [ ] 3.6 Ship Phase 2 as its own PR.

## 4. Phase 3 — Remaining files across all four affected test projects

- [ ] 4.1 Migrate the small `Daemon.Tests` remainder: `SerialRtsDtrPttControllerTests.cs` (3),
  `DaemonStartupTests.cs` (2), `QsoAnswererServiceExternalReplyTests.cs` (2),
  `GracefulStopDelegationTests.cs` (2). Remove from `test-delay-debt.md`.
- [ ] 4.2 Migrate `tests/OpenWSFZ.Web.Tests/SystemRestartEndpointTests.cs` (4) and
  `AuthMiddlewareTests.cs` (1) — add `OpenWSFZ.TestSupport` as a `ProjectReference` to
  `OpenWSFZ.Web.Tests.csproj`. Remove from `test-delay-debt.md`.
- [ ] 4.3 Migrate `tests/OpenWSFZ.Ft8.Tests/LoggingPipelineTests.cs` (3) — add `OpenWSFZ.TestSupport`
  as a `ProjectReference` to `OpenWSFZ.Ft8.Tests.csproj`. Remove from `test-delay-debt.md`.
- [ ] 4.4 Review `tests/OpenWSFZ.Audio.Tests/CaptureManagerTests.cs` (5 sites, `Task.WhenAny
  (Task.Delay(N), otherTask)` shape) case-by-case per design.md's Open Questions — migrate to the
  shared library if it's the same synchronization-barrier risk, or document in
  `test-delay-debt.md`'s resolution notes why it's a materially different (safer) pattern that
  doesn't need migration. Either way, this file's status must be explicitly resolved, not silently
  left ambiguous. Add `OpenWSFZ.TestSupport` as a `ProjectReference` to `OpenWSFZ.Audio.Tests.csproj`
  if migration is needed.
- [ ] 4.5 Confirm `test-delay-debt.md` is now empty (or contains only explicitly-justified,
  reviewed exceptions per design.md's suppression-mechanism decision — not silent leftovers).
- [ ] 4.6 Full local regression across all four affected test projects, 10 consecutive clean runs.
- [ ] 4.7 Run `python3 tools/pre_merge_check.py` clean.
- [ ] 4.8 Ship Phase 3 as its own PR.

## 5. Closeout

- [ ] 5.1 Confirm every scenario in both delta specs
  (`specs/test-synchronization-reliability/spec.md`, `specs/ci-quality-gates/spec.md`) is satisfied
  by the shipped state of `main`.
- [ ] 5.2 `openspec validate --strict --all` passes.
- [ ] 5.3 Draft a short retrospective note (dev-tasks or memory) confirming the four originally
  confirmed flakes (N8 excluded — different root cause; F-003 excluded — different root cause;
  `WaitReport`/`WaitRr73` retry-bracket, `PttWatchdog` Disarm) are now covered by the shared library,
  and that Gate G10 has been green (no untracked-debt failures) since Phase 0 landed.
- [ ] 5.4 Archive this change per the standard `/opsx:archive` workflow.
