**User-facing:** yes

## Why

The main page status bar currently shows two separate elements for decode state:
`#decode-badge` (a read-only status label reading "Decoding"/"Stopped") sitting directly next to
`#decode-toggle` (a button reading "Stop Decoding"/"Start Decoding"/"No device" that starts/stops
the pipeline). The Captain finds these confusing as two adjacent-but-distinct controls conveying
overlapping information. They can be the same element: one control that both displays the current
state and is the click target to change it, following the same "colour + label together" idiom
already used for the TX-enable button elsewhere in this status bar.

## What Changes

- **BREAKING** (UI markup/behaviour only, no API/data-model change): `#decode-badge` and
  `#decode-toggle` are removed and replaced by a single element, `#decode-toggle` (kept as the
  button, since it must remain clickable and keyboard-focusable), that serves both roles:
  - Decoding active: bright green background, text **"DECODING"** (all caps).
  - Decoding stopped: bright red background, text **"Start decoding"** (sentence case — capital S
    only).
  - No audio device configured (`audioDevice` null/empty): existing disabled "No device" state is
    preserved on the merged control.
  - Clicking it while active calls `POST /api/v1/decode/stop`; clicking it while stopped calls
    `POST /api/v1/decode/start` — identical to `#decode-toggle`'s current click behaviour.
- No backend, API, or WebSocket payload changes. `decodingEnabled` and `audioDevice` status fields
  are consumed exactly as today; only how they render in `web/index.html`/`web/js/main.js`/
  `web/css/app.css` changes.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `web-frontend`: the two existing requirements "Decode start/stop toggle button in status bar"
  and "Decoding-state badge in status bar" (`openspec/specs/web-frontend/spec.md`) are removed and
  replaced by a single requirement describing the merged `#decode-toggle` control's four states
  (active/stopped/no-device, plus its click behaviour).

## Impact

- `web/index.html` — removes the separate `<span id="decode-badge">` element (status bar around
  line 28); `<button id="decode-toggle">` (line 30) becomes the sole element and its label/style
  logic changes.
- `web/js/main.js` — the `decodeBadgeEl`/`decodeToggleEl` element references (around line
  948–950) and whatever render function currently sets each element's text/class from
  `decodingEnabled`/`audioDevice` collapse into one function driving one element.
- `web/css/app.css` — the existing `#decode-badge`, `.decoding-active`, `.decoding-stopped` rules
  (around lines 559–581) and the existing `#decode-toggle` button rules are consolidated into
  styling for the single merged control, reusing the existing `--color-success`/`--color-danger`
  tokens already used elsewhere (e.g. the TX-enable button) rather than introducing new colours.
- No changes to `src/` (backend), `/api/v1/decode/start`, `/api/v1/decode/stop`, or the WebSocket
  status payload shape.
- Any existing frontend tests or documentation referencing `#decode-badge` by ID need updating
  (none found in `*.test.js` at time of writing — verify again during implementation).
