# Linux `libft8.so` glibc floor: review of the Developer's `4c377f75`: RETURNED, one required test (the guard's exit codes are not pinned)

Reviewed-commit: 4c377f75bac59efdcd8510048cea17a3ddbcb832
Verdict: RETURNED

**Written:** 2026-11-13, `date -u` read 17:24:38Z. **Branch:** `fix/linux-so-glibc-floor` (off `origin/main` `ce5734b6`), the Developer's, local. **Task:** `dev-tasks/2026-11-13-linux-so-glibc-floor.md` (`7e250555`); ruling `arch/cross-cycle-prior` `c414bdb1`. **Delta read:** `.github/workflows/ci.yml` (+17/-1) and the new `tools/check_glibc_floor.py` (163 lines); `git diff --stat ce5734b6 4c377f75` lists those two files only (G5 met: no `native/`, no `src/`).

## 1. What I checked, and what I found

| check | result |
|---|---|
| Workflow change | The matrix entry `ubuntu-latest` becomes `ubuntu-24.04` with a comment; the new step "Guard - Linux .so glibc floor" runs `--self-test` then the guard, `if: runner.os == 'Linux'`, **after** "Build native Linux .so" and **before** "Upload Linux .so artifact", so `commit-native-binaries` cannot receive a blob above the floor. Mechanism choice (24.04, not a container) is reasoned and acceptable. Not run in CI (the Developer does not push; neither have I) |
| Guard on the real blobs (my own run, `_qa-scratch\glibc-review`) | `ce5734b6` blob (SHA-256 prefix `e8cb81805322`): **2.43, rc 1, FAIL**; `70bc72b1` blob: **2.35, rc 0, OK**; a non-ELF file: rc 2. This reproduces the Developer's negative and positive controls (G4) |
| Guard self-test | 9 of 9 pass on the branch |
| **Mutation of the guard** (7 + 4 mutants of `tools/check_glibc_floor.py`, each run against the self-test) | Killed: `<=`→`<`, floor 2.40, floor 2.38, `max`→`min`, dropping the third version component, `check` always true. **Survived (3, genuine): the failing path of `main` returns 0 instead of 1; the usage error returns 0 instead of 2; the read error returns 0 instead of 2.** |

## 2. Required change (one)

**The self-test pins the decision (`check`, `highest_glibc`) but not the process exit codes, and CI acts only on the exit code.** A guard that printed `FAIL: needs GLIBC_2.43` and exited 0 would pass its own self-test and the CI step: the regression this task exists to stop would go through silent. Mutant "fail path `return 1` → `return 0`" survives and, on the real 2.43 blob, gives rc 0.

- **Add self-test cases that call `main` end to end** (a temporary synthetic ELF written to a temp file, then `main([path])`): above the floor → **1**; at the floor → **0**; a missing file and a non-ELF file → **2**; `main([])` (usage) → **2**. Remove the temp file afterwards.
- Re-run the 11 mutants above; all must be killed.

No other change is required. Noted, not required: (a) the check name becomes "Build & Test (ubuntu-24.04)"; if branch protection requires the old name it needs the Captain's update; (b) four OpenSpec specs and `TECHNICAL_SPEC` still say the matrix is `{ windows-latest, ubuntu-latest, macos-latest }` (Developer's note; HK-002 audit may want them reworded); (c) the macOS `.dylib` read (LC_BUILD_VERSION minos 11.0.0) is the Developer's, read-only, unreviewed by me.

## 3. Still owed after the fix (acceptance, from the task)

The WSL Debian leg green needs the **rebuilt** `.so`, which only the bot's `commit-native-binaries` produces after the merge (the Developer declines a local build: not the same bytes). So acceptance items 2 to 4 are post-merge checks: on the first `main` build after the merge, `readelf -V` or the guard reads at most 2.39, and `pre_merge_check.py` WSL leg passes from a clean checkout. I will run them then.
