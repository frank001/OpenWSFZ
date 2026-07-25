#!/usr/bin/env bash
# Overnight crash-recovery supervisor for the fix-cycle-boundary-clock-drift 9.5 live run
# (Captain's instruction, 2026-07-24 night): on a genuine failure signature (ERR/FTL log line,
# unhandled exception, or >90s with no Heartbeat line at all), kill the daemon, log the event,
# wait RESTART_WAIT_SECS, relaunch, confirm it actually came back up and resumed decoding on the
# same persisted device/band, and continue watching the new log file. Stops trying after
# MAX_RETRIES restarts and logs that explicitly rather than looping forever.
#
# Restart mechanism: a direct hard kill (taskkill /F /PID) of OpenWSFZ.Daemon.exe followed by a
# fresh detached launch of the same built exe from the same working directory (repo root, matching
# the original process's own logged "Content root path"), NOT the app's own graceful
# POST /api/v1/system/restart endpoint — a hung or crashed process may not have a responsive HTTP
# server, so a mechanism that works uniformly regardless of *how* the process failed was chosen
# over one that only covers the graceful case. Auto-resume-on-launch is confirmed in
# src/OpenWSFZ.Daemon/Program.cs (ApplicationStarted hook): `if (deviceName is not null &&
# configStore.Current.DecodingEnabled) StartPipeline(deviceName);` — both are true in the
# currently-persisted config.json (device = 'Microphone (2- USB Audio CODEC )', decodingEnabled =
# true, dialFrequencyMHz = 7.074 i.e. 40m), so a fresh launch resumes the same test conditions with
# no extra API calls needed.
#
# Usage: RESTART_WAIT_SECS=<n> bash qa/endurance/2026-07-24-supervisor.sh
# (RESTART_WAIT_SECS defaults to 300 per the Captain's instruction; overridable for a fast
# mechanism-validation dry run before trusting this unattended.)

set -u

REPO_ROOT="D:/Projects/claude/OpenWSFZ"
EXE="$REPO_ROOT/src/OpenWSFZ.Daemon/bin/Debug/net10.0/OpenWSFZ.Daemon.exe"
SUPERVISOR_LOG="$REPO_ROOT/logs/restart-supervisor.log"
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
    # NOTE (found the hard way, 2026-07-24 validation test): `ps -W`'s first column is an
    # MSYS-synthetic PID, NOT the real Windows PID that taskkill needs -- using it silently
    # no-ops the kill (taskkill exits non-zero but the process lives on). tasklist's CSV output
    # gives the real PID directly (cross-checked against netstat's port-8080 LISTENING owner).
    tasklist //FI "IMAGENAME eq OpenWSFZ.Daemon.exe" //FO CSV //NH 2>/dev/null \
        | sed -E 's/^"([^"]+)","([^"]+)".*/\2/'
}

find_latest_log() {
    ls -t "$REPO_ROOT"/logs/openswfz-*.log 2>/dev/null | head -1
}

# Snapshot of existing log files, taken BEFORE a kill+relaunch. Used by wait_for_new_log below
# instead of mtime-sorting -- a still-alive (not actually killed) old process keeps appending to
# its own file, which can make it look "newest by mtime" even after a relaunch attempt, masking a
# failed kill as a false-positive healthy restart (also found during the validation test).
snapshot_logs() {
    ls "$REPO_ROOT"/logs/openswfz-*.log 2>/dev/null | sort
}

# Diffs a "before" snapshot against the current directory listing to find genuinely NEW log
# file(s) created since. Prints the newest such file, or nothing if none yet exist.
find_new_log_since() {
    local before="$1"
    comm -13 <(printf '%s\n' "$before") <(snapshot_logs) | tail -1
}

# Kills the current daemon (if any), waits, relaunches, and confirms it came back up healthy.
# Returns 0 on confirmed-healthy restart, 1 otherwise. Caller is responsible for retry counting.
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
            printf '%s' "$newlog" > "$REPO_ROOT/logs/.supervisor-current-log"
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
log_event "SUPERVISOR ARMED: watching $CURRENT_LOG. max_retries=$MAX_RETRIES restart_wait_secs=$RESTART_WAIT_SECS"

while true; do
    [ -z "$CURRENT_LOG" ] && CURRENT_LOG=$(find_latest_log)
    log_event "SUPERVISOR: watch phase on $CURRENT_LOG"

    failure_reason=""
    last_heartbeat_epoch=$(date +%s)
    last_status_epoch=$(date +%s)
    driftline=""
    timingline=""

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
            if [[ "$line" == *"Cycle boundary resync"* ]]; then
                echo "CORRECTION: $line"
            fi
            if [[ "$line" == *"Cycle boundary drift check"* ]]; then
                driftline="$line"
            fi
            if [[ "$line" == *"Cycle boundary pipeline timing"* ]]; then
                timingline="$line"
            fi
        else
            rc=$?
            if [ "$rc" -lt 129 ]; then
                failure_reason="log pipe closed unexpectedly (rc=$rc) -- $CURRENT_LOG"
                break
            fi
            # else: read timed out (no line in 10s) -- fall through to the staleness/digest
            # checks below and loop again; this is normal, not a failure by itself.
        fi

        now=$(date +%s)
        if [ $((now - last_heartbeat_epoch)) -gt 90 ]; then
            failure_reason="heartbeat stall: no Heartbeat line of any kind in >90s"
            break
        fi
        if [ $((now - last_status_epoch)) -ge 3600 ]; then
            echo "DIGEST ($(date -u +%H:%M:%SZ)): retries_so_far=$retry_count"
            [ -n "$driftline" ]  && echo "DIGEST last-drift: $driftline"
            [ -n "$timingline" ] && echo "DIGEST last-timing: $timingline"
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
