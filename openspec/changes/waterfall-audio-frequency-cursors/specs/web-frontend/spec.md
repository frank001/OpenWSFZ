## ADDED Requirements

### Requirement: Hold TX Freq checkbox on main page

The main page SHALL include a `<label>` containing an `<input type="checkbox" id="hold-tx-freq">` element positioned near the waterfall display. The checkbox SHALL reflect the current `holdTxFreq` state received from the `status` or `audioOffset` WebSocket events. When the operator toggles the checkbox, the page SHALL immediately call `POST /api/v1/audio-offset` with the updated `holdTxFreq` value alongside the current `rxHz` and `txHz`.

#### Scenario: Checkbox reflects initial state from status event

- **WHEN** the main page receives a `status` WebSocket event with `holdTxFreq: true`
- **THEN** `#hold-tx-freq` SHALL be checked

#### Scenario: Checkbox reflects initial state false

- **WHEN** the main page receives a `status` WebSocket event with `holdTxFreq: false`
- **THEN** `#hold-tx-freq` SHALL be unchecked

#### Scenario: Toggling checkbox calls audio-offset endpoint

- **WHEN** the operator checks `#hold-tx-freq` while `rxHz = 1500` and `txHz = 1500`
- **THEN** `POST /api/v1/audio-offset` SHALL be called with `{"rxHz": 1500, "txHz": 1500, "holdTxFreq": true}`

---

### Requirement: Main page handles audioOffset WebSocket event

The main page WebSocket handler SHALL process `audioOffset` events and update the cursor lines, numeric readouts, and Hold TX Freq checkbox to reflect the new values. This ensures that when the QSO answerer auto-updates the TX cursor (Hold TX = OFF, CQ answered), all browser tabs update without requiring a page reload.

#### Scenario: audioOffset event updates TX cursor and readout

- **WHEN** the main page receives an `audioOffset` event with `{"rxHz": 900, "txHz": 1234, "holdTxFreq": false}`
- **THEN** the waterfall TX cursor line SHALL move to 1234 Hz
- **AND** `#tx-freq-display` SHALL show `1234 Hz`
- **AND** `#hold-tx-freq` SHALL be unchecked

#### Scenario: audioOffset event updates RX cursor and readout

- **WHEN** the main page receives an `audioOffset` event with `{"rxHz": 750, "txHz": 1500, "holdTxFreq": false}`
- **THEN** the waterfall RX cursor line SHALL move to 750 Hz
- **AND** `#rx-freq-display` SHALL show `750 Hz`
