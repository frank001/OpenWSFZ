# Developer task: XC-BUILD, the two items owed before any default-ON: a QSO-queue capacity for batch 6, and keeping template decodes out of PSK Reporter

**Date:** 2026-11-14
**Prepared by:** QA
**Audience:** Developer (to execute); Captain (sign-off before merge, HK-010; the PR is on his go, flag default OFF)
**Authorised by:** the Architect's acceptance ruling `qa/rr-study/2026-11-14-1036-architect-xc-remedy-acceptance-ruling.md` §3 (`arch/cross-cycle-prior` `3da7b187`), under the Captain's build go of 2026-11-13 13:58Z.
**Status:** Proposed. HK-011: a `src/` change for a separate Developer session. 🛑 **No push, no PR, no merge, no `pre_merge_check.py` on your own initiative.** QA pushes (HK-033), after QA's HK-039 review and `pre_merge_check.py` on the exact commit (HK-006).
**Branch:** new commits on **`feat/xc-template-prior`** on top of **`a88dd402`** (the accepted build `4b70e418` plus its tests-only edge test). Never commit to `main`.
**Version / native:** a further bump only if `python tools/check_version_bump.py origin/main` demands it. **No `native/` change** (the DLL SHA-256 `bbde6eb66af4cd429ffc46f67291ba718c1ae36ae39665faac24629bcb6e6528` stays). 🔒 NFR-021: Q-prefix calls only in tests; counts only in log lines.
**Scope fence (the Architect's):** **`git diff --stat a88dd402 HEAD -- src/OpenWSFZ.Ft8/` must be EMPTY.** The accepted decoder (`4b70e418`) is not touched, so no replay arm is repeated. Say so in your report with the command output.

---

## 0. Why (two items from the Architect's ruling §3)

The remedy build publishes a **batch 6** (template decodes, `PathTemplate = 3`) after batches 1 to 5. Two consumers downstream of the decoder are not ready for it:

1. **The QSO service queue is one batch short.** `LateBatch.BatchesPerCycleFallbackOn = 4` (`src/OpenWSFZ.Daemon/LateBatch.cs:64`) sizes the answerer and caller channels as batches × 2 cycles + 2 spare = 10 (`QsoChannelCapacityFallbackOn`, `:77`). With the stage ON a cycle can deliver up to six batches, so two queued cycles need 6 × 2 + 2 = **14**, otherwise a batch is dropped (DropOldest) while a service is blocked for a whole transmission.
2. **PSK Reporter would upload template decodes.** `PskReporterEngine` (`src/OpenWSFZ.Daemon/PskReporter/PskReporterEngine.cs`, the per-result filter at about `:174`) excludes AP decodes, unknown-region decodes, hashed and own-call messages, but has no rule for a template decode. A batch-6 row is a message inferred from a prior transmission, not heard in this cycle; it must not become a public spot. (QA's XC-SUP measured that a stale template on a station's next, different message is the failure mode.)

## 1. What to build

| Id | What |
|---|---|
| **D1 QSO capacity** | **`BatchesPerCycleFallbackOn` from 4 to 6**, so `QsoChannelCapacityFallbackOn` = 6 × 2 + 2 = **14**. **First confirm from `DecodePump` which batch numbers actually reach the QSO services** (the pump hands `batchNumber` through `LateBatch.Token`; check that batches 5 and 6 are not filtered out before the QSO channels). **If fewer than six reach them, the constant is the number that do, and you say so** with the FILE:LINE that shows it. Update the XML comments (they say "4 batches x 2 cycles + 2 spare = 10"). The flag-OFF capacity (8) is unchanged. |
| **D2 PSK exclusion** | `PskReporterEngine` excludes a result with `r.Path == PathTemplate (3)` as a **counted reason `template`** in its R9 line and window (beside `ap=`, `region=`, `hashed=`, `own=`, and so on: a `_exTemplate` counter and a `_window.Template` field, shown in the same way). Order: after the AP check, before the region check, so a template decode is counted under `template=` whatever else would exclude it. **`DecodeResult.Path` is already exposed** (`src/OpenWSFZ.Abstractions/DecodeResult.cs:55`); the constant `PathTemplate` lives in `Ft8Decoder` (`internal`); do not take a dependency from the Daemon on a decoder internal: add the constant to `OpenWSFZ.Abstractions` (next to `Path`) or mirror it with a test that pins the equality, and say which. **The panel, `ALL.TXT`, the QSO services and GridTracker still get batch 6 (no change there).** |

## 2. Tests (TESTING_STRATEGY §11: no fixed sleeps; CI runs macOS and Linux; each must be able to fail, QA mutates)

1. **D1:** with the stage's batch count (6 per cycle), **two full cycles of six batches queued while the service is blocked drop nothing; a third cycle drops the oldest** (the channel holds exactly 14). Assert the capacity constant, and assert the OFF capacity is still 8. (Block the service with a gate you release; no sleeps.)
2. **D2:** a **mixed batch** (one batch-1 row and one template row, both otherwise uploadable, Q-prefix calls) uploads **only the batch-1 row**, and the R9 line reports **`template=1`**. A template row that would also be excluded for another reason (an unknown region) is counted under `template` only. A batch-1 row is unaffected (a row with `Path` 0 or 2 still uploads).
3. **D2 not a filter for the other consumers:** the same mixed batch reaches the panel / `ALL.TXT` writer / QSO service with both rows (an existing consumer test extended, or one new one).
4. **The constant pinned:** the value the Daemon uses for "template" equals the decoder's `PathTemplate` (3).

## 3. Not in this task

No change to `src/OpenWSFZ.Ft8/` (**the diff there must be empty**), to the decoder's batches, thresholds, T_E, T_P, the veto, or any setting default. **No default ON** (that is the Captain's separate go and starts a new era). No change to PSK Reporter's other exclusion reasons or to the panel.

## 4. What QA will check

B-NAT (`git diff --stat a88dd402 HEAD -- native src/OpenWSFZ.Ft8/Native src/OpenWSFZ.Ft8/` empty; DLL SHA-256 pinned); the QSO-queue and PSK suites and the full unfiltered suite on a clean tree (your counts and mine); a mutation pass on D1 and D2; then `pre_merge_check.py` on the exact commit and macOS/Linux CI after the Captain's go to push. HK-039 record before anything launches.

## 5. Questions to answer in your report

1. **Which batch numbers reach the QSO services** (FILE:LINE in `DecodePump` and `Program.cs`), and the final constant.
2. Where the `template` count is shown (log line field name, the window struct) and the line of the filter.
3. Where the `PathTemplate` constant now lives, and why.
4. Any other consumer of a decode batch that assumes at most five batches (grep for `== 5`, `<= 5`, `LateRoundBatch` switches) and what it does with batch 6.

## 6. Gates you run before handing back

The full unfiltered `dotnet test OpenWSFZ.slnx -c Release` (exact command line and per-project counts, HK-022), `openspec validate --all --strict` (extend the change's `design.md` and delta spec), `python tools/check_version_bump.py origin/main` after committing, the traceability gate (G3) clean. 🛑 **Do not run `pre_merge_check.py`.**

## 7. Stop-and-tell conditions

Stop and report to QA, without building around it, if: fewer than six batches reach the QSO services and the answer changes what the Architect ruled; the PSK filter would need a change in `src/OpenWSFZ.Ft8/`; the `template` reason cannot be added without changing the R9 line's existing field order for other reasons.

## 8. Report back (HK-001 sections), then STOP

The commit hash(es); the §1 table answered row by row with FILE:LINE; the §5 answers; the test list with what each asserts; the command lines and counts of the full suite; the **empty `git diff --stat` on `src/OpenWSFZ.Ft8/`**; deviations and why. **Then stop**: QA reviews, runs `pre_merge_check`, and the PR waits for the Captain's go.
