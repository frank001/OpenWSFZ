# Replay-only override of the subtraction cycle budget (`SubtractionCycleBudget`, 13 s) for the REFERENCE-SET study on `sol`

**Date:** 2026-10-11
**Prepared by:** QA
**Audience:** Developer (to execute); Captain (sign-off required before merge, HK-010)
**Authorised by:** the Captain, in QA's window, 2026-10-11: "option 2 is confirmed" (the REFERENCE-SET replay legs run on `sol` with the budget lifted), recorded as spec 2m (amendment 8, `arch/reference-set`). OpenSpec change: `openspec/changes/subtraction-budget-replay-override/` (proposal, design, tasks, spec delta; `openspec validate` clean).
**Status:** Proposed. Per HK-011 this is a `src/` change for a separate Developer session. The Developer does not push or merge, and does not run `pre_merge_check.py` on its own initiative (QA verifies, the Captain signs off the merge).
**Branch:** cut a new branch from the current `main` (`76aa48cd`, v0.57, shim 20260060). **Do not touch `native/` or the shipped binaries.**

---

## 0. Why (one paragraph)

QA's gate RS-V2P on `sol` (AMD FX-8350, 8 cores) abandoned the residual pass in **40 of 40** cycles of one anchor block, each cycle ending at 11.53 to 11.56 s: the cancel point of `SubtractionCycleBudget` = 13 s (`Ft8Decoder.cs:108`, `private static readonly`). The same block on the station PC abandoned 0 of 40 at about 5.2 s per cycle. On the station the budget does not bind, so a replay with the budget lifted gives the station decoder's output; the override lets the study measure on `sol`. **It is for replays only.** It is not a feature, not a setting and not user-facing.

## 1. Precise scope

1. **The override.** `SubtractionCycleBudget` becomes an instance value resolved once in the `Ft8Decoder` constructor.
   - QA proposes the environment variable `OPENWSFZ_SUBTRACTION_BUDGET` (your choice of name; a config key is NOT wanted: it would be written by every Settings save and need a migration/overlay decision, HK-035).
   - **Unset ⇒ exactly `TimeSpan.FromSeconds(13)`, behaviour byte-identical to today.**
   - **Valid:** a number of seconds ≥ 13 (invariant culture, `13` and `13.0` both fine), or the word `unlimited` (case-insensitive).
   - **Refused (throw at construction, naming the variable and the rule), never clamped:** below 13, zero, negative, non-numeric (`abc`, `13s`), empty, `NaN`, `Infinity`.
2. **Both call sites.** The value is used at the one-stage and the two-stage `SubtractionPass.RunAsync` calls (`Ft8Decoder.cs` ~550 and ~760: `SubtractionCycleBudget - sw.Elapsed`). `unlimited` passes `deadline: null`, which `RunAsync` already supports. **Read `SubtractionPass.RunCore` for the null path and say in the PR that it adds no unbounded wait beyond the native fits themselves** (the `Expired()` check, the `fitBudget` null case, the reserve check at ~302).
3. **Logged per cycle.** The residual-pass summary line (`SubtractionPass.RunAsync`, the `Sub-feas residual pass: ...` line) gains ONE trailing field `budgetMs={BudgetMs}`: the effective budget in milliseconds as the caller computed it for the cycle's start, or the word `unlimited`. **Existing fields keep name, order and meaning** (`residualDecodes`, `elapsedMs`, `deadlineAbandoned`, `containedException`, `fittedSignals`): the replay harness reads `elapsedMs` (each cycle's residual-pass duration) and `deadlineAbandoned` (the abandoned/completed flag) from this line. Aggregates only (HK-037).
4. **One warning at construction** when an override is active: the value and "replay only". The harness copies it into its run-conditions log.
5. **Nothing in `native/`**, no shim version change, no change to any decode parameter, nothing different when the override is unset.
6. **Doc comment** on the new member: "REPLAY ONLY ... not a user setting ... exists so a replay host slower than the station can measure the station decoder's output without the cycle budget cancelling the residual pass" and the unset/valid/refused rules.

## 2. Tests (test-first; HK-025(k): each must be able to fail)

1. **Unset is the identity:** the budget handed to the residual pass at the one-stage and at the two-stage call site equals 13 s minus the pass-0 elapsed time, using the seam `SubtractionDeadlineTests` uses; and a fixed synthetic cycle decodes to the same rows as the base commit.
2. **Valid values** `13`, `13.0`, `30`, `unlimited`, `UNLIMITED` resolve to 13 s, 13 s, 30 s, no deadline, no deadline.
3. **Refused values** (the list in §1.1) each throw at construction with a message naming the variable and the rule.
4. **Log line:** `budgetMs=13000` by default, `budgetMs=30000` with `30`, `budgetMs=unlimited` with `unlimited`; all existing fields still parse (extend `SubtractionLogLineTests`).
5. **Construction warning** once when active, never when unset.

## 3. What QA validates afterwards (the Developer needs none of this)

1. **Byte identity on a real block (PC):** the replay harness on the base build and on the new build with the override unset, same block, same settings: identical per-cycle decodes and identical residual-pass counts.
2. **Smoke on `sol`:** one anchor block with `unlimited` (and one with `30`): the log line carries `budgetMs`, abandonments 0, the residual-pass time per cycle recorded.
3. **Then the gate RS-V2P** (bar unchanged: ≥ 99 % of the live Windows non-hashed rows reproduced, ≤ 1 % extra, 0 abandonments).

## 4. Notes for the PR

- This is a `src/` change in `OpenWSFZ.Ft8` only. The harness (`qa/rr-study/refset/harness`) is QA's and needs no change from you.
- **User-facing: no.** No Settings field, no `config.json` key, no README text.
- If anything in §1 collides with what you find in the code, say so in the PR rather than choosing silently (the QA sentence "unset is byte-identical" is the one thing that must hold).
