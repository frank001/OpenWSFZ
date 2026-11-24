# Developer task: XC-BUILD, batch-6 (template) rows never start an exchange with a new station: the QSO answerer and caller

**Date:** 2026-11-14
**Prepared by:** QA
**Audience:** Developer (to execute); Captain (sign-off before merge, HK-010; the PR is on his go, flag default OFF)
**Authorised by:** the Architect's ruling, remedy acceptance ruling §6 (`arch/cross-cycle-prior` `2444aa50`), under the Captain's build go of 2026-11-13 ("go, don't wait for me"). Source of the finding: QA's review `qa/rr-study/2026-11-14-1118-qa-code-review-xc-default-on-items-42f6a390-APPROVED.md` §5.
**Status:** Proposed. HK-011: a `src/` change for a separate Developer session. 🛑 **No push, no PR, no merge, no `pre_merge_check.py` on your own initiative.** QA pushes (HK-033), after QA's HK-039 review and ONE `pre_merge_check.py` on the final commit (HK-006).
**Branch:** new commits on **`feat/xc-template-prior`**, on top of your tests-only commit that follows `42f6a390` (the three observability tests). **Scope fence: `src/OpenWSFZ.Daemon` only. `git diff --stat <your tests commit> HEAD -- src/OpenWSFZ.Ft8 src/OpenWSFZ.Abstractions native` must be EMPTY** (the decoder and the Abstractions are not touched; `DecodeResult.PathTemplate` already exists). No `native/` change; DLL SHA-256 `bbde6eb66af4cd429ffc46f67291ba718c1ae36ae39665faac24629bcb6e6528` stays. 🔒 NFR-021: Q-prefix calls only in tests.

---

## 0. Why

With the template stage ON, batch 6 (`Path == DecodeResult.PathTemplate`, 3) reaches both QSO services, and **a supplementary batch counts as *heard***: `QsoAnswererService.HandleLateIdleAsync` (`:1324-1352` at `42f6a390`) calls `ExecuteTxAnswerAsync` (`:1341`) or defers the answer (`:1347`) on a CQ found in a late batch, and `QsoCallerService.HandleLateWaitAnswerAsync` (`:1070`) engages a station that answered our CQ. **A CQ or an answer that only the template stage "found" can therefore start an on-air transmission.** A repeated CQ is harmless; a stale template of a station that has stopped calling CQ is not (XC-SUP: 6 and 7 stale publishes per 1,000 cycles after the remedy, a lower bound).

## 1. The rule (the Architect's)

**Batch-6 rows NEVER start an exchange with a new station. They MAY advance an exchange already in progress with the same partner.**

| Id | What |
|---|---|
| **Q1 Answerer, Idle** | In `HandleLateIdleAsync`, **skip every result with `r.Path == DecodeResult.PathTemplate`** when looking for a CQ to answer (immediate AND deferred). If the batch holds only template rows that would have matched, return the new outcome **`LateOutcome.IgnoredTemplate`**; if it holds a non-template CQ that matches, behaviour is unchanged. |
| **Q2 Caller, WaitAnswer** | In `HandleLateWaitAnswerAsync`, **skip every template row** when looking for a station that answered our CQ (First mode and any other branch that starts an exchange from a late row); return `IgnoredTemplate` when only template rows matched. |
| **Q3 Unchanged** | **Answerer WaitReport and WaitRr73, caller WaitRr73: unchanged.** There the template is the partner's own repeated message, and our response (repeat our last TX) is what we do with no decode anyway; the R14 veto removes the stale case. **Panel, `ALL.TXT`, GridTracker, external reporting: unchanged** (they keep batch 6); PSK Reporter already excludes it. |
| **Q4 New outcome** | **Add `IgnoredTemplate` to `LateOutcome`** (`src/OpenWSFZ.Daemon/LateBatch.cs:7`), with its log token in `LateBatch.Token(...)` in the same style as `ignored-stale` and `ignored-answered`, so the existing late-batch log line (`late batch {BatchNumber} {Outcome}`) shows it. It is **counted** (logged) each time a batch-6 row that would have started an exchange is skipped. |

## 2. Check every other path (and say what you found)

A batch-6 row can reach a decision in two more ways; **verify both and report**:
1. **`MergeIntoSnapshot`** (`QsoAnswererService.cs:1289`) merges every late batch, batch 6 included, into `_lastIdleDecodeBatch` while Idle. That snapshot is read by **`TryEngageExternal`** (`:391`, a GridTracker/WSJT-X-style external *Reply*, which is **operator-initiated**: the operator picked a callsign they saw; the Architect leaves this unchanged) and may be read elsewhere. **List every consumer of `_lastIdleDecodeBatch`.** If any **automatic** decision (one the operator did not choose) can start an exchange from a snapshot row, **exclude template rows from the merge for that consumer** and say so. If the only consumer is the operator-initiated external reply, leave it and say so.
2. **Any other late-batch handler** that calls `TryParseCq`, `TryParseResponder` or starts a TX from `batch.Results` (grep both services). Answerer `HandleIdleAsync` (`:883`) processes batch 1; confirm that a batch-6 row cannot reach it.

## 3. Tests (TESTING_STRATEGY §11: no fixed sleeps; each must be able to fail, QA mutates)

1. **Answerer Idle:** a **CQ present only in a batch-6 batch does not start an answer** (nothing transmitted, no deferred answer held), and the late log token is `ignored-template`.
2. **The same CQ in batch 1, or in batch 4 (or 2, 3, 5), still starts the answer** (immediate and, past `CanStartWhole`, deferred): the rule is about batch 6, not about late batches.
3. **Answerer WaitReport:** the partner's report present **only in batch 6** is handled as today (the exchange advances).
4. **Caller WaitAnswer:** a reply to our CQ present **only in batch 6 does not start the caller's exchange**, token `ignored-template`; the same reply in batch 1, 4 or 5 still does.
5. **Mixed batch:** a batch-6 batch containing a CQ row (`Path` 3) and a CQ row with `Path` 0 (different callsigns): the answer goes to the non-template one.
6. **The token and the enum** (`LateBatch.Token(LateOutcome.IgnoredTemplate)`), and that no existing token changed.
7. **Snapshot** (per §2): whatever you found, one test pins it (an automatic consumer excludes template rows, or the external-reply path still finds a batch-6 CQ the operator selected, whichever applies).

## 4. Not in this task

No change to the decoder, the template stage, T_E, T_P, the veto, the QSO queue capacity (14), the PSK exclusion, or any default. **No default ON.** Do not change what the services do with batches 2 to 5. Do not touch the operator-initiated external reply unless §2 finds an automatic consumer.

## 5. What QA will check

The scope fence (the diff outside `src/OpenWSFZ.Daemon` is empty); the full unfiltered suite on a clean tree; a mutation pass on Q1, Q2 and Q4 (the path test, the batch test, the token, the skip in each handler); HK-039 record; then ONE `pre_merge_check.py` on the final commit, and macOS/Linux CI after the Captain's go to push.

## 6. Questions to answer in your report

1. The result of §2 (every consumer of `_lastIdleDecodeBatch`, with FILE:LINE, and what you did).
2. Where the template check sits in each handler (FILE:LINE) and why there.
3. The log token chosen for `IgnoredTemplate`.
4. Any late-batch path in either service that starts a TX from a decode and that you did NOT change, and why.

## 7. Gates you run before handing back

The full unfiltered `dotnet test OpenWSFZ.slnx -c Release` (exact command line and per-project counts, HK-022), `openspec validate --all --strict` (extend the change's `design.md` and delta spec: a template row never starts an exchange), `python tools/check_version_bump.py origin/main` after committing, the traceability gate (G3) clean. 🛑 **Do not run `pre_merge_check.py`.**

## 8. Stop-and-tell conditions

Stop and report to QA, without building around it, if: a template row can start an exchange through a path §1 does not cover; the rule cannot be applied without touching `src/OpenWSFZ.Ft8` or Abstractions; an existing test pins that a batch-6 CQ starts an answer (say which).

## 9. Report back (HK-001 sections), then STOP

The commit hash(es); the §1 table answered row by row with FILE:LINE; the §6 answers; the test list with what each asserts; the command lines and counts of the full suite; the empty scope-fence diff; deviations and why. **Then stop**: QA reviews both of your commits since `42f6a390` together, runs ONE `pre_merge_check` on the final hash, and the PR waits for the Captain's go.
