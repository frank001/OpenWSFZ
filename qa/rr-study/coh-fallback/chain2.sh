#!/bin/bash
# COH-FALLBACK step 3 replay chain (spec sections 8-11): V-U0 FIRST (Stage 2 build's own OFF arm vs main), then ON, then the ON-repeat on every 3rd selected cycle.
# FAIL CLOSED: an empty or unparsable gate result stops the chain; a V-U0 FAIL stops it BEFORE any ON decode (U_max must be re-frozen in a dated note first).
S=/d/Projects/claude/_qa-scratch/coh-fallback
SW=D:/Projects/claude/_qa-scratch/coh-fallback
PY=/d/Projects/claude/_qa-scratch/rr-main/tree/qa/rr-study/.venv/Scripts/python.exe
R=D:/Projects/claude/OpenWSFZ/worktrees/qa/qa/rr-study/coh-fallback
log() { echo "$(date -u +%FT%TZ) $*" >> $S/chain2.log; }
rm -f $S/chain2.state
log "chain start: OFF arm (Stage 2 build, cohfb 0)"
bash $S/run_arm.sh off2 0 "$SW/frozen/selection.json"
grep -q "^exit 0" $S/off2_status.txt || { log "FAIL CLOSED: OFF arm did not exit 0"; echo STOP > $S/chain2.state; exit 1; }
log "OFF arm done"
$PY -I $R/cf_vu0.py "$SW/off_full/outcomes_OFF.csv" "$SW/off2/outcomes.csv" "$SW/vu0.json" > $S/vu0.stdout 2>&1
RES=$($PY -I -c "import json;print(json.load(open(r'$SW/vu0.json'))['V-U0'])" 2>/dev/null)
log "V-U0: [$RES]"
if [[ "$RES" != "PASS" && "$RES" != "FAIL" ]]; then log "FAIL CLOSED: V-U0 result empty or unparsable"; echo STOP > $S/chain2.state; exit 1; fi
if [[ "$RES" == "FAIL" ]]; then log "V-U0 FAIL - ON arm NOT started; U_max must be re-frozen from the Stage 2 OFF arm"; echo HALT_VU0 > $S/chain2.state; exit 0; fi
log "V-U0 PASS - U_max 0.078 stands; starting the ON arm"
bash $S/run_arm.sh on 1 "$SW/frozen/selection.json"
grep -q "^exit 0" $S/on_status.txt || { log "FAIL CLOSED: ON arm did not exit 0"; echo STOP > $S/chain2.state; exit 1; }
log "ON arm done"
$PY -I - > $S/selection_rep.log 2>&1 <<'E'
import json
j = json.load(open(r"D:\Projects\claude\_qa-scratch\coh-fallback\frozen\selection.json"))
r = j["runs"]["20261009_1752"]
r["Y40"] = r["Y40"][::3]
json.dump({"runs": j["runs"], "note": "every 3rd selected cycle (V6 repeat, spec A1.7)"}, open(r"D:\Projects\claude\_qa-scratch\coh-fallback\selection_rep.json", "w"))
print(len(r["Y40"]))
E
log "ON-repeat on $(cat $S/selection_rep.log) cycles"
bash $S/run_arm.sh onrep 1 "$SW/selection_rep.json"
grep -q "^exit 0" $S/onrep_status.txt || { log "FAIL CLOSED: ON-repeat did not exit 0"; echo STOP > $S/chain2.state; exit 1; }
log "ON-repeat done"
echo DONE > $S/chain2.state
