## ADDED Requirements

### Requirement: Pending responder fires unconditionally within a correct-phase window

When `QsoCallerService` consumes an armed pending responder (set by `SelectResponderAsync` in `CallerPartnerSelect = None` mode), it SHALL fire the transmission in the first decode cycle whose phase matches the pending responder's expected phase, regardless of how many seconds into that window the consumption occurs. There SHALL be no lateness-based rejection or deferral: the only gating conditions are the phase check and the existing 60-second stale-responder expiry. This formalises behaviour already present in `HandleWaitAnswerAsync`'s pending-responder path — no code change is required by this requirement, only regression protection against a future lateness guard being added by analogy with `QsoAnswererService`'s (now-removed) one.

#### Scenario: Pending responder fires immediately even when consumed late in its window

- **WHEN** a pending responder is armed for the A phase, and the decode cycle in which its phase
  check first passes is consumed 6 s into that A-phase window
- **THEN** the service SHALL clear the pending responder and begin transmitting the report in that
  same cycle — it SHALL NOT defer to the next A-phase occurrence

#### Scenario: Wrong-phase cycle still waits for the next matching-phase window

- **WHEN** a pending responder is armed for the B phase and the current decode cycle is A phase
- **THEN** the service SHALL retain the pending responder unfired and re-evaluate it on the next
  cycle, unchanged from today

#### Scenario: Stale pending responder still expires after 60 seconds regardless of lateness

- **WHEN** a pending responder has been armed for more than 60 seconds without its phase check
  passing
- **THEN** the service SHALL discard it and log a Warning

---

### Requirement: Transmission never keys past the current window's boundary

`TransmitAsync` (used by every transmission `QsoCallerService` sends — CQ, report, RR73/73 retries and continuations) SHALL, immediately before loading audio into the `IPttController`, compute the time remaining in the current 15-second cycle window from the moment of the call and truncate the synthesised sample buffer so that playback cannot extend past that window's boundary. A transmission that begins early enough to play in full SHALL be unaffected. If the computed remaining time is zero or negative at the moment `TransmitAsync` is entered, the service SHALL skip `LoadAudio`/`KeyDownAsync` entirely for that call and log at Debug level, rather than keying PTT with an empty buffer.

A transmission shortened by this requirement SHALL be treated identically to a full-length transmission for retry-counter accounting, watchdog reset, and ADIF logging purposes.

#### Scenario: Late-armed transmission is truncated to fit the remaining window

- **WHEN** `TransmitAsync` is called 9 s into its 15 s window (6 s remaining)
- **THEN** the synthesised audio buffer SHALL be truncated to at most 6 s of playback before
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
