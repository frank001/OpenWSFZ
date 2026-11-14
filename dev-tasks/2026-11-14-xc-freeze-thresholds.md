# Developer task: XC-BUILD, put the measured thresholds into the product (T_E and T_P), one small commit on PR #285

**Date:** 2026-11-14
**Prepared by:** QA
**Audience:** Developer (to execute)
**Authorised by:** the spec itself: R6 (T_E "a shipped constant ... placeholder +infinity in this build: QA's TRAIN arm measures the real value, which goes in before any merge") and Amendment 6 §A6.3 (T_P frozen on TRAIN in TR2, `te.json` v2 committed before any OFF or ON arm); the Architect's acceptance ruling (ACCEPT-2N). The Captain asked for the push and the PR; **PR #285 is open** (`feat/xc-template-prior`, tip `3add5442`).
**Status:** Proposed. HK-011: a `src/` change for a separate Developer session. 🛑 **No push, no PR, no merge, no `pre_merge_check.py` on your own initiative**; hand back the commit and QA reviews it.
**Branch:** `feat/xc-template-prior`, on top of `3add5442`. (Your worktree is on `ci/force-native-rebuild`; switch it, or say where you worked.) **Scope fence:** `src/OpenWSFZ.Ft8/Ft8Decoder.cs` (the two constants and their XML comments), the tests that assert the placeholders, and the OpenSpec wording. **No other src change; no `native/`; `git diff --stat 3add5442 HEAD -- native src/OpenWSFZ.Daemon src/OpenWSFZ.Abstractions` must be EMPTY.** The DLL SHA-256 `bbde6eb66af4cd429ffc46f67291ba718c1ae36ae39665faac24629bcb6e6528` stays.

---

## 0. Why

At `3add5442` the shipped defaults are placeholders: `Ft8Decoder.CrossCyclePriorThresholdDefault = double.PositiveInfinity` (`Ft8Decoder.cs:322`) and `CrossCyclePriorParityThresholdDefault = 0.0` (`:357`). QA's acceptance arms set the real values through the replay setters, so **in the product, with `decoder.crossCyclePrior` ON, the stage detects nothing** (S_E\* can never reach +infinity). The measured values were frozen on the TRAIN night before any OFF or ON arm (QA's TR2, committed in `te_v2`) and both acceptance nights ran on them.

## 1. What to change

| Id | What |
|---|---|
| **T1 T_E** | `CrossCyclePriorThresholdDefault = 3.076041980658299;` |
| **T2 T_P** | `CrossCyclePriorParityThresholdDefault = 2.2220253019230114;` |
| **T3 Comments** | Replace the "placeholder" wording in the XML comments (and the matching `design.md` and delta-spec sentences) with the source: "frozen on the TRAIN night by QA's TR2 (T_E from the shadow null at FA\* = 0.021 / K with K = 36, T_P the 10th percentile of corroborated detections' S_P), committed before any acceptance arm; `qa/xc-build/results/xc_te_v2_full_2026-11-14.json`". Do not round the numbers. |
| **T4 Tests** | Update every test that asserts the placeholders as defaults (the defaults test for T_P = 0.0, any that rely on T_E = +infinity as the default). **Add one test that pins the shipped constants to the frozen literals** (3.076041980658299 and 2.2220253019230114) with a comment naming the source file, so a later edit cannot move them unnoticed. **Keep the tests that set +infinity or 0.0 through the replay setters** (they are how TR-style arms and the OFF-path tests work); they must still pass. |

## 2. Things to check and say

1. **The default-OFF path is unchanged.** With `crossCyclePrior` false nothing new runs (R11); say which test pins that, and that it still passes with the new constants.
2. **No test relied on the default being +infinity to stay quiet** (for example a test that turns the stage ON without setting T_E and expects no publishes). List any you changed and why.
3. The read-back (`xcte`, `xctp`) of the defaults now shows the frozen values.

## 3. Not in this task

No change to R14, R15, the store, the log line, the sink, the QSO services or PSK Reporter. **No default ON.** No re-measurement: the values are frozen; if you believe a value is wrong, stop and tell QA.

## 4. What QA will check

The scope fence; the two literals against the frozen file (to the last digit); the full unfiltered suite on a clean tree; a mutation pass on the two constants and the pin test; and a short replay proving that the ON path with the **defaults** (no setter calls) reproduces the acceptance arms' behaviour on the first cycles of the TEST night; then `pre_merge_check.py` on the final commit, before the Developer's commit is pushed to the PR.

## 5. Gates you run before handing back

The full unfiltered `dotnet test OpenWSFZ.slnx -c Release` (exact command line and per-project counts, HK-022), `openspec validate --all --strict`, `python tools/check_version_bump.py origin/main` after committing, the traceability gate (G3) clean. 🛑 **Do not run `pre_merge_check.py`.**

## 6. Report back (HK-001 sections), then STOP

The commit hash; the diff stat; the §2 answers; the pin test and what it asserts; the command lines and counts of the full suite; deviations and why. **Then stop**: QA reviews and the commit goes onto PR #285.
