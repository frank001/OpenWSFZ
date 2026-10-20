#!/bin/bash
# Q-GATE-2: Amendment 2 order. pilot2 (already started) -> pool -> [pilot4 -> pool] -> main run unless STOP. Every step logged to chain.log.
F=/d/Projects/claude/_qa-scratch/q-gate-2
PY=/d/Projects/claude/_qa-scratch/rr-main/tree/qa/rr-study/.venv/Scripts/python.exe
R=/d/Projects/claude/OpenWSFZ/worktrees/qa/qa/rr-study/coh-gain
log() { echo "$(date -u +%FT%TZ) $*" >> $F/chain.log; }
until [ -f $F/pilot2/run_info.json ]; do sleep 10; done
log "pilot2 done"
$PY -I $R/qg2_rows.py pilotpool --runs "$F/frozen/rows_pilot.json::$F/pilot_full" "$F/frozen/rows_pilot2.json::$F/pilot2" --out $F/pilot_pool.json > $F/pilot_pool.stdout 2>&1
RES=$($PY -I -c "import json;j=json.load(open(r'$F/pilot_pool.json'));print(j['pilot_pool_result'], j['control_n'], j['matches'])")
log "pool after pilot2: $RES"
if ! [[ "$RES" =~ ^(PASS|STOP)\ [0-9]+\ [0-9]+$ ]]; then log "FAIL CLOSED: pool result empty or unparsable [$RES] - main run NOT started"; echo STOP > $F/chain.state; exit 1; fi
if [[ "$RES" == STOP* ]]; then
  N=$(echo $RES | cut -d' ' -f2); M=$(echo $RES | cut -d' ' -f3)
  if [ "$N" -lt 200 ] && [ "$M" -le $((N/100)) ]; then
    log "n < 200 and no excess matches: running pilot4"
    $PY -I $R/qg2.py run --rows $F/frozen/rows_pilot4.json --out $F/pilot4 --workers 4 --fresh > $F/pilot4.log 2>&1
    $PY -I $R/qg2_rows.py pilotpool --runs "$F/frozen/rows_pilot.json::$F/pilot_full" "$F/frozen/rows_pilot2.json::$F/pilot2" "$F/frozen/rows_pilot4.json::$F/pilot4" --out $F/pilot_pool.json > $F/pilot_pool.stdout 2>&1
    RES=$($PY -I -c "import json;j=json.load(open(r'$F/pilot_pool.json'));print(j['pilot_pool_result'], j['control_n'], j['matches'])")
    log "pool after pilot4: $RES"
    if ! [[ "$RES" =~ ^(PASS|STOP)\ [0-9]+\ [0-9]+$ ]]; then log "FAIL CLOSED: pool result empty or unparsable [$RES]"; echo STOP > $F/chain.state; exit 1; fi
  fi
fi
if [[ "$RES" == STOP* ]]; then log "STOP - main run NOT started"; echo STOP > $F/chain.state; exit 0; fi
log "pilot control PASS -> main run"
$PY -I $R/qg2.py run --rows $F/frozen/rows_main.json --out $F/main --workers 4 --fresh > $F/main.log 2>&1
log "main run done"
$PY -I $R/qg2_rows.py main --rows $F/frozen/rows_main.json --run $F/main --pool-json $F/pilot_pool.json --out $F/main_analysis.json > $F/main_analysis.stdout 2>&1
log "main analysis done"
echo DONE > $F/chain.state
