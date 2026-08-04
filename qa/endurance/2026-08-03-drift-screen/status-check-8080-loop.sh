#!/usr/bin/env bash
# qa/endurance/2026-08-03-drift-screen/status-check-8080-loop.sh
#
# 30-minute standing status check for the 24 h 20m drift-screen run armed
# 2026-08-03 17:13:26Z. Successor to qa/endurance/2026-08-01-status-check-loop.sh,
# which served the 8080-vs-8081 run.
#
# Per HK-023: CronCreate/Monitor are NOT durable for anything that must survive
# a session ending. This is a real detached bash process, launched with
# nohup ... & disown and PID-verified via Win32_Process, exactly as the daemon
# supervisors are. It ends only on an explicit kill.
#
# Launch:
#   cd /d/Projects/claude/OpenWSFZ
#   nohup bash qa/endurance/2026-08-03-drift-screen/status-check-8080-loop.sh \
#         > qa/endurance/2026-08-03-drift-screen/status-check-loop.log 2>&1 < /dev/null &
#   disown
#
# Stop:
#   kill <PID>          # the PID of THIS script, not the daemon
#
# NOTE: this loop reports; it never judges. The drift screen's verdict comes from
# drift_screen.py at closeout and from nowhere else. No row of the pre-registered
# rule may be inferred from anything printed here.

set -uo pipefail
cd "$(dirname "$0")/../../.." || exit 1

INTERVAL_SECONDS="${INTERVAL_SECONDS:-1800}"  # 30 minutes
CHECK="qa/endurance/2026-08-03-drift-screen/status-check-8080.sh"

echo "=== Loop ARMED: $(date -u +%Y-%m-%dT%H:%M:%SZ) | pid=$$ | interval=${INTERVAL_SECONDS}s ==="

while true; do
  echo "=== Loop fire: $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  bash "$CHECK"
  echo "=== Next fire in ${INTERVAL_SECONDS}s ==="
  sleep "$INTERVAL_SECONDS"
done
