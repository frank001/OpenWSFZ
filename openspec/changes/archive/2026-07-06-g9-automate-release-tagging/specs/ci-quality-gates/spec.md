## MODIFIED Requirements

### Requirement: Version-governance gate (G9)

The CI workflow SHALL run a `version-governance` job on every pull-request targeting `main`,
with a full-history (`fetch-depth: 0`) checkout, that enforces two conditions and fails the
workflow if either is violated:

1. **Doc/VERSION consistency** — the version cited by the anchor sentence in `README.md` and in
   `REQUIREMENTS.md` (see the `release-versioning` capability's documentation requirement) SHALL
   equal the content of `VERSION`.
2. **Mandatory bump on user-facing archive** — for every `proposal.md` newly added under
   `openspec/changes/archive/` by the pull request (relative to `main`), the file SHALL declare
   `**User-facing:**` as either `yes` or `no`; if any such file declares `yes`, `VERSION` SHALL
   differ from its content on `main`.

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

#### Scenario: User-facing archive without a version bump blocks merge

- **WHEN** a pull request adds a `proposal.md` under `openspec/changes/archive/` declaring `**User-facing:** yes`, and `VERSION` is unchanged relative to `main`
- **THEN** the `version-governance` job SHALL fail with a message naming the offending change and instructing the author to bump `VERSION`

#### Scenario: Missing or malformed declaration blocks merge

- **WHEN** a pull request adds a `proposal.md` under `openspec/changes/archive/` that lacks a `**User-facing:**` line, or whose value is neither `yes` nor `no`
- **THEN** the `version-governance` job SHALL fail with a message instructing the author to add the declaration

#### Scenario: Non-feature archive with no bump passes

- **WHEN** every `proposal.md` newly added under `openspec/changes/archive/` by the pull request declares `**User-facing:** no`
- **THEN** the `version-governance` job SHALL pass regardless of whether `VERSION` changed

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
