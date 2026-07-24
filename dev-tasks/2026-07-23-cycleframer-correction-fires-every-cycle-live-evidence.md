# Live-run finding: `fix-cycle-boundary-clock-drift` correction engages every cycle in production, driven by pipeline latency — not the ~42 ppm device clock-rate error it was built to fix

**Status:** Implemented (2026-07-24) — see `openspec/changes/fix-cycle-boundary-clock-drift/tasks.md`
section 6 and `design.md` Decision 4 for what was built: the correction is now persistence-gated
(3 consecutive same-sign, non-decreasing readings required before firing), `MaxCorrectionSamples`
raised 32→48, and a new unit test (`RunAsync_RecurringNonMonotonicDeviation_NeverFiresCorrection`)
replays this file's own logged second-session sample sequence verbatim and asserts zero
corrections fire. `python3 tools/pre_merge_check.py` passes clean against the revised code
(298/298 `OpenWSFZ.Ft8.Tests`, 57/57 openspec validate). Stage-by-stage WASAPI/Channel
instrumentation (Recommended Next Step 1) was deferred as a scope expansion beyond this change's
approved `Impact: CycleFramer.cs only` — flagged as a separate follow-up, not done here. **Still
open before the merge hold can lift:** Recommended Next Step 3 — re-running this same live setup
against the revised build to confirm the correction actually goes quiet in production, which
needs live audio hardware/session time and was explicitly the point of this whole exercise (a
static/unit-level fix cannot itself confirm that). See also the addendum on
`dev-tasks/2026-07-23-cycleframer-large-clock-step-slow-convergence.md`: this fix's persistence
gate measurably (~2x) worsens that other deferred item's slow-convergence gap — Captain should
weigh that before signing off on merge, not just this file's original finding.

---

**Original status (superseded by the above):** BLOCKING. Surfaced during the first live
pre-merge validation run, before sign-off. The planned OpenWSFZ-vs-WSJT-X live `delta_dt`
comparison was started and then paused by the Captain specifically because of this finding,
before an official comparison-window start marker was even set. Recommend holding merge on
`fix-cycle-boundary-clock-drift` until this is resolved.

## Context

- Change under review: `openspec/changes/fix-cycle-boundary-clock-drift/` (open PR #108,
  branch `docs/propose-fix-cycle-boundary-clock-drift`; `src/OpenWSFZ.Ft8/CycleFramer.cs` diff
  still uncommitted in the working tree at review time, on top of `ce13e30`).
  QA review of the diff itself (correctness, existing-test inertness, `pre_merge_check.py`)
  passed cleanly — see that review's findings for the design/spec-level analysis. This dev-task
  is about a *behavioural* gap the static review could not have caught: how the mechanism
  actually performs against a real capture pipeline under live conditions.
- Live run setup: `dotnet run --project src/OpenWSFZ.Daemon` (Debug config, not the Release
  self-contained publish `pre_merge_check.py` validated — see Open Questions), same physical
  capture device Phase 3 measured (`'Microphone (2- USB Audio CODEC )'`, WASAPI, 48000 Hz →
  12000 Hz resampled), WSJT-X running in parallel, both `ALL.TXT`-equivalent logs freshly wiped.
- Full daemon log: `logs/openswfz-20260723T211540Z.log`. Log level: Information (captures the
  new resync line from task 1.2/2.4).

## Evidence

### 1. The correction fires on every single 15 s cycle, always at the cap, from the very first cycle

First pipeline start (23:19:01–23:20:15, before an operator-initiated stop):

```
23:19:15.158  accumulated deviation = 1900.1 samples (158.35 ms); applying 32 sample correction
23:19:30.181  accumulated deviation = 2144.8 samples (178.73 ms); applying 32 sample correction
23:19:45.198  accumulated deviation = 2314.3 samples (192.86 ms); applying 32 sample correction
23:20:00.175  accumulated deviation = 2012.8 samples (167.74 ms); applying 32 sample correction
23:20:15.206  accumulated deviation = 2353.4 samples (196.12 ms); applying 32 sample correction
```

Second pipeline start, same device, five minutes later (23:25:28–23:38:45, ~53 cycles logged):

```
23:25:30.096  deviation = 1162.5 samples ( 96.87 ms) -> capped correction
23:25:45.070  deviation =  814.1 samples ( 67.84 ms) -> capped correction
23:26:00.115  deviation = 1326.1 samples (110.51 ms) -> capped correction
23:26:15.106  deviation = 1181.4 samples ( 98.45 ms) -> capped correction
23:26:30.075  deviation =  772.2 samples ( 64.35 ms) -> capped correction
23:26:45.059  deviation =  547.7 samples ( 45.64 ms) -> capped correction
23:27:00.100  deviation = 1016.1 samples ( 84.68 ms) -> capped correction
... (pattern continues every single cycle through 23:38:45, the end of the captured log)
```

Every reading is positive (the "lengthen/discard" branch) — never once negative — and the
magnitude bounces between roughly 500 and 2400 samples (40–200 ms) without shrinking, without
converging, and without diverging. `DriftThresholdSamples = 24` (2.0 ms) and
`MaxCorrectionSamples = 32` (2.7 ms) were derived from the ~42 ppm figure Phase 3 measured
(`qa/rr-study/results/2026-07-23-d001-live-path-root-cause/phase3_clockrate_results_usbcodec.json`),
which predicts ~7.6 samples (0.6 ms) of drift *per cycle* — a correction should fire roughly once
every 3 cycles and then go quiet. Instead it never goes quiet.

### 2. The real inter-window cadence is fine — the discrepancy is specific to what the drift-check computes

Measured directly from consecutive `"Window emitted"` log timestamps (independent of anything
`CycleFramer`'s own arithmetic computes):

```
gap=15023ms (+23ms)   gap=15017ms (+17ms)   gap=14977ms (-23ms)   gap=15031ms (+31ms)
gap=14974ms (-26ms)   gap=15045ms (+45ms)   gap=14991ms ( -9ms)   gap=14968ms (-32ms)
gap=14984ms (-16ms)   gap=15042ms (+42ms)   gap=14993ms ( -7ms)   gap=15035ms (+35ms)
... (58 consecutive emissions, full session)
```

True cadence is 15.000 s ± roughly 20–50 ms, zero-mean, no trend — normal-looking scheduler
jitter at a *plausible* scale. This is not the 40–200 ms, one-directional pattern the correction
log reports. Whatever the correction is reacting to is not "how far apart windows actually
close in real time."

### 3. The arithmetic itself is self-consistent (this is not a coding bug in the bookkeeping)

Hand-traced through two consecutive corrections in sequence 2 above:

- After window 0 (23:25:30.096 real time), `nominalCycleStart` was `21:25:30.000` (pure
  arithmetic, no correction applied yet). `deviation = 21:25:30.096 − 21:25:30.000 = 96 ms` ≈
  logged 96.87 ms. ✓.  Capped correction `+32` applied → `cycleStart` re-anchored to
  `21:25:30.002667` (only 2.667 ms closer to true time, not 96 ms).
- For window 1 (23:25:45.070 real time), `nominalCycleStart` advances from that corrected value
  by 15 s → `21:25:45.002667`. `deviation = 21:25:45.070 − 21:25:45.002667 ≈ 67.3 ms` ≈ logged
  67.84 ms. ✓.

The math is doing exactly what the design specifies. The problem is what it's measuring: because
the correction only ever closes the capped 2.7 ms sliver of whatever gap is read, and a
similarly large gap reappears on the *next* check regardless, the residual never approaches
zero and never blows up — it just recurs. That is the signature of a **roughly-constant,
per-cycle recurring latency**, not of a slowly accumulating device clock-rate error (which
Phase 3 measured as genuine, but roughly 100–300× smaller than what's showing up here).

### 4. Likely proximate cause (not yet isolated)

`WasapiAudioSource.cs`: `DataAvailable` fires on the WASAPI capture thread at ~50 Hz, drains into
2048-sample chunks through a `Channel<float[]>`; `CycleFramer.RunAsync`'s `await foreach`
consumes that channel on the thread pool, which is also running the native FT8 decode
(~500–600 ms of P/Invoke work per cycle, confirmed in the same log via
`"... decode(s) found, elapsed=..."` lines) every cycle. Any of WASAPI callback scheduling,
`Channel<float[]>` backpressure, or thread-pool contention with the concurrent decode work could
produce a recurring tens-to-~200 ms lag between "audio truly arrived" and "`CycleFramer`'s code
got scheduled to read `_clock.UtcNow`." This has **not** been isolated by direct instrumentation
— only inferred from the log evidence above — and doing so is exactly what's proposed in
Recommended Next Steps below.

### 5. Root divergence from the design's own calibration

Phase 3's device measurement (`phase3_clockrate_direct.py`) read the device's own capture
callback timestamps directly via Python `sounddevice`, entirely bypassing WASAPI, the resampler,
the `Channel<float[]>`, and `CycleFramer` — i.e., it measured the crystal's rate cleanly, but
never went through the pipeline this fix actually has to operate inside. `DriftThresholdSamples`
and `MaxCorrectionSamples` are correctly derived from that clean measurement, but that
measurement's noise floor is not the real deployed pipeline's noise floor.

## Why this matters

- The design's core stated goal — "the correction should be a no-op until genuine, sustained
  drift is detected... leave short/typical sessions' behaviour unchanged" — is not holding from
  cycle 1 in a real deployment. This isn't a rare edge case; it's the steady state observed on
  the actual hardware/pipeline this fix targets.
- Every emitted window is now getting a 32-sample (2.7 ms) discard, continuously, for the life
  of any session on this configuration — a materially more invasive and more frequent
  perturbation to decode input than what was reviewed against the unit tests (`RateClock`/
  `StepClock`), which modeled rare, isolated correction events, not continuous engagement.
  Nothing observed suggests this is currently *harmful* to decode output (decodes are
  proceeding normally, 15–24 per cycle throughout), but it is a materially different runtime
  behaviour than what was designed, tested, and reviewed.
- It directly contaminates the planned validation: a flattened `delta_dt` slope in a live
  WSJT-X comparison run right now would not cleanly confirm or refute the ~42 ppm hypothesis,
  because the mechanism as deployed is dominated by an unisolated pipeline-latency effect on
  top of (or possibly instead of) the intended one.

## Confirmed vs. still open

**Confirmed:**
- The `nominalCycleStart`/`cycleStart` bookkeeping is arithmetically self-consistent — not a
  coding bug in the mechanics themselves.
- Real inter-window wall-clock cadence stays close to nominal 15.000 s throughout the session;
  the anomaly is specific to the drift-check's own reading.
- The pattern reproduces identically across two independent pipeline starts (23:19–23:20 and
  23:25–23:38) on the same physical device, five minutes apart.

**Not yet isolated:**
- The exact proximate cause among WASAPI callback jitter, `Channel<float[]>` backpressure,
  thread-pool contention with concurrent native decode, or something else in the resampler stage.
- Whether this pipeline-latency component is itself stable/bounded over many hours, or could
  grow with session length (e.g., if it's related to any form of accumulating backpressure) —
  only a longer run or targeted instrumentation would show this.
- **Build-configuration caveat:** this run used `dotnet run` (Debug configuration), not the
  Release self-contained publish `pre_merge_check.py` validated. Worth re-confirming the same
  pattern under Release before ruling out Debug-JIT/managed-overhead as a partial contributor —
  though the observed 40–200 ms magnitude is far larger than typical Debug-vs-Release overhead
  would plausibly explain on its own.

## Recommended next steps

1. Instrument each pipeline stage with timestamps (WASAPI `DataAvailable` firing time, the
   `Channel<float[]>` enqueue/dequeue instants, `CycleFramer`'s own processing instant) to
   isolate where the recurring ~50–200 ms lag actually originates, rather than retuning any
   constant blindly against a still-unexplained effect.
2. Once isolated, decide on a fix shape — likely candidates: (a) require the deviation reading
   to persist or grow across several consecutive checks (same sign, non-decreasing) before
   acting, rather than reacting to any single reading, so ordinary recurring pipeline latency
   can't masquerade as accumulating drift; and/or (b) re-derive
   `DriftThresholdSamples`/`MaxCorrectionSamples` from this pipeline's own measured noise floor
   rather than Phase 3's bypass measurement.
3. Re-run this same live setup (same device, same log-capture technique used here) against the
   revised implementation to confirm the correction goes quiet during ordinary operation and
   only engages for genuine, sustained, multi-cycle drift.
4. Only then resume the OpenWSFZ-vs-WSJT-X live `delta_dt` comparison as the intended validation
   of actual decode-recall benefit (the original purpose of today's session).

## Disposition of the pending PR / merge

Found via live testing before merge, per the HK-011 pre-push gate. Recommend **holding**
`fix-cycle-boundary-clock-drift` out of merge until at least steps 1–2 above are addressed — the
implementation, as reviewed and unit-tested, does not behave as specified once run against a
real capture pipeline, even though the unit-level logic and the static review both check out
cleanly against the design document's own model.

## Cross-reference

Sharpens and supersedes the priority (not the content) of
`dev-tasks/2026-07-23-cycleframer-large-clock-step-slow-convergence.md`: that item flagged a
*hypothetical* large one-off clock step as a slow-convergence/log-spam risk, deferred as
low-priority/unlikely. This finding is the empirically-observed, continuous, high-frequency
version of the same underlying gap — the mechanism cannot currently distinguish an anomalous or
non-drift-related reading from genuine device drift — except it is not rare at all in practice;
it is the steady state on real hardware. That earlier item's proposed mitigation (detect an
implausible reading and skip-with-warning rather than always acting) is very likely relevant to
whatever fix comes out of this investigation too, and the two should probably be resolved
together.

## Appendix: reproduction

- Log: `logs/openswfz-20260723T211540Z.log` (this session).
- Gap analysis reproduced via:
  `grep "Window emitted" logs/openswfz-20260723T211540Z.log | awk '{print $1" "$2}' | python3 -c "..."`
  (parses consecutive timestamps, computes deltas — see this dev-task's originating conversation
  for the exact one-liner).
- Git state at time of this run: `HEAD = ce13e3080ad061fd66c8c059c612e3793d9c2091`, with the
  `fix-cycle-boundary-clock-drift` implementation (`CycleFramer.cs`,
  `CycleFramerTests.cs`, `tasks.md`) uncommitted in the working tree on top of that commit.
