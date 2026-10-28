#!/bin/bash
# Run on the PC, detached (HK-013/HK-023). Waits for sol's second-night chain (gs_arms.sh) to end, PULLS its records to the PC (the analysis runs here),
# then hibernates sol EXACTLY ONCE, whatever happened (the Captain, 2026-10-28: "be sure that sol hibernates when the test finishes").
# Rules (as tp-one.sh): never before the chain has ended; nothing of the rig is left running when it sleeps; a failing hibernate is logged and leaves
# the machine on; a failed pull is logged but does not stop the hibernate (the records stay on sol's disk); nothing alerts.
#   usage: setsid nohup bash gs_finish.sh > /d/Projects/claude/_qa-scratch/coh-gate-r-f4/finish.out 2>&1 &
K="-i $HOME/.ssh/id_ed25519_sol -o BatchMode=yes -o ConnectTimeout=15"
D=/d/Projects/claude/_qa-scratch/coh-gate-r-f4/sol
LOG=/d/Projects/claude/_qa-scratch/coh-gate-r-f4/finish.log
HIB="sudo -n /usr/sbin/hibernate-ram"
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$LOG"; }
mkdir -p "$D"
log "finish watcher start; waiting for sol's chain to end; hibernate command: $HIB"
while true; do
  st=$(timeout 40 ssh $K claude@sol 'tail -n 3 ~/_rf4/chain.out 2>/dev/null' 2>/dev/null)
  if echo "$st" | grep -qE "chain done|CHAIN HALT"; then break; fi
  sleep 60
done
log "sol chain ended: $(echo "$st" | tail -n 1 | cut -c1-120)"
# a chain that was aborted by hand leaves no 'chain done'; the loop above then waits forever, which is intended (the Captain can kill this watcher)
if timeout 120 scp $K -r claude@sol:~/_rf4/raw "$D/" > /dev/null 2>&1 && timeout 120 scp $K claude@sol:~/_rf4/chain.out "$D/" > /dev/null 2>&1; then
  mkdir -p "$D/scratch"
  timeout 300 scp $K -r claude@sol:~/_qa-scratch/rf4/. "$D/scratch/" > /dev/null 2>&1 && log "pull ok" || log "pull of scratch FAILED (records remain on sol)"
else
  log "pull of raw FAILED (records remain on sol)"
fi
for a in off on orig; do
  r=$(timeout 30 ssh $K claude@sol "sha256sum ~/_qa-scratch/rf4/$a/nc_dump.tsv 2>/dev/null | cut -c1-16")
  l=$(sha256sum "$D/scratch/$a/nc_dump.tsv" 2>/dev/null | cut -c1-16)
  log "verify $a nc_dump sol=$r pc=$l $([ -n "$r" ] && [ "$r" = "$l" ] && echo SAME || echo CHECK)"
done
busy=$(timeout 30 ssh $K claude@sol 'pgrep -f "Replay81.dll|OpenWSFZ.Daemon|wsjtx" | wc -l')
log "rig processes on sol before hibernate: $busy"
log "HIBERNATING sol now (once)"
timeout 60 ssh $K claude@sol "$HIB" > /dev/null 2>&1
log "hibernate command returned rc=$? (sol may already be asleep)"
