## MODIFIED Requirements

### Requirement: Waterfall click interaction

The waterfall canvas SHALL respond to pointer events to set the RX and TX audio frequency offsets,
gated on a modifier key so that an unmodified click never changes anything. Mouse interactions
SHALL be:

- **Ctrl+left-click** → set RX Hz to the clicked audio frequency
- **Ctrl+right-click** → set TX Hz to the clicked audio frequency; browser default context menu
  SHALL be suppressed
- **Shift+left-click** → set both RX Hz and TX Hz to the clicked audio frequency
- **Shift+right-click** → no-op (no frequency change); browser default context menu SHALL be
  suppressed
- **Any click with no modifier held** (left or right button) → no-op (no frequency change);
  browser default context menu SHALL be suppressed for an unmodified right-click

The browser's default context menu SHALL be suppressed on the waterfall canvas for every
right-click, regardless of modifier, so its appearance does not vary depending on which modifier
key the operator happens to be holding.

The canvas SHALL carry a tooltip (`title` attribute or equivalent) describing this scheme, so an
operator unfamiliar with the modifier requirement can discover it without consulting
documentation.

Frequency SHALL be computed as `Math.round((event.offsetX / rect.width) * 3000)` clamped to
`[0, 3000]`. Each frequency-changing interaction SHALL immediately:
1. Update the canvas cursor lines
2. Send `POST /api/v1/audio-offset` with the new `{rxHz, txHz, holdTxFreq}` values
3. Update the numeric RX/TX readout elements

A no-op interaction SHALL NOT perform any of the three steps above.

#### Scenario: Ctrl+left-click sets RX frequency

- **WHEN** the operator Ctrl+left-clicks at a position corresponding to 900 Hz on the waterfall canvas
- **THEN** the RX cursor line SHALL move to 900 Hz
- **AND** the `#rx-freq-display` element SHALL show `900 Hz`
- **AND** `POST /api/v1/audio-offset` SHALL be called with `rxHz = 900`

#### Scenario: Ctrl+right-click sets TX frequency without context menu

- **WHEN** the operator Ctrl+right-clicks at a position corresponding to 1800 Hz on the waterfall canvas
- **THEN** the TX cursor line SHALL move to 1800 Hz
- **AND** the browser context menu SHALL NOT appear
- **AND** `POST /api/v1/audio-offset` SHALL be called with `txHz = 1800`

#### Scenario: Shift+left-click sets both frequencies

- **WHEN** the operator Shift+left-clicks at a position corresponding to 1500 Hz
- **THEN** both RX and TX cursor lines SHALL move to 1500 Hz (rendering as a single yellow line)
- **AND** `POST /api/v1/audio-offset` SHALL be called with `rxHz = 1500` and `txHz = 1500`

#### Scenario: Shift+right-click is a no-op

- **WHEN** the operator Shift+right-clicks anywhere on the waterfall canvas
- **THEN** neither the RX nor TX cursor line SHALL move
- **AND** `POST /api/v1/audio-offset` SHALL NOT be called
- **AND** the browser context menu SHALL NOT appear

#### Scenario: Unmodified left-click is a no-op

- **WHEN** the operator left-clicks with no modifier key held, anywhere on the waterfall canvas
- **THEN** neither the RX nor TX cursor line SHALL move
- **AND** `POST /api/v1/audio-offset` SHALL NOT be called

#### Scenario: Unmodified right-click is a no-op

- **WHEN** the operator right-clicks with no modifier key held, anywhere on the waterfall canvas
- **THEN** neither the RX nor TX cursor line SHALL move
- **AND** `POST /api/v1/audio-offset` SHALL NOT be called
- **AND** the browser context menu SHALL NOT appear

#### Scenario: Click frequency clamped to valid range

- **WHEN** the operator Ctrl+clicks at the very left edge of the canvas (offsetX = 0)
- **THEN** the resulting Hz value SHALL be 0, not a negative number

#### Scenario: Waterfall canvas has a descriptive tooltip

- **WHEN** the operator hovers over the waterfall canvas
- **THEN** a tooltip SHALL be present describing the Ctrl/Shift click scheme
