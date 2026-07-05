## 1. Canonical source

- [ ] 1.1 Create `VERSION` at the repository root containing `0.30` (single line, no `v` prefix).
- [ ] 1.2 Update `Directory.Build.props` to derive `<Version>` from `VERSION` via
      `$([System.IO.File]::ReadAllText('$(MSBuildThisFileDirectory)VERSION').Trim())` instead of
      the literal `0.1.0`.
- [ ] 1.3 Build locally and confirm `AssemblyVersion.Get()` (via a quick daemon start + status
      API request, or a unit test) now returns `0.30`, not `0.1.0` or `0.0.0`.

## 2. Welcome banner

- [ ] 2.1 Update `src/OpenWSFZ.Daemon/WelcomeBannerEmitter.cs` to include the version (via
      `OpenWSFZ.Web.AssemblyVersion.Get()`) in its stdout banner line.
- [ ] 2.2 Add or update a test asserting the banner text contains the current version string.

## 3. Documentation

- [ ] 3.1 Confirm README.md's and REQUIREMENTS.md's anchor sentences (`The current release is
      **v0.30**.` / `The current release is v0.30.`) already match the pattern gate G9 will
      check; adjust wording only if needed to fit `The current release is **v<VERSION>**.`
      (bold optional) without changing their meaning.
- [ ] 3.2 Add a short note near each anchor sentence (or in a shared "Versioning" section) that
      the value is sourced from the root `VERSION` file and is CI-checked, so a future editor
      knows not to hand-drift it.

## 4. CI enforcement (gate G9)

- [ ] 4.1 Write `tools/check_version_docs.py`: reads `VERSION`, extracts the version from the
      anchor sentence in `README.md` and in `REQUIREMENTS.md`, exits non-zero with a clear
      remediation message if either disagrees with `VERSION` (following the messaging style of
      `tools/check_native_version.py`).
- [ ] 4.2 Write `tools/check_version_bump.py`: given a base ref (e.g.
      `origin/${{ github.base_ref }}`), lists `proposal.md` files newly added under
      `openspec/changes/archive/` in the diff; for each, checks for a `**User-facing:**` line
      (fails if missing/malformed) and, if `yes`, checks `VERSION` differs from the base ref's
      copy (fails if unchanged). Exits non-zero with a clear remediation message naming the
      offending change(s).
- [ ] 4.3 Add a `version-governance` job to `.github/workflows/ci.yml`, modelled on the existing
      `detect-native-changes` job's checkout style (`fetch-depth: 0`), gated to
      `github.event_name == 'pull_request'`, running both scripts from 4.1 and 4.2.
- [ ] 4.4 Verify the new job fails as expected against a deliberately-broken local scenario (e.g.
      a scratch branch with a `user_facing: yes` archived proposal and no `VERSION` change), then
      confirm it passes once corrected, before relying on it in the real PR.

## 5. OpenSpec process convention

- [ ] 5.1 Add `**User-facing:** yes` (this change ships an operator-visible fix — the daemon's
      reported version and welcome-banner text both change) as the first line of this change's
      own `proposal.md`, ahead of `## Why`, so this change is itself gate-G9-compliant when
      archived.
- [ ] 5.2 Document the `user_facing` marker convention in a place future proposal authors will
      see it before writing `proposal.md` — e.g. a short addition to `openspec/qa-backlog.md` or
      wherever this project's OpenSpec contribution notes live (confirm the right location during
      implementation; no dedicated CONTRIBUTING.md currently exists for OpenSpec conventions).

## 6. Manual follow-up (not automated by this change)

- [ ] 6.1 After merge, cut an annotated `v0.30` git tag (the stale `v0.11` tag may be left in
      place or deleted at the Captain's discretion — not a design blocker, see design.md Open
      Questions).

## 7. Verification

- [ ] 7.1 Run the full three-OS CI matrix and confirm gate G9 passes on this change's own PR
      (which itself changes `VERSION` from `0.1.0` to `0.30` and declares `user_facing: yes` once
      archived).
- [ ] 7.2 QA review: confirm `openspec validate --strict --all` (gate G8) still passes with the
      new `release-versioning` capability and the `ci-quality-gates` delta in place.
