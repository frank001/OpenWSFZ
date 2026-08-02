#!/usr/bin/env bash
# QA-judgment restart tool, 2026-08-01: fires ONLY on QA's (this session's) direct judgment during
# a check, per the Captain's standing policy -- NOT auto-triggered by any supervisor script, NOT
# the cross-instance decode-collapse check (disarmed, see dev-tasks/2026-08-01-8080-decode-
# collapse-after-long-uptime.md §6). One bundled script, one shell approval, per the lesson from
# the 2026-08-01 scratch-daemon drill: find PID, kill, wait, relaunch, confirm, log -- all as
# subprocesses of this single invocation, never a sequence of separate calls.
set -u

CAPTURE_DIR="D:/Projects/claude/OpenWSFZ-8080-capture"
EXE="$CAPTURE_DIR/OpenWSFZ.Daemon.exe"
CONFIG="$CAPTURE_DIR/config.json"
PORT=8080
LOG="$CAPTURE_DIR/restart-supervisor.log"     # same log the supervisor writes to -- one shared
                                               # timeline for this instance, QA-triggered restarts
                                               # clearly tagged so they're distinguishable on read

log() {
    local line
    line="$(date -u +%Y-%m-%dT%H:%M:%SZ) $1"
    echo "$line" | tee -a "$LOG"
}

find_pid() {
    powershell.exe -NoProfile -Command \
        "(Get-CimInstance Win32_Process -Filter \"Name='OpenWSFZ.Daemon.exe'\" | Where-Object { \$_.CommandLine -like '*8080-capture*' } | Select-Object -First 1 -ExpandProperty ProcessId)" \
        2>/dev/null | tr -d '\r'
}

find_latest_log() { ls -t "$CAPTURE_DIR"/logs/openswfz-*.log 2>/dev/null | head -1; }
snapshot_logs() { ls "$CAPTURE_DIR"/logs/openswfz-*.log 2>/dev/null | sort; }
find_new_log_since() { comm -13 <(printf '%s\n' "$1") <(snapshot_logs) | tail -1; }

REASON="${1:-unspecified -- pass a reason as \$1}"
log "QA-RESTART(8080): anomaly judged present >5min ($REASON). Executing bundled restart."

before_logs=$(snapshot_logs)
pid=$(find_pid)
if [ -z "$pid" ]; then
    log "QA-RESTART(8080): no running daemon found -- aborting, nothing to restart."
    exit 1
fi
log "QA-RESTART(8080): found daemon PID $pid."

taskkill //F //PID "$pid" >/dev/null 2>&1
sleep 2
still=$(find_pid)
if [ -n "$still" ]; then
    log "QA-RESTART(8080): kill did NOT take (still running as $still) -- aborting."
    exit 1
fi
log "QA-RESTART(8080): killed PID $pid, confirmed dead."

sleep 3
powershell.exe -NoProfile -Command \
    "Start-Process -FilePath '$EXE' -ArgumentList '--config','$CONFIG','--port','$PORT' -WorkingDirectory '$CAPTURE_DIR'" >/dev/null 2>&1
log "QA-RESTART(8080): relaunch command issued."

waited=0
newlog=""
while [ "$waited" -lt 60 ]; do
    newlog=$(find_new_log_since "$before_logs")
    if [ -n "$newlog" ] && grep -q "Heartbeat:" "$newlog" 2>/dev/null; then
        log "QA-RESTART(8080): restart CONFIRMED healthy -- new log $newlog, heartbeat resumed."
        log "QA-RESTART(8080): *** RESULT: PASS ***"
        exit 0
    fi
    sleep 5
    waited=$((waited + 5))
done

log "QA-RESTART(8080): *** RESULT: FAIL -- did not confirm healthy within 60s. Escalate to the Captain, do not retry blindly. ***"
exit 1
