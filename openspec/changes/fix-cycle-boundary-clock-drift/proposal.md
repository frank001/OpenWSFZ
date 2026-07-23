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
  sequence against the injected `IClock`; once accumulated deviation exceeds a threshold, it
  corrects the next window's sample count by a small bounded amount and re-anchors `cycleStart`
  to the true wall-clock value. Confined to `CycleFramer` — the one platform-agnostic point
  downstream of all three capture implementations — not the platform-specific capture/resampler
  layer (see `design.md` Decision 1 for why that alternative was rejected).
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

`audio-capture` is **not** modified: `design.md` (Decision 1) rejected fixing this at the
platform-specific capture/resampling layer, since two of three platforms resample via an
opaque external process that cannot be uniformly calibrated from this codebase. The fix is
confined to `CycleFramer`, the single platform-agnostic point downstream of all three capture
implementations.

## Impact

- **Code:** `src/OpenWSFZ.Ft8/CycleFramer.cs` only (cycle-boundary bookkeeping).
- **Tests:** new coverage using a fake/injectable `IClock` in `CycleFramer` tests, asserting
  (a) no correction fires absent drift, (b) a bounded correction fires once accumulated
  deviation exceeds threshold, (c) a single implausibly large deviation does not produce an
  unbounded jump.
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
