# Live run contents — 2026-10-28 (session 22:33:19 → 15:30:01 UTC)

Gathered automatically by `tools/gather_live_run_artefacts.py` (HK-016). Not committed to VCS (git-ignored, `artefacts/` — NFR-021/GDPR: these files contain real third-party callsigns).

**Analysis for this run:** `anova_report.md` (Section 4 historical table) and `FINAL_REPORT_dossier.html`; headline result below. Record gaps fixed 2026-10-29 (QA, at the Architect's request, Captain's go): build under test and nhard now stated in this file; no figure changed.

## Contents

- `owsfz/ALL.TXT` — OpenWSFZ's decoded-message log, filtered to the session window (105326 lines).
- `owsfz/` daemon log file(s): (none found in window).
- `owsfz/wav/` — 4071 WAV file(s) from the cycle-audio-archive feature (0 is normal if the feature was off this session — the folder is kept for future use regardless).
- `wsjt-x/ALL.TXT` — WSJT-X's decoded-message log, filtered to the session window
  (123022 lines).
- `wsjt-x/wav/` — 4069 WAV recordings from WSJT-X's own `save/` directory.

## WSJT-X / OpenWSFZ provenance (G1)

- **OpenWSFZ side**: read live and filtered, from `D:\Projects\claude\OpenWSFZ\artefacts\20261028_2233_endurance_run\ALL.TXT`. Gathered `owsfz/ALL.TXT`: 105326 lines, SHA-256 `3c32649d647fd8f7c367a371097ff7f27b1c458982aac8cc9f17a41aecfba098`.
- **WSJT-X side**: read live and filtered, from `C:\Users\Frank\AppData\Local\WSJT-X - FT991A\ALL.TXT`. Gathered `wsjt-x/ALL.TXT`: 123022 lines, SHA-256 `a6abb48a820876c27686b5dc952664ddcb57eb4aba0f7eab4b08a82f43bf65cc`. WAVs: 4069 total (copied from the live `save/` directory).
- **Shared-install assertion**: not asserted -- the §3.3 guard was active for this gather (refuses if more than one WSJT-X instance had in-window decodes and this flag was not passed).

## Build under test

**Build under test (stated 2026-10-29 from the run's own records, not by this gather):** branch `qa/coh-gate-r-f4-pr`, commit `fa119fe085cb6fa17c06e39ed12c80747aa58eac` (PR #271, v0.67), `libft8.dll` SHA-256 `1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914`, `osdNhardMax` 24 (the daemon's own read-back). Recorded in `arm_config.json`, `arm_readback.json` and `ERA.txt` (run folder `artefacts\20261028_2233_endurance_run`; copies in `qa\endurance\results\20261028_2233`) and in Section 4 Table B of `anova_report.md`. Era RF4ON.

*Gatherer's own note, kept:* **NOT RECORDED**: no readable `--arm-config` (the daemon's own `arm_config.json`) was given, so the build under test is unknown to this gather. For information only, the gatherer's own checkout is `qa/refset` at `29410207` (**uncommitted changes present** — run `git status`/`git diff` to record what was actually in play). That is the tooling worktree, not necessarily the daemon build (the 2026-09-23 R&R gather recorded `345e75ff` while the daemon ran `84cac119`).

## Device / session metadata

Audio device: Voicemeeter Out B1 (VB-Audio Voicemeeter VAIO). Dial frequency at time of gathering: 7.074 MHz
(a run parameter, may have changed during the session — check the ALL.TXT frequency column
for the actual per-line value, not this single snapshot).
Decoder settings: `kMinScorePass2=10`,
`osdCorrThreshold=0.1`,
`osdNhardMax=24`.
Session duration: 16:56:42 (22:33:19 → 15:30:01).

## Headline result

See `anova_report.md`: matched 103,489 = 84.1 % of WSJT-X's 123,021 decodes (98.3 % of OpenWSFZ's 105,326); OWS-only 1.7 %; SNR gap −2.906 dB; DT gap +0.6529 s. First live-WSJT-X row of the RF4ON era (setting `decoder.coherentFallbackResidualUngated` on): not comparable with earlier rows and not an R-F4 effect estimate (Architect, 2026-10-29).
