**User-facing:** no

## Why

QA's live-path root-cause investigation (`qa/rr-study/results/2026-07-23-d001-live-path-root-cause/report.md`,
D-001) found that OpenWSFZ's decoded FT8 DT drifts at ~-0.171 s/hr relative to WSJT-X for the
same signals — consistent across three independent live sessions (t-statistics in the
hundreds-to-thousands; not noise). A direct measurement of the actual capture device used in
those sessions found a genuine ~-42 ppm clock-rate error, which — combined with
`CycleFramer`'s cycle boundary being computed once at startup and then advanced purely by
sample count, never re-synced to wall clock — predicts -0.153 s/hr of drift via that mechanism
alone: 89% of the independently-measured figure, matching sign in all three sessions. Over a
17-hour session this accumulates to roughly 2.6 seconds of decode-window lag against true UTC,
plausibly explaining a meaningful share of the ~23.4% "Isolated-class" low-SNR misses that a
prior pilot (`qa/rr-study/results/2026-07-23-d9ab692-d001-isolated-pipeline-diagnosis/report.md`)
found decode successfully on isolated replay but fail live. This is a real, quantified,
long-session decode-recall defect with a well-understood mechanism — worth fixing now rather
than carrying indefinitely as an unexplained gap.

## What Changes

- Bound the drift between OpenWSFZ's internal FT8 decode-cycle timing and true wall-clock/UTC
  over a long-running capture session, instead of letting it accumulate unbounded for the life
  of the process.
- Mechanism (per `design.md`): `CycleFramer` periodically compares its arithmetic cycle-boundary
  sequence against the injected `IClock`; once accumulated deviation exceeds a threshold **and
  that threshold-crossing persists across several consecutive checks in the same direction
  without shrinking** (design.md Decision 4 — added after live pre-merge evidence showed a real
  capture pipeline's own recurring scheduling latency, not genuine device drift, was triggering a
  correction on every single cycle), it corrects the next window's sample count by the full
  confirmed accumulated deviation — bounded only by a much larger sanity ceiling that guards
  solely against a pathological `IClock` reading, not by a small fixed quantum (design.md
  Decision 5 — added after a live endurance re-test found the original small fixed cap absorbing
  as little as 0.3% of confirmed deviation per firing) — and re-anchors `cycleStart` to the true
  wall-clock value. Confined to
  `CycleFramer` — the one platform-agnostic point downstream of all three capture
  implementations — not the platform-specific capture/resampler layer (see `design.md`
  Decision 1 for why that alternative was rejected).
- No new user-facing capability and no breaking API change is intended — this is a correctness
  fix to existing decode-timing behavior. The observable effect is improved decode recall on
  long-running sessions, not a new feature.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `ft8-decoder`: adds a new requirement bounding how far the decode-cycle boundary may drift
  from true wall-clock/UTC over a session (there is currently no such requirement — cycle
  timing accuracy over long sessions is an undocumented gap, not a regression of stated
  behavior).

`audio-capture`'s *correction behaviour* is **not** modified: `design.md` (Decision 1) rejected
fixing the drift itself at the platform-specific capture/resampling layer, since two of three
platforms resample via an opaque external process that cannot be uniformly calibrated from this
codebase. The correction mechanism remains confined to `CycleFramer`, the single
platform-agnostic point downstream of all three capture implementations. `WasapiAudioSource.cs`
and `CaptureManager.cs` gained Debug-level *diagnostic* instrumentation only (Decision 6) — no
change to capture, resampling, or correction behaviour on any platform.

## Impact

- **Code:** `src/OpenWSFZ.Ft8/CycleFramer.cs` (cycle-boundary bookkeeping), plus, as of the
  root-cause instrumentation added for `tasks.md` 8.1
  (`dev-tasks/2026-07-24-cycleframer-correction-not-converging-live-evidence.md`, design.md
  Decision 6): `src/OpenWSFZ.Audio/WasapiAudioSource.cs` and `src/OpenWSFZ.Audio/CaptureManager.cs`
  — Debug-level, periodically-aggregated diagnostic timing only (capture-cadence and
  channel-hop latency), no behavioural change. Scope was originally confined to `CycleFramer.cs`
  alone (Decision 1's platform-agnostic-fix-point reasoning still holds for the *correction*
  itself); this amendment widens only the diagnostic-instrumentation scope, needed because a live
  endurance re-test found the (correctly-sized, per Decision 5) correction firing exactly as
  designed yet still not converging, and isolating why requires visibility into the capture
  pipeline stages upstream of `CycleFramer`, not just `CycleFramer` itself.
- **Tests:** new coverage using a fake/injectable `IClock` in `CycleFramer` tests, asserting
  (a) no correction fires absent drift, (b) a bounded correction fires once accumulated
  deviation exceeds threshold, (c) a single implausibly large deviation does not produce an
  unbounded jump; plus Debug-log-assertion coverage in `CycleFramerTests.cs` and
  `CaptureManagerTests.cs` for the diagnostic instrumentation above.
- **Validation:** re-running the Tight/Isolated replay pilots
  (`qa/rr-study/results/2026-07-23-d9ab692-d001-isolated-pipeline-diagnosis/` and
  `qa/rr-study/results/2026-07-23-d001-tight-class-replay/` harnesses) against a corrected build
  is the natural way to measure how much of the ~23.4% Isolated-class gap this recovers — noted
  as a suggested follow-up validation step in `tasks.md`, not a blocking requirement of this
  change itself (it needs live audio hardware and hours of session time, not something to gate
  merge on).
- **No** decode-behaviour change for short/typical sessions — the drift is only material after
  many hours of continuous operation; this only affects long-running daemon sessions.
- **No** dependency or external-interface changes.
