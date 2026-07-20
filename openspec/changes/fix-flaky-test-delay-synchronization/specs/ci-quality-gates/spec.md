## ADDED Requirements

### Requirement: Test-delay-synchronization gate (G10)

The CI workflow SHALL invoke a test-delay-synchronization lint (`tools/check_test_delay_sync.py`)
on the Linux matrix leg only, matching the placement of Gates G3/G5/G7/G8. The lint SHALL scan
every `.cs` file under `tests/**`, excluding `tests/OpenWSFZ.TestSupport/**` (the shared polling
library's own implementation, per the `test-synchronization-reliability` capability), for a bare
fixed-duration `Task.Delay(<numeric literal>)`. Any match not present in the companion test-delay
debt tracking file SHALL fail the workflow. This gate is blocking from the moment it lands — it does
not run in an advisory-only mode at any point — but it only fails on sites not already enumerated in
the debt file, so it never blocks on the pre-existing, already-tracked migration backlog.

#### Scenario: Untracked bare delay blocks merge

- **WHEN** a pull request introduces a bare `Task.Delay(<numeric literal>)` synchronization barrier
  in a test file under `tests/**` (excluding `tests/OpenWSFZ.TestSupport/**`) that is not listed in
  the test-delay debt tracking file
- **THEN** the CI workflow SHALL report failure on the Linux leg and the pull-request SHALL be
  blocked

#### Scenario: Debt-tracked bare delay does not block merge

- **WHEN** a bare `Task.Delay(<numeric literal>)` synchronization barrier exists in a test file and
  is explicitly listed, by file and matching text, in the test-delay debt tracking file
- **THEN** Gate G10 SHALL NOT fail the workflow on account of that site alone

#### Scenario: Migrating a debt-tracked site removes it from tracking

- **WHEN** a pull request replaces a previously debt-tracked bare delay with a shared-library
  polling helper call
- **THEN** the same pull request SHALL remove that site's entry from the test-delay debt tracking
  file, and Gate G10 SHALL continue to pass

#### Scenario: Shared library's own implementation is exempt

- **WHEN** a bare `Task.Delay(<numeric literal>)` appears inside `tests/OpenWSFZ.TestSupport/**`
  (the shared polling primitive's own internal implementation)
- **THEN** Gate G10 SHALL NOT flag it, since this is the one place such a delay is the correct
  implementation detail rather than a per-test synchronization shortcut
