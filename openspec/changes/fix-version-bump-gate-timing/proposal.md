**User-facing:** no

## Why

Gate G9b (`tools/check_version_bump.py`, backing the `ci-quality-gates` capability's
"Version-governance gate (G9)" requirement) only checks `proposal.md` files newly added under
`openspec/changes/archive/` — i.e. it enforces the mandatory VERSION bump exclusively at archive
time. `REQUIREMENTS.md` rows 1.35/1.36/1.38/1.39 show this repeatedly producing the same defect:
a user-facing change merges to `main` fully implemented, sits for days without a VERSION bump,
and the bump only lands later when QA happens to archive it — because that is the only point
anything actually checks. The Captain has now directed that the version bump is only acceptable
**pre-merge**: it must land in the same pull request that merges the feature's implementation to
`main`, not deferred to a later, separate archiving pull request. The gate must be fixed to
enforce that, or the same drift recurs on the next change.

## What Changes

- `tools/check_version_bump.py` — check the **first pull request that introduces a given
  change's `proposal.md` into `main`'s history at all** (whether that PR adds it under the active
  `openspec/changes/<name>/` path or, less commonly, directly under
  `openspec/changes/archive/<date>-<name>/`), not only PRs that add it under `archive/`. A later
  PR that purely relocates an already-introduced change's `proposal.md` from the active path to
  the archive path (ordinary archiving) is explicitly **not** re-checked — it was already
  accounted for at first introduction, and re-checking it would demand a second, spurious bump
  for a feature already bumped once.
- `openspec/specs/ci-quality-gates/spec.md` — update the "Version-governance gate (G9)"
  requirement's second condition and its scenarios to describe merge-time (first-introduction)
  enforcement instead of archive-time enforcement.
- `.github/workflows/ci.yml` — rename the G9b step to reflect the corrected timing; no change to
  which script runs or when the job runs.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `ci-quality-gates`: the "Version-governance gate (G9)" requirement's mandatory-bump condition
  changes from "on user-facing archive" to "on first merge of a user-facing change's proposal
  into `main`".

## Impact

- `tools/check_version_bump.py` (rewritten detection logic; no CLI signature change).
- `.github/workflows/ci.yml` (step name/comment only; job trigger and script invocation
  unchanged).
- `openspec/specs/ci-quality-gates/spec.md` (via this change's delta spec).
- No product/application code touched; no VERSION bump required for this change itself
  (CI/tooling-only, per the existing minor-version-per-user-facing-feature rule's own carve-out).
