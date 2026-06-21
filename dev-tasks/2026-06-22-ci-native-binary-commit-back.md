# Developer Handoff — CI: Automatic native binary commit-back

**Date:** 2026-06-22  
**Branch:** `chore/ci-native-binary-commit-back`  
**Base:** `main` at `4a080e4`  
**Requested by:** Captain (QA review post D-009 merge)

---

## 1. Context

Every time the native shim version is bumped, the Linux and macOS binaries must
be manually downloaded from CI artifacts and committed to the repository. This
is error-prone and produces a pattern of stale binaries that persist across
multiple commits.

The current CI workflow already rebuilds both binaries on every push:
- Linux rebuild: `.github/workflows/ci.yml` step "Build native Linux .so"
- macOS rebuild: step "Build native macOS dylib"

Both steps copy the rebuilt binary into the working directory and upload it as
a CI artifact. They do NOT commit the result back to the repository. This
handoff automates that final step.

**What the Captain sees as "CI failures":** The staleness check steps carry
`continue-on-error: true`, which means GitHub marks each step with an orange
warning annotation even when the overall job passes. After this change,
the fresh binary will be committed back automatically, so subsequent CI runs
will pass the staleness check cleanly.

---

## 2. Branch name

`chore/ci-native-binary-commit-back`

Do NOT commit directly to `main`.

---

## 3. Actions

### 3.1 — Add `permissions: contents: write` at workflow level

In `.github/workflows/ci.yml`, add a top-level `permissions` block immediately
after the `on:` section:

```yaml
permissions:
  contents: write
```

This allows the workflow to push commits using the built-in `GITHUB_TOKEN`.

### 3.2 — Add a `commit-native-binaries` job

Add the following job at the end of `.github/workflows/ci.yml`, after the
existing `build-test` job definition:

```yaml
  # -----------------------------------------------------------------
  # Commit-back: after the matrix builds fresh Linux and macOS
  # binaries, commit them to the triggering branch so the repo never
  # carries stale binaries.
  #
  # Only runs on direct-push events (not PRs from forks, where write
  # access is unavailable). Skipped when the push was itself made by
  # the GitHub Actions bot (loop guard). The commit message carries
  # [skip ci] so GitHub does not re-trigger the workflow.
  # -----------------------------------------------------------------
  commit-native-binaries:
    name: Commit rebuilt native binaries
    runs-on: ubuntu-latest
    needs: build-test
    if: |
      github.event_name == 'push' &&
      github.actor != 'github-actions[bot]'

    steps:
      - name: Checkout (full depth, with write access)
        uses: actions/checkout@v6
        with:
          submodules: recursive
          token: ${{ secrets.GITHUB_TOKEN }}

      - name: Download Linux .so artifact
        uses: actions/download-artifact@v4
        with:
          name: libft8-so-linux-x64
          path: src/OpenWSFZ.Ft8/Native/linux-x64/

      - name: Download macOS dylib artifact
        uses: actions/download-artifact@v4
        with:
          name: libft8-dylib-osx-arm64
          path: src/OpenWSFZ.Ft8/Native/osx-arm64/

      - name: Check whether binaries changed
        id: diff_check
        run: |
          git diff --exit-code \
            src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so \
            src/OpenWSFZ.Ft8/Native/osx-arm64/libft8.dylib \
          && echo "changed=false" >> "$GITHUB_OUTPUT" \
          || echo "changed=true"  >> "$GITHUB_OUTPUT"

      - name: Verify rebuilt binary versions
        if: steps.diff_check.outputs.changed == 'true'
        run: |
          EXPECTED=$(python3 -c "
          import re
          src = open('src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs').read()
          m = re.search(r'ExpectedShimVersion\s*=\s*(\d+)', src)
          print(m.group(1))
          ")
          echo "Expected shim version: $EXPECTED"
          python3 tools/check_native_version.py \
            src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so "$EXPECTED"
          python3 tools/check_native_version.py \
            src/OpenWSFZ.Ft8/Native/osx-arm64/libft8.dylib "$EXPECTED"

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

### 3.3 — Fix artifact download action version

The existing `build-test` job uses `actions/upload-artifact@v7`.
The new job uses `actions/download-artifact@v4`. Verify that `v4` and `v7` are
compatible (they are in GitHub's current runner environment — v4 download is the
correct counterpart for v7 upload). No change needed to the upload steps.

### 3.4 — Remove the `upload-artifact` redundancy note

No change to the existing upload steps is required. The upload from `build-test`
and the download in `commit-native-binaries` work together: the matrix jobs
produce the artifacts, the commit-back job consumes them.

---

## 4. Acceptance criteria

The QA engineer will verify each of the following before approving merge:

**AC-1 — Loop prevention confirmed:**  
The commit created by the job has message containing `[skip ci]`. A subsequent
push by the bot does NOT trigger another CI run (verify in the Actions tab —
the bot commit should appear without a workflow run attached).

**AC-2 — Staleness check now clean on re-run:**  
After the commit-back fires and updates the binaries, the next human-triggered
push to the same branch passes the "Check committed Linux/macOS binary" steps
with exit code 0 (no orange warning annotation).

**AC-3 — Version verification passes:**  
The "Verify rebuilt binary versions" step confirms that both downloaded binaries
report the correct `ExpectedShimVersion` before committing. If the version check
fails, the commit step is skipped and the job exits with a failure — the
developer must investigate.

**AC-4 — No-op when binaries are current:**  
When the committed binaries are already at the correct shim version, the
`diff_check` step outputs `changed=false` and neither the version check nor the
commit step runs. No spurious commit is created.

**AC-5 — PRs from forks are unaffected:**  
The `github.event_name == 'push'` condition means the commit-back job is
skipped for `pull_request` events. Forked PR CI runs do not attempt a push
(which would fail due to missing write access).

**AC-6 — `permissions: contents: write` scoped correctly:**  
The workflow-level permission does not break any existing gate (G3 traceability,
G5 licence, G7 gitleaks). Verify all three gates still pass in CI.

**AC-7 — Workflow YAML is valid:**  
`act` (local GitHub Actions runner) or a dry-run lint confirms the YAML parses
without errors. At minimum, confirm `yamllint` or GitHub's own syntax check on
the PR passes.

---

## 5. References

- `.github/workflows/ci.yml` — existing workflow to be modified
- `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs` — contains `ExpectedShimVersion`
- `tools/check_native_version.py` — version check utility used by the staleness
  gate; reused in AC-3
- MEMORY.md lesson 13 — Linux staleness gate and `continue-on-error: true`
  history
- MEMORY.md lesson 1 — "CI passes ≠ committed binary is current"

---

## 6. Out of scope

- Changing the staleness check steps (`continue-on-error: true` stays — it is
  still useful as an early warning on the first push after a shim bump, before
  the commit-back fires).
- Windows binary commit-back: win-x64 is always built and committed locally by
  the developer using `rebuild_shim_new.bat`. No CI commit-back is needed for
  Windows.
- Secrets: `GITHUB_TOKEN` is automatically provided by GitHub Actions and
  requires no additional configuration from the Captain.
