#!/bin/sh
# capture-loss-controls.sh <daemon.stdout.log> <port> <out-dir>   (QA 2026-10-17)
# Positive controls C1 and C2 of the capture-loss instrument (Architect spec 2026-10-17-0927 §4 + amendment 1, A4), run on the SAME daemon instance that then plays the S6 pass-O block.
# HK-026: prove the instrument fires on a known loss before believing any count.
#   C1 (L1)  kill -STOP the arecord child for 2.0 s, then -CONT.  PASS when CaptureOverrunCount rises by >= 1 within 5 s of -CONT AND the next window's framer `wanted` >= +12000 samples (+1.0 s).
#   C2 (L2)  kill -STOP the daemon for 3.0 s, then -CONT.         PASS when CaptureOverrunCount rises by >= 1 within 5 s of -CONT.
# "next window" = the SECOND `Window emitted` line after -CONT (the first is the window the stop fell in, which ends late; the second began late). Both lines are written out verbatim.
# A control is INVALID if the capture watchdog restarted capture during it (watchdogRestartCount rose, or a "Capture ended unexpectedly" line): it is repeated ONCE (A4); a second INVALID
# voids O1-O3, K1 and RC-11 (the analysis reads controls_result.txt). A control that simply FAILS is final (no repeat).
# After each control the script waits until two consecutive windows have |wanted| <= 600 samples (50 ms) again, so the block does not start while the framer is still converging.
# Aggregates and arecord's own text only (HK-037: no message text). Never exits non-zero: the caller (s6-phase hook) must not skip the pass because of a control; the result is in the files.
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
lines_after() { tail -n +"$(( $1 + 1 ))" "$LOG"; }          # log lines after line number $1
winlines_after() { lines_after "$1" | grep 'Window emitted'; }
wanted_of() { echo "$1" | sed -n 's/.*wanted \(-\{0,1\}[0-9]\{1,\}\),.*/\1/p'; }

wait_new_window() {   # <window-count-before> <timeout s>: wait until a new Window emitted line appears
  i=0; while [ "$(nwin)" -le "$1" ] && [ "$i" -lt "$2" ]; do sleep 1; i=$((i + 1)); done
  [ "$(nwin)" -gt "$1" ]
}

settle() {   # wait until two consecutive windows have |wanted| <= 600 samples; max 12 min
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

run_control() {   # <C1|C2> <attempt>
  NAME=$1; ATT=$2
  say "$NAME attempt $ATT: begin"
  dp=$(daemon_pid); [ -n "$dp" ] || { res "$NAME attempt $ATT: NO DAEMON"; return 2; }
  ap=$(arecord_pid "$dp"); [ -n "$ap" ] || { res "$NAME attempt $ATT: NO ARECORD CHILD of $dp"; return 2; }
  # start the stop ~3 s into a fresh window: wait for the next emission, then 3 s
  n0=$(nwin); wait_new_window "$n0" 40 || { res "$NAME attempt $ATT: no window emitted in 40 s"; return 2; }
  sleep 3
  cnt0=$(status captureOverrunCount); wd0=$(status watchdogRestartCount); L0=$(wc -l < "$LOG"); nw0=$(nwin)
  t0=$(date -u +%FT%T.%3NZ)
  if [ "$NAME" = "C1" ]; then kill -STOP "$ap"; sleep 2.0; kill -CONT "$ap"; else kill -STOP "$dp"; sleep 3.0; kill -CONT "$dp"; fi
  t1=$(date -u +%FT%T.%3NZ)
  say "$NAME attempt $ATT: STOP at $t0, CONT at $t1; counter before=$cnt0 watchdog before=$wd0"
  # the counter within 5 s of -CONT
  cnt1=$cnt0; i=0
  while [ "$i" -lt 10 ]; do
    sleep 0.5; i=$((i + 1)); c=$(status captureOverrunCount)
    [ -n "$c" ] && cnt1=$c
    [ -n "$cnt0" ] && [ -n "$cnt1" ] && [ "$cnt1" -gt "$cnt0" ] && break
  done
  # wait for two new Window emitted lines after the stop (the second is the "next window")
  i=0; while [ "$(( $(nwin) - nw0 ))" -lt 2 ] && [ "$i" -lt 60 ]; do sleep 1; i=$((i + 1)); done
  W1=$(winlines_after "$L0" | sed -n 1p); W2=$(winlines_after "$L0" | sed -n 2p)
  wd1=$(status watchdogRestartCount)
  OV=$(lines_after "$L0" | grep -i 'arecord overrun' | cut -c1-300)
  UNEXP=$(lines_after "$L0" | grep -c 'Capture ended unexpectedly')
  { echo "---- $NAME attempt $ATT: verbatim overrun line(s) (arecord's own text, after the colon) ----"; echo "$OV"
    echo "---- window lines after the stop ----"; echo "$W1"; echo "$W2"; } >> "$C"
  w2=$(wanted_of "$W2")
  say "$NAME attempt $ATT: counter $cnt0 -> $cnt1; watchdog $wd0 -> $wd1; unexpected-end lines $UNEXP; next-window wanted=$w2"
  if [ "$wd1" != "$wd0" ] || [ "$UNEXP" != "0" ]; then res "$NAME attempt $ATT: INVALID (capture restarted: watchdog $wd0 -> $wd1, unexpected-end lines $UNEXP)"; settle || say "settle: did not converge in 12 min"; return 3; fi
  rose=0; [ -n "$cnt0" ] && [ -n "$cnt1" ] && [ "$cnt1" -gt "$cnt0" ] && rose=1
  if [ "$NAME" = "C1" ]; then
    big=0; [ -n "$w2" ] && [ "$w2" -ge 12000 ] && big=1
    if [ "$rose" = 1 ] && [ "$big" = 1 ]; then v=PASS; else v=FAIL; fi
    res "$NAME attempt $ATT: $v (overrun counter $cnt0 -> $cnt1, next-window wanted ${w2:-none} samples, bar >= 12000)"
  else
    if [ "$rose" = 1 ]; then v=PASS; else v=FAIL; fi
    res "$NAME attempt $ATT: $v (overrun counter $cnt0 -> $cnt1)"
  fi
  settle || say "settle: did not converge in 12 min"
  [ "$v" = PASS ] && return 0 || return 1
}

for C1C2 in C1 C2; do
  run_control "$C1C2" 1; rc=$?
  [ "$rc" = 3 ] && { run_control "$C1C2" 2; rc=$?; [ "$rc" = 3 ] && res "$C1C2: INVALID TWICE (voids O1-O3, K1, RC-11)"; }
  [ "$C1C2" = C1 ] && sleep 30        # at least two cycles apart
done
sleep 30                               # at least two cycles before the block
res "overrun counter at hand-over: $(status captureOverrunCount); reported ms: $(status captureOverrunReportedMs); channel drops: $(status captureChannelDroppedChunks)"
say "controls done"
exit 0
