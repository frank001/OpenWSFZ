# Developer task: the Linux `libft8.so` gets a glibc floor of 2.39 (a pinned build image) and a CI guard that fails above it

**Date:** 2026-11-13
**Prepared by:** QA
**Audience:** Developer (to execute); Captain (hands this to the Developer, HK-000; sign-off before merge, HK-010)
**Authorised by:** the Architect's ruling `git show arch/cross-cycle-prior:qa/rr-study/2026-11-13-1715-architect-ruling-linux-so-glibc-floor.md` (`c414bdb1`, local; read it, it is the authority), on QA's evidence `qa/rr-study/2026-11-13-1658-qa-xc-build-pre-merge-check-f82b6432.md` (`qa/same-chain` `936001bf`). **The Captain's go to start this is still owed.**
**Status:** Proposed. HK-011: `.github/` and a regenerated binary under `src/OpenWSFZ.Ft8/Native/`, so a separate Developer session. 🛑 **No push, no PR, no merge on your own initiative** (QA pushes, HK-033; every merge is the Captain's, HK-010).
**Branch:** a NEW branch off **`origin/main` (`ce5734b6` today)**, e.g. `fix/linux-so-glibc-floor`. **Not** on `feat/xc-template-prior`, and do not merge `origin/main` into that branch (its arms pin a `libft8.so` SHA-256).
**Version:** check `python tools/check_version_bump.py origin/main` (commit before re-running G9b) and bump whatever the gate demands for a `.github/`/native-binary change. State what it demanded.

## The defect

`origin/main`'s tracked `src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so` requires **`GLIBC_2.43`** (highest symbol version; it was 2.35 at `70bc72b1`). It changed in `fa81a0be` (github-actions[bot], 2026-11-12 12:51Z: "rebuild Linux and macOS binaries to shim 20260072"), after `build-test`'s `os: ubuntu-latest` leg (`.github/workflows/ci.yml` lines 28 to 29) apparently moved to an image with glibc 2.43. Anything older cannot load it: WSL Debian 13 (glibc 2.41, no newer available) fails `pre_merge_check`'s WSL leg with `version 'GLIBC_2.43' not found` (Ft8 244, Daemon 176, Web 187, E2E 8 failed). The station (Windows) and sol (glibc 2.43) are unaffected.

## Requirements

| # | Requirement |
|---|---|
| **G1** | The committed Linux `.so` loads on **glibc >= 2.39** (highest `GLIBC_x.y` symbol version <= 2.39). |
| **G2** | Pin the Linux leg of `build-test` so the build runs on the floor image: **`ubuntu-24.04` instead of `ubuntu-latest`** (recommended), or a pinned container (e.g. `debian:12`, glibc 2.36) if 24.04 is unavailable or you want independence from image retirements. **You choose; say which and why in your report.** `commit-native-binaries` only commits the artifact, so its runner may stay as it is. Mind the matrix `if: runner.os == 'Linux'` conditions and the "Check committed Linux .so is current" step (about line 219): state how the pin interacts with it. |
| **G3** | **The guard.** After the Linux build, a CI step reads the `.so`'s highest `GLIBC_x.y` (`objdump -T` or `readelf -V`) and **fails above 2.39**. The 2.39 constant is named once, in one place. It must print the value it found. |
| **G4** | **Negative test (required):** show the guard FAILS on the current 2.43 blob (run the same command on `git show origin/main:src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so`, locally and, if you can, in a CI run), and passes on a blob at or below 2.39. Put the check's logic where a test can reach it (a small script under `tools/` with a self-test, in the repo's existing pattern for `check_*.py` tools), not only inline YAML. |
| **G5** | `.github/` and the binary only. **No `native/` source change, no `src/` C# change.** If the rebuild needs one, stop and report. |

## Acceptance (QA verifies, from a clean checkout of your commit)

1. G3's guard fails on the current blob and passes on a rebuilt one (QA re-runs your negative test).
2. The rebuilt `.so` (from the bot's `commit-native-binaries` after the merge, as usual, or from a local build in the pinned image if you can make the same bytes) has highest `GLIBC_` <= 2.39.
3. `python tools/pre_merge_check.py` from a clean checkout: **the WSL Debian leg green with the rebuilt `.so`**, and every other gate still PASS (G9a, G9b, G10, G3, G8, the full suite).
4. CI green on the branch (QA pushes it; macOS and Windows legs unchanged).

## Report (reply to QA, as `dev-reports/` or a message)

- Which mechanism (24.04 or a container) and why; the exact diff of `.github/workflows/ci.yml`.
- The guard's command, its constant, its self-test and the negative-test output on the 2.43 blob.
- The highest GLIBC version of the rebuilt `.so` and its SHA-256 (and of the old one, `e8cb81805322...`).
- What the VERSION gate demanded.
- **Not ruled and not in scope:** the macOS `.dylib` from `fa81a0be`; if you can cheaply read its minimum macOS version and say so, do, but change nothing.
