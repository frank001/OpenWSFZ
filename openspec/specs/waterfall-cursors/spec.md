# waterfall-cursors Specification

## Purpose

Specifies the waterfall display's RX/TX frequency cursor lines, click-to-tune interaction,
and the numeric RX/TX frequency readouts shown alongside the waterfall.

## Requirements

### Requirement: Waterfall cursor lines

The waterfall canvas SHALL display vertical cursor lines indicating the current RX and TX audio frequency offsets. The visual encoding SHALL be:

- RX and TX at different frequencies → green line at RX position, red line at TX position
- RX and TX at the same frequency → single yellow line at that position
- Lines SHALL span the full height of the canvas
- Lines SHALL be drawn after `putImageData` and the frequency axis ticks, so they appear on top of the waterfall content
- Line width SHALL be 1.5 CSS pixels; opacity SHALL be 80% so the underlying waterfall is readable through them

#### Scenario: Green line drawn at RX frequency when RX ≠ TX

- **WHEN** `setRxHz(1200)` and `setTxHz(1500)` are called on `WaterfallRenderer`
- **THEN** a green vertical line SHALL appear at the canvas X position corresponding to 1200 Hz
- **AND** a red vertical line SHALL appear at the canvas X position corresponding to 1500 Hz

#### Scenario: Single yellow line when RX equals TX

- **WHEN** `setRxHz(1500)` and `setTxHz(1500)` are called on `WaterfallRenderer`
- **THEN** a single yellow vertical line SHALL appear at 1500 Hz
- **AND** no separate green or red line SHALL be drawn

#### Scenario: Cursor lines survive a resize event

- **WHEN** `WaterfallRenderer.resize()` is called after cursor positions have been set
- **THEN** the next call to `render()` SHALL still draw the cursor lines at the correct Hz positions

---

### Requirement: Waterfall click interaction

The waterfall canvas SHALL respond to pointer events to set the RX and TX audio frequency offsets. Mouse interactions SHALL be:

- **Left-click** (no modifier) → set RX Hz to the clicked audio frequency
- **Right-click** → set TX Hz to the clicked audio frequency; browser default context menu SHALL be suppressed
- **Shift+left-click** → set both RX Hz and TX Hz to the clicked audio frequency

Frequency SHALL be computed as `Math.round((event.offsetX / rect.width) * 3000)` clamped to `[0, 3000]`. Each interaction SHALL immediately:
1. Update the canvas cursor lines
2. Send `POST /api/v1/audio-offset` with the new `{rxHz, txHz, holdTxFreq}` values
3. Update the numeric RX/TX readout elements

#### Scenario: Left-click sets RX frequency

- **WHEN** the operator left-clicks (no modifier) at a position corresponding to 900 Hz on the waterfall canvas
- **THEN** the RX cursor line SHALL move to 900 Hz
- **AND** the `#rx-freq-display` element SHALL show `900 Hz`
- **AND** `POST /api/v1/audio-offset` SHALL be called with `rxHz = 900`

#### Scenario: Right-click sets TX frequency without context menu

- **WHEN** the operator right-clicks at a position corresponding to 1800 Hz on the waterfall canvas
- **THEN** the TX cursor line SHALL move to 1800 Hz
- **AND** the browser context menu SHALL NOT appear
- **AND** `POST /api/v1/audio-offset` SHALL be called with `txHz = 1800`

#### Scenario: Shift+left-click sets both frequencies

- **WHEN** the operator shift+left-clicks at a position corresponding to 1500 Hz
- **THEN** both RX and TX cursor lines SHALL move to 1500 Hz (rendering as a single yellow line)
- **AND** `POST /api/v1/audio-offset` SHALL be called with `rxHz = 1500` and `txHz = 1500`

#### Scenario: Click frequency clamped to valid range

- **WHEN** the operator clicks at the very left edge of the canvas (offsetX = 0)
- **THEN** the resulting Hz value SHALL be 0, not a negative number

---

### Requirement: RX and TX numeric readouts

The main page SHALL display the current RX and TX audio frequency offsets as numeric readouts adjacent to the waterfall. The readouts SHALL update immediately on every cursor change (local click, remote WS event, or auto-update from the answerer).

#### Scenario: Readouts show initial values on page load

- **WHEN** a browser loads the main page and receives the initial `status` WebSocket event
- **THEN** `#rx-freq-display` SHALL show the current `rxAudioOffsetHz` formatted as `N Hz`
- **AND** `#tx-freq-display` SHALL show the current `txAudioOffsetHz` formatted as `N Hz`

#### Scenario: Readouts update after a click

- **WHEN** the operator clicks the waterfall to change the RX frequency to 750 Hz
- **THEN** `#rx-freq-display` SHALL immediately update to `750 Hz`
