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

### Decision 5: Once the persistence gate fires, absorb the full confirmed deviation — the per-event cap becomes a sanity ceiling, not a slew quantum

**Added post-implementation, from live evidence** (`dev-tasks/2026-07-24-cycleframer-correction-sizing-fix.md`,
following the fresh live endurance re-test at `qa/endurance/2026-07-24-ce13e30/report.md` that
validated Decision 4's persistence gate but found the *sizing* still wrong). Over a 7h54m21s live
session, the persistence gate worked exactly as designed — zero false-positive corrections in the
first ~9 minutes despite every reading exceeding threshold — but once genuine drift was confirmed,
20 corrections fired, every one saturating the (then-)48-sample cap, while accumulated deviation
climbed from 964 to 17,119 samples (net +16,155). The 20 corrections removed only 960 samples
total — about 6% of the growth — leaving a residual drift rate (≈0.171 s/hour) the same order of
magnitude as the original, unfixed D-001 defect this whole change exists to eliminate.

**Root cause.** `MaxCorrectionSamples` (Decisions 2–4) was sized reasoning about the persistence
gate's *delay* before a single threshold-crossing gets acted on, not about how large the
*confirmed, accumulated* deviation actually is by the time three consecutive non-decreasing
readings satisfy the gate. In the endurance run, deviation-at-fire-time ranged from ~1,700 to
~17,400 samples — the 48-sample cap absorbed as little as 0.3% of what had already been confirmed
genuine.

**Chosen.** Once `driftStreakCount >= RequiredConsecutiveReadings`, correct by the (rounded) full
accumulated deviation, not a small fixed quantum. The renamed `CorrectionSanityCeilingSamples`
(one full 15 s cycle = 180,000 samples) still clamps the applied correction, but purely as a
backstop against a truly pathological `IClock` reading (a `DateTime` overflow, a multi-day
misconfigured system clock) — not as a mechanism for slowly chipping away at ordinary confirmed
drift. This ceiling sits roughly an order of magnitude above any deviation-at-fire observed in the
endurance run (max 17,438 samples) and well below the ~3,600,000 samples a 5-minute host clock
step would produce, so a genuinely pathological step still slews over several corrections rather
than landing as one 15-second jump, while ordinary confirmed drift (of any magnitude actually seen
in practice) is now fully absorbed in the single event that confirms it.

**Why this is still consistent with the change's Goal of *bounding* drift, even though individual
corrections may now be materially larger than 48 samples:** the goal was always to bound
*accumulated* deviation from true UTC over an arbitrarily long session, not to bound the size of
any single correction event. Decision 2's "small, bounded... slew, not a step" framing was written
to justify *why a cap exists at all* (protecting against a single unconfirmed, possibly-implausible
reading) — but once `RequiredConsecutiveReadings` has already confirmed three consecutive
same-sign, non-decreasing readings, that protection has already been served by the persistence gate
itself. Capping the correction at that point no longer guards against anything; it only throttles
the fix's own remedy below the rate needed to keep up with confirmed reality, which is exactly the
defect this decision fixes. A correction sized to the full confirmed deviation is, if anything, a
*more* faithful reading of "bounded" than the old fixed quantum: the corrected residual is bounded
near zero after every firing, rather than growing without bound across a session as the endurance
run demonstrated.

**Interaction with the large-clock-step slow-convergence gap**
(`dev-tasks/2026-07-23-cycleframer-large-clock-step-slow-convergence.md`, previously
Captain-accepted as deferred): this fix substantially improves that scenario as a side effect,
without having been designed specifically for it. A confirmed one-off step now either lands within
`CorrectionSanityCeilingSamples` in a single event (if the step is smaller than the ceiling) or
slews over far fewer follow-on events than before (a 5-minute step: ~20 events of 180,000 samples
each, versus the ~39 days of 48-sample slews the old cap would have needed). Worth revisiting that
dev-task's status once this fix lands, but it is not re-litigated here.

**Alternative considered — no cap at all (rejected in favour of a generous ceiling).** Simpler, and
arguably still correct (by definition, if the persistence gate fired, the deviation is already
confirmed genuine, not a single anomalous reading), but removing the backstop entirely gives up a
cheap, deliberate defence against a truly pathological `IClock` reading (Decision 2's original
Risks-section intent) for no real benefit — a ceiling sized several orders of magnitude above any
plausible drift or clock-step scenario costs nothing in the common case while still catching
genuinely broken input.

### Decision 6: Widen diagnostic-instrumentation scope to `WasapiAudioSource.cs`/`CaptureManager.cs`, keeping it strictly Debug-level and non-behavioural

**Added post-implementation, from live evidence**
(`dev-tasks/2026-07-24-cycleframer-correction-not-converging-live-evidence.md`, following a fresh
live re-confirmation run at `qa/endurance/2026-07-24-1cebf81/report.md` that validated Decision
5's sizing formula fires exactly per spec — every one of 10 corrections matched its confirmed
deviation to the sample — yet the very next drift-check reading after each correction landed
within ±4% of the pre-correction value, all ten times, and the underlying deviation climbed
steadily across the whole 6h16m session largely independent of when corrections fired. The
correction is sized correctly but does not converge on real hardware.

**Root cause: not yet isolated.** Unlike Decisions 4 and 5, this is not a known fix — the
dev-task's own conclusion is that the proximate source of the measured "deviation" (genuine
capture-device clock-rate mismatch vs. `CycleFramer`'s own loop-scheduling delay vs. something
else) is not isolated, and re-tuning `DriftThresholdSamples`/`CorrectionSanityCeilingSamples`/
`RequiredConsecutiveReadings` again without isolating it first is explicitly discouraged (the
dev-task's own evidence already shows the sizing math itself is not where the problem lives).

**Chosen.** Add Debug-level, periodically-aggregated diagnostic timing instrumentation at three
pipeline stages — `WasapiAudioSource`'s `DataAvailable` firing cadence and resampler-drain-to-
enqueue latency, `CaptureManager`'s chunk-receive cadence and outer-channel write latency (the
single platform-agnostic point downstream of all three `IAudioSource` implementations, same
reasoning as Decision 1's choice of fix point), and `CycleFramer`'s own real wall-clock
inter-window elapsed time and chunk-dequeue-gap statistics — so a future live run has the data to
isolate where accumulated deviation actually originates, without needing a further code change
first.

**Why this widens `proposal.md`'s stated scope, and why that is the right call rather than a
silent scope creep.** The original `Impact: Code:` line confined this change to `CycleFramer.cs`
because that was sufficient for the *correction* itself (Decision 1). Diagnosing why a correctly-
sized correction fails to converge is a different question that the correction's own fix point
cannot answer alone — the dev-task's own Recommended Next Steps (and 6.3's identically-reasoned
deferral before it) are explicit that this exact instrumentation needs its own scope decision, not
silent inclusion. `proposal.md`'s Impact section has been amended in place (the Captain's explicit
choice, mirroring how Decisions 4/5 were folded into this same change rather than spun into a
separate one) to cover this.

**Why the instrumentation itself is safe to add without a full risk/mitigation write-up like
Decisions 1–5.** It is diagnostic-only: every new timestamp/aggregate is read-only with respect to
the audio pipeline's actual data flow (no chunk is ever delayed, dropped, or altered to produce a
measurement), logged at Debug level (already off by default in production per this codebase's
existing logging conventions — see `CycleFramer`'s existing per-cycle Debug lines), and
periodically aggregated (not per-event) specifically to keep log volume bounded over a multi-hour
session: `DataAvailable` fires at ~50 Hz, so per-event logging would produce tens of millions of
lines over a 6+ hour run — flushing a summary every 200 events (~4 s) keeps volume comparable to
`CycleFramer`'s existing once-per-15s Debug cadence. Deliberately keyed off `DateTime.UtcNow`
directly rather than the injectable `IClock` used by the correction logic itself — several
existing unit tests (`RateClock`/`StepClock`/`BouncingClock`) model drift purely as a function of
how many times `_clock.UtcNow` is read, so adding any further read there would silently corrupt
their arithmetic; the instrumentation needs real wall-clock timing regardless, so this is not a
compromise.

**Explicitly deferred, not done in this pass:** deciding a fix shape (tasks.md 8.3), which per the
dev-task must wait until this instrumentation has actually run live and 8.1/8.2's findings are in
hand — this decision adds the instrumentation only, not a fix.

### Decision 7: Widen scope to `Ft8Decoder.cs` for systematic `hashTableRejectCount` logging (tasks.md 8.4); add an isolated, confound-free unit test for the Decision-6-era self-inflicted-delay mechanism (tasks.md 8.7)

**Added post-implementation, from a dev-task addendum** (`dev-tasks/2026-07-24-cycleframer-correction-not-converging-live-evidence.md`,
"continued" addendum). Re-reading `qa/endurance/2026-07-24-29041f7/report.md`'s own artefacts
(no new live run) found that every discard correction observed live is followed, one cycle later,
by a real-inter-window-elapsed excess matching the correction's own size (89-114%, avg 98.5%,
n=8) — a candidate mechanism: the discard branch cannot reclaim real wall-clock time, only spend
more of it, because it waits for the discarded samples to actually arrive at the source's real
delivery rate before the next window can close. That addendum explicitly stopped short of calling
this confirmed (live-only confounds — the resync `LogInformation` call, a concurrent decode
kickoff — were not individually ruled out) and proposed two isolated, deterministic unit tests as
the next step, plus separately reiterated 8.4's still-open systematic-logging gap
(`hashTableRejectCount`, only ever sampled ad hoc via `/api/v1/status` polling, unlike decode
elapsed time which the 8.2 reconciliation confirmed is already logged every cycle and needed no
new instrumentation).

**Chosen — both items, same Captain-authorized Developer-session pass:**
- **8.7:** `RunAsync_DiscardCorrectionOnRateLimitedSource_CostsProportionalRealTime` and
  `RunAsync_ReplayCorrectionOnRateLimitedSource_DoesNotCostExtraRealTime` in `CycleFramerTests.cs`
  — a new `FeedSamplesAtRealRate` test helper reintroduces genuine per-chunk `Task.Delay` (absent
  from every other feed helper in that file by design, so those stay immune to real-timing
  flakiness) to make the source genuinely rate-limited, then asserts a *relative ratio* against
  the same run's own measured baseline chunk timing — never a hardcoded millisecond threshold, per
  `test-delay-debt.md`/Gate G10. **Result: both tests confirmed the mechanism, cleanly, across 5
  consecutive runs** — a materially stronger evidence class than the live-only correlational data,
  since the two confounds the addendum flagged are structurally absent from an isolated test. This
  does not touch `src/` (tests-only) and needed no `proposal.md` Impact amendment — the existing
  "new coverage using a fake/injectable `IClock`" Tests line already covers it.
- **8.4:** `Ft8Decoder.DecodeAsync` (`src/OpenWSFZ.Ft8/Ft8Decoder.cs`) now logs
  `hashTableRejectCount` at Information level once per cycle, immediately alongside the existing
  spec-mandated "Cycle {Time}: {Count} decode(s) found, elapsed={Elapsed} ms" line — same cadence,
  same level, so a future live run's raw log can reconstruct a session-long
  `hashTableRejectCount` trend the way it already can for decode elapsed time, without needing ad
  hoc endpoint polling mid-session. This **does** widen scope beyond `CycleFramer.cs` — same
  situation as Decision 6, same resolution: `proposal.md`'s Impact section is amended in place
  rather than silently expanded.

**Why `Ft8Decoder.cs` is the right place, not `CycleFramer.cs` or the daemon status endpoint.**
`GetHashTableRejectCount()` is only reachable through the decoder (`Ft8Decoder`/`IFt8NativeInterop`)
— `CycleFramer` has no access to it and no reason to acquire one just to log a value it doesn't
own. The existing `GET /api/v1/status` exposure (`hashTableRejectCountProvider` in
`WebApp`/`Program.cs`) remains unchanged and still useful for live, on-demand checks; this adds a
second, passive channel (the daemon log) for after-the-fact session analysis, which is what both
8.2's reconciliation gap and this Decision exist to close.

**Why this is safe to add without a full risk/mitigation write-up like Decisions 1-5.** Same
reasoning as Decision 6: read-only (the counter's own contract — `GetHashTableRejectCount`'s doc
comment already states reads have no side effects and do not reset it), Information level (matches
the existing elapsed-time line it sits beside, not a new noisier tier), and does not touch, gate,
or condition on the drift-correction logic itself — it is pure observability, added at the one
place upstream of that logic that already computes a per-cycle summary line.

### Decision 8: tasks.md 8.3's chosen fix shape — correct the deviation baseline for a correction's own real-time cost, rather than changing the correction architecture itself

**Chosen by the Captain, 2026-07-24 evening**, from three candidate shapes presented after 8.7's
mechanism confirmation (a live-confirmation run the same evening, `qa/endurance/2026-07-24-f57fa4d/report.md`,
reproduced the same non-convergence pattern a fourth time, at a rate — ≈35.3 samples/min —
consistent with `ce13e30`/`29041f7`'s independently-measured rates, reinforcing that one stable
mechanism is responsible):

1. **Fix the deviation-accounting math, keep the existing correction architecture.** *(Chosen.)*
2. Replace periodic large corrections with continuous small-quantum rate-tracking (estimate the
   device's real ppm error and nudge every window's sample target slightly, so no single
   correction is ever large enough to cost measurable real time).
3. Reopen Decision 1's scope boundary and correct the genuine device clock-rate error at the
   resampler/capture layer, upstream of `CycleFramer` entirely.

**Why (1), not (2) or (3):** smallest change, most directly targeted at exactly what 8.7 confirmed
(not a broader architectural response to the general problem class), and cheapest to falsify with
an isolated unit test before ever needing another live endurance run. (2) and (3) remain available
if (1) proves insufficient — recorded here so that fallback path doesn't need re-deriving from
scratch.

**The precise mechanism, traced to exact lines in `CycleFramer.RunAsync` (as of `f57fa4d`):**
`nominalCycleStart` — the purely-arithmetic reference deviation is measured against — is advanced
by a flat `CycleDurationSecs` (15.000 s) every window (`nominalCycleStart =
nominalCycleStart.AddSeconds(CycleDurationSecs)`), with no exception for the window immediately
following a correction. But that window's *actual* real-world fill time is **not** 15.000 s by
construction: a discard (`pendingSkipSamples > 0`) genuinely must wait to receive
`correction` extra raw samples from the real, rate-limited capture source before it can even start
accumulating; a replay pre-fills `filled = replay` samples from the already-captured previous
window's tail, so it needs `replay` *fewer* new raw samples and completes correspondingly sooner.
Concretely, using tonight's correction #3 (18:39:45.453Z, 2020-sample discard): the window that
consumes those 2020 samples takes ~168 ms *longer* than 15.000 s to fill in real wall-clock time —
but `nominalCycleStart`'s advance for that window is still a flat 15.000 s. So when that window
closes, `deviation = _clock.UtcNow − nominalCycleStart` reads the ~168 ms the correction itself
cost as fresh, apparently-genuine drift — reproducing almost exactly the size of the correction
that supposedly just fixed it. This is precisely what 8.7's isolated tests measured (discard ≈
1.10-1.60x an ordinary window's real time, replay ≈ 0.55-0.95x) and precisely what every live
endurance run's "next reading" data has shown since `1cebf81`.

**The fix:** at the moment a correction fires, record a one-shot pending time adjustment —
`pendingNominalAdjustSeconds = correction / (double)SampleRate` — representing the genuine
extra-or-reduced real time the *next* window (the one that actually consumes/reduces raw samples
because of this correction) will take to fill. Apply that adjustment to `nominalCycleStart`'s
*next* advance only (`nominalCycleStart.AddSeconds(CycleDurationSecs + pendingNominalAdjustSeconds)`
instead of the flat `CycleDurationSecs`), then clear it back to zero so it does not persist beyond
that one window. This makes the deviation baseline correctly anticipate the one window whose
real-time cost is known in advance (because we ourselves just imposed it), so the following
deviation check measures against a fair expectation instead of re-billing the correction's own
necessary cost as new drift. `cycleStart` (the reported, decoder-facing timestamp) is unaffected —
this only changes the internal reference `nominalCycleStart` is compared against, not what gets
reported or what audio content lands in which window.

**Acceptance criterion (tasks.md 9.3):** reuse 8.7's `FeedSamplesAtRealRate` rate-limited-source
test harness. After a correction fires under a genuinely rate-limited source (both discard and
replay directions), assert that the deviation reading on the window *immediately following* the
corrected one lands near the noise floor — not near the correction's own magnitude. This
operationalizes, as a fast isolated unit test, the exact property every live endurance run so far
has checked for and found failing (`1cebf81`'s report first named it: "does the post-correction
reading actually drop near the noise floor, or re-establish at the same magnitude").

**Scope:** `src/OpenWSFZ.Ft8/CycleFramer.cs` only — no change to `Ft8Decoder.cs`,
`WasapiAudioSource.cs`, or `CaptureManager.cs`. Per HK-011, implementation is a separate
Developer-session concern; this Decision documents the *what* and *why* so that session does not
need to re-derive the mechanism from the live-run reports.

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

### Decision 9: 9.5's failure is a defect *in* Decision 8's implementation, not a refutation of it — fix the `nominalCycleStart` reset; the escalation to fallback shapes 2/3 is withdrawn

**Decided by the Architect, 2026-07-25**, after re-analysing `qa/endurance/2026-07-25-40m-band-9.5-fail/`'s
own raw artefacts (`artefacts/20260724_live_run_2227/corrections_table.csv` and the two sub-session
daemon logs). The 9.5 report recommended escalating to Decision 8's fallback (2) or (3). **That
recommendation is not adopted.** The report's data is sound and its instrumentation is sound; its
central inference is wrong. Decision 1 stands, Decision 8 stands, and no new correction architecture
is needed.

**Finding 1 — the post-correction reading reproduces the *previous* correction, not its own.** The
9.5 report scored each correction against its own magnitude. Regressing each post-correction
deviation reading against the *preceding* correction instead:

| Test | Result |
|---|---|
| corr(next_reading, **own** correction) | 0.764 |
| corr(next_reading, **previous** correction) | **0.9931** |
| best-fit slope vs. previous correction | **0.977** |
| sign(next_reading) == sign(previous correction) | **135 / 135** |

This is an identity, not a trend. It also means **Decision 8 half-worked**: attempt #3's signature
was `next_reading ≈ own correction` (`1cebf81`'s "within ±4% of its pre-correction value"), and 9.1
changed it to `next_reading ≈ previous correction`. The one-shot adjustment *does* cancel a
correction's own real-time cost exactly as Decision 8 predicted; it is then re-injected one step
later. 9.3/9.5's acceptance metric — ratio to *own* magnitude — cannot see that difference, because
in steady state `c_prev ≈ c_own`, so a genuine half-fix scores identically to no fix at all.

**Finding 2 — root cause: `nominalCycleStart = cycleStart` discards the divergence 9.1 creates.**
The two clocks are advanced *unequally* once 9.1 exists:

```
cycleStart        += CycleDurationSecs                                // unchanged
nominalCycleStart += CycleDurationSecs + pendingNominalAdjustSeconds  // 9.1
```

So for every window following a correction, `nominalCycleStart` sits ahead of `cycleStart` by
exactly that correction's adjustment. The correction branch then re-anchors with
`nominalCycleStart = cycleStart`, throwing that divergence away. The total forward shift across a
correction is therefore `(2·c_now − c_prev)/SampleRate`, where the derivation requires
`2·c_now/SampleRate` — `c_now` to zero the current deviation, `c_now` again for the next window's
discard cost. The shortfall is precisely `c_prev`, which is what Finding 1 measures.

`nominalCycleStart = cycleStart` was **correct before Decision 8** — with no one-shot adjustment the
two clocks never diverged, so re-anchoring and shifting were the same operation. Decision 8 added a
mechanism that silently invalidated a pre-existing line, and the invariant was never re-derived. The
comment still asserting the old, now-false invariant ("Reset to match cycleStart whenever a
correction fires") is part of the defect and must be corrected with it.

**Finding 3 — 97% of the measured "drift" was self-inflicted.** Energy balance over the 9.5 session:

| Quantity | Value |
|---|---|
| Measured excess real time over nominal (2,836 windows × 15.0243 s avg) | 68.9 s |
| Signed sum of all 136 corrections | **66.8 s** |
| Unexplained residual | **2.1 s** |
| Predicted genuine drift at −42.41 ppm over 42,609 s | **1.81 s** |

Splitting the pipeline-timing instrumentation by whether a correction preceded the window confirms
it independently: windows with **no** preceding correction (n=2,554) averaged **15.0015 s**; windows
**immediately after** a correction (n=127) averaged **15.5047 s**, and subtracting that correction's
own cost returns **14.9854 s**. The entire excess in the post-correction population is the
correction's own discard cost, quantitatively. The genuine defect is ~4 s over 11.8 h; the loop
generated **67 s** of self-inflicted correction chasing it.

**This inverts H₀-3.** The 9.5 report reads "avg 15.0243 s, flat, no correlation" as *refuting*
pipeline timing as the mechanism. But deviation is the *integral* of that bias: a constant offset
with no trend is exactly what an accumulating drift source looks like. The report searched for a
trend, correctly found none, and drew the wrong inference from a summary statistic that was itself
97% correction cost. Future rounds must test the pipeline-timing figure against nominal, not only
for a trend.

**Finding 4 — Section 7's DT offset is this same defect, not a separate thread.** `cycleStart` is
shifted forward by every correction cumulatively and is never re-aligned to the UTC 15-second grid
after startup, so a runaway loop produces a *growing* label offset. Cumulative `cycleStart` shift in
the 9.5 run reached **+0.47 s at t+32 min and +0.63 s at t+34 min**; `f57fa4d`'s DT spot-check, at
t+39 min of a comparable run, found **+0.5 to +0.6 s**. This is a cross-run comparison, so
plausibility rather than proof — but it is sharply falsifiable against the preserved WAV archive
with no new live time: the offset should track the cumulative correction sum, not sit flat.

**Finding 5 — a multi-correction unit test already caught this and its tolerance was relaxed
instead.** `tasks.md` 9.2 records that
`RunAsync_SustainedConstantRateDrift_ResidualStaysBoundedAcrossManyCorrections` — the one existing
test that fires *many* corrections in sequence — needed its tolerance widened under 9.1, its
residual settling "~80 samples higher than before." That regression was rationalised as a benign new
plateau. It is the `c_prev` re-injection, visible in the test suite before the overnight run was
ever started. Restoring that tolerance is a falsifiable acceptance criterion for the fix below.

**The fix:** shift the arithmetic reference by the correction actually applied, rather than
re-anchoring it to `cycleStart`:

```csharp
// was: nominalCycleStart = cycleStart;
nominalCycleStart = nominalCycleStart.AddSeconds(correction / (double)SampleRate);
```

Shifting by `correction` (not by `deviationSeconds`) is deliberate: in the ordinary unclamped case
the two are equal and the current deviation is zeroed exactly, while if the
`CorrectionSanityCeilingSamples` backstop ever binds, the residual `(deviation − correction)`
correctly carries forward to be chipped away on subsequent cycles — preserving Decision 5's
intended slew-not-step behaviour. `cycleStart` keeps its own separate `+correction/SampleRate`
advance; the point of the fix is precisely that the two quantities are *not* the same thing and must
stop being conflated.

**Scope:** `src/OpenWSFZ.Ft8/CycleFramer.cs` only, one statement plus the stale comment at its
declaration. Per HK-011 this is Developer-session territory with the Captain's pre-push sign-off.

- **[Trade-off] Four failed rounds argue for a more defensive response than a one-line fix.**
  → Considered and rejected. Fallback (2) (continuous rate-tracking) would have *worked* while
  leaving this defect latent in the code, because it removes discrete corrections and so sidesteps
  the loop rather than fixing it — buying a new architecture and another overnight round to conceal
  a one-line bug. The diagnosis here is quantitative and closed (r=0.9931, energy balance to 0.3 s),
  which is a materially different evidentiary position from rounds 1–4.
- **[Risk] The correction-free per-cycle bias measures ~101 ppm, against D-001's 42.41 ppm
  hardware figure.** 95% CI [46, 156] ppm — wide, with its lower bound sitting on the D-001
  prediction, so "consistent with, possibly 2–3× larger." `DriftThresholdSamples` and
  `RequiredConsecutiveReadings` were derived from 7.6 samples/cycle; at ~18 samples/cycle the
  correction simply fires ~2.4× more often, which is not itself a defect. → Mitigation: re-derive
  and record the constants explicitly (tasks.md 10.5) rather than leaving the discrepancy
  undocumented.
- **[Risk] Every discard permanently destroys captured audio.** At the runaway scale this was 67 s
  of a 11.8 h session; at the corrected scale it is bounded by the genuine drift rate (~4 s), which
  is the irreducible cost of correcting a real clock-rate error. → Accepted, unchanged from
  Decision 2.

### Decision 9 Addendum: `RunAsync_SustainedConstantRateDrift_…` is rebuilt on `SampleCountClock` with a no-growth assertion; Finding 5's "restore the 220-sample tolerance" acceptance criterion is **withdrawn**

**Decided by the Architect, 2026-07-25**, resolving the escalation in
`qa/cycleframer-code-review/2026-07-25-decision9-review-and-rateclock-escalation.md`. QA confirmed
10.1–10.3 correct, confirmed all `SampleCountClock`-based tests pass, and routed one blocked item —
`RunAsync_SustainedConstantRateDrift_ResidualStaysBoundedAcrossManyCorrections`, which fails at 220
and whose residual climbs linearly without bound out to windowCount=60 — upward rather than
deciding it in a Developer or QA session. That was correct.

**Ruling: option (1) — rebuild the test on `SampleCountClock`, do not retire it — *and* replace its
absolute-tolerance assertion with a no-growth assertion. Finding 5's tolerance-restore criterion is
withdrawn as unachievable in principle, not merely unmet.**

**Finding 5 committed a category error, and it is mine.** That test is **Decision 5's** regression
guard. Its own header comment says so: it exists because the old fixed 48-sample cap "only ever
chipped away a small fraction of each confirmed deviation, so residual drift grew essentially
unbounded, correction after correction," and because "unit tests never caught it — the earlier tests
only exercise a handful of cycles around a single correction event." It predates Decisions 8 and 9
entirely. Finding 5 conscripted it as a falsification criterion for a mechanism it was never built
to observe, on the strength of a real observation (the 9.1 tolerance widening *was* the one-shot
adjustment showing up) plus an invalid inference (that 10.1 would therefore restore the old bound).

**This was foreseeable from the test file itself.** The comment block added at 9.3 already records
the governing fact: `RateClock`/`StepClock`/`BouncingClock` are "by design, decoupled from anything
happening during the window they measure (a fixed formula of read-count alone) and cannot exercise
this fix's mechanism at all — a clock that never reflects a correction's own real-time cost can
never show that cost re-surfacing as fresh deviation, fix or no fix." It even records the
hand-derivation that applying the fix under such a clock makes the post-correction reading *larger*.
Decision 9 was written without reconciling Finding 5 against that paragraph. QA's diagnosis is
independently correct and needed no correction; the defect was upstream of it.

**Why the 220-sample tolerance cannot be restored under any correct implementation.** Not a
constant-picking problem:

- Under `RateClock`, Decision 8's one-shot adjustment has nothing in the clock's reading to
  reconcile against, so it is pure un-cancelled bias that compounds per correction — unbounded, as
  QA measured. The pre-10.1 `nominalCycleStart = cycleStart` reset was acting as a periodic release
  valve for that synthetic mismatch. **Boundedness under `RateClock` was a property of the bug.**
  Preserving it would mean preserving the bug Finding 2 exists to remove.
- Under `SampleCountClock`, boundedness is real but the *scale* changes. The 220 figure derives from
  60 samples/cycle × 3 checks + margin. A genuinely rate-limited feed quantises a correction's
  real-time cost to the chunk size, so the mechanism is only observable when a correction spans
  several chunks — which forces a much larger per-cycle error, and therefore a residual bound in the
  tens of thousands of samples. 220 is unreachable in the model where the property is even
  meaningful.

**The assertion is reformulated, and this is the substantive part of the ruling.** The absolute
constant is what made this test brittle across every round (220 → 305 → unbounded). The property
Decision 5 actually cares about is *bounded vs. linearly growing*, which is a trend, not a
magnitude. Assert instead:

1. **No growth in residual** — residual over the final third of windows must not exceed the first
   third by more than a small factor. This is scale-free and survives any future change to the
   device-error constant or the clock model.
2. **Correction magnitude does not escalate** — successive corrections must trend toward the genuine
   drift rate rather than growing. This is the direct unit-test analogue of the live failure
   signature the 9.5 session recorded (correction magnitude growing ~8× hour-over-hour with no
   plateau), and no existing test asserts it.

(2) is worth more than the original test ever was: it encodes the exact session-scale
non-convergence that five live rounds detected and the suite never did.

**Feasibility, measured not assumed.** The existing 10.4 test (7 windows, 2 corrections,
`SampleCountClock` + genuinely rate-limited feed) runs in **5 s** — ~0.7 s per window, dominated by
40 chunks/window at the OS timer's real granularity rather than the nominal 10 ms. A naive port to
24 windows would cost ~17 s and exceed the 20 s `CancellationTokenSource` budget the existing tests
use. It becomes affordable by trading chunk count for chunk size: ~10 chunks/window over ~18 windows
(≈6 corrections) lands near **3–4 s**, at the price of a more exaggerated per-cycle error so that a
correction still spans several chunks. Exact constants are the Developer session's to derive and
record, same convention as 10.5 — the constraint to respect is `3 × per-cycle-error ≳ 4 × chunk
size`, and Gate G10 applies to whatever delays result.

**Why not option (2), retire it.** 10.4's new test covers two corrections, which is enough to
falsify reset-conflation but not enough to catch a slow divergence over a dozen firings — the exact
gap that let Decision 5's original fixed-cap defect reach a 7h54m live run undetected. Retiring
would leave Decision 5 with single- and double-correction coverage only, and would remove the one
test positioned to catch escalating-correction non-convergence before an overnight round does.

- **[Trade-off] This makes a slow test slower and coarser.** → Accepted. The alternative is a fast
  test asserting a precise number about a mechanism its clock cannot represent, which is what the
  last three rounds have been debugging. A 3–4 s test that measures the right property beats a
  0.1 s test that measures an artefact.
- **[Risk] A no-growth assertion over ~6 corrections may be statistically weak — 6 points is few,
  and a slow divergence could hide inside the tolerance.** → Mitigation: state the detectable
  growth rate explicitly in the test comment rather than implying the test proves boundedness in
  general, and treat the live gate (10.8), now backed by the alignment-replay study's recall bound,
  as the real session-scale check. This test's job is to catch gross divergence early and cheaply.
- **[Risk] The exaggerated device-error constant drifts further from the measured ~42–101 ppm.**
  → Accepted, unchanged from the existing tests' own rationale: these constants are chosen to reach
  a given number of correction events in a manageable window, not to model the real rate. 10.5
  records the real-rate derivation separately.

**Required `tasks.md` §10 changes** (Developer-session work per HK-011):

- **10.4** — strike the "restore the 220-sample tolerance" sub-item; it is withdrawn above. The new
  multi-correction `SampleCountClock` test already written and verified stands as complete.
- **New item (10.4a)** — rebuild `RunAsync_SustainedConstantRateDrift_ResidualStaysBoundedAcrossManyCorrections`
  on `SampleCountClock` + `FeedSamplesAtRealRateTrackingDelivery`, with the two assertions above
  replacing the absolute tolerance, and derive/record the constants per the envelope given here.
- **10.2** — the `RateClock`/`StepClock`/`BouncingClock` limitation is now a decided design
  constraint rather than a test-file aside. Note at their declarations that they must not be used
  for any test exercising the deviation-accounting mechanism.

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
