## Why

OpenWSFZ currently decodes FT8 signals but cannot transmit. Transmit capability is required to participate in QSOs and is the next logical capability milestone. A real radio is deliberately excluded from this phase to satisfy regulatory obligations — transmitting untested software over the air risks spurious emissions and licence violations. A VoiceMeeter software audio loopback (WSJT-X ↔ OpenWSFZ) serves as the safe, consequence-free test fixture.

## What Changes

- **New:** FT8 TX pipeline — encodes FT8 messages using libft8.dll, synthesises GFSK audio, plays it through the configured output device at the correct FT8 cycle boundary.
- **New:** PTT abstraction (`IPttController`) — decouples the TX pipeline from the physical keying mechanism; v1 implementation is audio-output on/off only.
- **New:** QSO answerer state machine — auto-answers the first decoded CQ, drives a 6-message FT8 exchange (answer → wait report → send R+report → wait RR73/RRR → send 73), retries up to 3 times per waiting state, aborts on watchdog expiry.
- **New:** ADIF log writer — appends one ADIF record per completed QSO to `ADIF.log`, located beside `ALL.TXT`.
- **Modified:** `configuration` spec — new `tx` config section (callsign, grid, retry count, watchdog, ADIF log path).

## Capabilities

### New Capabilities

- `ft8-tx`: FT8 message encoding (via libft8.dll), GFSK audio synthesis, cycle-aligned audio playback, and PTT abstraction interface (`IPttController`). Exposes new REST endpoints for TX control and status.
- `qso-answerer`: Automated FT8 QSO answerer state machine. Listens for decoded CQs, executes the standard 6-message exchange, handles all failure modes (no-response retry, wrong-callsign ignore, RRR/RR73 equivalence, out-of-sequence advance, watchdog abort, operator abort), and signals QSO completion for logging.
- `adif-log`: ADIF 3.x contact log writer. Appends one record per completed QSO. Fields: `CALL`, `GRIDSQUARE`, `MODE`, `BAND`, `FREQ`, `RST_SENT`, `RST_RCVD`, `QSO_DATE`, `TIME_ON`, `TIME_OFF`, `OPERATOR`, `MY_GRIDSQUARE`.

### Modified Capabilities

- `configuration`: Add `tx` sub-object to `AppConfig`. Fields: `callsign` (string, default `"Q1OFZ"` per NFR-021), `grid` (string, default `"JO33"`), `retryCount` (int, default `3`), `watchdogMinutes` (int, default `4`), `adifLogPath` (string, default `"ADIF.log"` resolved beside the executable).

## Impact

- **`OpenWSFZ.Ft8`** — new P/Invoke bindings for libft8.dll encode entry points; new `Ft8Encoder` class; new `Ft8AudioSynthesiser` class.
- **`OpenWSFZ.Daemon`** — new `QsoAnswererService` (hosted service or scoped to decode pipeline); new `AdifLogWriter`; new `AudioOnlyPttController` (implements `IPttController`); new REST endpoints `POST /api/v1/tx/answer`, `POST /api/v1/tx/abort`, `GET /api/v1/tx/status`; `AppConfig` schema extended with `tx` section.
- **`OpenWSFZ.Ft8.Tests` / `OpenWSFZ.Daemon.Tests`** — unit tests for state machine transitions, failure modes, ADIF record formatting, and audio synthesis.
- **libft8.dll** — existing binary dependency; encode functions used for the first time (decode functions already in use).
- **No breaking changes** — existing config files without a `tx` key load using defaults; existing endpoints unaffected.
