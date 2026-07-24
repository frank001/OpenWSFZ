# 8.6 live re-confirmation — run notes (COMPLETE — see `report.md` for the finalized write-up)

Session ended gracefully (operator-initiated `POST /api/v1/decode/stop` at 18:39:06 local) after
32m4s. These notes are the raw, timestamped working log kept during the run; `report.md` is the
polished analysis and is the citable artefact going forward — these notes are kept for the
detailed blow-by-blow and are not expected to be read on their own.

**Purpose:** `tasks.md` 8.6 — re-run the same live setup used in 6.6/7.6, now with 8.1's
pipeline-timing instrumentation deployed, to gather the diagnostic data 8.3 needs to isolate
root cause. No fix has landed yet (8.3/8.4 still open) — this run is not expected to show
convergence; it is expected to show whether real inter-window elapsed time and chunk-dequeue
gaps track, or diverge from, the still-growing accumulated deviation.

## Planned duration

Per the Captain (2026-07-24, ~18:20 local): default to a **short session, ~1-2 hours**, matching
`tasks.md` 7.6's own original plan (before that run grew to 6h16m based on what it observed) —
not an open-ended multi-hour commitment from the start. First checkpoint ~19:37-20:07 local:
review what the monitor/log have collected and decide explicitly, from evidence, whether to stop
and write up or extend with a stated reason. Corrected here after initially over-framing this as
open-ended in conversation.

## Setup

- Code under test: `29041f7` (root-cause pipeline-timing instrumentation) + `82469ca` (docs-only
  test-count correction, no `src/` change) on top.
- Daemon: PID 38336, `dotnet run` (Debug build), started 2026-07-24 16:07:05Z.
- Capture device: `'Microphone (2- USB Audio CODEC )'`,
  `d451e08c-82b5-446e-a5f1-1bdd8fceeac2`, WASAPI — same device family as `ce13e30`/`1cebf81`.
- Band: 20 m (14.074 MHz FT8), per Captain.
- Log file: `logs/openswfz-20260724T160705Z.log` (git-ignored, local only, NFR-021).
- WSJT-X running in parallel, ALL.TXT cleared before this run, capturing session WAV files.
- Confirmed before starting to monitor: `CycleFramer started` (16:07:15Z cycle boundary,
  4.209 s leading silence), `Resampling pipeline ready` on the expected device/rate
  (48000 Hz -> 12000 Hz), and — critically — the new Debug-level instrumentation lines
  (`WASAPI capture cadence`, `Capture pipeline cadence`, `Cycle boundary pipeline timing`)
  are actually present in the live log, confirming Debug-level file logging is active and
  the running binary includes 8.1's instrumentation (not a stale pre-instrumentation build).

## What to watch for

- Every `Cycle boundary resync` (correction firing): does the *next* drift-check reading
  land near the noise floor this time, or re-establish near the pre-correction magnitude
  (the `1cebf81` failure mode)?
- `Cycle boundary pipeline timing`'s `real inter-window elapsed` — does it track ~15.000 s
  throughout (points away from "window physically takes longer to fill"), or drift/grow in a
  way that correlates with the accumulated deviation?
- `chunk dequeue gaps` / `WASAPI capture cadence` / `Capture pipeline cadence` maxima — any
  growth over the session pointing at upstream backpressure/scheduling delay?
- Any `[ERR]`/`[FTL]`, or `Heartbeat:` lines with any field `=false` (device/capture dropout).

## Timeline (updated as the run progresses)

- 18:07 local (16:07 UTC) — daemon started.
- 18:14 local — `qa/endurance/2026-07-24-29041f7/monitor.sh` armed (Monitor task `bdg672fq2`),
  watching for corrections, `[ERR]`/`[FTL]`, heartbeat drops, with a 30-min periodic status
  fallback. Smoke-tested against synthetic log lines before arming for real (all 4 detection
  branches fire correctly).

### Early observation (first ~7 minutes, pre-dating the monitor's arm time — recovered via grep)

Two corrections already fired: #1 at 18:12:00 (deviation 2409.6 -> correction applied),
#2 at 18:13:30 (deviation 2768.6). Both reproduce the exact `1cebf81` non-convergence pattern:
the very next drift-check reading after each correction is *higher*, not lower
(18:12:00 -> 18:12:15: 2409.6 -> 2753.4; 18:13:30 -> 18:13:45: 2768.6 -> 2802.3).

More interesting: the new pipeline-timing instrumentation shows `real inter-window elapsed`
sitting at 14.97-15.05 s throughout this whole window (noise around nominal, no drift), while
`deviation` was *already* ~2200-2800 samples (~185-235 ms) on the very first post-window-1
reading (18:07:30) — i.e. this isn't a quantity that grew from ~0 over these 7 minutes, it
showed up nearly full-sized immediately and has been bouncing in that band since, uncorrelated
with real inter-window elapsed time. Chunk-dequeue-gap stats are flat and unremarkable
(avg ~62 ms, max ~63-68 ms, consistent cycle to cycle).

**Working observation, NOT a conclusion — needs the rest of this session to confirm or refute:**
this looks more consistent with a roughly-constant, present-from-minute-one pipeline/measurement
offset (e.g. a fixed buffering latency between real audio capture and when `CycleFramer` reads
`_clock.UtcNow` at window-close) than with either (a) genuine capture-rate drift, which would
show up as real-inter-window-elapsed growing, or (b) a slowly-growing scheduling delay as
Evidence 5 in the dev-task speculated. It does NOT yet explain `ce13e30`/`1cebf81`'s multi-hour
climb from ~1,000 to ~17,000+ samples — that growth, if it reproduces here too, must be a
separate/additional effect layered on top of whatever this early roughly-fixed offset is. Keep
watching for hours, not minutes, before treating this as the answer.

### Corrections #3-4 (18:15:30, 18:25:15) — routine, logged without interrupting

Same non-convergent pattern continues (next reading after #3: 2444.9 -> 2288.1, a rare
*decrease*; #4 fired at 3325.7, ten minutes after #3, having bounced 2200-3300 samples in
between). Notably, the oscillation band's floor crept up over those ten minutes (~2288 low near
18:15:45 vs. ~2641-3068 lows by 18:24-18:25) — a small-scale version of the same slow climb
`ce13e30`/`1cebf81` showed over hours, just compressed into minutes here. Not treating this as
confirmed yet, just noting it tracks the "fixed offset + separate slow-growth component" picture
above.

### Correction #5 (18:31:46) — routine, matches the climbing-floor trend already reported

Fired right where the 18:30:40 status update's trend line pointed (deviation 3442.9 at 18:30:01
-> correction at 3444.5 at 18:31:46, essentially no further climb in between — persistence gate
took the very next 3/3 streak). Real inter-window elapsed / chunk-dequeue-gap stats still flat
per the last check. No action needed; continuing toward the ~19:37-20:07 checkpoint.

### Correction #6 (18:32:46) — only 1 minute after #5; mechanically explained, not a new symptom

Checked the drift-check sequence between #5 and #6: post-#5 deviation was still ~3300 samples
(18:32:01), i.e. the correction barely touched the elevated baseline, so only a few cycles of
"non-decreasing, same-sign" wobble were needed to re-clear the persistence gate. Corrections are
firing closer together *because* the oscillation floor has risen into a band where the 3-reading
gate is satisfied almost by chance — this is the climbing-baseline trend already logged, not a
distinct new failure mode (not a reversion to "fires every single cycle" from section 6 — still
gated, still occasionally skipping a cycle, just more often now).

### Correction #7 (18:33:46) — third in a row ~60s apart; correction *magnitude* looks like it may be plateauing

Deviation-at-fire for the last three: 3444.5 -> 3466.1 -> 3380.5 — essentially flat, not still
climbing, over this stretch. Tentatively similar to the loose plateau `1cebf81`'s report noted
near its own session end (13,037 -> 13,403 -> 13,037 -> 13,801). Far too early (27 min in) to
call this settled — could easily resume climbing — but worth having in view at the checkpoint.

### Correction #8 (18:38:47) — still within the same plateau band

Deviation-at-fire 3453.5, in line with the last four (3444.5, 3466.1, 3380.5, 3453.5) — the
~3380-3470 band holds. Recommended stopping the run to the Captain at this point (see decision
below); awaiting the operator-initiated capture stop before wrapping up.
