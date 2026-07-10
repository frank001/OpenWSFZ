## Context

The status bar in `web/index.html` currently carries two adjacent elements for decode state:
`<span id="decode-badge">` (read-only, text "Decoding"/"Stopped", classes `decoding-active`/
`decoding-stopped`) and `<button id="decode-toggle">` (text "Stop Decoding"/"Start Decoding"/
"No device", the actual click target for `/api/v1/decode/start`/`/decode/stop`). Both are driven
from the same underlying `decodingEnabled`/`audioDevice` status fields, updated on the same events
(`status`, heartbeat, successful start/stop response) — the split into two elements adds no
information the operator can't get from one, and reads as visual clutter/redundancy. This mirrors
a pattern already resolved elsewhere in the same status bar: `#tx-enable-btn` is a single element
that is simultaneously the state indicator (colour) and the click target (per `tx-state-indicators`
and D-TX-UI-002).

## Goals / Non-Goals

**Goals:**
- Collapse `#decode-badge` and `#decode-toggle` into one element, `#decode-toggle`, that is both
  the visual state indicator and the click target.
- Preserve all four existing states' underlying triggers exactly (`decodingEnabled: true/false`,
  `audioDevice` null/empty → "No device" disabled), only changing how they render and where.
- Preserve exact click behaviour (`POST /api/v1/decode/start`/`/decode/stop`) unchanged.
- New label text per the Captain's explicit wording: **"DECODING"** (all caps) when active,
  **"Start decoding"** (sentence case) when stopped — deliberately different casing from the old
  "Stop Decoding"/"Start Decoding" labels, not a typo to be "fixed" during implementation.

**Non-Goals:**
- No backend, API, or WebSocket payload changes.
- No change to the "No device" disabled-state trigger condition or its existing behaviour beyond
  which element carries it.
- Not touching any other status-bar element (`#ws-state`, `#audio-indicator`, `#cat-badge`,
  `#cycle-timer`) — those are separate, unrelated to this change.

## Decisions

**Decision 1 — keep the `<button>` element, drop the `<span>`, both keep id `decode-toggle`.**
The merged control must remain a real, keyboard-focusable, clickable `<button>` (accessibility:
a `<span>` badge is not natively focusable/actionable). Renaming would be gratuitous churn for no
behavioural benefit and would break any external reference to `#decode-toggle` (e.g. existing
manual test notes, screenshots) for no reason — the id `decode-toggle` is kept, `#decode-badge`
is deleted outright.

**Decision 2 — reuse `--color-success`/`--color-danger` design tokens, not new colours.**
"Bright green"/"bright red" map directly to the tokens already defined at `app.css:8`–`9`
(`--color-success: #3fb950`, `--color-danger: #f85149`) and already used for other bright-state
indicators in this file (e.g. `.cat-connected`, `#tx-call-cq-btn.tx-call-cq-armed`). No new colour
values are introduced.

**Decision 3 — "No device" disabled styling stays neutral/muted, not red or green.**
The existing disabled-button convention elsewhere in this app (browser default `:disabled` +
reduced opacity, no colour override) is preserved for the merged control's "No device" state, so
it reads as unavailable rather than as a third coloured state competing with green/red.

## Risks / Trade-offs

- [Risk] Any external tooling, screenshot-based UAT scripts, or manual test notes that reference
  `#decode-badge` by id will silently stop finding it. → Mitigation: grep the repo for
  `decode-badge` during implementation (checked once already during proposal drafting — no
  `*.test.js` hits) and update any hits found; note the removal explicitly in the PR description.
- [Risk] The deliberately different capitalisation ("DECODING" vs. former "Decoding", "Start
  decoding" vs. former "Start Decoding") could be mistaken for a typo by a future
  maintainer/reviewer and "corrected" back. → Mitigation: the delta spec below states the exact
  casing normatively, in quotes, so `openspec validate` and any future spec-conformance review
  catches an accidental reversion.

## Migration Plan

Frontend-only, no data migration. Deploy as a normal PR: implement in `web/index.html`/
`web/js/main.js`/`web/css/app.css`, verify against the delta spec's scenarios, merge. No rollback
concerns beyond a normal revert (no persisted state depends on the markup shape).

## Open Questions

None outstanding — casing, colours, and element identity were all specified explicitly by the
Captain or resolved by Decision 1–3 above.
