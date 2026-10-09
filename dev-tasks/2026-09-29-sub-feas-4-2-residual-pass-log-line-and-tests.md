# SUB-FEAS §4.2: a distinct log line for the residual pass, plus tests 6.3 / 6.5 / 6.6

**Date:** 2026-09-29
**Prepared by:** QA (HK-015: Architect → QA → Developer)
**Audience:** Developer (to execute); Captain (merge sign-off, HK-010; push go-ahead, HK-033)
**Status:** **Go given.** The Captain confirmed the go to QA directly on 2026-09-29 (HK-011), after the Architect relayed it. Scope below is what he approved.
**Branch:** `feat/sub-feas-native-subtraction` (continue on it; do not branch off `main`). Base commit for this task: `0d6b1937`.
**OpenSpec change:** `openspec/changes/sub-feas-native-subtraction/` (tasks §4.2, §6.3, §6.5, §6.6).

---

## 0. Why this exists

The 2026-09-29 paired R&R S1–S8 sweep (flag OFF / ON) and the flag-OFF control could not say **which decodes came from the residual pass**, because the daemon logs nothing distinct for it. The §8.1 real-band runtime replay also needs per-cycle residual-pass timing and a deadline-abandon count taken from the daemon's own log, not inferred. §4.2 has been open since the change was written.

**The build must stay C#-only.** `libft8.dll` is currently `5a6a4dc04a2cf6fbd987c12ce7635a968f4c9b69f73cacebe422af62827e38c5` (shim `20260055`). The flag-OFF control (three DLLs byte-identical on 182 cycles, merge gate met on the native path) covers **that DLL only**. If the DLL changes, that result no longer covers the new one and the control must be re-run. So **no change under `native/` and none to `libft8.dll`**, and no shim bump.

## 1. Actions

1. **The §4.2 log line.** In `src/OpenWSFZ.Ft8/Subfeas/SubtractionPass.cs` (and whatever `Ft8Decoder.cs` needs to pass through), emit **exactly one** structured Information-level line **per residual-pass invocation**, with a **message template distinct from** the existing `"Iterative subtraction: pass N of 2, K new decodes"` line (leave that one exactly as it is). Suggested template, names fixed so log greps are stable:

   `Sub-feas residual pass: residualDecodes={ResidualDecodes} elapsedMs={ElapsedMs} deadlineAbandoned={DeadlineAbandoned} containedException={ContainedException}`

   Fields, all **aggregates only**:
   - `ResidualDecodes`: count of genuinely new decodes the pass returned (0 if abandoned or contained).
   - `ElapsedMs`: wall-clock of the residual pass itself, measured from the start of `RunAsync`'s work to its return.
   - `DeadlineAbandoned`: `true` iff the pass gave up because the cooperative deadline expired (any of the existing `DeadlineAbandon(...)` exits), else `false`.
   - `ContainedException`: `true` iff `RunCore`'s catch-all swallowed an exception and returned pass-0 only, else `false`.
   - **Permitted addition (aggregate integer):** `FittedSignals`, the number of re-encodable pass-0 signals actually fitted, so runtime can be plotted against it. No other fields without asking QA.
2. **When it is emitted (exact).** Only when the flag is **ON** and the residual pass **runs**, i.e. once per `SubtractionPass.RunAsync` call that is not cancelled by the caller. That includes the early exit with no re-encodable signals (`ResidualDecodes=0`, `FittedSignals=0`). **Not** emitted when the flag is OFF (the OFF path must not touch this code at all), and **not** emitted when the caller's cancellation propagates.
3. **Do not change behaviour.** The pass must return exactly what it returns today. The line is observability only. Achieve the two boolean flags without altering control flow (a small result record or out-values internal to `SubtractionPass` is fine; keep it `internal`).
4. 🔒 **No message text, no callsigns, no exception message text in the new line.** Aggregates only (HK-037 / NFR-021). The existing `LogWarning(ex, ...)` calls are unchanged.
5. **Test 6.3 `AllFitsAgainstOriginalBuffer_NotSequential`.** A fake `IFt8NativeInterop` whose `SubfeasFitSignal` records the identity (`ReferenceEquals`) and a content hash of the `xaRe`/`xaIm` arrays it receives, across at least 3 concurrent calls with `maxDegreeOfParallelism > 1`. Assert every call saw **the same arrays, unmodified** by any other fit's result. It must fail if a fit were given a residual instead of the original analytic signal (prove that by temporarily breaking it once and noting it in the PR).
6. **Test 6.5 `MaxPassesUnaffectedBySubtractionFlag`.** Assert `MaxDecodePasses` is `2` with the flag OFF and with it ON, on a real `Ft8Decoder`, and (real DLL) that `ft8_get_max_passes()` returns `2`.
7. **Test 6.6 `AllocationFailure_FallsBackGracefully_NoCrash`: managed scope only.** A native malloc-failure hook would change `libft8.dll` and is **out of scope** (see §0). Cover the managed half: a fake interop whose `SubfeasFitSignal` throws the `InvalidOperationException` that a native `rc == -1` produces, and whose `SubfeasComputeAnalytic` does the same, must yield pass-0-only results, the new log line with `ContainedException=true`, and no exception out of `DecodeAsync`. If tests from the R1–R3 fix (`91444300`) already assert this, **reuse and name them** rather than duplicating; add only what the log-line assertion needs. **Record in `tasks.md`'s 6.6 line (QA edits it) that the native-side injection remains unmet by design.**
8. **Tests for the log line itself** (`SubtractionPassTests` / `SubtractionFlagTests`), with a capturing logger:
   - flag ON, residual pass finds a new decode: exactly **one** matching line; fields correct.
   - flag OFF: **zero** lines with this template.
   - deadline expired: `DeadlineAbandoned=true`, `ResidualDecodes=0`.
   - contained exception: `ContainedException=true`, `ResidualDecodes=0`.
   - no re-encodable signals: one line, `FittedSignals=0`.
   - caller cancellation: **no** line.
   - **No-text canary:** feed pass-0 messages containing distinctive marker strings and assert the rendered line contains **none** of them and no `<`, `CQ ` or `Q1` fragments beyond the template's own fixed text.
9. **Nothing else.** No web-UI checkbox (5.1), no Linux/macOS build work (6.8), no G6 answer keys (6.7, deferred by the Captain until after §8), no changes to `tasks.md` (QA's file: QA updates it after review).

## 2. Acceptance criteria (what QA will check)

- `git diff --stat 0d6b1937 -- native/ src/OpenWSFZ.Ft8/Native/` is **empty**; `libft8.dll` SHA-256 is **still** `5a6a4dc04a2cf6fbd987c12ce7635a968f4c9b69f73cacebe422af62827e38c5` (QA verifies by hash, HK-022, not by assumption). `ExpectedShimVersion` unchanged at `20260055`. If any of these is not true, **stop and say so**: the flag-OFF control result no longer covers the build.
- **Default OFF unchanged.** Flag-OFF path has no new executed code; `_subtractionEnabled && native.Length > 0` guard untouched. Existing flag-OFF tests (6.1) pass unchanged.
- The log line matches Action 1's template and names, once per invocation, per Action 2's exact emission rule; no text/callsigns in it (canary test present and meaningful).
- The pass's return values are **identical** to before for every existing test (no behavioural diff).
- `OpenWSFZ.Ft8.Tests`: all existing tests still pass (353 at `0d6b1937`), plus the new ones; QA re-runs the whole suite itself, unfiltered.
- Version / shim: **none expected** (C#-only, DLL untouched). If a repo gate demands a version bump for a `src/` change, tell QA which gate and why; do not guess.

## 3. After the build

QA reviews the diff and re-verifies the DLL hash. **Then** the §8.1 real-band runtime replay (Architect's spec `2026-09-29-2010-architect-sub-feas-8-1-real-band-runtime-replay-spec.md` and its Amendment 1) runs on **that** build, with `selection.json` frozen and hashed before any timing. Merge and push remain the Captain's.

## 4. References

- `openspec/changes/sub-feas-native-subtraction/` (`tasks.md` §4.2, §6.3, §6.5, §6.6; `design.md` Decision 4).
- QA review reports: `qa/rr-study/2026-09-29-1524-qa-to-architect-sub-feas-native-build-code-review.md` (R1–R3), `qa/rr-study/2026-09-29-1933-qa-to-architect-sub-feas-native-build-review-and-rr-s1s8-off-vs-on.md`.
- Flag-OFF control: `qa/rr-study/2026-09-29-1956-qa-flagoff-control-preregistration.md`, `qa/rr-study/2026-09-29-2000-qa-to-architect-flagoff-control-results.md`.
- Architect rulings: `2026-09-29-1948-architect-sub-feas-native-build-rulings.md`, `2026-09-29-2030-architect-flagoff-control-ruling.md`.
- Standing rules: HK-011 (src changes need a separate Developer session), HK-037 / NFR-021 (aggregates only), HK-022 (pin by hash), HK-006 (QA runs the mechanical gates, not the Developer).
