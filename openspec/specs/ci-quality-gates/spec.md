## Requirements

### Requirement: CI matrix on three operating systems

The CI workflow `.github/workflows/ci.yml` SHALL run on the matrix `{ windows-latest, ubuntu-latest, macos-latest }` for every push and every pull-request targeting `main`. Each matrix leg SHALL restore dependencies, build the solution, and run `dotnet test` against every test project.

#### Scenario: Workflow runs on push

- **WHEN** a commit is pushed to any branch
- **THEN** the workflow SHALL be triggered and SHALL run all three matrix legs to completion

#### Scenario: Workflow runs on pull-request

- **WHEN** a pull-request targeting `main` is opened or updated
- **THEN** the workflow SHALL be triggered and SHALL run all three matrix legs to completion

#### Scenario: Matrix leg failure blocks merge

- **WHEN** any matrix leg reports a non-zero exit on `dotnet build` or `dotnet test`
- **THEN** the CI workflow SHALL report failure and the pull-request SHALL NOT be mergeable to `main`

### Requirement: Build-and-test gate (G1)

The CI workflow SHALL enforce gate **G1** &mdash; build and test pass on all three operating systems. A non-zero exit on `dotnet build` or `dotnet test` on any OS SHALL fail the workflow.

#### Scenario: Failing unit test blocks merge

- **WHEN** a unit test in any project reports failure on any matrix leg
- **THEN** the workflow SHALL exit non-zero and the pull-request SHALL be blocked

### Requirement: Traceability gate (G3)

The CI workflow SHALL invoke `tools/TraceabilityCheck` on the Linux matrix leg only. A non-zero exit from the tool SHALL fail the workflow.

#### Scenario: Missing requirement mapping blocks merge

- **WHEN** a requirement ID in `REQUIREMENTS.md` is not referenced in any test display name in any test assembly built by the solution
- **THEN** the CI workflow SHALL report failure on the Linux leg and the pull-request SHALL be blocked

### Requirement: Licence-inventory gate (G5)

The CI workflow SHALL invoke `tools/LicenseInventoryCheck` on the Linux matrix leg only. A non-zero exit from the tool SHALL fail the workflow.

#### Scenario: Non-redistributable dependency blocks merge

- **WHEN** a NuGet reference or submodule under `/native/` has a licence that is not MIT-redistributable per the policy in the `dependency-licence-policy` capability
- **THEN** the CI workflow SHALL report failure on the Linux leg and the pull-request SHALL be blocked

### Requirement: Coverage reporting is informational

The CI workflow SHALL collect Coverlet coverage on the Linux matrix leg and upload a ReportGenerator-formatted HTML report as a build artefact. The workflow SHALL NOT fail on coverage percentage.

#### Scenario: Low coverage does not block merge

- **WHEN** the Linux coverage run reports any coverage percentage, including 0%
- **THEN** the CI workflow SHALL NOT fail solely on coverage and the report SHALL be available as a downloadable build artefact

### Requirement: Decoder-correctness gate (G6)

The CI workflow `.github/workflows/ci.yml` SHALL enforce gate **G6** &mdash; the real-signal fixture integration test (FR-029) runs as part of `dotnet test` on every push and every pull-request targeting `main`, on all three matrix legs. A failure of this test SHALL fail the workflow and block the merge. G6 is structurally active from the moment the real-signal fixture test is committed to `tests/OpenWSFZ.Ft8.Tests/`; no separate CI step is required because the test runs within the existing G1 `dotnet test` step. The gate prevents decoder changes from regressing real-signal decode recovery &mdash; a regression class the previous circular test suite could not detect.

#### Scenario: Decoder regression blocks merge on all legs

- **WHEN** a change causes the real-signal fixture integration test to fail on any matrix leg (Windows, Linux, or macOS)
- **THEN** the CI workflow SHALL exit non-zero and the pull-request SHALL NOT be mergeable to `main`

#### Scenario: Real-signal test runs on every change

- **WHEN** a commit is pushed to any branch or a pull-request targeting `main` is opened or updated
- **THEN** the real-signal fixture integration test SHALL be executed as part of the `dotnet test` step on all three matrix legs

### Requirement: Reproducible-evidence rule for decoder defects (NFR-016)

A decoder defect "root cause" SHALL be substantiated by a failing reproducible test over a committed real-signal WAV fixture before a corresponding fix is accepted. Live hardware smoke tests SHALL serve as acceptance/confirmation only and SHALL NOT be the primary diagnostic instrument.

#### Scenario: Root-cause claim requires a reproducible failing test

- **WHEN** a decoder defect is reported with a proposed root cause
- **THEN** a failing test over a committed WAV fixture that demonstrates the defect SHALL be added before the fix is reviewed for acceptance

#### Scenario: Live smoke test is confirmation, not diagnosis

- **WHEN** a decoder fix is proposed
- **THEN** its correctness SHALL be established by the reproducible fixture test, with the live smoke test used only to confirm end-to-end behaviour in the field

### Requirement: Inert placeholders for later gates

The CI workflow SHALL include inert workflow steps for the performance gate (**G2**) and the strict-UI-visibility gate (**G4**) that succeed when no performance tests or UI-visibility tests are present. These steps SHALL begin gating once their owning phases land tests under the appropriate trait.

#### Scenario: No performance tests present

- **WHEN** the CI workflow runs and no test in the solution is tagged `[Trait("tier", "performance")]`
- **THEN** the performance-gate step SHALL succeed silently

#### Scenario: No UI-visibility tests present

- **WHEN** the CI workflow runs and no test in the solution is tagged `[Trait("tier", "ui-visibility")]`
- **THEN** the UI-visibility-gate step SHALL succeed silently
