# Live-confirmation run — f57fa4d — run notes (COMPLETE — see `report.md` once written)

Session ended on the Captain's explicit "stop it" at the first checkpoint (~34 min in). Raw,
timestamped working log kept during the run; a polished `report.md` is still to be written as the
citable go-forward artefact, same convention as `1cebf81`/`29041f7`.

**Purpose:** tasks.md 8.6-contributing live-confirmation, now with 8.4's `hashTableRejectCount`
logging deployed for the first time against real signal, and with 8.7's isolated-test confirmation
of the discard-costs-real-time mechanism already in hand from the unit-test evidence (not
re-tested live here — this run is observational, not a falsification test). No fix has landed for
8.3 — the correction logic under test is still Decision 5's size-to-confirmed-deviation mechanism,
already known non-convergent from `1cebf81`/`ce13e30`. This run is not expected to show
convergence; it exists to (a) gather a fresh comparison against WSJT-X now that both `ALL.TXT`
logs have been cleared, and (b) confirm the new 8.4 logging behaves correctly under sustained real
load, complementing the synthetic smoke check already done earlier this session.

## Planned duration

Per the Captain (2026-07-24, ~18:23 local start): **short session first**, matching the established
pattern from `7.6`/`8.6`'s prior rounds — explicit checkpoint to decide stop-vs-extend from
evidence, not an open-ended commitment from the start. First checkpoint target: ~30-45 min in
(~18:55-19:10 local / ~16:55-17:10 UTC), or sooner if the monitor surfaces something that itself
warrants an earlier look (a correction firing, a heartbeat drop, an error).

## Setup

- Code under test: `f57fa4d` (feat(ft8): log hashTableRejectCount per cycle; confirm
  discard-vs-replay real-time-cost asymmetry — tasks.md 8.4/8.7/8.8), on
  `docs/propose-fix-cycle-boundary-clock-drift`, already pushed to PR #108 (not merged).
- Daemon: PID 48664, started 2026-07-24 18:23:34Z (log file timestamp) — `CycleFramer started;
  leading silence = 104484 samples (8.707 s), cycle start = 18:23:45` confirmed at 18:23:53.707Z.
  `Resampling pipeline ready`: 48000 Hz stereo→mono(left) → 12000 Hz, confirmed same log line.
- Capture device: `'Microphone (2- USB Audio CODEC )'`, `d451e08c-82b5-446e-a5f1-1bdd8fceeac2`,
  WASAPI — same device family as every prior round this investigation.
- Band: 20 m (14.074 MHz FT8), confirmed via `GET /api/v1/status`.
- Daemon log: `logs/openswfz-20260724T182334Z.log` (git-ignored, local only, NFR-021).
- OpenWSFZ's own WSJT-X-format decode log: `ALL.TXT` (repo root, `AllTxtWriter`, FR-027/028) —
  actively growing, same `YYMMDD_HHMMSS  D.DDD Rx FT8 {snr} {dt} {freq} {message}` format as
  WSJT-X's own, so cycle-by-cycle DT comparison is possible directly from these two files without
  needing the full rr-study harness.
- WSJT-X: running in parallel, `ALL.TXT` cleared and WAV-saving **disabled** this run (per the
  Captain's setup) — no WAV artefacts will be preserved this time, decode-text comparison only.
  Path: `C:\Users\Frank\AppData\Local\WSJT-X\ALL.TXT`.
- Confirmed before arming the monitor: both `hashTableRejectCount=` (8.4) and `Cycle boundary
  drift check`/`Cycle boundary pipeline timing` (Decision 6) lines are present and correctly
  formatted in the live log — this is not a stale pre-instrumentation build.

## What to watch for

- Every `Cycle boundary resync` (correction firing): does the *next* drift-check reading land
  near the noise floor, or re-establish near the pre-correction magnitude (the established
  `1cebf81` failure mode)? Same question as every prior round — still unresolved, still the
  reason 8.3 is open.
- `hashTableRejectCount`: expected to stay at 0 for a short run on an unsaturated table (matches
  the smoke-test result) — only interesting if it moves at all.
- `Cycle boundary pipeline timing`'s `real inter-window elapsed` and chunk-dequeue-gap stats —
  continuing the flat/unremarkable pattern `29041f7` found, or not.
- Periodic DT comparison between `ALL.TXT` (OpenWSFZ) and WSJT-X's `ALL.TXT` for matched
  cycles/messages — at checkpoints, not continuously (matching cycles across the two files by
  timestamp+callsigns is a manual/scripted comparison step, not something the line-watching
  monitor does inline).
- Any `[ERR]`/`[FTL]`, or `Heartbeat:` lines with any field `=false` (device/capture dropout).

## Timeline (updated as the run progresses)

- 18:23:34Z — daemon started (per log filename/first log lines).
- ~18:23Z (local ~20:23) — Captain confirms both apps decoding live on 20 m, ALL.TXT cleared on
  both sides, WAV saving off in WSJT-X this run.
- Pre-arm grep of the log (no monitor running yet) found: no corrections fired 18:23:34-18:29:06Z,
  deviation oscillating 885-1640 samples (74-137 ms), persistence streak bouncing between 1/3 and
  2/3 without ever reaching 3/3 — consistent with the established "recurring, non-monotonic
  scheduling-jitter-like deviation, correctly not firing" pattern the persistence gate exists to
  reject (spec/ft8-decoder's own "recurring, non-monotonic deviation does not fire" scenario).
- `qa/endurance/2026-07-24-f57fa4d/monitor.sh` armed (Monitor task `bokfd0smf`, later replaced —
  see correction below), watching for corrections, `hashTableRejectCount` lines, `[ERR]`/`[FTL]`,
  heartbeat drops, with a 15-min periodic status fallback (shorter than `29041f7`'s 30-min
  cadence, matching this run's shorter planned length).
- **Correction, ~18:41Z:** the first `monitor.sh` version echoed every `hashTableRejectCount` line
  individually (intended to confirm 8.4's first live exposure). Once the table saturated
  (~18:39Z, see below) this fired every ~15-30s — too noisy for a session-length watch. Stopped
  task `bokfd0smf`, retuned the script to only announce a genuine 0-to-nonzero *onset* transition
  (seeded from the log's own history so a monitor restart mid-saturation doesn't misfire one) and
  fold the running count into the periodic 15-min status line instead, same treatment as the
  drift/timing lines. Re-armed as task `be9s3k7hu`. No data was lost — this only affects how the
  monitor *notifies*, not what's in the daemon log itself.
- **19:02:16Z — session stopped** on the Captain's "stop it" at the first checkpoint. `POST
  /api/v1/decode/stop` (operator-initiated, per the log: "Capture stopped on device ...
  (operator-stopped). Chunks received: 37048."), followed by a graceful application shutdown at
  19:02:21Z. Final `hashTableRejectCount` for the session: **2394**
  ("Non-zero means the 256-slot callsign hash table saturated and one or more Type 4 announcements
  could not be stored (f-005)." — expected and harmless under this band's real load, not a defect).
  Monitor task `be9s3k7hu` stopped in parallel (its last event, a `HEARTBEAT-DROP` for
  `captureActive=false`, was the capture-stop taking effect, not a fault). Total session length:
  18:23:34Z - 19:02:21Z, **~38m47s**. Final correction tally: **3** (table above); no 4th fired in
  the ~23 min between checkpoint and stop.
- 18:39:15Z — `hashTableRejectCount` moved off zero for the first time (450, up from 0 at
  session start) — expected under real 20 m load with far more than 256 unique stations heard;
  continuing to climb steadily since (2060 by 18:41:31Z last checked — roughly linear, ~1-1.5
  rejects/sec at this band's activity level). This is the new 8.4 instrumentation's first live
  exposure to real saturation, not a synthetic smoke test — working as designed.
- **Correction erratum (self-caught, ~18:57Z):** the first `monitor.sh` instance (`bokfd0smf`) was
  only armed shortly before 18:39Z — a few minutes *after* the run had already started at
  18:23:34Z — so its "Correction #1" label undercounted: a full `grep` of the log for `Cycle
  boundary resync` after the fact found **three** corrections fired before this checkpoint, not
  one. Corrected timeline, with the very next drift-check reading after each:

  | # | Fired at | Deviation at fire | Next reading | Delta | Direction |
  |---|---|---|---|---|---|
  | 1 | 18:34:45.163Z | 1956.9 samples (163.08 ms) | 1324.4 samples (18:35:00.273Z) | -632.5 | decrease |
  | 2 | 18:36:15.285Z | 1468.5 samples (122.37 ms) | 1877.3 samples (18:36:30.441Z) | +408.8 | **increase** |
  | 3 | 18:39:45.453Z | 2020.0 samples (168.34 ms) | 1755.5 samples (18:40:00.600Z) | -264.5 | decrease |

  So: 2 of 3 corrections this run are followed by a decrease (unlike `1cebf81`'s consistent
  same-or-higher pattern), one by an increase. Genuinely mixed so far — not the clean established
  failure mode, but also not evidence of convergence (deviation keeps oscillating in roughly the
  same 900-2000-sample band throughout, both before and after all three corrections, rather than
  trending toward the noise floor). Too early and too few corrections to read a trend into the
  2-decreases-1-increase split; flagging it accurately rather than either over- or under-claiming.

## First checkpoint (~18:57Z, ~34 min in)

- Corrections: 3 total (table above), last at 18:39:45Z — none in the ~17 min since.
- Latest drift check (18:57:00.618Z): deviation 1969.8 samples (164.15 ms), streak 1/3 — same
  oscillation band as the whole session so far, nothing building toward an imminent 4th
  correction.
- `real inter-window elapsed` still flat at 14.980s (nominal 15.000s); chunk-dequeue gaps still
  flat (n=241, avg=62.2ms, max=63.3ms) — continues `29041f7`'s "no visible scheduling-delay
  growth at the instrumented stages" finding.
- `hashTableRejectCount`: 1929 as of 18:56:45Z cycle (2060 moments later at last check) — climbing
  steadily and harmlessly (no errors, no heartbeat drops, decoding unaffected) — purely
  observational, exactly as designed.
- No `[ERR]`/`[FTL]`, no heartbeat drops, whole session.

**Assessment:** an uneventful, stable short run. Fewer corrections than `29041f7`'s comparable
early window (3 in ~34 min here vs. 8 in `29041f7`'s first 32 min) — could be ordinary
session-to-session variance in the jitter-driven deviation, or worth a data point in its own
right; not enough here to say which. No fix has landed for 8.3, so nothing about this run can
demonstrate convergence even if it runs longer — its value so far is (a) confirming 8.4's logging
under real load, done and working, and (b) the DT-offset observation below, the most actionable
finding this session has produced.

## Baseline DT comparison (cycle 18:29:00Z, before correction #1 fired)

Quick manual comparison, `ALL.TXT` (OpenWSFZ) vs. WSJT-X's `ALL.TXT`, matched by audio frequency
bin within the same cycle (11 matched decodes; OWSFZ logged 25 decodes this cycle vs. WSJT-X's 47
— a recall gap, consistent with the known baseline). **Every matched pair shows OpenWSFZ's DT
running ~+0.5 to +0.6 s higher than WSJT-X's DT for the same decode.** Message content (station
callsigns) is deliberately **not** reproduced here or in any committed artefact — those are real
third-party calls pulled live off-air, and `run-notes.md`/`report.md` are git-tracked, unlike the
gitignored `ALL.TXT`/`logs/` files they're drawn from (NFR-021 — no real callsign in VCS). Freq/DT
only:

| Freq (Hz) | OWSFZ DT | WSJT-X DT | Delta |
|---|---|---|---|
| 1031 | 0.8 | 0.2 | +0.6 |
| 1497 | 0.7 | 0.2 | +0.5 |
| 1944 | 0.7 | 0.1 | +0.6 |
| 2009 | 0.2 | -0.4 | +0.6 |
| 2063 | 0.4 | -0.1 | +0.5 |
| 981 | 1.0 | 0.4 | +0.6 |

(full 11-row comparison was also shown, with callsigns, in the interactive session transcript
earlier in this run — that transcript is outside version control, but the callsigns should not be
carried into any file that gets committed, including a future `report.md`.) **Not yet
interpreted** — this is a much larger and more consistent offset (~0.5-0.6 s, flat across every
matched message in one cycle) than the ~0.1-0.2 s `deviation` the `CycleFramer` instrumentation
itself was reporting at this same point in the run, which suggests it may be a separate, largely
time-invariant measurement/reference-point offset rather than the session-scale growing drift this
investigation exists to fix — but that is a hypothesis, not a finding, and needs checking against
whatever prior characterization of OpenWSFZ-vs-WSJT-X DT baseline offset already exists before
reading anything into it. Flagging for the checkpoint rather than chasing it now.
