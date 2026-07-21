# ci-quality-gates Specification

## Purpose

Specifies the CI pipeline's quality gates: the three-OS build/test matrix, the
build-and-test (G1), traceability (G3), licence-inventory (G5), decoder-correctness (G6),
secrets-scan (G7), OpenSpec-validation (G8), and version-governance (G9) gates, informational
coverage reporting, the reproducible-evidence rule for decoder defects (NFR-016), and reserved
placeholders for gates not yet active.
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

### Requirement: Secrets-scan gate (G7)

The CI workflow SHALL invoke `gitleaks detect` against the full repository history on the Linux matrix leg only, implementing NFR-017 (security — secrets scan gate). A non-zero exit from `gitleaks` SHALL fail the workflow.

#### Scenario: Detected secret blocks merge

- **WHEN** `gitleaks detect` finds a credential, private key, or other secret anywhere in the scanned commit history
- **THEN** the CI workflow SHALL report failure on the Linux leg and the pull-request SHALL be blocked

### Requirement: OpenSpec-validation gate (G8)

The CI workflow SHALL invoke `openspec validate --strict --all` (a version-pinned `npx` invocation, not `@latest`) on the Linux matrix leg only. A non-zero exit from the tool SHALL fail the workflow. This gate exists because no automated check previously verified that every spec under `openspec/specs/` and every active change under `openspec/changes/` satisfies the OpenSpec schema (missing `## Purpose`/`## Requirements` sections, a requirement lacking a SHALL/MUST keyword or a scenario, etc.) — 24 of 42 specs were found failing strict validation on 2026-07-05, discovered only by an ad-hoc manual run during an unrelated change, not by any process that required it.

#### Scenario: Invalid spec or change blocks merge

- **WHEN** any spec under `openspec/specs/` or any active change under `openspec/changes/` fails `openspec validate --strict`
- **THEN** the CI workflow SHALL report failure on the Linux leg and the pull-request SHALL be blocked

#### Scenario: Gate runs regardless of which files changed

- **WHEN** a pull-request touches any files at all (not only `openspec/`)
- **THEN** Gate G8 SHALL still run `openspec validate --strict --all` against the full repository, since a spec can drift out of validity independent of the PR's own diff

### Requirement: Version-governance gate (G9)

The CI workflow SHALL run a `version-governance` job on every pull-request targeting `main`,
with a full-history (`fetch-depth: 0`) checkout, that enforces two conditions and fails the
workflow if either is violated:

1. **Doc/VERSION consistency** — the version cited by the anchor sentence in `README.md` and in
   `REQUIREMENTS.md` (see the `release-versioning` capability's documentation requirement) SHALL
   equal the content of `VERSION`.
2. **Mandatory bump on first merge of a user-facing change** — for every `proposal.md` newly
   added anywhere under `openspec/changes/` (whether at the active `openspec/changes/<name>/`
   path or directly under `openspec/changes/archive/<date>-<name>/`) by the pull request
   (relative to `main`), the file SHALL declare `**User-facing:**` as either `yes` or `no`; if any
   such file declares `yes`, `VERSION` SHALL differ from its content on `main`. A `proposal.md`
   added under `openspec/changes/archive/<date>-<name>/` in this pull request SHALL be exempt from
   this condition if a `proposal.md` for the same change name already existed at the active
   `openspec/changes/<name>/` path on `main` before this pull request — that change was already
   subject to this condition when it first entered `main`'s history, and an ordinary archiving
   pull request that merely relocates it SHALL NOT be required to bump `VERSION` a second time.

A non-zero exit from either check SHALL fail the workflow and SHALL block the pull request from
merging.

In addition, the CI workflow SHALL run a `tag-release-version` job on every push to `main` (after
the build-and-test matrix succeeds) that cuts and pushes an annotated git tag named `v<VERSION>`
if a tag by that exact name does not already exist. This job is not a required branch-protection
status check — it runs after a commit is already on `main` and has nothing to block — but its
absence of an existing tag for the current `VERSION` value SHALL be treated as transient (resolved
by the next push to `main`), not as a standing defect requiring manual intervention.

#### Scenario: Doc/VERSION drift blocks merge

- **WHEN** `VERSION` and the anchor sentence in `README.md` or `REQUIREMENTS.md` disagree on the pull request's resulting state
- **THEN** the `version-governance` job SHALL fail with a message identifying which document is out of sync

#### Scenario: User-facing change merged without a version bump blocks merge

- **WHEN** a pull request adds a `proposal.md` under `openspec/changes/<name>/` (the active path) declaring `**User-facing:** yes`, and `VERSION` is unchanged relative to `main`
- **THEN** the `version-governance` job SHALL fail with a message naming the offending change and instructing the author to bump `VERSION` in this same pull request

#### Scenario: Missing or malformed declaration blocks merge

- **WHEN** a pull request adds a `proposal.md` under `openspec/changes/` (active or archived path) that lacks a `**User-facing:**` line, or whose value is neither `yes` nor `no`
- **THEN** the `version-governance` job SHALL fail with a message instructing the author to add the declaration

#### Scenario: Non-feature change with no bump passes

- **WHEN** every `proposal.md` newly added under `openspec/changes/` by the pull request declares `**User-facing:** no`
- **THEN** the `version-governance` job SHALL pass regardless of whether `VERSION` changed

#### Scenario: Propose-and-archive-in-one-PR without a version bump blocks merge

- **WHEN** a pull request adds a `proposal.md` directly under `openspec/changes/archive/<date>-<name>/` declaring `**User-facing:** yes`, no `proposal.md` for that change name existed at the active path on `main` before this pull request, and `VERSION` is unchanged relative to `main`
- **THEN** the `version-governance` job SHALL fail with a message naming the offending change and instructing the author to bump `VERSION` in this same pull request

#### Scenario: Ordinary archiving of an already-bumped change does not require a second bump

- **WHEN** a pull request adds a `proposal.md` under `openspec/changes/archive/<date>-<name>/` declaring `**User-facing:** yes`, and a `proposal.md` for that same change name already existed at the active `openspec/changes/<name>/` path on `main` before this pull request
- **THEN** the `version-governance` job SHALL pass regardless of whether `VERSION` changed in this pull request

#### Scenario: Gate does not run on direct pushes

- **WHEN** a commit is pushed directly to a branch outside the context of a pull request targeting `main`
- **THEN** the `version-governance` job SHALL be skipped, since there is no base ref to diff against

#### Scenario: Tag cut automatically after a version bump reaches main

- **WHEN** a push to `main` results in `VERSION` containing a value with no corresponding annotated tag
- **THEN** the `tag-release-version` job SHALL create and push an annotated tag named `v<VERSION>` pointing at that commit, without any manual step

#### Scenario: Tag-cutting is idempotent

- **WHEN** a push to `main` occurs and an annotated tag named `v<VERSION>` already exists
- **THEN** the `tag-release-version` job SHALL exit successfully without creating or pushing a duplicate tag

#### Scenario: Tag push does not re-trigger the workflow

- **WHEN** the `tag-release-version` job pushes a new tag ref
- **THEN** that push SHALL NOT itself trigger a new run of the CI workflow, since the workflow's `push` trigger is scoped to branch refs only

### Requirement: Inert placeholders for later gates

The CI workflow SHALL include inert workflow steps for the performance gate (**G2**) and the strict-UI-visibility gate (**G4**) that succeed when no performance tests or UI-visibility tests are present. These steps SHALL begin gating once their owning phases land tests under the appropriate trait.

#### Scenario: No performance tests present

- **WHEN** the CI workflow runs and no test in the solution is tagged `[Trait("tier", "performance")]`
- **THEN** the performance-gate step SHALL succeed silently

#### Scenario: No UI-visibility tests present

- **WHEN** the CI workflow runs and no test in the solution is tagged `[Trait("tier", "ui-visibility")]`
- **THEN** the UI-visibility-gate step SHALL succeed silently

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

