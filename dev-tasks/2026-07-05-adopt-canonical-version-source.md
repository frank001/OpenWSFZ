# DEV TASK — adopt-canonical-version-source: implementation

**Date:** 2026-07-05
**OpenSpec change:** `adopt-canonical-version-source` — proposal/design/specs/tasks complete,
`openspec validate --strict --changes adopt-canonical-version-source` passes (1 new capability:
`release-versioning`; 1 modified capability delta: `ci-quality-gates`, adding gate G9)
**Branch:** `feat/adopt-canonical-version-source` (not yet created — branch from current `main`)
**Status:** Ready for implementation — no code written yet, OpenSpec artifacts only
**Origin:** GitHub issue #49 ("Adopt a canonical version source + enforce minor-bump-per-feature")

---

## 1. Context

Three places name the project's version and disagree, and one of them is not merely a docs
artefact:

- Git tag: sole tag is `v0.11` (stale).
- README.md / REQUIREMENTS.md: hand-reconciled to `v0.30` (`7f619fc`).
- **`Directory.Build.props`: `<Version>0.1.0</Version>`** — this one is live. The SDK derives
  `AssemblyInformationalVersionAttribute` from it, `src/OpenWSFZ.Web/AssemblyVersion.cs` reads
  that attribute, and `WebApp.cs`/`WebSocketHub.cs` serve it in the status API. **The running
  daemon is currently telling its own operator it is version `0.1.0`.** Fixing this value is the
  most urgent single line in this change; everything else exists to stop it drifting again.

Full rationale and every design decision (including alternatives considered and why they were
rejected) is in `openspec/changes/adopt-canonical-version-source/design.md` — read it first, it's
short. The two things most worth internalising before you start:

1. `VERSION` is the *only* file a human edits going forward. `Directory.Build.props` reads it;
   nothing else should ever declare a version value independently.
2. Gate G9 (new) enforces the "one user-facing feature = one minor bump" rule mechanically, keyed
   off a new one-line `**User-facing:** yes/no` declaration every `proposal.md` must carry. This
   change's own `proposal.md` already carries that line (`yes`) — don't strip it during any
   editing pass.

## 2. Work breakdown & suggested sequencing

Follow `openspec/changes/adopt-canonical-version-source/tasks.md` §1–§7 in order — they're
dependency-ordered. Notes below are pitfalls found during spec/design review, not a restatement.

### §1 — Canonical source

- The MSBuild property function is exactly:
  ```xml
  <Version>$([System.IO.File]::ReadAllText('$(MSBuildThisFileDirectory)VERSION').Trim())</Version>
  ```
  `MSBuildThisFileDirectory` ensures the path resolves relative to `Directory.Build.props`
  itself regardless of which project is building, so this works unchanged across every project
  in the solution.
- `VERSION` should **not** end with a trailing newline that survives into the version string —
  `.Trim()` handles a trailing `\n` from most editors, but create the file deliberately (e.g.
  `printf '0.30' > VERSION`, not an editor that force-appends a newline) or verify the trim
  actually strips it before moving on.
- Verification for 1.3: easiest path is starting the daemon locally and hitting the status
  endpoint (`GET /api/v1/status` — same one `WebApp.cs` line ~257/469/487 serves) and confirming
  `"Version": "0.30"` in the JSON, rather than trusting the build output alone.

### §2 — Welcome banner

- `WelcomeBannerEmitter` lives in `OpenWSFZ.Daemon`; call `OpenWSFZ.Web.AssemblyVersion.Get()` —
  don't re-read `VERSION` directly from this class, that would reintroduce a second read path for
  the same value (design.md Decision 3 is explicit about this: one code path, not two).
- Check `OpenWSFZ.Daemon` already references `OpenWSFZ.Web` before assuming the call is free —
  `Program.cs` wires the HTTP host from `OpenWSFZ.Web`, so the reference should already exist,
  but confirm rather than assume.

### §3 — Documentation

- Task 3.1 is a *verification* task, not necessarily an edit — both anchor sentences already
  read `The current release is **v0.30**.` / `The current release is v0.30.`, which already fits
  the pattern gate G9's checker (§4) will grep for. Don't reword them unless you find they
  actually don't match; if you do reword, keep `check_version_docs.py` (§4.1) in sync in the same
  commit.

### §4 — CI enforcement (gate G9)

This is the part with the most new surface. Two independent scripts, one job:

- `tools/check_version_docs.py` — model its CLI ergonomics and messaging on
  `tools/check_native_version.py` (read it first): clear stdout progress lines, a specific
  actionable stderr message on failure, explicit exit codes. It needs no arguments (reads
  `VERSION`, `README.md`, `REQUIREMENTS.md` from the repo root by convention) — keep it that
  simple unless you find a reason not to.
- `tools/check_version_bump.py` — takes the base ref as an argument (pass
  `origin/${{ github.base_ref }}` from the workflow). Logic:
  1. `git diff --name-only --diff-filter=A <base>...HEAD -- 'openspec/changes/archive/**/proposal.md'`
  2. For each file: find the `**User-facing:**` line (search the first ~5 lines, not the whole
     file, since the convention is "before `## Why`" — but be lenient about exact position rather
     than brittle about line number). Missing or a value other than `yes`/`no` → fail.
  3. If any file says `yes`: `git diff --quiet <base>...HEAD -- VERSION` — non-empty diff
     required, fail if the exit code says "no difference."
  4. No matching files at all (PR doesn't archive anything) → pass trivially.
- New `version-governance` job in `.github/workflows/ci.yml`: copy the checkout style from the
  existing `detect-native-changes` job (`fetch-depth: 0`), gate the whole job with
  `if: github.event_name == 'pull_request'`. It does not need the 3-OS matrix — one runner
  (`ubuntu-latest` is fine, consistent with where G7/G8 already run) is sufficient since both
  scripts are pure Python/text operations.
- Task 4.4's "deliberately-broken local scenario" is worth doing exactly as written before
  trusting this in the real PR — a CI gate that's never been observed to actually fail is an
  unverified gate. A cheap way: on a scratch branch, add a throwaway
  `openspec/changes/archive/zzz-test/proposal.md` with `**User-facing:** yes` and don't touch
  `VERSION`; confirm the job fails; then fix it two ways (add the bump, and separately mark it
  `no` instead) and confirm each passes; delete the scratch branch before opening the real PR.

### §5 — OpenSpec process convention

- 5.1 is already done in the change's own `proposal.md` (see §1 note above) — this task is really
  "don't undo it," but keep it in the checklist for traceability.
- 5.2: there's genuinely no existing home for "OpenSpec contribution conventions" in this repo
  (confirmed — no `CONTRIBUTING.md`, and `openspec/qa-backlog.md` is QA-findings-only, not
  authoring guidance). Use your judgement on the least-bad location; a short new top-of-file note
  in `openspec/qa-backlog.md` ("Process notes" section) is a reasonable default if nothing better
  presents itself, but if you find a more natural home while implementing, use it and note the
  choice in the PR description so QA knows where to point future authors.

### §6 — Manual follow-up

- Cutting the `v0.30` tag is explicitly **not** part of this PR's CI or code — it's a manual
  `git tag -a v0.30 -m ...` + `git push --tags` step for after merge. Don't build tooling for it;
  design.md's Non-Goals is explicit that tag automation is out of scope here.

### §7 — Verification

- 7.1: this change's own PR is the first real test of gate G9 end-to-end (it changes `VERSION`
  and, once archived, will itself be a `user_facing: yes` entry under
  `openspec/changes/archive/`) — but note gate G9 only inspects the diff at merge/PR time, so it
  won't retroactively check itself against its own archival; that's expected and fine, don't
  chase it.
- 7.2: rerun `openspec validate --strict --all`, not just `--changes` — confirm the new
  `release-versioning` spec and the `ci-quality-gates` delta don't break the 46/46 passing baseline
  (verified clean as of this handoff).

## 3. Before opening a PR

- `openspec validate --strict --all` must still pass (46 specs + this change, currently green).
- Full `dotnet test` — 0 new failures.
- Confirm `git diff main -- VERSION` is non-empty in your own PR (`0.1.0` → `0.30`) — gate G9
  will check this once merged into the workflow, but verify it by eye too since G9 itself is
  being introduced in this same PR and won't be active to check itself on the way in.
- Manually confirm the daemon status API and the stdout welcome banner both show `0.30` on a
  local run — this is a "does it actually work" check, not just a unit-test claim (same category
  of caution as the flaky-decode-test lesson from `f-003-ap-assist`, see
  `dev-tasks/2026-07-05-f-003-ap-assist-flaky-decode-test.md`).

## 4. QA review

Standard process: QA reviews the diff against `openspec/changes/adopt-canonical-version-source/`'s
artifacts, confirms task-completion-on-archive and spec-sync state (HK-002 checklist), verifies
gate G9 actually fires in the negative case somewhere in the PR's CI history (not just that it's
green), and signs off before merge. Please hold the merge for that review.

## 5. References

- `openspec/changes/adopt-canonical-version-source/{proposal,design,tasks}.md` — source of truth;
  read `design.md` first, especially the Decisions and Risks/Trade-offs sections.
- `openspec/changes/adopt-canonical-version-source/specs/{release-versioning,ci-quality-gates}/spec.md`
  — the capability delta files.
- `tools/check_native_version.py` — style precedent for the two new scripts in §4.
- `src/OpenWSFZ.Web/AssemblyVersion.cs`, `src/OpenWSFZ.Daemon/WelcomeBannerEmitter.cs` — the two
  product files touched.
- GitHub issue #49 — original request.
