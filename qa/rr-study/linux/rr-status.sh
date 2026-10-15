#!/usr/bin/env bash
# rr-status.sh - progress and status of the B2BASE R&R series on sol (read-only).
# Usage: ./rr-status.sh [SERIES_ID]      (default B2BASE)
SERIES="${1:-B2BASE}"
RUN="$HOME/rr-run"
RES="$HOME/rr-work-b2/qa/rr-study/results"
SLOG="$RUN/series-$SERIES.log"
lc=$(echo "$SERIES" | tr 'A-Z' 'a-z')

hr() { printf '%s\n' "------------------------------------------------------------"; }
age() { # seconds since file mtime -> human
  local f="$1" s; [ -e "$f" ] || { echo "n/a"; return; }
  s=$(( $(date +%s) - $(stat -c %Y "$f") ))
  printf '%dh%02dm%02ds ago' $((s/3600)) $((s%3600/60)) $((s%60))
}

echo "R&R status  $(date -u +%Y-%m-%dT%H:%M:%SZ)   series $SERIES   host $(hostname)"
hr

# ---- 1. overall verdict -----------------------------------------------------
if [ ! -f "$SLOG" ]; then
  echo "VERDICT : no series log ($SLOG) - nothing has been started under that id"
else
  if   grep -q "SERIES $SERIES COMPLETE" "$SLOG"; then verdict="COMPLETE"
  elif grep -q "HALT:" "$SLOG";                   then verdict="HALTED"
  elif pgrep -f "series-b2base.sh" >/dev/null;    then verdict="RUNNING"
  else verdict="STOPPED (no HALT/COMPLETE line and no series process: killed or crashed?)"; fi
  echo "VERDICT : $verdict"
  head -1 "$SLOG" | cut -c1-260
  started=$(head -1 "$SLOG" | cut -d' ' -f1)
  echo "started : $started    last log write: $(age "$SLOG")"
  echo
  echo "Series log (last 12 lines):"
  tail -12 "$SLOG" | cut -c1-260 | sed 's/^/  /'
  if [ "$verdict" = "HALTED" ]; then
    echo
    echo "!!! HALT: $(grep 'HALT:' "$SLOG" | tail -1 | cut -c1-300)"
  fi
fi
hr

# ---- 2. processes ----------------------------------------------------------
echo "Processes:"
for p in "series-b2base.sh" "battery-b2.sh" "run_study.py" "OpenWSFZ.Daemon" "wsjtx" "jt9"; do
  n=$(pgrep -fc "$p" 2>/dev/null); printf '  %-18s %s\n' "$p" "${n:-0}"
done
echo "  load: $(cut -d' ' -f1-3 /proc/loadavg)   disk free in ~: $(df -h ~ | awk 'NR==2{print $4" ("$5" used)"}')"
hr

# ---- 3. latest sweep -------------------------------------------------------
last=$(ls -d "$RUN"/${lc}-[0-9]* 2>/dev/null | grep -v '\.log$' | sort -V | tail -1)
if [ -z "$last" ]; then
  echo "No sweep folder ${lc}-<n> yet."
else
  n=${last##*-}
  echo "Latest sweep: $n   ($last)"
  [ -f "$last/state.json" ] || [ -f "$last/status.json" ] && python3 - "$last" <<'PY'
import json, sys, os
d = sys.argv[1]
for f in ("status.json", "state.json"):
    p = os.path.join(d, f)
    if os.path.exists(p):
        try:
            j = json.load(open(p))
        except Exception as e:
            print("  %s unreadable: %s" % (f, e)); continue
        keys = ("phase", "started_utc", "battery_started_utc", "ended_utc", "exit_code",
                "predicted_run_dir", "scenario", "current_scenario", "attempt")
        print("  %s: %s" % (f, ", ".join("%s=%s" % (k, j[k]) for k in keys if k in j)))
        break
PY
  echo "  sweep log (last 8):"
  tail -8 "$RUN/${lc}-${n}.log" 2>/dev/null | cut -c1-240 | sed 's/^/    /'

  # supervisor line count and stalls
  sup="$last/supervisor.log"
  [ -f "$sup" ] && echo "  supervisor.log last write: $(age "$sup")"
  stalls=0; [ -f "$last/stall_events.jsonl" ] && stalls=$(wc -l < "$last/stall_events.jsonl")
  samples=0; [ -f "$last/monitor.jsonl" ] && samples=$(wc -l < "$last/monitor.jsonl")
  echo "  M1 monitor: $samples samples (last $(age "$last/monitor.jsonl")), stall events: $stalls"
  ls -d "$last"/stall-* 2>/dev/null | sed 's/^/    snapshot: /'

  # run folder (results) for this sweep
  rf=$(grep -o 'run folder: [^ ]*' "$RUN/${lc}-${n}.log" 2>/dev/null | tail -1 | cut -d' ' -f3)
  [ -z "$rf" ] && rf=$(python3 -c "import json;print(json.load(open('$last/status.json')).get('predicted_run_dir',''))" 2>/dev/null)
  if [ -n "$rf" ] && [ -d "$rf" ]; then
    echo "  run folder: $rf"
    echo "  scenarios with data so far:"
    ls -1 "$rf" 2>/dev/null | grep -E '^(s[0-9]|S[0-9]|truth|report|monitoring|scenario_retries|STALLED|RETRIES_EXHAUSTED|warmup)' | sed 's/^/    /'
    for f in scenario_retries.json STALLED.json RETRIES_EXHAUSTED.json; do
      [ -f "$rf/$f" ] && { echo "  --- $f"; head -c 1500 "$rf/$f" | sed 's/^/    /'; echo; }
    done
  fi
fi
hr

# ---- 4. completed sweeps ---------------------------------------------------
done_n=$(grep -c "sweep [0-9]* of [0-9]*: .*\(DONE\|complete\|COMPLETE\)" "$SLOG" 2>/dev/null)
echo "Completed sweeps (from series log): ${done_n:-0}"
grep -i "RUNNING TOTAL\|totals" "$SLOG" 2>/dev/null | tail -3 | cut -c1-260 | sed 's/^/  /'
ls -d "$RES"/*-"$SERIES"-sweep* 2>/dev/null | sed 's/^/  folder: /'
hr
echo "Details: tail -f $SLOG   |   $RUN/${lc}-<n>.log   |   $RUN/${lc}-<n>/"
