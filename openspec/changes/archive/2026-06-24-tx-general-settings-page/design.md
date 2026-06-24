## Context

The Settings page currently has four tabs: Radio, Logging, Advanced, Frequencies. The Radio tab contains two fieldsets: a CAT rig connection block and an "FT8 auto-answer (TX)" block. The TX block holds five fields: callsign, grid, auto-answer checkbox, watchdog minutes, and retry count.

Callsign and grid are station identity — they are not specific to the auto-answerer and will be needed for every future TX capability (caller role, manual CQ, etc.). Watchdog and retry count are behavioural tuning parameters that similarly apply to the broader TX subsystem. Grouping them with the auto-answer toggle, inside a Radio tab whose primary subject is audio hardware and serial ports, is an organisational accident of v1 scope constraints.

The fix is a General tab — the first tab, reached immediately on opening Settings — containing the four operator-level fields. The Radio tab's TX fieldset is reduced to the one remaining field that is genuinely radio-operation-specific: the auto-answer enable toggle.

## Goals / Non-Goals

**Goals:**
- Add a "General" tab as the first tab in `settings.html`
- Move callsign, grid, watchdog minutes, and retry count to the General tab
- Reduce the TX fieldset on the Radio tab to the auto-answer checkbox only
- Update `settings.js` so all load/save/snapshot operations use the new element IDs
- Update the `web-frontend` living spec to document the General tab

**Non-Goals:**
- Any changes to `AppConfig`, `TxConfig`, or any C# code
- Any changes to REST endpoints
- Any changes to test code (no behaviour change → no new test scenarios required)
- Any changes to the Logging, Advanced, or Frequencies tabs

## Decisions

### D1 — General tab is the first tab

Callsign and grid are the first things a new operator must configure before any TX capability can be used. Placing General as the first tab (before Radio) ensures these fields are found immediately rather than buried inside a hardware-oriented tab. Tab order: **General → Radio → Logging → Advanced → Frequencies**.

### D2 — Element IDs are renamed, not aliased

The four moved fields receive new element IDs that reflect their new home:

| Old ID | New ID |
|---|---|
| `tx-callsign` | `general-callsign` |
| `tx-grid` | `general-grid` |
| `tx-watchdog-minutes` | `general-watchdog-minutes` |
| `tx-retry-count` | `general-retry-count` |

Aliasing the old IDs (e.g. via `document.getElementById` lookup in both places) would leave dead HTML in the Radio tab and create confusion about the canonical element. A clean rename costs marginally more in `settings.js` changes but produces an unambiguous DOM.

### D3 — Auto-answer checkbox stays on the Radio tab

`autoAnswer` is the on/off switch for the transmitter. It belongs alongside the output audio device and CAT settings — the hardware-adjacent controls — rather than next to station identity. The fieldset legend will be updated from "FT8 auto-answer (TX)" to simply "TX" or a similar concise label now that it contains only the one control.

## Risks / Trade-offs

**[Risk] Operator bookmarks or muscle-memory for the Radio tab may be disrupted** → Mitigation: The Radio tab still exists and still contains the auto-answer toggle; only the four identity/tuning fields have moved. The disruption is minimal. No external API or config format changes.

**[Risk] `settings.js` dirty-state snapshot omits a moved field** → Mitigation: The developer must update `snapshotForm()` to reference the new element IDs. Tasks checklist includes an explicit verification step: open Settings, change each moved field, confirm the unsaved-changes indicator appears.

## Migration Plan

1. Add General tab button and panel to `settings.html` (before the Radio tab button).
2. Move the four field-group divs from the TX fieldset into the General panel.
3. Rename element IDs per D2.
4. Update TX fieldset legend; the fieldset now contains only the auto-answer checkbox.
5. Update `settings.js`: `loadConfig()` assigns callsign/grid/watchdog/retry to new IDs; `saveConfig()` reads from new IDs; `snapshotForm()` references new IDs.
6. Manual smoke-test: load Settings → verify all five TX fields appear and pre-populate correctly; change each → verify unsaved-changes indicator; save → verify no clamp warnings in daemon log.

No rollback complexity — all changes are in static files (`settings.html`, `settings.js`). Reverting is a git revert.
