#!/usr/bin/env bash
# Unattended runner for P2 (PCM scale) and P3 (sub-lattice shift union).
# Spec section 4: HK-023 (detached, not Monitor-owned), HK-013 (retry with
# cooldown, cap 5, every event logged), HK-019 (clean teardown, no lingering
# supervisor process).
#
# Self-supervising by design: the retry loop lives INSIDE this script rather
# than in a separate watchdog, so there is no second process to orphan.  Both
# harnesses checkpoint per partition to the scratch dir and skip completed
# partitions on restart, so a retry resumes rather than restarting from zero.
#
# Residual risk, stated honestly: if THIS script dies (not its child), nothing
# restarts it.  It is a bash loop with no state, so that is unlikely, and the
# run is resumable by hand from the same scratch dir.
#
# Launch with:  nohup bash run_p23_unattended.sh >/dev/null 2>&1 & disown
# then verify the PID via Win32_Process before trusting it.

set -u

REPO="D:/Projects/claude/OpenWSFZ"
QA="$REPO/qa/cycleframer-alignment-replay"
SCRATCH="C:/Temp/openwsfz_p23_scratch"
MAX_RETRIES=5
COOLDOWN=60
WORKERS=8

mkdir -p "$SCRATCH"
cd "$REPO" || exit 1

# HK-013 addendum: the reference supervisor mis-handles UTC-midnight log
# rotation and killed two healthy instances.  This run can cross 00:00Z, so the
# log name is pinned ONCE at launch and never re-derived per iteration.
LOG="$QA/p23_run_$(date -u +%Y%m%dT%H%M%SZ).log"
ln -sf "$LOG" "$QA/p23_run_latest.log" 2>/dev/null || true

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" >> "$LOG"; }

run_arm() {
  local name="$1" script="$2" out="$3"
  if [ -f "$out" ]; then
    log "$name: result already present at $out -- skipping"
    return 0
  fi
  local attempt=1
  while [ "$attempt" -le "$MAX_RETRIES" ]; do
    log "$name: attempt $attempt/$MAX_RETRIES starting"
    python "$QA/$script" --workers "$WORKERS" --scratch "$SCRATCH" --out "$out" >> "$LOG" 2>&1
    local rc=$?
    if [ "$rc" -eq 0 ] && [ -f "$out" ]; then
      log "$name: COMPLETED on attempt $attempt"
      return 0
    fi
    log "$name: attempt $attempt FAILED rc=$rc; cooling down ${COOLDOWN}s then resuming from checkpoints"
    attempt=$((attempt + 1))
    sleep "$COOLDOWN"
  done
  log "$name: GAVE UP after $MAX_RETRIES attempts -- retry budget exhausted"
  return 1
}

log "=== unattended P2/P3 run starting ==="
log "repo HEAD: $(git -C "$REPO" rev-parse --short HEAD)"
log "scratch: $SCRATCH  workers: $WORKERS"
log "runner PID: $$"

run_arm "P2" "p2_pcm_scale.py"   "$QA/p2_result.json"
P2RC=$?
run_arm "P3" "p3_shift_union.py" "$QA/p3_result.json"
P3RC=$?

{
  echo "# P2/P3 unattended run summary"
  echo
  echo "Started from HEAD \`$(git -C "$REPO" rev-parse --short HEAD)\`; log \`$(basename "$LOG")\`."
  echo
  for arm in P2 P3; do
    f="$QA/$(echo "$arm" | tr 'A-Z' 'a-z')_result.json"
    if [ -f "$f" ]; then
      row=$(python -c "import json,sys;print(json.load(open(sys.argv[1]))['final_row'])" "$f" 2>/dev/null)
      echo "- **$arm** -> \`${row:-UNKNOWN}\`  (\`$(basename "$f")\`)"
    else
      echo "- **$arm** -> **DID NOT COMPLETE** (retry budget exhausted; see the log)"
    fi
  done
  echo
  echo "Generated $(date -u +%Y-%m-%dT%H:%M:%SZ) by \`run_p23_unattended.sh\`."
} > "$QA/P23_RUN_SUMMARY.md"

log "=== run finished (P2 rc=$P2RC, P3 rc=$P3RC) -- runner exiting, no supervisor left behind ==="
exit 0
