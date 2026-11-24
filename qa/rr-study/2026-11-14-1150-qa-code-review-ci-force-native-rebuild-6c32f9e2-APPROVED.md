# Code review: CI, `force_native_rebuild` dispatch input and the glibc guards, `6c32f9e2` on `ci/force-native-rebuild`. APPROVED

Reviewed-commit: 6c32f9e229bf7551d3e1c83a6fc5a5ed2943161b
Verdict: APPROVED

**Written:** 2026-11-14, `date -u` read 11:49:01Z. **Reviewer:** QA. **Branch:** `ci/force-native-rebuild` in the Developer's worktree, one commit on `origin/main` `cc1a39ad`, local, not pushed. **Spec:** the Architect's glibc ruling §5 (`arch/cross-cycle-prior` `fc2cf5b8`) and his reply accepting the order; dev task `dev-tasks/2026-11-14-ci-force-native-rebuild.md`. **Scope:** `.github/workflows/ci.yml` only (53 insertions, 8 deletions); `git diff origin/main 6c32f9e2 -- src native` is **0 lines**, so HK-039's hook has nothing to require, and this record is for the audit trail.

## 1. Verdict

**APPROVED.** The diff does what the task says and nothing else. The trigger is a trigger and not a no-op native touch; every other run behaves exactly as before (checked mechanically below); the guard on the downloaded artifact is blocking, and the guard on the committed blob is non-blocking until the rebuild has merged, as ordered. A workflow cannot be run locally, so the proof that it parses and does not break the Linux leg is the PR's own CI run, and the functional proof is the first dispatch.

## 2. What I read (the whole diff)

- **F1** `workflow_dispatch:` gains `inputs.force_native_rebuild` (boolean, default false, a one-line description in single quotes).
- **F4** a Linux-only step in `build-test`, **before** "Build native Linux .so" (the build step overwrites the committed path, so this is the only moment the branch's blob can be examined), `continue-on-error: true`; on a failing guard it prints the guard's output and emits `::warning title=Committed libft8.so is above the glibc floor::<first stdout line> - remove continue-on-error from this step after the rebuild PR has merged.`, then exits 1 (the step shows failed-but-allowed, the check stays green). I checked `tools/check_glibc_floor.py`: its **stdout** line is `<path>: highest GLIBC_ symbol version needed = <v> (floor <f>)` and the FAIL explanation goes to stderr, so the captured first line does name the version, as the Architect asked, and the FAIL text still reaches the log.
- **F2** `detect-native-changes`: the `if:` is the original push rule OR a dispatch on `refs/heads/main` with `inputs.force_native_rebuild == true`; a new step `forced` (dispatch only) writes `relevant=true` with no checkout and no diff; the checkout and the diff step now carry `if: github.event_name == 'push'`, so the push path is the old logic; the job output is `steps.forced.outputs.relevant || steps.check.outputs.relevant`. `commit-native-binaries`: `relevant == 'true'` AND (the original push rule OR the same dispatch condition); `needs` unchanged; branch naming and the PR text untouched. No file under `native/` or `src/OpenWSFZ.Ft8/` is touched.
- **F3** a blocking step "Guard - downloaded Linux .so glibc floor" right after the two artifact downloads, before the diff and the commit, so a blob above the floor stops the job before anything is committed.

## 3. Checked

| check | result |
|---|---|
| Scope | `.github/workflows/ci.yml` only; `src` and `native` diff 0 lines; the Linux leg's pin (24.04), the matrix label and the floor (2.39) are untouched |
| **Truth table, mechanically** (the old and the new `if:` expressions transcribed and evaluated for the seven scenarios; `qa` scratch evaluator) | **only scenario 1 (push to main by a person, native paths changed) and scenario 5 (dispatch on main, input true) reach `commit-native-binaries`**; scenarios 2, 3, 4, 6 and 7 do not (2 runs the detect job and reports `relevant=false`; 3, 4, 6, 7 skip it). The Developer's table matches |
| **Old against new, exhaustively** | for every push and pull-request combination (event x ref main or other x actor person or bot x native changed or not, 16 cases) the new detect and commit conditions **equal the old ones**: 0 of 16 differ. The new path exists only under `workflow_dispatch`, where no input existed before |
| Safety of the forced path | it requires a dispatch **on `refs/heads/main`** and the input true; an ordinary push cannot take it (the `forced` step is gated on `workflow_dispatch`, and the commit job re-checks the event, the ref and the input); the commit job still only opens a PR and never commits to `main` |
| YAML | the Developer parsed it with PyYAML (installed to a scratch directory only) and checked the structure; `actionlint` is not installed. **I did not independently parse it**; the PR's own CI run is the proof that it parses |
| Other gates | `check_version_bump`: no bump required; nothing under `tools/` parses `ci.yml` (only comments and the `pre_merge_check` recipe); G3, G8, G9, G10 and the test-delay lint are unaffected; the G9 jobs key on the event name |

## 4. Things to know before the first dispatch (not defects)

- **The macOS `.dylib` will always differ** on a forced run (its build is not byte-reproducible across runner instances), so the bot PR carries a rebuilt `.dylib` as well as the `.so`. Accepted by the Architect; not a finding.
- **The bot PR needs the Captain's merge**, and creating it needs the repository setting that lets Actions open PRs (the job has opened PRs before, #26 and #28, so it should be on).
- **F4 will warn on every run until the rebuilt blob is on `main`** (the committed blob needs GLIBC_2.43 today); that is the intended signal. F5 (remove `continue-on-error`) follows as a one-line PR on QA's word, after the rebuild has merged.
- The Developer did not add `--self-test` to the F3 step; the build leg already runs the self-test before it uploads the artifact.

## 5. Next (every remote action is the Captain's go)

Push `ci/force-native-rebuild` and open the PR (the PR's CI run proves the file parses and that F4 leaves the Linux leg green); merge; dispatch once with `gh workflow run ci.yml --ref main -f force_native_rebuild=true`; read the guard's output (the rebuilt blob's maximum `GLIBC_` must be <= 2.39); the Captain merges the bot PR; re-run the WSL Debian leg of `pre_merge_check` on a commit carrying the new blob; record the new `.so` SHA-256; then F5. **Nothing is pushed, dispatched or rebuilt yet.**
