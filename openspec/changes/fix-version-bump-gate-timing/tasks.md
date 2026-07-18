## 1. Script rewrite

- [ ] 1.1 Rewrite `tools/check_version_bump.py`: scan `git diff --diff-filter=A <base>...HEAD --
      openspec/changes/**/proposal.md` (both active and archived paths, not archive-only).
- [ ] 1.2 Derive a change name from each added path (active: directory name; archived: directory
      name with the leading `YYYY-MM-DD-` prefix stripped).
- [ ] 1.3 For each added *archived*-path proposal, check whether
      `openspec/changes/<name>/proposal.md` already existed at `<base_ref>`; if so, exclude it
      from the checked set (ordinary archiving relocation, already bumped at introduction).
- [ ] 1.4 Apply the existing declaration-validity and yes/bump-required checks to the resulting
      de-duplicated set exactly as before.
- [ ] 1.5 Update the module docstring and inline comments to describe merge-time (first
      introduction), not archive-time, semantics.
- [ ] 1.6 Keep the CLI signature (`check_version_bump.py <base_ref>`) and exit codes unchanged.

## 2. CI workflow

- [ ] 2.1 Rename the `G9b — Mandatory bump on user-facing archive` step in
      `.github/workflows/ci.yml` to `G9b — Mandatory bump on user-facing merge`; update its
      neighbouring comment block (lines ~566–571) to describe the corrected timing. No change to
      the job's trigger condition or the script invocation itself.

## 3. Spec sync

- [ ] 3.1 Confirm the delta spec at `specs/ci-quality-gates/spec.md` in this change directory
      matches the intended MODIFIED requirement text (already drafted).

## 4. Manual verification (no pytest precedent exists for this tooling class)

- [ ] 4.1 Build a scratch git repo fixture and verify: a PR adding a new active `proposal.md`
      declaring `yes` with no VERSION change → script exits 1.
- [ ] 4.2 Same fixture + a VERSION change in the PR → script exits 0.
- [ ] 4.3 A new active `proposal.md` declaring `no` → script exits 0 regardless of VERSION.
- [ ] 4.4 A PR that relocates an already-introduced (already on `base_ref` at the active path)
      `proposal.md` to the archive path, with no VERSION change in this PR → script exits 0 (no
      second bump demanded).
- [ ] 4.5 A PR that adds a `proposal.md` directly under the archive path with no prior active-path
      history and no VERSION change → script exits 1.
- [ ] 4.6 A `proposal.md` missing/malformed `**User-facing:**` → script exits 1 regardless of
      path.
- [ ] 4.7 Run `python3 tools/pre_merge_check.py` and confirm Gate G8 (`openspec validate
      --strict --all`) still passes with this change's delta spec present.

## 5. Ship

- [ ] 5.1 Commit on a dedicated branch (`fix/version-bump-gate-timing`), open a PR. This change
      is `**User-facing:** no` — no VERSION bump required for it.
- [ ] 5.2 After merge, archive this OpenSpec change (sync the delta into
      `openspec/specs/ci-quality-gates/spec.md`) in a follow-up step, per the now-corrected
      understanding that VERSION-bump enforcement — not archiving itself — is what must happen
      pre-merge; archiving a `**User-facing:** no` change carries no bump requirement either way.
