#!/bin/bash
# Captain's request 2026-10-21: when the step-4 chain has finished (DONE or STOP), save its raw outputs (numbers only; the message-text working files STAY in scratch, HK-037) and HIBERNATE the PC. Detached; survives the Claude session.
# To cancel the hibernate: stop this script (taskkill the bash running finisher4.sh) before the 120 s grace ends; killing this script is the way.
S=/d/Projects/claude/_qa-scratch/coh-fallback/step4
Q=/d/Projects/claude/OpenWSFZ/worktrees/qa/qa/rr-study/results/2026-10-21-coh-fallback-step4-replay-raw
R=/d/Projects/claude/OpenWSFZ/qa/rr-study/results/2026-10-21-coh-fallback-step4-replay-raw
log() { echo "$(date -u +%FT%TZ) $*" >> $S/finisher4.log; }
log "finisher4 waiting for chain4.state"
until [ -f $S/chain4.state ]; do sleep 30; done
log "chain4.state = $(cat $S/chain4.state)"
mkdir -p "$Q" "$R"
for d in off on onrep; do
  [ -d $S/$d ] || continue
  mkdir -p "$Q/$d"
  for f in run.csv coh.csv testb.csv matched.csv matchedbatch.csv third.csv abandon.csv outcomes.csv log.log uprime_off.json uprime_off_classes.json uprime_off.json.percycle.csv uprime_on.json uprime_on.json.percycle.csv; do [ -f $S/$d/$f ] && cp $S/$d/$f "$Q/$d/"; done
done
for f in chain4.log chain4.state off_status.txt on_status.txt onrep_status.txt analysis_step4.json analysis_step4.stdout; do [ -f $S/$f ] && cp $S/$f "$Q/"; done
cp -r "$Q"/. "$R"/ 2>/dev/null
log "raw outputs copied to $Q and $R (nc_dump.tsv stays in $S)"
echo "$(cat $S/chain4.state)" > $S/finisher4.done
# Captain's request 2026-10-21 (night): use sol while the PC sleeps. The audio goes over AFTER the timed arms (never during them: it would compete with the ON arm's timing), then sol's own waiting job starts the full OFF and ON replay.
log "copying the 962 selected WAVs to sol (bounded to 15 min)"
timeout 900 bash /d/Projects/claude/_qa-scratch/coh-fallback/step4/sol_transfer.sh > /d/Projects/claude/_qa-scratch/coh-fallback/step4/sol_transfer.stdout 2>&1
log "sol transfer finished: $(tail -2 /d/Projects/claude/_qa-scratch/coh-fallback/step4/sol_transfer.log | tr '
' ' ')"
log "hibernating in 120 s"
sleep 120
log "hibernate now"
powershell -NoProfile -Command "shutdown.exe /h"
