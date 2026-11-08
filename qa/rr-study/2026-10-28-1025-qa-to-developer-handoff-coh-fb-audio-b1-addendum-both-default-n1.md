# Developer task: COH-FB-AUDIO B1 addendum, default `Both`, and N-1 (the budget guard test)

**To:** Developer · **From:** QA · **Date:** 2026-10-28 09:25:53Z (`date -u`) · **Base:** your reviewed commit `9ef703d0` on `dev/coh-fb-audio` (HK-039 record `881518b8`, APPROVED with notes N-1..N-3)
**Amends:** `qa/rr-study/2026-10-27-1950-qa-to-developer-handoff-coh-fallback-audio-config-b1.md` (commit `f77d1333`). Everything there that this file does not change still stands.
**Authority:** the Captain, 2026-10-28: *"Go with both"*. Architect spec Amendment 4 (`arch/coh-fallback-residual`, `bde72dc8`, section B4; read with `git show bde72dc8:qa/rr-study/2026-10-27-1818-architect-to-qa-coh-fallback-residual-replay-spec.md`). OpenSpec change: `openspec/changes/coh-fb-audio/` on `qa/refset` (QA's; do not edit it, tell QA if a line is wrong).
**You do not push.** Path afterwards: QA HK-039 review of your new commit, `pre_merge_check.py` from a clean checkout (HK-006), the Captain's push go (HK-033), his merge sign-off (HK-010).

## What to change

1. **An absent `decoder.coherentFallbackAudio` reads `Both`** (was `Residual`). Explicit values are unchanged. Fix the doc comment and every text that says "absent = Residual". If a shipped or example config writes the key, it writes `Both`.
2. The test "absent key gives Residual" becomes "absent key gives Both". The explicit-value round trips and the HK-035 overlay test stay.
3. **N-1 is required before merge.** It tests a guard that already exists in `9ef703d0`; it adds no production code. Re-check the line numbers on your tip and report any drift:
   - `src/OpenWSFZ.Ft8/Ft8Decoder.cs:1049-1061`: in `Both`, `leftMs = budgetMs − (elapsed since the fallback start)`; `leftMs > 0` runs the second run on `leftMs`, else the second run is not started and its eligible candidates are counted abandoned (`CohFallbackAudioSelector.NotRun`).
   - `src/OpenWSFZ.Ft8/CohFallbackParallelRunner.cs:65`: a worker claims no candidate once the run's wall clock is past its `budgetMs`.

   **(a) `leftMs <= 0`:** the second run does not start, its eligible candidates are counted abandoned, the first run's rows still publish. Assert the second run's backend was **never called**, the abandoned count **equals** the second run's eligible count, and the first run's rows are in the published set.
   **(b) `0 < leftMs` below one run's wall time** (the case the Architect asked QA to be sure is covered): the second run starts and stops claiming at its budget. Assert it processed **fewer** candidates than eligible (and at least the ones claimed before its budget), the rest counted abandoned, the first run's rows still publish, and the fallback's end is within `SubtractionCycleBudget − CoherentFallbackPublishReserve` plus the time of the one candidate in flight when the budget was reached (state that allowance as a named constant of the stub's per-candidate time).
4. **How to write N-1 so it does not flake** (TESTING_STRATEGY §11; CI runs it on macOS):
   - A **stub fallback backend with a controllable clock** (an injected time source, or a stub whose per-candidate cost advances a fake clock) so the budget is spent by arithmetic, not by sleeping. **No `Task.Delay`/`Thread.Sleep` as a means of spending budget.** If the production code reads `Stopwatch` directly and the clock cannot be injected without a `src/` change, **stop and tell QA** rather than inserting a fixed delay: a small seam is a Developer decision QA wants to see first.
   - Parallel workers make "how many candidates were claimed" non-deterministic in (b) unless `workers` is 1 in the test; set `workers = 1` for the exact-count assertion and say so.
   - Budgets are **named constants** derived from the production values (`SubtractionCycleBudget`, `CoherentFallbackPublishReserve`), not bare numbers.
5. **VERSION:** one minor bump for the arm in total (0.66), in every place the gates check (`REQUIREMENTS.md` anchor too: #266 R-1). Run `check_version_bump.py` and the G9a/b gates yourself. **G9b reads the proposal from git:** the OpenSpec change is committed on `qa/refset` (QA tells you the hash); base your branch so the proposal is visible, or tell QA and QA runs G9b.
6. **`REQUIREMENTS.md`:** add the next free `FR-` row (FR-099 at the time of writing; take the next free number on `origin/main` when you build) for the key, the default `Both` and the shared-budget rule; the wording is in `openspec/changes/coh-fb-audio/specs/ft8-coherent-fallback/spec.md`.
7. `native/` unchanged: report `git diff --stat origin/main -- native` (empty) and the `libft8` DLL SHA-256 against the pin.

## Not in this round

No re-measurement (B2 ran `Both` explicitly). R0 is unchanged: `Original` and `Residual` explicit stay byte-identical as before; report that the existing R0 evidence still holds, re-run only if you touched the paths it covers.

## Report back (HK-001 sections), then STOP

The commit hash on `dev/coh-fb-audio`; points 1-7 answered with FILE:LINE; the full Windows suite counts; the N-1 tests named, with how the clock is controlled. Do not push.
