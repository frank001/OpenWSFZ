# Tasks: config-save-preserves-unsent-settings

Owner: Engineer (Eng). Build (`src/`, `web/`, `tests/`): a separate Developer session (HK-011). Part E and
the OpenSpec artifacts: Engineer. Branch: `eng/config-save` off `origin/main` @ `c3f42362`. Test IDs T1–T16
and L1 are defined in the source spec §7 and are quoted in the delta specs.

## 0. Preconditions

- [x] 0.1 `origin/main` is `c3f42362` (2026-09-29). Evidence: `design.md` §Preconditions.
- [x] 0.2 Caller inventory: five `qa/` callers, all full-body. Evidence: `design.md`.

## 1. Tests first (Developer)

- [x] 1.1 Add T1, T2, T4–T12 to `tests/OpenWSFZ.Web.Tests/` against the current handler. T1, T4, T5, T6,
      T7 SHALL fail on `c3f42362`; record which do (proves the tests can fail, HK-022).
- [x] 1.2 The Settings-shaped fixture's key set is exactly the `postConfig({...})` literal at
      `web/js/settings.js:1354-1371`.

## 2. Part A: overlay merge (Developer)

- [x] 2.1 Implement design D1 in `src/OpenWSFZ.Web/WebApp.cs`.
- [x] 2.2 Remove the redundant guards and the two stale comments (spec §2).
- [x] 2.3 T1–T12 pass.
- [x] 2.4 Fill design D6: one row per existing test whose assertion changed.

## 3. Part D: change log line (Developer)

- [x] 3.1 One `Information` line per successful save; allowlisted values only.
- [x] 3.2 T14 passes; the test asserts no callsign and no passphrase in the captured log.

## 4. Part C: Settings-page archive group (Developer)

- [x] 4.1 Read `CycleArchiveService`; write the findings into `design.md` D5 and choose per-field validation.
- [x] 4.2 `web/settings.html`, `web/js/settings.js` (snapshot and payload), `web/css/app.css`. Four modes.
- [x] 4.3 T13 payload-contract test; T15 Playwright; before/after screenshots (HK-005, HK-007).

## 5. Part E: config-drift module (Engineer)

- [ ] 5.1 `qa/config_drift.py` with tests (design D7). No edit to any tool not on `main`.
- [ ] 5.2 Tell QA before it lands on `main`. Record wiring gaps in the report.
- [ ] 5.3 RUNBOOK note: drift aborts or not, per battery.

## 6. Docs and version

- [x] 6.1 `REQUIREMENTS.md`: amend the FR covering the config API; add the archive-control and log-line
      requirements; change-log row.
- [x] 6.2 `VERSION` 0.51 to 0.52 (user-facing). Commit before running `check_version_bump.py` (G9b).

## 7. Acceptance

- [ ] 7.1 T16: full suite green on all three CI platforms.
- [ ] 7.2 L1 live check on the station, slot agreed with QA first; record take and release in the board.
- [ ] 7.3 `/opsx:verify`, then QA-peer review is the Captain's call. Every merge needs the Captain (HK-010).
- [ ] 7.4 After merge: Architect updates memory `hk035`; nudge the Developer worktree (HK-032); sync to
      `decoding_improvement`.
