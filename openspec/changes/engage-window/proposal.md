**User-facing:** yes

## Why

Field evidence from 2026-07-14 (`logs/openswfz-20260714T171230Z.log`) shows that even after
D-CALLER-016 raised `MaxLateStartSeconds` from 1.5 s to 2.0 s, **10 of 14 (71%) of manual
double-click engage attempts were still deferred a full ~30 s cycle** in a single field session.
The root cause is not a mistuned constant — the true physical ceiling for a full 12.64 s FT8
transmission is `15 − 12.64 = 2.36 s`, and real decode-to-click latency routinely exceeds that.
No threshold tuning can close this gap without hitting the ceiling itself. The Captain has
specified the correct model (WSJT-X's own behaviour): **engage unconditionally whenever the phase
is correct, and simply stop transmitting at the window boundary if the click was late** — never
reject or defer a click just because it arrived deep into its window.

## What Changes

- **Remove the late-start rejection/defer guard** in `QsoAnswererService`'s jump-in and
  pending-target consumption paths. A manual engage (CQ click or double-click jump-in) now fires
  in the *same* window it was armed for, provided the phase check passes — regardless of how many
  seconds into that window it already is. The phase check itself (wait for the next matching-phase
  window when the click landed in the wrong phase) is unchanged.
- **`QsoCallerService`'s pending-responder path already has no such guard** — investigation during
  this proposal found the dev-task's assumption of symmetric logic was inaccurate; that path
  already fires unconditionally once phase matches. This proposal formalises that existing
  (correct) behaviour as a spec requirement so it isn't accidentally regressed, rather than
  changing code there.
- **Add window-boundary truncation to `TransmitAsync`** in both `QsoAnswererService` and
  `QsoCallerService`: at the moment a transmission is about to begin, compute the time remaining
  in the current 15 s window and truncate the synthesised audio buffer to fit, so a transmission
  starting late never keys into the following window. This is a property of `TransmitAsync` itself
  (every call site), not just the manual-engage paths — an on-time transmission is unaffected
  because its full 12.64 s already fits.
- **BREAKING (behavioural, not API):** a late manual engage that used to be silently deferred to
  the next matching-phase window now fires immediately with a truncated transmission. Operators
  who relied on the old defer-and-retry behaviour will see different (and, per the Captain's
  stated model, correct) timing.
- Remove the now-unused `MaxLateStartSeconds` constant and its guard blocks from
  `QsoAnswererService.cs`; retire/rewrite the D-CALLER-013/016 late-start-guard test region in
  `QsoAnswererServiceTests.cs` to assert the new immediate-fire-with-truncation behaviour instead.
- A truncated transmission counts toward `_retryCount`/watchdog exactly like a full one (Captain's
  decision — no new "was this truncated" state). There is no hard lower floor near the end of a
  window; the app always engages if the phase is correct, per the Captain's stated model literally
  ("if the operator waited too long, it's his problem, not the application's"). No UI indication of
  truncation is in scope for this change (candidate follow-up dev-task once this ships and is
  field-verified).

## Capabilities

### New Capabilities

_(none — this is a behavioural correction to existing capabilities)_

### Modified Capabilities

- `qso-answerer`: adds a first-class spec requirement for manual-engage timing (jump-in and
  pending-target consumption fire unconditionally once the phase check passes, no late-start
  rejection) and a requirement that `TransmitAsync` never keys past the current window's boundary.
- `qso-caller`: adds a requirement formalising that the pending-responder consumption path fires
  unconditionally once the phase check passes (already-correct behaviour, now specified), and the
  same window-boundary-truncation requirement for its `TransmitAsync`.

## Impact

- `src/OpenWSFZ.Daemon/QsoAnswererService.cs`: remove `MaxLateStartSeconds` (line 147) and its two
  guard blocks (jump-in consumption ~lines 626–642; pending-target consumption ~lines 710–726);
  add boundary-truncation logic to `TransmitAsync` (~line 1193).
- `src/OpenWSFZ.Daemon/QsoCallerService.cs`: add the same boundary-truncation logic to
  `TransmitAsync` (~line 931); no change needed to the pending-responder consumption path
  (~lines 601–653), which is already correct.
- `tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs`: the D-CALLER-013/016 late-start-guard
  test region (~lines 2383–2650+) asserts the *old* defer behaviour and must be rewritten to assert
  immediate-fire-with-truncation; the shared `BuildLateStartSut` fixture and its "0 s into window"
  phase-alignment comments need updating since lateness is no longer a rejection condition.
- No `IPttController` interface change — truncation is implemented by shrinking the synthesised
  sample buffer before `LoadAudio`, not by adding a deadline parameter to `KeyDownAsync`. This
  keeps `AudioOnlyPttController`, `CatPttController`, and `SerialRtsDtrPttController` all
  unaffected.
- Live verification required per this project's standing convention for QSO-timing defects (see
  D-CALLER-018 dev-task §5): a real isolated daemon exercised with deliberately late manual engages
  (2–10 s into the window) must show immediate TX with correct unkey timing at the boundary, not a
  30 s deferral.
