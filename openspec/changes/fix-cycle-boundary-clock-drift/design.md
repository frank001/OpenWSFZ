## Context

`CycleFramer.RunAsync` (`src/OpenWSFZ.Ft8/CycleFramer.cs`) anchors `cycleStart` once at startup
via `AlignToCycleStart(_clock.UtcNow)`, then advances it by pure arithmetic
(`cycleStart.AddSeconds(15)`) after every emitted window, forever — it is never re-checked
against `_clock.UtcNow` again. Separately, each window's actual *content* is always exactly
`SamplesPerCycle` (180,000) raw samples pulled from the already-12kHz-resampled `ICaptureSource`
stream, with no adjustment.

QA's investigation (`qa/rr-study/results/2026-07-23-d001-live-path-root-cause/report.md`)
measured the real capture device used in three historical sessions running its clock ~42 ppm
slow relative to its declared rate. Because 180,000 resampled samples therefore take slightly
*more* than 15.000 true seconds to arrive, both problems compound: the `cycleStart` **label**
drifts from true UTC by simple arithmetic, and — more importantly for decode correctness — the
window's actual **sample content** also stops spanning exactly one true UTC 15-second slot,
since nothing ever re-aligns the sample-count-driven window boundary to wall clock. Only the
second effect can cause decode failures (a real signal's sync tone eventually lands outside the
decoder's DT search range within its own buffer, or spans two buffers); relabelling `cycleStart`
alone would fix reporting but not recall — see Decisions, "reject relabel-only."

Three platform-specific `IAudioSource` implementations exist upstream of `CycleFramer`:
Windows (WASAPI + NAudio's `WdlResamplingSampleProvider`, an in-process, fixed-ratio resampler),
Linux (`arecord`, an external process resampling internally), macOS (`sox`, likewise external).
`CycleFramer` is the one platform-agnostic point downstream of all three, consuming a common
`ICaptureSource` stream already normalised to 12,000 Hz mono — this shapes the central design
decision below.

## Goals / Non-Goals

**Goals:**
- Bound how far a decode-cycle window's actual sample content can drift from the true UTC
  15-second grid over an arbitrarily long-running session.
- Fix this once, for any capture device/platform, rather than per-platform.
- Make the correction testable without real audio hardware (via the existing injectable
  `IClock`).
- Leave short/typical sessions' behaviour unchanged — the correction should be a no-op until
  genuine, sustained drift is detected.

**Non-Goals:**
- Calibrating or correcting the platform-specific resampler/capture layer itself (rejected —
  see Decisions). Two of three platforms resample via an opaque external process, not
  something this change can uniformly calibrate.
- Sub-sample or sub-millisecond precision. The problem is a slow (~0.15–0.2 s/hr), smooth drift
  accumulating over many hours; the fix does not need finer resolution than roughly one FT8
  sample period.
- Actually measuring how much decode recall this recovers — that is a follow-on validation step
  (re-running the existing Tight/Isolated replay pilots against a corrected build), not part of
  this change's own acceptance criteria.
- Any change to `IClock`, `ICaptureSource`, or `IAudioSource`'s public contracts.

## Decisions

### Decision 1: Fix in `CycleFramer`, not in the platform-specific capture/resampling layer

**Chosen.** `CycleFramer` is the single point every platform's audio funnels through as a
common, already-12kHz, `ICaptureSource` stream. A fix here uniformly corrects for clock-rate
error regardless of which device or platform introduced it.

**Alternative considered — calibrate `WasapiAudioSource`'s resampler ratio to a measured true
device rate (rejected).** Architecturally appealing (fixes the error at its source), but
Windows-only: `arecord`/`sox` on Linux/macOS resample internally as external processes and do
not expose a way to feed in a corrected target rate from this codebase. Adopting this approach
would still leave Linux/macOS sessions drifting, and would require three separate, materially
different implementations to cover all platforms. Rejected in favour of the single
platform-agnostic fix point.

### Decision 2: Periodic bounded sample-count resync, not a timestamp-only relabel

**Chosen.** Periodically compare the nominal, arithmetic cycle-boundary sequence against
`_clock.UtcNow`. When the accumulated deviation exceeds a threshold, correct the **next**
window's target sample count by a small, bounded number of samples (shortening or lengthening
it slightly) so the window's actual content re-aligns to the true UTC grid, and re-anchor
`cycleStart`'s label to the corrected wall-clock value at that same boundary.

**Alternative considered — relabel `cycleStart` only, leave `SamplesPerCycle` fixed at 180,000
always (rejected).** This is the "obvious" naive fix and was seriously considered, but it only
corrects the *reported* timestamp, not which physical audio samples land in which window. Since
the actual decode-failure mechanism is a real signal's sync tone falling outside the decoder's
search range within its own buffer (or spanning two buffers), relabelling changes nothing about
decode outcomes — it would only make the daemon's own logs look more accurate while leaving the
underlying recall defect exactly as it is today. Rejected as insufficient to address the
problem this change exists to fix.

**Correction shape — a bounded "leap sample" adjustment, not a hard jump.** A ~42 ppm error
corresponds to roughly one sample of drift every ~24,000 samples (~2 seconds of audio) at
12,000 Hz — small enough that nudging a window's target size by a handful of samples at a
resync point is inaudible to FT8 sync-tone detection (tens of microseconds against a 15-second
slot) and does not corrupt either adjacent window's decodable content. This mirrors how NTP/PTP
clock discipline slews small, frequent corrections rather than stepping the clock.

### Decision 3: Correction is threshold-gated, not applied every cycle

**Chosen.** Only resync when the accumulated deviation between `_clock.UtcNow` and the nominal
boundary sequence exceeds a threshold meaningfully larger than ordinary `DateTime.UtcNow`/GC/
scheduler jitter (exact value TBD during implementation — see Open Questions), and cap the
per-event correction to a small bounded sample count.

**Rationale:** reacting to every single `IClock.UtcNow` read would risk chasing measurement
noise (a GC pause or scheduler hiccup can make one `UtcNow` sample look briefly "off" without
any real drift). A sustained-deviation threshold, combined with a capped correction quantum,
keeps the mechanism a slow slew that only ever engages for genuine multi-cycle drift — which is
exactly the failure mode this change targets — while remaining inert for the jitter that
already exists harmlessly in every session today.

### Decision 4: Gate the correction on persistence (several consecutive, same-sign, non-decreasing readings), not a single threshold crossing

**Added post-implementation, from live evidence** (`dev-tasks/2026-07-23-cycleframer-correction-fires-every-cycle-live-evidence.md`).
A live pre-merge validation run against a real capture pipeline (WASAPI → `Channel<float[]>` →
`CycleFramer`, concurrent with native FT8 decode on the same thread pool) found the correction
firing on every single 15 s cycle from the very first cycle, always at the per-event cap — not
the rare, occasional event Decision 3 designed. The raw arithmetic was confirmed self-consistent
(not a bookkeeping bug); real inter-window wall-clock cadence stayed close to nominal 15.000 s
throughout. The anomaly was specific to what the drift-check's single `IClock.UtcNow` read was
measuring: a recurring, roughly-constant-order-of-magnitude (tens to ~200 ms observed),
non-monotonic pipeline-scheduling latency between "audio truly arrived" and "`CycleFramer`'s
code got scheduled to read the clock" — 100-300x larger than the ~7.6 samples/cycle genuine
device drift this change targets, but recurring every cycle rather than accumulating.

**Chosen.** Require `RequiredConsecutiveReadings` (3) consecutive drift-check readings that (a)
clear `DriftThresholdSamples`, (b) share the same sign, and (c) are non-decreasing in magnitude
versus the previous reading in the streak, before applying a correction. Any reading that fails
any of those three conditions starts a fresh candidate streak rather than continuing the old one.

**Why this distinguishes the two cases:** genuine device clock-rate drift, left uncorrected,
accumulates monotonically every cycle (each reading strictly larger than the last, same sign) —
it will always eventually satisfy a same-sign, non-decreasing streak, however long. The observed
pipeline latency bounces from cycle to cycle without a consistent trend (verified against the
live evidence's own logged second-session sequence — 1162.5, 814.1, 1326.1, 1181.4, 772.2,
547.7, 1016.1 samples — which never sustains a non-decreasing run of 3), so it essentially never
satisfies the same persistence test. This is a direct, testable consequence of the two
processes' different shapes (monotonic accumulation vs. bounded, non-monotonic noise), not a
tuned-to-one-trace heuristic.

**Alternative considered — re-derive `DriftThresholdSamples`/`MaxCorrectionSamples` directly
from the observed pipeline noise floor (~500-2400 samples) instead of gating on persistence
(partially adopted).** Raising `DriftThresholdSamples` alone to clear that noise ceiling would
make genuine drift take roughly 80+ minutes just to become a threshold candidate at all, without
actually improving noise rejection (persistence gating already does that job regardless of a
single reading's magnitude) — so `DriftThresholdSamples` is left at its original Phase-3-derived
value (24). `MaxCorrectionSamples` **is** raised (32 → 48): persistence-gating necessarily delays
a genuine correction until several cycles after the threshold is first crossed, so accumulated
deviation at fire time is typically larger than a single-cycle crossing; a modestly larger cap
resolves it in fewer follow-on slew events. This is a bounded, reasoned adjustment tied to the
new mechanism's own delayed-reaction effect, not a blind retune against the noisy live trace.

**Deferred, not done in this pass:** stage-by-stage timestamp instrumentation (WASAPI
`DataAvailable` firing time, `Channel<float[]>` enqueue/dequeue instants) to isolate the
proximate cause of the recurring latency was recommended in the live-evidence dev-task as
Recommended Next Step 1. `CycleFramer` now logs its own per-check deviation and persistence
streak at Debug level (within this change's approved `Impact: CycleFramer.cs only` scope), but
instrumenting `WasapiAudioSource`/the capture layer itself is outside that stated scope and
would need its own scope decision (a proposal.md amendment or a follow-on change) — tracked as
an open follow-up in `tasks.md`, not done silently here.

## Risks / Trade-offs

- **[Risk] A large, one-time system clock step (operator changes system time, host NTP client
  steps the clock) could be misread as accumulated device drift and trigger a correction.**
  → Mitigation: cap the per-event correction to a small bounded sample count (Decision 2) so a
  large step cannot produce a single large, decode-corrupting jump; optionally detect
  implausibly large single-reading deviations and skip correction that cycle with a logged
  warning, deferring to the next check instead of over-correcting on a possibly-spurious sample.
- **[Risk] Wrong threshold/quantum tuning either over-corrects (chases jitter) or
  under-corrects (still allows meaningful drift to accumulate).** → Mitigation: values are
  derived from the measured ~42 ppm-scale error (Open Questions proposes concrete starting
  numbers) and validated by unit tests against a fake `IClock` before any live re-run; the
  qa replay-pilot re-run (tasks.md) provides an independent real-world check once implemented.
- **[Risk] Regression on the vast majority of short/typical sessions where drift never
  accumulates enough to matter.** → Mitigation: the correction is designed to be a no-op below
  threshold — no behavioural change is expected or should occur for typical session lengths;
  this must be explicit in the spec scenarios and covered by a test asserting no correction
  fires for a short/no-drift `IClock`.
- **[Trade-off] This fixes the CycleFramer-level symptom but does not address the underlying
  device clock-rate error itself** (which remains ~42 ppm off, uncorrected at the source) —
  accepted, per Decision 1's platform-uniformity argument; a resampler-level fix would only
  cover Windows.

## Migration Plan

No data migration. This is a behavioural change confined to `CycleFramer`'s internal cycle-
boundary bookkeeping — no public API, config schema, or persisted-state change. Recommend
shipping always-on (no feature flag): the correction is designed to be inert below threshold,
so there is no meaningful "opt out" state worth adding complexity for. If the Architect prefers
a kill-switch given this touches core decode timing, that can be added cheaply in `tasks.md`
without changing the design above.

Rollback: revert the `CycleFramer` change; no other component depends on the new behaviour.

## Open Questions

- **Exact drift threshold to trigger a resync, and the per-event correction cap.** Proposed
  starting point, to be confirmed during implementation: trigger when accumulated deviation
  exceeds roughly one sample period at typical check cadence (i.e., check every cycle, but only
  act once cumulative deviation exceeds a small multi-sample threshold — enough to be clearly
  above `DateTime.UtcNow` jitter, small enough that no more than a handful of cycles pass
  between corrections at the measured ~42 ppm rate); cap each correction to a small bounded
  sample count. Finalise with a unit test asserting both "no correction below threshold" and
  "correction fires and is bounded above threshold."
- **Should `CycleFramer` log when a resync fires?** Leaning yes (Debug or Information level,
  low volume given corrections are rare) — useful for any future investigation of this same
  class of issue, and cheap. Confirm in tasks.md.
- **Feature flag or always-on?** Design recommends always-on (see Migration Plan); flag if the
  Architect disagrees.
