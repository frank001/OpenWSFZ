#!/bin/sh
# One supervised R&R battery on sol with the B2-MERGED build and the WSJT-X monitoring M1-M3 (QA, 2026-10-14; the Captain: "I want this B2 version to run on sol,
# including the M1-M3 monitoring", and "yes, build the capped retry").
#   usage: [MAX_STALL_RETRIES=1] battery-b2.sh <name> <scenarios> [extra run_study.py arguments...]
#   build under test: ~/OpenWSFZ-b2src (338ef61c = B2 merged with main 76aa48cd, shim 20260062), daemon published from it; its committed libft8.so is the pin
#   tooling:          ~/rr-work-b2 (qa/refset): the analyser gates %GR&R on %StudyVar; M2 stops and flags; M3 coverage row
#   WSJT-X 2.7.0 (rig `rr`) is (re)started here with `ulimit -c unlimited` (core dumps land in the working directory); M1 runs beside the battery.
# CAPPED RETRY (opt-in, default 0 = stop and flag): when a battery ends because the liveness gate stopped it (STALLED.json in the run folder), and fewer than
#   MAX_STALL_RETRIES retries were used, the WHOLE sweep is run again (never one scenario): the failed sweep's folders are KEPT and renamed *-INVALID-stall-attemptK
#   with an INVALID.md, WSJT-X is restarted, and the new sweep carries REPLACEMENT.json (attempt number, the folder it replaces, why). A second stall, or ANY other failure,
#   HALTS for good (no retry loop). The retries are in the log, so a replaced sweep is never silent.
# HALTS if another job is on, WSJT-X does not start, or the battery ends in anything but DONE. Detached by the caller; no cron (HK-023).
NAME=$1; SCEN=$2; shift 2
MAXR=${MAX_STALL_RETRIES:-0}
SUP0=$HOME/rr-run/$NAME
LOG=$HOME/rr-run/$NAME.log
WORK=$HOME/rr-work-b2/qa/rr-study
DAEMON=$HOME/OpenWSFZ-b2src/src/OpenWSFZ.Daemon/bin/Release/net10.0/linux-x64/publish/OpenWSFZ.Daemon
SAVE="$HOME/.local/share/WSJT-X - rr/save"
ARCH=$HOME/rr-run/cycle-audio
PY=$HOME/rr-venv/bin/python
log() { echo "$(date -u +%FT%TZ) $*" >> "$LOG"; }
halt() { log "HALT: $*"; exit 1; }

stop_wsjtx() {   # a frozen (SIGSTOP) wsjtx cannot act on SIGTERM: continue it first; then the normal stop; then force what is left
  pkill -CONT -x wsjtx 2>/dev/null; pkill -CONT -x jt9 2>/dev/null; sleep 1
  sh "$HOME/stop-wsjtx.sh" > /dev/null 2>&1
  i=0; while pgrep -x wsjtx > /dev/null 2>&1 && [ $i -lt 15 ]; do sleep 1; i=$((i + 1)); done
  pkill -9 -x wsjtx 2>/dev/null; pkill -9 -x jt9 2>/dev/null; pkill -9 -x Xvfb 2>/dev/null
  sleep 2
}

cd "$HOME"
# busy check by EXACT process name / anchored command line, so the launcher's own command line (which may mention the daemon's path) can never match
if pgrep -x OpenWSFZ.Daemon > /dev/null 2>&1 || pgrep -x aplay > /dev/null 2>&1 || pgrep -f "^[^ ]*python[^ ]* [^ ]*(run_study|run_refset|run_leg_e)" > /dev/null 2>&1 || pgrep -f "^dotnet [^ ]*RefSet.dll" > /dev/null 2>&1; then halt "another job is running on sol"; fi
log "battery $NAME start; scenarios $SCEN; extra args: $*; max stall retries: $MAXR"
log "build under test: $(git -C $HOME/OpenWSFZ-b2src rev-parse HEAD); libft8.so $(sha256sum "$(dirname "$DAEMON")/libft8.so" | cut -d' ' -f1); tooling $(git -C $HOME/rr-work-b2 rev-parse HEAD)"

# S6 pins the OpenWSFZ native library the daemon loads: the one in the daemon's publish folder (added here so no caller has to pass the path)
S6LIB=""; case ",$SCEN," in *,S6,*) S6LIB="--s6-ows-lib $(dirname "$DAEMON")/libft8.so";; esac
attempt=1
REPLACES=""
while : ; do
  SUP=$SUP0; [ $attempt -gt 1 ] && SUP=$SUP0-attempt$attempt
  rm -rf "$SUP"; mkdir -p "$SUP"
  T0=$(date +%s)
  log "attempt $attempt: starting WSJT-X"
  stop_wsjtx
  setsid nohup sh "$HOME/start-wsjtx27.sh" rr > /dev/null 2>&1 < /dev/null &
  sleep 60
  pgrep -x wsjtx > /dev/null 2>&1 || halt "WSJT-X (the real wsjtx binary) did not start"
  log "WSJT-X up: pid $(pgrep -x wsjtx | head -1); core limit in its shell: $(grep -m1 'Max core' /proc/$(pgrep -x wsjtx | head -1)/limits)"
  rm -rf "$ARCH"/* 2>/dev/null
  setsid nohup "$PY" "$WORK/linux/wsjtx_monitor.py" --save-dir "$SAVE" --out-dir "$SUP" --owsfz-archive "$ARCH" >> "$SUP/monitor.out" 2>&1 < /dev/null &
  sleep 3
  log "monitor started (pid $(pgrep -f wsjtx_monitor.py | head -1)); supervisor folder $SUP"
  export PYTHONPATH=$WORK/linux/shim RR_ALSA_PLAYBACK=plughw:0,0 ALSA_PLUGIN_DIR=$HOME/local/lib/alsa-lib
  ( cd "$WORK" && "$PY" run_study_linux.py --poll --supervisor-dir "$SUP" --daemon-exe "$DAEMON" --config "$HOME/rr-run/config.json" --port 8080 \
      --wsjtx-ini "$HOME/.local/share/WSJT-X - rr/WSJT-X - rr.ini" -- --scenarios "$SCEN" --skip-warmup --device RR-ALSA \
      --liveness-save-dir "$SAVE" --coverage-owsfz-dir "$ARCH" $S6LIB "$@" > "$SUP/supervisor.log" 2>&1 )
  rc=$?
  PH=$("$PY" -c "import json;print(json.load(open('$SUP/status.json'))['phase'])" 2>/dev/null)
  log "attempt $attempt ended rc=$rc phase=$PH"
  touch "$SUP/monitor.stop"; sleep 20
  stop_wsjtx
  log "stall events: $(wc -l < "$SUP/stall_events.jsonl" 2>/dev/null || echo 0); monitor samples: $(wc -l < "$SUP/monitor.jsonl" 2>/dev/null || echo 0)"
  # the run folder of this attempt: the newest folder with a status newer than T0
  RUN=""
  for d in $(ls -dt "$WORK"/results/20*/ 2>/dev/null | head -4); do
    d=${d%/}; case "$d" in *-captured-audio|*-INVALID-*) continue;; esac
    [ "$(stat -c %Y "$d" 2>/dev/null || echo 0)" -ge "$T0" ] && { RUN=$d; break; }
  done
  log "run folder: ${RUN:-none found}"
  if [ "$PH" = "DONE" ] && [ -n "$RUN" ]; then
    if [ -n "$REPLACES" ]; then
      printf '{"attempt": %s, "replaces": "%s", "reason": "the previous attempt was stopped by the WSJT-X liveness gate (STALLED.json); capped retry %s of %s, whole sweep rerun", "retries_cap": %s}\n' "$attempt" "$REPLACES" "$((attempt - 1))" "$MAXR" "$MAXR" > "$RUN/REPLACEMENT.json"
      log "REPLACEMENT.json written in $RUN (replaces $REPLACES)"
    fi
    break
  fi
  # not DONE: a stall (the gate stopped it) may be retried within the cap; anything else halts
  if [ -n "$RUN" ] && [ -f "$RUN/STALLED.json" ] && [ $((attempt - 1)) -lt "$MAXR" ]; then
    NEWNAME="${RUN}-INVALID-stall-attempt$attempt"
    mv "$RUN" "$NEWNAME"; [ -d "${RUN}-captured-audio" ] && mv "${RUN}-captured-audio" "${NEWNAME}-captured-audio"
    printf '# INVALID: WSJT-X stalled in this sweep (attempt %s)\n\nStopped by the liveness gate (see STALLED.json). None of its data is used. Replaced by a complete rerun of the whole sweep (capped retry %s of %s). Supervisor folder with the monitor log and the stall snapshot: %s\n' "$attempt" "$attempt" "$MAXR" "$SUP" > "$NEWNAME/INVALID.md"
    log "STALL in attempt $attempt ($(python3 -c "import json;print(json.load(open('$NEWNAME/STALLED.json'))['reason'])" 2>/dev/null)); folder kept as $NEWNAME; RETRY $attempt of $MAXR: rerunning the whole sweep"
    REPLACES=$(basename "$NEWNAME")
    attempt=$((attempt + 1))
    continue
  fi
  if [ -n "$RUN" ] && [ -f "$RUN/STALLED.json" ]; then
    halt "stalled again (attempt $attempt) with the retry cap ($MAXR) used up: stopping for good; the folders are kept and INVALID"
  fi
  halt "battery ended $PH (rc=$rc) without a liveness stall: not retried"
done
log "orphans: $(pgrep -af 'bin/wsjtx|bin/jt9|aplay|Xvfb|OpenWSFZ.Daemon|wsjtx_monitor' | grep -v pgrep | wc -l)"
log "DONE (attempts used: $attempt)"
