## Context

The waterfall canvas (`spectrum.js`) currently renders a scrolling frequency/time display with axis tick marks drawn as a canvas overlay after `putImageData`. There is no concept of an operator-selected audio frequency — the QSO answerer always transmits at the caller's decoded `freqHz`, and the decode pipeline processes the full 0–3000 Hz passband with no RX focus.

`TxConfig` holds the TX/answerer preferences (`AutoAnswer`, `Callsign`, `Grid`, `RetryCount`, `WatchdogMinutes`). `IConfigStore` is the single source of truth for all persisted config, saved atomically via write-to-temp-then-rename.

The existing canvas event model has no click handlers. The frequency axis drawing (`_drawFrequencyAxis`) runs after every `putImageData`, making it the natural anchor point for cursor overlays.

## Goals / Non-Goals

**Goals:**
- Left-click → RX cursor (green line); right-click → TX cursor (red line); shift+left-click → both (yellow when equal)
- `POST /api/v1/audio-offset` endpoint: updates `rxAudioOffsetHz`, `txAudioOffsetHz`, `holdTxFreq` in-memory and persists immediately to `app.json`
- `HoldTxFreq` checkbox on the main page; when OFF the answerer auto-updates the TX cursor to the caller's frequency on each new CQ; when ON the answerer ignores the caller's offset and transmits at the operator-set `txAudioOffsetHz`
- Numeric readouts (`RX: N Hz`, `TX: N Hz`) near the waterfall
- All connected browser tabs stay in sync via WebSocket
- Defaults: `rxAudioOffsetHz = 1500`, `txAudioOffsetHz = 1500`, `holdTxFreq = false`

**Non-Goals:**
- Directed AP decode at the RX frequency (Path B — deferred to D-001 investigation as Hypothesis 6)
- Decode filtering by RX frequency (visual-only in this change)
- Making the numeric readouts editable inputs (click-on-canvas is the setter)
- Sub-Hz precision (integer Hz resolution throughout)

## Decisions

### D1 — Persist in `TxConfig`, not a separate singleton

**Decision:** Add `RxAudioOffsetHz` (int, default 1500), `TxAudioOffsetHz` (int, default 1500), and `HoldTxFreq` (bool, default false) as new fields on `TxConfig`. Persist via `IConfigStore.SaveAsync` on every `POST /api/v1/audio-offset`.

**Rationale:** Keeps the single-source-of-truth pattern. `IConfigStore.Current.Tx` is already readable from `QsoAnswererService` without additional injection. No new interface or singleton. Config saves are atomic and fast; one write per waterfall click is acceptable.

**Alternative considered:** A separate `IAudioOffsetState` in-memory singleton loaded from config on startup, with debounced writes. Rejected — adds a new interface, a startup loading step, and an in-memory / on-disk sync hazard. Not warranted for three fields.

### D2 — Dedicated lightweight endpoint `POST /api/v1/audio-offset`

**Decision:** New endpoint, not a reuse of `POST /api/v1/config`.

**Rationale:** `POST /api/v1/config` expects the full config object assembled by the Settings JS. Sending a full config from a waterfall click would require `main.js` to maintain a full config snapshot — an unacceptable coupling between the main page and the settings page. A dedicated endpoint accepts only `{rxHz, txHz, holdTxFreq}` and merges into the current config atomically.

### D3 — WS event strategy: extend `status` payload + new `audioOffset` push event

**Decision:** Include `rxAudioOffsetHz`, `txAudioOffsetHz`, `holdTxFreq` in the existing `status` WebSocket event payload (so newly connected tabs receive the current state immediately). Additionally, push a dedicated `audioOffset` event whenever `POST /api/v1/audio-offset` succeeds, so connected tabs update cursors without waiting for the next `status` heartbeat.

When the answerer auto-updates `TxAudioOffsetHz` (Hold TX = OFF, CQ answered), it also pushes an `audioOffset` event via `TxEventBus` or a new `AudioOffsetEventBus`.

### D4 — Canvas cursor overlay in `_drawCursors()` called from `render()`

**Decision:** Add a new private `_drawCursors()` method on `WaterfallRenderer`. It is called at the end of `render()`, after `putImageData` and `_drawFrequencyAxis()`. It holds `_rxHz` and `_txHz` as instance fields set by `setRxHz(hz)` / `setTxHz(hz)` public methods. When `_rxHz === _txHz`, a single yellow line is drawn; otherwise green (RX) and red (TX) lines are drawn independently. Lines span the full canvas height and are drawn with 1.5 px width at 80% opacity so the underlying waterfall is readable through them.

**Alternative considered:** Drawing cursors in `_drawFrequencyAxis()`. Rejected — axis ticks and cursors have different update semantics; keeping them separate is cleaner.

### D5 — Click coordinate mapping

**Decision:** Use `event.offsetX` (CSS pixels relative to the element) divided by `canvas.getBoundingClientRect().width` to get the fractional position, then multiply by `MAX_FREQ_HZ` (3000). No DPR correction — `offsetX` is in CSS pixels independent of device pixel ratio.

```
hz = Math.round((event.offsetX / rect.width) * MAX_FREQ_HZ)
hz = Math.max(0, Math.min(MAX_FREQ_HZ, hz))
```

Suppress the browser's context menu on right-click via `preventDefault()` on `contextmenu`.

### D6 — QsoAnswererService reads TxConfig directly; auto-updates via SaveAsync

**Decision:** When `HoldTxFreq` is false and the answerer answers a CQ, it:
1. Uses `cqResult.FreqHz` as the TX frequency (existing behaviour).
2. Calls `IConfigStore.SaveAsync` with `TxAudioOffsetHz = cqResult.FreqHz` so the cursor reflects the actual TX position.
3. Pushes an `audioOffset` WS event.

When `HoldTxFreq` is true, step 1 uses `configStore.Current.Tx.TxAudioOffsetHz` instead. Steps 2 and 3 are skipped (cursor stays put).

**Risk:** `SaveAsync` inside `QsoAnswererService` adds a disk write on every CQ answer. Acceptable — CQ answers are rare (one per 15-second cycle at most) and the write is async and atomic.

## Risks / Trade-offs

- **Rapid waterfall clicks** → rapid `POST /api/v1/audio-offset` calls → rapid `SaveAsync` calls. Mitigation: the client debounces at 100 ms (pointer-up, not pointer-move), so rapid drags don't flood the endpoint. Worst case is one write per click, which is acceptable.
- **Hold TX ON with TX = 1500 Hz default** → answerer transmits at 1500 Hz even if the CQ is at 800 Hz. Operator must be aware. Mitigation: the Hold TX checkbox is visually prominent; the TX readout always shows the actual frequency used. No silent behaviour.
- **Cursor not visible on narrow canvases** — at very small viewport widths a 1 px line at 1500 Hz may be indistinguishable. Accepted; minimum supported width is sufficient for a 1.5 px cursor line.
- **Multi-tab sync lag** — if two tabs update the cursor simultaneously the last write wins. Accepted for a single-operator tool.

## Migration Plan

No migration required. New `TxConfig` fields have defaults (`rxAudioOffsetHz = 1500`, `txAudioOffsetHz = 1500`, `holdTxFreq = false`), so existing `app.json` files that lack these fields deserialise correctly via C# record defaults. On the next config write the new fields will be persisted.
