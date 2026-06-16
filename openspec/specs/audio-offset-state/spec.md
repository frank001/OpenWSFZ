## Requirements

### Requirement: POST /api/v1/audio-offset endpoint

The daemon SHALL expose a `POST /api/v1/audio-offset` endpoint that accepts a JSON body with `rxHz` (integer), `txHz` (integer), and `holdTxFreq` (boolean). On receipt the daemon SHALL:

1. Validate that `rxHz` and `txHz` are in the range `[0, 3000]`; return HTTP 400 with a descriptive message if either is out of range
2. Update the in-memory config (`IConfigStore.Current.Tx`) to reflect the new values
3. Persist the updated config to `app.json` via `IConfigStore.SaveAsync`
4. Push an `audioOffset` WebSocket event to all connected clients
5. Return HTTP 200 with the accepted values as JSON

#### Scenario: Valid request updates config and pushes WS event

- **WHEN** `POST /api/v1/audio-offset` is called with `{"rxHz": 900, "txHz": 1500, "holdTxFreq": false}`
- **THEN** `IConfigStore.Current.Tx.RxAudioOffsetHz` SHALL be 900
- **AND** `IConfigStore.Current.Tx.TxAudioOffsetHz` SHALL be 1500
- **AND** `IConfigStore.Current.Tx.HoldTxFreq` SHALL be false
- **AND** an `audioOffset` WebSocket event SHALL be pushed to all connected clients
- **AND** the response SHALL be HTTP 200 with `{"rxHz": 900, "txHz": 1500, "holdTxFreq": false}`

#### Scenario: Out-of-range Hz rejected

- **WHEN** `POST /api/v1/audio-offset` is called with `{"rxHz": -1, "txHz": 1500, "holdTxFreq": false}`
- **THEN** the response SHALL be HTTP 400
- **AND** the config SHALL NOT be modified
- **AND** no WebSocket event SHALL be pushed

#### Scenario: holdTxFreq update persists

- **WHEN** `POST /api/v1/audio-offset` is called with `{"rxHz": 1500, "txHz": 1500, "holdTxFreq": true}`
- **THEN** `IConfigStore.Current.Tx.HoldTxFreq` SHALL be true
- **AND** `app.json` SHALL contain `"holdTxFreq": true` after the next config write completes

---

### Requirement: audioOffset WebSocket event

When audio offset state changes (via `POST /api/v1/audio-offset` or via the QSO answerer auto-updating the TX offset), the daemon SHALL push a WebSocket event of type `audioOffset` to all connected clients:

```json
{
  "type": "audioOffset",
  "payload": {
    "rxHz": 900,
    "txHz": 1500,
    "holdTxFreq": false
  }
}
```

The `status` WebSocket event payload SHALL also include `rxAudioOffsetHz`, `txAudioOffsetHz`, and `holdTxFreq` so that newly connected clients receive the current cursor state without waiting for a change event.

#### Scenario: Status event includes audio offset fields

- **WHEN** a WebSocket client connects and receives the initial `status` event
- **THEN** the `status` payload SHALL include `rxAudioOffsetHz`, `txAudioOffsetHz`, and `holdTxFreq` reflecting the current persisted values

#### Scenario: audioOffset event pushed after endpoint call

- **WHEN** `POST /api/v1/audio-offset` returns HTTP 200
- **THEN** all currently connected WebSocket clients SHALL receive an `audioOffset` event within one round-trip of the HTTP response

#### Scenario: audioOffset event pushed when answerer auto-updates TX

- **WHEN** the QSO answerer answers a CQ with `holdTxFreq = false` and uses the caller's audio frequency
- **THEN** all connected WebSocket clients SHALL receive an `audioOffset` event with the updated `txHz` equal to the caller's `freqHz`
