#!/bin/sh
# THIRD-PASS (#240) variant of series-b2cap.sh (QA, 2026-10-18): N COMPLETE sweeps in a row on a build and config chosen by the caller (TP_DAEMON, TP_REPO, TP_CONFIG: see
# battery-tp.sh), through battery-tp.sh. Only the build line and the battery name change; the folders carry the series ID (use TPDEEP / TPNORMAL) so Deep-ON and Deep-OFF can never be pooled.
# Original header follows.
# The B2 BASELINE series driver on sol (QA, 2026-10-14; Architect amendment 3 + the Captain's retry ruling): N COMPLETE sweeps in a row on the B2 build, S6 (standard tier) in every sweep,
# with the monitoring M1-M3 and the SCENARIO-level retry (SCENARIO_RETRIES per scenario, default 3; no wall-time limit). Detached by the caller; no cron (HK-023).
#   usage: [SCENARIO_RETRIES=3] [START=<k>] series-b2base.sh <n sweeps> [series id, default B2BASE] [scenarios, default the full battery]
#   START=k RESUMES a halted series at sweep k (sweeps 1..k-1 are already complete and renamed; <n> stays the TOTAL, so the sweep names and folders carry on). The running totals then
#   count only the sweeps of this invocation: the per-sweep scenario_retries.json files are the record.
# For each sweep it runs battery-series.sh (one battery = one sweep; the retries happen INSIDE it, per scenario), then renames the sweep's run folder (and its captured-audio folder and the S6
# scratch folder) to <date>-<sha>-<ID>-sweep<n>, so the next sweep cannot collide with it and every folder carries the series label. It HALTS the whole series on any halt of a sweep
# (a scenario failing again with its retries used up, a restart that fails, any non-stall failure). After every sweep it logs the RUNNING TOTALS (scenario attempts / failed attempts /
# replacements) to ~/rr-run/series-<ID>.log. There is no series-level cap (the Captain's call; the Architect flagged the worst case). The series is never pooled with another one.
N=${1:?number of sweeps}; ID=${2:-B2BASE}
SCEN=${3:-S1,S1b,S2,S3,S4,S5,S7,S8,S3c,S6}
export SCENARIO_RETRIES=${SCENARIO_RETRIES:-3}
SLOG=$HOME/rr-run/series-$ID.log
PY=$HOME/rr-venv/bin/python
slog() { echo "$(date -u +%FT%TZ) $*" >> "$SLOG"; }
slog "series $ID start (from sweep ${START:-1}): $N sweeps; scenarios $SCEN; retries per scenario $SCENARIO_RETRIES; S6 mode ${S6_MODE:-sequential}; daemon scheduling ${DAEMON_SCHED:-none}; build $(git -C ${TP_REPO:?} rev-parse HEAD); tooling $(git -C $HOME/rr-work-b2 rev-parse HEAD)"
TA=0; TF=0; TR=0
i=${START:-1}
while [ $i -le "$N" ]; do
  NAME=$(echo "$ID" | tr 'A-Z' 'a-z')-$i
  rm -f "$HOME/rr-run/$NAME.log"
  slog "sweep $i of $N: start ($NAME)"
  case ",$SCEN," in *,S6,*) sh "$HOME/battery-tp.sh" "$NAME" "$SCEN" --s6-tier "${S6_TIER:-standard}";; *) sh "$HOME/battery-tp.sh" "$NAME" "$SCEN";; esac
  rc=$?
  if [ $rc -ne 0 ] || ! grep -q " DONE$" "$HOME/rr-run/$NAME.log" 2>/dev/null; then
    slog "HALT: sweep $i did not end DONE (rc $rc); see $HOME/rr-run/$NAME.log; the series stops here (complete sweeps so far: $((i - 1)))"
    exit 1
  fi
  RUN=$(grep "run folder:" "$HOME/rr-run/$NAME.log" | tail -1 | sed 's/.*run folder: //')
  [ -d "$RUN" ] || { slog "HALT: run folder of sweep $i not found ($RUN)"; exit 1; }
  FINAL="$RUN-$ID-sweep$i"
  mv "$RUN" "$FINAL" || { slog "HALT: cannot rename $RUN"; exit 1; }
  [ -d "$RUN-captured-audio" ] && mv "$RUN-captured-audio" "$FINAL-captured-audio"
  S6S="$HOME/qa-scratch/s6-$(basename "$RUN")"
  [ -d "$S6S" ] && mv "$S6S" "$HOME/qa-scratch/s6-$(basename "$FINAL")"
  cp "$HOME/rr-run/$NAME.log" "$FINAL/launcher.log" 2>/dev/null
  # V-F (DI7COH2; Architect K2): was the coherent fallback running in this sweep? Read from the sweep's own daemon log; a VOID is logged here and decided at the close.
  if [ -f "$HOME/rr-work-b2/qa/rr-study/linux/flag_readback.py" ] && [ "${TP_REQUIRE_FLAG:-}" = "true" ]; then
    VF=$("$PY" "$HOME/rr-work-b2/qa/rr-study/linux/flag_readback.py" --daemon-log "$HOME/rr-run/$NAME/daemon.stdout.log" --config "${TP_CONFIG:?}" --out "$FINAL/flag_readback.json" 2>&1 | tail -1)
    slog "sweep $i V-F: $VF"
  fi
  SUMLINE=$("$PY" - "$FINAL" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1] + "/scenario_retries.json"))["totals"]
print(d["scenario_attempts"], d["failed_attempts"], d["replacements"])
PYEOF
)
  set -- $SUMLINE
  TA=$((TA + $1)); TF=$((TF + $2)); TR=$((TR + $3))
  slog "sweep $i of $N DONE: $(basename "$FINAL"); this sweep: attempts $1, failed $2, replacements $3; RUNNING TOTALS over $i sweep(s): scenario attempts $TA, failed attempts $TF, replacements $TR"
  i=$((i + 1))
done
slog "SERIES $ID COMPLETE: $N complete sweeps; scenario attempts $TA, failed attempts $TF, replacements $TR"
