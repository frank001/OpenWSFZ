# Dev-task — CycleFramer clock drift is still present after PR #118; reconcile with its own oracle

**Author:** QA, 2026-08-02 (17:40 UTC, `date -u`). Repo at `455d893`.
**For:** a separate Developer-persona session (HK-011 — this is `src/` investigation and must
not run in the QA session that found the recurrence).
**Origin:** `qa/cycleframer-alignment-replay/2026-08-02-1714-architect-to-qa-correction-cycle-
grid-artefact-voids-8080-anova.md` §5 and §8 item 3; reopens
`DEFECT-capture-clock-drift-silent-decode-loss.md` (see that file's 2026-08-02 REOPENED
banner for the full evidence summary — read it before this task).

**This is investigation, not a prescribed fix.** The evidence below establishes that drift is
still occurring on affected hardware; it does not establish *why*, given that PR #118's own
oracle tests assert the opposite. Do not assume the original per-cycle-resync design is wrong
without first confirming the live code path actually executes it the way the oracle simulates.

---

## 1. The contradiction that needs resolving

`dev-tasks/2026-07-31-fix-cycleframer-clock-drift-boundary-resync.md` implemented per-cycle
wall-clock resync in `CycleFramer.RunAsync` (`src/OpenWSFZ.Ft8/CycleFramer.cs`), verified
against `tests/OpenWSFZ.Ft8.Tests/CycleFramerClockDriftOracleTests.cs`:

- `RunAsync_24hAt48ppmSlowClock_BoundaryDriftsWellBeyondTolerance` — asserts drift stays
  **within 0.2s** over a simulated 24h session at 48.4 ppm (pre-fix: 4.17s, unbounded).
- `RunAsync_DroppedChunkMidStream_PermanentlyShiftsAllSubsequentBoundaries` — asserts a single
  dropped chunk no longer permanently shifts subsequent boundaries.

Both are reported green on `main` since the fix merged.

**Live evidence directly contradicts the first guarantee.** A 43.8-hour live run on the same
affected hardware class (FT-991A / USB Audio CODEC) this fix targets shows cycle timestamps
drifting off the 15-second FT8 grid at **~0.18 s/h — the same order of magnitude as the
pre-fix ~45 ppm figure** — accumulating without bound within an uptime epoch and resetting
only on process restart (three restarts during the run produced three visible reset-and-
reaccumulate sawtooth cycles; see `qa/cycleframer-alignment-replay/2026-08-02-1714-...md` §2.2
for the full hour-by-hour table). That is roughly an order of magnitude beyond the oracle's
0.2s bound, reached in well under the oracle's 24h window.

**This is not merely a re-litigation of whether the fix is "enough."** The oracle test
*simulates* a 48.4 ppm slow clock and asserts the fix bounds drift under that simulated
condition. The live corpus is real hardware that the fix should also cover. Either:

1. The live code path does not actually perform the resync the way the oracle's simulation
   exercises it (an implementation gap between the tested unit and the deployed behaviour), or
2. The real device's drift characteristics differ from the oracle's linear-clock-rate-error
   model in a way that defeats the resync (e.g. non-linear drift, a resync that reads a stale
   or cached clock value, or something in `WasapiAudioSource`'s actual sample delivery that the
   oracle's synthetic clock doesn't reproduce), or
3. Something downstream of the timestamp resync (buffer/sample-index bookkeeping feeding the
   decoder) was not updated in step with the label, so the *reported* cycle start now honestly
   reflects wall-clock time while the *audio samples actually assigned to that cycle* remain
   governed by the old accumulated-sample-count logic — i.e. the label was fixed, the window
   wasn't. This reading is consistent with the correction's finding that DT (a decode-time
   property, not a logging property) tracks the label offset almost exactly 1:1, and that mean
   SNR degrades by ~10 dB per second of accumulated offset — real decode-quality damage, not a
   cosmetic mismatch.

**Determine which of these (or something else) is actually happening before proposing a fix.**
Option 3 is QA's leading hypothesis based on the evidence pattern, not a conclusion — it is
offered as a starting point for code reading, not a directive.

## 2. Evidence available

- `qa/cycleframer-alignment-replay/2026-08-02-1714-architect-to-qa-correction-cycle-grid-
  artefact-voids-8080-anova.md` §2 — the grid/sawtooth mechanism, per-hour offset table, the
  three restart-aligned resets, drift rate (~0.18 s/h ≈ pre-fix magnitude), and §2.3's DT/SNR-
  vs-offset table (each second of label drift costs ~10 dB reported SNR and moves DT ~0.9s).
- `qa/cycleframer-alignment-replay/2026-08-02-1721-architect-to-qa-spec-grid-snapped-anova-
  rerun.md` §3 and the QA re-run output in `qa/endurance/2026-08-02-multiday-20m-anova/table_c_
  drift_stratified_decode_ratio.md` — the actual decode-count cost, corrected for a same-
  instant zero-drift control (8081) so propagation is not a confound: decode ratio is flat to
  within noise up to +1s of accumulated offset, then falls off a cliff of roughly 30% at +2s.
  This is a threshold, not a smooth gradient — worth keeping in mind when designing any new
  oracle case (a single "drift accumulates linearly, decode count degrades linearly" model
  would not match what was actually measured).
- `artefacts/20260731_live_run_2004-8080/` (git-ignored, NFR-021) — the live run's own ALL.TXT,
  logs (5 files spanning the 3 restarts), and cycle-audio-archive WAVs, if a fresh offline
  reproduction against real captured audio is wanted rather than reasoning from the oracle's
  synthetic clock alone.
- `tests/OpenWSFZ.Ft8.Tests/CycleFramerClockDriftOracleTests.cs` — the existing oracle; read
  in full alongside `CycleFramer.cs`'s current `RunAsync` before forming a hypothesis.

## 3. What to build

Not prescribed — this task is investigation-first, per the header. At minimum:

1. Read `CycleFramer.cs`'s current `RunAsync` in full, specifically the resync point added by
   PR #118, and trace exactly what is and is not re-derived from the wall clock each cycle
   (the timestamp label alone, vs. the sample-window boundary itself, vs. both).
2. Reconcile why the oracle's synthetic 48.4 ppm simulation shows <0.2s drift over 24h while
   live hardware shows the pre-fix magnitude of drift within a few hours. If the oracle's
   simulated clock does not faithfully reproduce how `WasapiAudioSource` actually advances
   `IClock.UtcNow` (or however the real clock is consulted) in production, that is itself a
   finding worth recording, independent of whatever the eventual code fix turns out to be.
3. If §1's option 3 (label resynced, sample window not) is confirmed, the fix needs to
   re-derive which actual samples belong to a cycle from the wall clock, not just the
   timestamp used to label it — analogous in spirit to the original per-cycle-resync design,
   but applied to the thing that's still drifting rather than the thing that was already fixed.
4. Extend `CycleFramerClockDriftOracleTests.cs` with a case that would have caught this: a
   restart-punctuated multi-epoch simulation (drift accumulates for N hours, resets, repeats)
   rather than a single continuous 24h run, since that is the actual failure shape observed
   live and the existing oracle's single-epoch design cannot distinguish "bounded forever" from
   "bounded until the next restart happens to arrive first."
5. Do not relax the existing oracle's 0.2s tolerance to make it pass on unfixed code — if the
   real fix cannot hit that bound, stop and raise it with QA/Architect rather than loosening
   the acceptance criterion unilaterally (same standing instruction as the original dev-task).

## 4. Boundaries (do not deviate)

- Per **HK-011**: this is `src/` investigation/implementation. Run local build/tests only.
  **Show findings and any diff to the Captain for sign-off before `git push`** — not just
  before merge.
- Per **HK-006**: do not run `python3 tools/pre_merge_check.py` as part of this task or put it
  in any checklist — Captain's trigger only, at merge time.
- Per **HK-010**: merge to `main` needs the Captain's explicit sign-off regardless of green CI.
- If investigation concludes the defect is more involved than a targeted fix (e.g. requires
  rethinking the framer's whole timing model), **stop and escalate to QA/Architect** rather
  than expanding scope unilaterally — same discipline as the original dev-task's boundaries.

## 5. Traceability

- `DEFECT-capture-clock-drift-silent-decode-loss.md` — reopened 2026-08-02, full history.
- `dev-tasks/2026-07-31-fix-cycleframer-clock-drift-boundary-resync.md` — the PR #118 task
  this one follows up on; read its "What to build" section for the original design intent.
- `qa/cycleframer-alignment-replay/2026-08-02-1714-...-correction-cycle-grid-artefact-voids-
  8080-anova.md` — full evidence and mechanism.
- `qa/cycleframer-alignment-replay/2026-08-02-1721-...-spec-grid-snapped-anova-rerun.md` — the
  re-run spec that surfaced Table C's decode-cost-vs-drift-offset measurement.
- `project-state-2026-07-31-d001-competition-confirmed.md` (QA memory) — records this defect
  as fixed; needs correcting once this task's outcome is known (not edited here per HK — see
  the DEFECT file's REOPENED banner).
