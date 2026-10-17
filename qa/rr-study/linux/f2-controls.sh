#!/bin/sh
# f2-controls.sh <daemon.stdout.log> <port> <out-dir>   (QA 2026-10-17; Architect reliable-capture spec amendment 1 + A1.1)
# Controls of the pipe-wrapper check block, on the SAME daemon instance that then plays the block.
#   CT1 (the pipe holds a daemon stall)  kill -STOP the DAEMON 3.0 s, then -CONT.  PASS = CaptureOverrunCount unchanged AND the net applied correction over the 3 windows after -CONT
#                                        is within +-600 samples AND the third window's |wanted| <= 600.  The three windows' wanted/applied are written out verbatim (A1.1: the daemon
#                                        reads the backlog in a burst, so the framer's own comment (CycleFramer.cs:243-282) predicts a backlog bias in the first windows).
#   CT2 (instrument alive)               kill -STOP the arecord child 1.0 s, then -CONT.  PASS = the counter rises by >= 1 within 5 s of -CONT (the rig's ring is 0.2 s; HK-026).
# A control is INVALID if the capture watchdog restarted capture (watchdogRestartCount rose, or a "Capture ended unexpectedly" line): repeated ONCE; a second invalid attempt counts as failed.
# After each control: wait until two consecutive windows have |wanted| <= 600; after CT2 at least 10 further cycles (150 s) before the first play.  Aggregates and arecord's own text only.
# Never exits non-zero: the result is in controls_result.txt.
LOG=${1:?daemon stdout log}; PORT=${2:-8080}; OUT=${3:?out dir}
PY=${S6_PY:-$HOME/rr-venv/bin/python}
mkdir -p "$OUT"
R=$OUT/controls_result.txt; C=$OUT/controls.log
: > "$R"
say() { echo "$(date -u +%FT%T.%3NZ) $*" >> "$C"; }
res() { echo "$*" >> "$R"; say "RESULT $*"; }
daemon_pid() { ps -C OpenWSFZ.Daemon -o pid=,stat= 2>/dev/null | awk '$2 !~ /^Z/ {print $1}' | head -1; }
arecord_pid() { pgrep -P "$1" -x arecord | head -1; }
status() { "$PY" - "$PORT" "$1" <<'PYEOF'
import json, sys, urllib.request
try:
    with urllib.request.urlopen("http://127.0.0.1:%s/api/v1/status" % sys.argv[1], timeout=4) as r:
        s = json.loads(r.read().decode("utf-8"))
    print(s.get(sys.argv[2], ""))
except Exception:
    print("")
PYEOF
}
nwin() { n=$(grep -c 'Window emitted' "$LOG" 2>/dev/null); echo "${n:-0}"; }
lines_after() { tail -n +"$(( $1 + 1 ))" "$LOG"; }
winlines_after() { lines_after "$1" | grep 'Window emitted'; }
wanted_of() { echo "$1" | sed -n 's/.*wanted \(-\{0,1\}[0-9]\{1,\}\),.*/\1/p'; }
applied_of() { echo "$1" | sed -n 's/.*applied \(-\{0,1\}[0-9]\{1,\}\) samples.*/\1/p'; }

wait_new_window() { i=0; while [ "$(nwin)" -le "$1" ] && [ "$i" -lt "$2" ]; do sleep 1; i=$((i + 1)); done; [ "$(nwin)" -gt "$1" ]; }

settle() {
  i=0; ok=0; seen=$(nwin)
  while [ "$i" -lt 720 ]; do
    if [ "$(nwin)" -gt "$seen" ]; then
      l=$(grep 'Window emitted' "$LOG" | tail -1); w=$(wanted_of "$l"); seen=$(nwin)
      if [ -n "$w" ] && [ "${w#-}" -le 600 ]; then ok=$((ok + 1)); else ok=0; fi
      say "settle: wanted=$w ok=$ok"
      [ "$ok" -ge 2 ] && return 0
    fi
    sleep 2; i=$((i + 2))
  done
  return 1
}

run_control() {   # <CT1|CT2> <attempt>
  NAME=$1; ATT=$2
  say "$NAME attempt $ATT: begin"
  dp=$(daemon_pid); [ -n "$dp" ] || { res "$NAME attempt $ATT: NO DAEMON"; return 2; }
  ap=$(arecord_pid "$dp"); [ -n "$ap" ] || { res "$NAME attempt $ATT: NO ARECORD CHILD of $dp"; return 2; }
  n0=$(nwin); wait_new_window "$n0" 40 || { res "$NAME attempt $ATT: no window emitted in 40 s"; return 2; }
  sleep 3
  cnt0=$(status captureOverrunCount); wd0=$(status watchdogRestartCount); L0=$(wc -l < "$LOG"); nw0=$(nwin)
  t0=$(date -u +%FT%T.%3NZ)
  if [ "$NAME" = "CT1" ]; then kill -STOP "$dp"; sleep 3.0; kill -CONT "$dp"; else kill -STOP "$ap"; sleep 1.0; kill -CONT "$ap"; fi
  t1=$(date -u +%FT%T.%3NZ)
  say "$NAME attempt $ATT: STOP at $t0, CONT at $t1; counter before=$cnt0 watchdog before=$wd0"
  # the three windows after -CONT (CT1) / the counter within 5 s (CT2)
  i=0; while [ "$(( $(nwin) - nw0 ))" -lt 3 ] && [ "$i" -lt 90 ]; do sleep 1; i=$((i + 1)); done
  cnt1=$(status captureOverrunCount); wd1=$(status watchdogRestartCount)
  OV=$(lines_after "$L0" | grep -i 'arecord overrun' | cut -c1-300)
  UNEXP=$(lines_after "$L0" | grep -c 'Capture ended unexpectedly')
  W1=$(winlines_after "$L0" | sed -n 1p); W2=$(winlines_after "$L0" | sed -n 2p); W3=$(winlines_after "$L0" | sed -n 3p); W4=$(winlines_after "$L0" | sed -n 4p)
  { echo "---- $NAME attempt $ATT: verbatim overrun line(s) ----"; echo "$OV"; echo "---- the framer lines after the stop, verbatim (the first is the window the stop fell in) ----"; echo "$W1"; echo "$W2"; echo "$W3"; echo "$W4"; } >> "$C"
  say "$NAME attempt $ATT: counter $cnt0 -> $cnt1; watchdog $wd0 -> $wd1; unexpected-end lines $UNEXP"
  if [ "$wd1" != "$wd0" ] || [ "$UNEXP" != "0" ]; then res "$NAME attempt $ATT: INVALID (capture restarted: watchdog $wd0 -> $wd1, unexpected-end lines $UNEXP)"; settle || say "settle: did not converge"; return 3; fi
  if [ "$NAME" = "CT1" ]; then
    # the 3 windows after -CONT: lines 2,3,4 (line 1 is the window the stop fell in, which ends late)
    a2=$(applied_of "$W2"); a3=$(applied_of "$W3"); a4=$(applied_of "$W4"); w4=$(wanted_of "$W4")
    net=$(( ${a2:-0} + ${a3:-0} + ${a4:-0} ))
    same=0; [ -n "$cnt0" ] && [ "$cnt1" = "$cnt0" ] && same=1
    netok=0; [ "${net#-}" -le 600 ] && netok=1
    lastok=0; [ -n "$w4" ] && [ "${w4#-}" -le 600 ] && lastok=1
    if [ "$same" = 1 ] && [ "$netok" = 1 ] && [ "$lastok" = 1 ]; then v=PASS; else v=FAIL; fi
    res "$NAME attempt $ATT: $v (overrun counter $cnt0 -> $cnt1; net applied over the 3 windows after -CONT $net samples (bar +-600); third window wanted ${w4:-none} (bar |.| <= 600); windows: [$(wanted_of "$W2")/$a2] [$(wanted_of "$W3")/$a3] [$w4/$a4])"
  else
    rose=0; [ -n "$cnt0" ] && [ -n "$cnt1" ] && [ "$cnt1" -gt "$cnt0" ] && rose=1
    if [ "$rose" = 1 ]; then v=PASS; else v=FAIL; fi
    res "$NAME attempt $ATT: $v (overrun counter $cnt0 -> $cnt1; arecord stopped 1.0 s)"
  fi
  settle || say "settle: did not converge in 12 min"
  [ "$v" = PASS ] && return 0 || return 1
}

for CT in CT1 CT2; do
  run_control "$CT" 1; rc=$?
  [ "$rc" = 3 ] && { run_control "$CT" 2; rc=$?; [ "$rc" = 3 ] && res "$CT: INVALID TWICE (counts as failed)"; }
  [ "$CT" = CT1 ] && sleep 30
done
say "quiet gap: 10 cycles"; sleep 150
res "counters at hand-over: overruns $(status captureOverrunCount); channel drops $(status captureChannelDroppedChunks); watchdog restarts $(status watchdogRestartCount)"
say "controls done"
exit 0
