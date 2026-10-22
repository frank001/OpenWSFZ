#!/bin/sh
# s6-phase.sh <w|o|restore>   (QA 2026-10-15)  the SEQUENTIAL-S6 phase hook for run_study.py (--s6-phase-cmd "sh $HOME/s6-phase.sh").
#
# Sequential S6 plays the same schedule twice with ONE appraiser listening each time (why: qa/rr-study/s6/s6_merge.py). run_study.py calls this between the steps:
#   w        pass W comes next: OpenWSFZ OFF, WSJT-X ON.   Stops the daemon (the one the supervisor started) and proves WSJT-X is writing save WAVs.
#   o        pass O comes next: WSJT-X OFF, OpenWSFZ ON.   Creates the monitor's `wsjtx.expected_off` flag, stops WSJT-X (and its jt9 and Xvfb), starts a FRESH daemon from the
#            same exe / config / port as the battery (its stdout appends to the supervisor's daemon.stdout.log, which S6 reads for the per-play abandonment) and waits until it
#            reports captureActive and decodingEnabled.
#   restore  a scenario retry follows: remove the flag, bring the daemon back if it is down. WSJT-X itself is restarted by the retry (--wsjtx-restart-cmd), not here.
# Exit 0 = the state was reached; anything else makes run_study.py skip the pass (and, for S6, retry the scenario within the per-scenario cap).
# Environment, exported by battery-b2.sh: S6_SUP (supervisor folder: daemon.stdout.log, wsjtx.expected_off), S6_DAEMON, S6_CONFIG, S6_PORT, S6_LOG (the sweep log).
# Never put process-name patterns in the command line that launches this script's children: pgrep below uses EXACT names (-x).
PHASE=$1
SUP=${S6_SUP:?S6_SUP not set}; DAEMON=${S6_DAEMON:?S6_DAEMON not set}; CONFIG=${S6_CONFIG:?S6_CONFIG not set}; PORT=${S6_PORT:-8080}
LOG=${S6_LOG:-$SUP/s6-phase.log}
SAVE="${S6_SAVE:-$HOME/.local/share/WSJT-X - rr/save}"
PY=${S6_PY:-python3}
log() { echo "$(date -u +%FT%TZ) s6-phase[$PHASE]: $*" >> "$LOG"; echo "  s6-phase[$PHASE]: $*"; }
fail() { log "FAILED: $*"; exit 1; }

# LIVE daemon pids. A stopped daemon the supervisor has not reaped yet is a zombie (<defunct>): pgrep -x still lists it, so it must be filtered out by state
# (found on the first sol validation run, 2026-10-15: "the daemon would not stop" with the daemon long dead).
daemon_pids() { ps -C OpenWSFZ.Daemon -o pid=,stat= 2>/dev/null | awk '$2 !~ /^Z/ {print $1}'; }

stop_daemon() {
  [ -z "$(daemon_pids)" ] && { log "daemon already stopped"; return 0; }
  for p in $(daemon_pids); do kill "$p" 2>/dev/null; done
  i=0; while [ -n "$(daemon_pids)" ] && [ $i -lt 40 ]; do sleep 1; i=$((i + 1)); done
  for p in $(daemon_pids); do kill -9 "$p" 2>/dev/null; done
  sleep 2
  [ -z "$(daemon_pids)" ] || return 1
  log "daemon stopped"
}

daemon_ready() {
  "$PY" - "$PORT" <<'PYEOF'
import json, sys, urllib.request
try:
    with urllib.request.urlopen("http://127.0.0.1:%s/api/v1/status" % sys.argv[1], timeout=4) as r:
        s = json.loads(r.read().decode("utf-8"))
    sys.exit(0 if s.get("captureActive") and s.get("decodingEnabled") else 1)
except Exception:
    sys.exit(1)
PYEOF
}

start_daemon() {
  if [ -n "$(daemon_pids)" ]; then log "daemon already running (pid $(daemon_pids | head -1))"; return 0; fi
  setsid nohup "$DAEMON" --config "$CONFIG" --port "$PORT" >> "$SUP/daemon.stdout.log" 2>&1 < /dev/null &
  i=0
  while [ $i -lt 180 ]; do
    [ -n "$(daemon_pids)" ] || { sleep 3; i=$((i + 3)); continue; }
    daemon_ready && { log "daemon up (pid $(daemon_pids | head -1)) and capturing after about $i s"; return 0; }
    sleep 3; i=$((i + 3))
  done
  return 1
}

stop_wsjtx() {
  pkill -CONT -x wsjtx 2>/dev/null; pkill -CONT -x jt9 2>/dev/null; sleep 1
  sh "$HOME/stop-wsjtx.sh" > /dev/null 2>&1
  i=0; while pgrep -x wsjtx > /dev/null 2>&1 && [ $i -lt 15 ]; do sleep 1; i=$((i + 1)); done
  pkill -9 -x wsjtx 2>/dev/null; pkill -9 -x jt9 2>/dev/null; pkill -9 -x Xvfb 2>/dev/null
  sleep 2
  pgrep -x wsjtx > /dev/null 2>&1 && return 1
  log "WSJT-X stopped"
}

wsjtx_listening() {
  pgrep -x wsjtx > /dev/null 2>&1 || return 1
  [ -n "$(find "$SAVE" -name '*.wav' -newermt "45 seconds ago" 2>/dev/null | head -1)" ]
}

# Condition 1a (Architect, amendment 4): the run record states, once per S6, the library the FRESH pass-O daemon actually loaded (read from the live process, never from the path we
# pinned) and that file's SHA-256. S6_RUN_DIR is exported by run_study.py for the hook. Without this record the merged S6-V5 reads NOT CHECKED, not PASS.
record_daemon_lib() {
  [ -n "${S6_RUN_DIR:-}" ] || { log "S6_RUN_DIR not set: no library record written"; return 0; }
  d=$(daemon_pids | head -1)
  [ -n "$d" ] || return 1
  lib=$(awk '/libft8/ {print $6}' "/proc/$d/maps" 2>/dev/null | sort -u | head -1)
  mkdir -p "$S6_RUN_DIR/s6/pass-o"
  if [ -n "$lib" ] && [ -f "$lib" ]; then
    real=$(readlink -f "$lib"); sha=$(sha256sum "$real" | cut -d' ' -f1)
    printf '{"pid": %s, "libft8_path": "%s", "libft8_sha256": "%s", "recorded_utc": "%s"}
' "$d" "$real" "$sha" "$(date -u +%FT%TZ)" > "$S6_RUN_DIR/s6/pass-o/daemon_lib.json"
    log "pass-O daemon pid $d loaded $real (sha256 $sha)"
  else
    printf '{"pid": %s, "libft8_path": null, "libft8_sha256": null, "recorded_utc": "%s"}
' "$d" "$(date -u +%FT%TZ)" > "$S6_RUN_DIR/s6/pass-o/daemon_lib.json"
    log "pass-O daemon pid $d: no libft8 mapping found in /proc/$d/maps"
  fi
}

case "$PHASE" in
  w)
    rm -f "$SUP/wsjtx.expected_off"
    stop_daemon || fail "the daemon would not stop"
    wsjtx_listening || fail "WSJT-X is not writing save WAVs"
    log "pass W may start: WSJT-X listening, OpenWSFZ off"
    ;;
  o)
    touch "$SUP/wsjtx.expected_off"
    stop_wsjtx || fail "WSJT-X would not stop"
    start_daemon || fail "the daemon did not report captureActive within 180 s"
    record_daemon_lib || fail "could not read the daemon's loaded library"
    log "pass O may start: OpenWSFZ capturing, WSJT-X off"
    ;;
  restore)
    rm -f "$SUP/wsjtx.expected_off"
    start_daemon || fail "the daemon did not come back"
    log "both appraisers may be restarted: daemon up, flag removed"
    ;;
  *)
    echo "usage: s6-phase.sh w|o|restore" >&2; exit 2 ;;
esac
exit 0
