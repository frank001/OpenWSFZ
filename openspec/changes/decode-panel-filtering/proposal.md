## Why

`#decodes-panel` shows every decode the daemon produces, with no way for the operator to narrow
what they're looking at — a DX-hunter wanting only EU stations they haven't worked, or an
operator running a local net who only cares about their own country, has to visually filter by
eye while decodes scroll past. Separately, and more importantly: when TX automation
(`QsoAnswererService`/`QsoCallerService`) is enabled, it currently has no way to respect any such
preference even if one existed in the GUI — it reads decodes from its own server-side channel,
completely decoupled from what the operator has chosen to look at. An operator focused on EU
DXCC-hunting has no way today to stop the automation from auto-answering a station they'd
explicitly rather ignore.

## What Changes

- **New per-column filter popup on `#decodes-table`**, triggered by clicking a column header, for
  the five worked-before columns introduced by `qso-confirmation-band-awareness` (Ctc/DXCC/Cnt/
  CQz/ITz — this change depends on that one). Each popup has two independent, combinable
  sections, both defaulting to "everything selected" (no filtering):
  - **Attribute allow-list**: which actual values of this dimension are shown at all (e.g. which
    DXCC entities, which continents, which zone numbers) — opt out via unchecking in a
    multi-select popup.
  - **Worked-before filter**: three-way, matching the tri-state model from
    `qso-confirmation-band-awareness` — show/hide by `Never` / `DifferentBand` / `ThisBand`.
- **Filter state is daemon-owned, ephemeral, and shared** — not persisted to `TxConfig`'s JSON or
  any config file, resets on daemon restart, and is not scoped per browser tab: if multiple
  WebSocket clients are connected simultaneously, the last one to change the filter is
  authoritative for all of them, mirroring how `tx.autoAnswer` already works today as shared,
  non-tab-scoped daemon state.
- **Automation gating (the primary driver of this change)**: `QsoAnswererService` and
  `QsoCallerService` consult the active filter at the single moment they choose which candidate
  to engage — `QsoAnswererService.Idle` scanning a decode batch for the first CQ to answer skips
  any CQ whose callsign is currently filtered out and engages the first non-filtered one instead;
  `QsoCallerService.WaitAnswer` (in `CallerPartnerSelectMode.First`) does the same over responders
  to our own CQ. Once a QSO is actually engaged, the filter becomes irrelevant to that QSO — it is
  **not** re-checked continuously and does **not** abort an in-progress QSO if the filter changes
  mid-QSO; the operator's existing Abort/Stop controls remain the only lever for that case. This
  is a deliberately narrow, single-decision-point hook per service, not a pervasive filter check.

## Capabilities

### New Capabilities

- `decode-panel-filtering`: daemon-owned, ephemeral, shared filter state (per-dimension attribute
  allow-list + worked-before tri-state selection) consulted by both QSO controller services at
  their engagement-decision point, and exposed via API for the frontend popup UI to read/write.

### Modified Capabilities

- `web-frontend`: `#decodes-table` column headers become clickable, opening the new filter popup;
  filtered-out rows are hidden from the rendered table.
- `qso-answerer`: `QsoAnswererService`'s CQ-selection logic (`Idle` state) gains a filter check —
  skip filtered-out CQs when choosing which to answer.
- `qso-caller`: `QsoCallerService`'s responder-selection logic (`WaitAnswer` state,
  `CallerPartnerSelectMode.First`) gains the same filter check over responders.

## Impact

- **Backend**: new `IDecodeFilterStore`-equivalent (or similar; naming left to design.md) holding
  the daemon-owned filter state, a new API surface for the frontend to read/write it (GET current
  filter, PATCH/POST to change it), and a shared filter-evaluation helper both
  `QsoAnswererService` and `QsoCallerService` call at their respective engagement-decision points.
  No persistence layer — purely in-memory, reset on restart.
- **Frontend**: `web/index.html` (clickable column headers), `web/js/main.js` (popup UI, row
  hiding logic, API calls to read/write filter state), `web/css/app.css` (popup styling).
- **Dependency**: requires `qso-confirmation-band-awareness` (proposed alongside this change, not
  yet implemented) — the worked-before filter section's three-way semantics and the five
  filterable dimensions (Ctc/DXCC/Cnt/CQz/ITz) don't exist without it. This change should not be
  implemented before that one lands, though the two were proposed together for a combined view of
  the full feature.
- **No breaking changes** to any existing WebSocket payload field or persisted config shape — the
  filter is new, additive, in-memory-only state.
