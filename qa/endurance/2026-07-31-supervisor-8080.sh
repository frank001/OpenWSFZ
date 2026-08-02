#!/usr/bin/env bash
# Crash-recovery supervisor for the 2026-07-31 multi-day 20m live-run corpus-gathering session
# (Architect's pre-flight brief: qa/cycleframer-alignment-replay/2026-07-31-1907-...-preflight-
# brief-multiday-20m-live-run.md). Watches the 8080 instance: physical radio via
# "Microphone (2- USB Audio CODEC )", paired with a live WSJT-X on the same audio feed. This is
# the decisive corpus -- stays on 14.074 MHz for the entire run, mode=all, no retunes, no
# Settings-page saves, for the whole duration (brief item 3).
#
# Directory/port naming: keyed by PORT, not band. Per CONTAMINATION-NOTE.md
# (qa/endurance/2026-07-29-5016363/), the 07-29 run's band-named directory
# ("OpenWSFZ-20m-capture") ended up holding four non-contiguous band windows across its life --
# the folder name went stale the moment the instance was retuned. The port is what's stable for
# the life of the directory; the band is not. Do not rename this directory if the band changes.
#
# Adapted from the validated 2026-07-29 template (qa/endurance/2026-07-29-supervisor-40m-
# overnight.sh) -- same ERR/FTL/hang-detection, kill+log+cooldown+restart shape, cap 5 retries,
# log-rotation guard (kept as defense-in-depth even though config.json's logging.rotationSchedule
# is "session", matching the 07-29 precedent, which makes LogRotationService's automatic
# UTC-midnight rotation a no-op at the source -- see LogRotationService.cs:25-26).
#
# Restart-health check fixed vs. the 07-29 template: that script grepped the post-restart log for
# the literal string "CycleFramer started", which no longer exists anywhere in the current
# codebase (confirmed via grep across src/ before writing this script -- the check would have
# silently never matched, so every restart would report as unconfirmed). Uses the current
# "Heartbeat:" line instead, which this same script already treats as the primary liveness signal
# throughout the watch loop and was confirmed live in daemon_log.txt today.
#
# TX is OFF (tx.autoAnswer=false) -- decode-only corpus gathering, not a QSO/TX test.
# WSJT-X is NOT touched by this script or by QA -- Captain configures/runs it himself.
#
# Usage: RESTART_WAIT_SECS=<n> bash qa/endurance/2026-07-31-supervisor-8080.sh
# (defaults to 300s per prior precedent.)

set -u

CAPTURE_DIR="D:/Projects/claude/OpenWSFZ-8080-capture"
EXE="$CAPTURE_DIR/OpenWSFZ.Daemon.exe"
CONFIG="$CAPTURE_DIR/config.json"
PORT=8080
SUPERVISOR_LOG="$CAPTURE_DIR/restart-supervisor.log"
MAX_RETRIES=5
RESTART_WAIT_SECS="${RESTART_WAIT_SECS:-300}"
retry_count=0

# ── DRAFT, 2026-08-01: cross-instance decode-collapse detection -- NOT YET REVIEWED, DEFAULT OFF ──
# Written after tonight's live incident: 8080's decode rate collapsed from ~20/cycle to ~2-3/cycle
# for ~50 minutes (10:07Z-10:57Z) while every other health signal (heartbeats, no [ERR]/[FTL],
# archiving) stayed green -- the supervisor did not and could not notice. Manually diagnosed and
# fixed by a clean daemon restart (identical config, same radio, same antenna) -- confirmed
# software/runtime-state, not hardware, since nothing else changed. Root cause not yet found; see
# the companion dev-task. This block teaches the supervisor to catch a recurrence, but is
# deliberately gated OFF (ENABLE_CROSS_INSTANCE_DECODE_CHECK=0) until the Captain has reviewed the
# heuristic and its false-positive risk -- a genuine correlated band-condition dip (which happened
# earlier tonight and recovered on its own) must NOT trigger a restart; only a one-sided collapse
# should. Flip the flag to 1 (or export it before launch) to arm this once reviewed.
ENABLE_CROSS_INSTANCE_DECODE_CHECK="${ENABLE_CROSS_INSTANCE_DECODE_CHECK:-0}"
SIBLING_DIR="D:/Projects/claude/OpenWSFZ-8081-capture"
DECODE_CHECK_INTERVAL_SECS=180   # how often to evaluate -- not every 10s poll, to bound log-scan cost
DECODE_CHECK_WINDOW=20           # cycles to average over (~5 min at 15s/cycle)
DECODE_CHECK_CONSECUTIVE=3       # consecutive bad evaluations required before declaring a failure
                                  # (~9-10.5 min at the interval above) -- absorbs single blips
DECODE_CHECK_ABS_FLOOR=8         # this instance's own mean must be below this to even consider it
DECODE_CHECK_SIBLING_MIN=10      # sibling's own mean must be at least this -- if the sibling is
                                  # ALSO quiet, that's a shared/correlated cause (band conditions),
                                  # not a one-sided defect, and must NOT trigger a restart
DECODE_CHECK_RATIO=0.30          # own_mean / sibling_mean must be below this
_decode_check_bad_streak=0
_decode_check_last_epoch=0

find_sibling_latest_log() {
    ls -t "$SIBLING_DIR"/logs/openswfz-*.log 2>/dev/null | head -1
}

# Mean of the last DECODE_CHECK_WINDOW "N decode(s) found" values in a log file. Bounds the scan
# to the last 4000 lines (a few hours at this app's log verbosity) rather than grepping the whole
# file, since these logs run for many hours and grow large -- an unbounded grep here would get
# slower every time it's called over the life of a multi-day run.
recent_decode_mean() {
    local logfile="$1"
    [ -z "$logfile" ] || [ ! -f "$logfile" ] && { echo ""; return; }
    tail -n 4000 "$logfile" | grep -oP "\d+(?= decode\(s\) found)" | tail -n "$DECODE_CHECK_WINDOW" \
        | awk '{s+=$1; n++} END { if (n>0) printf "%.2f", s/n; }'
}

# Returns 0 (bash "true") and sets $1 (nameref-style via echo, since this targets an old-ish bash)
# if this evaluation looks like a one-sided collapse. Logs its reasoning either way so a false
# negative/positive is diagnosable after the fact, not silent.
check_decode_collapse() {
    local own_log sibling_log own_mean sibling_mean
    own_log=$(find_latest_log)
    sibling_log=$(find_sibling_latest_log)
    own_mean=$(recent_decode_mean "$own_log")
    sibling_mean=$(recent_decode_mean "$sibling_log")

    if [ -z "$own_mean" ] || [ -z "$sibling_mean" ]; then
        return 1   # not enough data yet (startup, or sibling log not found) -- not a failure
    fi

    # Integer-arithmetic threshold checks (bash has no float compare) via awk, one boolean out.
    local verdict
    verdict=$(awk -v own="$own_mean" -v sib="$sibling_mean" \
        -v floor="$DECODE_CHECK_ABS_FLOOR" -v sibmin="$DECODE_CHECK_SIBLING_MIN" \
        -v ratio="$DECODE_CHECK_RATIO" \
        'BEGIN {
            if (own < floor && sib >= sibmin && (sib > 0) && (own/sib) < ratio) print "bad";
            else print "ok";
        }')

    if [ "$verdict" = "bad" ]; then
        _decode_check_bad_streak=$((_decode_check_bad_streak + 1))
        log_event "SUPERVISOR(8080): decode-collapse check: own_mean=$own_mean sibling_mean=$sibling_mean -- ONE-SIDED, streak=$_decode_check_bad_streak/$DECODE_CHECK_CONSECUTIVE"
        if [ "$_decode_check_bad_streak" -ge "$DECODE_CHECK_CONSECUTIVE" ]; then
            return 0
        fi
    else
        if [ "$_decode_check_bad_streak" -gt 0 ]; then
            log_event "SUPERVISOR(8080): decode-collapse check: own_mean=$own_mean sibling_mean=$sibling_mean -- recovered, resetting streak (was $_decode_check_bad_streak)"
        fi
        _decode_check_bad_streak=0
    fi
    return 1
}
# ── end draft block ──────────────────────────────────────────────────────────────────────────────

log_event() {
    local line
    line="$(date -u +%Y-%m-%dT%H:%M:%SZ) $1"
    echo "$line" >> "$SUPERVISOR_LOG"
    echo "$line"
}

find_daemon_pid() {
    # Match on the --config argument (not bare IMAGENAME) so this only ever finds/kills THIS
    # instance, never the paired 8081 instance running from a different capture dir under the
    # same image name.
    powershell.exe -NoProfile -Command \
        "(Get-CimInstance Win32_Process -Filter \"Name='OpenWSFZ.Daemon.exe'\" | Where-Object { \$_.CommandLine -like '*8080-capture*' } | Select-Object -First 1 -ExpandProperty ProcessId)" \
        2>/dev/null | tr -d '\r'
}

find_latest_log() {
    ls -t "$CAPTURE_DIR"/logs/openswfz-*.log 2>/dev/null | head -1
}

# Archiving-liveness check (2026-07-31, no-alerting-possible correction): the checks above only
# catch a crashed/hung/erroring PROCESS. They do not catch a process that stays perfectly healthy
# by every other signal (heartbeats flowing, no [ERR]/[FTL]) while CycleArchiveService's writer is
# stuck and no new WAV is landing in cycle-audio/ -- exactly the 07-29 failure mode (WAV count
# flat, everything else green). With mode="all" in config.json, one WAV is guaranteed every 15s
# cycle with no exceptions, so ">120s since the newest WAV" (8 missed cycles) is a clean signal
# with wide margin against false positives, not a guess.
find_latest_wav_epoch() {
    local newest
    newest=$(ls -t "$CAPTURE_DIR"/cycle-audio/*.wav 2>/dev/null | head -1)
    [ -z "$newest" ] && return
    stat -c %Y "$newest" 2>/dev/null
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
    log_event "SUPERVISOR(8080): failure detected ($reason). Killing daemon and restarting (attempt $((retry_count+1))/$MAX_RETRIES)."

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
            log_event "SUPERVISOR(8080): kill of PID $pid did NOT take (rc=$kill_rc, still running as $still_there) -- aborting this restart attempt."
            return 1
        fi
        log_event "SUPERVISOR(8080): killed PID $pid, confirmed dead."
    else
        log_event "SUPERVISOR(8080): no running OpenWSFZ.Daemon.exe (8080) PID found (already dead)."
    fi

    log_event "SUPERVISOR(8080): waiting ${RESTART_WAIT_SECS}s before restart."
    sleep "$RESTART_WAIT_SECS"

    powershell.exe -NoProfile -Command \
        "Start-Process -FilePath '$EXE' -ArgumentList '--config','$CONFIG','--port','$PORT' -WorkingDirectory '$CAPTURE_DIR'" >/dev/null 2>&1
    log_event "SUPERVISOR(8080): relaunch command issued ($EXE)."

    local waited=0
    local newlog=""
    while [ "$waited" -lt 60 ]; do
        newlog=$(find_new_log_since "$before_logs")
        if [ -n "$newlog" ] && grep -q "Heartbeat:" "$newlog" 2>/dev/null; then
            log_event "SUPERVISOR(8080): restart CONFIRMED healthy -- new log $newlog, heartbeat resumed."
            printf '%s' "$newlog" > "$CAPTURE_DIR/.supervisor-current-log"
            return 0
        fi
        if [ -n "$newlog" ] && grep -q "Hosting failed to start\|address already in use" "$newlog" 2>/dev/null; then
            log_event "SUPERVISOR(8080): new instance failed to bind (port still held?) -- $newlog"
            return 1
        fi
        sleep 5
        waited=$((waited + 5))
    done

    log_event "SUPERVISOR(8080): restart did NOT confirm healthy (no 'Heartbeat:' line seen in any new log within 60s since $EXE was relaunched)."
    return 1
}

CURRENT_LOG=$(find_latest_log)
log_event "SUPERVISOR ARMED (8080, 20m decisive corpus): watching $CURRENT_LOG. max_retries=$MAX_RETRIES restart_wait_secs=$RESTART_WAIT_SECS"

while true; do
    [ -z "$CURRENT_LOG" ] && CURRENT_LOG=$(find_latest_log)
    log_event "SUPERVISOR(8080): watch phase on $CURRENT_LOG"

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
                echo "HEARTBEAT-DROP(8080): $line"
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

        # Log-rotation guard (per HK-013 addendum), kept as defense-in-depth even though
        # config.json's rotationSchedule="session" should make LogRotationService a no-op --
        # if that ever changes, this loop still follows a genuine rotation instead of killing a
        # healthy process over apparent silence on an abandoned old log file.
        latest_log=$(find_latest_log)
        if [ -n "$latest_log" ] && [ "$latest_log" != "$CURRENT_LOG" ]; then
            log_event "SUPERVISOR(8080): log rotation detected -- switching watch from $CURRENT_LOG to $latest_log (no restart needed)."
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

        latest_wav_epoch=$(find_latest_wav_epoch)
        if [ -n "$latest_wav_epoch" ] && [ $((now - latest_wav_epoch)) -gt 120 ]; then
            failure_reason="archiving stall: no new WAV in cycle-audio/ in >120s (newest is $((now - latest_wav_epoch))s old) -- process is otherwise healthy, this is the 07-29 failure mode"
            break
        fi

        # DRAFT, gated off by default -- see block above. Only evaluated (and only costs a log
        # scan) once per DECODE_CHECK_INTERVAL_SECS, not every 10s poll iteration.
        if [ "$ENABLE_CROSS_INSTANCE_DECODE_CHECK" = "1" ] && [ $((now - _decode_check_last_epoch)) -ge "$DECODE_CHECK_INTERVAL_SECS" ]; then
            _decode_check_last_epoch=$now
            if check_decode_collapse; then
                failure_reason="decode collapse: own decode rate one-sidedly low vs. sibling 8081 for $DECODE_CHECK_CONSECUTIVE consecutive checks (~$((DECODE_CHECK_CONSECUTIVE * DECODE_CHECK_INTERVAL_SECS / 60)) min) -- the 2026-08-01 10:07Z-10:57Z incident pattern"
                break
            fi
        fi

        if [ $((now - last_status_epoch)) -ge 3600 ]; then
            echo "DIGEST(8080) ($(date -u +%H:%M:%SZ)): retries_so_far=$retry_count"
            last_status_epoch=$now
        fi
    done
    exec 3<&- 2>/dev/null

    [ -z "$failure_reason" ] && failure_reason="watch loop ended for an undetermined reason"

    if [ "$retry_count" -ge "$MAX_RETRIES" ]; then
        log_event "SUPERVISOR(8080): failure ($failure_reason) but already at $MAX_RETRIES/$MAX_RETRIES retries -- giving up, no further restart attempts. Manual intervention needed."
        break
    fi

    retry_count=$((retry_count + 1))
    if kill_and_restart "$failure_reason"; then
        CURRENT_LOG=$(find_latest_log)
        continue
    else
        if [ "$retry_count" -ge "$MAX_RETRIES" ]; then
            log_event "SUPERVISOR(8080): restart attempt $retry_count/$MAX_RETRIES failed to confirm healthy -- max retries reached, giving up."
            break
        fi
        log_event "SUPERVISOR(8080): restart attempt $retry_count/$MAX_RETRIES did not confirm healthy within 60s -- will re-enter watch loop and retry again on next failure."
        CURRENT_LOG=$(find_latest_log)
        continue
    fi
done

log_event "SUPERVISOR(8080) EXITED (retry_count=$retry_count)."
