## Context

OpenWSFZ currently writes an ADIF log entry automatically and silently the moment a QSO reaches `QsoComplete`. The entry contains the fields available to the state machine (call, grid, RST, timestamps, freq, operator) but nothing the operator has in their head (name, TX power, propagation mode, comments, contest exchange). There is no confirmation step and no opportunity to discard an accidental QSO.

WSJT-X presents a modal "Log QSO" dialog the instant the final transmission begins. The operator reviews and optionally enriches the entry during the ~15-second TX window, then clicks OK or Cancel. The entry is only written to ADIF on OK.

This design replicates that workflow in OpenWSFZ. The daemon and browser are already event-driven over WebSocket; the main structural work is (a) routing a new WS event at the right state transition, (b) standing up a standalone write endpoint, and (c) implementing the modal dialog in the web frontend.

A secondary deliverable is `PropModeStore` — a protocol-aware list of propagation modes seeded with the FT8 subset, following the same architectural pattern as `FrequencyStore`.

---

## Goals / Non-Goals

**Goals:**
- Show a modal confirmation dialog when the last TX begins (`Tx73` / `TxRr73`).
- Allow operator to enrich the record (Name, Tx Power, Comments, Prop Mode, Exch Sent, Exch Rcvd, Operator override) and confirm or discard.
- Only write ADIF when operator explicitly confirms (OK).
- Persist "Retain" field values (`TxPower`, `Comment`, `PropMode`) across QSOs via `TxConfig`.
- Feature-toggle (`tx.qsoConfirmation`, default `true`); when `false`, existing auto-log behaviour is fully preserved.
- `PropModeStore`: protocol-aware, seeded FT8 subset, same GET/POST API pattern as frequencies.
- `QsoEndUtc` aligned with WSJT-X convention (current cycle-start floor, not wall-clock completion).

**Non-Goals:**
- Settings UI for managing the prop-modes list (deferred; frequencies page pattern can be copied later).
- Auto-submission on timeout (no timeout — dialog stays open indefinitely, as in WSJT-X).
- Modification of the existing ADIF write path when `tx.qsoConfirmation = false`.
- Multi-browser synchronisation of the confirmation dialog (single-operator assumption).
- Changes to the state machine beyond emitting the `qsoReview` event and skipping the auto-ADIF call.

---

## Decisions

### D1 — Browser owns the QSO record; POST sends it back in full

**Decision:** The `qsoReview` WS event carries the complete QSO record (all fields the daemon knows at Tx73/TxRr73 entry). The browser enriches it and sends it back via `POST /api/v1/tx/log-qso`. The daemon writes ADIF from the POST body without consulting any in-memory pending state.

**Alternatives considered:**

- *Daemon stores a pending record, POST sends only enrichments.* Requires the daemon to hold record state across what is already a completed state-machine transition; creates concurrency ambiguity if a second QSO completes before the first is confirmed. Rejected.
- *Browser sends only enrichment fields; daemon merges with its internal record.* Same problem: daemon must retain state post-Idle. Rejected.

**Why D1:** The daemon is already at Idle when the operator clicks OK. It has no in-flight state to protect. A self-contained POST is simple, stateless, and naturally handles the "QSO completed but operator still deciding" case.

---

### D2 — `qsoReview` event fires at last-TX state entry, not at `QsoComplete`

**Decision:** `PublishQsoReview(...)` is called inside `SetStateAndNotify` (or immediately before `TransmitAsync`) when entering `QsoState.Tx73` (answerer) or `CallerState.TxRr73` (caller). `QsoEndUtc` is calculated at that moment as `floor(UtcNow, 15 s)` — the current FT8 cycle start.

**Rationale:** This exactly replicates WSJT-X behaviour: the dialog appears the instant the final TX keying begins, giving the operator the full ~12.64-second transmission window. Firing at `QsoComplete` (after TX) is too late — the operator would see the dialog only after the on-air exchange is fully done.

The cycle-start floor (e.g., 11:08:30 for a TX beginning at 11:08:37) matches WSJT-X's `TIME_OFF` field convention and is accurate to the FT8 cycle boundary that radio loggers expect.

---

### D3 — Dialog is a native `<dialog>` element opened with `.showModal()`

**Decision:** The confirmation dialog is an HTML `<dialog>` element opened via `dialog.showModal()`. The close (`×`) button is hidden via CSS. Cancel is wired to `dialog.close()` with no POST. The `Escape` key's default close behaviour is suppressed with `e.preventDefault()` on the `cancel` event.

**Alternatives considered:**

- *Custom overlay div.* Requires manually managing focus-trap, `aria-modal`, keyboard handling, and backdrop. More code for equivalent behaviour. Rejected.
- *New browser tab / window.* Breaks operator workflow. Rejected.

**Why D3:** Native `<dialog>` provides a browser-managed focus trap, `::backdrop` pseudo-element for the overlay, `showModal()` for stacking context, and correct `aria-modal` semantics at zero library cost. Already the platform-standard approach for modal dialogs in modern web UIs.

---

### D4 — Retain values stored in `TxConfig`, read from the `qsoReview` event

**Decision:** `TxConfig` gains three nullable string fields: `RetainedTxPower`, `RetainedComment`, `RetainedPropMode`. These are serialised to `appconfig.json` via the existing `IConfigStore` / `SaveAsync` path. The `qsoReview` WS event carries the current retained values; the browser pre-fills the relevant fields on dialog open. When the operator clicks OK, the POST body includes `RetainTxPower`, `RetainComment`, `RetainPropMode` booleans; the `POST /api/v1/tx/log-qso` handler reads current config, updates the three retained fields if flagged, and calls `SaveAsync`.

**Alternatives considered:**

- *Browser `localStorage`.* Per-browser persistence; does not survive a browser switch or remote access. Less consistent than other settings. Rejected.
- *Separate retained-fields endpoint.* Adds an endpoint for what is structurally just three config fields. Rejected.

**Why D4:** `TxConfig` already owns operator-level TX preferences (`Callsign`, `Grid`, `RetryCount`, etc.). Retained log fields are the same category — operator preferences that survive restart. The `SaveAsync` path is already atomic-write + DI-registered.

---

### D5 — `PropModeStore` mirrors `FrequencyStore` exactly

**Decision:** `PropModeStore` is a new class in `OpenWSFZ.Daemon` with a `PropModeEntry { string Protocol, string Value, string Description }` record, a `prop-modes.json` backing file, and a default seed populated on first run. `GET /api/v1/prop-modes` and `POST /api/v1/prop-modes` are added to `WebApp.cs` following the frequencies endpoint pattern. The browser dialog filters entries by `protocol === activeProtocol` ('FT8') when populating the dropdown.

**Rationale:** The frequencies pattern is already proven and tested. Replicating it ensures no new architectural surface is introduced. Future protocols (FT4, WSPR) simply add entries with their own `Protocol` tag; the dialog dropdown picks up the correct subset automatically.

**Default FT8 seed (10 entries):** blank (not specified), TR, ES, F2, EME, MS, TEP, SAT, LOS, INTERNET.

---

### D6 — `qsoConfirmation = false` is a strictly conservative off-path

**Decision:** When `tx.qsoConfirmation = false`, the code path in `QsoAnswererService` and `QsoCallerService` is exactly the current code: `AppendQsoAsync` is called at `QsoComplete`, the `qsoReview` event is **not** emitted, and the browser shows nothing. No other behaviour changes.

**Rationale:** Any operator who does not upgrade their config (or explicitly sets `false`) must see identical behaviour to the pre-change build. This is a strict compatibility guarantee.

---

## Risks / Trade-offs

**R1 — Browser closed / disconnected while dialog is open → QSO not logged**
If the operator closes the browser tab or loses connectivity after the `qsoReview` event is emitted but before clicking OK, the QSO is lost. This matches WSJT-X's behaviour (Cancel = no log). Mitigation: the dialog is opened the moment TX begins — the operator has the full TX window plus unlimited time thereafter; disconnection during the 12-second TX is unlikely. No mitigation beyond operator awareness.

**R2 — `POST /api/v1/tx/log-qso` called for a stale or wrong QSO**
If the operator has two browser tabs and one tab still has an old dialog open, they could POST a stale record after a new QSO has completed. The POST endpoint is a stateless ADIF append (no validation of temporal ordering); both records are written. Mitigation: single-operator assumption; two active browser tabs is an unusual configuration. A `correlationId` could be added to the event and POST body in future if needed.

**R3 — `dialog.showModal()` may be called while a dialog is already open**
If two QSOs complete in very rapid succession (pathological edge case — the state machine prevents concurrent QSOs), the browser could attempt to open a second modal while the first is still open. Mitigation: guard in the `qsoReview` handler — if `dialog.open` is true, do not call `showModal()` again; instead queue or discard (log a warning to console).

**R4 — `TxConfig` STJ source-gen `init` property default for `QsoConfirmation`**
Per lesson 6 in MEMORY.md: STJ source-gen ignores C# `init` property defaults for missing JSON fields — `bool` absent from JSON deserialises to `false`, not `true`. Since `QsoConfirmation` defaults to `true`, a `[JsonConstructor]`-annotated constructor with `bool qsoConfirmation = true` is required to ensure first-run / old-config behaviour is correct.

**R5 — Prop Mode dropdown empty if `GET /api/v1/prop-modes` fails**
If the fetch fails, the dialog renders with an empty dropdown. Mitigation: seed is written to `prop-modes.json` on first run (same guarantee as frequencies); network failure on an already-running daemon is transient. Browser falls back to showing only the blank "Not specified" option hardcoded in the `<option>` element.

---

## Migration Plan

1. **Config migration (automatic):** Old `appconfig.json` files without `tx.qsoConfirmation` will deserialise `QsoConfirmation` as `false` due to STJ default-for-missing-field. This is incorrect (we want `true`). The `[JsonConstructor]` fix (R4) sets the default to `true`, so old configs get confirmation enabled on first start after upgrade. This is the correct operator experience.
2. **`prop-modes.json` creation:** If `prop-modes.json` does not exist on startup, `PropModeStore` writes the default FT8 seed (same pattern as `frequencies.json`). No manual migration needed.
3. **Rollback:** Set `tx.qsoConfirmation = false` in config to restore the pre-change silent auto-log behaviour. The `POST /api/v1/tx/log-qso` endpoint is additive; no existing endpoints are modified.

---

## Open Questions

None. All design decisions settled during exploration (2026-06-27).
