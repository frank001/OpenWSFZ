## 1. A-01 — Skip-first-cycle guard in QsoAnswererService

- [x] 1.1 Add a `private bool _skipNextRetry` field to `QsoAnswererService`
- [x] 1.2 Set `_skipNextRetry = true` at the point where the state transitions into `WaitReport` (after TX audio completes)
- [x] 1.3 Set `_skipNextRetry = true` at the point where the state transitions into `WaitRr73` (after TX audio completes)
- [x] 1.4 In `HandleWaitReportAsync`: at the top of the empty-batch / silence-guard branch, check `_skipNextRetry`; if true, set it to `false` and return without retransmitting or incrementing the retry counter
- [x] 1.5 In `HandleWaitRr73Async`: apply the identical guard — check `_skipNextRetry`; if true, clear and return
- [x] 1.6 Ensure `_skipNextRetry` is cleared to `false` whenever a matching decode is received (so the flag does not linger across state transitions)
- [x] 1.7 Ensure `_skipNextRetry` is reset to `false` when the state machine returns to `Idle` (abort or complete)

## 2. A-01 — Unit tests

- [x] 2.1 Add test: entering `WaitReport` and receiving one empty batch → no retry fired, counter still 0
- [x] 2.2 Add test: entering `WaitReport` and receiving two consecutive empty batches → retry fires on the second, counter is 1
- [x] 2.3 Add test: entering `WaitRr73` and receiving one empty batch → no retry fired
- [x] 2.4 Add test: entering `WaitRr73` and receiving two consecutive empty batches → retry fires on the second
- [x] 2.5 Add test: entering `WaitReport`, first batch has a matching response → state advances; no retry; flag cleared
- [x] 2.6 Add test (A-01 retry path): silence cycle after retry TX in `WaitReport` is skipped; fourth empty cycle triggers second retry (verifies `_skipNextRetry = true` added to `RetryOrAbortAsync`)
- [x] 2.7 Add test (A-01 retry path): silence cycle after retry TX in `WaitRr73` is skipped; same pattern as 2.6 from the `WaitRr73` state
- [x] 2.8 Update existing test `WaitReport_NoResponse_RetriesThenAborts` (6.6): expanded from 4 to 6 cycles to match the corrected abort sequence — `[skip][retry1][skip][retry2][skip][abort]`

## 3. A-02 — Settings page pre-population

- [x] 3.1 In `settings.js`, locate the config-load callback where `config.tx` fields are applied to the form (callsign, grid, output device)
- [x] 3.2 Confirm the exact `id` attributes of the `watchdogMinutes` and `retryCount` `<input>` elements in `settings.html` — inputs were absent; added as `tx-watchdog-minutes` and `tx-retry-count` with matching save-handler and snapshot wiring
- [x] 3.3 In the same callback block, add assignment of `watchdogMinutes` input's `.value` from `config.tx.watchdogMinutes`
- [x] 3.4 In the same callback block, add assignment of `retryCount` input's `.value` from `config.tx.retryCount`

## 4. A-02 — Verification

- [x] 4.1 Open the Settings page in a browser; confirm the TX tab shows `watchdogMinutes` = 4 and `retryCount` = 3 (or whatever the current config holds) without editing anything — confirmed by UAT session `artefacts/ft8-qso-answerer-v1_items/202606151810` (log `openswfz-20260615T160612Z.log`: no clamping warnings; ADIF entries confirm correct watchdog behaviour)
- [x] 4.2 Click Save without changing anything; confirm the daemon log contains no `WRN TX: watchdogMinutes … clamped` or `WRN TX: retryCount … clamped` entries — confirmed; UAT log shows no such warnings across three QSOs
- [x] 4.3 Change `retryCount` to 5, Save, reload the page; confirm the field shows 5 — confirmed during UAT; field round-tripped correctly

## 5. Build and regression gate

- [x] 5.1 `dotnet build OpenWSFZ.slnx -c Release` — 0 errors, 0 warnings
- [x] 5.2 `dotnet test OpenWSFZ.slnx -c Release` — all existing tests pass; new tests from section 2 pass (442 total, 87 in Daemon.Tests)
- [x] 5.3 Run traceability check — G3 gate passes (34/34)
