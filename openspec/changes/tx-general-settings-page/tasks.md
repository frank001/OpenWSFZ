## 1. HTML — General tab

- [x] 1.1 Add "General" tab button to the `<div class="settings-tabs">` tablist as the **first** button (`aria-controls="tab-general"`, `id="tab-btn-general"`), with `aria-selected="true"` and class `active`; demote the Radio tab button to `aria-selected="false"` and remove `active`
- [x] 1.2 Add General tab panel (`<div id="tab-general" class="settings-tab-panel active" role="tabpanel" aria-labelledby="tab-btn-general">`) immediately before `<div id="tab-radio">`; remove `active` from the Radio tab panel
- [x] 1.3 Move the callsign `field-group` div (currently inside `#tx-settings`) into the General panel; rename element ID from `tx-callsign` to `general-callsign`
- [x] 1.4 Move the grid `field-group` div into the General panel; rename element ID from `tx-grid` to `general-grid`
- [x] 1.5 Move the watchdog-minutes `field-group` div into the General panel; rename element ID from `tx-watchdog-minutes` to `general-watchdog-minutes`
- [x] 1.6 Move the retry-count `field-group` div into the General panel; rename element ID from `tx-retry-count` to `general-retry-count`
- [x] 1.7 Update the TX fieldset legend to "FT8 TX"; confirm it now contains only the auto-answer checkbox `field-group`

## 2. JavaScript — settings.js

- [x] 2.1 In `loadConfig()`, update the four assignments that set callsign/grid/watchdog/retry to use `general-callsign`, `general-grid`, `general-watchdog-minutes`, `general-retry-count`
- [x] 2.2 In `saveConfig()` (or equivalent save handler), update the four reads that retrieve callsign/grid/watchdog/retry to use the new element IDs
- [x] 2.3 In `snapshotForm()` (dirty-state baseline capture), update any references to the old IDs to the new IDs; confirm the snapshot includes all four General tab fields
- [x] 2.4 Verify the tab-switching click handler (if any) correctly initialises the General tab as the active default; confirm no hard-coded reference to `tab-radio` as the initial active tab

## 3. Spec update

- [x] 3.1 Run `openspec sync` (or equivalent) to merge the delta spec into `openspec/specs/web-frontend/spec.md`

## 4. Manual verification

- [ ] 4.1 Open `settings.html` in a browser — confirm General tab is selected by default and all four fields (callsign, grid, watchdog minutes, retry count) are pre-populated from the current config
- [ ] 4.2 Confirm the Radio tab → TX fieldset shows only the auto-answer checkbox; no callsign/grid/watchdog/retry inputs remain there
- [ ] 4.3 Change each General tab field — confirm the unsaved-changes indicator appears
- [ ] 4.4 Click Save — confirm `POST /api/v1/config` body contains the correct values for all five `tx.*` fields and the daemon log shows **no** WRN clamp messages
- [ ] 4.5 Reload the page — confirm the values saved in 4.4 are correctly pre-populated on reload

## 5. Regression gate

- [x] 5.1 Run `dotnet build OpenWSFZ.slnx -c Release` — confirm 0 errors, 0 warnings
- [x] 5.2 Run `dotnet test OpenWSFZ.slnx -c Release` — confirm all existing tests pass (no new tests required; this change has no backend behaviour change)
