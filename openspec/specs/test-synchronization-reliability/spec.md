# test-synchronization-reliability Specification

## Purpose
TBD - created by archiving change fix-flaky-test-delay-synchronization. Update Purpose after archive.
## Requirements
### Requirement: Shared polling helper library

The solution SHALL provide a shared, non-test class library project (`OpenWSFZ.TestSupport`) that
exposes a poll-until-condition primitive and typed convenience wrappers for the synchronization
shapes used across the test suites (state/value equality, boolean-flag, "at least one call
received," "at least N calls received"). Any test project that needs to wait for an asynchronous
condition to become true SHALL use this shared library rather than defining its own private,
duplicated polling helper.

#### Scenario: Test waits for a state transition via the shared library

- **WHEN** a test needs to wait for a service's observable state to reach an expected value before
  asserting against it
- **THEN** the test SHALL call a shared-library polling helper (directly or via a thin wrapper) that
  polls the condition at a bounded interval until it is satisfied or a timeout elapses, rather than
  awaiting a fixed-duration delay and assuming the condition has been reached

#### Scenario: Polling helper times out with a diagnosable message

- **WHEN** a shared-library polling helper's condition is not satisfied before its timeout elapses
- **THEN** the helper SHALL throw a `TimeoutException` (or fail the assertion, for boolean-style
  wrappers) whose message identifies what was expected and how long was waited, rather than the
  test failing later on an unrelated assertion with no indication that a wait had timed out

#### Scenario: Existing duplicated helpers are consolidated, not left in place

- **WHEN** a test file already defines its own private polling helper with the same shape as one
  provided by the shared library (e.g. `QsoAnswererServiceTests.WaitForStateAsync` and
  `QsoCallerServiceTests.WaitForStateAsync`, independently duplicated)
- **THEN** the file's migration SHALL delete the private duplicate and use the shared library
  helper instead, rather than leaving both in place

### Requirement: No untracked fixed-delay test synchronization

Test code (outside the shared library's own implementation) SHALL NOT use a bare fixed-duration
`Task.Delay` with a numeric literal as a synchronization barrier before an assertion, unless the
specific call site is explicitly enumerated as pre-existing, tracked debt pending migration. New
test code SHALL NOT introduce a new instance of this pattern under any circumstance.

#### Scenario: New test code uses a bare fixed delay as a synchronization barrier

- **WHEN** a pull request adds a test file (or modifies an existing one) containing a bare
  `Task.Delay(<numeric literal>)` used to wait for an asynchronous condition, and that exact site is
  not already present in the tracked debt list
- **THEN** the change SHALL be blocked (see the `ci-quality-gates` capability's Gate G10) until the
  delay is replaced with a shared-library polling helper or the author provides a reviewed,
  justified exception

#### Scenario: Pre-existing tracked debt is tolerated until migrated

- **WHEN** a test file contains a bare fixed-duration delay that is explicitly listed in the
  project's test-delay debt tracking file
- **THEN** that specific site SHALL NOT block merges on its own account, until it is migrated and
  removed from the debt list by a dedicated follow-up change

### Requirement: The polling primitive itself is verified by deterministic tests

The shared library's core polling primitive SHALL have its own automated test coverage proving its
timeout, success, and interval behavior deterministically, without relying on the same
fixed-delay-guessing pattern this capability exists to eliminate.

#### Scenario: Primitive returns as soon as its condition becomes true

- **WHEN** the polling primitive is given a condition that becomes true after a controlled, known
  number of poll iterations
- **THEN** a test SHALL assert that the primitive returns promptly once that condition is met,
  without waiting for its full timeout

#### Scenario: Primitive times out on a condition that never becomes true

- **WHEN** the polling primitive is given a condition that is designed to never become true, with an
  explicit short timeout
- **THEN** a test SHALL assert that the primitive throws its timeout failure once that timeout
  elapses, and this test SHALL NOT itself rely on an unrelated fixed delay to determine pass/fail

