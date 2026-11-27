# Developer task: ship THIN + FINE as the lean decoder's default (thin 1, time_osr 4, freq_osr 4)

**Date:** 2026-11-27
**Prepared by:** QA
**Audience:** Developer (to execute)
**Authorised by:** the Captain, 2026-11-27 ("go with recommendations. push"), after QA's FINE-GRID replay (`qa/rr-study/results/2026-11-26-lc-base/fine-grid-result.md`): arm F (thin 1, 4 x 4) gains +2.08 / +1.39 / +0.60 pp over the shipped build on S40 / H40 / H20, CPU about +10 %, no abandoned cycles; thin alone (arm T) is mixed (+1.00 / +0.06 / -0.44) and is NOT to ship on its own.
**Status:** Proposed. HK-011: `src/` changes for a separate Developer session. Hand back the commit; QA reviews it (HK-039). **Do not push, open a PR or merge**; QA pushes.
**Branch:** `feat/fine-grid-default` from **`qa/sprint-known-erasure`** (it holds `feat/fine-grid` and `feat/interface-no-defaults`, both merged; `git fetch` is not needed, the branch is local to the repository). The sprint branch is what QA pushes, so this must sit on it.
**Test requirement (the Captain's rule, 2026-11-24):** unit tests and QA's review. No replay. **Do NOT run ASan, UBSan or the fuzz locally** (CI's `native-asan`). Run each project separately and quote each "Passed: N".

## The change

The lean engine's FINE-GRID parameters (shim 20260083: `thin`, `time_osr`, `freq_osr`) are off by default today. Make the **lean decoder run with thin 1, time_osr 4, freq_osr 4 by default**, in every place the lean engine is driven from managed code in production (the daemon's lean cycle and the XC round, through `Ft8Decoder`). The classic decoder stays bit-identical, and the native defaults of `ftz_params_t` (0 = today's 2 x 2, thin off) **stay as they are** (QA's harness and the existing native tests rely on them).

1. **Where:** the managed request that `Ft8Decoder` builds for a lean cycle and for the XC round (`DecodeLeanAsync` and the XC request, `Ft8Decoder.cs`; they build `LeanCycleParams`). Prefer ONE named constant per value (no magic numbers), documented with the replay numbers above. `LeanCycleParams`'s own record defaults (`Thin: false`, `TimeOsr: 0`, `FreqOsr: 0`) stay, so a test that builds a `LeanCycleParams` itself is unchanged.
2. **A switch to turn it off** without a rebuild is NOT required (the Captain did not ask for one); if the existing lean settings pattern (e.g. the effort or thread setters) makes a decoder-level setter natural and tiny, add it and say so, otherwise do not.
3. **Tests:** (a) a test that a lean cycle and the XC round issued by `Ft8Decoder` carry thin 1, time_osr 4, freq_osr 4 (a recording fake of the interop, as the existing wiring tests do); (b) **every existing test passes unchanged.** If a lean golden or wiring test changes because the real native lean path now runs on the 4 x 4 grid, **do not edit it**: stop and report which one and by how much (QA decides). (c) classic is untouched: say how you checked it.
4. **Documents:** amend `REQUIREMENTS.md` FR-108 where it says the FINE-GRID parameters are off by default (the lean decoder now runs thin 1 and 4 x 4 by default; classic unchanged; the parameters remain runtime parameters) and add a changelog row; keep the OpenSpec change `lean-decoder` in step (strict). `tools/check_version_bump.py` and follow it. **No native change, no shim bump, `libft8.dll` is not rebuilt.**
5. **Out of scope:** the native library, the harness, any other lean parameter, the classic decoder, the Settings page.

## Report back

The commit SHA; the per-project "Passed: N" lines (Ft8 also at `DOTNET_PROCESSOR_COUNT=4`) and the JS result; where the constants live; whether any existing test changed behaviour (and which); how classic was checked; whether you added a setter.
