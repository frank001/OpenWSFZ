## Context

`release-versioning`'s "Version consistency across all surfaces" requirement lists the annotated
git tag as one of the surfaces that must agree with `VERSION`, but exempts it from automation:
*"the git tag is cut manually and SHALL NOT be forgotten."* `adopt-canonical-version-source`'s own
`design.md` made this an explicit Non-Goal, reasoning that tag automation "has its own
permission/race-condition surface not worth opening for a once-per-feature action." That
reasoning turned out to be wrong in practice within a single day: `VERSION` bumped to `0.31` in
the same PR that formalised the manual-tag convention, the tag was not cut, and nobody noticed
until the Captain asked about it directly. Given the project already has a working precedent for
CI pushing to the repo with `contents: write` (the `commit-native-binaries` job pushes a branch
and opens a PR), extending that same permission to push a lightweight tag ref is a small
increment, not a new category of risk.

## Goals / Non-Goals

**Goals:**
- Every push to `main` where `VERSION` has no corresponding tag yet results in that tag being
  cut and pushed automatically, with no human step required.
- The mechanism is idempotent and side-effect-free when the tag already exists, so it can safely
  run unconditionally on every push to `main` without an extra "did VERSION change" pre-check
  job (unlike `commit-native-binaries`, which does need `detect-native-changes` because its
  underlying rebuild is expensive and non-deterministic across runners — tag cutting is neither).
- Pushing the new tag must not itself trigger a redundant full CI run.

**Non-Goals:**
- Retiring or backfilling tags for versions between `v0.30` and `v0.31` that never existed as a
  release point in their own right (there wasn't one — `0.31` superseded `0.30` within the same
  day, no commit on `main` was ever released at an intermediate version). Only the tag for the
  *current* `VERSION` value is cut.
- Deleting or renaming the pre-existing `v0.11`/`v0.30` tags — out of scope, no change requested.
- Signing tags (GPG-signed annotated tags). The existing commit history is not GPG-signed either;
  adding tag signing would be a separate, larger change to the repo's signing posture.

## Decisions

**1. New job `tag-release-version`, not an extension of the existing `version-governance` job.**
`version-governance` (gate G9's existing two checks) runs `if: github.event_name ==
'pull_request'` and diffs the PR branch against its base ref — there is no base ref on a direct
push, and the job is explicitly documented as skipped on push (`ci-quality-gates` spec, "Gate
does not run on direct pushes"). Tag-cutting is the opposite: it only makes sense *after* a merge
lands on `main`, when `HEAD` is the release point. Bolting a second, incompatible trigger
condition onto one job would make its `if:` logic harder to read than two small single-purpose
jobs. This mirrors the existing precedent of `detect-native-changes`/`commit-native-binaries`
being separate from `build-test` despite all being push-triggered.

**2. `needs: [build-test]`, gating the tag on a green three-OS matrix.**
A tag is meant to mark a working release point; cutting one against a commit that hasn't passed
its own build/test matrix would defeat that purpose. This mirrors `commit-native-binaries`'s
`needs: [build-test, detect-native-changes]`.

**3. Idempotency check via `git rev-parse --verify --quiet refs/tags/v<VERSION>`, no separate
pre-check job.** Unlike the native-binary rebuild (expensive, and non-deterministic across
runners per lesson 26 — see `project-state-2026-07.md`), checking for a tag's existence is a
single, cheap, deterministic git command. Running it unconditionally on every push to `main` costs
one `git rev-parse` in the overwhelming common case (tag already exists) and only actually creates
a tag on the rare push where `VERSION` just changed. A `detect-native-changes`-style gating job
would be pure overhead here.

**4. Push-trigger narrowed to `branches: ['**']`.**
GitHub Actions' `on: push` with no filter matches both branch-ref and tag-ref pushes. Before this
change nothing in CI ever pushed a tag, so this ambiguity was harmless. Once `tag-release-version`
pushes `refs/tags/v0.31`, that push is itself a `push` event and would re-trigger the whole
workflow (a full three-OS `build-test` matrix, wastefully, since none of the other push-gated jobs
key off `github.ref == 'refs/heads/main'` matching — a tag ref never satisfies that comparison, so
no infinite loop, but `build-test` itself has no such guard and would run needlessly). Restricting
the trigger to `branches: ['**']` (all branches, no tags) is the minimal fix, added in the same
change that introduces the tag push, so the two land together rather than the waste being
discovered separately later.

**5. `tools/cut_version_tag.py` follows the `check_version_docs.py`/`check_version_bump.py`
house style** (dependency-free stdlib Python, explicit exit codes, actionable stderr) rather than
inlining the logic as workflow-embedded bash, for the same reason those two scripts aren't inlined
either: it is independently testable (including the `--dry-run` flag, exercised locally in
`tasks.md` before trusting it in CI) and keeps `ci.yml` from growing another multi-line bash
block that's awkward to unit-reason-about in a code review.

**6. Tag message references gate G9, not the PR/issue number.**
The annotated tag's message is a fixed template (`v<VERSION> — cut automatically by CI gate G9
(release-versioning capability)`), not a per-release changelog. This keeps the automation
simple — the tag is a version marker, not a release-notes artifact; anyone wanting release notes
already has `REQUIREMENTS.md`'s changelog and the OpenSpec archive history.

## Risks / Trade-offs

- **[Risk]** A `GITHUB_TOKEN`-authenticated push re-triggering this same workflow, wasting a full
  three-OS matrix run. GitHub's documentation claims `GITHUB_TOKEN`-originated pushes don't
  re-trigger workflows, but this repo has already falsified that in practice: lesson 25
  (`project-state-2026-07.md`) found the `commit-native-binaries` job's own bot-authored branch
  push *did* trigger a new run, which is why that job carries an explicit
  `github.actor != 'github-actions[bot]'` guard rather than relying on the documented behaviour.
  The tag push this change adds has no equivalent actor guard available to it (the tag-cutting job
  itself is what would be doing the pushing), so the safer fix is removing tag refs from the
  trigger surface entirely. Mitigation: Decision 4's `branches: ['**']` filter does exactly that —
  it is a push-event *ref-shape* filter, so it applies regardless of which actor performs the
  push.
- **[Risk]** Race between two merges to `main` in close succession, both attempting to cut the
  same tag. → Mitigation: `git push origin refs/tags/vX.Y` fails loudly (non-fast-forward /
  already-exists) if a concurrent run wins the race first; the job fails but does not corrupt
  state, and a failed tag-push on a commit that isn't actually the one needing a new tag (i.e. the
  losing run's own `HEAD` already has an existing tag by the time it retries) is expected to
  self-resolve on the *next* push once the idempotency check sees the tag now exists. Accepted
  as low-probability (tag-worthy `VERSION` bumps are, by the minor-version-per-feature rule,
  already infrequent — at most one per user-facing archive) and low-consequence (a failed CI job
  on this one job, not a merge block, since `tag-release-version` is not a required status check
  for branch protection — see tasks.md).
- **[Trade-off]** The job is not added as a required branch-protection status check (unlike gate
  G9's `version-governance`). Tagging is a post-merge convenience, not a merge gate — there is
  nothing for it to block, since it only ever runs after a commit is already on `main`.

## Migration Plan

1. Add `tools/cut_version_tag.py`.
2. Add the `tag-release-version` job to `.github/workflows/ci.yml`; narrow the `push` trigger to
   `branches: ['**']`.
3. Verify locally with `--dry-run` against the current repo state (expect: "would create and push
   v0.31").
4. Merge to `main`. The merge's own push event triggers the new job, which cuts and pushes `v0.31`
   — closing the drift that motivated this change, with no separate manual `git tag` command.
5. Confirm on GitHub that `v0.31` now exists and points at the merge commit.

## Open Questions

None — the Captain's instruction ("include it in G9; the tag should reflect the actual version")
directly resolved the one open question the original change deferred (whether tag automation was
worth the permission/race surface).
