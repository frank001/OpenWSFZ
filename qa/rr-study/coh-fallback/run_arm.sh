#!/bin/bash
# COH-FALLBACK step 3 replay arm: run_arm.sh <name> <cohfb 0|1> <selection json>.  Build = feat/coh-fallback-stage1 1405ada4 (shim 20260068, libft8.dll 581331da...); Replay81 --mode three1 (Deep), nhard 24, sign fix 1, 8 threads.
S=D:/Projects/claude/_qa-scratch/coh-fallback
NAME=$1; FLAG=$2; SEL=$3
O=$S/$NAME
rm -rf "$O"; mkdir -p "$O"
echo "start $(date -u +%FT%TZ)" > "$S/${NAME}_status.txt"
"$S/out_stage2/Replay81.exe" \
  --selection "$SEL" --run 20261009_1752 --stratum Y40 \
  --wav-root D:/Projects/claude/OpenWSFZ/worktrees/qa/artefacts \
  --out "$O/run.csv" --log "$O/log.log" \
  --nhard 24 --osd-sign-fix 1 --mode three1 --threads 8 --cohfb "$FLAG" --cohfb-out "$O/coh.csv" --label "cohfb-step3:$NAME" \
  --wsjtx-alltxt D:/Projects/claude/OpenWSFZ/worktrees/qa/artefacts/20261009_1752_endurance_run-gathered/wsjt-x/ALL.TXT --testb-out "$O/testb.csv" \
  --matched-out "$O/matched.csv" --matched-batch-out "$O/matchedbatch.csv" \
  --third-out "$O/third.csv" --abandon-out "$O/abandon.csv" \
  --outcomes "$O/outcomes.csv" > "$O/stdout.txt" 2>&1
echo "exit $? at $(date -u +%FT%TZ)" >> "$S/${NAME}_status.txt"
