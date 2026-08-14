#!/usr/bin/env bash
# Unattended runner for P1a (decode-depth invocation robustness), CHAINED to
# run only after the P2/P3 runner has finished.
#
# Chained rather than concurrent on purpose: P2/P3 hold 8 decoder processes and
# P1a's per-file leg holds 8 jt9 threads.  On 16 cores that is oversubscription,
# and while none of P1a's gated metrics are timing-dependent, contention would
# distort the wall-clock figures both runs report.
#
# Same discipline as run_p23_unattended.sh: HK-023 detached (not Monitor-owned),
# HK-013 retry with cooldown capped at 5, HK-019 clean exit with nothing left
# behind.  P1a caches each completed leg, so a retry resumes.
#
# Launch:  nohup bash run_p1a_unattended.sh >/dev/null 2>&1 & disown

set -u

REPO="D:/Projects/claude/OpenWSFZ"
QA="$REPO/qa/cycleframer-alignment-replay"
SCRATCH="C:/Temp/openwsfz_p1a_scratch"
OUT="$QA/p1a_result.json"
MAX_RETRIES=5
COOLDOWN=60
WORKERS=8
MAX_WAIT_MIN=300        # give up waiting for P2/P3 after 5 h and run anyway

mkdir -p "$SCRATCH"
cd "$REPO" || exit 1

# Log name pinned once at launch -- HK-013 addendum, this run can cross 00:00Z.
LOG="$QA/p1a_run_$(date -u +%Y%m%dT%H%M%SZ).log"
log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" >> "$LOG"; }

log "=== P1a runner starting (PID $$), waiting for P2/P3 to finish ==="

waited=0
while [ ! -f "$QA/P23_RUN_SUMMARY.md" ]; do
  sleep 60
  waited=$((waited + 1))
  if [ "$waited" -ge "$MAX_WAIT_MIN" ]; then
    log "waited ${waited} min for P2/P3 summary and it never appeared -- proceeding anyway"
    break
  fi
  if [ $((waited % 15)) -eq 0 ]; then
    log "still waiting for P2/P3 (${waited} min)"
  fi
done
log "proceeding after ${waited} min wait"

attempt=1
rc=1
while [ "$attempt" -le "$MAX_RETRIES" ]; do
  if [ -f "$OUT" ]; then
    log "P1a: result already present -- nothing to do"
    rc=0
    break
  fi
  log "P1a: attempt $attempt/$MAX_RETRIES starting (legs: perfile, batched@150)"
  python "$QA/p1a_invocation_robustness.py" \
      --workers "$WORKERS" --scratch "$SCRATCH" --out "$OUT" >> "$LOG" 2>&1
  rc=$?
  if [ "$rc" -eq 0 ] && [ -f "$OUT" ]; then
    log "P1a: COMPLETED on attempt $attempt"
    break
  fi
  log "P1a: attempt $attempt FAILED rc=$rc; cooling down ${COOLDOWN}s then resuming from leg cache"
  attempt=$((attempt + 1))
  sleep "$COOLDOWN"
done

[ "$rc" -eq 0 ] || log "P1a: GAVE UP after $MAX_RETRIES attempts"

{
  echo "# P1a unattended run summary"
  echo
  echo "HEAD \`$(git -C "$REPO" rev-parse --short HEAD)\`; log \`$(basename "$LOG")\`."
  echo
  if [ -f "$OUT" ]; then
    python - "$OUT" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
print("- **final row**: `%s`" % d.get("final_row"))
print("- stage 1 (validity): `%s`  |  stage 2 (substantive): `%s`"
      % (d.get("stage1_validity"), d.get("stage2_substantive")))
print("- `A_perfile` = %.3f pp, `A_batched` = %.3f pp, **dA = %.3f pp**, SE(dA) = %.3f"
      % (d["A_perfile"], d["A_batched"], d["dA"], d["SE_dA"]))
if d.get("row0"):
    print("- ROW 0 fired: `%s` -- %s" % (d["row0"], d.get("row0_reason")))
print()
print("NOT BLIND: %s" % d.get("NOT_BLIND"))
PY
  else
    echo "- **DID NOT COMPLETE** -- retry budget exhausted; see the log."
  fi
  echo
  echo "Generated $(date -u +%Y-%m-%dT%H:%M:%SZ) by \`run_p1a_unattended.sh\`."
} > "$QA/P1A_RUN_SUMMARY.md"

log "=== P1a runner exiting (rc=$rc), nothing left behind ==="
exit 0
