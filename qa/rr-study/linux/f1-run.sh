#!/bin/sh
# f1-run.sh <run-name>   (QA 2026-10-17; Architect spec F1 + amendment 1: the dsnoop slave at 4 s PLUS the --buffer-time=4000000 wrapper)
# ONE OpenWSFZ-only block on sol: V0, V1a, daemon with a private ALSA config, V1b, controls CT1/CT2, quiet gap, the 60 plays of today's trial 0 (s6_play.py --k-trials 1), end pins.
#   WRAP=0 runs the D-b' arm instead (same private config, NO wrapper: client buffer ~0.5 s).
# Everything lives under ~/qa-scratch/capture-loss/f1/<run-name>/ (outside git).  Detached by the caller (HK-023).  Never touches ~/.asoundrc.
NAME=${1:?run name}; WRAP=${WRAP:-1}
F1=$HOME/qa-scratch/capture-loss/f1
RUN=$F1/$NAME; LOG=$RUN/daemon.stdout.log; RL=$RUN/run.log
TOOL=$F1/tool/qa/rr-study
DAEMON=$HOME/OpenWSFZ-capture-loss/src/OpenWSFZ.Daemon/bin/Release/net10.0/linux-x64/publish/OpenWSFZ.Daemon
LIB=$(dirname "$DAEMON")/libft8.so; PIN=873287b114a8674f800d4816fd5362c51175fc050e535d190516e01dab03ac6a
CONFIG=$HOME/rr-run/config.json; PORT=8080
PY=$HOME/rr-venv/bin/python
ALSAENV="ALSA_CONFIG_PATH=$F1/alsa-f1.conf ALSA_PLUGIN_DIR=$HOME/local/lib/alsa-lib"
mkdir -p "$RUN"; : > "$LOG"
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

log "F1' run $NAME start; WRAP=$WRAP"
# ---- V0: nothing else on the capture node, no WSJT-X, no daemon, no player
[ -z "$(daemon_pids)" ] || halt "a daemon is running"
for n in wsjtx jt9 aplay arecord; do pgrep -x $n > /dev/null 2>&1 && halt "$n is running"; done
FU=$(fuser -v /dev/snd/pcmC0D0c 2>&1 | tr '\n' ' ')
log "V0: fuser on /dev/snd/pcmC0D0c: [${FU}]; wsjtx/jt9/daemon/aplay/arecord not running"
[ -z "$(echo "$FU" | tr -d ' ')" ] || halt "the capture node has a holder: $FU"
# ---- pins at start
[ "$(sha256sum "$LIB" | cut -d' ' -f1)" = "$PIN" ] || halt "libft8.so pin failed"
echo "build $(git -C $HOME/OpenWSFZ-capture-loss rev-parse HEAD); libft8.so $PIN; config.json $(sha256sum $CONFIG | cut -d' ' -f1); alsa-f1.conf $(sha256sum $F1/alsa-f1.conf | cut -d' ' -f1); asoundrc-f1 $(sha256sum $F1/asoundrc-f1 | cut -d' ' -f1); rig .asoundrc $(sha256sum $HOME/.asoundrc | cut -d' ' -f1)" > "$RUN/pins_start.txt"
log "pins at start: $(cat $RUN/pins_start.txt)"
diff "$HOME/.asoundrc" "$F1/asoundrc-f1" > "$RUN/asoundrc.diff"
# ---- V1a: buffer granted, under the daemon's exact environment and arguments
if [ "$WRAP" = 1 ]; then BT="--buffer-time=4000000"; else BT=""; fi
env $ALSAENV /usr/bin/arecord -v $BT -D rr_in -f FLOAT_LE -r 12000 -c 1 -t raw -d 2 /dev/null > "$RUN/v1a.txt" 2>&1
G=$("$PY" - "$RUN/v1a.txt" <<'PYEOF'
import re, sys
t = open(sys.argv[1]).read()
b = re.search(r"buffer_size\s*:\s*(\d+)", t); r = re.search(r"exact rate\s*:\s*(\d+)", t)
print(round(int(b.group(1)) / int(r.group(1)), 3) if b and r else "")
PYEOF
)
log "V1a: granted G = $G s (client PCM buffer_size / rate; dump in v1a.txt)"
[ -n "$G" ] || halt "V1a: could not read the granted buffer"
if [ "$WRAP" = 1 ] && [ "$("$PY" -c "print(1 if $G < 1.0 else 0)")" = 1 ]; then halt "V1a: G < 1.0 s: the treatment is absent, arm VOID"; fi
echo "$G" > "$RUN/G.txt"
# ---- daemon: private ALSA config and (WRAP=1) the wrapper dir first on ITS PATH only
mkdir -p "$F1/bin"
printf '#!/bin/sh\nexec /usr/bin/arecord --buffer-time=4000000 "$@"\n' > "$F1/bin/arecord"; chmod +x "$F1/bin/arecord"
if [ "$WRAP" = 1 ]; then DPATH="$F1/bin:$PATH"; else DPATH="$PATH"; fi
env PATH="$DPATH" $ALSAENV setsid nohup "$DAEMON" --config "$CONFIG" --port "$PORT" >> "$LOG" 2>&1 < /dev/null &
i=0; while [ $i -lt 180 ]; do [ -n "$(daemon_pids)" ] && ready && break; sleep 3; i=$((i + 3)); done
ready || halt "the daemon did not report captureActive within 180 s"
DP=$(daemon_pids | head -1)
log "daemon up (pid $DP) after about $i s"
# ---- V1b: wrapper in effect, and the daemon's environment
AP=$(pgrep -P "$DP" -x arecord | head -1)
ps -o args= -p "$AP" > "$RUN/v1b_arecord_args.txt" 2>&1
tr '\0' '\n' < /proc/$DP/environ | grep -E '^(ALSA_CONFIG_PATH|ALSA_PLUGIN_DIR)=' > "$RUN/v1b_daemon_alsa_env.txt"
tr '\0' '\n' < /proc/$DP/environ | grep -c "^PATH=$F1/bin" > "$RUN/v1b_path_has_wrapper.txt"
log "V1b: arecord child args [$(cat $RUN/v1b_arecord_args.txt)]; wrapper on the daemon's PATH: $(cat $RUN/v1b_path_has_wrapper.txt)"
export S6_PY=$PY
if [ "$WRAP" = 1 ]; then
  sh "$HOME/f1-controls.sh" "$LOG" "$PORT" "$RUN/controls" "$G" >> "$RL" 2>&1
else
  sleep 150
fi
CNT0=$(curl -s http://127.0.0.1:$PORT/api/v1/status | "$PY" -c "import sys,json;d=json.load(sys.stdin);print(d['captureOverrunCount'],d['captureChannelDroppedChunks'],d['watchdogRestartCount'])")
log "counters before the plays (overruns, channel drops, watchdog restarts): $CNT0"
echo "$CNT0" > "$RUN/counters_before.txt"
: > "$RUN/empty-wsjt-ALL.TXT"
# ---- the plays: trial 0 of the S6 standard schedule, OpenWSFZ pass only
( cd "$TOOL" && PYTHONPATH=$TOOL/linux/shim RR_ALSA_PLAYBACK=plughw:0,0 ALSA_PLUGIN_DIR=$HOME/local/lib/alsa-lib "$PY" s6/s6_play.py --run-dir "$RUN" --tier standard --k-trials 1 \
    --corpus $HOME/rr-s6-refset-corpus --device RR-ALSA --wsjt-all-txt "$RUN/empty-wsjt-ALL.TXT" --owsfz-all-txt $HOME/rr-run/owsfz-ALL.TXT \
    --ows-lib "$LIB" --appraiser owsfz --out-sub pass-o ) > "$RUN/s6_play.out" 2>&1
log "s6_play exited rc=$?"
sleep 20
CNT1=$(curl -s http://127.0.0.1:$PORT/api/v1/status | "$PY" -c "import sys,json;d=json.load(sys.stdin);print(d['captureOverrunCount'],d['captureChannelDroppedChunks'],d['watchdogRestartCount'])")
echo "$CNT1" > "$RUN/counters_after.txt"
log "counters after the plays (overruns, channel drops, watchdog restarts): $CNT1"
ps -o args= -p "$(pgrep -P "$DP" -x arecord | head -1)" > "$RUN/v1b_arecord_args_end.txt" 2>&1
# ---- end pins and teardown
[ "$(sha256sum "$LIB" | cut -d' ' -f1)" = "$PIN" ] && log "end pin: libft8.so $PIN" || log "END PIN FAILED"
echo "$(date -u +%FT%TZ)" > "$RUN/ended.txt"
for p in $(daemon_pids); do kill "$p" 2>/dev/null; done
i=0; while [ -n "$(daemon_pids)" ] && [ $i -lt 40 ]; do sleep 1; i=$((i + 1)); done
for p in $(daemon_pids); do kill -9 "$p" 2>/dev/null; done
log "daemon stopped; the wrapper dir was on that daemon's PATH only and is gone with it (nothing else was changed)"
log "DONE"
