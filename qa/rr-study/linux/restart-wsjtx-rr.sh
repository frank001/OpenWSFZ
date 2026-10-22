#!/bin/sh
# (Re)start WSJT-X 2.7.0, rig `rr`, headless, on sol (QA, 2026-10-14). Used at the start of every battery and by run_study.py for a scenario retry (--wsjtx-restart-cmd).
# A frozen (SIGSTOP) process is continued first, because it cannot act on SIGTERM; what is left after the normal stop is killed. Exit 0 only when the real `wsjtx` binary is
# running AND has written a save WAV within the last 45 s; 1 otherwise. `ulimit -c unlimited` is set in start-wsjtx27.sh (a crash leaves a core in the working directory).
SAVE="$HOME/.local/share/WSJT-X - rr/save"
pkill -CONT -x wsjtx 2>/dev/null; pkill -CONT -x jt9 2>/dev/null; sleep 1
sh "$HOME/stop-wsjtx.sh" > /dev/null 2>&1
i=0; while pgrep -x wsjtx > /dev/null 2>&1 && [ $i -lt 15 ]; do sleep 1; i=$((i + 1)); done
pkill -9 -x wsjtx 2>/dev/null; pkill -9 -x jt9 2>/dev/null; pkill -9 -x Xvfb 2>/dev/null
sleep 3
cd "$HOME"
setsid nohup sh "$HOME/start-wsjtx27.sh" rr > /dev/null 2>&1 < /dev/null &
# wait for the process, then for a fresh WAV (WSJT-X writes one per 15 s cycle once it listens)
i=0
while [ $i -lt 120 ]; do
  P=$(pgrep -x wsjtx | head -1)
  if [ -n "$P" ]; then
    NEW=$(find "$SAVE" -name '*.wav' -newermt "30 seconds ago" 2>/dev/null | head -1)
    [ -n "$NEW" ] && { echo "wsjtx up: pid $P, fresh WAV $(basename "$NEW")"; exit 0; }
  fi
  sleep 3; i=$((i + 3))
done
echo "wsjtx did not produce a fresh save WAV within 120 s (pid: $(pgrep -x wsjtx | head -1))"
exit 1
