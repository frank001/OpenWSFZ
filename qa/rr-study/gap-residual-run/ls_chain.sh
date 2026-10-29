#!/bin/bash
# LATE-SUB full chain: OFF (verdict configuration), V-rows gate, then ON (descriptive). One process each, 1,200 cycles from cycle 1.  Run: nohup bash ls_chain.sh > chain.out 2>&1 &
S=/d/Projects/claude/_qa-scratch/late-sub
HERE=$(cd "$(dirname "$0")" && pwd)
SEL=/d/Projects/claude/_qa-scratch/coh-gate-r-f4/selection1200.json
[ "$(sha256sum $SEL | cut -c1-8)" = "328c85d4" ] || { echo "selection pin FAILED"; exit 9; }
bash $HERE/ls_arm.sh off $SEL || exit 9
python -I $HERE/ls_check.py off main > $S/check_off.out 2>&1
grep -q '"ALL_PASS": true' $S/check_off.out || { echo "$(date -u +%FT%TZ) OFF validity rows FAILED: the ON arm is not started" | tee -a $S/raw/chain_status.txt; exit 8; }
bash $HERE/ls_arm.sh on $SEL 1 || exit 9
python -I $HERE/ls_check.py on on > $S/check_on.out 2>&1
echo "$(date -u +%FT%TZ) CHAIN COMPLETE (off + on)" | tee -a $S/raw/chain_status.txt
