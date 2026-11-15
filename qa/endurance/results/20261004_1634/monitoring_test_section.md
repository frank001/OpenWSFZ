# Monitoring test (this run only; not a template section)

Captain-directed disturbances of the audio chain on 2026-10-04, to see whether the #194
audio-setup sampler and the config-drift monitor notice them. All times UTC, taken from
`date -u` or from the sampler's own detection times (the sampler's period is 5 s, so a record
can lag the real action). Source: `audio_setup.jsonl`, `QA_NOTES.md`.

| # | Action (Captain) | Sampler record | State hash | Verdict |
|---|---|---|---|---|
| 1 | Movie audio routed to B1 and off again, 18:14:31 to 18:16:17 | `voicemeeter.strips[3].B1` 0→1 and 1→0, both caught, lag a few seconds (first detection 4 s before QA's start mark) | f41891d8 → db9af40a → f41891d8 | caught |
| 2 | WSJT-X slider 100% → 50% → 100%, 18:25:20 to 18:26:08 | none | unchanged | **VOID**: it was the TX (output) slider; WSJT-X has no RX gain; says nothing about an application's input gain; prediction not scored |
| 3 | Music onto B1, five toggles of about 1 to 5 s (by feel, not stopwatch), 18:40:21 to 18:42:14 | five on/off pairs, none missed (n = 5) | returned to f41891d8 | no floor claimed; the off record lagged the real off by up to about 10 s on the later toggles, mechanism unknown |
| 4 | Fast taps, about 15 (iirc), about 18:48:20 to 18:49:58 | five on/off pairs for about 15 taps (about 1 in 3 seen) | returned to f41891d8 | prediction "at least one tap missed" HIT; `vm_dirty_nonzero` 14 in the heartbeat (the dirty flag counts what the change records miss; mechanism UNTESTED) |

(An earlier, too-short attempt, 18:36:24 to 18:36:58, is also excluded: one on/off pair.)

**Config-drift monitor:** silent through every test, as it should be: it watches 12 config keys,
not audio. After the daemon stopped (05:30:45Z) it logged `CONFIG-POLL-FAILED` every minute
(32 failures to 06:02Z) until killed at teardown: expected, not a finding. No DRIFT line in the run.

**Not tested:** a gain change on a strip other than 3; the Windows endpoint format; a path that
bypasses Voicemeeter state; the receive level of an application.

**Excluded from Section 4 and the ANOVA** (Captain's ruling): 18:14:31 to 18:16:17, 18:36:20 to
18:36:58, 18:40:21 to 18:42:14, 18:48:15 to 18:50:00 (any 15 s cycle overlapping). 26 cycles per
appraiser removed (OpenWSFZ 652 lines, WSJT-X 939), by timestamp only; script `filter_windows.py`.
The 18:25 slider window was not excluded (no receive effect).

## Sampler over the whole run (outside the tests)

Coverage 100.0 % of 46 594 s (max gap 61.2 s), 0 worker crashes, 0 restarts, 64 change records
(24 inside the test windows, 40 outside), `unverified_start_diff` 0. The 40 outside:

- 16:35:22 `strips[0].mute` 1→0: the Captain's unmute (the five all-zero WAVs 163400 to 163500
  precede it; the first ALL.TXT cycle is 163515).
- Strip 3 (AUX, not routed to B1 outside the tests) gain changed at 17:35 (4 steps), 20:59, 21:14.
  Strip 0 (the radio) was untouched.
- Windows application-session churn (a game, a browser, Steam, VLC appearing and leaving): 31 records, none on the capture path.
- `windows.endpoints[30]` (Voicemeeter VAIO, a render endpoint) muted 21:14:55 to 21:20:27.
- Start vs end snapshots differ in 5 fields only: the unmute, strip 3 gain −24 → −15 dB, and one VLC session gone.
