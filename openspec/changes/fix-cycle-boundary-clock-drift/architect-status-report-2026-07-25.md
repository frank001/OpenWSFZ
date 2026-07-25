# Architect Status Report — `fix-cycle-boundary-clock-drift`

**Prepared by:** QA
**Date:** 2026-07-25
**Change:** `openspec/changes/fix-cycle-boundary-clock-drift/` (PR #108, `docs/propose-fix-cycle-boundary-clock-drift`, **not merged**)
**Purpose:** Bring the Architect up to date on a defect that has now survived four independent fix attempts, and to ask for a direction decision — this is no longer a tuning problem QA and Developer sessions can resolve alone.

---

## 1. Executive summary

OpenWSFZ's decode-cycle timing drifts from true wall-clock/UTC over long-running sessions (originally measured at ~-0.171 s/hour, traced to a genuine ~-42 ppm capture-device clock-rate error). We set out to bound that drift inside `CycleFramer`, the one platform-agnostic point downstream of all three capture implementations. **Four architecturally-distinct fix attempts have now been built, unit-tested, and live-tested — and every one has been defeated by live endurance testing.** The correction mechanism fires exactly as designed each time; the underlying deviation does not converge. The most recent and most rigorous test (11h51m overnight, 40m band, 2,839 cycles) shows correction magnitude growing **~8x hour-over-hour with no plateau** — this is not a "needs more time" result, it is a clear signal that something about how we're framing the fix is wrong.

Nothing has been merged. The `src/` diff for the fourth attempt sits uncommitted on the branch, held under our HK-011 pre-push discipline specifically because it has not passed its live acceptance test.

**What we need from the Architect:** a decision on which of two recorded fallback directions to pursue (Section 6), since continuing to iterate on the current fix's internal accounting has now been tried four times without success.

---

## 2. Where this came from

QA's D-001 live-path root-cause investigation (`qa/rr-study/results/2026-07-23-d001-live-path-root-cause/report.md`) found OpenWSFZ's decoded FT8 DT drifting at ~-0.171 s/hr relative to WSJT-X on the same signals, consistent across three independent sessions (t-statistics in the hundreds-to-thousands — not noise). A direct measurement of the capture device found a genuine ~-42 ppm clock-rate error, which — combined with `CycleFramer` computing its cycle boundary once at startup and then advancing it by pure sample-count arithmetic, never re-synced to wall clock — predicts 89% of the measured drift by mechanism alone. Over a 17-hour session this accumulates to ~2.6 s of decode-window lag, plausibly explaining a meaningful share of a ~23.4% "Isolated-class" low-SNR miss rate found in a separate replay pilot.

This is a real, quantified, well-understood-mechanism decode-recall defect — worth fixing, not carrying indefinitely.

## 3. Design decision so far: fix in `CycleFramer`, not the capture layer

`design.md` Decision 1 confined the fix to `CycleFramer` because it is the single point every platform's audio (WASAPI+NAudio on Windows, `arecord` on Linux, `sox` on macOS) funnels through as a common, already-12kHz stream. Calibrating the platform-specific resampler was rejected because two of three platforms resample via an opaque external process this codebase cannot uniformly correct. **This decision is the one now in question** — see Section 6.

## 4. Timeline of fix attempts, all defeated by live testing

| # | Mechanism | Decision | Live test | Duration | Outcome |
|---|---|---|---|---|---|
| 1 | Threshold-gated correction, small fixed cap, reacts to any single reading | Decisions 2–3 | Pre-merge validation run | — | Fired on **every single cycle** from cycle 1 — driven by real pipeline scheduling jitter (WASAPI callback/channel backpressure), not genuine device drift. Not the rare event designed. |
| 2 | + Persistence gate (3 consecutive same-sign, non-decreasing readings required before firing) | Decision 4 | `ce13e30` | 7h54m | Persistence gate worked correctly (0 false positives despite every reading exceeding threshold) — but once confirmed, 20 corrections removed only ~6% of the 16,155-sample accumulated growth. Sizing wrong. |
| 3 | + Size correction to the full confirmed deviation (cap becomes a sanity ceiling, not a slew quantum) | Decision 5 | `1cebf81` | 6h16m | Sizing formula fired exactly as specified (all 10 corrections matched confirmed deviation to the sample) — but every single correction left the next reading within ±4% of its pre-correction value. Correctly sized, does not converge. |
| — | + Pipeline-timing instrumentation added (WASAPI/CaptureManager/CycleFramer stage timestamps) to isolate why | Decision 6 | `29041f7` | 32 min (short, by design) | Instrumentation stayed completely flat throughout a ~40% rise in deviation-at-fire — rules out capture-pipeline scheduling delay as the cause. |
| — | Candidate mechanism identified from `29041f7`'s own artefacts: a discard correction must wait for real samples to arrive, spending (not reclaiming) wall-clock time, which the next check re-measures as fresh "drift." Confirmed via two isolated, confound-free unit tests. | Decision 7 (8.7) | `f57fa4d` | 39 min (short, by design) | Mechanism confirmed in isolation, 5/5 clean runs. Live: non-convergence persists a third time, at a rate (~35.3 samples/min) consistent with `ce13e30`/`29041f7` — strong cross-run evidence of one stable underlying mechanism. New finding: a flat +0.5–0.6 s DT offset vs. WSJT-X, larger than the drift-check's own measured deviation (unconfirmed, separate hypothesis, see Section 7). |
| 4 | Deviation-accounting fix: correct the arithmetic baseline (`nominalCycleStart`) so it anticipates a correction's own next-window real-time cost, instead of billing that cost as fresh drift | Decision 8 | `2026-07-25-40m-band-9.5-fail` | **11h51m (longest round yet)** | **FAILED.** Only 32/136 (23.5%) of corrections landed near the noise floor on their next reading. Correction magnitude grew ~8x hour-over-hour with no plateau. Pipeline-timing instrumentation stayed flat throughout (ruling that out again). Zero crashes, zero ERR/FTL — this is a convergence defect, not a stability one. |

Each round's fix was itself correctly implemented and unit-tested against the failure mode the *previous* round had found — and each was defeated by a *new* failure mode only visible under real hardware and session length. That pattern, four rounds running, is itself the main piece of evidence behind this report.

## 5. Current technical state

- **Not merged.** PR #108 remains open against `docs/propose-fix-cycle-boundary-clock-drift`.
- **Uncommitted `src/` diff on the branch right now:** `src/OpenWSFZ.Ft8/CycleFramer.cs` and `tests/OpenWSFZ.Ft8.Tests/CycleFramerTests.cs` (attempt #4, deviation-accounting fix), plus the associated `tasks.md`/dev-task documentation updates. Per HK-011, `src/` changes require a separate Developer session and the Captain's explicit pre-push sign-off before merge — that sign-off has correctly not been sought, given attempt #4's live result.
- **Mechanical gates:** every attempt has passed `pre_merge_check.py` (build, full test suite, traceability, openspec validation, AOT publish) at each stage — the gap is exclusively in live convergence behaviour, never in code quality, test coverage, or documentation discipline.
- **New infrastructure delivered as a side effect:** an unattended-run auto-recovery supervisor (HK-013, `qa/endurance/2026-07-24-supervisor.sh`) — kill/log/cooldown/restart on failure signature, capped retries, live-validated against the real process (two real bugs found and fixed before being trusted unattended, a third harmless edge case found overnight). This is what made the 11h51m round possible unattended and should be reused for any future overnight testing, on this defect or otherwise.

## 6. The decision this report is asking for

`design.md` Decision 8 already recorded two fallback shapes in case the deviation-accounting fix (attempt #4) failed. It has failed. The two fallbacks:

1. **Continuous small-quantum rate-tracking.** Replace periodic large corrections with a continuously-updated estimate of the device's real ppm error, nudging every window's sample target by a small amount each cycle, so no single correction is ever large enough to cost measurable real time in the first place. This sidesteps the entire class of defect all four attempts have run into (correction-event accounting), rather than trying to account for it more precisely. Stays within `CycleFramer`, so Decision 1's platform-uniformity property is preserved.
2. **Reopen Decision 1's scope boundary.** Fix the genuine device clock-rate error at the resampler/capture layer itself, upstream of `CycleFramer`. This is the more fundamental fix and matches what the original D-001 measurement actually found (a genuine device-level clock-rate error) — but reopens the exact trade-off Decision 1 rejected: `WasapiAudioSource` (Windows) could be calibrated in-process, but `arecord`/`sox` (Linux/macOS) resample via opaque external processes this codebase cannot uniformly feed a corrected rate into, meaning either three separate platform-specific implementations, or accepting a Windows-only fix while Linux/macOS keep drifting.

QA's read, offered for the Architect's judgement rather than as a recommendation to act on unilaterally (this is squarely a design-direction call, not a QA-scoped one): fallback (1) is the smaller, more surgical change and directly targets the specific defect class four live rounds have now converged on identifying (correction events costing real time); fallback (2) is architecturally more honest about where the error actually lives, at the cost of the platform-fragmentation problem Decision 1 was written to avoid. Continuing to refine attempt #4's internal accounting a fifth time is not recommended by anyone on record — `tasks.md` 9.6 explicitly says as much, and there are no more tunable constants left in that mechanism to adjust.

Two supporting analyses are available with **no further live session time** needed, if useful input before deciding:
- A session-wide DT-offset comparison against WSJT-X (extending the single-cycle spot-check from `f57fa4d`) using the preserved full-night WAV archive from the 9.5 run (2,827 files, 973 MB, `artefacts/20260724_live_run_2227/wav/`).
- A targeted, larger-N unit test of the discard/replay asymmetry noted in the 9.5 report (32/132 discard vs. 0/4 replay landing near the noise floor) — 4 replay events overnight is too thin a sample to trust independently.

## 7. One more thread, not yet chased down

The `f57fa4d` round's live DT comparison against WSJT-X (one cycle, 11 matched decodes) found OpenWSFZ running a flat **+0.5 to +0.6 s** higher than WSJT-X throughout — larger and flatter than the ~0.1–0.2 s `deviation` the drift-check instrumentation itself reported at that same point. This raises a hypothesis, explicitly not yet confirmed: a possibly separate, time-invariant measurement-reference offset, distinct from the session-scale drift this whole change targets. It is based on a single cycle, not a session-wide comparison, and has not been checked against any prior baseline. Flagged here because if real, it would sit outside everything Sections 4–6 discuss — a fixed offset, not a drift — and the Section 6 WAV archive could resolve it without new live time.

## 8. Bottom line

- Defect: confirmed, quantified, mechanism understood (device clock-rate error, ~-42 ppm).
- Fix location decision (Decision 1 — fix in `CycleFramer`): now the thing in question, not settled background.
- Four fix attempts inside that location: all correctly built, all correctly unit-tested against known failure modes, all defeated by live endurance testing at increasing session lengths and data richness.
- Nothing merged; HK-011 hold stands; no data loss, no stability defect, no regression risk taken.
- **Ask:** direction on Section 6's fallback (1) vs (2), or an alternative the Architect prefers, before a fifth attempt is built.

---

*Cross-referenced source material: `openspec/changes/fix-cycle-boundary-clock-drift/{proposal,design,tasks}.md`; `qa/endurance/2026-07-24-ce13e30/`, `2026-07-24-1cebf81/`, `2026-07-24-29041f7/`, `2026-07-24-f57fa4d/`, `2026-07-25-40m-band-9.5-fail/` (all `report.md`); `dev-tasks/2026-07-23-cycleframer-correction-fires-every-cycle-live-evidence.md`, `2026-07-24-cycleframer-correction-sizing-fix.md`, `2026-07-24-cycleframer-correction-not-converging-live-evidence.md`, `2026-07-24-cycleframer-deviation-accounting-fix.md`.*
