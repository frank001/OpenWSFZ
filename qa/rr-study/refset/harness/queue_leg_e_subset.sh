#!/bin/sh
# SUBSET variant of queue_leg_e.sh (QA, 2026-10-13, Captain go): the 7 blocks of the 70 min WSJT-X keep-up run (4 burst blocks of 20260803_live_run_1713 + the 3 busiest by live rows per cycle). Same PRECHECK, pins and halts; own scratch ~/qa-scratch/leg-e-subset.
# For each replicate: WSJT-X 2.7.0 fresh per block, WSJT-X's own recording of the 33 first-run blocks played in real time (lead 0.0 s),
# decode time from its UDP messages. One summary per replicate (aggregates only). Detached by the caller (nohup/setsid); no cron (HK-023).
# HALTS (no retry loop) on: a busy sol, PRECHECK refusal, WSJT-X executable SHA mismatch, a driver failure, a missing summary.
# Finished blocks are checkpoints (<block>.rep<N>.json), so a re-launch resumes. State: ~/qa-scratch/leg-e/QUEUE-STATUS.txt (append-only).
BASE=$HOME/qa-scratch/leg-e-subset
ST=$BASE/QUEUE-STATUS.txt
HARNESS=$HOME/refset-src/qa/rr-study/refset/harness
CORPUS=$HOME/rr-s6-refset-corpus
LEGB=$HOME/qa-scratch/refset-first/first-run-76aa48cd-standard/B
PIN_WSJTX_SHA=2f968b2fc9dcac6081b8306255159bffd3aef52afb3a9a624d2a0ae6bdaf17b4
PY=$HOME/rr-venv/bin/python
log() { echo "$(date -u +%FT%TZ) $*" >> "$ST"; }
halt() { log "HALT: $*"; sh "$HOME/stop-wsjtx.sh" > /dev/null 2>&1; exit 1; }

mkdir -p "$BASE"
log "queue started (pid $$), replicates: $*"
[ -f "$BASE/block-order.txt" ] || halt "block-order.txt missing"
[ "$(wc -l < "$BASE/block-order.txt")" -eq 7 ] || halt "block-order.txt is not 7 blocks"
if pgrep -f "run_refset|run_leg_e.py|OpenWSFZ.Daemon|aplay" > /dev/null 2>&1; then halt "another job is running on sol (run_refset / run_leg_e / daemon / aplay)"; fi
log "driver SHA-256 $(sha256sum "$HARNESS/run_leg_e.py" | cut -c1-64); summariser $(sha256sum "$HARNESS/summarize_leg_e.py" | cut -c1-64)"
cp "$HOME/.local/share/WSJT-X - rr/WSJT-X - rr.ini" "$BASE/wsjtx-rr.ini.at-queue-start" 2>/dev/null
log "WSJT-X decode settings (ini): $(grep -E '^(NDepth|FT8AP|Mode|SingleDecode|Ftol|RxFreq|Decode52|FastMode)=' "$HOME/.local/share/WSJT-X - rr/WSJT-X - rr.ini" | tr '\n' ' ')"

# PRECHECK (measured appraiser gate): start WSJT-X, decode the Q-prefix canary through its own jt9, refuse otherwise
sh "$HOME/stop-wsjtx.sh" > /dev/null 2>&1; sleep 2
setsid nohup sh "$HOME/start-wsjtx27.sh" rr > /dev/null 2>&1 < /dev/null &
sleep 60
PROBE=$(cd "$HOME/rr-work/qa/rr-study" && "$PY" -s -E -c "
import json, wsjtx_version as w
r = w.probe(); print(json.dumps(r))")
log "PRECHECK probe: $PROBE"
echo "$PROBE" | grep -q '"canary_decoded": true' || halt "PRECHECK refused (canary did not decode)"
echo "$PROBE" | grep -q "$PIN_WSJTX_SHA" || halt "WSJT-X executable SHA-256 differs from the pin $PIN_WSJTX_SHA"
sh "$HOME/stop-wsjtx.sh" > /dev/null 2>&1; sleep 3

BLOCKARGS=""
for b in $(cat "$BASE/block-order.txt"); do BLOCKARGS="$BLOCKARGS --block $b"; done
for REP in "$@"; do
  SCR=$BASE/rep$REP
  mkdir -p "$SCR"
  log "replicate $REP start; scratch $SCR"
  # shellcheck disable=SC2086
  (cd "$HARNESS" && "$PY" -s -E run_leg_e.py --corpus "$CORPUS" $BLOCKARGS --scratch "$SCR" --rep "$REP" --lead 0.0 >> "$BASE/rep$REP.log" 2>&1)
  rc=$?
  [ $rc -eq 0 ] || halt "driver failed rc=$rc in replicate $REP (see $BASE/rep$REP.log); finished blocks are checkpoints"
  n=$(ls "$SCR"/*.rep$REP.json 2>/dev/null | wc -l)
  ex=0; [ -f "$SCR/EXCLUDED.txt" ] && ex=$(grep -c "rep$REP " "$SCR/EXCLUDED.txt")
  [ $((n + ex)) -eq 7 ] || halt "replicate $REP finished with $n block files + $ex excluded, not 7"
  [ "$ex" -gt 1 ] && halt "replicate $REP excluded $ex blocks (more than 1): something systematic is wrong"
  log "replicate $REP: $n blocks done, $ex excluded"
  "$PY" -s -E "$HARNESS/summarize_leg_e.py" --scratch "$SCR" --rep "$REP" --legB "$LEGB" --out "$BASE/SUMMARY-rep$REP.json" > "$BASE/SUMMARY-rep$REP.txt" 2>&1 || halt "summary failed for replicate $REP"
  log "replicate $REP COMPLETE; summary $BASE/SUMMARY-rep$REP.json"
done
sh "$HOME/stop-wsjtx.sh" > /dev/null 2>&1
log "orphan check: $(pgrep -af 'bin/wsjtx|bin/jt9|aplay|Xvfb' | grep -v pgrep | wc -l) wsjtx/jt9/aplay/Xvfb processes left"
log "QUEUE COMPLETE (replicates: $*)"
