#!/usr/bin/env bash
# Crash-recovery supervisor for the 2026-08-08 three-way decode comparison corpus.
#
# GOAL (HK-020: stated explicitly, not inherited): gather an OpenWSFZ ALL.TXT + WAV corpus on
# port 8080 ("Microphone (2- USB Audio CODEC )" -- the FT-991A's own audio path, 14.074 MHz/20m)
# to compare later against the Captain's two live WSJT-X instances (WSJT-X - FT991A and
# WSJT-X - FT991A-Copy, both already running on the same antenna/band). Decode-only -- there is
# no TX/QSO purpose to this run.
#
# Build under test: main @ b8845cd, published fresh tonight via
#   dotnet publish src/OpenWSFZ.Daemon -c Release -r win-x64 --self-contained -p:PublishAot=false
# (per dev-tasks/2026-07-18-self-contained-non-aot-working-binary.md -- AOT does not support
# WASAPI, framework-dependent `dotnet build` output does not carry its own CLR host files and
# must not be overlaid onto an existing self-contained tree -- see tonight's session notes for
# the FileNotFoundException that cost an hour before this was diagnosed).
#
# PTT SAFETY (Captain flagged this explicitly before arming): ptt.method is "AudioVox", not the
# 07-31 template's "SerialRtsDtr". AudioOnlyPttController (src/OpenWSFZ.Daemon/
# AudioOnlyPttController.cs) asserts no serial line and issues no CAT command under any code
# path -- KeyDownAsync only ever plays a pre-loaded buffer over the WASAPI *output* device, and
# that only happens if something calls it. tx.autoAnswer stays false as a second, now-redundant
# gate (this is decode-only; nothing should ever call KeyDownAsync on this instance). cat.enabled
# is false, unchanged from the template. Three receivers now share one antenna -- this instance
# needs zero TX capability, so it carries none, rather than relying on a single flag the way the
# 07-31 template did.
#
# Directory/port naming: keyed by PORT, not band (see 2026-07-31-supervisor-8080.sh for why --
# CONTAMINATION-NOTE.md, qa/endurance/2026-07-29-5016363/). Do not rename this directory if the
# band changes.
#
# No 8081 sibling exists this run (unlike 07-31's paired capture) -- the cross-instance
# decode-collapse check from that template is dropped entirely rather than carried as dead code.
#
# WSJT-X is NOT touched by this script or by QA -- Captain configures/runs it himself.
#
# Usage: RESTART_WAIT_SECS=<n> bash qa/endurance/2026-08-08-supervisor-8080-comparison-run.sh
# (defaults to 300s per HK-013 precedent.)

set -u

CAPTURE_DIR="D:/Projects/claude/OpenWSFZ-8080-capture"
EXE="$CAPTURE_DIR/OpenWSFZ.Daemon.exe"
CONFIG="$CAPTURE_DIR/config.json"
PORT=8080
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
    # Match on the --config argument so this only ever finds/kills THIS instance.
    powershell.exe -NoProfile -Command \
        "(Get-CimInstance Win32_Process -Filter \"Name='OpenWSFZ.Daemon.exe'\" | Where-Object { \$_.CommandLine -like '*8080-capture*' } | Select-Object -First 1 -ExpandProperty ProcessId)" \
        2>/dev/null | tr -d '\r'
}

find_latest_log() {
    ls -t "$CAPTURE_DIR"/logs/openswfz-*.log 2>/dev/null | head -1
}

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
    log_event "SUPERVISOR(8080-cmp): failure detected ($reason). Killing daemon and restarting (attempt $((retry_count+1))/$MAX_RETRIES)."

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
            log_event "SUPERVISOR(8080-cmp): kill of PID $pid did NOT take (rc=$kill_rc, still running as $still_there) -- aborting this restart attempt."
            return 1
        fi
        log_event "SUPERVISOR(8080-cmp): killed PID $pid, confirmed dead."
    else
        log_event "SUPERVISOR(8080-cmp): no running OpenWSFZ.Daemon.exe (8080) PID found (already dead)."
    fi

    log_event "SUPERVISOR(8080-cmp): waiting ${RESTART_WAIT_SECS}s before restart."
    sleep "$RESTART_WAIT_SECS"

    # IMPORTANT (found live during tonight's HK-013 validation test): the --config argument MUST
    # be the full path, not a bare "config.json" relative to CurrentDirectory. find_daemon_pid()
    # above matches on the '*8080-capture*' substring appearing in the process's CommandLine --
    # a relative config.json produces a command line with no such substring, silently breaking
    # PID lookup for the rest of this instance's life (kill_and_restart would then never find a
    # genuinely-hung old process to kill before relaunching, risking a port-8080-already-in-use
    # failure on every future recovery attempt).
    powershell.exe -NoProfile -Command \
        "\$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = 'cmd.exe /c \"cd /d $CAPTURE_DIR && OpenWSFZ.Daemon.exe --config $CONFIG --port $PORT >> daemon-stdout.log 2>&1\"'; CurrentDirectory = '$CAPTURE_DIR' }; \$r.ReturnValue" \
        >/dev/null 2>&1
    log_event "SUPERVISOR(8080-cmp): relaunch command issued ($EXE)."

    local waited=0
    local newlog=""
    while [ "$waited" -lt 60 ]; do
        newlog=$(find_new_log_since "$before_logs")
        if [ -n "$newlog" ] && grep -q "Heartbeat:" "$newlog" 2>/dev/null; then
            log_event "SUPERVISOR(8080-cmp): restart CONFIRMED healthy -- new log $newlog, heartbeat resumed."
            printf '%s' "$newlog" > "$CAPTURE_DIR/.supervisor-current-log"
            return 0
        fi
        if [ -n "$newlog" ] && grep -q "Hosting failed to start\|address already in use\|Unhandled exception" "$newlog" 2>/dev/null; then
            log_event "SUPERVISOR(8080-cmp): new instance failed to start -- $newlog"
            return 1
        fi
        sleep 5
        waited=$((waited + 5))
    done

    log_event "SUPERVISOR(8080-cmp): restart did NOT confirm healthy (no 'Heartbeat:' line seen in any new log within 60s since relaunch)."
    return 1
}

CURRENT_LOG=$(find_latest_log)
log_event "SUPERVISOR ARMED (8080, 3-way decode comparison corpus vs WSJT-X FT991A/FT991A-Copy): watching $CURRENT_LOG. max_retries=$MAX_RETRIES restart_wait_secs=$RESTART_WAIT_SECS"

while true; do
    [ -z "$CURRENT_LOG" ] && CURRENT_LOG=$(find_latest_log)
    log_event "SUPERVISOR(8080-cmp): watch phase on $CURRENT_LOG"

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
                echo "HEARTBEAT-DROP(8080-cmp): $line"
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

        # Log-rotation guard (HK-013 addendum) -- follow a genuine rotation instead of killing a
        # healthy process over apparent silence on an abandoned old log file.
        latest_log=$(find_latest_log)
        if [ -n "$latest_log" ] && [ "$latest_log" != "$CURRENT_LOG" ]; then
            log_event "SUPERVISOR(8080-cmp): log rotation detected -- switching watch from $CURRENT_LOG to $latest_log (no restart needed)."
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
            failure_reason="archiving stall: no new WAV in cycle-audio/ in >120s (newest is $((now - latest_wav_epoch))s old) -- process is otherwise healthy"
            break
        fi

        if [ $((now - last_status_epoch)) -ge 3600 ]; then
            echo "DIGEST(8080-cmp) ($(date -u +%H:%M:%SZ)): retries_so_far=$retry_count"
            last_status_epoch=$now
        fi
    done
    exec 3<&- 2>/dev/null

    [ -z "$failure_reason" ] && failure_reason="watch loop ended for an undetermined reason"

    if [ "$retry_count" -ge "$MAX_RETRIES" ]; then
        log_event "SUPERVISOR(8080-cmp): failure ($failure_reason) but already at $MAX_RETRIES/$MAX_RETRIES retries -- giving up, no further restart attempts. Manual intervention needed."
        break
    fi

    retry_count=$((retry_count + 1))
    if kill_and_restart "$failure_reason"; then
        CURRENT_LOG=$(find_latest_log)
        continue
    else
        if [ "$retry_count" -ge "$MAX_RETRIES" ]; then
            log_event "SUPERVISOR(8080-cmp): restart attempt $retry_count/$MAX_RETRIES failed to confirm healthy -- max retries reached, giving up."
            break
        fi
        log_event "SUPERVISOR(8080-cmp): restart attempt $retry_count/$MAX_RETRIES did not confirm healthy within 60s -- will re-enter watch loop and retry again on next failure."
        CURRENT_LOG=$(find_latest_log)
        continue
    fi
done

log_event "SUPERVISOR(8080-cmp) EXITED (retry_count=$retry_count)."
