#!/bin/sh
# f1-controls.sh <daemon.stdout.log> <port> <out-dir> <G seconds>   (QA 2026-10-17; Architect spec F1 + amendment 1)
# Controls of the F1' capture-buffer arm, on the SAME daemon instance that then plays the block.
#   CT1 (treatment works)   kill -STOP the arecord child 1.5 s, then -CONT.  PASS = CaptureOverrunCount unchanged AND the next window's framer `wanted` < +0.2 s (2400 samples).
#                           (Today, with the 0.2 s dsnoop ring, a 2.0 s stop lost audio: wanted 24002.)  A FAIL is final: the rows are then labelled "treatment not demonstrated".
#   CT2 (instrument alive)  kill -STOP the arecord child G+1.0 s, then -CONT.  PASS = the counter rises by >= 1 within 5 s of -CONT.  A FAIL voids F-1 and RC-13.
# "next window" = the SECOND `Window emitted` line after -CONT, as in capture-loss-controls.sh.  A control is INVALID if the capture watchdog restarted capture
# (watchdogRestartCount rose, or a "Capture ended unexpectedly" line): repeated ONCE; a second invalid attempt counts as a failure.
# After each control: wait until two consecutive windows have |wanted| <= 600 samples, and after CT2 at least 10 further cycles (150 s) before the first play.
# Aggregates and arecord's own text only (HK-037).  Never exits non-zero: the result is in controls_result.txt.
LOG=${1:?daemon stdout log}; PORT=${2:-8080}; OUT=${3:?out dir}; G=${4:?granted buffer seconds}
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

wait_new_window() {
  i=0; while [ "$(nwin)" -le "$1" ] && [ "$i" -lt "$2" ]; do sleep 1; i=$((i + 1)); done
  [ "$(nwin)" -gt "$1" ]
}

settle() {   # two consecutive windows with |wanted| <= 600; max 12 min
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
  if [ "$NAME" = "CT1" ]; then STOPS=1.5; else STOPS=$("$PY" -c "print(round($G + 1.0, 3))"); fi
  say "$NAME attempt $ATT: begin (stop $STOPS s)"
  dp=$(daemon_pid); [ -n "$dp" ] || { res "$NAME attempt $ATT: NO DAEMON"; return 2; }
  ap=$(arecord_pid "$dp"); [ -n "$ap" ] || { res "$NAME attempt $ATT: NO ARECORD CHILD of $dp"; return 2; }
  n0=$(nwin); wait_new_window "$n0" 40 || { res "$NAME attempt $ATT: no window emitted in 40 s"; return 2; }
  sleep 3
  cnt0=$(status captureOverrunCount); wd0=$(status watchdogRestartCount); L0=$(wc -l < "$LOG"); nw0=$(nwin)
  t0=$(date -u +%FT%T.%3NZ)
  kill -STOP "$ap"; sleep "$STOPS"; kill -CONT "$ap"
  t1=$(date -u +%FT%T.%3NZ)
  say "$NAME attempt $ATT: STOP at $t0, CONT at $t1; counter before=$cnt0 watchdog before=$wd0"
  cnt1=$cnt0; i=0
  while [ "$i" -lt 10 ]; do
    sleep 0.5; i=$((i + 1)); c=$(status captureOverrunCount)
    [ -n "$c" ] && cnt1=$c
    [ "$NAME" = "CT2" ] && [ -n "$cnt0" ] && [ -n "$cnt1" ] && [ "$cnt1" -gt "$cnt0" ] && break
  done
  i=0; while [ "$(( $(nwin) - nw0 ))" -lt 2 ] && [ "$i" -lt 60 ]; do sleep 1; i=$((i + 1)); done
  W1=$(winlines_after "$L0" | sed -n 1p); W2=$(winlines_after "$L0" | sed -n 2p)
  cnt1=$(status captureOverrunCount); wd1=$(status watchdogRestartCount)
  OV=$(lines_after "$L0" | grep -i 'arecord overrun' | cut -c1-300)
  UNEXP=$(lines_after "$L0" | grep -c 'Capture ended unexpectedly')
  { echo "---- $NAME attempt $ATT: verbatim overrun line(s) ----"; echo "$OV"; echo "---- window lines after the stop ----"; echo "$W1"; echo "$W2"; } >> "$C"
  w2=$(wanted_of "$W2")
  say "$NAME attempt $ATT: counter $cnt0 -> $cnt1; watchdog $wd0 -> $wd1; unexpected-end lines $UNEXP; next-window wanted=$w2"
  if [ "$wd1" != "$wd0" ] || [ "$UNEXP" != "0" ]; then res "$NAME attempt $ATT: INVALID (capture restarted: watchdog $wd0 -> $wd1, unexpected-end lines $UNEXP)"; settle || say "settle: did not converge"; return 3; fi
  if [ "$NAME" = "CT1" ]; then
    same=0; [ -n "$cnt0" ] && [ "$cnt1" = "$cnt0" ] && same=1
    small=0; [ -n "$w2" ] && [ "$w2" -lt 2400 ] && small=1
    if [ "$same" = 1 ] && [ "$small" = 1 ]; then v=PASS; else v=FAIL; fi
    res "$NAME attempt $ATT: $v (overrun counter $cnt0 -> $cnt1, next-window wanted ${w2:-none} samples, bar < 2400)"
  else
    rose=0; [ -n "$cnt0" ] && [ -n "$cnt1" ] && [ "$cnt1" -gt "$cnt0" ] && rose=1
    if [ "$rose" = 1 ]; then v=PASS; else v=FAIL; fi
    res "$NAME attempt $ATT: $v (overrun counter $cnt0 -> $cnt1; stop $STOPS s; next-window wanted ${w2:-none})"
  fi
  settle || say "settle: did not converge in 12 min"
  [ "$v" = PASS ] && return 0 || return 1
}

CTS="CT1 CT2"; [ -n "${ONLY_CT2:-}" ] && CTS="CT2"      # D-b' (no wrapper): CT1 would lose audio by design (the buffer is ~0.5 s); only the instrument-alive control runs
for CT in $CTS; do
  run_control "$CT" 1; rc=$?
  [ "$rc" = 3 ] && { run_control "$CT" 2; rc=$?; [ "$rc" = 3 ] && res "$CT: INVALID TWICE (counts as failed)"; }
  [ "$CT" = CT1 ] && sleep 30
done
say "quiet gap: 10 cycles"; sleep 150
res "counters at hand-over: overruns $(status captureOverrunCount); channel drops $(status captureChannelDroppedChunks); watchdog restarts $(status watchdogRestartCount)"
say "controls done"
exit 0
