## Why

The application currently has no concept of a per-protocol frequency list: the operator must type dial frequencies manually, and there is no convenient way to switch bands from the main UI. HAM operators expect to be able to select a working frequency from a curated list — exactly as WSJT-X provides — and have the rig tune to it automatically when CAT is active. This change introduces that capability as a first-class feature, using WSJT-X's standard FT8 frequency list as the default so the application is useful out-of-the-box.

Additionally, the existing CAT abstraction (`IRadioConnection`) is read-only by design (p16). Frequency selection from the main GUI requires the ability to _command_ the rig to a new frequency, so the read-only restriction must be lifted for this single operation.

## What Changes

- **NEW** `frequencies.json` committed to the repository as a project deliverable containing the full WSJT-X-equivalent default FT8 working frequencies (15 entries, 160 m through 70 cm)
- **NEW** `IFrequencyStore` service: loads `frequencies.json` at startup; writes default file when absent; exposes the in-memory list to the rest of the system
- **NEW** `GET /api/v1/frequencies` — returns the full frequency entry list as a JSON array
- **NEW** `POST /api/v1/frequencies` — accepts and persists an updated frequency list
- **NEW** `POST /api/v1/tune` — commands the rig (CAT enabled) or updates the manual dial frequency config (CAT disabled), returns the new effective frequency
- **BREAKING** `IRadioConnection` gains `SetDialFrequencyMhzAsync(double, CancellationToken)` — this amends the p16 read-only restriction for frequency only; all implementors (`SerialCatConnection`, `RigctldConnection`) and all test doubles must be updated
- **NEW** Settings page *Frequencies* tab (4th tab): table-based CRUD for the frequency list, participates in the existing Save/unsaved-changes flow
- **MODIFIED** Main GUI `#dial-freq` element: when CAT is active (Connected or Connecting), renders as a `<select>` dropdown populated from the active-protocol frequency list; reverts to static text when CAT is disabled or in error; selecting a frequency calls `POST /api/v1/tune`

## Capabilities

### New Capabilities

- `frequency-management`: Frequency list data model, `IFrequencyStore` service, `frequencies.json` file lifecycle (default creation, load, save), and REST endpoints for list CRUD and rig tuning

### Modified Capabilities

- `cat-control`: `IRadioConnection` interface gains `SetDialFrequencyMhzAsync`; `SerialCatConnection` sends `FA<11-digit-Hz>;`; `RigctldConnection` sends `\set_freq <Hz>\n`; the p16 no-set-commands restriction is explicitly amended for frequency
- `web-frontend`: Settings page gains a Frequencies tab; main-page `#dial-freq` element gains conditional dropdown behaviour driven by CAT state
- `web-server`: Two new REST endpoints (`GET /api/v1/frequencies`, `POST /api/v1/frequencies`) and one new action endpoint (`POST /api/v1/tune`)
- `configuration`: `IFrequencyStore` joins the DI container alongside `IConfigStore`; `frequencies.json` path resolution follows the same convention as `app.json`

## Impact

- **`OpenWSFZ.Abstractions`** — `IRadioConnection` interface change (breaking for all implementors and mocks)
- **`OpenWSFZ.Rig`** — `SerialCatConnection` and `RigctldConnection` gain `SetDialFrequencyMhzAsync`
- **`OpenWSFZ.Daemon`** — new `IFrequencyStore` / `FrequencyStore` service registered in DI; `POST /api/v1/tune` handler touches `CatPollingService` or `IConfigStore` depending on CAT state
- **`OpenWSFZ.Web`** — three new API endpoint handlers
- **`web/settings.html`** and **`web/js/settings.js`** — Frequencies tab added; tab-count changes from 3 to 4
- **`web/index.html`** and **`web/js/main.js`** — `#dial-freq` element gains conditional dropdown logic driven by `cat_status` WebSocket events
- **`frequencies.json`** (new file at repository root, alongside the application) — committed as deliverable
- **Tests** — all existing test doubles for `IRadioConnection` must implement the new method; new tests required for `FrequencyStore`, tune endpoint, and `SetDialFrequencyMhzAsync` implementations
