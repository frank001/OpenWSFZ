# Developer task: CI, a manual trigger that rebuilds and commits the Linux and macOS native binaries without a native change, and a glibc guard on the committed Linux blob

**Date:** 2026-11-14
**Prepared by:** QA
**Audience:** Developer (to execute); Captain (go for push, PR and merge, HK-010, HK-033)
**Authorised by:** the Architect's glibc ruling, §5 (`arch/cross-cycle-prior` `fc2cf5b8`): the acceptance of §2 of `c414bdb1` was never met, because PR #284 changed only CI and rebuilt nothing; the committed Linux `libft8.so` still needs GLIBC_2.43 and the WSL Debian leg still fails on it. **This does not block the XC PR.**
**Status:** Proposed. **`.github/` only. No `src/`, no `native/`.** (HK-011 is not triggered by a CI-only change, but the same separate-session discipline holds.) 🛑 **No push, no PR, no merge on your own initiative; no `pre_merge_check.py`.** QA pushes after the Captain's go.
**Branch:** a NEW branch off **`origin/main`** (currently `cc1a39ad`, PR #284 merged), **not** off `feat/xc-template-prior`. Name it so that it does not collide with the bot's `ci/native-binaries-shim<N>` branches (for example `ci/force-native-rebuild`). Your worktree is on `feat/xc-template-prior`; switch it, or leave it and say where you worked.

---

## 0. The facts (read `.github/workflows/ci.yml` on `origin/main`)

- `on:` already lists `workflow_dispatch:` **with no inputs**.
- The job **`detect-native-changes`** (about `:611`) runs only on a **push to `main` by someone other than the bot**, and sets `relevant=true` only when the push touches `src/OpenWSFZ.Ft8/Native/`, `native/ft8_lib_build/` or `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs`.
- The job **`commit-native-binaries`** (about `:646`) needs `[build-test, detect-native-changes]`, runs on the same condition plus `relevant == 'true'`, downloads the artifacts `libft8-so-linux-x64` and `libft8-dylib-osx-arm64` built by `build-test`, `git diff`s them against the committed files, and when they differ commits them to the branch `ci/native-binaries-shim<SHIM>` and **opens a PR** (`gh pr create`). It never commits to `main` directly.
- In `build-test`, the Linux leg (pinned to `ubuntu-24.04`, check name kept as "Build & Test (ubuntu-latest)" by a matrix label) builds the `.so` (step "Build native Linux .so", about `:232`), **copies it over `src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so` in the workspace** (about `:298`), runs `tools/check_glibc_floor.py` on **that fresh build** (the step "Guard - Linux .so glibc floor", added by #284) and uploads it. **So the committed blob is never examined**, and nothing rebuilds it unless a native-relevant path changes.
- **Result today:** the committed `src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so` (SHA-256 prefix `e8cb81805322`) needs GLIBC_2.43; the floor is 2.39 (`tools/check_glibc_floor.py`, `GLIBC_FLOOR`).

## 1. What to build

| Id | What |
|---|---|
| **F1 The input** | `workflow_dispatch:` gains `inputs: force_native_rebuild:` (`type: boolean`, `default: false`, a one-line description). |
| **F2 The trigger, not a no-op native touch** | When the run is a `workflow_dispatch` on **`refs/heads/main`** with `inputs.force_native_rebuild == true`: `detect-native-changes` runs and reports `relevant=true` **without diffing**, and `commit-native-binaries` runs, so the rebuilt Linux `.so` and macOS `.dylib` are committed to `ci/native-binaries-shim<SHIM>` and a PR is opened exactly as today. Do **not** touch any file under `native/` or `src/OpenWSFZ.Ft8/` to provoke it. Keep the existing `github.actor != 'github-actions[bot]'` rule for the push path. Normal pushes, pull requests and every other dispatch behave **exactly as before** (a dispatch with the input false, or from another ref, must not reach `commit-native-binaries`). |
| **F3 Guard before commit** | In `commit-native-binaries`, run `python3 tools/check_glibc_floor.py src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so` on the **downloaded artifact** before it is committed (belt and braces: the build already ran it before the upload). A blob above the floor must stop the job; it must never be committed. |
| **F4 Guard on the committed blob** | In the Linux leg of `build-test`, **before** "Build native Linux .so" (the build step overwrites the committed path), run `python3 tools/check_glibc_floor.py src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so` on the **committed** blob, so a committed blob above the floor is reported on every run. **Ordering constraint, read it:** the committed blob is above the floor today, so a **blocking** step would fail every CI run, including this PR's own, and nothing could merge. **Therefore land F4 as non-blocking first** (`continue-on-error: true`, plus a `::warning::` annotation naming the glibc version found and saying "remove continue-on-error after the rebuild PR has merged"), and **ask QA for the flip** (a second, one-line PR, F5) once the rebuilt blob is on `main`. If you see another order that keeps CI green and makes the guard blocking from the start, say so; do not weaken `check_glibc_floor.py` itself. |
| **F5 (later, a separate tiny PR, on QA's word)** | Remove `continue-on-error` from F4, so the committed blob is a blocking check. Not part of this PR; do not do it until QA says the rebuilt blob is on `main`. |

## 2. Not in this task

No change to the Linux leg's pin (**it stays on `ubuntu-24.04`**), to the matrix label (the required check name stays "Build & Test (ubuntu-latest)"), to the floor (2.39), to `tools/check_glibc_floor.py`, to any job other than the three named, to the bot's branch naming or PR text, or to any file outside `.github/`. **Do not rebuild or commit a binary yourself** and do not dispatch anything: QA dispatches, after merge, on the Captain's go.

## 3. How this is verified (a workflow cannot be run locally; say what you did instead)

- Validate the YAML with whatever you have (`actionlint` if installed, or a YAML parser) and say which; if neither is available, say so and QA reads the PR's own CI run (a workflow that does not parse fails at once).
- Reason through the conditions in your report as a small truth table: for each of {push to main by a person with native paths changed, push to main by a person without, push by the bot, pull request, dispatch on main with the input true, dispatch on main with the input false, dispatch on another ref with the input true}, does `detect-native-changes` run, what does it output, does `commit-native-binaries` run. The result must be: only the first and the fifth reach the commit step with `relevant=true`.
- The functional proof is the first dispatch after merge (QA's, below); the PR's CI run proves the file parses and that F4 does not break the Linux leg.

## 4. What QA does after it lands (so you build for it)

1. (Captain's go) push, PR, merge. 2. Dispatch once: `gh workflow run ci.yml --ref main -f force_native_rebuild=true`. 3. Read the guard's output in the run: the rebuilt Linux blob's maximum `GLIBC_` must be **<= 2.39**; the bot PR (`ci/native-binaries-shim20260072`) carries the new `.so` and `.dylib`. 4. (Captain's go) merge the bot PR. 5. Re-run the WSL Debian leg of `pre_merge_check` on a commit that has the new blob: green means the glibc ruling's §2 is met. 6. Record the new `.so` SHA-256 (the shim version, 20260072, does not change; the pin does). 7. Ask you for F5.

## 5. Questions to answer in your report

1. The truth table of §3, filled in, and the YAML validation you ran.
2. Exactly where each of F1 to F4 sits (FILE:LINE in `ci.yml`).
3. Whether `detect-native-changes` is the right place to short-circuit for the forced run (it checks out full history and diffs; say what the forced path skips).
4. Whether the macOS dylib is also committed by a forced run, and what that implies (the macOS build is not byte-reproducible across runner instances, so a forced run will always show a dylib diff; say whether that is acceptable as stated or whether a separate input is needed; do not add one unless you find a reason).
5. Anything in the other CI gates (G3, G8, G9, G10, the test-delay lint) that a change to `ci.yml` touches.

## 6. Gates you run before handing back

`python tools/check_version_bump.py origin/main` after committing (a CI-only change should not need a bump; say what it reports), the existing local lints that read `.github/` if any (grep `tools/` for `ci.yml`), and the YAML validation above. 🛑 **Do not run `pre_merge_check.py`.**

## 7. Stop-and-tell conditions

Stop and report to QA, without building around it, if: the forced run cannot reach `commit-native-binaries` without a change outside `.github/`; the job structure makes F2 unsafe (it could let an ordinary push commit binaries); F4 cannot be made non-blocking without hiding a real failure.

## 8. Report back (HK-001 sections), then STOP

The commit hash(es); the §1 table answered row by row with FILE:LINE; the §5 answers; the diff stat (only `.github/`); the validation you ran; deviations and why. **Then stop**: QA reviews the workflow diff line by line, and the push waits for the Captain's go.
