## ADDED Requirements

### Requirement: Decode-cycle boundary tracks true UTC over long-running sessions

`CycleFramer` SHALL bound the deviation between a decode-cycle window's actual sample content
and the true UTC 15-second FT8 slot grid over an arbitrarily long-running capture session. When
the accumulated deviation between the nominal (arithmetic) cycle-boundary sequence and the
injected `IClock`'s wall-clock reading exceeds a threshold, `CycleFramer` SHALL correct the
next window's target sample count by a small, bounded number of samples and re-anchor the
reported `cycleStart` to the corrected wall-clock value at that same boundary, so that neither
the window's decodable content nor its reported timestamp drift unboundedly from true UTC for
the life of a session. Below that threshold, `CycleFramer` SHALL NOT alter its existing
behaviour (exactly `SamplesPerCycle` samples per window, `cycleStart` advanced by 15 seconds).

#### Scenario: No correction fires for a session with no clock deviation

- **WHEN** `CycleFramer.RunAsync` runs against an `IClock` whose `UtcNow` advances in exact
  lock-step with the nominal 15-second cycle-boundary sequence (no simulated drift) across many
  emitted windows
- **THEN** every emitted window SHALL contain exactly `SamplesPerCycle` (180 000) samples and
  `cycleStart` SHALL equal the prior `cycleStart` plus exactly 15 seconds for every window

#### Scenario: Bounded correction fires once accumulated deviation exceeds the threshold

- **WHEN** `CycleFramer.RunAsync` runs against an `IClock` whose `UtcNow` advances at a
  constant rate offset from the nominal cycle-boundary sequence (simulating a capture device
  clock-rate error), across enough emitted windows for the accumulated deviation to exceed the
  correction threshold
- **THEN** at the window where the threshold is crossed, the next window's target sample count
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
