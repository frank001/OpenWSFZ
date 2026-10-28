# Developer task: COH-GATE-G R-F4, the residual-audio fallback rows skip the F1b gate, behind a setting (default OFF)

**To:** Developer · **From:** QA · **Date:** 2026-10-28T17:35:36Z (`date -u`) · **Base:** `origin/main` `95e69e87` (v0.66, PR #270). Branch suggestion: `dev/coh-gate-r-f4`.
**Authority:** the Captain ("spec it for qa", 2026-10-28, relayed by the Architect) after the G-BUILD ruling `db578cf7` on `arch/coh-gate-g`. Build spec `qa/rr-study/2026-10-28-1724-architect-to-qa-build-spec-coh-gate-r-f4.md` with Amendment 1 section 7 (`15e0f838`; read with `git show 15e0f838:<path>`). OpenSpec change `openspec/changes/coh-gate-r-f4/` (proposal, design, delta spec with scenarios, tasks): read all four first. QA reference for the merge semantics: `qa/rr-study/gap-relocate-run/gg_lib.py` (`publish`, `select`) on `qa/refset`.
**You do not push.** Path afterwards: QA's HK-039 review of your commit, the acceptance rows on the PC, `pre_merge_check.py` from a clean checkout (HK-006), the Captain's push go (HK-033), his merge sign-off (HK-010).

## What to build (C# only)

1. **A new setting** `decoder.coherentFallbackResidualUngated` (bool; absent or false = today's behaviour). `DecoderConfig`, a volatile field on `Ft8Decoder` set by the daemon before the first window, read once per window; overlay semantics of HK-035 (a partial post leaves it as it was); no Settings-page control. It acts only in `Both` mode.
2. **In `Both` mode**, a `GatedOut` row from the run that read the **residual** audio (`choice.IsResidual`, `Ft8Decoder.cs:1060-1069` on `95e69e87`) is treated as `NewGated` **from the merge onwards**: it joins the residual key set (so an original-run `NewGated` row with the same payload is dropped), takes part in `Select`'s one-row-per-payload and edge rules in candidate order (sorted by the row's index within its run, residual before original, as `CohFallbackAudioSelector.Merge` does), then unpack, per-cycle text de-duplication and `IsPlausibleMessage` run unchanged. Sites: `CoherentFallbackSelector.cs:31`; `Subfeas/CohFallbackAudioSelector.cs:101/105/114`. `GatedOut` rows of the original-audio run are never admitted. `Original` and `Residual` modes are unchanged. A lone original-audio run (`both(unavailable)`) admits nothing. If the residual run completed and the original run was not started for budget (`leftMs <= 0`), the residual run's rows are still admitted.
3. **The row keeps its true state** for diagnostics (a separate flag or a wrapper, your choice); never relabel it `NewGated` in any counter or log.
4. **The log line** (`Ft8Decoder.cs:1122` on `95e69e87`; the spec said 1125): `ungated=N` (published messages that came from admitted rows) printed **only when the setting is ON**; `fromOriginal / fromResidual / inBoth` count admitted residual rows as found by the residual run; `Gated` keeps its meaning (at or below T1).
5. 🔴 **No native change.** `git diff --stat origin/main -- native/ src/OpenWSFZ.Ft8/Native/` must be empty and the built `libft8.dll` SHA-256 must equal `1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914`. The native side already fills a `GatedOut` row before the gate decides (`ft8_shim.c:2618`, `:2637`). If you find a native change unavoidable, STOP and tell QA.

## Tests (TESTING_STRATEGY section 11: no fixed sleeps; CI runs macOS)

Merge and `Select` with residual `GatedOut` rows, ON and OFF; an original-run `NewGated` row dropped by an admitted residual row with the same payload; edge preference across the mixed states; absent key = OFF, explicit round trip, a partial post leaves it as it was; `Original` and `Residual` modes ignore the setting; the log line (`ungated=` only when ON, counters as above); and, through the existing `BudgetClock`/`TimeProvider` seam of `c9255ae2` (stub backend, `workers = 1`, named budget constants, no sleeps): **(a)** residual run complete, original run `NotRun` (budget spent): the residual `GatedOut` rows are admitted and published; **(b)** a lone original-audio run: nothing is admitted over T1.

## Housekeeping

`VERSION` 0.66 to 0.67 in every place the gates check (the `REQUIREMENTS.md` anchor too); run `check_version_bump.py` and G9a/G9b (**G9b reads the proposal from git: the OpenSpec change is committed on `qa/refset` first**). `REQUIREMENTS.md`: the next free `FR-` (FR-101 at the time of writing; take the next free number on `origin/main`) and a changelog row (1.63 at the time of writing). `openspec validate coh-gate-r-f4 --strict` before committing any edit to the change; if the OpenSpec text and your code disagree, tell QA, do not edit `tasks.md` (QA's, HK-015).

## Not in this round

No change to T1, to `Original` or `Residual`, to the F1b computation or to native code; the setting is OFF by default and stays so; no Settings control; no re-measurement (QA runs the acceptance rows).

## Report back (HK-001 sections), then STOP

The commit hash; points 1-5 answered with FILE:LINE (and the line drift against this file); the full Windows suite counts; the new tests named, with how the clock is controlled in 3(a)/(b); `git diff --stat origin/main -- native/ src/OpenWSFZ.Ft8/Native/` (empty) and the DLL SHA-256. Do not push.
