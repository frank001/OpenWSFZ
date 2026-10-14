#!/bin/sh
# One supervised R&R battery (= one SWEEP) on sol with the B2-MERGED build and the WSJT-X monitoring M1-M3 (QA, 2026-10-14).
#   usage: [SCENARIO_RETRIES=3] battery-b2.sh <name> <scenarios> [extra run_study.py arguments...]
#   build under test: ~/OpenWSFZ-b2src (338ef61c = B2 merged with main 76aa48cd, shim 20260062), daemon published from it; its committed libft8.so is the pin
#   tooling:          ~/rr-work-b2 (qa/refset): analyser on %StudyVar; M1 monitor; M2 liveness gate (ON through every scenario incl. S6); M3 coverage; S6-V7
#   WSJT-X 2.7.0 (rig `rr`) is started here with `ulimit -c unlimited` (core dumps land in the working directory); M1 runs beside the battery.
# SCENARIO-LEVEL RETRY (Captain 2026-10-14: "the 3-retry cap should be within trials, not as a whole"): SCENARIO_RETRIES (default 0 = stop and flag at the first stall) is the number of
#   retries PER SCENARIO. When WSJT-X stalls inside a scenario (M2 stop) or the scenario's coverage fails (M3; S6-V7), run_study.py restarts WSJT-X (restart-wsjtx-rr.sh), reruns THAT
#   scenario with all its trials in the SAME sweep folder, keeps the failed attempt as INVALID and records a replacement (scenario_retries.json). The next failure of the same
#   scenario halts (exit 22). Passed scenarios are kept. Any other failure halts at once. No wall-time limit. Never a single trial or play.
# HALTS if another job is on, WSJT-X does not start, or the battery does not end DONE. Detached by the caller; no cron (HK-023).
NAME=$1; SCEN=$2; shift 2
RETR=${SCENARIO_RETRIES:-0}
SUP=$HOME/rr-run/$NAME
LOG=$HOME/rr-run/$NAME.log
WORK=$HOME/rr-work-b2/qa/rr-study
DAEMON=$HOME/OpenWSFZ-b2src/src/OpenWSFZ.Daemon/bin/Release/net10.0/linux-x64/publish/OpenWSFZ.Daemon
SAVE="$HOME/.local/share/WSJT-X - rr/save"
ARCH=$HOME/rr-run/cycle-audio
PY=$HOME/rr-venv/bin/python
log() { echo "$(date -u +%FT%TZ) $*" >> "$LOG"; }
halt() { log "HALT: $*"; exit 1; }

cd "$HOME"
# busy check by EXACT process name / anchored command line, so the launcher's own command line (which may mention the daemon's path) can never match
if pgrep -x OpenWSFZ.Daemon > /dev/null 2>&1 || pgrep -x aplay > /dev/null 2>&1 || pgrep -f "^[^ ]*python[^ ]* [^ ]*(run_study|run_refset|run_leg_e)" > /dev/null 2>&1 || pgrep -f "^dotnet [^ ]*RefSet.dll" > /dev/null 2>&1; then halt "another job is running on sol"; fi
rm -rf "$SUP"; mkdir -p "$SUP"
T0=$(date +%s)
log "sweep $NAME start; scenarios $SCEN; extra args: $*; retries per scenario: $RETR"
log "build under test: $(git -C $HOME/OpenWSFZ-b2src rev-parse HEAD); libft8.so $(sha256sum "$(dirname "$DAEMON")/libft8.so" | cut -d' ' -f1); tooling $(git -C $HOME/rr-work-b2 rev-parse HEAD)"
# S6 pins the OpenWSFZ native library the daemon loads: the one in the daemon's publish folder (added here so no caller has to pass the path)
S6LIB=""; case ",$SCEN," in *,S6,*) S6LIB="--s6-ows-lib $(dirname "$DAEMON")/libft8.so";; esac

sh "$HOME/restart-wsjtx-rr.sh" > "$SUP/wsjtx-start.out" 2>&1 || halt "WSJT-X (the real wsjtx binary) did not start (see $SUP/wsjtx-start.out)"
log "WSJT-X up: pid $(pgrep -x wsjtx | head -1); core limit in its shell: $(grep -m1 'Max core' /proc/$(pgrep -x wsjtx | head -1)/limits)"
rm -rf "$ARCH"/* 2>/dev/null
setsid nohup "$PY" "$WORK/linux/wsjtx_monitor.py" --save-dir "$SAVE" --out-dir "$SUP" --owsfz-archive "$ARCH" >> "$SUP/monitor.out" 2>&1 < /dev/null &
sleep 3
log "monitor started (pid $(pgrep -f wsjtx_monitor.py | head -1)); supervisor folder $SUP"
export PYTHONPATH=$WORK/linux/shim RR_ALSA_PLAYBACK=plughw:0,0 ALSA_PLUGIN_DIR=$HOME/local/lib/alsa-lib
( cd "$WORK" && "$PY" run_study_linux.py --poll --supervisor-dir "$SUP" --daemon-exe "$DAEMON" --config "$HOME/rr-run/config.json" --port 8080 \
    --wsjtx-ini "$HOME/.local/share/WSJT-X - rr/WSJT-X - rr.ini" -- --scenarios "$SCEN" --skip-warmup --device RR-ALSA \
    --liveness-save-dir "$SAVE" --coverage-owsfz-dir "$ARCH" --scenario-retries "$RETR" --wsjtx-restart-cmd "sh $HOME/restart-wsjtx-rr.sh" $S6LIB "$@" > "$SUP/supervisor.log" 2>&1 )
rc=$?
PH=$("$PY" -c "import json;print(json.load(open('$SUP/status.json'))['phase'])" 2>/dev/null)
log "battery ended rc=$rc phase=$PH"
touch "$SUP/monitor.stop"; sleep 20
sh "$HOME/stop-wsjtx.sh" > /dev/null 2>&1; pkill -CONT -x wsjtx 2>/dev/null; sleep 1; pkill -9 -x wsjtx 2>/dev/null; pkill -9 -x jt9 2>/dev/null; pkill -9 -x Xvfb 2>/dev/null
# the run folder of this sweep: the newest results folder touched since T0 (captured-audio and INVALID folders are not it)
RUN=""
for d in $(ls -dt "$WORK"/results/20*/ 2>/dev/null | head -4); do
  d=${d%/}; case "$d" in *-captured-audio|*-INVALID-*) continue;; esac
  [ "$(stat -c %Y "$d" 2>/dev/null || echo 0)" -ge "$T0" ] && { RUN=$d; break; }
done
log "run folder: ${RUN:-none found}"
if [ -n "$RUN" ] && [ -f "$RUN/scenario_retries.json" ]; then
  log "scenario retries: $("$PY" -c "import json;d=json.load(open('$RUN/scenario_retries.json'));print(json.dumps(d['totals']), {k:v['retries_used'] for k,v in d['scenarios'].items() if v['retries_used']})")"
fi
log "stall events (M1): $(wc -l < "$SUP/stall_events.jsonl" 2>/dev/null || echo 0); monitor samples: $(wc -l < "$SUP/monitor.jsonl" 2>/dev/null || echo 0)"
# the per-sweep monitoring summary (aggregates only) goes into the run folder for the report
[ -n "$RUN" ] && "$PY" "$WORK/linux/monitoring_summary.py" --sup-dir "$SUP" --run-dir "$RUN" --core-dir "$HOME" > "$SUP/monitoring_summary.out" 2>&1 && log "monitoring_summary.json written in the run folder"
log "orphans: $(pgrep -af 'bin/wsjtx|bin/jt9|aplay|Xvfb|OpenWSFZ.Daemon|wsjtx_monitor' | grep -v pgrep | wc -l)"
case $rc in
  0) [ "$PH" = "DONE" ] || halt "battery ended $PH (rc=$rc)";;
  21) halt "WSJT-X stalled and no retry was allowed (rc 21)";;
  22) halt "a scenario failed again with its retries used up (rc 22): the battery halted and flagged (RETRIES_EXHAUSTED.json)";;
  23) halt "WSJT-X could not be restarted or did not pass the warm-up (rc 23)";;
  *) halt "battery ended $PH (rc=$rc) without a stall: not retried";;
esac
log "DONE"
