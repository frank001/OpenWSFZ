> **Note (2026-07-03):** The Captain directed QA to implement this directly rather
> than route it through a developer handoff — a deliberate one-off deviation from
> HK-000 for this CI-only item. This document is retained as the design record.
> Implemented on branch `chore/ci-native-binary-reproducibility`. The link flag used
> is `-Wl,-no_uuid` (confirmed correct; the `-Wl,-random_uuid,no` / `-reproducible`
> alternatives floated in §3 below were speculative and are superseded — `-no_uuid`
> is the documented ld64 flag for omitting `LC_UUID` outright). A permanent
> regression-guard step ("Verify deterministic macOS link") was added to the
> workflow so this can't silently regress.

# Handoff: Fix non-reproducible macOS native binary build (CI churn)

## 1. Context

The `commit-native-binaries` CI job (added `2f18865`/`55a2046`, 2026-06-27) rebuilds
`libft8.so` and `libft8.dylib` on every push to `main`, does a raw `git diff --exit-code`
against the committed binaries, and opens an automated PR (`ci/native-binaries-shimN`)
whenever the bytes differ.

QA review on 2026-07-03 found this job has fired **four times already** for the exact
same shim version, all merged to `main` under an identical commit message:

| Commit | Date | Label |
|---|---|---|
| `ec5bae0` | 2026-06-24 16:17 | shim 20260030 |
| `ea452d9` | 2026-06-24 20:39 | shim 20260030 |
| `d46450a` | 2026-06-27 13:31 | shim 20260030 |
| `5729c83` | 2026-06-28 10:46 | shim 20260030 |

A fifth instance, PR #23 (branch `ci/native-binaries-shim20260030`, commit `53881bf`,
opened 2026-06-30), was **closed without merging** on 2026-07-03 — it carried no source
change, no CI verification (`[skip ci]` on the commit), and was 36 commits behind `main`.
The `libft8.dylib` size differed between `main` (89728 bytes) and the PR branch
(89664 bytes) despite both being labelled "shim 20260030" — i.e. the *semantic* shim
version is stable, but the *raw bytes* of the macOS build are not.

**Root cause (near-certain):** `clang -dynamiclib` embeds a fresh, randomly-generated
`LC_UUID` load command into the Mach-O output on every link, by default, on macOS.
Nothing else in the build (`-O2`, no `-g`, pinned Clang target triple, pinned
`ft8_lib` branch/commit) varies between runs. The Linux `.so` build has *not* exhibited
this churn (GNU `ld`'s default `--build-id` is content-derived, not random), consistent
with only the `.dylib` differing in the PR #23 diff.

**Impact:** every `main` push that touches anything in the build-test matrix produces a
spurious "binaries changed" PR that carries zero functional change, consumes review
attention, and (per the four merged instances above) pollutes commit history with
no-op binary churn. Left alone, this recurs indefinitely.

## 2. Branch name

`chore/ci-native-binary-reproducibility`

**Do not commit directly to `main`.**

## 3. Actions

1. In `.github/workflows/ci.yml`, locate the macOS build step ("Build native macOS
   dylib (ARM64, Clang)", currently lines ~74-99). Add a deterministic-link flag to the
   final `clang -dynamiclib` invocation (line ~92-95) to suppress the random UUID:
   ```
   clang -dynamiclib -target arm64-apple-macos11.0 \
     -Wl,-random_uuid,no \
     -o libft8.dylib \
     constants.o crc.o decode.o encode.o ldpc.o message.o text.o \
     monitor.o kiss_fft.o kiss_fftr.o ft8_shim.o
   ```
   If `-Wl,-random_uuid,no` is rejected by the linker version GitHub's `macos-latest`
   runner ships, use the alternative `-Wl,-no_uuid` flag, or Apple's newer
   `-Wl,-reproducible` flag (Xcode 11+ ld64) — try in that order and use whichever
   the runner's `ld` accepts. Confirm which flag is accepted by running
   `clang -dynamiclib -Wl,-random_uuid,no ... ` locally in the workflow and checking
   the step doesn't fail with an "unknown option" linker error.
2. Do **not** touch the Linux `.so` build — no evidence of churn there; adding
   `--build-id=sha1` speculatively risks an unrelated regression for no observed gain.
3. Verification, before opening a PR: trigger the `build-test` matrix twice in a row on
   the same commit (two `workflow_dispatch` runs, or push an empty commit and re-run),
   download both `libft8-dylib-osx-arm64` artifacts, and confirm:
   ```
   sha256sum libft8.dylib   # from run 1
   sha256sum libft8.dylib   # from run 2
   ```
   produce identical hashes. Do this locally/in-branch before merging — don't rely on
   `main` to prove it after the fact.
4. Confirm `tools/check_native_version.py` (the shim-version staleness gate) still
   passes unmodified — this fix must not touch shim-version detection, only byte-level
   determinism of the link step.
5. Once merged, watch the next 1-2 organic `main` pushes: the `commit-native-binaries`
   job should report `changed=false` for the macOS dylib when no source/shim-version
   change occurred. If a spurious PR opens again, the fix didn't address the actual
   non-determinism source and needs re-diagnosis (e.g. check for embedded build paths
   via `-fdebug-prefix-map`, or timestamps in `ar`/object files via `ZERO_AR_DATE`).

## 4. Acceptance criteria (QA will verify)

- [ ] Two independent CI builds of `libft8.dylib` from the same commit are byte-identical
      (`sha256sum` match), demonstrated in the PR description with both hashes shown.
- [ ] `tools/check_native_version.py` staleness gate still passes for both Linux and
      macOS.
- [ ] CI green on `chore/ci-native-binary-reproducibility` itself (this is a workflow
      file change on a human-authored branch, so `pull_request` CI triggers normally —
      unlike the bot-committed `ci/native-binaries-shimN` branches).
- [ ] No functional change to `libft8_shim.c`, `ft8_lib` overlay, or `Ft8LibInterop.cs`
      — this is a build-flag-only change.
- [ ] Follow-up: after merge, the next 1-2 organic `main` pushes should NOT spawn a new
      `ci/native-binaries-shimN` PR unless source or `FT8_SHIM_VERSION` genuinely changed.

## 5. References

- `.github/workflows/ci.yml` lines 74-107 (macOS build), lines 324-423
  (`commit-native-binaries` job, diff check at 355-362).
- Closed PR #23: https://github.com/frank001/OpenWSFZ/pull/23
- Duplicate "shim 20260030" commits on `main`: `ec5bae0`, `ea452d9`, `d46450a`, `5729c83`.
- MEMORY.md "Native binary state" section (CI commit-back mechanism background,
  `2f18865`, `55a2046`).
