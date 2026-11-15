# Live run contents — 2026-10-22 (session 19:49:19 → 08:00:00 UTC)

Gathered automatically by `tools/gather_live_run_artefacts.py` (HK-016). Not committed to VCS (git-ignored, `artefacts/` — NFR-021/GDPR: these files contain real third-party callsigns).

**TODO (QA/Developer to fill in before closing out the run):** link the analysis this run supports and fill in the "Headline result" section below.

## Contents

- `owsfz/ALL.TXT` — OpenWSFZ's decoded-message log, filtered to the session window (60902 lines).
- `owsfz/` daemon log file(s): (none found in window).
- `owsfz/wav/` — 2927 WAV file(s) from the cycle-audio-archive feature (0 is normal if the feature was off this session — the folder is kept for future use regardless).
- `wsjt-x/ALL.TXT` — WSJT-X's decoded-message log, filtered to the session window
  (78287 lines).
- `wsjt-x/wav/` — 2926 WAV recordings from WSJT-X's own `save/` directory.

## WSJT-X / OpenWSFZ provenance (G1)

- **OpenWSFZ side**: read live and filtered, from `D:\Projects\claude\OpenWSFZ\artefacts\20261022_1949_endurance_run\ALL.TXT`. Gathered `owsfz/ALL.TXT`: 60902 lines, SHA-256 `11ccbbf7b8e5f9353c32934acd783a09d906dd7bba78fd9cbf155d39c616d0b2`.
- **WSJT-X side**: read live and filtered, from `C:\Users\Frank\AppData\Local\WSJT-X - FT991A\ALL.TXT`. Gathered `wsjt-x/ALL.TXT`: 78287 lines, SHA-256 `b1475f7c589b9d471706ff7c2db4360ca0809c4dc1b038d87802387c430c9aa9`. WAVs: 2926 total (copied from the live `save/` directory).
- **Shared-install assertion**: not asserted -- the §3.3 guard was active for this gather (refuses if more than one WSJT-X instance had in-window decodes and this flag was not passed).

## Build under test

**NOT RECORDED**: no readable `--arm-config` (the daemon's own `arm_config.json`) was given, so the build under test is unknown to this gather. For information only, the gatherer's own checkout is `qa/refset` at `e04477be` (**uncommitted changes present** — run `git status`/`git diff` to record what was actually in play). That is the tooling worktree, not necessarily the daemon build (the 2026-09-23 R&R gather recorded `345e75ff` while the daemon ran `84cac119`).

## Device / session metadata

Audio device: Voicemeeter Out B1 (VB-Audio Voicemeeter VAIO). Dial frequency at time of gathering: 7.074 MHz
(a run parameter, may have changed during the session — check the ALL.TXT frequency column
for the actual per-line value, not this single snapshot).
Decoder settings: `kMinScorePass2=10`,
`osdCorrThreshold=0.1`,
`osdNhardMax=24`.
Session duration: 12:10:41 (19:49:19 → 08:00:00).

## Headline result

TODO — one-line pointer to wherever the actual analysis/report for this run lives.
