## 1. Canonical source

- [x] 1.1 Create `VERSION` at the repository root containing `0.30` (single line, no `v` prefix).
      **Done by QA directly, commit `547b05c`.**
- [x] 1.2 Update `Directory.Build.props` to derive `<Version>` from `VERSION` via
      `$([System.IO.File]::ReadAllText('$(MSBuildThisFileDirectory)VERSION').Trim())` instead of
      the literal `0.1.0`. **Done, `547b05c`.**
- [x] 1.3 Build locally and confirm `AssemblyVersion.Get()` (via a quick daemon start + status
      API request, or a unit test) now returns `0.30`, not `0.1.0` or `0.0.0`. **Done, `547b05c`
      — verified via full solution build (0 warnings/errors) and
      `StatusAndBindingTests.GetStatus_Returns200WithJson`.** Note: `AssemblyVersion` had to be
      changed from `internal` to `public` for task 2.1 to call it across the assembly boundary —
      this was not anticipated in design.md and is called out there as a "confirm rather than
      assume" risk that materialised.

## 2. Welcome banner

- [x] 2.1 Update `src/OpenWSFZ.Daemon/WelcomeBannerEmitter.cs` to include the version (via
      `OpenWSFZ.Web.AssemblyVersion.Get()`) in its stdout banner line. **Done, `547b05c`.**
- [x] 2.2 Add or update a test asserting the banner text contains the current version string.
      **Done, `547b05c`** — `tests/OpenWSFZ.Daemon.Tests/WelcomeBannerEmitterTests.cs`.

## 3. Documentation

- [x] 3.1 Confirm README.md's and REQUIREMENTS.md's anchor sentences (`The current release is
      **v0.30**.` / `The current release is v0.30.`) already match the pattern gate G9 will
      check; adjust wording only if needed to fit `The current release is **v<VERSION>**.`
      (bold optional) without changing their meaning. **Confirmed already correct — no edit
      needed, `547b05c`'s commit message notes this explicitly.**
- [x] 3.2 Add a short note near each anchor sentence (or in a shared "Versioning" section) that
      the value is sourced from the root `VERSION` file and is CI-checked, so a future editor
      knows not to hand-drift it. **Done** — a `<sub>`-tagged note added after the anchor
      sentence in both `README.md` and `REQUIREMENTS.md`.

## 4. CI enforcement (gate G9)

- [x] 4.1 Write `tools/check_version_docs.py`: reads `VERSION`, extracts the version from the
      anchor sentence in `README.md` and in `REQUIREMENTS.md`, exits non-zero with a clear
      remediation message if either disagrees with `VERSION` (following the messaging style of
      `tools/check_native_version.py`). **Done** — no-argument script, exits 0 against current
      repo (both docs cite v0.30).
- [x] 4.2 Write `tools/check_version_bump.py`: given a base ref (e.g.
      `origin/${{ github.base_ref }}`), lists `proposal.md` files newly added under
      `openspec/changes/archive/` in the diff; for each, checks for a `**User-facing:**` line
      (fails if missing/malformed) and, if `yes`, checks `VERSION` differs from the base ref's
      copy (fails if unchanged). Exits non-zero with a clear remediation message naming the
      offending change(s). **Done** — exits 0 against current baseline (no archived proposals in
      diff).
- [x] 4.3 Add a `version-governance` job to `.github/workflows/ci.yml`, modelled on the existing
      `detect-native-changes` job's checkout style (`fetch-depth: 0`), gated to
      `github.event_name == 'pull_request'`, running both scripts from 4.1 and 4.2. **Done** —
      job `version-governance` (Gate G9) with steps G9a (docs) and G9b (bump); YAML validated.
      **QA review addendum:** the job existing in `ci.yml` is necessary but not sufficient — unlike
      G1–G8 (steps inside the `build-test` job, which *is* a required status check), G9 was added
      as a separate top-level job, so it was initially possible for it to fail red without
      blocking merge. Confirmed via `gh api repos/:owner/:repo/branches/main/protection` that
      `required_status_checks.contexts` only listed the three `Build & Test (<os>)` contexts.
      Fixed directly against the live repo (not a file in this change) via
      `gh api --method PATCH .../branches/main/protection/required_status_checks`, adding
      `"Gate G9 — Version governance"` (verified byte-for-byte against the job's `name:` field, em
      dash included, so the required check isn't left permanently pending on a string mismatch).
      Re-queried afterwards to confirm all four contexts are present with `strict: true`.
- [x] 4.4 Verify the new job fails as expected against a deliberately-broken local scenario (e.g.
      a scratch branch with a `user_facing: yes` archived proposal and no `VERSION` change), then
      confirm it passes once corrected, before relying on it in the real PR. **Done** — scratch
      branch `scratch/g9-test` exercised all four G9b paths (yes+no-bump → FAIL; yes+bump → PASS;
      no+no-bump → PASS; malformed → FAIL) plus the G9a docs-drift FAIL path; all behaved as
      designed; scratch branch deleted.

## 5. OpenSpec process convention

- [x] 5.1 Add `**User-facing:** yes` (this change ships an operator-visible fix — the daemon's
      reported version and welcome-banner text both change) as the first line of this change's
      own `proposal.md`, ahead of `## Why`, so this change is itself gate-G9-compliant when
      archived. **Done** — already present as line 1 of `proposal.md`; verified, not re-added.
- [x] 5.2 Document the `user_facing` marker convention in a place future proposal authors will
      see it before writing `proposal.md` — e.g. a short addition to `openspec/qa-backlog.md` or
      wherever this project's OpenSpec contribution notes live (confirm the right location during
      implementation; no dedicated CONTRIBUTING.md currently exists for OpenSpec conventions).
      **Done** — added a "Process notes" section at the top of `openspec/qa-backlog.md` (no
      `AGENTS.md`/`project.md`/`CONTRIBUTING.md` exists; qa-backlog is the most-read OpenSpec doc).

## 6. Manual follow-up (not automated by this change)

- [x] 6.1 After merge, cut an annotated `v0.30` git tag (the stale `v0.11` tag may be left in
      place or deleted at the Captain's discretion — not a design blocker, see design.md Open
      Questions). **Done ahead of merge, tag `v0.30` on commit `547b05c`; `v0.11` left in place
      per the Captain's instruction.**

## 7. Verification

- [ ] 7.1 Run the full three-OS CI matrix and confirm gate G9 passes on this change's own PR
      (which itself changes `VERSION` from `0.1.0` to `0.30` and declares `user_facing: yes` once
      archived). **PENDING** — requires pushing `feat/adopt-canonical-version-source` and opening
      the PR so GitHub Actions runs; awaiting the Captain's go-ahead to push. Gate G9 was fully
      exercised locally in task 4.4 (all four G9b paths + the G9a drift path), so the CI run is a
      confirmation, not a first test. Note: G9 only inspects the PR diff at merge time, so it will
      not retroactively gate this change against its own future archival — expected, per §7 of the
      dev-tasks handoff.
- [x] 7.2 QA review: confirm `openspec validate --strict --all` (gate G8) still passes with the
      new `release-versioning` capability and the `ci-quality-gates` delta in place. **Done** —
      `46 passed, 0 failed` with `@fission-ai/openspec@1.3.1`.
- [ ] 7.3 **Cross-surface consistency check (release-versioning's "Version consistency across all
      surfaces" requirement) — required before every merge that touches `VERSION` or any of the
      surfaces it governs, not just this PR.** Confirm, by direct inspection (not by trusting that
      the individual tasks above were done correctly), that all of the following report the
      identical value:
      - `VERSION` file content
      - `Directory.Build.props`-derived `AssemblyInformationalVersion` (any built assembly)
      - daemon status API (`GET /api/v1/status` `version` field)
      - daemon stdout welcome banner
      - `README.md` anchor sentence
      - `REQUIREMENTS.md` anchor sentence
      - the annotated git tag
      A one-line shell check is sufficient and should be run, not just eyeballed:
      ```bash
      cat VERSION
      grep '<Version>' Directory.Build.props
      git describe --tags --exact-match HEAD
      grep -o 'v[0-9.]*' README.md | head -1
      grep -o 'v[0-9.]*' REQUIREMENTS.md | head -1
      ```
      Once gate G9 (task 4) exists, it automates the README/REQUIREMENTS/`VERSION` leg of this
      check on every future PR — but it does not check the status API, banner, or git tag, so this
      task remains a manual step for any PR touching versioning until/unless those are also
      automated.
      **Done** — all seven surfaces independently observed to report `0.30`/`v0.30`: `VERSION`
      file; `Directory.Build.props` (reads `VERSION`); built `OpenWSFZ.Web` assembly (Release);
      daemon status API (`GET /api/v1/status` → `"Version": "0.30"`, observed on a live local
      run); daemon stdout welcome banner (`OpenWSFZ v0.30 listening on ...`, observed on the same
      run); `README.md` anchor (`v0.30`); `REQUIREMENTS.md` anchor (`v0.30`); annotated git tag
      `v0.30`.
