## Context

`QsoAnswererService` and `QsoCallerService` both run a per-cycle decode-batch handler that, among
other things, consumes operator-armed "manual engage" state (a CQ click → `AnswerCqAsync` pending
target; a jump-in double-click → `EngageAtAsync`; a caller-side responder double-click →
`SelectResponderAsync`). D-CALLER-013 (2026-06-27) added a `MaxLateStartSeconds` guard to
`QsoAnswererService`'s two consumption paths (jump-in, pending-target) that defers firing to the
next matching-phase window (~30 s later) if the click landed more than the threshold into the
current window. D-CALLER-016 (2026-07-14, PR #72) retuned that threshold from 1.5 s to 2.0 s based
on production KeyDown/device-open jitter analysis.

The same day's field session (`logs/openswfz-20260714T171230Z.log`) shows the retune did not solve
the underlying problem: 10/14 manual engages were still deferred. The physical ceiling for a
full-length 12.64 s transmission inside a 15 s window is 2.36 s — real decode-to-click latency
(operator reaction time + UI dispatch + `KeyDownAsync` device-open jitter) routinely exceeds that,
so *any* threshold below ~2.4 s produces frequent deferrals, and thresholds above it risk overrun.
The Captain has specified WSJT-X's own model as authoritative: engage unconditionally if the phase
is correct; let the transmission run only as long as the window allows; a click that's "too late"
degrades gracefully (a short/truncated transmission, likely undecoded) rather than being silently
deferred a full cycle.

Investigation during this design also found the dev-task's assumption that `QsoCallerService` has
"mirror-image" late-start logic was incorrect: `HandleWaitAnswerAsync`'s pending-responder
consumption path (lines ~601–653) has no lateness guard at all — it already fires unconditionally
once the phase check passes. That half of this change is therefore a formalisation-only spec
addition on the caller side, not a code change.

## Goals / Non-Goals

**Goals:**
- A manual engage (jump-in or pending-target, `QsoAnswererService`) fires in the same window it was
  armed for whenever the phase check passes, with no lateness-based rejection.
- Any `TransmitAsync` call (either service, any trigger — manual engage, auto-answer, retry,
  report/RR73/73 continuation) truncates its audio to fit the remaining time in the current 15 s
  window, so PTT is never held into the next window.
- Formalise (via spec, not code) that `QsoCallerService`'s pending-responder path already has the
  correct no-rejection behaviour, closing the gap between implementation and spec.
- Preserve all other retry/watchdog/ADIF/phase-check semantics unchanged.

**Non-Goals:**
- No new `IPttController` capability or interface change. Truncation is implemented purely by
  shrinking the pre-synthesised sample buffer before `LoadAudio`; `KeyDownAsync`/`KeyUpAsync`
  contracts are untouched.
- No hard lower floor near the end of a window (e.g. refusing to engage with <0.5 s remaining) —
  per the Captain's decision, the model is unconditional engagement whenever phase is correct.
- No distinct retry/ADIF treatment for a truncated transmission — it counts exactly like a full one
  (Captain's decision).
- No UI indication that an upcoming transmission will be truncated — candidate follow-up, out of
  scope here.
- No change to the phase check itself (`nextCycleIsAPhase != pendingIsAPhase` / `jumpIsAPhase`) —
  it is already correct and must be preserved byte-for-byte in behaviour.

## Decisions

### D1 — Truncate the sample buffer, not the `IPttController` contract

**Chosen:** at the top of `TransmitAsync` (both services), compute
`remaining = windowBoundary − _timeProvider.GetUtcNow()` (reusing the existing `RoundDownTo15s`
helper already present in both classes: `windowBoundary = RoundDownTo15s(now) + 15s`). Convert
`remaining` to a sample count (`48000 Hz × remaining.TotalSeconds`, clamped to
`[0, samples.Length]`) and slice the synthesised buffer to that length before calling
`_pttController.LoadAudio(...)`. If the computed length is 0 (window already closed by the time
`TransmitAsync` runs — a defensive edge case), skip `LoadAudio`/`KeyDownAsync` entirely, log a
Debug line, and return without transmitting, since keying zero samples still asserts PTT on
CAT/serial controllers for nothing.

**Alternatives considered:**
- *Add a deadline `CancellationToken` or timeout parameter to `KeyDownAsync`.* Rejected: would
  require touching the `IPttController` interface and all three implementations
  (`AudioOnlyPttController`, `CatPttController`, `SerialRtsDtrPttController`) plus every test double,
  for no behavioural gain over truncating the buffer up front — WASAPI playback duration is already
  determined entirely by buffer length, so a shorter buffer produces exactly the same physical
  keying window with far less surface area changed.
- *Cancel the linked `CancellationTokenSource` via a `Task.Delay` racing the remaining window time.*
  Rejected: `KeyDownAsync`'s cancellation path is documented (D-007) to sometimes return normally
  without throwing depending on controller implementation, which would make the "did we actually
  truncate" signal implementation-dependent and harder to unit-test deterministically than a fixed
  buffer length computed synchronously before playback starts.

### D2 — Remove the late-start guard outright rather than special-case it

**Chosen:** delete the `MaxLateStartSeconds` constant and both guard blocks
(`QsoAnswererService.cs` ~lines 626–642, ~710–726) rather than keeping the constant at a much
higher value (e.g. 14.9 s) as a vestigial "basically never trips" safety net. An unreachable/
near-unreachable threshold is dead weight that a future maintainer may re-tune under the same
mistaken assumption D-CALLER-016 made. Deleting it makes the "no lateness rejection" model
unambiguous in the code, matching the spec.

**Alternatives considered:** keeping the constant at 14.9 s so the guard "still exists" — rejected
per above; also considered removing only the pending-target guard and leaving jump-in unchanged
since jump-in is double-click (arguably more deliberate) — rejected because the Captain's stated
model draws no such distinction and the field evidence covers both paths.

### D3 — Formalise `QsoCallerService`'s pending-responder behaviour via spec only

**Chosen:** add a scenario to the `qso-caller` delta spec asserting the existing (correct)
unconditional-fire behaviour, with no corresponding code change, and a design note (this document)
recording that the dev-task's "mirror-image" assumption was checked and found already-satisfied.

**Alternatives considered:** touching `QsoCallerService.cs` anyway "for symmetry" — rejected as
unnecessary code churn; the point of this proposal is behavioural correctness, not code-shape
parity between the two services.

## Risks / Trade-offs

- **[Risk] Truncated transmissions are usually undecodable at the far end** (a partial FT8 tone
  sequence rarely demodulates) → **Mitigation:** accepted by design — this matches WSJT-X's own
  behaviour per the Captain's model, and the existing retry/watchdog backstop already recovers from
  a transmission that goes unanswered, truncated or not (Captain's decision: truncated TX counts
  the same toward `_retryCount`).
- **[Risk] Removing the test region for the old defer behaviour could silently drop coverage for
  the phase-check logic that guard code was interleaved with** → **Mitigation:** the phase check
  (`nextCycleIsAPhase != pendingIsAPhase`/`jumpIsAPhase`) has its own independent scenarios already
  in the base spec and existing tests exercise it directly (e.g. wrong-phase-defers cases); the
  rewritten tests must keep asserting phase-check-still-defers-on-wrong-phase (AC-2) as a distinct
  case from late-but-correct-phase-now-fires (AC-1), so no coverage gap opens.
- **[Risk] Boundary-truncation edge case at exactly `remaining == 0`** (window closes in the same
  tick `TransmitAsync` is entered) → **Mitigation:** explicit zero-length guard in D1 skips
  `LoadAudio`/`KeyDownAsync` rather than calling them with an empty buffer, which is undefined
  behaviour for `AudioOnlyPttController`'s WASAPI init.
- **[Risk] Live field behaviour still needs re-verification** — today's evidence characterises the
  old defer bug but never exercised an actual overrun scenario, since every fired engage in the
  2026-07-14 session was well within its window → **Mitigation:** AC-5 (live verification with
  deliberately late 2–10 s clicks against a real isolated daemon) is a required task, not optional,
  before this change is considered done.

## Migration Plan

No data migration. This is a pure behaviour change in two hosted services; deploy as a normal
daemon build. Rollback is a plain revert (no persisted state format changes, no config schema
changes).

## Open Questions

None outstanding — the three design questions flagged in the originating dev-task (truncated-TX
retry counting, hard lower floor, UI indication) were resolved with the Captain before this design
was written (see proposal.md "What Changes" closing paragraph).
