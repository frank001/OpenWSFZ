## Why

The operator cannot easily compare OpenWSFZ decode output against WSJT-X because the two applications produce results in incompatible formats. WSJT-X writes every decoded message to `ALL.TXT` in a well-defined columnar format; OpenWSFZ currently emits decodes only as WebSocket events. Providing an `ALL.TXT`-compatible log file removes the need for manual transcription and enables direct side-by-side comparison.

## What Changes

- **New configuration field** `dialFrequencyMHz` (double, e.g. `7.074`) — the dial frequency shown in each `ALL.TXT` line; required because the decode pipeline operates on audio-domain frequencies (Hz offset from 0) and has no knowledge of the transceiver's VFO setting.
- **New ALL.TXT log file** — the daemon appends one line per decoded message to `ALL.TXT` (configurable path, default: `ALL.TXT` beside the executable) after every decode cycle, using the WSJT-X columnar format:
  ```
  YYMMDD_HHMMSS     D.DDD Rx FT8 {snr,6} {dt,5:F1} {freq,4} {message}
  ```
- **Settings UI** — the dial frequency field and ALL.TXT path are exposed on the Settings page.
- **No changes to the FT8 decode pipeline** — SNR, DT, and audio frequency are already present on `DecodeResult`; only the file-writing path is new.

## Capabilities

### New Capabilities

- `decode-log`: Appends decoded FT8 messages to an `ALL.TXT` file in WSJT-X-compatible format after each decode cycle.

### Modified Capabilities

- `configuration`: Two new config fields are added (`dialFrequencyMHz`, `allTxtPath`), requiring an updated spec.

## Impact

- **`src/OpenWSFZ.Daemon/`** — new `AllTxtWriter` service; `Program.cs` wires it to the decode event; `AppConfig` gains two fields.
- **`src/OpenWSFZ.Web/`** — Settings page gains dial-frequency input and ALL.TXT path input.
- **`REQUIREMENTS.md`** — two new functional requirements (FR-027, FR-028); note that FR-026 (FT8 decode throughput, already implemented in tests) should also be formally recorded.
- No changes to `OpenWSFZ.Ft8`, `OpenWSFZ.Audio`, or any existing spec behaviour.
