**User-facing:** yes

## Why

The operator can no longer follow the actual QSO conversation. The TX panel's Tx 1/Tx 2/Tx 3
rows only ever show the *template* for the current exchange step (overwritten in place each
cycle — never a history), and the panel's "TX History" list only records abort reasons, never
message content. The only place a partner's actual replies appear is the decodes table — and
the `decode-panel-filtering` column filter can legitimately hide those very rows from view,
since it is designed to suppress everything except what the operator has chosen to see. The
result: filtering works exactly as designed, but the operator loses the thread of their own
live QSO while it is filtered out from under them. Raised directly by the Captain (screenshot,
2026-07-18) pointing at the existing "TX History" section as the natural place for a fix.

## What Changes

- Add a **QSO Transcript** section to the TX panel, in the exact DOM location currently occupied
  by the "TX History" abort-reason list, absorbing that list into a single unified,
  chronological, newest-on-top log.
- The transcript records every message the operator's own station actually transmits (derived
  from the existing `renderMessageRows` state-machine hook, at the moment a Tx* state first
  becomes active — not re-logged on repeated renders of the same state) and every decoded
  message belonging to the operator's own tracked conversation (matched by callsign token
  against `txCallsign`/`currentTxPartner`, the same matching idiom the existing
  `decode-partner` row highlight already uses).
- The transcript is read from the raw `decode` WebSocket feed **before** the
  `decode-panel-filtering` column filter and **before** `decode-noise-suppression` are applied —
  it is deliberately unaffected by both, since the entire point is to keep the operator's own
  conversation visible regardless of filter state.
- The list is a rolling session log (not cleared per-QSO): every message for every partner
  worked this session persists, newest-on-top, with a visible partner-change separator whenever
  the tracked partner changes. Abort-reason entries (existing `FR-UX-002` behaviour) are folded
  into the same chronological list rather than kept in a separate one.
- Entries are colorized by direction only: sent (own TX) vs. received (partner's decode) in two
  distinct colors. No further per-message-type sub-coloring in this iteration.
- Adds **FR-062** to `REQUIREMENTS.md` and a corresponding new "Requirement:" entry in
  `openspec/specs/web-frontend/spec.md`, alongside the existing TX-panel requirements.
- **User-facing:** yes — bumps `VERSION` per the minor-version-per-user-facing-feature rule.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `web-frontend`: adds a new requirement for the TX panel's QSO Transcript section (message
  capture, partner-change separators, filter-bypass sourcing, direction colorization), and
  retires the standalone "TX History" abort-only requirement in favour of the unified log.

## Impact

- `web/index.html` — replace the `#tx-abort-log-section` block with the new transcript section
  markup.
- `web/js/main.js` — `renderMessageRows`/`renderTxPanel` (sent-message capture hook),
  `handleDecodes` (received-message capture, pre-filter), `appendTxAbortLog` and its call site
  (folded into the new unified transcript function).
- New DOM-free JS module (mirroring `web/js/decodeFilter.js`'s pattern) housing the
  matching/aggregation logic, so it can be unit-tested independently of the DOM — needed to
  satisfy Gate G3 traceability once FR-062 exists in `REQUIREMENTS.md`.
- `web/css/app.css` — direction-based colorization classes.
- `REQUIREMENTS.md` — new FR-062 entry, VERSION bump.
- `openspec/specs/web-frontend/spec.md` — new/modified TX-panel requirement (via delta spec in
  this change).
- No backend/API/WebSocket wire-format changes — all source data already reaches the frontend
  via the existing `decode` and `txState` WebSocket events.
