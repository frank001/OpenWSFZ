#!/bin/bash
# Run on the PC, detached (HK-013/HK-023). Waits for sol's second-night chain to end, PULLS its records to the PC (the analysis runs here), then
# hibernates sol EXACTLY ONCE (the Captain, 2026-10-28: "be sure that sol hibernates when the test finishes") -- EXCEPT when V-2N-AB failed:
# the Captain, 2026-10-28: "if candidates were abandoned, sol should not hibernate but do the re-run". In that case (HOLD_ON_ABANDON=1, the default
# for the first chain) the watcher pulls what exists, logs "ABANDONMENT: sol NOT hibernated; re-run needed", and EXITS without hibernating.
# QA then re-runs and starts this watcher again for the re-run chain with HOLD_ON_ABANDON=0 (hibernate once, whatever happened).
# Rules (as tp-one.sh): never before the chain has ended; nothing of the rig is left running when it sleeps; a failing hibernate is logged and leaves
# the machine on; a failed pull is logged but does not stop the hibernate (the records stay on sol's disk); nothing alerts.
#   usage: [HOLD_ON_ABANDON=1] [CHAIN_OUT=~/_rf4/chain.out] [SOL_RAW=~/_rf4/raw] [SOL_SCR=~/_qa-scratch/rf4] [TAG=sol] bash gs_finish.sh > finish.out 2>&1 &
K="-i $HOME/.ssh/id_ed25519_sol -o BatchMode=yes -o ConnectTimeout=15"
HOLD=${HOLD_ON_ABANDON:-1}
CHAIN_OUT=${CHAIN_OUT:-'~/_rf4/chain.out'}
SOL_RAW=${SOL_RAW:-'~/_rf4/raw'}
SOL_SCR=${SOL_SCR:-'~/_qa-scratch/rf4'}
TAG=${TAG:-sol}
D=/d/Projects/claude/_qa-scratch/coh-gate-r-f4/$TAG
LOG=/d/Projects/claude/_qa-scratch/coh-gate-r-f4/finish.log
HIB="sudo -n /usr/sbin/hibernate-ram"
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$LOG"; }
mkdir -p "$D"
log "finish watcher start (tag=$TAG, hold_on_abandon=$HOLD); waiting for the chain at $CHAIN_OUT to end; hibernate command: $HIB"
while true; do
  st=$(timeout 40 ssh $K claude@sol "tail -n 3 $CHAIN_OUT 2>/dev/null" 2>/dev/null)
  if echo "$st" | grep -qE "chain done|CHAIN HALT"; then break; fi
  sleep 60
done
log "sol chain ended: $(echo "$st" | tail -n 1 | cut -c1-120)"
if timeout 120 scp $K -r claude@sol:$SOL_RAW "$D/" > /dev/null 2>&1 && timeout 120 scp $K claude@sol:$CHAIN_OUT "$D/" > /dev/null 2>&1; then
  mkdir -p "$D/scratch"
  timeout 300 scp $K -r claude@sol:$SOL_SCR/. "$D/scratch/" > /dev/null 2>&1 && log "pull ok" || log "pull of scratch FAILED (records remain on sol)"
else
  log "pull of raw FAILED (records remain on sol)"
fi
# V-2N-AB: fallback abandoned (coh.csv col 'abandoned') and residual pass abandoned (abandon.csv col 3) in every arm
ab=$(timeout 60 ssh $K claude@sol "cd $SOL_RAW && for a in off on orig; do [ -f \$a/coh.csv ] && python3 - \$a <<'PY'
import csv, sys
a = sys.argv[1]
c = list(csv.DictReader(open(a + '/coh.csv')))
fb = sum(int(r['abandoned']) for r in c)
rs = sum(int(l.split(',')[2]) for l in open(a + '/abandon.csv') if l[:1].isdigit())
print(a, 'fallback_abandoned', fb, 'residual_abandoned', rs)
PY
done" 2>&1)
log "V-2N-AB read: $(echo "$ab" | tr '\n' ';')"
if echo "$ab" | grep -qE "(fallback|residual)_abandoned [1-9]" || echo "$st" | grep -q "CHAIN HALT"; then
  if [ "$HOLD" = "1" ]; then
    log "ABANDONMENT or HALT: sol NOT hibernated; re-run needed (the Captain's rule). Watcher exits."
    exit 0
  fi
fi
for a in off on orig; do
  r=$(timeout 30 ssh $K claude@sol "sha256sum $SOL_SCR/$a/nc_dump.tsv 2>/dev/null | cut -c1-16")
  l=$(sha256sum "$D/scratch/$a/nc_dump.tsv" 2>/dev/null | cut -c1-16)
  log "verify $a nc_dump sol=$r pc=$l $([ -n "$r" ] && [ "$r" = "$l" ] && echo SAME || echo CHECK)"
done
busy=$(timeout 30 ssh $K claude@sol 'pgrep -f "Replay81.dll|OpenWSFZ.Daemon|wsjtx" | wc -l')
log "rig processes on sol before hibernate: $busy"
log "HIBERNATING sol now (once)"
timeout 60 ssh $K claude@sol "$HIB" > /dev/null 2>&1
log "hibernate command returned rc=$? (sol may already be asleep)"
