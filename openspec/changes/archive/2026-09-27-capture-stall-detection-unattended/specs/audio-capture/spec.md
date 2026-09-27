## ADDED Requirements

### Requirement: Capture health is evaluated independently of client connections

The daemon SHALL evaluate audio-capture health on a single daemon-lifetime periodic timer with a
5-second window, regardless of how many WebSocket clients are connected, including zero. Each
window SHALL be evaluated exactly once. The evaluation SHALL consume the per-window data-flow state
exactly once, SHALL advance the capture watchdog exactly once, and SHALL publish a snapshot that all
other consumers read. WebSocket connections SHALL NOT consume per-window monitor state and SHALL NOT
advance the watchdog. The watchdog SHALL trigger a pipeline restart after 3 consecutive windows in
which capture is active and no audio chunk was received.

#### Scenario: Watchdog restarts a silent stall with no client connected

- **WHEN** capture is active, zero WebSocket clients are connected, and the audio source stops
  delivering chunks without throwing
- **THEN** the pipeline restart action SHALL be invoked exactly once after 3 consecutive empty
  windows (15 s), and `watchdogRestartCount` SHALL increase by 1

#### Scenario: Watchdog tick rate does not depend on client count

- **WHEN** capture is active and 3 WebSocket clients are connected for 10 consecutive windows
- **THEN** the watchdog SHALL have been advanced exactly 10 times, and the data-flow state SHALL
  have been consumed exactly 10 times

#### Scenario: Quiet but flowing audio is not a stall

- **WHEN** capture is active and the source delivers chunks whose samples are all zero
- **THEN** `dataFlowing` SHALL be `true` for each window and the watchdog SHALL NOT trigger

#### Scenario: Stopped capture is not a stall

- **WHEN** no capture session is running (`captureActive` is `false`)
- **THEN** the watchdog SHALL NOT trigger, however many windows pass

#### Scenario: Heartbeat log line is written with no client connected

- **WHEN** the daemon runs with capture configured and zero WebSocket clients for 60 s
- **THEN** the log SHALL contain one line per window matching
  `Heartbeat: captureActive=(true|false), audioActive=(true|false), dataFlowing=(true|false)`
  (lowercase, byte-identical to the format the daemon writes today), and at most one such line
  per window, regardless of client count

### Requirement: Live data-flow status on the status endpoint

`GET /api/v1/status` and the initial WebSocket `status` event SHALL include three capture-health
fields:

- `dataFlowing` (boolean): whether at least one audio chunk was received in the most recent
  completed window. It is `false` before the first window completes.
- `lastChunkAgeMs` (integer or null): milliseconds elapsed since the most recent audio chunk was
  received, computed at the time the response is built from a monotonic clock. It is `null` only if
  no chunk has been received since process start. A pipeline restart SHALL NOT reset it.
- `watchdogRestartCount` (integer): the number of times the capture watchdog has triggered a
  pipeline restart since process start.

None of these fields SHALL latch. Each SHALL reflect current state at request time or at the most
recent window.

#### Scenario: Stall becomes visible to an HTTP-only poller

- **WHEN** capture is active with zero WebSocket clients and the source stops delivering chunks at time T
- **THEN** a `GET /api/v1/status` issued at T + 11 s SHALL return `dataFlowing: false` and
  `lastChunkAgeMs >= 10000`

#### Scenario: Healthy capture reads healthy

- **WHEN** the source delivers chunks continuously
- **THEN** every `GET /api/v1/status` after the first completed window SHALL return
  `dataFlowing: true` and `lastChunkAgeMs < 2000`

#### Scenario: A restart that delivers nothing keeps ageing

- **WHEN** the last chunk arrived at time T, the pipeline is restarted at T + 15 s, and the
  restarted session delivers no chunks
- **THEN** a `GET /api/v1/status` at T + 30 s SHALL return `lastChunkAgeMs >= 29000`

### Requirement: Audio activity has one meaning on every surface

The `audioActive` field SHALL carry the same value on `GET /api/v1/status`, on the initial WebSocket
`status` event, and on each WebSocket `heartbeat` frame: the `dataFlowing` value of the most recent
completed window. `audioActive` SHALL NOT latch across windows.

#### Scenario: REST audioActive falls when audio stops

- **WHEN** audio chunks were flowing and then stop, with zero WebSocket clients connected
- **THEN** `GET /api/v1/status` SHALL return `audioActive: false` within 10 s

#### Scenario: Surfaces agree

- **WHEN** a WebSocket client connects and, within the same window, `GET /api/v1/status` is requested
- **THEN** the `audioActive` value in the initial `status` event and in the REST response SHALL be equal
