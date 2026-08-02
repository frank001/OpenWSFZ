# QA session handoff #2 — context about to be cleared again, run continues unattended

**Author:** QA (this session), 2026-08-01 22:16Z (`date -u`, per HK-017). This supersedes
`2026-08-01-2001-qa-context-clear-handoff-multiday-20m-live-run.md` for anything about *how the
standing check runs* (§1-2 below) — that changed materially this session. Everything else in the
2001Z handoff (contamination note, restart policy, dev-task, gotchas) is unchanged and still the
reference. Read both; this one is the delta.

---

## 0. What changed since the 2001Z handoff (read this first)

The prior handoff said a `CronCreate` job was firing every 30 min to prompt the standing check.
**That job is gone and should not be recreated.** Over this session the Captain reported it was
not actually firing autonomously while he was genuinely AFK — no report appeared until he sent a
message, contrary to the tool's own "fires while idle" documentation. Rebuilt on `Monitor` next;
found that a `Monitor`-owned background process only survives until session end (documented), and
that `TaskStop` on it reported "success" while the underlying `bash.exe` was **still running**
two seconds later — a half-detached orphan, not a clean stop. Full writeup, don't re-derive this:
**`hk023-cron-not-durable-use-detached-process-plus-log-tail.md`** (project memory, HK-023).

**Current, correct mechanism — do not replace this with `CronCreate` again:**

- The check loop is a genuinely detached OS process: `qa/endurance/2026-08-01-status-check-loop.sh`,
  launched via `nohup ... > logfile 2>&1 < /dev/null & disown`, currently **PID `11964`**
  (re-verify, don't trust this number blind — `Get-CimInstance Win32_Process -Filter
  "Name='bash.exe'" | Where-Object CommandLine -match 'status-check-loop'`). It runs
  `qa/endurance/status-check.sh` immediately, then sleeps 1800s, forever, and writes everything to
  `qa/endurance/2026-08-01-status-check-loop.log`. This process is not owned by any tool and is
  not tied to this or any Claude session — it is the same class of process as the 8080/8081
  supervisors, which were directly confirmed to survive this session's own earlier crash intact.
  **The only way it stops is an explicit kill of that PID** — nothing about a session ending,
  crashing, or being cleared touches it.
- Notifications are separate and disposable: a `Monitor` task doing `tail -n0 -f
  qa/endurance/2026-08-01-status-check-loop.log` (session task id `b68c85j0c` as of this handoff —
  it will not survive this context clear, and that's fine and expected). **A fresh session should
  re-attach a new `tail -f` Monitor on that same log file** to resume getting notified per cycle;
  this does not touch or restart the underlying loop, which keeps running regardless.
- Per the Captain's explicit correction this session: **do not ask for a decision via shell
  interaction, ever, for the anomaly-restart policy.** Detection is QA's judgment on each cycle's
  numbers (not a scripted heuristic — same reasoning as why the cross-instance decode-collapse
  check stays disarmed, see 2001Z handoff §4); response, when a genuine one-sided anomaly persists
  >5 min, is the atomic restart script run immediately, no confirmation sought. Only two things
  escalate to the Captain: the restart cap (5/run) being reached, or a restart script reporting
  FAIL.
- The Captain also asked, separately, that the **full raw `status-check.sh` output be shown
  verbatim** on every check (routine all-clear included), with judgment as a brief note
  underneath, not instead of it. Keep doing that whenever reporting a check to him — the loop's
  own log already has this shape, so just relay/quote it.

## 1. What is running, right now

Same daemons/supervisors as the 2001Z handoff, unchanged and re-verified at 22:16Z this session:

| | 8080 | 8081 |
|---|---|---|
| Directory | `D:\Projects\claude\OpenWSFZ-8080-capture\` | `D:\Projects\claude\OpenWSFZ-8081-capture\` |
| Audio device | Microphone (2- USB Audio CODEC), physical radio | Voicemeeter Out B1 (SDR Uno) |
| Role | Decisive corpus — do not touch config, no retuning, no Settings-page saves | Secondary, full-record |
| PID (re-verified 22:16Z) | `34596` (started `2026-08-01T10:57:02Z` — the Window-4 decode-collapse fix restart from earlier, not new) | `10212` (unchanged since 07-31 launch) |
| Supervisor | `qa/endurance/2026-07-31-supervisor-8080.sh` (multiple `bash.exe` PIDs is the known harmless exec-chain quirk) | `qa/endurance/2026-07-31-supervisor-8081.sh` (same) |

Cross-instance decode-collapse auto-restart check still **DISARMED** — do not re-arm without
reading 2001Z handoff §4 first.

**Snapshot at 22:08Z** (last loop-check before this handoff; recompute fresh, don't trust going
forward): WAVs 6254/6256/6225 (8080/8081/WSJT-X), `ALL.TXT` 110,595/126,821/211,516, ratios 8080
45.2%/30min, 8081 53.0%/30min — both had been softening gently and co-directionally over the prior
hour (roughly 52-53%→45-47% on 8080, 60-61%→53-55% on 8081), moving together, not one-sided, judged
as within baseline / band-conditions drift, no action taken. `0-dec/20` = `0/20` both. No
`[ERR]`/`[FTL]`. **Autonomous-restart tally: still 0/5.**

## 2. The standing status-check format (unchanged from 2001Z handoff §2)

```
Source | Band | WAVs | ALL.TXT | vs WSJT-X | Decodes/30min | 0-dec/20
```

Full definitions in the 2001Z handoff §2 — not repeated here, still accurate.
`qa/endurance/status-check.sh` implements this exactly; the loop script just calls it on a timer.

## 3. QA-judgment autonomous restart policy (unchanged from 2001Z handoff §3, reiterated per Captain correction this session)

- No supervisor-script changes, decode-collapse check stays disarmed.
- Trigger: one-sided (one instance bad, other healthy, no external cause stated), persisted >5 min
  (the `0-dec/20` window already samples this).
- Response: run `qa/endurance/restart-8080-on-anomaly.sh` or `restart-8081-on-anomaly.sh` (reason
  as `$1`) — one atomic call. **Do this immediately on judgment, do not ask the Captain first.**
- Cap 5/run, tallied in `qa/endurance/2026-07-31-2dacd1a/CONTAMINATION-NOTE.md`. Log every restart
  there (same shape as Window 4). Cap reached or a restart script FAIL → stop and escalate; that is
  the one legitimate case for surfacing to the Captain.

## 4. Where everything lives

- **This session's addition:** `qa/endurance/2026-08-01-status-check-loop.sh` (the loop),
  `qa/endurance/2026-08-01-status-check-loop.log` (its output/history) — read the tail of this log
  first in a fresh session to see recent checks without waiting for the next fire.
- **Lesson learned, written to project memory:** HK-023
  (`hk023-cron-not-durable-use-detached-process-plus-log-tail.md`), pointed to from the top of
  `MEMORY.md`'s standing-rules block. Read it before reaching for `CronCreate` for anything meant
  to survive a session boundary.
- Live corpus + contamination record: `qa/endurance/2026-07-31-2dacd1a/CONTAMINATION-NOTE.md`.
- Open defect: `dev-tasks/2026-08-01-8080-decode-collapse-after-long-uptime.md`.
- Restart scripts: `qa/endurance/restart-8080-on-anomaly.sh`, `restart-8081-on-anomaly.sh`.
- Prior handoff (still the reference for everything not covered in §0 above):
  `qa/cycleframer-alignment-replay/2026-08-01-2001-qa-context-clear-handoff-multiday-20m-live-run.md`.
- Architect's original brief: `qa/cycleframer-alignment-replay/2026-07-31-1907-...-preflight-
  brief-multiday-20m-live-run.md`.

## 5. First thing to do in a fresh session picking this up

1. `date -u` for a real timestamp.
2. Re-verify the loop process is alive (`Win32_Process` query above) and the daemon PIDs
   (`34596`/`10212`, but re-check — they may have changed if a judgment restart happened since
   this handoff; check the contamination note tally to see).
3. `tail -40 qa/endurance/2026-08-01-status-check-loop.log` for recent history.
4. Attach a fresh `tail -n0 -f` Monitor on that log for ongoing notifications.
5. Do not recreate a `CronCreate` job for this purpose (HK-023).

Per HK-011/HK-014, nothing here touches `src/`; per HK-017 timestamp is real `date -u`.
