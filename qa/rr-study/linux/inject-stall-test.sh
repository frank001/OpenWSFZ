#!/bin/sh
# TEST ONLY (QA, 2026-10-14): freeze the real wsjtx (SIGSTOP) once, ~75 s into the first scenario of attempt 1, to prove the liveness gate stops the battery, the monitor takes
# its snapshot, and the capped retry reruns the whole sweep. Usage: inject-stall.sh <battery name>   Does nothing a second time (flag file).
NAME=$1
LOG=$HOME/rr-run/$NAME.log
FLAG=$HOME/rr-run/$NAME.injected
SUP=$HOME/rr-run/$NAME
[ -f "$FLAG" ] && exit 0
# wait until the scenario is playing (the supervisor log shows the scenario runner starting)
while ! grep -q "run_scenario.py" "$SUP/supervisor.log" 2>/dev/null; do sleep 3; done
sleep 75
P=$(pgrep -x wsjtx | head -1)
[ -n "$P" ] || exit 1
kill -STOP "$P"
touch "$FLAG"
echo "$(date -u +%FT%TZ) TEST: SIGSTOP sent to wsjtx $P (injected stall)" >> "$LOG"
