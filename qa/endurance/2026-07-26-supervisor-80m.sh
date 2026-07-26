#!/usr/bin/env bash
# Overnight crash-recovery supervisor for the 80m/night live-run corpus (Captain's instruction,
# 2026-07-26 night, "this run will be several hours unattended"). Adapted from the validated
# 2026-07-24 template (qa/endurance/2026-07-24-supervisor.sh, used successfully for an 11h51m
# unattended run) with two changes for this session:
#   - EXE points at the self-contained `main` baseline build published into a separate worktree
#     (D-001 requires this corpus NOT be built from d001-c4-min-score-sweep's dirty tree — the
#     branch's native libft8.dll carries an unexplained size delta the Architect has flagged as a
#     merge blocker; a corpus built on it wouldn't be trustworthy evidence).
#   - No CycleFramer-drift-specific DIGEST fields (driftline/timingline) — this run isn't testing
#     cycle-boundary correction, so those lines never appear in this build's log; the digest
#     still reports retry count hourly.
#
# On a genuine failure signature (ERR/FTL log line, unhandled exception, or >90s with no
# Heartbeat line at all): kill the daemon, log the event, wait RESTART_WAIT_SECS, relaunch,
# confirm it actually came back up and resumed decoding (persisted config: device = 'Microphone
# (2- USB Audio CODEC )', decodingEnabled = true, dialFrequencyMHz = 3.573 i.e. 80m), and
# continue watching. Stops trying after MAX_RETRIES restarts and logs that explicitly rather
# than looping forever.
#
# Restart mechanism: a direct hard kill (taskkill /F /PID) followed by a fresh detached launch
# of the same built exe from REPO_ROOT (so ALL.TXT/logs/ land in the same place as always —
# AllTxtWriter/file-log-sink resolve their configured relative paths against the process's
# current working directory, not the exe's own directory) — not the app's own graceful
# POST /api/v1/system/restart endpoint, since a hung or crashed process may not have a
# responsive HTTP server.
#
# Usage: RESTART_WAIT_SECS=<n> bash qa/endurance/2026-07-26-supervisor-80m.sh
# (RESTART_WAIT_SECS defaults to 300s per the 07-24 precedent; overridable for a fast
# mechanism-validation dry run before trusting this unattended — see the 07-26 validation note
# in the session's notification doc for the dry-run this script was put through before being
# armed for real.)

set -u

REPO_ROOT="D:/Projects/claude/OpenWSFZ"
EXE="D:/Projects/claude/OpenWSFZ-worktrees/main-80m-baseline/src/OpenWSFZ.Daemon/bin/Release/net10.0/win-x64/publish/OpenWSFZ.Daemon.exe"
SUPERVISOR_LOG="$REPO_ROOT/logs/restart-supervisor-80m.log"
MAX_RETRIES=5
RESTART_WAIT_SECS="${RESTART_WAIT_SECS:-300}"
retry_count=0

log_event() {
    local line
    line="$(date -u +%Y-%m-%dT%H:%M:%SZ) $1"
    echo "$line" >> "$SUPERVISOR_LOG"
    echo "$line"
}

find_daemon_pid() {
    # tasklist's CSV output gives the real Windows PID directly -- `ps -W`'s first column is an
    # MSYS-synthetic PID that silently no-ops taskkill (found the hard way in the 07-24 validation).
    #
    # BUG FOUND IN THIS SCRIPT'S OWN 07-26 VALIDATION RUN: when no matching process exists,
    # tasklist prints a plain (unquoted) line to stdout -- `INFO: No tasks are running which
    # match the specified criteria.` -- instead of emitting nothing. Without the `grep '^"'`
    # filter below, sed's substitution doesn't match that line and (with no -n flag) prints it
    # through verbatim, so find_daemon_pid() returned that literal sentence as if it were a PID.
    # kill_and_restart() then passed it to `taskkill //PID`, which failed, and immediately
    # re-checked "still there?" via the same broken call -- which returned the same non-empty
    # garbage string again -- concluding the (already-dead) process was "still running" and
    # aborting the restart entirely instead of proceeding to relaunch. Caught live: a deliberate
    # kill during this script's own mandatory HK-013 validation left the daemon down for ~4.5
    # minutes before this was found and fixed. The `grep '^"'` keeps only genuine quoted-CSV
    # data lines, so a no-match case now correctly yields empty output.
    tasklist //FI "IMAGENAME eq OpenWSFZ.Daemon.exe" //FO CSV //NH 2>/dev/null \
        | grep '^"' \
        | sed -E 's/^"([^"]+)","([^"]+)".*/\2/'
}

find_latest_log() {
    ls -t "$REPO_ROOT"/logs/openswfz-*.log 2>/dev/null | head -1
}

# Snapshot of existing log files, taken BEFORE a kill+relaunch, so a still-alive (not actually
# killed) old process appending to its own file can't be mistaken for a healthy new instance.
snapshot_logs() {
    ls "$REPO_ROOT"/logs/openswfz-*.log 2>/dev/null | sort
}

find_new_log_since() {
    local before="$1"
    comm -13 <(printf '%s\n' "$before") <(snapshot_logs) | tail -1
}

kill_and_restart() {
    local reason="$1"
    log_event "SUPERVISOR: failure detected ($reason). Killing daemon and restarting (attempt $((retry_count+1))/$MAX_RETRIES)."

    local before_logs
    before_logs=$(snapshot_logs)

    local pid
    pid=$(find_daemon_pid)
    if [ -n "$pid" ]; then
        taskkill //F //PID "$pid" >/dev/null 2>&1
        local kill_rc=$?
        sleep 2
        local still_there
        still_there=$(find_daemon_pid)
        if [ -n "$still_there" ]; then
            log_event "SUPERVISOR: kill of PID $pid did NOT take (rc=$kill_rc, still running as $still_there) -- aborting this restart attempt."
            return 1
        fi
        log_event "SUPERVISOR: killed PID $pid, confirmed dead."
    else
        log_event "SUPERVISOR: no running OpenWSFZ.Daemon.exe PID found (already dead)."
    fi

    log_event "SUPERVISOR: waiting ${RESTART_WAIT_SECS}s before restart."
    sleep "$RESTART_WAIT_SECS"

    powershell.exe -NoProfile -Command \
        "Start-Process -FilePath '$EXE' -WorkingDirectory '$REPO_ROOT'" >/dev/null 2>&1
    log_event "SUPERVISOR: relaunch command issued ($EXE)."

    local waited=0
    local newlog=""
    while [ "$waited" -lt 60 ]; do
        newlog=$(find_new_log_since "$before_logs")
        if [ -n "$newlog" ] && grep -q "CycleFramer started" "$newlog" 2>/dev/null; then
            log_event "SUPERVISOR: restart CONFIRMED healthy -- new log $newlog, decode resumed."
            printf '%s' "$newlog" > "$REPO_ROOT/logs/.supervisor-80m-current-log"
            return 0
        fi
        if [ -n "$newlog" ] && grep -q "Hosting failed to start\|address already in use" "$newlog" 2>/dev/null; then
            log_event "SUPERVISOR: new instance failed to bind (port still held?) -- $newlog"
            return 1
        fi
        sleep 5
        waited=$((waited + 5))
    done

    log_event "SUPERVISOR: restart did NOT confirm healthy decode resume within 60s (no 'CycleFramer started' seen in any new log since $EXE was relaunched)."
    return 1
}

CURRENT_LOG=$(find_latest_log)
log_event "SUPERVISOR ARMED (80m corpus): watching $CURRENT_LOG. max_retries=$MAX_RETRIES restart_wait_secs=$RESTART_WAIT_SECS"

while true; do
    [ -z "$CURRENT_LOG" ] && CURRENT_LOG=$(find_latest_log)
    log_event "SUPERVISOR: watch phase on $CURRENT_LOG"

    failure_reason=""
    last_heartbeat_epoch=$(date +%s)
    last_status_epoch=$(date +%s)

    exec 3< <(tail -f -n 0 "$CURRENT_LOG")
    while true; do
        if read -t 10 -r line <&3; then
            now=$(date +%s)
            if [[ "$line" == *"[ERR]"* || "$line" == *"[FTL]"* || "$line" == *"Unhandled exception"* ]]; then
                failure_reason="log-error: $line"
                break
            fi
            if [[ "$line" == *"Heartbeat:"*"=false"* ]]; then
                echo "HEARTBEAT-DROP: $line"
            fi
            if [[ "$line" == *"Heartbeat:"* ]]; then
                last_heartbeat_epoch=$now
            fi
        else
            rc=$?
            if [ "$rc" -lt 129 ]; then
                failure_reason="log pipe closed unexpectedly (rc=$rc) -- $CURRENT_LOG"
                break
            fi
            # read timed out (no line in 10s) -- fall through to staleness check, loop again.
        fi

        now=$(date +%s)
        if [ $((now - last_heartbeat_epoch)) -gt 90 ]; then
            failure_reason="heartbeat stall: no Heartbeat line of any kind in >90s"
            break
        fi
        if [ $((now - last_status_epoch)) -ge 3600 ]; then
            echo "DIGEST ($(date -u +%H:%M:%SZ)): retries_so_far=$retry_count"
            last_status_epoch=$now
        fi
    done
    exec 3<&- 2>/dev/null

    [ -z "$failure_reason" ] && failure_reason="watch loop ended for an undetermined reason"

    if [ "$retry_count" -ge "$MAX_RETRIES" ]; then
        log_event "SUPERVISOR: failure ($failure_reason) but already at $MAX_RETRIES/$MAX_RETRIES retries -- giving up, no further restart attempts. Manual intervention needed."
        break
    fi

    retry_count=$((retry_count + 1))
    if kill_and_restart "$failure_reason"; then
        CURRENT_LOG=$(find_latest_log)
        continue
    else
        if [ "$retry_count" -ge "$MAX_RETRIES" ]; then
            log_event "SUPERVISOR: restart attempt $retry_count/$MAX_RETRIES failed to confirm healthy -- max retries reached, giving up."
            break
        fi
        log_event "SUPERVISOR: restart attempt $retry_count/$MAX_RETRIES did not confirm healthy within 60s -- will re-enter watch loop and retry again on next failure."
        CURRENT_LOG=$(find_latest_log)
        continue
    fi
done

log_event "SUPERVISOR EXITED (retry_count=$retry_count)."
