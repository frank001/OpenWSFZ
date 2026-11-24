# HK-039 review of the last two Developer commits on `feat/xc-template-prior` (`bca4babf` tests, `3add5442` QSO rule) and `pre_merge_check` on the final hash. APPROVED; every gate passes except the WSL leg, which fails on the glibc defect already on `origin/main`

Reviewed-commit: bca4babf38fb074500ac3d9e49904699cd68858f
Reviewed-commit: 3add544221d3b191ebda69e5d44063b08291111f
Verdict: APPROVED

**Written:** 2026-11-14, `date -u` read 11:44:05Z. **Reviewer:** QA. **Parents:** `42f6a390` (APPROVED, `2026-11-14-1118-qa-code-review-xc-default-on-items-42f6a390-APPROVED.md`) then `bca4babf` then `3add5442`. **Spec:** the Architect's remedy acceptance ruling §6 (`arch/cross-cycle-prior` `2444aa50`); dev task `dev-tasks/2026-11-14-xc-qso-ignore-template-batch.md`. **Branch:** `feat/xc-template-prior` in the Developer's worktree, local, not pushed.

## 1. Verdict

**APPROVED, both commits.** `bca4babf` is the three observability tests I asked for and it kills the three survivors. `3add5442` applies the Architect's rule: **a batch-6 (template) row never starts an exchange with a new station**; the code is small, correct as read, and fully pinned by tests (all mutants killed by tests or stopped by the compiler). **`pre_merge_check` on `3add5442`: every gate passes except the WSL Debian leg and an AOT warning, both explained in section 4.** The PR is the Captain's go.

## 2. What I read and checked

- **`bca4babf`**: tests only (`git diff 42f6a390 bca4babf -- src native` is **0 lines**): `DatagramLine_TemplateCount_RestartsAfterEachDatagram`, `Reset_ClearsTheTemplateCount` and `T18_NoSource_ReportsZeroApAndTemplate`.
- **`3add5442` product code** (`LateBatch.cs`, `QsoAnswererService.cs`, `QsoCallerService.cs`, three small hunks): `LateOutcome.IgnoredTemplate` with the log token `ignored-template`; in `HandleLateIdleAsync` (answerer, Idle) and `HandleLateWaitAnswerAsync` (caller, First mode) a row with `r.Path == DecodeResult.PathTemplate` is skipped **after** the CQ parse, the decode filter and the engagement validation and **before** `CanStartWhole`, so it covers the immediate and the deferred answer; the loop **continues** (a later ordinary CQ or responder in the same batch is still answered); the counted outcome is returned only when nothing was answered, so `ignored-template` means "a template row that would have started an exchange was skipped". WaitReport, WaitRr73 and the panel, `ALL.TXT`, GridTracker and external reporting are untouched, as ruled. The Developer's §2 answers check out: the only reader of `_lastIdleDecodeBatch` is `TryEngageExternal` (`:391`, operator-initiated); the auto-answer scan reads batch 1's own rows (`:883`), never the snapshot; the caller's None mode only records a responder for the operator to select.

## 3. Checks

| check | result |
|---|---|
| **Scope fence** | `git diff 3add5442 vs bca4babf -- src/OpenWSFZ.Ft8 src/OpenWSFZ.Abstractions native`: **0 lines**; `src/OpenWSFZ.Ft8` and `native` against `42f6a390`: 0 lines; the decoder the arms ran on (`4b70e418`) is untouched. DLL pin `bbde6eb66af4cd429ffc46f67291ba718c1ae36ae39665faac24629bcb6e6528` held |
| **Full unfiltered suite** (QA, clean detached tree, `dotnet test OpenWSFZ.slnx -c Release`) | **0 failures in every project**: TraceabilityCheck 34, LicenseInventoryCheck 24, Rig 41, TestSupport 12, Config 204, Audio 40, E2E 9, **Web 448, Daemon 961, Ft8 821** (the Developer's counts exactly) |
| **Mutation, `3add5442`** (`xc_mutate4.py`, 17 mutants, plus one run by hand; `xc-build-3add5442-mutants.json`) | **15 killed by tests**: answerer filter inverted, skip removed, counted but still answered, wrong path constant (2 instead of 3), a template row ending the scan (a later ordinary CQ not answered), skip returning no-match; the same set for the caller (skip removed, inverted, no-match, scan ended); the token colliding with `ignored-stale`, the token spelling; **and the three survivors of `42f6a390` (D14, D15, D18) are now killed by `bca4babf`'s tests. 3 stopped by the compiler** (Q04, Q05, Q10 leave `skippedTemplate` assigned and never read, which is a build error here); none survived |
| TESTING_STRATEGY section 11 | the new test file has no sleeps or clock reads |

## 4. `pre_merge_check.py` on the exact final hash (HK-006)

Run in a clean `git worktree add --detach` of `3add544221d3b191ebda69e5d44063b08291111f` (`D:\Projects\claude\_qa-scratch\premerge-3add5442`), started 2026-11-14T11:33:58Z, summary read 11:43:29Z; base `origin/main` `cc1a39ad` (PR #284 merged).

| gate | result |
|---|---|
| native binary freshness (Windows DLL, Linux .so, macOS .dylib) | PASS (all at 20260072) |
| G9a doc/VERSION consistency, G9b mandatory VERSION bump | PASS, PASS |
| solution build (Release) | PASS |
| UDP capture margin lint, G10 test-delay-synchronization lint | PASS, PASS |
| full test suite (Release, Windows leg) | **PASS**: 24, 34, 41, 12, 204, 40, 9, 448, 961, 821 (0 failed) |
| G3 requirement traceability, G8 OpenSpec strict validation | PASS, PASS |
| self-contained non-AOT publish | PASS |
| **WSL Debian compile + test** | **FAIL** (Web 188, Ft8 272, Daemon 189, E2E 8 failed) |
| AOT publish | WARN: `vswhere.exe` is not recognised on this machine, so the local native linker toolchain is missing; an environment gap (CI runs the functional proof) |

**The WSL failure is the defect already on `origin/main`, not this change.** The loader says `libm.so.6: version 'GLIBC_2.43' not found (required by …/libft8.so)` (WSL Debian 13 has glibc 2.41); 362 mentions in the WSL leg, 356 `DllNotFoundException` and 184 `TimeoutException` (the QSO tests waiting for a decode that cannot happen), the rest knock-on. The tracked Linux blob is the **same one** as on `origin/main` and in the `f82b6432` check (SHA-256 prefix `e8cb81805322`), and `git diff --stat ce5734b6 3add5442 -- native src/OpenWSFZ.Ft8/Native` is **0 lines**. The failure counts are higher than the `f82b6432` run (Ft8 244, Daemon 176, Web 187, E2E 8) by roughly the number of tests added since. PR #284 (the glibc guard) is merged, but it only checks a freshly built `.so`; the committed blob stays at 2.43 until a native change triggers the rebuild, and the check name "Build & Test (ubuntu-latest)" now reports the pinned 24.04 leg. **This is a named failure for the Captain to accept (HK-006), not a regression of this branch.**

## 5. Not established

macOS and Linux CI have not run these commits (not pushed; pushing is the Captain's go, and CI would show the macOS result in about 6 minutes). The Linux leg of CI builds its own `.so` on the pinned 24.04 image, so it does not hit the loader failure. Nothing on air changes: the flag defaults OFF; turning it on at the station is a separate go and starts a new era (record the daemon start and the commit, never pool across it).

## 6. What is left before a PR

The Captain's go to push and open the PR (flag default OFF), after he accepts the named WSL failure. Owed by the Architect before the flag is turned on: nothing open from QA's findings (the PSK tag, the queue capacity and the QSO rule are all built and reviewed).
