# Handoff: CI — `commit-native-binaries` push blocked by branch protection

**Date:** 2026-06-26
**Prepared by:** QA engineer
**Status:** Awaiting developer action

---

## 1. Context

The `commit-native-binaries` CI job rebuilds the Linux (`libft8.so`) and macOS
(`libft8.dylib`) native binaries and commits them back to the triggering branch.
It has always pushed directly to `HEAD:${{ github.ref_name }}`.

Branch protection was enabled on `main` on 2026-06-24 (PR required + 3 status
checks). `GITHUB_TOKEN` (which the job uses) does not have admin bypass on a
personal repository — only the repository owner (`frank001`) does. The job
therefore fails with **GH006** whenever the triggering branch is `main`.

First failure observed on merge commit `f92d062` (Merge branch
`feat/qso-caller`, 2026-06-26).

A PAT-based fix (Option A) was considered and rejected in favour of Option B:
push the binary update to a short-lived branch and open a PR automatically.
This preserves the security intent of branch protection rather than
circumventing it.

---

## 2. Branch

`fix/ci-native-binary-push` — new branch from `main`.

---

## 3. Actions

All changes are confined to **`.github/workflows/ci.yml`**.

### 3.1 — Add `pull-requests: write` permission to the job

The `commit-native-binaries` job needs permission to open PRs via `gh pr
create`. Add a `permissions` block **at the job level** (not the workflow
level) so the broader `build-test` matrix is unaffected.

**Current** (no job-level permissions block):

```yaml
  commit-native-binaries:
    name: Commit rebuilt native binaries
    runs-on: ubuntu-latest
    needs: build-test
    if: |
      github.event_name == 'push' &&
      github.actor != 'github-actions[bot]'
```

**Replace with:**

```yaml
  commit-native-binaries:
    name: Commit rebuilt native binaries
    runs-on: ubuntu-latest
    needs: build-test
    permissions:
      contents: write
      pull-requests: write
    if: |
      github.event_name == 'push' &&
      github.actor != 'github-actions[bot]'
```

---

### 3.2 — Replace the "Commit and push updated binaries" step

**Current step** (lines 366–381 of `ci.yml`):

```yaml
      - name: Commit and push updated binaries
        if: steps.diff_check.outputs.changed == 'true'
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add \
            src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so \
            src/OpenWSFZ.Ft8/Native/osx-arm64/libft8.dylib
          SHIM=$(python3 -c "
          import re
          src = open('src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs').read()
          m = re.search(r'ExpectedShimVersion\s*=\s*(\d+)', src)
          print(m.group(1))
          ")
          git commit -m "chore(native): rebuild Linux and macOS binaries to shim ${SHIM} [skip ci]"
          git push origin HEAD:${{ github.ref_name }}
```

**Replace with these two steps:**

```yaml
      - name: Commit updated binaries to PR branch
        if: steps.diff_check.outputs.changed == 'true'
        id: branch_push
        run: |
          SHIM=$(python3 -c "
          import re
          src = open('src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs').read()
          m = re.search(r'ExpectedShimVersion\s*=\s*(\d+)', src)
          print(m.group(1))
          ")
          BRANCH="ci/native-binaries-shim${SHIM}"
          git config user.name  "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git checkout -b "$BRANCH"
          git add \
            src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so \
            src/OpenWSFZ.Ft8/Native/osx-arm64/libft8.dylib
          git commit -m "chore(native): rebuild Linux and macOS binaries to shim ${SHIM} [skip ci]"
          git push origin "$BRANCH"
          echo "branch=$BRANCH" >> "$GITHUB_OUTPUT"
          echo "shim=$SHIM"     >> "$GITHUB_OUTPUT"

      - name: Open PR for updated binaries
        if: steps.diff_check.outputs.changed == 'true'
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          BRANCH="${{ steps.branch_push.outputs.branch }}"
          SHIM="${{ steps.branch_push.outputs.shim }}"
          EXISTING=$(gh pr list --head "$BRANCH" --json number --jq 'length')
          if [ "$EXISTING" -gt 0 ]; then
            echo "PR already open for branch $BRANCH — skipping."
            exit 0
          fi
          gh pr create \
            --base main \
            --head "$BRANCH" \
            --title "chore(native): update Linux/macOS binaries to shim ${SHIM}" \
            --body "Automated PR from the \`commit-native-binaries\` CI job.

          The Linux (\`libft8.so\`) and macOS (\`libft8.dylib\`) native binaries
          were rebuilt from source and differ from the committed versions.
          This PR updates them to shim ${SHIM}.

          **No source changes.** Safe to merge once CI passes on this branch."
```

---

### 3.3 — No other files require changes

The `build-test` matrix jobs, gates G1–G7, and all other workflow steps are
unchanged.

---

## 4. Acceptance criteria

QA will verify the following before approving merge to `main`:

1. **Stale binaries → PR opened:** A push to `main` where the committed
   binaries are at a lower shim version than `ExpectedShimVersion` results in
   a PR titled `chore(native): update Linux/macOS binaries to shim N` being
   opened against `main` by `github-actions[bot]`. No direct push to `main` is
   attempted.

2. **Current binaries → PR skipped:** A push to `main` where the committed
   binaries already match `ExpectedShimVersion` produces no PR and no branch.
   The "Commit updated binaries" and "Open PR" steps are both skipped
   (`steps.diff_check.outputs.changed == 'false'`).

3. **Idempotency:** If the CI job runs a second time for the same shim version
   (e.g., a retried run), the "Open PR" step detects the existing PR and
   exits with `"PR already open"` rather than creating a duplicate.

4. **No push to `main`:** Confirm `git push origin main` (or any equivalent
   direct push) does not appear in the job logs. The only push is to the
   `ci/native-binaries-shimN` branch.

5. **Existing CI gates unaffected:** `build-test` matrix (G1/G3/G5/G6/G7)
   continues to pass without modification. The `build-test` job's
   `permissions` block is unchanged.

6. **Zero build warnings:** `dotnet build OpenWSFZ.slnx -c Release` — 0
   errors, 0 warnings (workflow change does not touch .NET source).

---

## 5. References

- Failing commit: `f92d062` — Merge branch `feat/qso-caller` (2026-06-26)
- CI error: `GH006: Protected branch update failed for refs/heads/main`
- MEMORY.md lesson 20: personal repo branch protection does not support
  named-user bypass allowances
- Branch protection enabled: `33c5f75` (2026-06-24, fix/security-lan-hardening)
- Affected job: `.github/workflows/ci.yml` — `commit-native-binaries`
  (lines 315–381)
