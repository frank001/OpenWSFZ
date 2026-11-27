# QA code review (HK-039): the lean members of IFt8NativeInterop lose their default bodies

**Reviewed commit:** `7031bb380fd410de77388b42139bc4681a63ebf4` (`feat/interface-no-defaults`, one commit on `origin/main` `ea3350e2`, not pushed)
**Reviewed-commit:** 7031bb380fd410de77388b42139bc4681a63ebf4
**Verdict:** APPROVED, with 2 minor notes (none blocks)
**Reviewer:** QA, 2026-11-27. Read: the whole diff (the interface, `NonLeanInteropBase`, the guard test, the three lean-modelling fakes and the 26 one-line fake declarations), against `dev-tasks/2026-11-27-lean-interface-no-default-bodies.md`.

## Tests and checks QA ran (clean scratch worktree: `e9c8f02d` plus this commit, Release, whole projects, no `--filter`, HK-022)

- Config **237**, Web **464**, Daemon **963**; `DOTNET_PROCESSOR_COUNT=4` Ft8 **939** (main 929 minus this commit's 1 = 928, plus the 10 of `e9c8f02d`, plus this commit's guard test: the Developer reports 929 for this commit alone); JavaScript **131 / 131**.
- `Replay81` (QA's harness) builds with `HasLean`, `HasProbe`, `HasXcRound`, `HasInternals`: **0 errors**, so `StageProbeInterop` already forwards all four members (the Developer's claim). No other implementer exists in `src/`; the production adapter already implemented all four.
- No native, shim or `libft8.dll` change; `check_version_bump.py origin/main`: no bump required.

## What was checked and found sound

- **Exactly the four lean members lose their default** (`DecodeLeanCycle` both overloads, `DecodeLeanXcRound`, `LeanShutdown`); the three non-lean no-op defaults are left as the task allowed. The XML comments say why.
- **A fake can no longer fall silently onto a default.** The 26 fakes that do not model the lean engine derive from the test-only `NonLeanInteropBase`, whose decode members throw `NotSupportedException` and whose `LeanShutdown` is a no-op; the five that model it (`ScriptedLean` and `RealLean` in the batches tests, `LeanFake` and `NoLeanFake` in the wiring tests, `ScriptedLean` in the XC managed tests) implement the members themselves. A new fake that forgets one fails to compile; one that changes a signature fails to compile. No assertion was edited.
- **`LeanFake` keeps the old two-argument-with-callback behaviour** by moving the former interface default into itself (the batch-1 hand-off), so the tests that rely on it still deliver round 0.
- **The guard test** reflects over the interface and asserts the four lean members (by name, two of them the overloads) are abstract, so a default added later fails a test, not a replay.

## Minor notes (none blocks)

1. The XML comment of the `onRound0` overload still says "The default calls the plain overload ... (a fake that does not model the hand-off still delivers batch 1)"; there is no default any more (the next sentence, "No default body.", is right). A stale half-sentence only.
2. `NonLeanInteropBase` implements the members publicly and the derived fakes list the interface again; the pattern is documented in its comment. A fake that derives from it and then runs the lean path fails loudly with `NotSupportedException` (the intent), where it used to be silent for `DecodeLeanXcRound`; a managed caller that swallows that exception would hide it, as before. The guard test covers the interface, not the base class.

## Next (QA)

Merge with `feat/fine-grid` into `qa/sprint-known-erasure` (different files; no conflict), and fix the harness's own stale comment about the interface default (QA's `Replay81.csproj` / `StageProbe.cs`) after the merge.
