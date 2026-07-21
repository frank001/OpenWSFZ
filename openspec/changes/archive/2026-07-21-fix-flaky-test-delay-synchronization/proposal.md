## Why

Fixed-duration `Task.Delay(<literal>)` calls used as ad hoc test synchronization barriers are the
dominant cause of the CI flakiness that has repeatedly disrupted development over the past several
days (N8 on 2026-07-18; PR #93 and PR #94 both on 2026-07-20). These delays pass reliably on an
idle dev machine but are timing-sensitive under real CI load (shared runners, parallel push+
pull_request jobs for the same commit, GC pauses, thread-pool contention), and each occurrence has
so far been found and fixed reactively, one at a time, only after it actually fails a build. A
repo-wide audit found roughly 150 more sites sharing the identical risky shape, concentrated in a
few large files, with no shared test-infrastructure project anywhere in the solution to make the
correct (polling) pattern easier to reach for than the risky one. This change pays that debt down
systematically instead of continuing to chase individual instances after the fact.

## What Changes

- Introduce a shared, reusable test-synchronization helper library (a plain class library, not
  another `IsTestProject` test project) providing a small family of poll-until-condition helpers
  built on one common primitive, so writing a correct wait is no more effort than writing
  `await Task.Delay(150)` was.
- Migrate the ~150 audited fixed-delay call sites across `OpenWSFZ.Daemon.Tests`,
  `OpenWSFZ.Web.Tests`, `OpenWSFZ.Ft8.Tests`, and `OpenWSFZ.Audio.Tests` to the shared helpers, in
  phases ordered by risk/concentration (see `tasks.md`), de-duplicating the two existing
  hand-copied `WaitForStateAsync`/`WaitForKeyingAsync` implementations in `QsoAnswererServiceTests.cs`
  and `QsoCallerServiceTests.cs` onto the shared library in the process.
- Fix the one already-identified, not-yet-fixed live flake this same audit turned up:
  `PttWatchdogTests.Disarm_BeforeTimeout_CallbackNeverInvoked`.
- Add a new mechanical CI gate (**G10**) that flags a bare `await Task.Delay(<int-literal>)` in a
  test file outside a recognized polling helper. It launches in **advisory (non-blocking) mode** —
  mirroring how gates **G2**/**G4** already exist inert in this codebase until their owning work
  lands — and flips to blocking once the migration phases in `tasks.md` are complete, so no new
  instances of the fixed-pattern can be added once the paydown is finished, without blocking
  in-flight migration work in the meantime.
- **BREAKING**: none — this is test-only and CI-tooling-only; no production/runtime behavior
  changes.

## Capabilities

### New Capabilities

- `test-synchronization-reliability`: defines the shared polling-helper library, the requirement
  that test synchronization use poll-until-condition rather than fixed delays, and the phased
  migration/tracking mechanism (a debt-tracking file analogous to `traceability-debt.md`) for the
  sites not yet migrated.

### Modified Capabilities

- `ci-quality-gates`: adds Gate **G10** (test-delay-synchronization lint), initially advisory,
  documented alongside the existing **G2**/**G4** inert-placeholder pattern.

## Impact

- **New**: a class library project (exact name/location decided in `design.md`) referenced by
  `OpenWSFZ.Daemon.Tests`, `OpenWSFZ.Web.Tests`, `OpenWSFZ.Ft8.Tests`, and `OpenWSFZ.Audio.Tests`.
- **New**: a lint script under `tools/` (matching the existing style of
  `tools/check_screenshot_task_order.py` and the UDP-capture-margin lint), wired into
  `tools/pre_merge_check.py` and `.github/workflows/ci.yml`.
- **Modified**: `tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs` (58 sites + de-duplicated
  helpers), `QsoCallerServiceTests.cs` (45 sites + de-duplicated helpers),
  `ExternalReportingServiceTests.cs` (18), `CatPollingServiceTests.cs` (14),
  `PttWatchdogTests.cs` (8, including the live flake fix), `CatPttControllerTests.cs` (4),
  `CatPollingServiceFreqPersistTests.cs` (3), `SerialRtsDtrPttControllerTests.cs` (3),
  `DaemonStartupTests.cs` (2), `QsoAnswererServiceExternalReplyTests.cs` (2),
  `GracefulStopDelegationTests.cs` (2); `tests/OpenWSFZ.Web.Tests/SystemRestartEndpointTests.cs` (4),
  `AuthMiddlewareTests.cs` (1); `tests/OpenWSFZ.Ft8.Tests/LoggingPipelineTests.cs` (3);
  `tests/OpenWSFZ.Audio.Tests/CaptureManagerTests.cs` (5, reviewed case-by-case — some already use
  a `Task.WhenAny` bounded-wait shape that may not need the same treatment).
- **Not in scope**: `N8` (`DecodeFilterStoreAdmitNewValuesTests` — a test-design/assertion flaw, not
  a synchronization-timing bug) and `F-003` (native FT8 decoder margin sensitivity, already resolved
  separately) are different root causes and are explicitly excluded from this change's mechanical
  migration.
