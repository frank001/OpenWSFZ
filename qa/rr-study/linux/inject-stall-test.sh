#!/bin/sh
# TEST ONLY (QA, 2026-10-14): freeze the real wsjtx (SIGSTOP) ONCE, <delay> s after the FIRST start of one scenario, to prove the gate stops that scenario, the scenario-level retry
# restarts WSJT-X and reruns only it, and the other scenarios are untouched. Usage: inject-stall.sh <battery name> <marker> <delay s>
#   marker: a string that appears on the supervisor.log line that starts the scenario ('s1b' for the scenario file name, 's6_play' for S6); a second start of the same scenario is ignored.
NAME=$1; MARK=$2; DELAY=${3:-75}
LOG=$HOME/rr-run/$NAME.log
FLAG=$HOME/rr-run/$NAME.injected-$MARK
SUPLOG=$HOME/rr-run/$NAME/supervisor.log
[ -f "$FLAG" ] && exit 0
while ! grep -E "^>>> .*($MARK)" "$SUPLOG" 2>/dev/null | grep -q .; do sleep 3; done
sleep "$DELAY"
P=$(pgrep -x wsjtx | head -1)
[ -n "$P" ] || exit 1
kill -STOP "$P"
touch "$FLAG"
echo "$(date -u +%FT%TZ) TEST: SIGSTOP sent to wsjtx $P ($MARK, +${DELAY}s after the scenario started)" >> "$LOG"
