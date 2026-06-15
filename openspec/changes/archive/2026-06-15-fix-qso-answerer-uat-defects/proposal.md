## Why

Two defects were found during UAT of the `ft8-qso-answerer-v1` feature (2026-06-15). Neither prevents a QSO from completing in the loopback test environment, but A-01 would cause incorrect on-air behaviour (transmitting over the partner's TX window) and A-02 produces confusing WRN log entries on every config save.

## What Changes

- **A-01 — QSO answerer retry timing**: The `WaitReport` and `WaitRr73` states must not count a silence-guard-triggered empty window as a missed response. The silence guard fires because OpenWSFZ was transmitting in that window, not because the partner failed to respond. The state machine must wait through at least one partner cycle before retrying.
- **A-02 — TX settings UI pre-population**: The Settings screen must pre-populate `watchdogMinutes` and `retryCount` fields from the values returned by `GET /api/v1/config` before the user edits them. Currently these fields submit `0` on every save, which triggers a WRN clamp at the API layer.

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

- `qso-answerer`: Retry requirement amended — a cycle suppressed by the silence guard (RMS below threshold) during our own TX window SHALL NOT count as a missed-response cycle; the state machine must receive at least one unsuppressed empty cycle from the partner before retrying.
- `web-frontend`: New explicit requirement that TX settings form fields (`watchdogMinutes`, `retryCount`) are pre-populated from the values returned by `GET /api/v1/config` when the Settings screen is opened or the config is fetched.

## Impact

- `src/OpenWSFZ.Daemon/QsoAnswererService.cs` — retry logic in `HandleWaitReportAsync` / `HandleWaitRr73Async`
- `src/OpenWSFZ.App/` (WPF Settings view/viewmodel) — TX settings field binding to loaded config values
- No API surface change; no new dependencies; no breaking changes
