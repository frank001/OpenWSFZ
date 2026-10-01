# Developer handoff: make four SUB-FEAS `Ft8.Tests` portable to macOS arm64 (8.1, 8.2, 8.6, 8.7), PR #196

**Date:** 2026-10-01 (18:16 UTC). **From:** QA. **To:** Developer. **Priority:** high: it is the only red gate on PR #196 (`merge/sub-feas` @`26374f60`); Windows, Ubuntu and G9 pass. **Test-only.** `src/` and `native/` stay untouched (HK-011).

## 1. What fails, and why (diagnosed from CI logs and one CI experiment)

On the macOS job (`macos-latest` = Apple Silicon, `osx-arm64`), `OpenWSFZ.Ft8.Tests` fails **4 of 417**, identically in both CI runs (same hashes, so deterministic, not a race). All four are in `tests/OpenWSFZ.Ft8.Tests/SubfeasNativeSpeedTests.cs`.

| Test | Failure | Cause |
|---|---|---|
| **8.1** `Fit_NoDeadline_OutputBitIdenticalToBase` | the **analytic signal** of `synth-qso-01.wav` hashes differently from the golden (fails at the first assertion, before any fit) | bit-exact float golden recorded on x86-64 |
| **8.2** `cancelling one fit does not disturb other in-flight fits` | a fit beside a cancelled one hashes differently from the golden | same |
| **8.6** `Fit_ManyWorkersManyCycles_DeterministicAndNoInterference` | `worker 2, round 0: a completed fit must equal its single-thread hash` | same |
| **8.7** `Workspace_NoGrowthAfterWarmup_AndFreedAtDispose` | freed bytes `0`, expected `> 18 729 508` ("the memory really goes back") | macOS has no equivalent of the Linux `malloc_trim` step; libmalloc keeps freed pages |

**The experiment (QA, 2026-10-01, branch `exp/macos-fp-contract-off` @`622c32d6`, CI run 36904592630):** adding `-ffp-contract=off` to the five `clang` compile lines of the macOS native build makes **8.1, 8.2 and 8.6 PASS** on macOS (`Ft8.Tests` 4 failed, then 1 failed of 417; only 8.7 stays red; Windows and Ubuntu green). So the three hash failures are **FMA contraction**: Apple clang on arm64 fuses multiply-add by default, x86-64 does not, so the same C code gives different last bits. The goldens (`tests/Ft8.FitProbe/golden/e1-base-5a6a4dc0.csv`) were recorded on the win-x64 base DLL; Linux x86-64 happens to agree with them.

**DECIDED by the Captain, 2026-10-01: the product build is NOT changed.** `-ffp-contract=off` is **not** adopted for the macOS native build, and the experiment branch was deleted (remote and local). So the macOS library keeps its default arm64 numerics, the goldens stay x86-64 only, and **the tests themselves must be made portable**; nothing may depend on that flag. The experiment is recorded here only as the explanation of the cause.

## 2. Branch

Cut **`fix/sub-feas-macos-tests`** from **`origin/merge/sub-feas`** (PR #196's head, `26374f60`; `git fetch` first). QA merges the result back into the PR branch. Check `git branch --show-current` before committing; stage by path.

## 3. Actions

1. **8.7 (always needed).** In `SubfeasNativeSpeedTests.cs`, `ReturnedBytesAfterFree()` (~line 560) calls `LibC.TrimHeap()` only on Linux, and the measured figure comes from `PrivateBytes()` elsewhere (~line 557: `OperatingSystem.IsLinux() ? AnonRssBytes() : PrivateBytes()`). Give macOS an explicit branch. Recommended, decisive in one CI iteration: on macOS **assert the plateau (no growth after warm-up) and the "usable again" part, and do not assert that freed bytes return to the OS**, with a comment stating why (libmalloc retains freed pages; the Linux `RssAnon`/`malloc_trim` fix `a8abe4de` has no macOS analogue). Windows and Linux keep the full assertion unchanged. You may *try* `malloc_zone_pressure_relief(NULL, 0)` (`libSystem`, wrapped in a `try/catch` for `EntryPointNotFoundException`) first only if you can show it works; you cannot run macOS locally, so do not leave an unproven macOS return assertion in.
2. **8.2 (in-flight) and 8.6 (many workers): compare against an in-process single-thread reference, not the golden.** What these two tests actually prove is "a concurrent fit equals the same fit run alone, and a cancelled neighbour does not disturb it". Compute the reference once, in the same process, by running `Ft8LibInterop.SubfeasFitSignal` sequentially for each grid job before the concurrent phase, and compare each completed concurrent result to **that** hash. This is platform-independent by construction and is a truer test of the claim. Keep every other assertion (forced-cancel modes, `rc == -4` and all-zero `Shat` on cancel, lease and pool checks, worker and round counts) exactly as it is.
3. **8.1 (bit-identity to the base DLL): keep the golden comparison only where it is valid.** Introduce one predicate, for example `GoldenApplies` = (Windows or Linux) and `RuntimeInformation.ProcessArchitecture == Architecture.X64`. Where it holds, assert against the golden exactly as today. Where it does not (macOS arm64), **do not skip silently**: run the same inputs twice in-process and assert the two hashes are equal (portable determinism), and state in the test output that bit-identity to the base DLL is asserted on x64 only. Keep the predicate in **one place** so QA can widen it if the Captain adopts `-ffp-contract=off`.
4. Do not weaken or remove any other assertion. No new bare `Task.Delay`/`Thread.Sleep` (Gate G10). If a change tempts you to touch `src/` or `native/`, **stop and tell QA** (HK-011).
5. List, do not fix, any other test that compares a float-derived hash or a memory figure against a recorded value (QA's `git grep` found the SUB-FEAS file only for float goldens, plus three win-x64 binary-pin files that hash the DLL itself: `AwgnFpReplayTests`, `FpParityP3Tests`, `Row0rCarryForwardTests`).

## 4. Acceptance criteria (what QA checks)

1. `git diff --stat origin/merge/sub-feas -- src native` is **empty**; the diff is confined to `SubfeasNativeSpeedTests.cs` (and, if you add one, a shared test helper).
2. Your report states, for **8.1, 8.2, 8.6, 8.7**, what each now asserts on **Windows**, **Linux** and **macOS arm64**, and quotes the unchanged assertions you kept.
3. **Windows:** `dotnet test tests/OpenWSFZ.Ft8.Tests -c Release`, unfiltered: pass counts quoted. **WSL Debian:** the same, unfiltered. A filtered run is not a result (HK-022).
4. **The macOS acceptance is CI, and QA runs it:** after your report QA pushes your branch (CI runs on any branch push) and reads the macOS `OpenWSFZ.Ft8.Tests` line. **Pass bar: 417 passed, 0 failed on macOS**, with Windows and Ubuntu still green. You cannot verify macOS yourself; say so, do not claim it.
5. `python tools/check_test_delay_sync.py` OK.
6. Only QA pushes; commit locally.

## 5. References

- Failing CI: PR #196 runs 36897258513 (push) and 36897468932 (pull_request), macOS job, `Test (Release)` step; experiment run 36904592630.
- Tests: `tests/OpenWSFZ.Ft8.Tests/SubfeasNativeSpeedTests.cs` (8.1 at ~37, 8.2 at ~127, 8.6 at ~158, 8.7 at ~280; memory probes ~545 to 575). Golden: `tests/Ft8.FitProbe/golden/e1-base-5a6a4dc0.csv`.
- macOS native build recipe: `.github/workflows/ci.yml` (the `Build native macOS dylib (ARM64, Clang)` step, five `clang -std=c11 ... -O2 -Wall -fPIC` lines). The stale committed `.dylib` warning is a separate, expected message: CI rebuilds the library from source, so it is not the cause.
- Prevention note for authors (QA-to-QA plan, Layer 1): a numeric golden is valid only on the platform and architecture that recorded it; compare in-process, record per platform, or use a stated tolerance. Memory-return assertions need an explicit branch per OS in the CI matrix.
