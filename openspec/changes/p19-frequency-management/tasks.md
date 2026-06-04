## 1. Requirements and data model

- [x] 1.1 Add FR-042 (frequency list configuration), FR-043 (frequencies settings tab), FR-044 (frequency selector in main GUI), and FR-045 (CAT frequency set) to `REQUIREMENTS.md`; bump document version to 1.18
- [x] 1.2 Add `FrequencyEntry` record to `OpenWSFZ.Abstractions` with properties `Protocol` (string), `FrequencyMHz` (double), `Description` (string)
- [x] 1.3 Add `IFrequencyStore` interface to `OpenWSFZ.Abstractions` with `IReadOnlyList<FrequencyEntry> Entries` property and `Task SaveAsync(IReadOnlyList<FrequencyEntry>, CancellationToken)` method

## 2. frequencies.json default file

- [x] 2.1 Add `FrequencyDefaults` static class to `OpenWSFZ.Daemon` containing the 15-entry default FT8 list (1.840 through 432.065 MHz) as a `IReadOnlyList<FrequencyEntry>` constant
- [x] 2.2 Create the committed `frequencies.json` file at the repository root (same directory as `app.json` when running locally) containing the 15-entry default FT8 list in the `{ "entries": [...] }` wrapper format

## 3. FrequencyStore implementation

- [x] 3.1 Implement `FrequencyStore : IFrequencyStore` in `OpenWSFZ.Daemon` — constructor accepts a resolved file path; `LoadAsync()` reads and deserialises `frequencies.json`, writes defaults if absent, falls back to in-memory defaults and logs Error if file is malformed; `SaveAsync` writes atomically (temp-file-then-rename)
- [x] 3.2 Register `IFrequencyStore` / `FrequencyStore` as a singleton in `Program.cs` DI configuration; resolve the `frequencies.json` path using the same data-directory logic as `IConfigStore`
- [x] 3.3 Call `FrequencyStore.LoadAsync()` at daemon startup (before web host starts) alongside the existing `IConfigStore` initialisation

## 4. IRadioConnection — add SetDialFrequencyMhzAsync

- [x] 4.1 Add `Task SetDialFrequencyMhzAsync(double frequencyMHz, CancellationToken cancellationToken = default)` to `IRadioConnection` in `OpenWSFZ.Abstractions`
- [x] 4.2 Implement `SetDialFrequencyMhzAsync` in `SerialCatConnection`: convert MHz to Hz (round to nearest integer), zero-pad to 11 digits, write `FA<11-digit-Hz>;` to the serial port (no read-back)
- [x] 4.3 Implement `SetDialFrequencyMhzAsync` in `RigctldConnection`: convert MHz to Hz integer, send `\set_freq <Hz>\n` to the TCP socket (no read-back)
- [x] 4.4 Update all `IRadioConnection` test doubles / fakes in `OpenWSFZ.Rig.Tests` and `OpenWSFZ.Daemon.Tests` to implement the new method (NSubstitute auto-stubs; no manual updates required)

## 5. REST API — frequency list endpoints

- [x] 5.1 Add `GET /api/v1/frequencies` handler: returns `IFrequencyStore.Entries` serialised as a JSON array
- [x] 5.2 Add `POST /api/v1/frequencies` handler: deserialises the request body as a list of `FrequencyEntry`, validates (returns 400 on malformed), calls `IFrequencyStore.SaveAsync`, returns the saved list with HTTP 200

## 6. REST API — tune endpoint

- [x] 6.1 Add `POST /api/v1/tune` handler: deserialises `{ "frequencyMHz": number }` (returns 400 if missing/invalid/negative); if `ICatState.Status` is `Connected` or `Connecting` call `ICatTuner.SetDialFrequencyAsync` (which calls `IRadioConnection.SetDialFrequencyMhzAsync` and updates `ICatState` optimistically via `CatPollingService`); otherwise update `AppConfig.DecodeLog.DialFrequencyMHz` and call `IConfigStore.SaveAsync()`; return `{ "effectiveFrequencyMHz": <number> }` with HTTP 200; return HTTP 502 if `SetDialFrequencyAsync` throws

## 7. Settings page — Frequencies tab

- [x] 7.1 Add a fourth tab button `<button ... id="tab-btn-frequencies" aria-controls="tab-frequencies">Frequencies</button>` to the tab bar in `settings.html`, after the *Advanced* tab
- [x] 7.2 Add the `<div id="tab-frequencies" ...>` panel containing the frequency table (columns: Protocol, Frequency MHz, Description, Delete) and the "Add frequency" button
- [x] 7.3 In `settings.js`, on page load call `GET /api/v1/frequencies` and render the table rows; wire the Add button to append a new `FT8 / 0.000 / ""` row
- [x] 7.4 Wire each Delete button to remove its row from the DOM and mark the form dirty (FR-040)
- [x] 7.5 Include the serialised frequency table in the FR-040 dirty-state JSON snapshot so changes to this tab show the unsaved-changes indicator
- [x] 7.6 On Save, issue `POST /api/v1/frequencies` with the current table contents (in parallel with the existing `POST /api/v1/config`); handle 400/network errors with the existing feedback element

## 8. Main GUI — conditional #dial-freq selector

- [x] 8.1 On page load in `main.js`, call `GET /api/v1/frequencies` and cache the response; filter the cache to `protocol === "FT8"` for use in the dropdown
- [x] 8.2 Implement `renderDialFreqSpan(freqMHz)` — creates/replaces `#dial-freq` with a `<span>` displaying the formatted frequency (existing text behaviour)
- [x] 8.3 Implement `renderDialFreqSelect(freqMHz)` — creates/replaces `#dial-freq` with a `<select>` populated from the cached FT8 frequency list; selects the option closest to `freqMHz`; attaches a `change` handler that calls `POST /api/v1/tune` and updates the display on success
- [x] 8.4 In the `cat_status` and `status` WebSocket event handlers, call `renderDialFreqSelect` when CAT status is `Connected` or `Connecting`, and `renderDialFreqSpan` when status is `Disabled`, `Error`, or absent — triggering the transition in place without a page reload

## 9. Unit tests

- [x] 9.1 `FrequencyStore` tests (prefix `FR-042:`): default file written when absent; existing file loaded; malformed file falls back to defaults and does not overwrite; `SaveAsync` atomically updates in-memory list and file; unknown JSON fields preserved on round-trip
- [x] 9.2 `SerialCatConnection.SetDialFrequencyMhzAsync` tests (prefix `FR-045:`): correct `FA<11-digit-Hz>;` string written for representative frequencies (7.074 MHz, 14.074 MHz, 0.001 MHz); method does not await a read-back
- [x] 9.3 `RigctldConnection.SetDialFrequencyMhzAsync` tests (prefix `FR-045:`): correct `\set_freq <Hz>\n` string sent for representative frequencies; method does not await a read-back
- [x] 9.4 `POST /api/v1/frequencies` API tests (prefix `FR-042:`): valid list returns 200 and persists; malformed body returns 400; empty array accepted
- [x] 9.5 `POST /api/v1/tune` API tests (prefix `FR-045:`): CAT-active path calls `SetDialFrequencyAsync` and returns 200; CAT-disabled path updates config and returns 200; negative frequency returns 400; `SetDialFrequencyAsync` throws returns 502
- [x] 9.6 Add any new requirement IDs (FR-042 through FR-045) to `traceability-debt.md` for any IDs not yet covered by tests at the time of the PR (per NFR-020)

## 10. Final validation

- [x] 10.1 Run `dotnet build -c Release` — zero errors, zero warnings
- [x] 10.2 Run `dotnet test -c Release --no-build` — all tests pass
- [ ] 10.3 **Defect fix gate (S2 — WebSocket shutdown race):** With the browser tab open and the WebSocket connected, stop the daemon (Ctrl+C). Confirm: (a) the process exits cleanly within ~5 seconds; (b) Task Manager shows no lingering `dotnet.exe` instance from the stopped daemon after that window; (c) start the daemon again — the browser reconnects successfully. This verifies the `503` shutdown gate in `WebApp.cs` prevents browser reconnects from holding up graceful drain. *Block merge until this passes.*
- [ ] 10.4 Manual smoke: start the daemon, open the browser, verify the Frequencies tab lists the 15 default FT8 entries; add and delete a row; save; verify `frequencies.json` is updated on disk
- [ ] 10.5 Manual smoke (CAT path): enable CAT in Settings; verify `#dial-freq` becomes a dropdown on the main page; select a different frequency; verify the rig tunes (or that `app.json` `dialFrequencyMHz` updates when CAT is disabled)
- [ ] 10.6 Commit, push, open PR to `main`, confirm CI green
- [ ] 10.7 **Defect fix gate (F-003 — CatPollingService double dispose):** Start the daemon, stop it cleanly (Ctrl+C). Confirm no `ObjectDisposedException` in console output and no lingering `dotnet.exe` process. *Block merge until this passes.*
- [ ] 10.8 **Defect fix gate (F-004/F-005 — frequency dropdown race + width):** Enable CAT in Settings, reload the main page. Confirm: (a) `#dial-freq` shows all 15 FT8 frequency options (not just one); (b) the dropdown does not stretch across the full status bar. *Block merge until this passes.*
- [x] 10.9 Fix F-006 (Root A–D): consume rigctld `RPRT 0` acknowledgement in `RigctldConnection.SetDialFrequencyMhzAsync`; add `SemaphoreSlim _connectionLock` to `CatPollingService` to serialise concurrent poll and set I/O; promote `_lastBroadcastFreq` / `_lastBroadcastStatus` to class fields so the poll loop can publish frequency-correction events when the rig silently ignores a tune command; update stale XML doc comments in `SerialCatConnection` and `RigctldConnection`.
- [ ] 10.10 **Defect fix gate (F-006 — tune command):** With CAT connected: select a different frequency from the `#dial-freq` dropdown; confirm the rig tunes to the selected frequency; confirm no `Error` badge appears and no exceptions in the daemon console. With CAT disabled: select a frequency via the CAT-less path; confirm `app.json` `dialFrequencyMHz` updates on disk. *Block merge until this passes.*
