## MODIFIED Requirements

### Requirement: Pending responder fires unconditionally within a correct-phase window

When `QsoCallerService` consumes an armed pending responder (set by `SelectResponderAsync` in `CallerPartnerSelect = None` mode), it SHALL fire the transmission in the first decode cycle whose phase matches the pending responder's expected phase, however many seconds into that window the consumption occurs, **as long as the offset t into that 15-second window is less than 11.25 s**. There SHALL be no refusal of a late responder before 11.25 s. When t is 11.25 s or more at the moment the phase check passes, the service SHALL NOT fire: it SHALL retain the pending responder and re-evaluate it on the next cycle, so that it fires in the next correct-phase window. The other gating conditions are the phase check and the existing 60-second stale-responder expiry. The offset t SHALL be computed from the service's injectable `TimeProvider`.

#### Scenario: Pending responder fires immediately even when consumed late in its window

- **WHEN** a pending responder is armed for the A phase, and the decode cycle in which its phase check first passes is consumed 6 s into that A-phase window
- **THEN** the service SHALL clear the pending responder and begin transmitting the report in that same cycle (time-aligned as the transmission requirement below states) — it SHALL NOT defer to the next A-phase occurrence

#### Scenario: A pending responder consumed from 11.25 s into its window is retained

- **WHEN** a pending responder is armed for the A phase, and its phase check first passes 12 s into that A-phase window
- **THEN** the service SHALL NOT transmit in that window, SHALL retain the pending responder, and SHALL fire it in the next A-phase window

#### Scenario: Wrong-phase cycle still waits for the next matching-phase window

- **WHEN** a pending responder is armed for the B phase and the current decode cycle is A phase
- **THEN** the service SHALL retain the pending responder unfired and re-evaluate it on the next cycle, unchanged from today

#### Scenario: Stale pending responder still expires after 60 seconds regardless of lateness

- **WHEN** a pending responder has been armed for more than 60 seconds without its phase check passing
- **THEN** the service SHALL discard it and log a Warning

### Requirement: Transmission never keys past the current window's boundary

`TransmitAsync` (used by every transmission `QsoCallerService` sends — CQ, report, RR73/73 retries and continuations) SHALL, immediately before loading audio into the `IPttController`, compute the offset t into the current 15-second window from the moment of the call, using the injectable `TimeProvider`, and apply this rule to the 12.64 s synthesised buffer (606,720 samples at 48 kHz):

- **t at most 2.36 s:** the full buffer SHALL be loaded unmodified.
- **t greater than 2.36 s and less than 11.25 s:** the first `round((t - 0.5) x 48,000)` samples SHALL be skipped and the remaining samples loaded, so that every remaining symbol goes out at its proper time (as WSJT-X does for a late start). The start of the clip is cut, not the tail.
- **t at least 11.25 s:** the service SHALL NOT call `LoadAudio` or `KeyDownAsync` and SHALL log at Information level.

The existing boundary clamp SHALL remain as a safety net, applied after the skip, and SHALL log the number of samples it cuts at Information level. Where the clip is cut, the cut SHALL be shaped: the first 240 samples (5 ms) loaded after a skip SHALL be faded in with a raised cosine, gain(i) = 0.5 x (1 - cos(pi x i / 239)) for i = 0 to 239, and the last 240 samples before a tail cut by the boundary clamp SHALL be faded out along the same curve; a full, uncut buffer SHALL be loaded unmodified. For every transmission with t greater than 2.36 s the service SHALL write one Information log line carrying the offset, the samples skipped and the samples loaded, as milliseconds, and no message text. A transmission shortened by this requirement SHALL be treated identically to a full-length transmission for retry-counter accounting, watchdog reset, and ADIF logging purposes.

#### Scenario: A start within 2.36 s transmits the full clip

- **WHEN** `TransmitAsync` is called 0 s, 0.62 s or 2.36 s into its window
- **THEN** the full synthesised 12.64 s buffer SHALL be passed to `LoadAudio` unmodified, exactly as before this change

#### Scenario: Late-armed transmission is time-aligned

- **WHEN** `TransmitAsync` is called 9 s into its 15 s window
- **THEN** `round((9 - 0.5) x 48,000)` = 408,000 samples SHALL be skipped and 198,720 loaded, the first 240 loaded samples rising from 0 and the rest equal to the input from index 408,240, and one Information line SHALL be written

#### Scenario: From 11.25 s the service does not key

- **WHEN** `TransmitAsync` is entered 11.25 s or later into its window
- **THEN** the service SHALL NOT call `LoadAudio` or `KeyDownAsync`, SHALL log at Information level, and SHALL return without transmitting

#### Scenario: Aligned transmission counts toward retry/watchdog like a full one

- **WHEN** a transmission is shortened by this requirement and receives no matching response in the following decode cycle
- **THEN** the retry counter SHALL increment exactly as it would for a full-length transmission that went unanswered
