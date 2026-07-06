## 1. Tag-cutting tool

- [x] 1.1 Write `tools/cut_version_tag.py`: reads `VERSION`, computes `v<VERSION>`, checks whether
      that tag already exists (`git rev-parse --verify --quiet refs/tags/<tag>`); if absent,
      creates an annotated tag and pushes it to `origin`. Supports `--dry-run` (prints the action
      without tagging or pushing). Follows the style of `tools/check_version_docs.py` /
      `tools/check_version_bump.py`: dependency-free stdlib Python, clear stdout progress, exit
      codes 0/1/2. **Done.**
- [x] 1.2 Exercise locally against the current repo state with `--dry-run` and confirm it reports
      "would create and push v0.31" (the known current gap). **Done** — confirmed
      `Result : DRY RUN — would create and push annotated tag v0.31 at 7340e45...`. Also verified
      the idempotent path: with a scratch `v0.31` tag present, the script reports "already exists;
      nothing to do." and exits 0; scratch tag deleted afterwards.

## 2. CI wiring

- [x] 2.1 Add job `tag-release-version` to `.github/workflows/ci.yml`: `needs: [build-test]`,
      `if: github.event_name == 'push' && github.ref == 'refs/heads/main'`, full-history checkout
      with a token that has push access, git identity configured (mirroring
      `commit-native-binaries`), then runs `tools/cut_version_tag.py`. **Done.**
- [x] 2.2 Narrow the workflow's top-level `push:` trigger from unfiltered to
      `push: branches: ['**']`, so the tag push in 2.1 does not itself re-trigger the workflow
      (see design.md Decision 4 and the lesson-25 precedent it cites). **Done.**
- [x] 2.3 Validate the modified `ci.yml` is well-formed YAML (e.g. `python3 -c "import
      yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml'))"` or equivalent) before opening
      the PR. **Done** — parses cleanly; confirmed the job list includes `tag-release-version` and
      the `on.push` trigger reads `{'branches': ['**']}`.

## 3. Spec sync

- [x] 3.1 Confirm the delta specs under this change's `specs/` directory (`ci-quality-gates`,
      `release-versioning`) read correctly against the archived baseline — i.e. the MODIFIED
      requirement text is a complete, self-consistent replacement, not a partial diff. **Done** —
      confirmed via `openspec validate --strict --all` (task 4.4).

## 4. Verification

- [x] 4.1 Open the PR and confirm the existing three-OS `build-test` matrix and gate
      `version-governance` (this PR's own diff touches no `VERSION` line, so G9b should report "no
      version bump required") both still pass. **Done** — PR #52, all six checks passed (three OSes
      on both the push- and pull_request-triggered runs, plus `Gate G9 — Version governance`
      passing in 5s having correctly found no archived proposals in the diff).
- [x] 4.2 After merge, confirm on GitHub that the `tag-release-version` job ran on the resulting
      push to `main`, and that a `v0.31` tag now exists pointing at the merge commit — closing the
      drift that motivated this change with no manual `git tag` command. Verify with
      `git ls-remote --tags origin` or the GitHub UI. **Done** — merged as `4397742` (squash-merge
      of PR #52). The resulting push-to-main run (28813235853) ran `Gate G9 — Tag release version`
      in 8s, with job log confirming `Result : OK — created and pushed annotated tag v0.31 at
      4397742...`. Independently verified via `git fetch --tags && git rev-list -n1 v0.31`, which
      returns `4397742...`, matching the merge commit exactly.
- [x] 4.3 Confirm the tag push did not spawn a second `build-test` run (per task 2.2) — check the
      Actions run list for the repository around the merge time. **Done** — `gh run list --branch
      main --limit 6` shows exactly one run for the merge commit (28813235853); no second/duplicate
      run appears, confirming the `push: branches: ['**']` trigger scoping (task 2.2) worked as
      designed.
- [x] 4.4 Run `openspec validate --strict --all` locally and confirm it still passes with the two
      modified capability specs in place (gate G8 will also check this in CI, but confirm before
      opening the PR). **Done** — `47 passed, 0 failed` with `@fission-ai/openspec@1.3.1`, including
      `✓ change/g9-automate-release-tagging`.

## 5. Follow-up note

- [x] 5.1 No dev-tasks handoff required — this is a CI-only change (workflow + tooling script),
      which QA is authorized to implement directly per the standing HK-000 delegation
      (`hk000-developer-handoff.md`). **Confirmed applicable — implemented directly, this PR.**
