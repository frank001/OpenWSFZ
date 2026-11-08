#!/bin/bash
# Captain's request 2026-10-20: when the replay chain has finished (DONE, HALT_VU0 or STOP), save its raw outputs and HIBERNATE the PC. Detached; survives the Claude session.
# To cancel the hibernate: stop this script (taskkill the bash running finisher.sh) before the 120 s grace ends, or run `shutdown /a` is NOT applicable to /h; killing this script is the way.
S=/d/Projects/claude/_qa-scratch/coh-fallback
Q=/d/Projects/claude/OpenWSFZ/worktrees/qa/qa/rr-study/results/2026-10-20-coh-fallback-stage2-replay-raw
R=/d/Projects/claude/OpenWSFZ/qa/rr-study/results/2026-10-20-coh-fallback-stage2-replay-raw
log() { echo "$(date -u +%FT%TZ) $*" >> $S/finisher.log; }
log "finisher waiting for chain2.state"
until [ -f $S/chain2.state ]; do sleep 30; done
log "chain2.state = $(cat $S/chain2.state)"
mkdir -p "$Q" "$R"
for d in off2 on onrep; do
  [ -d $S/$d ] || continue
  mkdir -p "$Q/$d"
  for f in run.csv coh.csv testb.csv matched.csv matchedbatch.csv third.csv abandon.csv outcomes.csv log.log; do [ -f $S/$d/$f ] && cp $S/$d/$f "$Q/$d/"; done
done
for f in chain2.log vu0.json off2_status.txt on_status.txt onrep_status.txt; do [ -f $S/$f ] && cp $S/$f "$Q/"; done
cp -r "$Q"/. "$R"/ 2>/dev/null
log "raw outputs copied to $Q and $R"
echo "$(cat $S/chain2.state)" > $S/finisher.done
log "hibernating in 120 s"
sleep 120
log "hibernate now"
powershell -NoProfile -Command "shutdown.exe /h"
