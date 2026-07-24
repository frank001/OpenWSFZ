#!/usr/bin/env bash
# Live-monitor for this session's live-confirmation run (tasks.md 8.6 contributing evidence),
# adapted from qa/endurance/2026-07-24-29041f7/monitor.sh for commit f57fa4d (8.4 hashTableRejectCount
# logging + 8.7 discard-vs-replay real-time-cost confirmation, no fix landed for 8.3 yet).
# Watches the current daemon log for: correction events, failures, capture dropouts,
# and emits a periodic status summary so a long silence doesn't look identical to
# "nothing has gone wrong yet" (Monitor tool coverage guidance).

set -u
LOG="${1:-D:/Projects/claude/OpenWSFZ/logs/openswfz-20260724T182334Z.log}"

echo "MONITOR ARMED: watching $LOG"

last_heartbeat_epoch=$(date +%s)
last_status_epoch=$(date +%s)
warned_stale=0
driftline=""
timingline=""
rejectline=""
# Seed from the log's own history so a monitor (re)start mid-session doesn't misreport an
# already-saturated table as a fresh "onset" — only a genuine 0-to-nonzero transition qualifies.
last_reject_count=$(grep -o 'hashTableRejectCount=[0-9]*' "$LOG" | tail -1 | cut -d= -f2)
last_reject_count="${last_reject_count:-0}"
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
        *"hashTableRejectCount="*)
            # tasks.md 8.4: fires every cycle once the 256-slot table saturates (every ~15-30s
            # on a busy band) — too frequent to echo per-occurrence without spamming the chat
            # (Monitor tool's own noise guidance). Track latest + only surface the *first* time
            # it moves off zero (saturation onset is the interesting event; every subsequent
            # increment on a busy band is not), otherwise fold into periodic status like drift/
            # timing lines.
            rejectline="$line"
            count="${line##*hashTableRejectCount=}"
            count="${count%% *}"
            if [ "$last_reject_count" = "0" ] || [ -z "$last_reject_count" ]; then
                if [ "$count" != "0" ]; then
                    echo "REJECT-COUNT-ONSET: $line"
                fi
            fi
            last_reject_count="$count"
            ;;
    esac

    # Periodic status every ~15 min (shorter than the 29041f7 run's 30 min — this is
    # explicitly a short first session per the Captain, so more frequent checkpoints
    # make more sense than a 30-min cadence tuned for a multi-hour run).
    if [ $((now - last_status_epoch)) -ge 900 ]; then
        echo "STATUS ($(date -u +%H:%M:%SZ)): corrections_so_far=$corrections"
        [ -n "$driftline" ]   && echo "STATUS last-drift: $driftline"
        [ -n "$timingline" ]  && echo "STATUS last-timing: $timingline"
        [ -n "$rejectline" ]  && echo "STATUS last-reject-count: $rejectline"
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
