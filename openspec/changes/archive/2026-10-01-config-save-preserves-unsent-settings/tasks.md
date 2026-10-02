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

- [x] 5.1 `qa/config_drift.py` with tests (design D7). No edit to any tool not on `main`.
      **Evidence:** `qa/tests/test_config_drift.py`, 18 passed (`python -m pytest qa/tests/test_config_drift.py -q`).
- [x] 5.2 Tell QA before it lands on `main`. Record wiring gaps in the report.
      **Evidence:** #193 went to `main` through PR #196 (`d3c53ed0`, 2026-10-01) with QA's knowledge; the Engineer closed this item in substance, no wiring gap to record.
- [x] 5.3 RUNBOOK note: drift aborts or not, per battery. **Evidence:** `qa/rr-study/RUNBOOK.md` §2.1.

## 6. Docs and version

- [x] 6.1 `REQUIREMENTS.md`: amend the FR covering the config API; add the archive-control and log-line
      requirements; change-log row.
- [x] 6.2 `VERSION` 0.51 to 0.52 (user-facing). Commit before running `check_version_bump.py` (G9b).

## 7. Acceptance

- [x] 7.0 T1-T15 run by the Engineer on `a2d216c3`/`be8dd882`, unfiltered: Web.Tests 359/359 (30/30 re-loop on `be8dd882`, 18:07:54Z-18:23:52Z), `node --test web/js/*.test.js` 65/65, Playwright T15 27/27. The T8 flake (1 in 13, 1 in 30 before the fix) was a test-fixture defect, fixed in `be8dd882` (design D3).
- [x] 7.1 T16: full suite green on all three CI platforms. **Evidence (2026-10-01):** CI on the #196 PR head `0e096e78` green on macOS, Windows and Ubuntu (runs 36909023185, 36909033884); CI on `main` at `9bade2bc` green on all three (run 36911434239). (The earlier macOS failure on `d3c53ed0` was a flake family in Daemon.Tests, fixed test-only by #197.) Known intermittent on `main` itself (not from this change): `OpenWSFZ.Daemon.Tests` timing tests (cycle-audio-archive manifest order, TX-D04/decode-panel-filtering SelectResponder None-mode, D-CALLER-021 A late click, fix-external-reporting-clear-and-reply-filter default config).
- [x] 7.2 L1 MET 2026-09-30, **deviation from "on the station" (accepted by the Architect):** run on an isolated daemon (port 18193, own config and archive directory) capturing `CABLE Output` (granted by QA) with low-level noise played to `CABLE Input` by explicit device index, because the station was reserved for QA's overnight run. The property under test, config persistence and archive continuity across a real Settings-page save, does not depend on the audio source. Run 2, 18:04:00Z-18:07:13Z: a Playwright Settings save at 18:05:27Z; 13 WAVs, every gap 15 s (6 before, 7 after); `mode=all`, `decodingEnabled`, `decoder` unchanged; Part D line paths only; `config_drift` wrote no row. Run 1 (config without a `decoder` section) correctly flagged `decoder.*` absent to present, the page materialising the section. No real band audio, no real CODEC. Station not touched.
- [x] 7.3 `/opsx:verify`, then QA-peer review is the Captain's call. Every merge needs the Captain (HK-010).
      **Evidence (2026-10-01):** `/opsx:verify` PASS with one minor note (Engineer, on `eng/base` at `9bade2bc`; Web.Tests 359/359, `config_drift` 18/18). QA review ordered by the Captain, done post-merge: APPROVE, no blocker, notes R1 to R5 (`QA-REVIEW-config-save-preserves-unsent-settings.md`). Merged by the Captain's sign-off (HK-010).
- [ ] 7.4 After merge: Architect updates memory `hk035`; nudge the Developer worktree (HK-032); sync to
      `decoding_improvement`. **Status at archive (2026-10-01):** `hk035` updated by QA (addendum), Developer and Engineer nudged (HK-032); the **`decoding_improvement` sync is tracked on the BOARD**, not here (Captain decided 2026-10-01: sync before the next endurance run, one dedicated merge by QA with a new arm label).
