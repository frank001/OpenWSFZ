## ADDED Requirements

### Requirement: Test-delay-synchronization gate (G10)

The CI workflow SHALL invoke a test-delay-synchronization lint (`tools/check_test_delay_sync.py`)
on the Linux matrix leg only, matching the placement of Gates G3/G5/G7/G8. The lint SHALL scan
every `.cs` file under `tests/**`, excluding `tests/OpenWSFZ.TestSupport/**` (the shared polling
library's own implementation, per the `test-synchronization-reliability` capability), for a bare
fixed-duration delay whose argument is a numeric literal, in any of `Task.Delay(<numeric literal>)`,
`Task.Delay(TimeSpan.From*(<numeric literal>))`, `Thread.Sleep(<numeric literal>)`, or
`Thread.Sleep(TimeSpan.From*(<numeric literal>))` — the bare-literal and TimeSpan-factory spellings
of both the async and synchronous delay APIs are equally matched, since all four are the same
fixed-duration guess wearing a different syntactic coat. Any match not present in the companion
test-delay debt tracking file SHALL fail the workflow. This gate is blocking from the moment it
lands — it does not run in an advisory-only mode at any point — but it only fails on sites not
already enumerated in the debt file, so it never blocks on the pre-existing, already-tracked
migration backlog.

#### Scenario: Untracked bare delay blocks merge

- **WHEN** a pull request introduces a bare fixed-duration delay synchronization barrier — whether
  `Task.Delay(<numeric literal>)`, `Task.Delay(TimeSpan.From*(<numeric literal>))`,
  `Thread.Sleep(<numeric literal>)`, or `Thread.Sleep(TimeSpan.From*(<numeric literal>))` — in a
  test file under `tests/**` (excluding `tests/OpenWSFZ.TestSupport/**`) that is not listed in the
  test-delay debt tracking file
- **THEN** the CI workflow SHALL report failure on the Linux leg and the pull-request SHALL be
  blocked

#### Scenario: Debt-tracked bare delay does not block merge

- **WHEN** a bare fixed-duration delay synchronization barrier, in any of the shapes above, exists
  in a test file and is explicitly listed, by file and matching text, in the test-delay debt
  tracking file
- **THEN** Gate G10 SHALL NOT fail the workflow on account of that site alone

#### Scenario: Migrating a debt-tracked site removes it from tracking

- **WHEN** a pull request replaces a previously debt-tracked bare delay with a shared-library
  polling helper call
- **THEN** the same pull request SHALL remove that site's entry from the test-delay debt tracking
  file, and Gate G10 SHALL continue to pass

#### Scenario: Shared library's own implementation is exempt

- **WHEN** a bare fixed-duration delay, in any of the shapes above, appears inside
  `tests/OpenWSFZ.TestSupport/**` (the shared polling primitive's own internal implementation)
- **THEN** Gate G10 SHALL NOT flag it, since this is the one place such a delay is the correct
  implementation detail rather than a per-test synchronization shortcut

#### Scenario: A variable or parameter argument is not a fixed-duration delay

- **WHEN** any of the four call shapes above is invoked with a variable or parameter — e.g.
  `Task.Delay(interval)`, `Task.Delay(TimeSpan.FromMilliseconds(interval))`,
  `Thread.Sleep(interval)`, or `Thread.Sleep(TimeSpan.FromMilliseconds(interval))` — rather than a
  numeric literal
- **THEN** Gate G10 SHALL NOT flag it, since a variable/parameter argument is already the correct
  post-migration shape (the caller computes or is handed the wait, rather than the test guessing a
  literal duration), not the anti-pattern this gate exists to catch
