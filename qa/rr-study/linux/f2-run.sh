#!/bin/sh
# f2-run.sh <run-name>   (QA 2026-10-17; Architect reliable-capture spec amendment 1 + A1.1: the pipe between arecord and the daemon enlarged to 1 MiB by a test-only wrapper)
# ONE OpenWSFZ-only block on the REAL rig (no private ALSA config): V0, V1a, daemon with the wrapper dir first on ITS PATH, V1b, V2, controls CT1/CT2, 10-cycle gap, the 60 plays of trial 0,
# end pins.  Build = main as it is: F2_DAEMON (published daemon of the study tree).  Everything under ~/qa-scratch/capture-loss/f2/<run-name>/.  Detached by the caller (HK-023).
NAME=${1:?run name}
F2=$HOME/qa-scratch/capture-loss/f2
RUN=$F2/$NAME; LOG=$RUN/daemon.stdout.log; RL=$RUN/run.log
TOOL=$HOME/qa-scratch/capture-loss/f1/tool/qa/rr-study
DAEMON=${F2_DAEMON:?path of the published daemon (main as it is)}
TREE=${F2_TREE:?path of the study tree (git checkout of main)}
LIB=$(dirname "$DAEMON")/libft8.so
CONFIG=$HOME/rr-run/config.json; PORT=8080
PY=$HOME/rr-venv/bin/python
mkdir -p "$RUN" "$F2/bin"; : > "$LOG"
log() { echo "$(date -u +%FT%TZ) $*" >> "$RL"; }
halt() { log "HALT: $*"; exit 1; }
daemon_pids() { ps -C OpenWSFZ.Daemon -o pid=,stat= 2>/dev/null | awk '$2 !~ /^Z/ {print $1}'; }
ready() { "$PY" - "$PORT" <<'PYEOF'
import json, sys, urllib.request
try:
    with urllib.request.urlopen("http://127.0.0.1:%s/api/v1/status" % sys.argv[1], timeout=4) as r:
        s = json.loads(r.read().decode("utf-8"))
    sys.exit(0 if s.get("captureActive") and s.get("decodingEnabled") else 1)
except Exception:
    sys.exit(1)
PYEOF
}
log "pipe-wrapper check block $NAME start"
# ---- V0: nothing else on the capture node
[ -z "$(daemon_pids)" ] || halt "a daemon is running"
for n in wsjtx jt9 aplay arecord; do pgrep -x $n > /dev/null 2>&1 && halt "$n is running"; done
FU=$(fuser -v /dev/snd/pcmC0D0c 2>&1 | tr '\n' ' ')
log "V0: fuser on /dev/snd/pcmC0D0c: [${FU}]; wsjtx/jt9/daemon/aplay/arecord not running"
[ -z "$(echo "$FU" | tr -d ' ')" ] || halt "the capture node has a holder: $FU"
# ---- pins at start
LIBSHA=$(sha256sum "$LIB" | cut -d' ' -f1)
echo "build $(git -C "$TREE" rev-parse HEAD); libft8.so $LIBSHA; config.json $(sha256sum $CONFIG | cut -d' ' -f1); .asoundrc $(sha256sum $HOME/.asoundrc | cut -d' ' -f1); wrapper $(sha256sum "$HOME/qa-scratch/capture-loss/f2/pipewrap-arecord.py" | cut -d' ' -f1)" > "$RUN/pins_start.txt"
log "pins at start: $(cat $RUN/pins_start.txt)"
# ---- V1a: the pipe may be raised to 1 MiB
PMAX=$(cat /proc/sys/fs/pipe-max-size); echo "$PMAX" > "$RUN/v1a_pipe_max_size.txt"
log "V1a: /proc/sys/fs/pipe-max-size = $PMAX"
[ "$PMAX" -ge 1048576 ] || halt "V1a: pipe-max-size < 1 MiB"
# ---- the wrapper, named arecord, first on the daemon's PATH only
cp "$HOME/qa-scratch/capture-loss/f2/pipewrap-arecord.py" "$F2/bin/arecord"; chmod +x "$F2/bin/arecord"
env PATH="$F2/bin:$PATH" ALSA_PLUGIN_DIR=$HOME/local/lib/alsa-lib setsid nohup "$DAEMON" --config "$CONFIG" --port "$PORT" >> "$LOG" 2>&1 < /dev/null &
i=0; while [ $i -lt 180 ]; do [ -n "$(daemon_pids)" ] && ready && break; sleep 3; i=$((i + 3)); done
ready || halt "the daemon did not report captureActive within 180 s"
DP=$(daemon_pids | head -1)
log "daemon up (pid $DP) after about $i s"
# ---- V1b / V2
AP=$(pgrep -P "$DP" -x arecord | head -1)
ps -o args= -p "$AP" > "$RUN/v2_arecord_args.txt" 2>&1
readlink /proc/$AP/fd/1 > "$RUN/v1b_fd1.txt" 2>&1
readlink /proc/$AP/exe > "$RUN/v2_exe.txt" 2>&1
ps -e -o pid=,ppid=,comm= | awk -v d="$DP" '$2==d' > "$RUN/v2_daemon_children.txt"
grep "pipe size" "$LOG" | head -3 > "$RUN/v1b_log_pipe_size.txt"
log "V1b: log [$(cat $RUN/v1b_log_pipe_size.txt | tr '\n' '|')] fd1 [$(cat $RUN/v1b_fd1.txt)]; V2: args [$(cat $RUN/v2_arecord_args.txt)] exe [$(cat $RUN/v2_exe.txt)] children of the daemon [$(cat $RUN/v2_daemon_children.txt | tr '\n' '|')]"
grep -q "pipe size 1048576" "$RUN/v1b_log_pipe_size.txt" || halt "V1b: the log does not show 'pipe size 1048576'"
case "$(cat $RUN/v1b_fd1.txt)" in pipe:*) ;; *) halt "V1b: fd 1 of arecord is not a pipe: $(cat $RUN/v1b_fd1.txt)";; esac
grep -qi python "$RUN/v2_arecord_args.txt" "$RUN/v2_daemon_children.txt" && halt "V2: a python process is in the chain"
export S6_PY=$PY
sh "$HOME/f2-controls.sh" "$LOG" "$PORT" "$RUN/controls" >> "$RL" 2>&1
status() { curl -s http://127.0.0.1:$PORT/api/v1/status | "$PY" -c "import sys,json;d=json.load(sys.stdin);print(d['captureOverrunCount'],d['captureChannelDroppedChunks'],d['watchdogRestartCount'])"; }
status > "$RUN/counters_before.txt"; log "counters before the plays (overruns, channel drops, watchdog restarts): $(cat $RUN/counters_before.txt)"
: > "$RUN/empty-wsjt-ALL.TXT"
( cd "$TOOL" && PYTHONPATH=$TOOL/linux/shim RR_ALSA_PLAYBACK=plughw:0,0 ALSA_PLUGIN_DIR=$HOME/local/lib/alsa-lib "$PY" s6/s6_play.py --run-dir "$RUN" --tier standard --k-trials 1 \
    --corpus $HOME/rr-s6-refset-corpus --device RR-ALSA --wsjt-all-txt "$RUN/empty-wsjt-ALL.TXT" --owsfz-all-txt $HOME/rr-run/owsfz-ALL.TXT \
    --ows-lib "$LIB" --config "$CONFIG" --appraiser owsfz --out-sub pass-o ) > "$RUN/s6_play.out" 2>&1
log "s6_play exited rc=$?"
sleep 20
status > "$RUN/counters_after.txt"; log "counters after the plays: $(cat $RUN/counters_after.txt)"
ps -o args= -p "$(pgrep -P "$DP" -x arecord | head -1)" > "$RUN/v2_arecord_args_end.txt" 2>&1
[ "$(sha256sum "$LIB" | cut -d' ' -f1)" = "$LIBSHA" ] && log "end pin: libft8.so $LIBSHA" || log "END PIN FAILED (libft8.so)"
echo "build $(git -C "$TREE" rev-parse HEAD); libft8.so $(sha256sum "$LIB" | cut -d' ' -f1); config.json $(sha256sum $CONFIG | cut -d' ' -f1); .asoundrc $(sha256sum $HOME/.asoundrc | cut -d' ' -f1)" > "$RUN/pins_end.txt"
echo "$(date -u +%FT%TZ)" > "$RUN/ended.txt"
for p in $(daemon_pids); do kill "$p" 2>/dev/null; done
i=0; while [ -n "$(daemon_pids)" ] && [ $i -lt 40 ]; do sleep 1; i=$((i + 1)); done
for p in $(daemon_pids); do kill -9 "$p" 2>/dev/null; done
log "daemon stopped; the wrapper dir was on that daemon's PATH only (nothing else was changed; ~/.asoundrc untouched)"
log "DONE"
