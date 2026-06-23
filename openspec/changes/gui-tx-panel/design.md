## Context

The TX subsystem (`QsoAnswererService`) is fully implemented and broadcasting `txState`
WebSocket events on every state transition, but the frontend drops those events entirely.
TX is armed and monitored only through the Settings page (`tx.autoAnswer` checkbox) and
application logs. There is no in-page TX surface.

The proposal introduces two related but separable concerns:

1. **Backend refactor** — rename `IQsoAnswerer` to `IQsoController` to prepare the
   abstraction for a future `QsoCallerService`. No behaviour changes.
2. **UI extension** — add a TX panel beside the decoded-messages table and wire it to
   the existing WebSocket events and new API endpoints.

Current state worth noting:
- `WebApp.cs` captures `qsoAnswerer` as `app.Services.GetService<IQsoAnswerer>()` and
  uses it in two route handlers (`/api/v1/tx/status`, `/api/v1/tx/abort`).
- `TxEventBus.Publish(QsoState, string?)` already calls
  `WebSocketHub.BroadcastTxState` — the wire exists; the UI just ignores it.
- `GET /api/v1/config` is already called on page load (for `showCycleCountdown`), so
  the callsign and grid are available without an extra HTTP round-trip.

## Goals / Non-Goals

**Goals:**
- Single source of truth for the armed/disarmed state: the `tx.autoAnswer` flag in
  `IConfigStore`. The Enable TX / TX Armed button reflects and drives that flag.
- Operator cannot be in doubt: when TX is armed the button is visually alarming (red).
- Panel is always visible and usable even when TX is not configured (greyed rows,
  disabled controls).
- The `IQsoController` rename introduces no behaviour changes and leaves the door open
  for `QsoCallerService` without further abstraction work.

**Non-Goals:**
- `QsoCallerService` or CQ origination (TX-D01 labelling retired; aimed answering implemented via D10).
- Removing `AutoAnswer` from config (retained as the armed-flag; click-on-CQ sets it to true implicitly).
- Tune button, per-message manual TX override ("Now"/"Next" radio buttons).

## Decisions

### D1 — `IQsoAnswerer` → `IQsoController` (rename, not extend)

**Decision:** Delete `IQsoAnswerer.cs` and create `IQsoController.cs` with the same three
members (`State`, `Partner`, `AbortAsync`). `QsoAnswererService` implements
`IQsoController`. All consumers updated in the same commit.

**Alternatives considered:**
- *Keep `IQsoAnswerer`, add `IQsoController` as a base* — adds an unnecessary interface
  layer and means both names exist simultaneously, which is confusing during code review.
- *Add `QsoRole Role { get; }` to the interface now* — the property is only meaningful
  when two implementations exist. Adding it now requires a stub on `QsoAnswererService`.
  Deferred to the QsoCaller change.

**Rationale:** The rename is a one-time cost with immediate clarity payoff. The interface
is internal to the solution; there are no external consumers.

### D2 — New endpoints `POST /api/v1/tx/enable` and `POST /api/v1/tx/disable`

**Decision:** Two thin route handlers in `WebApp.cs`. Each reads `store.Current`,
mutates only `tx.autoAnswer`, saves, and returns a `TxStatusResponse` (state, partner,
`autoAnswerEnabled`).

**Alternatives considered:**
- *Reuse `POST /api/v1/config` with the full `AppConfig`* — caller must read the current
  config first to avoid overwriting unrelated fields. Too heavyweight for a button click.
- *Single `POST /api/v1/tx/toggle`* — stateless from the caller's perspective but creates
  a race if two clients click simultaneously. Two explicit endpoints are idempotent.
- *`PATCH /api/v1/config`* — REST-purist but adds JSON Patch complexity the project has
  not adopted elsewhere.

**Rationale:** Explicit enable/disable matches the `decode/start` and `decode/stop`
pattern already in the codebase (FR-017). Zero new concepts.

### D3 — `TxStatusResponse` gains `autoAnswerEnabled` field

**Decision:** The response DTO returned by `/api/v1/tx/status`, `/tx/enable`, and
`/tx/disable` is extended with a boolean `AutoAnswerEnabled`. The frontend reads this
from the response of every TX-API call (and on the initial `GET /api/v1/tx/status` poll)
to keep the button label in sync without a separate config fetch.

**Rationale:** The alternative — having the button read `GET /api/v1/config` after every
TX enable/disable call — doubles the HTTP round-trips and creates a window where the
button shows a stale state. Embedding the flag in the response is the pattern already
used by `DaemonStatus.DecodingEnabled`.

### D4 — Layout: CSS flexbox row, fixed-width TX panel

**Decision:** The `#app` flex container remains a column. A new wrapper `#content-row`
div is inserted as a flex child (between `#waterfall-controls` and the existing content)
and is itself a flex row. `#decodes-panel` is moved inside `#content-row` and takes
`flex: 1 1 0` (grows to fill). `#tx-panel` is also inside `#content-row` with
`flex: 0 0 320px` (fixed width, does not shrink).

**Alternatives considered:**
- *CSS Grid* — more expressive for two-column layouts but the rest of the page uses
  flexbox. Mixing models adds cognitive overhead for future maintainers.
- *Percentage width for TX panel* — more fluid but the message rows contain fixed-width
  monospace text; a 320 px floor is appropriate regardless of window width.

**Rationale:** Matches the existing flex-column spine; the only addition is one new flex
row. Minimal CSS delta.

### D5 — Standard message rows computed client-side

**Decision:** The three message strings are assembled in JavaScript from:
- `partner` (from the latest `txState` WS event, or `null` when Idle)
- `callsign` and `grid` (from `config.tx` received via `GET /api/v1/config` on page load)

When `partner` is null (Idle), the partner slot is rendered as `———` (em-dashes) so
the row still shows the operator's own callsign and grid as a preview.

**Rationale:** The backend already computes these strings in `QsoAnswererService`, but
broadcasting them in the `txState` event would couple the event schema to a specific QSO
role. Keeping computation client-side avoids schema churn when `QsoCallerService` is
added (different message format, same event type). The inputs (callsign, grid, partner)
are already available on the client.

### D6 — Initial TX state fetched via `GET /api/v1/tx/status` on page load

**Decision:** On `DOMContentLoaded`, the frontend calls `GET /api/v1/tx/status` once to
seed the panel with the current state, partner, and armed flag. Subsequent updates come
from `txState` WS events. The initial `status` WS event does not carry TX state.

**Alternatives considered:**
- *Add TX state to the `status` WS event payload* — would eliminate the extra HTTP call
  but requires changing `DaemonStatus` and all consumers. Disproportionate for a one-time
  page-load fetch.
- *Poll `GET /api/v1/tx/status` periodically* — unnecessary; `txState` WS events are
  already pushed on every state transition.

**Rationale:** One extra HTTP call on page load is acceptable. The WS event is the live
channel; the HTTP call is just the initial hydration. Same pattern used for the frequency
list (`GET /api/v1/frequencies`).

### D7 — TX panel always visible

**Decision:** The TX panel is always rendered in the DOM regardless of whether TX is
configured. When `tx.autoAnswer` is false or when `tx.callsign` / `tx.grid` are at their
defaults, the message rows render with greyed-out (muted) styling. No visibility toggle.

**Rationale:** Consistent with the UI visibility rule — the panel controls are fully
functional even in the unconfigured state (the button enables TX; the abort button
aborts if somehow active). Hiding the panel based on config would require client-side
config introspection and adds surface area for bugs.

### D8 — Supervised single-QSO model: every return to Idle disarms (UAT 2026-06-22)

**Decision:** Any return to `Idle` — whether from abort, normal QSO completion (73 sent),
retry exhaustion, or partner working another station — SHALL save `tx.autoAnswer = false`
and broadcast a `txState` event with `autoAnswerEnabled: false`. The operator must
explicitly click "Enable TX" before the system will answer another CQ.

**Alternatives considered:**
- *Persistent armed mode* — originally the implementation and original spec assumed
  `tx.autoAnswer` would persist across QSOs. Live testing (2026-06-22) revealed that
  after QSO completion the system immediately answered the next CQ without operator
  action, which the Captain found unsafe and undesirable.
- *Disarm on abort only, retain on completion* — rejected; the Captain confirmed both
  abort and normal completion should disarm.

**Rationale:** The supervised model gives the operator clear control over each QSO
individually. Autonomous re-arming after completion removes the human from the loop in
a way that is inappropriate for a station that may be unattended only briefly.

**Implementation:** `SafeAbortToIdleAsync` saves `tx.autoAnswer = false` and publishes
`autoAnswerEnabled: false` via `TxEventBus`. The `POST /api/v1/tx/abort` HTTP handler
also saves `tx.autoAnswer = false` (idempotent with the service save). Both paths
return or broadcast `autoAnswerEnabled: false` so the frontend disarms immediately.

**Related:** D-TX-UI-001 (abort disarm), D-TX-UI-003 (QSO-completion disarm).

---

### D9 — Button label is always "Enable TX"; armed state signalled by colour only (UAT 2026-06-22)

**Decision:** The `#tx-enable-btn` label is the static string `"Enable TX"` in both the
armed and disarmed states. The `tx-btn-armed` CSS class (red background, bold weight)
is applied when armed and removed when disarmed. The label never changes to "TX Armed".

**Alternatives considered:**
- *Label changes to "TX Armed" when armed* — original design (D-TX-UI-002). Live testing
  revealed the operator found the label change confusing rather than helpful. The armed
  state is already visually alarming via the red background; an additional label change
  was deemed redundant and potentially misleading post-abort.

**Rationale:** Consistent label reduces cognitive load. The operator always knows which
button to click to toggle TX; the colour alone communicates the current state.

---

### D10 — Clickable CQ rows: phase-aware pending-target queue (TX-D01)

**Decision:** A CQ row in the decode table may be clicked to target a specific station.
The frontend sends `POST /api/v1/tx/answer-cq {callsign, frequencyHz, cqCycleStartUtc}`.
The backend stores a pending target with three fields:
`_pendingTargetCallsign`, `_pendingTargetFrequencyHz`, and `_pendingTargetAnswerPhase`
(derived from `cqCycleStartUtc`), then returns HTTP 200.

`HandleIdleAsync` is called at every FT8 cycle boundary (regardless of phase). When a
pending target exists, `HandleIdleAsync` checks whether the current cycle is of the
**correct answer phase** — the opposite phase to the CQ. If the phase matches, the TX
fires and the pending fields are cleared. If the phase does not match, the cycle is
skipped silently and the system waits for the next boundary.

**Phase derivation:**  
FT8 cycles begin at :00, :15, :30, :45 of each UTC minute. The phase is determined by
`cycleStartSecond % 30`:
- `== 0` → A-phase (:00 and :30 slots)
- `== 15` → B-phase (:15 and :45 slots)

The correct answer phase is the opposite: CQ on A-phase → answer on B-phase, and
vice versa.

**Maximum wait:** Two successive `HandleIdleAsync` calls span 30 seconds (the full
phase rotation). After a click the system waits at most 30 seconds before TX. This is
imperceptible in FT8 protocol terms.

**Why the frontend must pass `cqCycleStartUtc`:** The service cannot reliably infer the
CQ's cycle from the current time — the operator may click on a row from several cycles
ago. The frontend has the decode timestamp from the row; it MUST parse it and pass it
as an ISO 8601 UTC string.

**Pending target timeout:** If the pending target has not fired within 60 seconds
(four full cycles — e.g. because the batch loop stalled), `HandleIdleAsync` SHALL clear
it and log a warning, rather than holding a stale pending target indefinitely.

**While a pending target is held, `HandleIdleAsync` SHALL NOT answer any other CQ from
the decode batch.** The operator's explicit click takes priority over automatic CQ
detection.

**`IQsoController` extension:** A new method
`Task AnswerCqAsync(string callsign, double frequencyHz, DateTimeOffset cqCycleStart, CancellationToken ct)`
is added. `QsoAnswererService` implements it. All other implementations (future
`QsoCallerService`) must add the method.

**Abort clears the pending target:** `SafeAbortToIdleAsync` clears all three pending-target
fields so a queued answer is cancelled if the operator aborts before the correct phase fires.

**Alternatives considered:**
- *Cycle-blind pending target (fires at next HandleIdleAsync regardless of phase)* — may
  transmit in the same phase as the CQ station, creating a TX collision. Rejected.
- *Timer-initiated TX outside the decode loop* — avoids the phase-wait delay but creates
  concurrency between the timer task and the decode loop. The phase-aware pending target
  achieves the same result with no new concurrency surfaces.
- *Transition to a new `PendingAnswer` QSO state* — adds state machine complexity; the
  pending-field approach achieves the same effect within the existing Idle state.

**Related:** Removes "Clickable decode rows" from the deferred Non-Goals list (was TX-D01).

---

### D11 — CQ row highlighting in the decode table

**Decision:** Decode table rows whose message begins with `"CQ "` SHALL receive the CSS
class `decode-cq`. The styling uses a warm accent colour (distinct from partner red) to
draw the operator's eye to stations calling CQ, particularly useful when the decode table
is dense with traffic.

**Implementation:** Applied at row-creation time in `renderDecodeRow()` (or equivalent)
in `main.js`. No server-side change required.

---

### D12 — Partner interaction highlighting in the decode table (strict mode)

**Decision:** Decode table rows that are part of the active QSO exchange SHALL receive
the CSS class `decode-partner`. The colouring SHALL be a subdued red — clearly
distinguishable but not aggressive on the eyes.

**"Part of the QSO exchange"** is defined strictly: the message contains BOTH the
operator's own callsign (from `config.tx.callsign`) AND the active partner's callsign
(from `currentTxPartner`) as space-delimited tokens. A token matches a callsign if it
equals the callsign exactly, or equals the callsign followed by `/` and a suffix
(portable indicator).

**What is NOT highlighted:**
- Third-party messages mentioning only the partner (`Q9ABC PD2FZ +12`)
- The partner's CQ calls (`CQ PD2FZ JO33`)

**Rationale:** Strict matching avoids false highlights when the band is busy and many
stations are working the same DX. The operator's own callsign being present is the
reliable signal that the row is part of their QSO.

---

## Risks / Trade-offs

**[Risk] `IQsoController` rename touches tests and DI** →  
All references to `IQsoAnswerer` are internal. A project-wide symbol rename in the IDE
handles 100 % of the call sites. The risk is a missed mock in a test — mitigated by
the build failing if any interface reference is unresolved.

**[Risk] `autoAnswerEnabled` field on `TxStatusResponse` is a JSON schema addition** →  
Old clients (browser tabs from before the deploy) will receive an extra field they
ignore. No breaking change. STJ source-gen requires the new property to be added to
`AppJsonContext`; the build will fail if omitted.

**[Risk] TX panel fixed width (320 px) is too narrow on very small screens** →  
The application targets desktop operators; narrow mobile viewports are not a supported
configuration. Acceptable trade-off for layout simplicity.

**[Risk] Message rows show `R+00` as the fixed report** →  
`QsoAnswererService` always sends `R+00` today. When SNR-derived reports are implemented
(TX-D04), the client-side message preview will show a stale value until the txState
event arrives. Acceptable: the preview is an aid, not the authoritative transmission
content.

## Migration Plan

1. Rename `IQsoAnswerer` → `IQsoController` in the same branch as the UI work.
   Build verifies zero broken references.
2. Add `autoAnswerEnabled` to `TxStatusResponse` and `AppJsonContext`.
3. Add the two new route handlers to `WebApp.cs`.
4. Restructure `index.html` and update `main.js` / `app.css`.
5. Existing config files: `tx.autoAnswer` key name unchanged — no migration needed.

No rollback complexity: the rename is mechanical; the UI additions are purely additive.
