# QA session handoff — context about to be cleared, run continues unattended

**Author:** QA (this session), 2026-08-01 20:01Z (`date -u`, per HK-017), written specifically
because the Captain is clearing this conversation's context and the run keeps going. Everything a
fresh session needs to pick this up cold is below — do not assume prior conversation memory.

---

## 1. What is running, right now

Two daemon instances + two supervisors, multi-day 20m corpus-gathering run (Architect's brief:
`qa/cycleframer-alignment-replay/2026-07-31-1907-...-preflight-brief-multiday-20m-live-run.md`).

| | 8080 | 8081 |
|---|---|---|
| Directory | `D:\Projects\claude\OpenWSFZ-8080-capture\` | `D:\Projects\claude\OpenWSFZ-8081-capture\` |
| Audio device | Microphone (2- USB Audio CODEC), physical radio | Voicemeeter Out B1 (SDR Uno) |
| Paired with | Live WSJT-X on the same physical feed | Free to band-hop (currently still 14.074) |
| Role | **Decisive corpus — do not touch config, do not retune, no Settings-page saves** | Secondary, full-record (`mode=all`) |
| PID as of 20:01Z | `34596` | `10212` |
| Supervisor script | `qa/endurance/2026-07-31-supervisor-8080.sh` (running, multiple PIDs due to a known git-bash exec-chain quirk — harmless) | `qa/endurance/2026-07-31-supervisor-8081.sh` (same) |

Both supervisors are running with the cross-instance decode-collapse auto-restart check
**DISARMED** (`ENABLE_CROSS_INSTANCE_DECODE_CHECK` not set / defaults to 0) — do not re-arm it
without reading §4 below first. Everything else in the supervisors (heartbeat-stall,
archiving-liveness, log-rotation guard, `[ERR]`/`[FTL]` detection) is live and unchanged from the
original design.

**Snapshot at 20:01Z** (for continuity — recompute fresh, don't trust these numbers going forward):
WAVs 5750/5751/5720 (8080/8081/WSJT-X), `ALL.TXT` lines 101,178/115,903/192,691, zero errors, zero
supervisor restarts on either instance.

## 2. The standing status-check format — use this exact shape when asked to "check"

```
Source | Band | WAVs | ALL.TXT | vs WSJT-X | Decodes/30min | 0-dec/20
```

- **WAVs / ALL.TXT**: `find .../cycle-audio -iname "*.wav" | wc -l` and `wc -l < ALL.TXT`, for all
  three sources (WSJT-X's own paths: `%LocalAppData%\WSJT-X\save\` and `...\WSJT-X\ALL.TXT`).
- **vs WSJT-X**: this instance's `ALL.TXT` line count as a % of WSJT-X's. WSJT-X's own row shows
  `-` here (it isn't compared against itself).
- **Decodes/30min**: count `ALL.TXT` lines whose leading `YYMMDD_HHMMSS` timestamp field is within
  the last 30 minutes (`awk -v t="$(date -u --date="-30 minutes" +%y%m%d_%H%M%S)" '$1 >= t' file |
  wc -l`), shown alongside its own % of WSJT-X's 30-min count. Added specifically because the
  cumulative `vs WSJT-X` column dilutes short-duration deviations into invisibility once the
  session has 100,000+ lines — see Window 5 in the contamination note for the actual case that
  motivated this.
- **0-dec/20**: how many of the last 20 decode-count log lines (`grep -oP "\d+(?= decode\(s\)
  found)" <logfile> | tail -20`) were exactly `0`. **Informational only** — a single zero cycle is
  normal band variance, not a signal by itself. What mattered in the one real incident (Window 4)
  was sustained near-zero across the whole 20-cycle window, not any individual zero.
- Also silently check (report only if nonzero): `grep -c "\[ERR\]\|\[FTL\]"` on each instance's
  *current* log file (use the actual current filename, not a glob — old bundled stale logs exist
  in every capture dir from historical testing and will produce false "errors" if you grep across
  all `logs/*.log`), and `grep -c "restarting"` in each `restart-supervisor.log`.
- Always lead with a UTC timestamp (`date -u`), mechanically pulled, never hand-typed.

## 3. QA-judgment autonomous restart policy (replaces any supervisor-level auto-restart)

Per the Captain's explicit direction, 2026-08-01:

- **No supervisor script changes for this purpose.** The decode-collapse check stays disarmed (§4
  explains why). All detection and action is QA's own direct judgment during checks — not a bash
  heuristic, not a spawned agent (explicitly told not to create agents for this).
- **Trigger**: an anomaly that has clearly persisted for more than 5 minutes. The `0-dec/20`
  column (20 cycles × 15s = 5 minutes) is sized exactly to make this assessable from a single
  check without a separate wait. A one-sided anomaly (this instance bad, the other one healthy, no
  external cause offered) is the pattern that matters — a shared/correlated dip (real over-the-air
  noise, a genuine band-conditions shift) is not a trigger; neither is any deviation the Captain
  has already attributed to a stated external cause (a gain/tuning change he's doing himself —
  confirmed via Window 5, restarting cannot fix a config/gain setting).
- **Response, when a genuine trigger occurs**: run the pre-staged single-script restart —
  `qa/endurance/restart-8080-on-anomaly.sh` or `restart-8081-on-anomaly.sh` (pass a reason string
  as `$1`) — **one shell approval, one bundled script** that does find-PID → kill → wait → relaunch
  → confirm-via-real-Heartbeat-line → log, all as subprocesses of that one call. **Do not** do this
  as a sequence of separate PowerShell/Bash calls — that was explicitly tested and corrected earlier
  this session; every restart action must be one atomic script.
- **Cap: 5 restarts total for the run.** Tracked as a running tally in
  `qa/endurance/2026-07-31-2dacd1a/CONTAMINATION-NOTE.md` (currently **0/5 used** as of this
  handoff — the two "restarts" during testing were on the throwaway scratch daemon and explicitly
  do not count). If the cap is reached, stop restarting and escalate instead of continuing to act.
- **Every restart must be logged** in that same contamination note, same shape as Window 4 — UTC
  span, what was observed, what action was taken, outcome. Do not skip this even if the Captain is
  AFK; that's exactly when it matters most.
- **If a restart script reports FAIL** (doesn't confirm healthy within 60s), it stops on its own
  rather than retrying — treat that as an immediate signal to stop and escalate to the Captain,
  not to try again on your own judgment.

## 4. Why the decode-collapse auto-restart is disarmed, and what NOT to do about it

A cross-instance decode-collapse detector was drafted, unit-tested against real numbers, briefly
armed live, then properly integration-tested via a throwaway scratch daemon (port `9998`,
`D:\Projects\claude\OpenWSFZ-test-decode-collapse\` — directory preserved, not deleted, contains
the test harness and drill scripts, currently stopped). **The integration test found it likely
doesn't work on this platform**: it never fired on its own decode-collapse trigger, a false
heartbeat-stall fired instead, and the evidence points at Windows/git-bash file-handle contention
between the check's own `tail -n 4000` read and the supervisor's persistent `tail -f` on the same
log file. Full writeup: `dev-tasks/2026-08-01-8080-decode-collapse-after-long-uptime.md` §6.
**Do not re-arm `ENABLE_CROSS_INSTANCE_DECODE_CHECK` without first fixing that log-reading
contention or redesigning the check to not share a file handle with the tailed log.**

The underlying defect this was meant to catch — a real, unexplained decode-quality collapse on
8080 after ~14h uptime, fixed once by a clean process restart, root cause still unknown — is
**still unresolved**. See the same dev-task for the full incident, what was ruled out (clipping,
silence, noise floor, hash-table saturation — all checked directly, not assumed), and open
hypotheses. This is exactly the class of anomaly §3's judgment-based restart exists to catch now.

## 5. Key facts / gotchas worth not re-discovering the hard way

- **Directory/port naming is deliberate**: keyed by port (`-8080-capture`, `-8081-capture`), never
  by band — see `CONTAMINATION-NOTE.md`'s own explanation and the 07-29 precedent
  (`qa/endurance/2026-07-29-5016363/CONTAMINATION-NOTE.md`) that this convention exists to prevent.
- **Every published binary copy carries stale bundled `logs/*.log` files** from unrelated historical
  testing (dated 07-11, 07-16, etc.) — `ls -t` occasionally races on these during a fresh daemon
  start (same-second mtime collision), so always resolve the log file explicitly by the daemon's
  actual startup timestamp when in doubt, not blindly via `ls -t | head -1` moments after launch.
- **`decodingEnabled=false` also disables audio capture entirely**, not just decoding — learned
  from the scratch-daemon test, not previously documented anywhere.
- **Gain/level chasing is a documented anti-pattern** (Windows 1, 2, and 5 in the contamination
  note) — a visual waterfall difference between two independently-rendered panels is not evidence
  of a problem by itself; check WAV peak amplitude or decode counts before touching a running
  capture's gain.
- **A 30-minute cron job** (`check`, session-only, auto-expires after 7 days from creation) is
  already firing periodically to prompt these checks — no need to recreate it unless it's gone.

## 6. Where everything lives

- Live corpus + contamination record: `qa/endurance/2026-07-31-2dacd1a/CONTAMINATION-NOTE.md` —
  five windows recorded, autonomous-restart tally, all measurement detail.
- Open defect: `dev-tasks/2026-08-01-8080-decode-collapse-after-long-uptime.md`.
- Restart scripts (pre-staged, ready): `qa/endurance/restart-8080-on-anomaly.sh`,
  `restart-8081-on-anomaly.sh`.
- Supervisors: `qa/endurance/2026-07-31-supervisor-8080.sh`, `-8081.sh` (decode-collapse block
  present but disarmed).
- Scratch test rig (stopped, preserved): `D:\Projects\claude\OpenWSFZ-test-decode-collapse\`.
- Architect's original brief: `qa/cycleframer-alignment-replay/2026-07-31-1907-...-preflight-
  brief-multiday-20m-live-run.md`.

Per HK-011/HK-014, nothing here touches `src/`; per HK-017 timestamp is real `date -u`, not
hand-typed.
