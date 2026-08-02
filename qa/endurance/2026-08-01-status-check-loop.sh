#!/usr/bin/env bash
# qa/endurance/2026-08-01-status-check-loop.sh
#
# True background loop for the standing 30-min status check on the multi-day
# 20m live run (8080 vs 8081 vs WSJT-X). Replaces the in-session CronCreate
# cadence, which the Captain found unreliable while AFK (2026-08-01/02): its
# "fire while REPL idle" behavior did not deliver a report on a clock without
# some other session activity to piggyback on. This script is a real,
# independent bash process, no different in kind from the supervisor scripts
# already running for the daemons themselves — it runs status-check.sh, then
# sleeps 30 minutes, forever, regardless of whether anyone is interacting with
# the QA session.
#
# Usage: run in background, watched via the Monitor tool so each cycle's
# output surfaces as a notification for QA judgment (one-sided-anomaly check
# per qa/cycleframer-alignment-replay/2026-08-01-2001-...-handoff.md §2-3).

set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1

INTERVAL_SECONDS=1800  # 30 minutes

while true; do
  echo "=== Loop fire: $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  bash qa/endurance/status-check.sh
  echo "=== Next fire in ${INTERVAL_SECONDS}s ==="
  sleep "$INTERVAL_SECONDS"
done
