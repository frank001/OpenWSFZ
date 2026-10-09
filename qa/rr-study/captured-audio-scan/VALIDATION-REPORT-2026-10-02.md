# #194 captured-audio scan: VALIDATION REPORT (09-23 calibration, 09-29 OFF and ON)

- **From:** Engineer (owner)  **To:** Architect, cc QA, Captain  **Date:** 2026-10-02 evening (HK-017)
- **Branch:** `eng/194-scan` (local; QA pushes). QA tooling under `qa/` and `tools/` only; `git diff --stat -- src/ native/` empty. Nothing was deleted; no station, daemon or decoder was used; no `ALL.TXT` or message text was read (NFR-021: counts, slot keys, hashes).
- **Frozen at re-freeze 3 (`d4316452`):** `thresholds.json` SHA-256 `e1789e2ec8a02caf66898dd15b2e208df6ebec3508460f2f29433a81b1146d11`, `scan_core.py` `6ca48d41fe3e957f2bea7bbdaf03b94150079ba80f341c2d6a36ff6d50b18eb4` (both LF bytes). Chain of freezes: `3953ac35` (A1 to A6) → `edb5b56f` (A7) → `d4316452` (A3', A10, A9 above-range cells). The 09-29 pair was first opened after the third freeze and a PC1 that passed. **HK-022 pins:** no decoder ran, so no `--filter` or DLL pin applies; the tool's own tests are `qa/rr-study/tests` (scan code has no test file yet, see §7) and `tools/tests/test_gather_live_run_artefacts.py` (15 passed, no filter).

## 0. Guard paragraph (spec §1, verbatim)

> A WAV is recorded **before** either decoder runs, so **no WAV anomaly is ever a decoder defect.** Comparing the two apps' WAVs for the same slot locates a fault in one of two places only. If it shows **in both**, it is in the **shared playback path** (render → PortAudio → Voicemeeter → both recorders). If it shows **in one**, it is in **that app's recording path**. A slot with no anomaly says nothing about how either decoder handled it.

S1 `g_db`/`resid_db` appear in each `scan_report.md` as descriptive chain gains only (owsfz −1.6, wsjt-x −0.7 dB on S1); the dropped +1.45 dB follow-up is not reopened.

## 1. Headline, in plain words

1. **The scan runs, and it is cheap:** 2.6 to 4.6 minutes of one core per run (V3) plus about 30 s for the reference renders, so it can run automatically after each R&R run.
2. 🔴 **Holes (state them to the Captain).** 30 (side, group, metric) cells are DESCRIPTIVE and never flag; 12 of them are DESCRIPTIVE-ABOVE-RANGE. **With these thresholds the scan cannot detect a short added sound (a Windows notification, a beep) or a click in the busy and tonal scene types** (owsfz: tile in single, multi, tone2, tone3; wsjt-x: tile in single, multi, tone3 and click in multi, noise, tone3). WSJT-X's last 600 ms cannot show a dropout. Slots whose reference is a steady carrier (60 per side per run, plus 3 in `single`) have no timing check.
3. **The OFF run exceeds the 50 % REF-UNVERIFIABLE limit** (160 of 244 = 66 %; 09-23 43 %, ON 43 %). By ruling A1 that is "stop and report". I report it and give the OFF numbers as **provisional**: the cause is that OpenWSFZ's archive for OFF holds only 259 slots (no S5 noise slot at all, whose references are the discriminating ones), see §3.
4. **Findings that matter (all descriptive; none is a decoder defect):** shared playback-path events exist in every run (BOTH slot × family findings: 42 on 09-23, 36 on OFF, 68 on ON); on OFF, **the first 90 s of the run** (slots 15:37:45 to 15:39:15Z, 7 BOTH slots) coincide with a burst of Windows events (8 Kernel-General id 16, a Software Protection pair, 2 AppModel-State) that is not present at any other time of either run. On ON, one BOTH slot (17:58:00Z) sits next to a Windows Update / SecurityCenter / SPP cluster.
5. **A run-level timing offset swamps the frozen two-sided timing rule** (§5): `tau_ms` and `dtau_ms` are centred on the calibration run's median; the chain's timing offset differs by run (e.g. wsjt-x `noise` median τ −328 ms on 09-23 vs −291 ms on ON; dτ `single` −8.7 vs −32.8 ms on OFF), so most slots flag: CROSS 54 (OFF) and 156 (ON), WSJTX-ONLY 78 (ON). Re-centred on each run's own median with the same frozen T, almost all of those clear (OFF: 54 → 1; ON noise dτ: 118 → 0). **That is a design question for you (A11), not something I changed** (terminal rule: no design change before the report).

## 2. Validation rows

| Row | 09-23 | OFF | ON |
|---|---|---|---|
| R0a determinism | 407/407 identical | 407/407 | 407/407 |
| R0b drift vs current harness | 0 differ | 0 | 0 |
| R0c literal (as written) | FAIL: owsfz 2.9 %, wsjt-x 10.3 % | FAIL: 1.2 % / 1.2 % | FAIL: 4.4 % / 15.7 % |
| R0c per slot (A1), discriminating slots | PASS, 0 of 232 | PASS, 0 of 84 | PASS, 0 of 232 |
| REF-UNVERIFIABLE (A1) | 175/407 = 43 % | **160/244 = 66 % (> 50 %)** | 175/407 = 43 % |
| V1 coverage | owsfz 437 = 407 SCANNED + 30 UNPLANNED; wsjt-x 438 = 407 + 31: PASS | owsfz 259 = 244 + 15 UNPLANNED; wsjt-x 437 = 244 + 163 UNPAIRED + 30 UNPLANNED: PASS | owsfz 437 = 407 + 30; wsjt-x 438 = 407 + 31: PASS |
| V1 MISSING (no WAV either side) | 0 | 0 | 0 |
| V2 fresh re-hash vs sidecar | 875 files, 0 mismatch: PASS | 696 files, 0 mismatch: PASS | 875 files, 0 mismatch: PASS |
| V3 measure wall time (one core) | 276 s (a concurrent job ran) | 157 s | 267 s |
| PC1 | 71 PASS + 5 FAIL first time; after A7 to A10: 18 PASS, 4 BLIND (tone groups), the rest DESCRIPTIVE (`pc1_v3.json`) | n/a | n/a |

R0c "literal" is kept as ruled; the rule as written cannot pass on this material (§ ruling 1915). The reference renders were made from `5f17b43` (09-23) and `62e8e74` (09-29); harness, synth and scenario trees are byte-identical across `5f17b43`, `62e8e74` and the current tree.

## 3. The OFF run's archive, and a caution

OpenWSFZ's OFF archive has 259 WAVs against WSJT-X's 437: the 163 truth slots with a WSJT-X WAV only are `UNPAIRED` (listed, never counted as normal or anomalous), and the S5 `noise` group has **0** paired slots for OpenWSFZ (OFF: single 77, multi 110, noise 0, tone2 27, tone3 30). That pattern is consistent with the archive mode having been "decoded cycles only" for much of the run (compare issue #193, the Settings save that resets `cycleAudioArchive`), but I did **not** read the config or logs, so it is a reading, not a finding. Its effect on this scan is arithmetic: the paired set loses its most discriminating group, so REF-UNVERIFIABLE rises to 66 %.

## 4. Flagged slots (frozen thresholds; non-DESCRIPTIVE metrics only), by class

| run | flagged slots | BOTH | OWSFZ-ONLY | WSJTX-ONLY | CROSS |
|---|---:|---:|---:|---:|---:|
| 09-23 (calibration) | 25 | 42 family-findings | 9 | 17 | 1 |
| OFF | 69 | 36 | 7 | 5 | 54 |
| ON | 179 | 68 | 14 | 104 | 156 |

(Class counts are slot × metric-family findings; a slot can carry several.) The lists are `flagged_slots.csv` in each run's `captured-audio-scan/` directory. One-sided findings are recording-path findings, never decoder findings. Dominant ON families: dtau CROSS (153), WSJTX-ONLY `tau_ms` (78), BOTH level (22), BOTH drift (12), OWSFZ-ONLY `click_max` (11). Dominant OFF: CROSS dtau (54), BOTH `tau_ms` (19), BOTH level (7), OWSFZ-ONLY `click_max` (6), BOTH drift (5), BOTH `lag_lost` (3). `lag_lost` (A10) fired in 5 calibration slots (all BOTH, so none one-sided) and in 3 OFF slots (BOTH).

## 5. The run-level offset (a question, with numbers; nothing applied)

Per-run median τ by (side, group) and the count beyond the frozen T versus beyond the same T centred on the run's own median are in each `scan_report.md` ("Descriptive, NOT frozen"). Summary: on OFF, wsjt-x `single` τ −247 ms against −315 calibration (20 flagged, 0 re-centred) and the owsfz/wsjt-x offset dτ `single` −32.8 against −8.7 ms (54 of 74 flagged, 1 re-centred); on ON, wsjt-x `noise` τ −291 against −328 (83 flagged, 50 re-centred) and dτ `noise` −33.5 against −3.9 ms (118 of 120, 0 re-centred); `g_db` medians agree to ≤ 0.05 dB across the three runs, so the level family is stable while the timing offset is run-specific. The spec text says the dev rule applies "to the deviation from the run's median"; I implemented it as the **calibration run's** median because `thresholds.json` stores a median per cell. **Question A11:** for a run other than the calibration run, centre `g_db`, `tau_ms`, `dg_db` and `dtau_ms` on that run's own median per (side, group) and keep T frozen? The re-centred counts above are what it would do. Per the terminal rule I changed nothing.

## 6. Section 7 (event log) for 09-29

Retention: System back to 2026-03-28, Audio/Operational 2026-09-15, Kernel-PnP/Configuration 2025-05-31, DeviceSetupManager 2026-05-23: all reach 09-29, so the absence of audio and device events is real for those logs. 56 events (Windows Error Reporting excluded) in 15:35 to 19:22Z across both runs, none from an audio, USB, PnP or driver-reset provider: Kernel-General 16 ×8, SPP 16384/16394 ×20, AppModel-State 4 ×11, Group Policy ×4, Windows Update ×3, Service Control Manager 7040 ×2, RestartManager ×4, NETLOGON, SecurityCenter, and **Time-Service 35 and 37 at 15:56:19Z** (a time-synchronisation event inside the OFF run; no flagged slot lies within ±30 s of it). Cross-reference of BOTH-classified slots (±30 s): OFF 7 of 31 (all in the first 90 s, one cluster); ON 1 of 35. Descriptive only, no cause claimed. (`windows_events_0929_both_runs.csv`.)

## 7. Predictions for scoring, and what is not done

CA1 MISS, CA2 MISS, CA3 HIT, CA4 MISS, CA5 HIT, as already scored by you; CA4 here means PC1 passed first time (it did not). **Not done:** a unit-test file for `scan_core`/`scan_apply` (the controls are PC1 and the validation rows, but a pytest file for the pure functions should exist before the scan is wired in); the post-run wiring itself (waiting for your ruling); the `tile_excess_db`/`click_max` redesign (the Captain's decision after this report). §11 (gatherer) is done: `799eac56` (build from `arm_config.json`, "NOT RECORDED" otherwise, `--synthetic-run` wording, 15 tests green). Cause (CA5): `git_build_info()` read the tooling worktree's `HEAD`.

## 8. Rulings requested

1. A11 (§5): per-run centring of the four dev metrics, yes or no.
2. The OFF run's 66 % REF-UNVERIFIABLE: accept its numbers as provisional descriptive data, or treat the OFF run as not validated.
3. May the scan be wired into the post-run step, with the holes in its headline and the §7 unit tests added first?
