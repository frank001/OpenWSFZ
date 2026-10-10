# Developer handoff: #122 step 4 — extend completeness test 2.4a to every native source in libft8.dll

**Date:** 2026-10-03. **From:** QA. **To:** Developer. **Priority:** blocks the step-4 merge.
**Ruling:** Architect, §0b of `qa/rr-study/2026-10-03-1440-architect-to-qa-spec-122-step4-early-decode.md` (commit `bffb4c95` on `arch/122-latency`, 2026-10-03 17:36Z by `date -u`); read it with `git show bffb4c95:<path>`.
**Branch:** your `feat/122-step4-early-decode-panel` (`fee81a2b`). Test change only unless the scan finds a global that is neither in the image nor exempt (then stop and tell QA before touching `native/`).

## 1. Why

QA's review found the build sound. QA's A2 replay could not reproduce the known loss with the restore removed (the positive control), so the Architect ruled A2 "not evaluable for this defect" and **R4 now rests on A2b**. A2b is only as strong as the list of globals it covers. Test 2.4a today scans `ft8_shim.c` only; the Architect's quick grep found no mutable statics in the ft8 core and only the `subfeas_fit.c` pool statics (`:596-612`), but a grep is not a guard. The test must make it mechanical.

## 2. What to change

1. Extend test 2.4a (`tests/OpenWSFZ.Ft8.Tests/HashStateCompletenessTests.cs`) to scan **every native source compiled into `libft8.dll`**: `native/ft8_lib_vendor/**` (`ft8`, `common`, `fft`, `refine`, `subfeas`) and `native/ft8_lib_build/patched/**`, as well as `ft8_shim.c`. Derive the list from the build (`native/ft8_lib_build/rebuild_shim.bat` / `build_linux.sh` compile lists) or assert the scanned set equals the compiled set, so a source added to the build and not the scan fails the test.
2. Every **mutable file-scope static, mutable global and thread-local static** (`static` non-`const`, `_Thread_local`, `__declspec(thread)`, any TLS macro; also function-scope `static` locals that are mutable) must be classified in the manifest as exactly one of:
   - **in the image** (`HSM-IMAGE`);
   - **reset per call (FILE:LINE)**;
   - **not written on the pass-0 path (FILE:LINE)** — new category; the FILE:LINE names the evidence (for example the pool statics at `subfeas_fit.c:596-612` are only written on the residual pass, which the early entry never runs).
3. The test fails on an unclassified variable and on a manifest entry that names a variable that no longer exists (as today).
4. Record the full scan output (each variable, its file, its class) in `design.md` D4, replacing QA's first-pass table where it is superseded.
5. Add a **mutation check you can run**: add a file-scope mutable static to a vendored source (not the shim) and show 2.4a fails; revert. Quote it in your report.

## 3. Acceptance (QA verifies)

Full unfiltered `dotnet test OpenWSFZ.slnx` and `node --test web/js/*.test.js`, counts quoted; 2.4a fails when QA adds a stray static to a vendored file, and passes on the real tree. **Merge rule (Architect): A2b PASS with the extended 2.4a.** If the scan finds a mutable global written on the pass-0 path that is not in the image, STOP and tell QA: that is a state-leak defect, and a `native/` change with a new shim number.

## 4. CPU

QA is running acceptance checks (A1b, A5) on the same PC: tell QA before starting a full suite.

## 5. Report back

The scan table (variable, file:line, class); the exact `dotnet test` and `node --test` lines with counts; your mutation check; anything you could not do.
