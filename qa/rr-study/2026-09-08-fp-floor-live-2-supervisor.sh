#!/bin/bash
# HK-013 supervisor for FP-FLOOR-LIVE-2's up-to-24h capture run.
# kill+log+cooldown+restart, cap 5 retries. Watches process liveness AND that the
# daemon is actually reporting decodingEnabled/captureActive=true on 14.074 -- a
# process that's alive but stuck (wrong device, wrong band, decoding off) is exactly
# as useless to this corpus as a dead one, and the config-restart defect found tonight
# is precisely the kind of "alive but wrong" failure a bare process check would miss.

DAEMON_DIR="D:/Projects/claude/OpenWSFZ/worktrees/qa/src/OpenWSFZ.Daemon/bin/Release/net10.0"
STATUS_URL="http://127.0.0.1:8080/api/v1/status"
LOG="D:/Projects/claude/OpenWSFZ/artefacts/20260908_live_run_1827-fp-floor-live-2/supervisor.log"
MAX_RETRIES=5
COOLDOWN_S=15
retries=0

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $1" >> "$LOG"; }

log "supervisor started, pid $$"

while true; do
  sleep 30
  status=$(curl -s --max-time 5 "$STATUS_URL")
  healthy=1
  [ -z "$status" ] && healthy=0
  echo "$status" | grep -q '"captureActive":true' || healthy=0
  echo "$status" | grep -q '"decodingEnabled":true' || healthy=0
  echo "$status" | grep -q '"dialFrequencyMHz":14.074' || healthy=0

  if [ "$healthy" -eq 0 ]; then
    retries=$((retries + 1))
    log "UNHEALTHY (attempt $retries/$MAX_RETRIES): status='$status'"
    if [ "$retries" -gt "$MAX_RETRIES" ]; then
      log "RETRY CAP EXCEEDED -- giving up, human intervention required"
      exit 1
    fi
    # kill any daemon process cleanly, then cold-restart (config on disk is already correct)
    powershell -NoProfile -Command "Get-Process -Name OpenWSFZ.Daemon -ErrorAction SilentlyContinue | Stop-Process -Force" >> "$LOG" 2>&1
    sleep "$COOLDOWN_S"
    (cd "$DAEMON_DIR" && nohup ./OpenWSFZ.Daemon.exe --background --port 8080 >> "$LOG" 2>&1 &)
    log "cold-restarted daemon after unhealthy check, cooldown ${COOLDOWN_S}s applied"
    sleep "$COOLDOWN_S"
  else
    retries=0
  fi
done
