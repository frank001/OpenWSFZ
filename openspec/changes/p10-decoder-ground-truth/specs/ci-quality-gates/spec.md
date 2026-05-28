## ADDED Requirements

### Requirement: Decoder-correctness gate (G6)

The CI workflow `.github/workflows/ci.yml` SHALL enforce gate **G6** — the real-signal fixture integration test (from the `decoder-ground-truth` capability) runs as part of `dotnet test` on every push and every pull-request targeting `main`. A failure of this test SHALL fail the workflow and block the merge. This gate exists to prevent decoder changes from regressing real-signal decode recovery, a failure mode the previous (circular) test suite could not detect.

#### Scenario: Decoder regression blocks merge

- **WHEN** a change causes the real-signal fixture integration test to fail on any matrix leg
- **THEN** the CI workflow SHALL exit non-zero and the pull-request SHALL NOT be mergeable to `main`

#### Scenario: Real-signal test runs on every change

- **WHEN** a commit is pushed or a pull-request targeting `main` is opened or updated
- **THEN** the real-signal fixture integration test SHALL be executed as part of the build-and-test gate

### Requirement: Reproducible-evidence rule for decoder defects

A decoder defect "root cause" SHALL be substantiated by a reproducible failing test over a committed real-signal WAV fixture before a corresponding fix is accepted. Live hardware smoke tests SHALL serve as acceptance/confirmation only and SHALL NOT be the primary instrument for diagnosing decoder defects.

#### Scenario: Root-cause claim requires a reproducible test

- **WHEN** a decoder defect is reported with a proposed root cause
- **THEN** a failing test over a committed WAV fixture SHALL be added that demonstrates the defect before a fix is reviewed for acceptance

#### Scenario: Live smoke test is confirmation, not diagnosis

- **WHEN** a decoder fix is proposed
- **THEN** its correctness SHALL be established by the reproducible fixture test, with the live smoke test used only to confirm end-to-end behaviour
