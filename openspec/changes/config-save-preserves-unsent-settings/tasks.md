# Tasks: config-save-preserves-unsent-settings

Owner: Engineer (Eng). Build (`src/`, `web/`, `tests/`): a separate Developer session (HK-011). Part E and
the OpenSpec artifacts: Engineer. Branch: `eng/config-save` off `origin/main` @ `c3f42362`. Test IDs T1–T16
and L1 are defined in the source spec §7 and are quoted in the delta specs.

## 0. Preconditions

- [x] 0.1 `origin/main` is `c3f42362` (2026-09-29). Evidence: `design.md` §Preconditions.
- [x] 0.2 Caller inventory: five `qa/` callers, all full-body. Evidence: `design.md`.

## 1. Tests first (Developer)

- [ ] 1.1 Add T1, T2, T4–T12 to `tests/OpenWSFZ.Web.Tests/` against the current handler. T1, T4, T5, T6,
      T7 SHALL fail on `c3f42362`; record which do (proves the tests can fail, HK-022).
- [ ] 1.2 The Settings-shaped fixture's key set is exactly the `postConfig({...})` literal at
      `web/js/settings.js:1354-1371`.

## 2. Part A: overlay merge (Developer)

- [ ] 2.1 Implement design D1 in `src/OpenWSFZ.Web/WebApp.cs`.
- [ ] 2.2 Remove the redundant guards and the two stale comments (spec §2).
- [ ] 2.3 T1–T12 pass.
- [ ] 2.4 Fill design D6: one row per existing test whose assertion changed.

## 3. Part D: change log line (Developer)

- [ ] 3.1 One `Information` line per successful save; allowlisted values only.
- [ ] 3.2 T14 passes; the test asserts no callsign and no passphrase in the captured log.

## 4. Part C: Settings-page archive group (Developer)

- [ ] 4.1 Read `CycleArchiveService`; write the findings into `design.md` D5 and choose per-field validation.
- [ ] 4.2 `web/settings.html`, `web/js/settings.js` (snapshot and payload), `web/css/app.css`. Four modes.
- [ ] 4.3 T13 payload-contract test; T15 Playwright; before/after screenshots (HK-005, HK-007).

## 5. Part E: config-drift module (Engineer)

- [x] 5.1 `qa/config_drift.py` with tests (design D7). No edit to any tool not on `main`.
      **Evidence:** `qa/tests/test_config_drift.py`, 18 passed (`python -m pytest qa/tests/test_config_drift.py -q`).
- [ ] 5.2 Tell QA before it lands on `main`. Record wiring gaps in the report.
- [x] 5.3 RUNBOOK note: drift aborts or not, per battery. **Evidence:** `qa/rr-study/RUNBOOK.md` §2.1.

## 6. Docs and version

- [ ] 6.1 `REQUIREMENTS.md`: amend the FR covering the config API; add the archive-control and log-line
      requirements; change-log row.
- [ ] 6.2 `VERSION` 0.51 to 0.52 (user-facing). Commit before running `check_version_bump.py` (G9b).

## 7. Acceptance

- [ ] 7.1 T16: full suite green on all three CI platforms.
- [ ] 7.2 L1 live check on the station, slot agreed with QA first; record take and release in the board.
- [ ] 7.3 `/opsx:verify`, then QA-peer review is the Captain's call. Every merge needs the Captain (HK-010).
- [ ] 7.4 After merge: Architect updates memory `hk035`; nudge the Developer worktree (HK-032); sync to
      `decoding_improvement`.
