**User-facing:** no

## Why

The `release-versioning` capability already names the annotated git tag as one of the surfaces
that must agree with the canonical `VERSION` file, but its own text carves out an exception:
*"the git tag is cut manually and SHALL NOT be forgotten."* It was forgotten within one day of
that sentence being written. `VERSION` moved `0.30` → `0.31` in commit `d36f711` (archiving
`adopt-canonical-version-source` itself, per the minor-version-per-user-facing-feature rule the
same change introduced), but no `v0.31` tag was ever cut — the last annotated tag on the repo
remains `v0.30`, pointed at the prior commit `547b05c`. Discovered 2026-07-06 when the Captain
asked why GitHub's tag list disagreed with the README's stated version.

The original change's `design.md` explicitly deferred this ("Automating git tag creation/pushing
on merge... is logged as a manual follow-up in tasks.md instead," Non-Goals #1), accepting the
risk as low-frequency/low-risk. In practice the manual step lapsed on its very first opportunity,
which is exactly the failure mode gate G9 exists to design out of every *other* version surface.
The Captain has now asked that tag-cutting be folded into G9 rather than left as a remembered
chore.

## What Changes

- Add a new CI job, `tag-release-version`, to `.github/workflows/ci.yml`. It runs on every push
  to `main` (after the `build-test` matrix passes), reads `VERSION`, and — if an annotated tag
  matching `v<VERSION>` does not already exist — creates and pushes one. Idempotent: a `main`
  push where the tag already exists is a fast no-op, so ordinary merges that don't touch
  `VERSION` cost one cheap `git rev-parse` check, not a spurious tag.
- Add `tools/cut_version_tag.py`, following the existing `check_version_docs.py` /
  `check_version_bump.py` style (dependency-free, clear stdout progress, actionable stderr on
  failure, a `--dry-run` flag for local verification without mutating the remote).
- Narrow the workflow's `push` trigger from unfiltered (`push:` with no filter, which matches
  both branch and tag ref updates) to `push: branches: ['**']`, so pushing the new tag doesn't
  itself re-trigger the full three-OS build matrix. This is a direct consequence of introducing
  the first CI step that pushes tags — the redundant-trigger risk didn't exist before because
  nothing in CI ever pushed a tag.
- Update the `release-versioning` spec's "Version consistency across all surfaces" requirement to
  drop the "cut manually, SHALL NOT be forgotten" language now that it's automated.
  Update the `ci-quality-gates` spec's gate G9 requirement to document the new tag-cutting job
  alongside the two existing pull-request-time checks.
- As an immediate, one-time consequence of this change reaching `main`: the very next push to
  `main` (this change's own merge) will find `VERSION` already at `0.31` with no `v0.31` tag, and
  the new job will cut it automatically — closing the drift that prompted this change without a
  separate manual `git tag` command.

## Capabilities

### Modified Capabilities
- `ci-quality-gates`: gate G9 gains a third leg — an automated post-merge tag-cutting job — in
  addition to the existing doc/VERSION-consistency and mandatory-bump checks.
- `release-versioning`: the "Version consistency across all surfaces" requirement no longer
  treats the git tag as a manual, easily-forgotten step; it is now CI-automated like every other
  surface in that requirement.

## Impact

- **CI**: `.github/workflows/ci.yml` gains a `tag-release-version` job and a narrowed `push`
  trigger.
- **Tooling**: new `tools/cut_version_tag.py`.
- **Docs**: `openspec/specs/ci-quality-gates/spec.md` and
  `openspec/specs/release-versioning/spec.md` updated at archive time.
- **Immediate effect**: a `v0.31` tag is cut automatically the first time this change's merge
  commit reaches `main`, with no further manual action required.
