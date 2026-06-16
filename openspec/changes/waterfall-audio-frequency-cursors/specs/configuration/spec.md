## MODIFIED Requirements

### Requirement: TX configuration schema

`TxConfig` SHALL include the following fields. All fields SHALL have defaults so that existing `app.json` files without these keys deserialise without error.

| Field | Type | Default | Description |
|---|---|---|---|
| `AutoAnswer` | bool | false | Master enable for the QSO auto-answerer |
| `Callsign` | string | `"Q1OFZ"` | Operator callsign for outgoing FT8 messages |
| `Grid` | string | `"JO33"` | Operator Maidenhead grid locator |
| `RetryCount` | int | 3 | Max retry cycles per QSO state before abort |
| `WatchdogMinutes` | int | 4 | Watchdog timeout in minutes |
| `RxAudioOffsetHz` | int | 1500 | RX frequency cursor position in Hz (0–3000) |
| `TxAudioOffsetHz` | int | 1500 | TX frequency cursor position in Hz (0–3000) |
| `HoldTxFreq` | bool | false | When true, answerer transmits at `TxAudioOffsetHz` regardless of the caller's frequency |

#### Scenario: TxConfig with new fields round-trips through JSON

- **WHEN** a `TxConfig` with `rxAudioOffsetHz = 900`, `txAudioOffsetHz = 1800`, and `holdTxFreq = true` is serialised to JSON and deserialised again
- **THEN** all three fields SHALL have their original values

#### Scenario: Existing app.json without new fields deserialises with defaults

- **WHEN** `app.json` contains a `tx` object without `rxAudioOffsetHz`, `txAudioOffsetHz`, or `holdTxFreq`
- **THEN** the deserialised `TxConfig` SHALL have `RxAudioOffsetHz = 1500`, `TxAudioOffsetHz = 1500`, and `HoldTxFreq = false`
- **AND** the daemon SHALL start without error

#### Scenario: New fields appear in app.json after first save

- **WHEN** the daemon receives a `POST /api/v1/audio-offset` request and saves config
- **THEN** `app.json` SHALL contain `"rxAudioOffsetHz"`, `"txAudioOffsetHz"`, and `"holdTxFreq"` in the `tx` object
