#!/bin/sh
# THIRD-PASS (#240) variant of battery-series.sh (QA, 2026-10-18): one supervised R&R battery (= one SWEEP) on sol for a build and a decoder config CHOSEN BY THE CALLER, so a
# Deep-ON and a Deep-OFF sweep run on the SAME build and differ only in the config's decoder.decodingDepth. Derived from battery-series.sh with exactly these changes:
#   TP_DAEMON (the published daemon), TP_REPO (its checkout, for the build line) and TP_CONFIG (the rig config, with decoder.decodingDepth set) are REQUIRED environment variables;
#   the build line also logs the config's decoder.decodingDepth. Everything else is battery-series.sh unchanged. A Deep-ON sweep is NEVER pooled with a Deep-OFF one (spec 4).
# Original header follows.
# One supervised R&R battery (= one SWEEP) on sol with the B2-MERGED build and the WSJT-X monitoring M1-M3 (QA, 2026-10-14).
#   usage: [SCENARIO_RETRIES=3] battery-b2.sh <name> <scenarios> [extra run_study.py arguments...]
#   build under test: ~/OpenWSFZ-series (b6fdd391 = B2 338ef61c merged with main 306975d2 (series build, 2026-10-17)), daemon published from it; its committed libft8.so is the pin
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
DAEMON=${TP_DAEMON:?set TP_DAEMON to the published OpenWSFZ.Daemon of the build under test}
TP_REPO=${TP_REPO:?set TP_REPO to the git checkout the daemon was published from}
CFG=${TP_CONFIG:?set TP_CONFIG to the rig config (a copy of ~/rr-run/config.json with decoder.decodingDepth)}
[ -x "$DAEMON" ] && [ -f "$CFG" ] || { echo "TP_DAEMON or TP_CONFIG missing" >&2; exit 1; }
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
DEPTH=$("$PY" -c "import json;print(json.load(open('$CFG'))['decoder'].get('decodingDepth','Normal (key absent)'))" 2>/dev/null)
log "decoding depth (config $CFG): $DEPTH"
# CONFIG PIN (QA, 2026-10-18, after a Settings-page save changed the rig config unnoticed): the rig config must still be byte-identical to the pinned one, and TP_CONFIG must be
# that config plus ONLY decoder.decodingDepth (re-serialised in the daemon's own style: indent 2, no trailing newline). Anything else HALTS the sweep before it starts.
RIGCFG=${TP_RIG_CONFIG:-$HOME/rr-run/config.json}
PIN=${TP_RIG_CONFIG_SHA:-661de047bc52b833620316c2fe505000584fcde318987f25793a378c37733c9d}
# 2026-10-19 (PR #248: decoder.decodingDepth now DEFAULTS TO DEEP on main): the pin identifies the rig config MINUS decoder.decodingDepth (661de047..., the config every R&R since B2 ran on, which had
# no such key), and the rig config must now CARRY the key explicitly, so a key-absent rig config can never silently become Deep. Both files are compared after dropping the key and re-serialising
# (indent 2, no trailing newline = the daemon's own style); the rig config's own explicit depth is reported beside the result.
CK=$("$PY" - "$RIGCFG" "$CFG" "$PIN" <<'PYEOF'
import hashlib, json, sys
rig, tp, pin = sys.argv[1:4]
FLAGS = []
def minus_depth(path):
    c = json.load(open(path, encoding="utf8"))
    depth = c["decoder"].pop("decodingDepth", None)
    # 2026-10-22 (PR #253, DI sync 7: decoder.coherentFallbackEnabled now DEFAULTS TO ON): the sweep config may CARRY the flag explicitly (DI7COH sets it true); like the depth, it is dropped
    # before the pin comparison and reported beside the result, so an explicit flag is the ONLY other difference allowed between TP_CONFIG and the pinned rig config.
    flag = c["decoder"].pop("coherentFallbackEnabled", "absent")
    FLAGS.append(flag)
    return hashlib.sha256(json.dumps(c, indent=2, ensure_ascii=False).encode()).hexdigest(), depth
rs, rig_depth = minus_depth(rig)
ts, _ = minus_depth(tp)
ok = rs == pin and ts == pin and rig_depth in ("Normal", "Deep")
print(("OK" if ok else "FAIL") + " rig-minus-depth=%s tp-minus-depth=%s pin=%s rig-depth=%s rig-flag=%s tp-flag=%s" % (rs[:16], ts[:16], pin[:16], rig_depth, FLAGS[0], FLAGS[1]))
PYEOF
)
log "config pin: $CK"
case "$CK" in OK*) ;; *) halt "CONFIG PIN FAILED ($CK): the rig config or the sweep config differs from the pinned one; nothing was run";; esac
log "build under test: $(git -C $TP_REPO rev-parse HEAD); libft8.so $(sha256sum "$(dirname "$DAEMON")/libft8.so" | cut -d' ' -f1); tooling $(git -C $HOME/rr-work-b2 rev-parse HEAD)"
# S6 pins the OpenWSFZ native library the daemon loads: the one in the daemon's publish folder (added here so no caller has to pass the path)
S6LIB=""; case ",$SCEN," in *,S6,*) S6LIB="--s6-ows-lib $(dirname "$DAEMON")/libft8.so";; esac
# S6 MODE (Captain 2026-10-15): SEQUENTIAL by default on sol. Played together, WSJT-X's Qt ALSA capture stalls (4 of 4 S6 attempts of B2BASE sweep 1; isolation runs of 2026-10-15), so S6 is
# played twice, WSJT-X alone and then OpenWSFZ alone (run_study.py --s6-mode sequential; hook s6-phase.sh; s6/s6_merge.py). S1-S5, S7, S8 and S3c stay concurrent. S6_MODE=concurrent restores
# the original single concurrent S6 (never pool a concurrent S6 row with a sequential one).
S6_MODE=${S6_MODE:-sequential}
S6SEQ=""; case ",$SCEN," in *,S6,*) [ "$S6_MODE" = "sequential" ] && S6SEQ="--s6-mode sequential --s6-phase-cmd $HOME/s6-phase.sh";; esac

sh "$HOME/restart-wsjtx-rr.sh" > "$SUP/wsjtx-start.out" 2>&1 || halt "WSJT-X (the real wsjtx binary) did not start (see $SUP/wsjtx-start.out)"
log "WSJT-X up: pid $(pgrep -x wsjtx | head -1); core limit in its shell: $(grep -m1 'Max core' /proc/$(pgrep -x wsjtx | head -1)/limits)"
rm -rf "$ARCH"/* 2>/dev/null
setsid nohup "$PY" "$WORK/linux/wsjtx_monitor.py" --save-dir "$SAVE" --out-dir "$SUP" --owsfz-archive "$ARCH" >> "$SUP/monitor.out" 2>&1 < /dev/null &
sleep 3
log "monitor started (pid $(pgrep -f wsjtx_monitor.py | head -1)); supervisor folder $SUP"
# THIRD PASS (#240): the 1 Hz status poll (arecord overruns, channel drops, restarts + the live decoding depth and third-pass counters) runs for the whole sweep, so overruns and
# drops are per PLAY and not only per sweep, and the depth read-back below can void a sweep. The poller tolerates a daemon that is down between scenarios (null samples).
POLL=$HOME/status_poller_tp.py
[ -f "$POLL" ] || halt "status_poller_tp.py is not in $HOME (copy qa/rr-study/linux/status_poller.py there)"
rm -f "$SUP/poller.stop"
setsid nohup "$PY" "$POLL" --port 8080 --out "$SUP/statuspoll.jsonl" --stop-file "$SUP/poller.stop" >> "$SUP/poller.out" 2>&1 < /dev/null &
log "status poller started (pid $(pgrep -f status_poller_tp.py | head -1))"
# CPU scheduling of the daemon (sched-helper.sh; QA 2026-10-15): DAEMON_SCHED=none (default) | nice | pin. The daemon's residual pass can starve WSJT-X's Qt ALSA capture thread (WSJT-X then
# silently stops saving WAVs); 'nice' lowers the daemon's threads so WSJT-X and the daemon's own arecord pre-empt them. Whatever is chosen is recorded in this sweep's log.
SCHED=${DAEMON_SCHED:-none}
rm -f "$SUP/sched.stop"
if [ "$SCHED" != "none" ]; then
  setsid nohup sh "$HOME/sched-helper.sh" "$SCHED" "$SUP/sched.stop" "$LOG" > /dev/null 2>&1 < /dev/null &
fi
log "daemon scheduling: $SCHED"
log "S6 mode: $S6_MODE"
rm -f "$SUP/wsjtx.expected_off"
export S6_SUP="$SUP" S6_DAEMON="$DAEMON" S6_CONFIG="$CFG" S6_PORT=8080 S6_LOG="$LOG" S6_PY="$PY"
export PYTHONPATH=$WORK/linux/shim RR_ALSA_PLAYBACK=plughw:0,0 ALSA_PLUGIN_DIR=$HOME/local/lib/alsa-lib
( cd "$WORK" && "$PY" run_study_linux.py --poll --supervisor-dir "$SUP" --daemon-exe "$DAEMON" --config "$CFG" --port 8080 \
    --wsjtx-ini "$HOME/.local/share/WSJT-X - rr/WSJT-X - rr.ini" -- --scenarios "$SCEN" --skip-warmup --device RR-ALSA \
    --liveness-save-dir "$SAVE" --coverage-owsfz-dir "$ARCH" --scenario-retries "$RETR" --wsjtx-restart-cmd "sh $HOME/restart-wsjtx-rr.sh" $S6LIB $S6SEQ "$@" > "$SUP/supervisor.log" 2>&1 )
rc=$?
touch "$SUP/sched.stop"
rm -f "$SUP/wsjtx.expected_off"
PH=$("$PY" -c "import json;print(json.load(open('$SUP/status.json'))['phase'])" 2>/dev/null)
log "battery ended rc=$rc phase=$PH"
touch "$SUP/monitor.stop"; touch "$SUP/poller.stop"; sleep 20
pkill -x OpenWSFZ.Daemon 2>/dev/null     # a sequential S6 restarts the daemon outside the supervisor's pid record: make sure none is left
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
# THIRD PASS validity row (Architect 2026-10-18): the depth read back from the LIVE daemon must equal the config's at the start and at the end of the sweep; a mismatch VOIDS the sweep.
if [ -n "$RUN" ]; then
  cp "$SUP/statuspoll.jsonl" "$RUN/statuspoll.jsonl" 2>/dev/null
  [ -f "$HOME/depth_readback.py" ] || halt "depth_readback.py is not in $HOME (copy qa/rr-study/linux/depth_readback.py there)"
  DR=$("$PY" "$HOME/depth_readback.py" --config "$CFG" --statuspoll "$SUP/statuspoll.jsonl" --out "$RUN/depth_readback.json" 2>&1); DRC=$?
  log "depth read-back: $DR"
  [ $DRC -eq 0 ] || halt "VOID: the decoding depth read back from the live daemon does not match the config ($DR); this sweep is void (depth_readback.json in the run folder)"
fi
case $rc in
  0) [ "$PH" = "DONE" ] || halt "battery ended $PH (rc=$rc)";;
  21) halt "WSJT-X stalled and no retry was allowed (rc 21)";;
  22) halt "a scenario failed again with its retries used up (rc 22): the battery halted and flagged (RETRIES_EXHAUSTED.json)";;
  23) halt "WSJT-X could not be restarted or did not pass the warm-up (rc 23)";;
  *) halt "battery ended $PH (rc=$rc) without a stall: not retried";;
esac
log "DONE"
