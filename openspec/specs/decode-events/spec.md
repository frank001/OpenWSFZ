## Requirements

### Requirement: WebSocket decode event broadcast

After each FT8 decode cycle completes the daemon SHALL broadcast a `decode` event to all
currently connected WebSocket clients. The event SHALL follow the existing envelope format
`{ "type": "decode", "payload": [<DecodeResult>, ...] }`. An empty payload array SHALL be
sent when a cycle produces no decodes. The broadcast SHALL be fire-and-forget per connection;
a connection that cannot accept the frame within 1 second SHALL be closed and removed from
the active set without affecting other connections or the decode pipeline.

#### Scenario: Decode event is received by a connected client after a decode cycle

- **WHEN** a WebSocket client is connected and `Ft8Decoder` completes a cycle that produced
  at least one decode
- **THEN** the client SHALL receive a text frame with `"type": "decode"` and a non-empty
  `payload` array within 500 ms of the decode completing

#### Scenario: Empty decode event is sent for a silent cycle

- **WHEN** a WebSocket client is connected and a decode cycle produces zero results
- **THEN** the client SHALL receive a text frame with `"type": "decode"` and an empty
  `payload` array (`[]`) within 500 ms of the cycle completing

#### Scenario: Slow client is disconnected without blocking other clients

- **WHEN** one connected client stops reading from its socket while a second client is
  active and a decode event is broadcast
- **THEN** the second client SHALL receive the event within 500 ms and the slow client's
  connection SHALL be closed

---

### Requirement: DecodeResult JSON shape in WebSocket payload

Each element of the `decode` event's `payload` array SHALL be a JSON object with the
following keys and types:

| Key | Type | Description |
|---|---|---|
| `time` | string | UTC cycle start, format `HH:mm:ss` |
| `snr` | number (integer) | SNR in dB relative to 2500 Hz noise floor |
| `dt` | number (float) | Timing offset in seconds |
| `freqHz` | number (integer) | Audio offset of strongest tone in Hz |
| `message` | string | Decoded message text or `"<hex>"` |

#### Scenario: Decode payload matches DecodeResult serialisation

- **WHEN** a `decode` event is received by a WebSocket client
- **THEN** each element of the `payload` array SHALL contain exactly the five keys listed
  above with the correct types

---

### Requirement: UI decoded-messages table populated from decode events

The browser UI (`js/main.js`) SHALL handle incoming `decode` WebSocket events and insert
each `DecodeResult` as a new row in the `#decodes-table` tbody (`#decodes-body`). Rows
SHALL be prepended (newest at top). The "No decodes yet" placeholder row SHALL be removed
on the first decode event with a non-empty payload. The table SHALL be capped at 200 rows;
excess rows SHALL be removed from the bottom when the cap is exceeded.

#### Scenario: First decode event removes the placeholder row and inserts decoded rows

- **WHEN** the UI receives a `decode` event with at least one result and the table currently
  shows only the placeholder row
- **THEN** the placeholder row SHALL be removed and one new `<tr>` SHALL be prepended for
  each result in the payload, displaying Time, dB, DT (seconds), Freq (Hz), and Message

#### Scenario: Decode rows are newest-first

- **WHEN** two successive decode events are received with results
- **THEN** the rows from the second event SHALL appear above the rows from the first event
  in the table

#### Scenario: Table is capped at 200 rows

- **WHEN** cumulative decode rows in the table would exceed 200
- **THEN** rows beyond 200 (oldest) SHALL be removed from the tbody to keep the count at
  or below 200

#### Scenario: Empty decode event does not modify the table

- **WHEN** a `decode` event with an empty payload array is received
- **THEN** the table SHALL not change (no rows added, placeholder not removed)
