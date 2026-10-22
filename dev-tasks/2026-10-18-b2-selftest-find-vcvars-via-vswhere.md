# Dev task: B2's freq_search self-test must find the C compiler on the current Windows runner (vswhere)

- **From:** QA. **To:** Developer. **Date:** 2026-10-18. **HK-000 handoff**, on the Architect's request and the **Captain's choice of option A** for PR #245 (2026-10-18).
- **Branch:** `qa/b2-to-main` (the branch of PR #245, `origin/qa/b2-to-main` = `e3fc6dec`; checked out in `D:\Projects\claude\_qa-scratch\series-b2main`, or check it out in your own worktree). Do NOT commit to `main`. **Commit and push to `qa/b2-to-main` only; do not open a PR, do not merge.** The Captain merges #245 (HK-010).
- **Test tooling only.** Scope: `tests/Ft8.FitProbe/native/run_freq_search_selftest.py`, function `find_vcvars()`. Nothing under `src/` or `native/` changes.

## 1. Context

PR #245 (Stage B B2 into `main`, shim 20260062) is green on ubuntu, macOS and G9, and **red on Windows in both CI runs** (runs 39115808800 and 39115812060). The one failing test is B2's own, `SubfeasPrunedFreqSearchTests.PrunedFreqSearch_MatchesTheReferenceFullFftSearch` (`tests/OpenWSFZ.Ft8.Tests/SubfeasPrunedFreqSearchTests.cs`, line 76, `code.Should().NotBe(3, ...)`): 488 of 489 pass.

The test runs `run_freq_search_selftest.py`, which builds a C program with MSVC. On the runner it prints `no Visual Studio vcvars64.bat found` and exits 3. The runner image is **`windows-2025-vs2026`** (image version 20261007.264.1). `find_vcvars()` searches only the years `('2022', '2019')` and the editions `('Community', 'Professional', 'Enterprise', 'BuildTools')`, under both Program Files roots. A VS 2026 install is outside that list (Architect's reading: probably a `18` directory; NOT verified, the job log prints no VS path). B2's own CI on `feat/sub-feas-stage-b` was already red on 2026-10-04 (run 37152788558); B2 has never been green on Windows CI.

`tools/pre_merge_check.py` already finds MSVC through `vswhere`, which is why the same test passes on QA's PC.

## 2. Actions

1. **Look first with vswhere.** In `find_vcvars()`, before the year/edition list, run
   `%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -find VC\Auxiliary\Build\vcvars64.bat`
   and use the first line of its output if the file exists. Guard against `vswhere.exe` being absent, returning non-zero, or printing nothing: any of those falls through to step 2 (no exception).
2. **Keep the current year/edition list as the fallback**, unchanged.
3. **If neither finds it, keep the failure exactly as it is:** print `no Visual Studio vcvars64.bat found` and exit 3. **No silent skip.** A skip would be option B, which the Captain did not choose. Do not change the test file's `NotBe(3, ...)` assertion.
4. **Print the vcvars path it used** (one line, e.g. `using vcvars: <path>`), so the CI log shows it. The test already writes the script output to the test log.
5. **Do not touch anything else.** The `.bat` build scripts that hard-code `Community` are out of scope. If you think they need the same fix, say so in the hand-back as a separate item; do not change them.
6. **Run the Windows test locally** (`dotnet test tests/OpenWSFZ.Ft8.Tests -c Release --filter "FullyQualifiedName~SubfeasPrunedFreqSearchTests"`; quote the filter and the pass count) and confirm the output contains the `using vcvars:` line.
7. **Commit and push to `qa/b2-to-main`.** One commit, message naming the cause (the image is VS 2026, the list is 2022/2019). Run `git diff --stat origin/qa/b2-to-main HEAD -- src/ native/` first: it must print **nothing**.
8. **Hand back.** Report: the commit SHA, the diff stat (one file expected), the local test result, and the CI result of the push if you can see it. QA reads the CI.

## 3. Acceptance criteria (what QA will check)

- (a) Windows CI on PR #245 is **green**, and the job log shows the self-test **using a vcvars path and passing**. A "skipped" result does NOT count.
- (b) `OpenWSFZ.Ft8.Tests` is **489/489 on Windows CI**.
- (c) It still passes locally on the Captain's PC and under WSL.
- (d) The fix commit's `git diff --stat -- src/ native/` is **EMPTY**; the commit changes `run_freq_search_selftest.py` only.
- The failure path is unchanged: with no VS found the script still prints the same message and exits 3 (QA reads the code for this; no test removal, no `Skip`).

## 4. After the hand-back (QA's part, not yours)

QA reads the CI of #245 and reports it to the Captain, who merges. Then DI sync 6 goes as planned (a separate dev-task).

## 5. References

- PR #245, `qa/b2-to-main`; failing runs 39115808800 and 39115812060; earlier red run 37152788558.
- `tests/Ft8.FitProbe/native/run_freq_search_selftest.py` lines 26-37 (`find_vcvars`), line 41 (the message); `tests/OpenWSFZ.Ft8.Tests/SubfeasPrunedFreqSearchTests.cs` lines 59-76.
- `tools/pre_merge_check.py` (finds MSVC through vswhere; the precedent).
- HK-000 (this handoff), HK-010 / HK-033 (the Captain merges), HK-011 (the Developer owns `src/` and `native/`; this task touches neither).
