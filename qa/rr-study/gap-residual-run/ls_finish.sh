#!/bin/bash
# LATE-SUB finish (the Captain: "hibernate when the test is done", 2026-10-29): wait for ls_chain.sh to end, run the analyses, then hibernate THIS PC.
# Run: nohup bash ls_finish.sh > finish.out 2>&1 &      Cancel before it fires: kill its PID (the first line of finish_status.txt), also during the 90 s grace after the log line "HIBERNATING".
S=/d/Projects/claude/_qa-scratch/late-sub
HERE=$(cd "$(dirname "$0")" && pwd)
log() { echo "$(date -u +%FT%TZ) $*" | tee -a $S/finish_status.txt; }
log "finish watcher started pid=$$"
until grep -qE "CHAIN COMPLETE|CHAIN HALT|validity rows FAILED" $S/chain_full.out $S/raw/chain_status.txt 2>/dev/null; do sleep 60; done
log "chain ended: $(tail -1 $S/raw/chain_status.txt | cut -c1-120)"
sleep 30
python -I $HERE/nrtax_analyse.py > $S/nrtax_rerun.out 2>&1 && log "row tags written" || log "nrtax_analyse FAILED (mechanism check will be unavailable)"
grep -q '"ALL_PASS": true' $S/check_off.out 2>/dev/null && { python -I $HERE/ls_analyse.py off > $S/analyse_off.out 2>&1 && log "analysis OFF done" || log "analysis OFF FAILED"; } || log "OFF validity rows not all pass: no analysis"
grep -q '"ALL_PASS": true' $S/check_on.out 2>/dev/null && { python -I $HERE/ls_analyse.py on > $S/analyse_on.out 2>&1 && log "analysis ON done" || log "analysis ON FAILED"; } || log "ON not run or its validity rows not all pass: no ON analysis"
log "HIBERNATING the PC in 90 s (kill this script to cancel)"
sleep 90
shutdown.exe /h
