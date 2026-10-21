#!/bin/bash
# COH-FALLBACK step 4 replay chain (spec 14-18; Captain's go and hibernate request 2026-10-21): ON arm -> ON-repeat (every 3rd selected cycle) -> U' on the ON dump (frozen cf_uprime.py arm) -> analysis (U'_max 0.042, frozen
# in 2026-10-21-1955-qa-uprime-max-frozen-0042-supersedes-1948.md) -> finisher.
# FAIL CLOSED: an arm whose status line is not 'exit 0 preflight_end_ok=1' stops the chain. Detached; survives the Claude session. Logs to $S/chain4.log; the final state is $S/chain4.state (DONE or STOP).
S=/d/Projects/claude/_qa-scratch/coh-fallback/step4
SW=D:/Projects/claude/_qa-scratch/coh-fallback/step4
R=/d/Projects/claude/OpenWSFZ/worktrees/qa/qa/rr-study/coh-fallback
ART=D:/Projects/claude/OpenWSFZ/worktrees/qa/artefacts
SELSHA=9ce4fbb4b94ae7328bc62697224cc8db918ca03f234d4401830f3501e25f7c28
U_PRIME_MAX=0.042
log() { echo "$(date -u +%FT%TZ) $*" >> $S/chain4.log; }
rm -f $S/chain4.state
log "chain start: ON arm (cohfb 1) on the frozen selection"
bash $R/run_arm4.sh on 1 "$SW/selection.json" $SELSHA
grep -q "^exit 0 preflight_end_ok=1" $S/on_status.txt || { log "FAIL CLOSED: ON arm did not exit 0 with preflight_end_ok=1"; echo STOP > $S/chain4.state; exit 1; }
log "ON arm done"
python -I - > $S/selection_rep4.log 2>&1 <<'E'
import json
j = json.load(open(r"D:\Projects\claude\_qa-scratch\coh-fallback\step4\selection.json"))
r = j["runs"]["20260922_2056"]
r["Y40"] = r["Y40"][::3]
json.dump({"runs": j["runs"], "note": "every 3rd selected cycle (V6 repeat)"}, open(r"D:\Projects\claude\_qa-scratch\coh-fallback\step4\selection_rep4.json", "w"))
print(len(r["Y40"]))
E
log "ON-repeat on $(cat $S/selection_rep4.log) cycles"
bash $R/run_arm4.sh onrep 1 "$SW/selection_rep4.json" -
grep -q "^exit 0 preflight_end_ok=1" $S/onrep_status.txt || { log "FAIL CLOSED: ON-repeat did not exit 0 with preflight_end_ok=1"; echo STOP > $S/chain4.state; exit 1; }
log "ON-repeat done"
python -I $R/cf_uprime.py arm $SW/on/nc_dump.tsv $SW/on/testb.csv $ART 20260922_2056 $SW/dll/libft8.dll $SW/off/uprime_off_classes.json $SW/on/uprime_on.json > $S/on/uprime_on.log 2>&1
[ -f $S/on/uprime_on.json.percycle.csv ] || { log "FAIL CLOSED: U' on the ON dump produced no per-cycle file"; echo STOP > $S/chain4.state; exit 1; }
log "U' (ON) done"
python -I $R/cf_step4_analysis.py $SW $SW/analysis_step4.json $U_PRIME_MAX > $S/analysis_step4.stdout 2>&1
[ -s $S/analysis_step4.json ] || { log "FAIL CLOSED: analysis wrote no result"; echo STOP > $S/chain4.state; exit 1; }
log "analysis done"
echo DONE > $S/chain4.state
