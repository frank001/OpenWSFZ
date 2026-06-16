## Why

The waterfall display shows signal activity across the 0–3000 Hz audio passband but provides no way for the operator to mark which frequency they are listening on or transmitting at. Without RX/TX frequency cursors, the QSO answerer always transmits at the caller's audio frequency (TX-D02 deferred), giving the operator no control over TX placement. Adding visual cursors and a "Hold TX Freq" mode closes this gap and makes the waterfall an operational control surface rather than a passive display.

## What Changes

- Left-click on the waterfall sets the RX audio frequency offset (green vertical cursor line).
- Right-click sets the TX audio frequency offset (red vertical cursor line).
- Shift+left-click sets both RX and TX to the same frequency (yellow cursor line when identical).
- When RX and TX are at the same audio offset a single yellow line is drawn; otherwise two separate lines.
- A "Hold TX Freq" checkbox appears on the main page near the waterfall. When checked, the QSO answerer transmits at the operator-set TX frequency rather than the caller's audio frequency.
- When Hold TX Freq is **off** (default), the TX cursor auto-updates to the caller's audio frequency each time the answerer selects a CQ to answer, so the waterfall always reflects where the software is actually transmitting.
- RX offset, TX offset, and Hold TX Freq state are persisted in `app.json` and survive daemon restarts.
- Numeric readouts (`RX: NNNN Hz`, `TX: NNNN Hz`) are displayed near the waterfall for precision reference.
- Default values on first run: RX = 1500 Hz, TX = 1500 Hz, Hold TX Freq = false.

## Capabilities

### New Capabilities

- `waterfall-cursors`: RX and TX audio frequency cursor lines on the waterfall canvas, set by mouse interaction (left-click, right-click, shift+left-click). Visual encoding: green = RX, red = TX, yellow = both same. Numeric readouts alongside the canvas.
- `audio-offset-state`: Daemon-side in-memory state for `rxAudioOffsetHz`, `txAudioOffsetHz`, and `holdTxFreq`. Initialised from config on startup. Updated via `POST /api/v1/audio-offset`. Pushed to all WebSocket clients on change. Persisted to `app.json` on every update.

### Modified Capabilities

- `qso-answerer`: TX frequency selection now consults `holdTxFreq` and `txAudioOffsetHz`. When Hold TX Freq is on, the answerer transmits at the operator-set TX offset. When off, the answerer uses the caller's decoded `freqHz` and updates the in-memory `txAudioOffsetHz` so the cursor reflects the actual TX frequency.
- `web-frontend`: Main page gains the Hold TX Freq checkbox, RX/TX Hz readouts, and canvas click handlers. Status WebSocket events carry the current audio offset state so all browser tabs stay in sync.
- `configuration`: `TxConfig` gains three new persisted fields: `rxAudioOffsetHz` (int, default 1500), `txAudioOffsetHz` (int, default 1500), `holdTxFreq` (bool, default false).

## Impact

- `web/js/spectrum.js` — new cursor drawing methods and click coordinate mapping
- `web/js/main.js` — canvas event listeners, Hold TX Freq checkbox, readout updates
- `web/index.html` — new UI elements (readouts, checkbox)
- `web/css/app.css` — minor styling for readouts and checkbox
- `src/OpenWSFZ.Daemon/` — new `IAudioOffsetState` / `AudioOffsetState` singleton; new `POST /api/v1/audio-offset` endpoint; `QsoAnswererService` TX frequency logic; `AppConfig` / `TxConfig` model extension; WebSocket status event extension
- No change to native shim, decode pipeline, or test infrastructure
