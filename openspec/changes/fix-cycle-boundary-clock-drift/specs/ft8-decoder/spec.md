## ADDED Requirements

### Requirement: Decode-cycle boundary tracks true UTC over long-running sessions

`CycleFramer` SHALL bound the deviation between a decode-cycle window's actual sample content
and the true UTC 15-second FT8 slot grid over an arbitrarily long-running capture session. When
the accumulated deviation between the nominal (arithmetic) cycle-boundary sequence and the
injected `IClock`'s wall-clock reading exceeds a threshold **and that threshold-crossing
persists across several consecutive checks in the same direction without shrinking**,
`CycleFramer` SHALL correct the next window's target sample count by a small, bounded number of
samples and re-anchor the reported `cycleStart` to the corrected wall-clock value at that same
boundary, so that neither the window's decodable content nor its reported timestamp drift
unboundedly from true UTC for the life of a session. Below that threshold, or on a reading that
does not persist (a sign reversal, or a shrinking magnitude, relative to the current candidate
streak), `CycleFramer` SHALL NOT alter its existing behaviour (exactly `SamplesPerCycle` samples
per window, `cycleStart` advanced by 15 seconds). This persistence requirement exists because a
real capture pipeline's own recurring scheduling latency can make a single reading look far
outside the threshold without any genuine device drift being present — see Scenario "A
recurring, non-monotonic deviation does not fire a correction" below.

#### Scenario: No correction fires for a session with no clock deviation

- **WHEN** `CycleFramer.RunAsync` runs against an `IClock` whose `UtcNow` advances in exact
  lock-step with the nominal 15-second cycle-boundary sequence (no simulated drift) across many
  emitted windows
- **THEN** every emitted window SHALL contain exactly `SamplesPerCycle` (180 000) samples and
  `cycleStart` SHALL equal the prior `cycleStart` plus exactly 15 seconds for every window

#### Scenario: Bounded correction fires once accumulated deviation persists above the threshold

- **WHEN** `CycleFramer.RunAsync` runs against an `IClock` whose `UtcNow` advances at a
  constant rate offset from the nominal cycle-boundary sequence (simulating a capture device
  clock-rate error), across enough emitted windows for the accumulated deviation to exceed the
  correction threshold and remain above it, growing in the same direction, for several
  consecutive checks
- **THEN** no correction fires while the threshold-crossing has not yet persisted for the
  required number of consecutive checks; once it has, the next window's target sample count
  SHALL be adjusted by a small, bounded number of samples (no larger than the documented cap)
  and `cycleStart` SHALL be re-anchored to the `IClock`-derived wall-clock value at that
  boundary, rather than continuing the uncorrected arithmetic sequence

#### Scenario: A single implausibly large clock deviation does not trigger a single large correction

- **WHEN** `CycleFramer.RunAsync` runs against an `IClock` whose `UtcNow` reports one
  implausibly large, one-off deviation from the nominal cycle-boundary sequence (simulating a
  host system clock step rather than gradual device drift)
- **THEN** the resulting correction, if any, SHALL NOT exceed the documented per-event bound —
  a single anomalous reading SHALL NOT produce an unbounded jump in the window's sample count
  or in `cycleStart`

#### Scenario: A recurring, non-monotonic deviation does not fire a correction

- **WHEN** `CycleFramer.RunAsync` runs against an `IClock` whose `UtcNow` reports a deviation
  from the nominal cycle-boundary sequence that repeatedly exceeds the correction threshold on
  every check, but whose magnitude bounces up and down from check to check rather than growing
  monotonically in one direction (simulating a real capture pipeline's own recurring scheduling
  latency — WASAPI callback jitter, channel backpressure, thread-pool contention with concurrent
  decode work — rather than genuine device clock-rate drift)
- **THEN** no correction SHALL fire for any of those checks, and `cycleStart` SHALL continue
  advancing by exactly 15 seconds per window, unchanged — an isolated or non-persistent
  threshold-crossing reading, however large, SHALL NOT by itself be treated as genuine,
  sustained drift
