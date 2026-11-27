# Developer task: remove the default bodies of the lean interface methods (a signature change must fail to compile)

**Date:** 2026-11-27
**Prepared by:** QA, from the Architect's structural proposal
**Audience:** Developer (to execute)
**Authorised by:** the Captain, 2026-11-27 ("implement it"), after KNOWN-ERASURE was dropped.
**Status:** Proposed. HK-011: `src/` changes for a separate Developer session. Hand back the commit; QA reviews it (HK-039). **Do not push, open a PR or merge**; QA pushes (once per sprint).
**Branch:** `feat/interface-no-defaults` from `main` (`a1e1c84c` or later; `git fetch origin`). KNOWN-ERASURE (`104bc426`) is **dropped**: do not base on `feat/known-erasure`.
**Test requirement (the Captain's rule, 2026-11-24):** unit tests and QA's review. No replay. Read the per-assembly "Passed: N" lines (HK-022). **Do NOT run ASan, UBSan or the fuzz locally** (CI's `native-asan` runs them on the PR).

---

## 0. Why

`IFt8NativeInterop` gives the lean methods **default bodies**. A class that implements the interface with a **different parameter list** does not implement the method: the call lands on the default and nothing says so. Twice on 2026-11-27 this silently disabled the XC round in QA's replay harness (`DecodeLeanXcRound` default = an empty outcome, so batch 4 never ran and the replay was void). With no default the same mistake is a compile error.

## 1. The change

In `src/OpenWSFZ.Ft8/Interop/IFt8NativeInterop.cs` remove the default bodies of the **lean engine** members:

| Member | Default today | After |
|---|---|---|
| `DecodeLeanCycle(pcm, request)` | throws `NotSupportedException` | abstract |
| `DecodeLeanCycle(pcm, request, onRound0)` | calls the plain overload, then fakes the hand-off | abstract |
| `DecodeLeanXcRound(pcm, request, residual, detections)` | empty outcome (the silent one) | abstract |
| `LeanShutdown()` | no-op | abstract |

Judgement call, say what you chose: the non-lean no-op defaults (`SubfeasPoolConfigure`, `SubfeasPoolShutdown`, the M2 switch) are **out of scope** unless removing them is free; the lean four are required.

Then make every implementer say what it means:

1. **Production:** `Ft8NativeInteropAdapter` already forwards; confirm it implements all four explicitly.
2. **Test fakes (about 30 classes in `tests/OpenWSFZ.Ft8.Tests`):** each must implement the four members. A fake that does not model the lean engine implements them **explicitly as "not modelled"** (throw `NotSupportedException` for the decode methods, no-op for `LeanShutdown`). **Do not** recreate a silent empty outcome for `DecodeLeanXcRound` in a fake that is used in a test that runs the lean path. To avoid 30 copies you may add ONE shared helper in the test project (e.g. an abstract base class `NonLeanInteropBase`) that the non-lean fakes derive from; the helper is test-only and lives under `tests/`, never under `src/`.
3. **The QA harness:** `qa/rr-study/sub-feas/replay81/StageProbe.cs` (`StageProbeInterop`) and any other class under `qa/` that implements the interface must still compile. QA fixes the harness after your hand-back (it is QA's code); list in your report every `qa/` file that no longer compiles. Do not edit `qa/`.

## 2. Tests

1. **(a) Compile-time guard:** the change itself. Add a small test that reflects over `IFt8NativeInterop` and asserts that **no lean member (`*Lean*`) has a default body** (`MethodInfo.IsAbstract` true for each), so a default added back later fails a test, not a replay. Quote the member names it checks.
2. **(b) Nothing else moved:** every existing test passes with **no change to its assertions**; only the fakes' declarations change. If a test needs an assertion edit, stop and report which and why.
3. **(c) No behavioural change:** the decoder's output is untouched; `libft8.dll` is **not** rebuilt (no `native/` diff, no shim bump). Say so, and run `tools/check_version_bump.py` and follow it for `VERSION` (a `src/` change).
4. **Run each project separately** and quote each "Passed: N": Config, Web, Daemon, Ft8 (also at `DOTNET_PROCESSOR_COUNT=4`), and the JS runner.

## 3. Out of scope

Any behaviour, the native library, the shim, the harness (`qa/`), a flag, `REQUIREMENTS.md` unless a sentence now says something false (then amend it in the same commit and say so).

## 4. Report back

The commit SHA; the per-project "Passed: N" lines (Ft8 also at 4 processors) and the JS result; which members lost their default; how the fakes were fixed (helper class or per-class) and the count of classes touched; the list of `qa/` files that no longer compile; anything that differs from the neighbouring tests' pattern.
