#!/usr/bin/env bash
# Live-monitor for tasks.md 8.6 re-confirmation run.
# Watches the current daemon log for: correction events, failures, capture dropouts,
# and emits a periodic status summary so a multi-hour silence doesn't look identical
# to "nothing has gone wrong yet" (Monitor tool coverage guidance).

set -u
LOG="${1:-D:/Projects/claude/OpenWSFZ/logs/openswfz-20260724T160705Z.log}"

echo "MONITOR ARMED: watching $LOG"

last_heartbeat_epoch=$(date +%s)
last_status_epoch=$(date +%s)
warned_stale=0
driftline=""
timingline=""
corrections=0

# Start reading new lines only (skip existing content), keep following as it grows.
while read -t 60 -r line <&3; do
    now=$(date +%s)

    case "$line" in
        *"Cycle boundary resync"*)
            corrections=$((corrections + 1))
            echo "CORRECTION #$corrections: $line"
            ;;
        *"[ERR]"*|*"[FTL]"*)
            echo "FAILURE: $line"
            ;;
        *"Heartbeat:"*"=false"*)
            echo "HEARTBEAT-DROP: $line"
            ;;
        *"Heartbeat:"*)
            last_heartbeat_epoch=$now
            warned_stale=0
            ;;
        *"Cycle boundary drift check"*)
            driftline="$line"
            ;;
        *"Cycle boundary pipeline timing"*)
            timingline="$line"
            ;;
    esac

    # Periodic status every ~30 min, independent of which lines arrived.
    if [ $((now - last_status_epoch)) -ge 1800 ]; then
        echo "STATUS ($(date -u +%H:%M:%SZ)): corrections_so_far=$corrections"
        [ -n "$driftline" ]   && echo "STATUS last-drift: $driftline"
        [ -n "$timingline" ]  && echo "STATUS last-timing: $timingline"
        last_status_epoch=$now
    fi

    # Heartbeat normally arrives every ~5s. If we go >90s without ANY heartbeat line
    # (true or false), the daemon may have stalled or the log stopped growing.
    if [ $((now - last_heartbeat_epoch)) -gt 90 ] && [ "$warned_stale" -eq 0 ]; then
        echo "WARNING: no Heartbeat line of any kind in >90s as of $(date -u +%H:%M:%SZ) — daemon may have stalled."
        warned_stale=1
    fi
done 3< <(tail -f -n 0 "$LOG")

echo "MONITOR EXITED: tail pipe on $LOG closed unexpectedly (log rotated/deleted, or process ended)."
