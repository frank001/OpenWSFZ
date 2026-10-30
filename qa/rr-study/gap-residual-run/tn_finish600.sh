#!/bin/bash
# Run on the PC, detached (HK-013/HK-023):  nohup bash tn_finish600.sh > finish600.out 2>&1 < /dev/null &
# Waits for sol's Original-arm chain on selected cycles 201-800 (tn_orig600.sh, HK-026 contingency) to end, PULLS its records to the PC, verifies the nc_dump hash,
# then hibernates sol EXACTLY ONCE (the Captain, 2026-10-30: "go. hibernate sol afterwards"). Rules as gs_finish.sh: never before the chain has ended; nothing of the rig
# is left running when it sleeps; a failing hibernate is logged and leaves the machine on; a failed pull is logged but does not stop the hibernate (records stay on sol's disk).
# A CHAIN HALT (the arm itself failed) is logged and sol is NOT hibernated (QA decides; the Captain's order covers a finished run).
K="-i $HOME/.ssh/claude/id_ed25519_sol -o BatchMode=yes -o ConnectTimeout=15"
CHAIN_OUT='~/_l1p/chain600.out'
SOL_RAW='~/_l1p/raw/orig600'
SOL_SCR='~/_qa-scratch/l1p3n/orig600'
D=/d/Projects/claude/_qa-scratch/late-sub/sol3n
LOG=/d/Projects/claude/_qa-scratch/late-sub/finish600.log
HIB="sudo -n /usr/sbin/hibernate-ram"
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$LOG"; }
mkdir -p "$D/raw" "$D/scratch/orig600"
log "finish600 watcher start; waiting for $CHAIN_OUT to end; hibernate command: $HIB"
while true; do
  st=$(timeout 40 ssh $K claude@sol "tail -n 3 $CHAIN_OUT 2>/dev/null" 2>/dev/null)
  if echo "$st" | grep -qE "chain done|CHAIN HALT"; then break; fi
  sleep 60
done
log "sol chain ended: $(echo "$st" | tail -n 1 | cut -c1-120)"
if timeout 300 scp $K -r claude@sol:$SOL_RAW "$D/raw/" > /dev/null 2>&1 && timeout 120 scp $K claude@sol:$CHAIN_OUT "$D/" > /dev/null 2>&1; then
  timeout 600 scp $K -r claude@sol:$SOL_SCR/. "$D/scratch/orig600/" > /dev/null 2>&1 && log "pull ok" || log "pull of scratch FAILED (records remain on sol)"
else
  log "pull of raw FAILED (records remain on sol)"
fi
r=$(timeout 30 ssh $K claude@sol "sha256sum $SOL_SCR/nc_dump.tsv 2>/dev/null | cut -c1-16")
l=$(sha256sum "$D/scratch/orig600/nc_dump.tsv" 2>/dev/null | cut -c1-16)
log "verify orig600 nc_dump sol=$r pc=$l $([ -n "$r" ] && [ "$r" = "$l" ] && echo SAME || echo CHECK)"
if echo "$st" | grep -q "CHAIN HALT"; then
  log "CHAIN HALT: sol NOT hibernated (the arm failed); QA to decide. Watcher exits."
  exit 0
fi
busy=$(timeout 30 ssh $K claude@sol 'pgrep -f "Replay81.dll|OpenWSFZ.Daemon|wsjtx" | grep -v $$ | wc -l')
log "rig-process count on sol before hibernate (may include the pgrep's own shell): $busy"
log "HIBERNATING sol now (once)"
timeout 60 ssh $K claude@sol "$HIB" > /dev/null 2>&1
log "hibernate command returned rc=$? (sol may already be asleep)"
log "finish600 watcher done"
