#!/bin/sh
# sched-helper.sh <mode> <stopfile> <logfile>   (QA 2026-10-15)  CPU scheduling of the OpenWSFZ daemon during a battery on sol.
#
# WHY: with the daemon's subtraction residual pass on (8 worker threads, bursts of 2-7 s), WSJT-X's Qt ALSA capture thread is occasionally delayed; Qt's ALSA plugin then runs
#   its own recovery (close + reopen, a ~0.45 s device re-enumeration inside libqtaudio_alsa.so) and the reopened input never ticks again: WSJT-X silently stops saving WAVs
#   (4 of 4 S6 attempts in B2BASE sweep 1; 4 of 4 daemon-on isolation runs; none in 3 daemon-off or reader-only runs). See qa/rr-study/linux/README.md and the 2026-10-15 isolation runs.
#
# MODES:
#   none  do nothing (default; the script is not even started by battery-b2.sh).
#   nice  renice +10 every daemon THREAD (workers inherit it). arecord (the daemon's capture child, a separate process) and WSJT-X stay at 0, so they pre-empt the workers when cores
#         are contended, and the daemon loses nothing when cores are free. Re-applied every 5 s (new daemon pid after a restart; threads that are still 0).
#   pin   taskset the daemon to cores 2-7 and its arecord to cores 0-1. NOT RECOMMENDED: in the 2026-10-15 isolation run it kept WSJT-X clean but raised the daemon's own
#         capture-clamp rate to 58 % of cycles (23 clamps >= 1 s, max 2.36 s), because arecord then shares cores 0-1 with WSJT-X, jt9 and the player.
#
# Runs until <stopfile> exists. Appends what it applied to <logfile>. Never touches WSJT-X, jt9 or the harness.
MODE=$1; STOP=$2; LOG=$3
log() { echo "$(date -u +%FT%TZ) sched-helper[$MODE]: $*" >> "$LOG"; }
[ "$MODE" = "nice" ] || [ "$MODE" = "pin" ] || { log "mode '$MODE' does nothing"; exit 0; }
last=""
while [ ! -e "$STOP" ]; do
  D=$(pgrep -x OpenWSFZ.Daemon | head -1)
  if [ -n "$D" ]; then
    if [ "$MODE" = "nice" ]; then
      n=0
      for t in $(ps -L -p "$D" -o tid=,ni= | awk '$2==0 {print $1}'); do renice -n 10 -p "$t" > /dev/null 2>&1 && n=$((n + 1)); done
      [ "$n" -gt 0 ] && log "daemon pid $D: reniced $n thread(s) to +10 (arecord pid $(pgrep -x arecord | head -1) left at $(ps -o ni= -p "$(pgrep -x arecord | head -1)" 2>/dev/null | tr -d ' '))"
    else
      A=$(pgrep -x arecord | head -1)
      key="$D/$A"
      if [ "$key" != "$last" ] && [ -n "$A" ]; then
        taskset -a -pc 2-7 "$D" > /dev/null 2>&1; taskset -pc 0,1 "$A" > /dev/null 2>&1
        log "daemon pid $D pinned to $(taskset -pc "$D" | sed 's/.*: //'); arecord pid $A pinned to $(taskset -pc "$A" | sed 's/.*: //')"
        last=$key
      fi
    fi
  fi
  sleep 5
done
log "stopped"
