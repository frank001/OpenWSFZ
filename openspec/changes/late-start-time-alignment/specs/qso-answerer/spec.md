## MODIFIED Requirements

### Requirement: Manual engage fires unconditionally within a correct-phase window

When `QsoAnswererService` consumes an armed manual-engage target — a pending target set by `AnswerCqAsync` (CQ click) or by `TryEngageExternal`, or a jump-in target set by `EngageAtAsync` (double-click) — it SHALL fire the transmission in the first decode cycle whose phase matches the armed target's expected phase, however many seconds into that window the consumption occurs, **as long as the offset t into that 15-second window is less than 11.25 s**. There SHALL be no refusal of a late engage before 11.25 s. When t is 11.25 s or more at the moment the phase check passes, the service SHALL NOT fire: it SHALL retain the target and re-evaluate it on the next cycle, so that it fires in the next correct-phase window. The other gating conditions are the phase check (fire only when `nextCycleIsAPhase` matches the armed `pendingIsAPhase`/`jumpIsAPhase`) and the existing 60-second stale-target expiry. A target whose phase does not match the current cycle SHALL continue to be retained and re-evaluated on the next cycle.

The offset t SHALL be computed from the service's injectable `TimeProvider`.

#### Scenario: Pending target fires immediately even when armed late in its window

- **WHEN** a pending target (from `AnswerCqAsync`) is armed for the A phase, and the decode cycle in which its phase check first passes is consumed 5 s into that A-phase window
- **THEN** the service SHALL clear the pending target and begin transmitting in that same cycle (time-aligned as the transmission requirement below states) — it SHALL NOT defer to the next A-phase occurrence

#### Scenario: Jump-in fires immediately even when armed late in its window

- **WHEN** a jump-in target (from `EngageAtAsync`) is armed for the B phase, and the decode cycle in which its phase check first passes is consumed 6 s into that B-phase window
- **THEN** the service SHALL clear the jump-in target and begin transmitting in that same cycle — it SHALL NOT defer to the next B-phase occurrence

#### Scenario: A manual engage consumed from 11.25 s into its window is retained

- **WHEN** a pending target or a jump-in target is armed for the A phase, and its phase check first passes 12 s into that A-phase window
- **THEN** the service SHALL NOT transmit in that window, SHALL retain the target, and SHALL fire it in the next A-phase window (about 18.75 s later)

#### Scenario: Wrong-phase cycle still waits for the next matching-phase window

- **WHEN** a pending target is armed for the A phase and the current decode cycle is B phase
- **THEN** the service SHALL retain the pending target unfired and re-evaluate it on the next cycle

#### Scenario: Stale target still expires after 60 seconds regardless of lateness

- **WHEN** a pending or jump-in target has been armed for more than 60 seconds without its phase check passing
- **THEN** the service SHALL discard it and log a Warning

### Requirement: Transmission never keys past the current window's boundary

`TransmitAsync` (used by every transmission the service sends — manual-engage answers, retries, report/RR73/73 continuations) SHALL, immediately before loading audio into the `IPttController`, compute the offset t into the current 15-second window from the moment of the call, using the injectable `TimeProvider`, and apply this rule to the 12.64 s synthesised buffer (606,720 samples at 48 kHz):

- **t at most 2.36 s:** the full buffer SHALL be loaded unmodified. (2.36 s = 15 s - 12.64 s, the latest a whole signal can start.)
- **t greater than 2.36 s and less than 11.25 s:** the first `round((t - 0.5) x 48,000)` samples SHALL be skipped and the remaining samples loaded, so that every remaining symbol goes out at its proper time (as WSJT-X does for a late start; the nominal FT8 start is 0.5 s into the window). Playback then ends about 13.14 s into the window. The start of the clip is cut, not the tail.
- **t at least 11.25 s:** the service SHALL NOT call `LoadAudio` or `KeyDownAsync` and SHALL log at Information level, rather than keying PTT with an empty or useless buffer.

The existing boundary clamp (truncating the buffer so that playback cannot extend past the window's boundary) SHALL remain as a safety net and SHALL be applied after the skip; when it cuts any samples it SHALL log the number of samples cut at Information level. **Where the clip is cut, the cut SHALL be shaped:** the first 240 samples (5 ms) loaded after a skip SHALL be faded in with a raised cosine, gain(i) = 0.5 x (1 - cos(pi x i / 239)) for i = 0 to 239, and the last 240 samples before a tail cut by the boundary clamp SHALL be faded out along the same curve. A full, uncut buffer SHALL be loaded unmodified.

For every transmission with t greater than 2.36 s the service SHALL write one Information log line carrying the offset, the samples skipped and the samples loaded, as milliseconds, and no message text.

A transmission shortened by this requirement SHALL be treated identically to a full-length transmission for `_retryCount` accounting, watchdog reset, and ADIF logging purposes — there is no distinct "truncated" state tracked elsewhere in the state machine.

#### Scenario: A start within 2.36 s transmits the full clip

- **WHEN** `TransmitAsync` is called 0.62 s into its window, or 2.36 s into its window
- **THEN** the full 12.64 s buffer SHALL be passed to `LoadAudio` unmodified, and no late-start log line SHALL be written

#### Scenario: A start just past 2.36 s skips the start of the clip

- **WHEN** `TransmitAsync` is called 2.37 s into its window
- **THEN** the first 89,760 samples SHALL be skipped and 516,960 samples SHALL be loaded; the first 240 loaded samples SHALL rise from 0 to 1 x the input by the raised cosine, and from the 241st loaded sample on they SHALL equal the input samples from index 90,000

#### Scenario: Late-armed transmission is time-aligned

- **WHEN** `TransmitAsync` is called 4.9 s into its window
- **THEN** 211,200 samples SHALL be skipped and 395,520 loaded, the first 240 loaded samples rising from 0 and the rest equal to the input from index 211,440, and one Information line with the offset, skipped and loaded milliseconds SHALL be written

#### Scenario: The last allowed start

- **WHEN** `TransmitAsync` is called 11.24 s into its window
- **THEN** 515,520 samples SHALL be skipped and 91,200 loaded

#### Scenario: From 11.25 s the service does not key

- **WHEN** `TransmitAsync` is entered 11.25 s or 14.9 s into its window
- **THEN** the service SHALL NOT call `LoadAudio` or `KeyDownAsync`, SHALL log at Information level, and SHALL return without transmitting

#### Scenario: Aligned transmission counts toward retry/watchdog like a full one

- **WHEN** a transmission is shortened by this requirement and receives no matching response in the following decode cycle
- **THEN** the retry counter SHALL increment exactly as it would for a full-length transmission that went unanswered
