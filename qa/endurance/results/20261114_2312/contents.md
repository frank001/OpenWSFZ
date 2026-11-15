# Live run contents — 2026-11-14 (session 23:12:16 → 10:59:58 UTC)

Gathered automatically by `tools/gather_live_run_artefacts.py` (HK-016). Not committed to VCS (git-ignored, `artefacts/` — NFR-021/GDPR: these files contain real third-party callsigns).

**TODO (QA/Developer to fill in before closing out the run):** link the analysis this run supports and fill in the "Headline result" section below.

## Contents

- `owsfz/ALL.TXT` — OpenWSFZ's decoded-message log, filtered to the session window (79317 lines).
- `owsfz/` daemon log file(s): (none found in window).
- `owsfz/wav/` — 2834 WAV file(s) from the cycle-audio-archive feature (0 is normal if the feature was off this session — the folder is kept for future use regardless).
- `wsjt-x/ALL.TXT` — WSJT-X's decoded-message log, filtered to the session window
  (85783 lines).
- `wsjt-x/wav/` — 2833 WAV recordings from WSJT-X's own `save/` directory.

## WSJT-X / OpenWSFZ provenance (G1)

- **OpenWSFZ side**: read live and filtered, from `D:\Projects\claude\OpenWSFZ\artefacts\20261114_2312_endurance_run\ALL.TXT`. Gathered `owsfz/ALL.TXT`: 79317 lines, SHA-256 `266a43e07170bafbc07ca6757fa4067bc66be0a318582de1f8e05584dd422193`.
- **WSJT-X side**: read live and filtered, from `C:\Users\frans\AppData\Local\WSJT-X - FT991A\ALL.TXT`. Gathered `wsjt-x/ALL.TXT`: 85783 lines, SHA-256 `bf5d3d0c7f08391f7d4ed7ea8d6c1d20903342d2596c651a27cd29692d961eb6`. WAVs: 2833 total (copied from the live `save/` directory).
- **Shared-install assertion**: not asserted -- the §3.3 guard was active for this gather (refuses if more than one WSJT-X instance had in-window decodes and this flag was not passed).

## Build under test

**NOT RECORDED**: no readable `--arm-config` (the daemon's own `arm_config.json`) was given, so the build under test is unknown to this gather. For information only, the gatherer's own checkout is `qa/same-chain` at `d8e3c5f3` (**uncommitted changes present** — run `git status`/`git diff` to record what was actually in play). That is the tooling worktree, not necessarily the daemon build (the 2026-09-23 R&R gather recorded `345e75ff` while the daemon ran `84cac119`).

## Device / session metadata

Audio device: Microphone (2- USB Audio CODEC ). Dial frequency at time of gathering: 7.074 MHz
(a run parameter, may have changed during the session — check the ALL.TXT frequency column
for the actual per-line value, not this single snapshot).
Decoder settings: `kMinScorePass2=5`,
`osdCorrThreshold=0.05`,
`osdNhardMax=24`.
Session duration: 11:47:42 (23:12:16 → 10:59:58).

## Headline result

TODO — one-line pointer to wherever the actual analysis/report for this run lives.
