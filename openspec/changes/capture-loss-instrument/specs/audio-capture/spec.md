## ADDED Requirements

### Requirement: The Linux capture source SHALL drain and count `arecord` diagnostics without altering the captured audio

The `arecord`-based capture source SHALL read the subprocess's standard error continuously from process start until exit, concurrently with standard output, so that a full stderr pipe can never block `arecord`. The stderr reader SHALL NOT delay or alter the standard-output read loop: the chunks yielded SHALL be byte-identical to those yielded for the same PCM when stderr is empty. `arecord` SHALL be started with `LC_ALL=C` in its environment and otherwise with the same arguments as before this change.

A stderr line containing `overrun` (case-insensitive) is an overrun. For each one the source SHALL log a Warning whose text contains its receive time in UTC to the millisecond and the reported length in milliseconds when present, SHALL increment a process-lifetime `CaptureOverrunCount`, and SHALL add the reported length to a process-lifetime `CaptureOverrunReportedMs` when it parses. Other stderr lines SHALL be logged at Information, the first 20 and then every 100th, with a running count.

#### Scenario: An overrun line is counted and logged with its time

- **WHEN** the subprocess writes `overrun!!! (at least 10.5 ms long)` to stderr while streaming PCM
- **THEN** `CaptureOverrunCount` increases by 1 and `CaptureOverrunReportedMs` by 10.5
- **AND** a Warning is logged whose text contains the UTC receive time with milliseconds and the reported length

#### Scenario: Stderr noise does not change the audio

- **WHEN** the same PCM is captured once with an empty stderr and once with overrun and other lines on stderr
- **THEN** the sequences of yielded chunks are byte-identical

#### Scenario: A large stderr does not block capture

- **WHEN** the subprocess writes at least 256 KiB to stderr before closing stdout
- **THEN** capture completes and all PCM is yielded

#### Scenario: Other lines are not overruns and are rate-limited

- **WHEN** the subprocess writes 150 lines that do not contain `overrun`
- **THEN** `CaptureOverrunCount` is unchanged
- **AND** 20 of them are logged at Information, then every 100th

### Requirement: The capture manager SHALL count chunks dropped from its channel

`CaptureManager` SHALL count every chunk discarded by its bounded `DropOldest` channel in a process-lifetime `CaptureChannelDroppedChunks`, and SHALL log a Warning, containing the UTC time to the millisecond, on the first drop and on every 100th thereafter. Counting SHALL NOT block the capture thread.

#### Scenario: A stalled consumer causes counted drops

- **WHEN** the source delivers more chunks than the channel holds and nothing reads the channel
- **THEN** `CaptureChannelDroppedChunks` equals the number of chunks discarded

#### Scenario: A draining consumer causes none

- **WHEN** the consumer keeps pace with the source
- **THEN** `CaptureChannelDroppedChunks` remains 0

### Requirement: The cycle framer SHALL log every window's grid realignment

For every emitted window the cycle framer SHALL log at Information the window's cycle start, the realignment it wanted and the realignment it applied (both in samples), and the number of source samples consumed. The realignment arithmetic SHALL be unchanged.

#### Scenario: One line per window with wanted and applied

- **WHEN** a window is emitted
- **THEN** exactly one Information line is logged for it, carrying the cycle start, `wanted` and applied values in samples

### Requirement: The capture-loss counters SHALL be reported on the daemon status surface

`CaptureOverrunCount`, `CaptureOverrunReportedMs` and `CaptureChannelDroppedChunks` SHALL be reported in `DaemonStatus` on `GET /api/v1/status` and on the WebSocket `status` event, defaulting to 0 where a platform has no such source. The `Heartbeat:` log line defined by FR-067 SHALL remain byte-identical.

#### Scenario: Counters appear on the status endpoint

- **WHEN** `GET /api/v1/status` is requested
- **THEN** the response carries the three counters, and they are 0 on a platform whose source reports none

#### Scenario: The heartbeat line is unchanged

- **WHEN** a capture-health window is evaluated
- **THEN** the `Heartbeat:` line text is exactly as before this change
