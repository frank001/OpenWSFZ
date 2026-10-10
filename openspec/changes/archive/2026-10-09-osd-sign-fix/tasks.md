> **Status note (QA, 2026-10-09, when the change was archived).** Implemented and merged: `feat/osd-sign-fix` (`3048176d`, `3276573b`, shim 20260060) in PR #221
> (merge `9fe32e8d`, 2026-10-09, CI green). Checked items below are evidenced by the merged code and tests (`tests/OpenWSFZ.Ft8.Tests/OsdSignFixTests.cs`, `FR-084:`),
> the pre-merge check on the merged tree (full unfiltered Windows suite, 0 failures, 2026-10-09) and QA's reports (`qa/rr-study/results/2026-10-08-osd-fix/`,
> `…/2026-10-09-osd-fix-test/`, `…/2026-10-09-s1-snr-replay/`). **Item 1.1 (the FILE:LINE drift record in `design.md`) was not written and stays unchecked.**
> The follow-on change (default `osdNhardMax` 24, valid range [24, 100], one-time 40 → 24 migration) is **FR-085**, delivered without its own OpenSpec change
> (specs `configuration` and `decoder-settings` were amended directly). TEST (860 cycles, replay, one 40 m night): F-GO, NET +0.208 pp [+0.117, +0.326],
> ΔU −0.073 [−0.090, −0.058]; a correctness fix with a small dividend, not a decode-rate lever.

## 1. Pre-implementation (record in `design.md` before writing code)

- [ ] 1.1 Re-check every FILE:LINE in the `design.md` table on the branch tip; record drift. Grep `osd_decode(` over `native/` and `src/` and list every hit with FILE:LINE (expected: the definition and three callers, all in `decode.c`).
- [x] 1.2 Record the helper's form (new buffer or in place) and why.
- [x] 1.3 Pick the shim number: the next free above every number on any live ref (`git grep -h "define FT8_SHIM_VERSION" origin/*`); at the time of writing `origin/feat/sub-feas-stage-b` holds 20260059, so **20260060** (design D4).

## 2. Native (`native/`, `src/OpenWSFZ.Ft8/Native/`, shim bump)

- [x] 2.1 Add the helper to `decode.c` and use it at the three callers, `osd_decode` and the gate reading the same array (design D1). Fix the comments that state or imply the old convention (the `decode.c` top-of-file R4/R5 block and the `osd_decode` header). Do NOT touch `native/ft8_lib_vendor/ft8/ldpc.c:9` (upstream's comment).
- [x] 2.2 `int s_osd_sign_fix = 1;` in `ft8_shim.c`, `extern` in `decode.c`, `ft8_set_osd_sign_fix` / `ft8_get_osd_sign_fix` exported and declared in `ft8_shim.h`; add them to the export lists (`native/ft8_lib_build/rebuild_shim.bat`, `build_linux.sh`, any `.def`) and `BUILD.md`.
- [x] 2.3 Bump `FT8_SHIM_VERSION` everywhere it lives (`ft8_shim.h` incl. the history entry, `Ft8LibInterop.cs` `ExpectedShimVersion`, `win-x64/libft8.version.txt`, `BUILD.md`, `rebuild_shim.bat` header text, any ABI-sentinel test constant). `openspec/specs/ft8lib-interop/spec.md` is not edited here (the archive step folds in the delta). Rebuild `libft8.dll` and `libft8.so`; macOS by CI. Pin the DLL SHA-256 (actual and pinned); run `python tools/check_native_version.py <binary> <number>` for each binary built.
- [x] 2.4 Existing OSD / gate tests: run them first, re-baseline **only** those that encoded the inverted behaviour, list each with the reason (design D5).

## 3. Tests

- [x] 3.1 **Sign unit test, native or interop level:** a known codeword's LLR vector with enough erasures or flipped signs that 50-iteration BP fails and depth-2 OSD succeeds on the corrected path. Switch 1: payload equal, accepted `nhard` ≤ the injected flip count, corr/norm > `OSD_CORR_THRESHOLD`. Switch 0: no decode. The test must fail if the gate is left reading the un-negated array (QA mutates it).
- [x] 3.2 **No-bare-callers scan:** a test that fails if `osd_decode(` appears outside its definition and the pattern of design D1 (every caller preceded by the helper on the same array the gate reads).
- [x] 3.3 The all-ones word is not accepted.
- [x] 3.4 **Switch-0 characterisation (flag-OFF-like identity):** with the switch at 0, a fixed set of recorded cycles gives the same calls, results and order as the previous shim.
- [x] 3.5 Interop: set/get round trip through `Ft8LibInterop` and the test double; the ABI sentinel test follows the new number.
- [x] 3.6 Not configurable: a test (or source scan) that no config record, settings page or API model carries the switch.

## 4. Diagnostics (R6)

- [x] 4.1 If the per-accepted-OSD `nhard`, corr/norm, depth and batch are not already returned to the harness, return them (aggregates only, no message text, HK-037). The existing `C:\Temp\nhard_diag.log` writes (`decode.c` near `:725`, `:1132`) are unchanged.

## 5. Docs and version

- [x] 5.1 `REQUIREMENTS.md`: the next FR number and a change-history row; tests carry the `FR-nnn:` prefix (gate G3). `proposal.md` declares **User-facing: no**; confirm with QA whether a VERSION bump is wanted (the gate G9b reads the proposal from git: commit before running it).
- [x] 5.2 `native/.../BUILD.md` and the shim header history entry describe the correction and say `nhard` 40 was calibrated on the inverted output.

## 6. Verification (Developer, then QA)

- [x] 6.1 Full unfiltered `dotnet test OpenWSFZ.slnx` and `node --test web/js/*.test.js`; quote the exact commands and the pass/fail/skip counts. Bracket the station config's mtime around the run.
- [x] 6.2 QA: A-SIGN′ and A-OFF on the built DLL (spec §5.1, ruling §3), then probes, TRAIN calibration, TEST. These are QA's measurements, not the Developer's.
