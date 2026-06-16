## ADDED Requirements

### Requirement: Settings page — General tab

The Settings page SHALL contain a "General" tab inserted as the **first** tab, before the existing Radio tab. The tab SHALL contain the operator's station-identity and TX behaviour fields: callsign, Maidenhead grid locator, watchdog timer, and retry count. These fields are moved here from the Radio tab's TX fieldset (see MODIFIED Requirements below).

The General tab SHALL participate in the same Save / unsaved-changes flow as all other tabs.

#### Scenario: General tab is present and is the first tab

- **WHEN** a browser loads `GET /settings.html`
- **THEN** the DOM SHALL contain a tab button labelled "General" with `aria-controls="tab-general"` and a corresponding tab panel with `id="tab-general"`
- **AND** the General tab button SHALL be the first tab button in the tab list (leftmost in the rendered order)

#### Scenario: General tab is active by default on page load

- **WHEN** a browser loads `GET /settings.html`
- **THEN** the General tab panel SHALL be the initially visible panel and its tab button SHALL have `aria-selected="true"`

#### Scenario: General tab pre-fills callsign from config

- **WHEN** a browser loads `GET /settings.html` and `GET /api/v1/config` returns `{ "tx": { "callsign": "Q9XYZ", ... } }`
- **THEN** the `<input id="general-callsign">` element SHALL display `Q9XYZ` before the operator edits anything

#### Scenario: General tab pre-fills grid from config

- **WHEN** a browser loads `GET /settings.html` and `GET /api/v1/config` returns `{ "tx": { "grid": "IO91", ... } }`
- **THEN** the `<input id="general-grid">` element SHALL display `IO91` before the operator edits anything

#### Scenario: General tab pre-fills watchdogMinutes from config

- **WHEN** a browser loads `GET /settings.html` and `GET /api/v1/config` returns `{ "tx": { "watchdogMinutes": 4, ... } }`
- **THEN** the `<input id="general-watchdog-minutes">` element SHALL display `4` before the operator edits anything

#### Scenario: General tab pre-fills retryCount from config

- **WHEN** a browser loads `GET /settings.html` and `GET /api/v1/config` returns `{ "tx": { "retryCount": 3, ... } }`
- **THEN** the `<input id="general-retry-count">` element SHALL display `3` before the operator edits anything

#### Scenario: Save includes General tab fields in tx object

- **WHEN** the operator changes any General tab field and clicks Save
- **THEN** `POST /api/v1/config` SHALL include a `tx` object containing the values of `general-callsign`, `general-grid`, `general-watchdog-minutes`, and `general-retry-count`, alongside the `tx.autoAnswer` value read from the Radio tab

#### Scenario: Saving without changes does not trigger clamp warnings

- **WHEN** the operator opens the Settings page, makes no changes, and clicks Save
- **THEN** `POST /api/v1/config` SHALL submit `tx.watchdogMinutes` ≥ 1 and `tx.retryCount` ≥ 1, and the daemon SHALL NOT log a WRN clamp message

#### Scenario: General tab fields participate in dirty-state tracking

- **WHEN** the operator changes any field in the General tab
- **THEN** the unsaved-changes indicator SHALL become visible, consistent with the behaviour for all other settings controls


## MODIFIED Requirements

### Requirement: Settings page — TX fieldset on Radio tab

The Radio tab SHALL contain an "FT8 TX" fieldset containing **only** the auto-answer enable/disable checkbox (`id="tx-auto-answer"`). The callsign, grid, watchdog minutes, and retry count fields have been moved to the General tab (see ADDED Requirements above) and SHALL NOT appear in the TX fieldset.

The TX fieldset legend SHALL read "FT8 TX" (or equivalent concise label).

#### Scenario: TX fieldset contains only the auto-answer checkbox

- **WHEN** a browser loads `GET /settings.html`
- **THEN** the TX fieldset (`id="tx-settings"`) SHALL contain a `<input type="checkbox" id="tx-auto-answer">` element
- **AND** the TX fieldset SHALL NOT contain inputs with IDs `tx-callsign`, `tx-grid`, `tx-watchdog-minutes`, or `tx-retry-count`

#### Scenario: Auto-answer checkbox pre-fills from config

- **WHEN** a browser loads `GET /settings.html` and `GET /api/v1/config` returns `{ "tx": { "autoAnswer": true, ... } }`
- **THEN** the `<input id="tx-auto-answer">` checkbox SHALL be checked

#### Scenario: Save includes autoAnswer from Radio tab

- **WHEN** the operator changes the auto-answer checkbox and clicks Save
- **THEN** `POST /api/v1/config` SHALL include `tx.autoAnswer` reflecting the current checkbox state, alongside the General tab's callsign, grid, watchdog, and retry fields


## MODIFIED Requirements

### Requirement: Settings page pre-fills TX numeric fields from loaded config

**This requirement is superseded by the General tab pre-fill scenarios above.** The element IDs `tx-watchdog-minutes` and `tx-retry-count` no longer exist; the fields are now `general-watchdog-minutes` and `general-retry-count` on the General tab. The behavioural contract (pre-populate from config, save without changes does not trigger clamp warnings) is preserved in the ADDED requirement above.
