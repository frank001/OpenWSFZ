#!/bin/bash
# pull-series.sh - bring a FINISHED (or --partial) R&R series home from sol, aggregates only.   QA 2026-10-17
#   usage: pull-series.sh <series id, e.g. B2CAPR> [--partial]
# What it does, in order, with no Claude session needed (run it from Git Bash on the PC):
#   1. reads the series log on sol; refuses to go on unless it ends 'SERIES <ID> COMPLETE' (or --partial is given); prints any HALT line
#   2. copies every <date>-<sha7>-<ID>-sweep<n> run folder (files only) into D:\Projects\claude\OpenWSFZ\qa\rr-study\results (the Captain's standard location, 2026-10-04)
#   3. writes capture_counters.txt into each copied folder, computed ON sol from that sweep's daemon.stdout.log: channel drops, clamped grid windows, 1 MiB pipe granted,
#      and the residual-pass timing of the LAST daemon (= the S6 pass-O daemon). Counts and timings only: the raw daemon log never leaves sol (NFR-021).
#   4. prints the S6 row of each sweep (OWS and WSJT-X consistency) and applies the Architect's WSJT-X TRIPWIRE (ruling 2026-10-17-2218): FLAG iff the WAV-clustered 95 % CI
#      excludes 93.9 % (mean of the six prior standard sequential blocks; re-derive it if the rig, the WSJT-X exe or the WAV list changes)
#   5. renders report.html beside each report.md (render_report.py)
# It changes nothing on sol. It does not commit or push anything.
ID=${1:?series id, e.g. B2CAPR}
PARTIAL=0; [ "$2" = "--partial" ] && PARTIAL=1
DEST=${PULL_DEST:-/d/Projects/claude/OpenWSFZ/qa/rr-study/results}
RENDER=/d/Projects/claude/OpenWSFZ/worktrees/qa/qa/rr-study/render_report.py
TRIPWIRE=93.9
SOL="ssh -i $HOME/.ssh/id_ed25519_sol -o BatchMode=yes -o ConnectTimeout=15 claude@sol"
RES=/home/claude/rr-work-b2/qa/rr-study/results
LC=$(echo "$ID" | tr 'A-Z' 'a-z')

echo "== series log on sol"
$SOL "tail -n 12 /home/claude/rr-run/series-$ID.log" | cut -c1-260 || { echo "cannot reach sol"; exit 2; }
if ! $SOL "grep -q 'SERIES $ID COMPLETE' /home/claude/rr-run/series-$ID.log"; then
  echo "!! the series is NOT complete:"; $SOL "grep -E 'HALT|ABORT' /home/claude/rr-run/series-$ID.log | tail -3" | cut -c1-260
  [ $PARTIAL -eq 1 ] || { echo "stopping (use --partial to pull what is finished)"; exit 3; }
fi

DIRS=$($SOL "cd $RES && ls -d *-$ID-sweep[0-9]* 2>/dev/null | grep -v captured-audio")
[ -n "$DIRS" ] || { echo "no finished sweep folder for $ID on sol"; exit 4; }

for d in $DIRS; do
  n=${d##*sweep}
  echo; echo "== $d  (sweep $n)"
  if [ -e "$DEST/$d" ]; then echo "   already at $DEST/$d - not overwritten"; continue; fi
  mkdir -p "$DEST/$d" || exit 5
  $SOL "tar -C $RES -cf - $d" | tar -C "$DEST" -xf - || { echo "copy failed"; exit 6; }
  echo "   copied: $(ls "$DEST/$d" | wc -l) entries"
  # aggregates from this sweep's daemon log, computed on sol
  $SOL "L=/home/claude/rr-run/$LC-$n/daemon.stdout.log; [ -f \$L ] || { echo 'daemon.stdout.log missing'; exit 0; };
        echo 'sweep $d  (computed on sol from daemon.stdout.log, aggregates only)';
        echo \"channel drops:        \$(grep -c 'Capture channel dropped a chunk' \$L)\";
        echo \"clamped grid windows: \$(grep -c 'Cycle-grid realignment clamped' \$L)\";
        echo \"1 MiB pipe granted:   \$(grep -c 'pipe enlarged: requested 1048576, granted 1048576' \$L) daemon start(s)\";
        S=\$(grep -n 'pipe enlarged' \$L | tail -1 | cut -d: -f1); S=\${S:-1};
        echo \"residual pass, LAST daemon (S6 pass O, from log line \$S):\";
        tail -n +\$S \$L | grep 'Sub-feas residual pass' | sed -E 's/.*elapsedMs=([0-9]+) deadlineAbandoned=([A-Za-z]+).*/\1 \2/' | sort -n |
          awk '{a[NR]=\$1; if(\$2!=\"False\")ab++} END{ if(NR==0){print \"  none\"} else printf \"  n=%d median=%d ms p90=%d ms max=%d ms abandoned=%d (bar: median <= 4000 ms, 0 abandoned)\n\",NR,a[int((NR+1)/2)],a[int(NR*0.9)],a[NR],ab+0}'" > "$DEST/$d/capture_counters.txt"
  cat "$DEST/$d/capture_counters.txt"
  # the S6 row + the tripwire
  R="$DEST/$d/report.md"
  if [ -f "$R" ]; then
    echo "   verdict: $(grep -m1 'Overall verdict' "$R")"
    ownline=$(grep -m1 'within-appraiser consistency, own universe' "$R")
    echo "   S6 consistency, own universe (WSJT-X | OpenWSFZ): $(echo "$ownline" | sed -E 's/^\| [^|]*\| *//')"
    w=$(echo "$ownline" | sed -E 's/^\|[^|]*\| *([0-9.]+) % \[([0-9.]+), ([0-9.]+)\].*/\2 \3/')
    lo=${w% *}; hi=${w#* }
    if [ -n "$lo" ] && [ -n "$hi" ]; then
      awk -v lo="$lo" -v hi="$hi" -v t=$TRIPWIRE 'BEGIN{ if (lo>t || hi<t) print "   !! WSJT-X TRIPWIRE: FLAG - the CI [" lo ", " hi "] excludes " t " %"; else print "   WSJT-X tripwire: not flagged (CI [" lo ", " hi "] contains " t " %)" }'
    else echo "   could not parse the WSJT-X interval - read Section 6 by hand"; fi
    python "$RENDER" "$R" 2>&1 | tail -1
  else echo "   no report.md in the folder"; fi
done
echo; echo "Next (HK-031): READ Section 6 of each report before analysing; board entry; nudge the Architect."
