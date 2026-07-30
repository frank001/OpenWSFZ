#!/usr/bin/env bash
# Crash-recovery supervisor for tonight's 40m/20m-then-80m dual-band overnight corpus-gathering +
# build-reliability soak (Captain going AFK 2026-07-30 ~02:00 local; armed on his explicit request
# after I flagged HK-013: both instances were running bare with no auto-recovery watcher).
# Watches the "20m-capture" instance (folder/port name retained from session start). Captain
# retuned it LIVE partway through the evening: 20m (SDRuno -> Voicemeeter Out B1, dial 14.074 MHz)
# until 2026-07-29T21:14:30Z, then 80m (dial 3.573 MHz) from 2026-07-29T21:18:00Z onward -- see
# D:\Projects\claude\OpenWSFZ-20m-capture\cycle-audio\CONTAMINATION-NOTE.md for the retune timeline
# and a separate, unrelated audio-leak contamination finding on part of the 80m span (already
# resolved/documented, does not affect capture-chain health -- not a reason for this supervisor to
# restart anything). Retune is persisted to config.json (decodeLog.dialFrequencyMHz,
# externalReporting.instanceId=OpenWSFZ-20m), so an auto-recovery restart correctly reloads 80m.
# Adapted from the validated 2026-07-28 template (qa/endurance/2026-07-28-supervisor-80m-overnight.sh)
# -- same ERR/FTL/hang-detection, kill+log+cooldown+restart shape, cap 5 retries, log-rotation guard.
#
# Build under test: integration/2026-07-29-live-run-40m-20m @ 5016363 (includes the merged
# feat/external-reporting-single-connection relay + the LoggingConfig STJ-omitted-key guard from
# 221240c). Self-contained win-x64 publish, running from D:\Projects\claude\OpenWSFZ-20m-capture\.
#
# Paired with the 40m instance above via external-reporting relay (this instance is the follower,
# "OpenWSFZ-20m", relaying to the 40m leader on 127.0.0.1:8080).
#
# TX is OFF (tx.autoAnswer=false) on both instances -- decode-only soak, not a QSO/TX test.
# WSJT-X is NOT touched by this script or by QA -- Captain configures/runs it himself (40m only).
#
# Usage: RESTART_WAIT_SECS=<n> bash qa/endurance/2026-07-29-supervisor-20m-capture-overnight.sh
# (defaults to 300s per prior precedent.)

set -u

CAPTURE_DIR="D:/Projects/claude/OpenWSFZ-20m-capture"
EXE="$CAPTURE_DIR/OpenWSFZ.Daemon.exe"
CONFIG="$CAPTURE_DIR/config.json"
PORT=8081
SUPERVISOR_LOG="$CAPTURE_DIR/restart-supervisor.log"
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
    # Match on the --config argument (not bare IMAGENAME) so this only ever finds/kills THIS
    # instance, never the paired 40m instance running from a different capture dir under the
    # same image name.
    powershell.exe -NoProfile -Command \
        "(Get-CimInstance Win32_Process -Filter \"Name='OpenWSFZ.Daemon.exe'\" | Where-Object { \$_.CommandLine -like '*20m-capture*' } | Select-Object -First 1 -ExpandProperty ProcessId)" \
        2>/dev/null | tr -d '\r'
}

find_latest_log() {
    ls -t "$CAPTURE_DIR"/logs/openswfz-*.log 2>/dev/null | head -1
}

snapshot_logs() {
    ls "$CAPTURE_DIR"/logs/openswfz-*.log 2>/dev/null | sort
}

find_new_log_since() {
    local before="$1"
    comm -13 <(printf '%s\n' "$before") <(snapshot_logs) | tail -1
}

kill_and_restart() {
    local reason="$1"
    log_event "SUPERVISOR(20m): failure detected ($reason). Killing daemon and restarting (attempt $((retry_count+1))/$MAX_RETRIES)."

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
            log_event "SUPERVISOR(20m): kill of PID $pid did NOT take (rc=$kill_rc, still running as $still_there) -- aborting this restart attempt."
            return 1
        fi
        log_event "SUPERVISOR(20m): killed PID $pid, confirmed dead."
    else
        log_event "SUPERVISOR(20m): no running OpenWSFZ.Daemon.exe (20m) PID found (already dead)."
    fi

    log_event "SUPERVISOR(20m): waiting ${RESTART_WAIT_SECS}s before restart."
    sleep "$RESTART_WAIT_SECS"

    powershell.exe -NoProfile -Command \
        "Start-Process -FilePath '$EXE' -ArgumentList '--config','$CONFIG','--port','$PORT' -WorkingDirectory '$CAPTURE_DIR'" >/dev/null 2>&1
    log_event "SUPERVISOR(20m): relaunch command issued ($EXE)."

    local waited=0
    local newlog=""
    while [ "$waited" -lt 60 ]; do
        newlog=$(find_new_log_since "$before_logs")
        if [ -n "$newlog" ] && grep -q "CycleFramer started" "$newlog" 2>/dev/null; then
            log_event "SUPERVISOR(20m): restart CONFIRMED healthy -- new log $newlog, decode resumed."
            printf '%s' "$newlog" > "$CAPTURE_DIR/.supervisor-current-log"
            return 0
        fi
        if [ -n "$newlog" ] && grep -q "Hosting failed to start\|address already in use" "$newlog" 2>/dev/null; then
            log_event "SUPERVISOR(20m): new instance failed to bind (port still held?) -- $newlog"
            return 1
        fi
        sleep 5
        waited=$((waited + 5))
    done

    log_event "SUPERVISOR(20m): restart did NOT confirm healthy decode resume within 60s (no 'CycleFramer started' seen in any new log since $EXE was relaunched)."
    return 1
}

CURRENT_LOG=$(find_latest_log)
log_event "SUPERVISOR ARMED (20m/80m, overnight corpus + build-reliability soak): watching $CURRENT_LOG. max_retries=$MAX_RETRIES restart_wait_secs=$RESTART_WAIT_SECS"

while true; do
    [ -z "$CURRENT_LOG" ] && CURRENT_LOG=$(find_latest_log)
    log_event "SUPERVISOR(20m): watch phase on $CURRENT_LOG"

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
                echo "HEARTBEAT-DROP(20m): $line"
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
        fi

        # Log-rotation guard (per HK-013 addendum, found live 2026-07-29): the app's own daily
        # rotationSchedule/rotationTime="00:00" rolls to a NEW log file at UTC midnight while this
        # loop is still mid-watch-phase on the OLD one. The old file goes silent -- not because the
        # app died, it kept heartbeating fine in the new file -- and without this check the >90s
        # heartbeat-stall test below fires on that silence and kills a perfectly healthy process.
        # Detect the rotation and follow the new file instead of waiting for a failure verdict on
        # an abandoned one.
        latest_log=$(find_latest_log)
        if [ -n "$latest_log" ] && [ "$latest_log" != "$CURRENT_LOG" ]; then
            log_event "SUPERVISOR(20m): log rotation detected -- switching watch from $CURRENT_LOG to $latest_log (no restart needed)."
            exec 3<&- 2>/dev/null
            CURRENT_LOG="$latest_log"
            exec 3< <(tail -f -n 0 "$CURRENT_LOG")
            last_heartbeat_epoch=$(date +%s)
            continue
        fi

        now=$(date +%s)
        if [ $((now - last_heartbeat_epoch)) -gt 90 ]; then
            failure_reason="heartbeat stall: no Heartbeat line of any kind in >90s"
            break
        fi
        if [ $((now - last_status_epoch)) -ge 3600 ]; then
            echo "DIGEST(20m) ($(date -u +%H:%M:%SZ)): retries_so_far=$retry_count"
            last_status_epoch=$now
        fi
    done
    exec 3<&- 2>/dev/null

    [ -z "$failure_reason" ] && failure_reason="watch loop ended for an undetermined reason"

    if [ "$retry_count" -ge "$MAX_RETRIES" ]; then
        log_event "SUPERVISOR(20m): failure ($failure_reason) but already at $MAX_RETRIES/$MAX_RETRIES retries -- giving up, no further restart attempts. Manual intervention needed."
        break
    fi

    retry_count=$((retry_count + 1))
    if kill_and_restart "$failure_reason"; then
        CURRENT_LOG=$(find_latest_log)
        continue
    else
        if [ "$retry_count" -ge "$MAX_RETRIES" ]; then
            log_event "SUPERVISOR(20m): restart attempt $retry_count/$MAX_RETRIES failed to confirm healthy -- max retries reached, giving up."
            break
        fi
        log_event "SUPERVISOR(20m): restart attempt $retry_count/$MAX_RETRIES did not confirm healthy within 60s -- will re-enter watch loop and retry again on next failure."
        CURRENT_LOG=$(find_latest_log)
        continue
    fi
done

log_event "SUPERVISOR(20m) EXITED (retry_count=$retry_count)."
