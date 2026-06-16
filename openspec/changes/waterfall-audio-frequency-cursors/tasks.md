## 1. Configuration model

- [x] 1.1 Add `RxAudioOffsetHz` (int, default 1500), `TxAudioOffsetHz` (int, default 1500), and `HoldTxFreq` (bool, default false) to `TxConfig` in `src/OpenWSFZ.Abstractions/TxConfig.cs`
- [x] 1.2 Verify existing `app.json` without new fields deserialises with defaults (unit test in `OpenWSFZ.Config.Tests` or equivalent)
- [x] 1.3 Verify new fields round-trip through JSON serialisation

## 2. Audio offset REST endpoint

- [x] 2.1 Add `POST /api/v1/audio-offset` endpoint handler in the daemon — accepts `{rxHz, txHz, holdTxFreq}`, validates `rxHz` and `txHz` are in `[0, 3000]`, returns HTTP 400 on out-of-range
- [x] 2.2 On valid request: update `IConfigStore` by calling `SaveAsync` with the merged `TxConfig`, push `audioOffset` WS event, return HTTP 200 with accepted values
- [x] 2.3 Register the endpoint route in `Program.cs`

## 3. WebSocket audioOffset event

- [x] 3.1 Define the `audioOffset` WebSocket event payload (type `"audioOffset"`, fields `rxHz`, `txHz`, `holdTxFreq`) — add to the WS event dispatch in the daemon
- [x] 3.2 Include `rxAudioOffsetHz`, `txAudioOffsetHz`, `holdTxFreq` in the existing `status` WebSocket event payload so newly connecting clients receive the current state

## 4. QsoAnswererService — TX frequency selection

- [x] 4.1 When answering a CQ and `holdTxFreq` is `false`: use `cqResult.FreqHz` as the TX frequency (existing behaviour); additionally call `IConfigStore.SaveAsync` to update `TxAudioOffsetHz = cqResult.FreqHz`; push `audioOffset` WS event
- [x] 4.2 When answering a CQ and `holdTxFreq` is `true`: use `configStore.Current.Tx.TxAudioOffsetHz` as the TX frequency; do not modify config or push an event
- [x] 4.3 Ensure the TX frequency selected at CQ-answer time is used consistently for all subsequent transmissions in the session (answer, report, Tx73, retries) — store in `_lastTxFreqHz` as before

## 5. WaterfallRenderer — cursor drawing

- [x] 5.1 Add `_rxHz` and `_txHz` private fields (nullable int or -1 sentinel) to `WaterfallRenderer` in `web/js/spectrum.js`; initialise to 1500 each
- [x] 5.2 Add `setRxHz(hz)` and `setTxHz(hz)` public methods that store the values and schedule a redraw (or mark dirty for next `render()` call)
- [x] 5.3 Add `_drawCursors()` private method: draw green (RX) and red (TX) vertical lines, or a single yellow line when `_rxHz === _txHz`; lines span full canvas height, 1.5 px wide at 80% opacity
- [x] 5.4 Call `_drawCursors()` at the end of `render()` after `_drawFrequencyAxis()`
- [x] 5.5 Call `_drawCursors()` from `resize()` (via `_resize()`) so cursors persist after canvas resize

## 6. Main page — canvas click handlers

- [x] 6.1 In `web/js/main.js`: add `click` event listener on `#waterfall` — if `event.shiftKey`, set both RX and TX; else set RX only; compute Hz from `event.offsetX / rect.width * 3000` clamped to `[0, 3000]`
- [x] 6.2 Add `contextmenu` event listener on `#waterfall` — `preventDefault()`, then set TX Hz from click position
- [x] 6.3 After each cursor change: call `renderer.setRxHz()` / `renderer.setTxHz()`, update `#rx-freq-display` and `#tx-freq-display`, call `POST /api/v1/audio-offset`
- [x] 6.4 Add handler for incoming `audioOffset` WS event: update renderer cursors, readouts, and checkbox state

## 7. Main page — Hold TX Freq checkbox and readouts

- [x] 7.1 In `web/index.html`: add `<span id="rx-freq-display">` and `<span id="tx-freq-display">` near the waterfall
- [x] 7.2 Add `<label><input type="checkbox" id="hold-tx-freq"> Hold TX Freq</label>` near the waterfall
- [x] 7.3 In `web/js/main.js`: wire `#hold-tx-freq` change event to call `POST /api/v1/audio-offset` with current rxHz, txHz, and updated holdTxFreq
- [x] 7.4 On receiving `status` WS event: initialise renderer cursors, readouts, and checkbox from `rxAudioOffsetHz`, `txAudioOffsetHz`, `holdTxFreq` in the payload
- [x] 7.5 In `web/css/app.css`: style the readouts and checkbox label to align cleanly with the waterfall

## 8. Tests

- [x] 8.1 Unit test — `TxConfig` deserialises from JSON without new fields using defaults
- [x] 8.2 Unit test — `TxConfig` with new fields round-trips through JSON
- [x] 8.3 Unit test / integration test — `POST /api/v1/audio-offset` with valid body returns 200 and updates config
- [x] 8.4 Unit test / integration test — `POST /api/v1/audio-offset` with out-of-range `rxHz` returns 400
- [x] 8.5 Unit test — `QsoAnswererService`: when `holdTxFreq` is false, answering a CQ updates `TxAudioOffsetHz` to the caller's `freqHz`
- [x] 8.6 Unit test — `QsoAnswererService`: when `holdTxFreq` is true, answering a CQ uses `TxAudioOffsetHz` from config and does not modify it

## 9. D-001 investigation note

- [x] 9.1 Add a note to the D-001 investigation record (GitHub Issue #3 or MEMORY.md) documenting the AP decode mechanism as Hypothesis 6: a new shim entry point `ft8_decode_directed(pcm, targetFreqHz, mycall, hiscall, qsoState, ...)` could provide up to +4 dB sensitivity at the partner's audio frequency during active QSO states — equivalent to WSJT-X's `nfqso` + AP mechanism in `ft8b.f90`
