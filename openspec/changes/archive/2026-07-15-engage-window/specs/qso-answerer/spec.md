## ADDED Requirements

### Requirement: Manual engage fires unconditionally within a correct-phase window

When `QsoAnswererService` consumes an armed manual-engage target — a pending target set by `AnswerCqAsync` (CQ click) or a jump-in target set by `EngageAtAsync` (double-click) — it SHALL fire the transmission in the first decode cycle whose phase matches the armed target's expected phase, regardless of how many seconds into that window the consumption occurs. There SHALL be no lateness-based rejection or deferral: the only gating conditions are the phase check (fire only when `nextCycleIsAPhase` matches the armed `pendingIsAPhase`/`jumpIsAPhase`) and the existing 60-second stale-target expiry. A target whose phase does not match the current cycle SHALL continue to be retained and re-evaluated on the next cycle, unchanged from prior behaviour.

#### Scenario: Pending target fires immediately even when armed late in its window

- **WHEN** a pending target (from `AnswerCqAsync`) is armed for the A phase, and the decode cycle
  in which its phase check first passes is consumed 5 s into that A-phase window
- **THEN** the service SHALL clear the pending target and begin transmitting in that same cycle —
  it SHALL NOT defer to the next A-phase occurrence

#### Scenario: Jump-in fires immediately even when armed late in its window

- **WHEN** a jump-in target (from `EngageAtAsync`) is armed for the B phase, and the decode cycle
  in which its phase check first passes is consumed 6 s into that B-phase window
- **THEN** the service SHALL clear the jump-in target and begin transmitting in that same cycle —
  it SHALL NOT defer to the next B-phase occurrence

#### Scenario: Wrong-phase cycle still waits for the next matching-phase window

- **WHEN** a pending target is armed for the A phase and the current decode cycle is B phase
- **THEN** the service SHALL retain the pending target unfired and re-evaluate it on the next cycle,
  exactly as before this change

#### Scenario: Stale target still expires after 60 seconds regardless of lateness

- **WHEN** a pending or jump-in target has been armed for more than 60 seconds without its phase
  check passing
- **THEN** the service SHALL discard it and log a Warning, unaffected by the removal of the
  lateness guard

---

### Requirement: Transmission never keys past the current window's boundary

`TransmitAsync` (used by every transmission the service sends — manual-engage answers, retries, report/RR73/73 continuations) SHALL, immediately before loading audio into the `IPttController`, compute the time remaining in the current 15-second cycle window from the moment of the call and truncate the synthesised sample buffer so that playback cannot extend past that window's boundary. A transmission that begins early enough to play in full SHALL be unaffected — truncation SHALL only shorten the buffer when the full 12.64 s clip would otherwise overrun the window. If the computed remaining time is zero or negative at the moment `TransmitAsync` is entered, the service SHALL skip `LoadAudio`/`KeyDownAsync` entirely for that call and log at Debug level, rather than keying PTT with an empty buffer.

A transmission shortened by this requirement SHALL be treated identically to a full-length transmission for `_retryCount` accounting, watchdog reset, and ADIF logging purposes — there is no distinct "truncated" state tracked elsewhere in the state machine.

#### Scenario: Late-armed transmission is truncated to fit the remaining window

- **WHEN** `TransmitAsync` is called 8 s into its 15 s window (7 s remaining)
- **THEN** the synthesised audio buffer SHALL be truncated to at most 7 s of playback before
  `LoadAudio` is called, and the resulting `KeyDownAsync` call SHALL NOT extend transmission past
  the window boundary

#### Scenario: On-time transmission is not truncated

- **WHEN** `TransmitAsync` is called at the start of its window (0 s in, full 15 s remaining)
- **THEN** the full synthesised 12.64 s buffer SHALL be passed to `LoadAudio` unmodified, exactly as
  before this change

#### Scenario: Zero remaining time skips transmission rather than keying an empty buffer

- **WHEN** `TransmitAsync` is entered at or after the window's boundary (zero or negative time
  remaining)
- **THEN** the service SHALL NOT call `LoadAudio` or `KeyDownAsync`, SHALL log at Debug level, and
  SHALL return without transmitting

#### Scenario: Truncated transmission counts toward retry/watchdog like a full one

- **WHEN** a transmission is truncated by this requirement and receives no matching response in the
  following decode cycle
- **THEN** the retry counter SHALL increment exactly as it would for a full-length transmission
  that went unanswered
