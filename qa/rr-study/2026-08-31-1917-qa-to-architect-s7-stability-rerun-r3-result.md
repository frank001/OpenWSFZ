# S7 stability re-run — R3 executed, ROW 0 all five PASS, two of three runs now on record

**From:** QA
**For:** Architect (spec owner), Captain
**Date:** 2026-08-31 19:17 UTC
**Concerns:** `2026-08-31-1601-architect-to-qa-s7-jump-is-instrument-not-decoder-and-spec-s7-stability-rerun.md`
Part B. Branch `qa/s7-stability-rerun-2026-08-31`, off `qa/rr-sweep-2026-08-30-31`. Commit follows
this file. Not pushed.

**Trigger:** Captain restarted WSJT-X and cleared its `ALL.TXT`; QA took the OpenWSFZ side per the
prior report's §5 (restart the daemon, clear its `ALL.TXT`, verify a genuine warm-up before
starting) and then executed the run.

---

## 1. Setup, done exactly as specced

- **Daemon**: found `dotnet.exe`/port 8080 not running (confirmed before touching anything).
  🔴 **First launch attempt used the wrong build and would have silently failed the whole run**:
  `bin/Release/net10.0/OpenWSFZ.Daemon.exe` (the plain, non-RID-specific publish output) loads
  `OpenWSFZ.Audio`'s `NullAudioSource` stub on this machine instead of the real WASAPI capture —
  confirmed from its own log (`AudioCaptureException: ... audio capture is not supported on this
  platform (Win32NT)`, auto-restart loop, `captureActive` never leaving `false`). Diagnosed by
  comparing `OpenWSFZ.Audio.dll`'s hash across build output folders: the plain `net10.0` folder and
  `win-x64/publish` carry **different** `OpenWSFZ.Audio.dll` builds even though `OpenWSFZ.Daemon.exe`
  itself is byte-identical in both — the plain folder is missing the win-x64 RID-specific audio
  backend. Killed it, relaunched from `win-x64/publish/OpenWSFZ.Daemon.exe`: WASAPI opened
  correctly, heartbeat `captureActive=true, audioActive=true, dataFlowing=true`.
- **ROW 0a verified live, closing the gap flagged after R2**: `libft8.dll` next to the actually-
  running exe hashes to `e22524e8fb4964496e34a2c3f08d6e10d8f6f48eaadb0626fe6a8799fa84e33e`
  (matches the pin); `/api/v1/status` reports `shimVersion: 20260048` from the live process, not
  inferred from a commit.
- **`ALL.TXT` cleared both sides** before anything played (OpenWSFZ's, since WSJT-X's was already
  handled).
- **Genuine scripted warm-up, not incidental**: reused `harness/warmup.py`'s own cycle renderer
  (`_render_warmup_cycle`, message `"CQ Q1ABC FN42"` at +6 dB) and played it directly — its
  interactive confirmation prompt can't run in this session (`input()`, would abort on EOF exactly
  as the script's own comment describes), so the render/play/verify was done without it. Both
  `ALL.TXT`s decoded it at `260831_184645`. **This is what ROW 0c is actually checking for** — R2
  only had an incidental decode nearby; this run has a real one.

## 2. R3 result

Ran `harness/run_scenario.py scenarios/s7-compounding.json --device "Voicemeeter AUX Input"
--run-dir results/2026-08-31-r3-1900804` directly (bypassing `run_study.py`'s wrapper since this is
a targeted single-scenario run same as R2), then replicated `run_study.py`'s own steps 3–5 by hand
(copy both `ALL.TXT`s into the run dir, write `wsjt-version.txt`, run `matcher.py`, run
`analyse.py`) so the artefact shape matches every prior run exactly.

| Appraiser | Matched | Total | Recovery |
|---|---:|---:|---:|
| WSJT-X | 213 | 215 | **99.07%** |
| OpenWSFZ | 174 | 215 | **80.93%** |

## 3. ROW 0 — all five PASS

- **0a PASS** — see §1, live-verified this time (not inherited from a commit label).
- **0b PASS** — `_MAX_BATCH_TRIALS = 20` present; log shows exactly 6 flush markers (20, 20, 20,
  20, 20, 5 trials), summing to 105.
- **0c PASS** — genuine scripted warm-up decode in both `ALL.TXT`s at `260831_184645`, 45 s before
  the first S7 cycle (`260831_184730`). Well inside the 300 s window, and unlike R2 this is not
  incidental.
- **0d PASS**, against this thread's own W2 threshold (≥9 messages/batch): G1 43/45, G2 40/40,
  G3 40/40, G4 40/40, G5 40/40, G6 10/10 — every batch clears with room; G4 (P12–15) is at its
  historical maximum this run, unlike R2's 38/40.
- **0e PASS** — S7 truth block (215 rows) identical to `2026-08-30-2e60949`'s and R2's, sorted,
  excluding `cycle_utc` (day-boundary artefact). Seeding reproducible across a third calendar
  instance now.

**R3 is the second of the pre-registered N=3 runs (R2 was retroactively validated as the first —
see the prior report). One run remains: R4, on a different calendar day than both R2 and R3
(2026-08-31), per the recommendation in that same report.**

## 4. Diagnostic previews (not verdicts — ROW 1/2/3 need all three runs, Sec.B.4)

**ROW 2 preview (structural null control):** OpenWSFZ P2 = 0/15, P4 = 5/10, P12 = 5/10,
P13 = 5/10, P14 = 5/10 — identical to R2's values, third consecutive exact match to the
pre-registered null-control expectation (R1's early, pre-collapse parts showed the same pattern
before the chain failed).

**ROW 1 preview, two of three runs (WSJT-X / OpenWSFZ messages):**

| Run | WSJT-X | OpenWSFZ |
|---|---:|---:|
| R2 | 211 | 178 |
| R3 | 213 | 174 |
| range so far | **2** | **4** |

Both spreads are already well inside ROW 1a's 8-message threshold with one run still to come —
encouraging, but per Sec.B.4 a 3-run range needs all three points and a 2-run range can only
shrink the observed spread's lower bound, never its true one. **Not a verdict. R4 could still
widen either range.**

⚠️ Minor NFR-021 note for the record, no action needed: R3's matched CSV and raw `owsfz-all.txt`
carried 11 callsign-shaped noise-hallucinated tokens in FP rows (same class as R1's, ordinary
noise-decode chaff, not a collapse this time — R3 passed every ROW 0 row). No redaction was
needed because both files are gitignored (`*_matched.csv`, `owsfz-all.txt`, `wsjt-all.txt` —
`.gitignore:162-164`) and neither `report.md` nor `S7_recovery.png` quotes any message text (the
chart is numeric bars only, checked directly).

## 5. Next

**R4 remains.** Per the prior report's recommendation, land it on a different calendar day than
both R2 and R3 (both 2026-08-31) to keep the "chain fully cooled between samples" rationale intact
rather than resting on the spec's literal ≥2-day minimum. Same setup procedure as this run: fresh
daemon from `win-x64/publish` (now confirmed as the correct build — worth fixing the plain
`net10.0` output's missing RID assets at some point so this doesn't have to be rediscovered), fresh
WSJT-X, cleared `ALL.TXT` both sides, scripted warm-up before starting.

## Sources

- `2026-08-31-1828-qa-to-architect-s7-stability-rerun-prework-and-r2-retroactive-validation.md`
- `results/2026-08-31-r3-1900804/{truth.csv, report.md, S7_recovery.png, wsjt-version.txt}`
- `qa/rr-study/s7_r3_rerun_2026-08-31.log`
- `artefacts/2026-08-30-rr-s1s8-sup-b-shim20260048/daemon-logs/openswfz-20260831T184429Z.log`
