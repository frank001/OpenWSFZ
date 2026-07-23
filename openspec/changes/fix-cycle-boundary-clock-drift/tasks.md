## 1. Design finalisation

- [ ] 1.1 Finalise the drift-detection threshold and per-event correction cap (`design.md` Open
      Questions) — derive concrete constants from the ~42 ppm-scale error QA measured
      (`qa/rr-study/results/2026-07-23-d001-live-path-root-cause/phase3_clockrate_results_usbcodec.json`),
      with a short written rationale in code comments (mirrors the existing `CycleFramer`
      documentation style — see the class-level `<summary>` and `R3`-style inline notes already
      present).
- [ ] 1.2 Decide and document whether a resync event is logged (Debug or Information level) —
      design.md leans yes; confirm and pick the level/format consistent with existing
      `CycleFramer` log lines (`CycleFramer started; ...`, `Window emitted ...`).

## 2. Implementation

- [ ] 2.1 Add the accumulated-deviation tracking to `CycleFramer.RunAsync` (nominal
      arithmetic cycle-boundary sequence vs. `_clock.UtcNow`), threshold-gated per design.md
      Decision 3.
- [ ] 2.2 Implement the bounded correction: adjust the next window's target sample count by a
      small, capped amount and re-anchor `cycleStart` to the corrected wall-clock value at that
      boundary, per design.md Decision 2. Ensure the correction can be either sign (window
      slightly shorter or longer) since drift direction is device-dependent, not assumed
      negative.
- [ ] 2.3 Cap a single correction event's magnitude so one anomalous/implausible `IClock`
      reading (e.g. a host clock step) cannot produce an unbounded jump — per design.md's risk
      mitigation.
- [ ] 2.4 Add the resync log line decided in 1.2, if any.

## 3. Tests

- [ ] 3.1 Unit test: no correction fires when `IClock.UtcNow` advances in exact lock-step with
      the nominal cycle-boundary sequence across many emitted windows (spec scenario "No
      correction fires for a session with no clock deviation").
- [ ] 3.2 Unit test: a bounded correction fires once accumulated deviation (simulated via a
      fake `IClock` advancing at a constant rate offset from nominal) exceeds the threshold —
      assert the correction is within the documented cap and `cycleStart` is re-anchored, not
      just arithmetically advanced (spec scenario "Bounded correction fires once accumulated
      deviation exceeds the threshold").
- [ ] 3.3 Unit test: a single implausibly large one-off `IClock` deviation does not produce a
      correction exceeding the documented per-event bound (spec scenario "A single implausibly
      large clock deviation does not trigger a single large correction").
- [ ] 3.4 Confirm existing `tests/OpenWSFZ.Ft8.Tests/CycleFramerTests.cs` coverage (leading-
      silence alignment, window emission, cancellation) still passes unmodified — the
      correction must be provably inert for every existing test's `IClock` usage.

## 4. Verification

- [ ] 4.1 Run `python3 tools/pre_merge_check.py` — full gate (G9a, Release build+tests, G3
      traceability, G8 openspec validate, G9b, AOT publish) before calling this ready for merge,
      per HK-006.
- [ ] 4.2 openspec archive workflow: confirm `openspec validate --strict` passes for this
      change before archiving.

## 5. Suggested follow-up validation (not blocking merge)

- [ ] 5.1 Once merged, re-run the Tight-class and Isolated-class replay pilots
      (`qa/rr-study/results/2026-07-23-d001-tight-class-replay/`,
      `qa/rr-study/results/2026-07-23-d9ab692-d001-isolated-pipeline-diagnosis/` harnesses)
      against a corrected build to measure how much of the ~23.4% Isolated-class
      Decoded-on-replay gap this fix actually recovers. Needs live audio hardware and session
      time — explicitly not a merge gate for this change; track as a separate QA follow-up.
