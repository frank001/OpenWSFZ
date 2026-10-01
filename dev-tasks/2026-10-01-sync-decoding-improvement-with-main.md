# Developer handoff: sync `decoding_improvement` with `main` (v0.53), including a native-interface merge, an FR renumber and a new shim

**Date:** 2026-10-01 (19:22 UTC). **From:** QA. **To:** Developer. **Priority:** high: it gates the next endurance run. **Authority:** the Captain decided on 2026-10-01 to sync `decoding_improvement` before the next endurance run, as one dedicated merge, with a new arm label. `src/` and `native/` are touched, so a separate Developer session does the work (HK-011). **Only QA pushes** (Captain).

## 1. Why, and what QA measured

`decoding_improvement` (`origin/decoding_improvement` @`51e40b55`, VERSION 0.52, shim 20260054) is the Captain's long-lived decode-rate branch; endurance and R&R runs build from it. `main` is now `9bade2bc` (VERSION **0.53**, shim **20260056**) after PR #196 (SUB-FEAS, config-save, G10/Linux/macOS test fixes) and #197 (flake fixes). Until the sync, builds from `decoding_improvement` still **replace** the config on `POST /api/v1/config` (a Settings save wipes unsent fields, #193), so no Settings saves in measurement runs.

**QA's dry run (2026-10-01, throwaway worktree, nothing committed or pushed):** `git merge --no-commit origin/main` into `origin/decoding_improvement`: **17 commits ahead, 34 behind; 12 conflicted files**:

| Area | Files |
|---|---|
| Docs and version | `README.md`, `REQUIREMENTS.md`, `VERSION` (0.52 vs 0.53), `openspec/specs/ft8lib-interop/spec.md` |
| Native interface (C#) | `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs`, `Ft8NativeInteropAdapter.cs`, `IFt8NativeInterop.cs` |
| Native shim and build | `src/OpenWSFZ.Ft8/Native/ft8_shim.h` (2 large hunks), `Native/BUILD.md`, `Native/win-x64/libft8.version.txt`, `Native/win-x64/libft8.dll` (binary), `native/ft8_lib_build/rebuild_shim.bat` |

**The two real collisions** (everything else follows from them):

1. **Native exports: both sides added different functions.** Only on `decoding_improvement`: `ft8_get_decoder_params`, `ft8_set_supp_params`, `ft8_get_supp_params`, `ft8_get_last_suppression`, `ft8_set_probe`, `ft8_clear_probe`, `ft8_get_probe_llrs` (decoder-param-readout and the pass-1 probe tap, shim 20260054). Only on `main`: `ft8_set_diagnostics_enabled`, `ft8_subfeas_compute_analytic`, `ft8_subfeas_fit_signal`, `ft8_subfeas_pool_configure`, `ft8_subfeas_pool_get_stats`, `ft8_subfeas_pool_shutdown` (SUB-FEAS, shim 20260056). The merged shim must export **all** of them.
2. **FR numbers: both sides used FR-074..077.** `decoding_improvement`: decoder-param-readout (FR-074 native parameter table, FR-075 suppression runtime setter, FR-076 `GET /api/v1/decoder/params`, FR-077 the decoder-parameter page). `main`: FR-074 config overlay, FR-075 audio-archive control, FR-076 change-log line, FR-077 residual-pass thread count (highest FR on `main` is FR-077). The `decoding_improvement` set must move to **FR-078..FR-081**. (This is the same class of collision the 2026-09-25 sync hit; see `dev-tasks/2026-09-25-fr-number-renumber-decoder-param-readout.md`.)

Files on `decoding_improvement` that cite its FR-074..077 (8, from `git grep`): `REQUIREMENTS.md`, `openspec/changes/decoder-param-readout/proposal.md` and `tasks.md`, `tests/OpenWSFZ.Ft8.Tests/DecoderParamReadoutTests.cs`, `tests/OpenWSFZ.Web.Tests/DecoderParamsEndpointTests.cs`, `DecoderParamsPageTests.cs`, `web/js/decoderParams.test.js`, and the 2026-09-25 handoff itself (leave that one as the historical record).

## 2. Branch

Cut **`sync/di-with-main-3`** from **`origin/decoding_improvement`** (`git fetch` first), then `git merge origin/main`. Never commit to `main` or `decoding_improvement` directly. Check `git branch --show-current` before committing; stage by path. Local only; QA pushes.

## 3. Actions

1. **Native shim and interface (the union).** In `ft8_shim.h`, `Ft8LibInterop.cs`, `Ft8NativeInteropAdapter.cs`, `IFt8NativeInterop.cs`: keep **both** sets of exports and members. Do not drop either side's functions. Pass-0/pass-1 behaviour with the SUB-FEAS flag OFF and the suppression setter at its defaults must stay exactly as each side had it.
2. **One new shim number: `FT8_SHIM_VERSION` = 20260057** (above both 20260054 and 20260056), set **everywhere it lives**: `ft8_shim.h`, `Ft8LibInterop.cs` (`ExpectedShimVersion`), `win-x64/libft8.version.txt`, `BUILD.md`, `rebuild_shim.bat` header text, `openspec/specs/ft8lib-interop/spec.md`, and any ABI-sentinel test constant. A merged DLL that reports a shim version either side has already used would be ambiguous (the number identifies nothing without the DLL SHA, but never reuse it).
3. **Rebuild the native binaries from the merged source.** Windows: `native/ft8_lib_build/rebuild_shim.bat` (see `BUILD.md`); record the new `libft8.dll` **SHA-256** in `libft8.version.txt`. Linux: `native/ft8_lib_build/build_linux.sh` in WSL Debian, commit the `.so`. macOS: CI rebuilds the dylib from source; leave the committed `.dylib` to the CI "Commit rebuilt native binaries" step and say so. Run `python tools/check_native_version.py <binary> 20260057` for each binary you can build and quote the output. **Never hand-resolve a binary conflict by taking one side.**
4. **FR renumber on the `decoding_improvement` side: FR-074..077 become FR-078..081**, in the 7 non-historical files above (titles unchanged), plus the `REQUIREMENTS.md` change-log: add one new row for the sync and keep both existing rows, `main`'s 1.50 (config-save) and 1.51 (sub-feas-speed-redesign) intact; `decoding_improvement`'s own 1.50 row was dated 2026-09-20 and also numbered 1.50, so renumber that row too (1.52, dated honestly). Test `DisplayName` prefixes `FR-074:` to `FR-077:` in the decoder-param tests become `FR-078:` to `FR-081:` (Gate G3 matches the prefix).
5. **VERSION: take `main`'s 0.53** for this sync (do not invent a number); `README.md` and `REQUIREMENTS.md` cite v0.53. A later `decoding_improvement`-to-`main` PR decides its own bump.
6. **Docs and specs:** merge `openspec/specs/ft8lib-interop/spec.md` as the union of both sides' requirements (decoder parameter table and SUB-FEAS pool exports), no requirement dropped.
7. **Tests.** Fix only what the merge breaks. The win-x64 binary-pin tests (`AwgnFpReplayTests`, `FpParityP3Tests`, `Row0rCarryForwardTests`, `CoherentLlrAtTests` assert DLL identities) will see a new DLL: **do not edit a pin to make a test pass without telling QA**; report which pin tests fail and why, QA decides.
8. **Do not weaken or delete any test.** `git diff --stat origin/decoding_improvement -- src native` will be large (the merge); list the files you resolved by hand.

## 4. Acceptance criteria (what QA checks)

1. Merge commit on `sync/di-with-main-3` with **no conflict markers anywhere** (`git grep -n '^<<<<<<<\|^>>>>>>>'` empty) and every one of the 12 files resolved as above, each described in your report.
2. Both export sets present: `git grep -c` of each of the 13 export names in `ft8_shim.h`, `Ft8LibInterop.cs`, and the adapter (QA mechanically diffs the lists).
3. `FT8_SHIM_VERSION` 20260057 in every file listed in action 2; the `check_native_version.py` output for each binary you rebuilt; the new `libft8.dll` SHA-256.
4. Unfiltered `dotnet test OpenWSFZ.slnx -c Release` on **Windows** and on **WSL Debian**: pass counts and the exact commands (HK-022), plus `python tools/check_test_delay_sync.py` and `openspec validate --all --strict`.
5. `FR-078..081` cited consistently; `python tools/check_version_docs.py` OK; Gate G3 traceability: every FR has a test `DisplayName` prefix (run the checker, quote it).
6. **QA's own acceptance after your report** (not yours): the flag-OFF identity of the merged DLL against the current `decoding_improvement` DLL on the 161 E1 cycles (QA has the harness), a config-POST overlay check on the merged daemon, and the arm label. QA also pushes the branch and runs CI for the macOS dylib.

## 5. References

- Dry run: 2026-10-01, `origin/decoding_improvement` @`51e40b55` merged with `origin/main` @`9bade2bc`.
- `src/OpenWSFZ.Ft8/Native/BUILD.md`, `native/ft8_lib_build/rebuild_shim.bat`, `tools/check_native_version.py`.
- Precedent: the 2026-09-25 sync (`dev-tasks/2026-09-25-fr-number-renumber-decoder-param-readout.md`, merge `51e40b55`).
- Standing rules: HK-011 (src needs a Developer session), HK-022 (quote the unfiltered line), HK-029, HK-032 (nudge worktrees after a merge), the `FT8_SHIM_VERSION identifies nothing, pin the DLL SHA-256` rule, `closed-arms-prohibitions.md` (nothing here reopens a closed arm).
