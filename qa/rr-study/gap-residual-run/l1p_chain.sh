#!/bin/bash
# LATE-SUB L1' chain (freeze record 23a35eb4's file 2026-10-30-0717): pilot (40 cycles, validity only, NO outcome read) -> verdict night OFF -> verdict night ON -> refset OFF (descriptive, cycles 1-1,200) -> analyses.
# Run only after the Captain's go: nohup bash l1p_chain.sh > chain_l1p.out 2>&1 &
S=/d/Projects/claude/_qa-scratch/late-sub
HERE=$(cd "$(dirname "$0")" && pwd)
R4=/d/Projects/claude/_qa-scratch/coh-gate-r-f4
FREEZE=$HERE/../2026-10-30-0717-qa-late-sub-l1p-freeze-record.md
NIGHT=20261022_1949
SEL=$R4/selection_2n.json
[ "$(sha256sum $SEL | cut -d' ' -f1)" = "cf9908a5dcc66ef8966693b2d29ae5bd04fc357d3e1af5058b0e35d7eea6726e" ] || { echo "selection pin FAILED"; exit 9; }
[ "$(sha256sum $R4/u2/orig_classes.json | cut -d' ' -f1)" = "0d83d685db2aee961211b022d5b563c0b5b24a83e51f16c126d0f6cff870ab25" ] || { echo "classes pin FAILED"; exit 9; }
[ "$(sha256sum $R4/selection1200.json | cut -c1-8)" = "328c85d4" ] || { echo "refset selection pin FAILED"; exit 9; }
python -I -c "
import json
s=json.load(open('$SEL')); r=s['runs']['$NIGHT']; r['FULL']=r['FULL'][:40]
json.dump(s,open('$S/selection_2n_pilot40.json','w'))" || exit 9
gate() { grep -q '"ALL_PASS": true' $S/l1p_check_$1.json 2>/dev/null; }
bash $HERE/l1p_arm.sh pilot $NIGHT $S/selection_2n_pilot40.json || exit 9
python -I $HERE/l1p_check.py arm pilot $NIGHT --freeze $FREEZE > $S/l1p_check_pilot.out 2>&1
python -I $HERE/l1p_check.py v8 > $S/l1p_check_v8.out 2>&1
gate pilot && grep -q '"PASS": true' $S/l1p_check_v8.out || { echo "$(date -u +%FT%TZ) PILOT validity rows FAILED: nothing further started" | tee -a $S/raw/l1p_chain_status.txt; exit 8; }
bash $HERE/l1p_arm.sh off $NIGHT $SEL || exit 9
python -I $HERE/l1p_check.py arm off $NIGHT --freeze $FREEZE > $S/l1p_check_off.out 2>&1
gate off || { echo "$(date -u +%FT%TZ) OFF validity rows FAILED: ON and the refset leg are not started" | tee -a $S/raw/l1p_chain_status.txt; exit 8; }
bash $HERE/l1p_arm.sh on $NIGHT $SEL 1 || exit 9
python -I $HERE/l1p_check.py arm on $NIGHT --freeze $FREEZE > $S/l1p_check_on.out 2>&1
bash $HERE/l1p_arm.sh refoff 20260925_2010 $R4/selection1200.json || exit 9
python -I $HERE/l1p_check.py arm refoff 20260925_2010 --freeze $FREEZE > $S/l1p_check_refoff.out 2>&1
for a in off on; do gate $a && python -I $HERE/l1p_analyse.py $a verdict > $S/l1p_analyse_$a.out 2>&1; done
gate refoff && python -I $HERE/l1p_analyse.py refoff refset > $S/l1p_analyse_refoff.out 2>&1
echo "$(date -u +%FT%TZ) CHAIN COMPLETE (pilot + off + on + refoff)" | tee -a $S/raw/l1p_chain_status.txt
