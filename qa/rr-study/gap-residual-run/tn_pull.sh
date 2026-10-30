#!/bin/bash
# Run on the PC, detached (HK-013/HK-023):  nohup bash tn_pull.sh > pull3n.out 2>&1 & disown
# Waits for sol's L1' third-night chain (tn_arms.sh) to end, then PULLS its records to the PC (the analysis runs here). It does NOT hibernate sol:
# hibernation was not asked for this run (the R-F4 watcher gs_finish.sh did it on the Captain's word; add that only if he says so again).
# Pull checks: nc_dump hashes compared sol vs PC for every arm, like gs_finish.sh. A failed pull is logged and leaves the records on sol.
K="-i $HOME/.ssh/id_ed25519_sol -o BatchMode=yes -o ConnectTimeout=15"
CHAIN_OUT=${CHAIN_OUT:-'~/_l1p/chain.out'}
SOL_RAW=${SOL_RAW:-'~/_l1p/raw'}
SOL_SCR=${SOL_SCR:-'~/_qa-scratch/l1p3n'}
D=/d/Projects/claude/_qa-scratch/late-sub/sol3n
LOG=/d/Projects/claude/_qa-scratch/late-sub/pull3n.log
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$LOG"; }
mkdir -p "$D"
log "pull watcher start; waiting for the chain at $CHAIN_OUT to end"
while true; do
  st=$(timeout 40 ssh $K claude@sol "tail -n 3 $CHAIN_OUT 2>/dev/null" 2>/dev/null)
  if echo "$st" | grep -qE "chain done|CHAIN HALT"; then break; fi
  sleep 60
done
log "sol chain ended: $(echo "$st" | tail -n 1 | cut -c1-120)"
if timeout 300 scp $K -r claude@sol:$SOL_RAW "$D/" > /dev/null 2>&1 && timeout 120 scp $K claude@sol:$CHAIN_OUT "$D/" > /dev/null 2>&1; then
  mkdir -p "$D/scratch"
  timeout 600 scp $K -r claude@sol:$SOL_SCR/. "$D/scratch/" > /dev/null 2>&1 && log "pull ok" || log "pull of scratch FAILED (records remain on sol)"
else
  log "pull of raw FAILED (records remain on sol)"
fi
for a in off on orig; do
  r=$(timeout 30 ssh $K claude@sol "sha256sum $SOL_SCR/$a/nc_dump.tsv 2>/dev/null | cut -c1-16")
  l=$(sha256sum "$D/scratch/$a/nc_dump.tsv" 2>/dev/null | cut -c1-16)
  log "verify $a nc_dump sol=$r pc=$l $([ -n "$r" ] && [ "$r" = "$l" ] && echo SAME || echo CHECK)"
done
rig=$(timeout 30 ssh $K claude@sol 'pgrep -f "Replay81.dll|OpenWSFZ.Daemon|wsjtx" | wc -l')
log "rig processes on sol after the chain: $rig; sol left on (no hibernate, not asked)"
log "pull watcher done"
