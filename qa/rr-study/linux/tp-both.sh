#!/bin/sh
# tp-both.sh - the UNATTENDED third-pass pair on sol (QA 2026-10-18; Captain: "both runs, TPNORMAL and then TPDEEP after that. when both tests are completed with or without
# an error hibernate the system with 'sudo hibernate-ram'. no password is required").
#   TPNORMAL (Normal on the third-pass build) runs FIRST, TPDEEP (Deep, the same build) SECOND, one complete sweep each (series-tp.sh -> battery-tp.sh).
#   RULES (Captain, 2026-10-18, third statement): (1) NO hibernate between the two runs; (2) TPDEEP ALWAYS starts after TPNORMAL, whatever TPNORMAL did: OK, voided (a pin or depth
#   check), or failed after all its retries; (3) a failure of TPDEEP counts as the failure of the pair; (4) the system hibernates exactly ONCE, after TPDEEP, whatever happened. A scenario
#   that fails and then passes within its retries is simply OK (the retries live inside the battery). Before the hibernate stray processes are cleaned up and the log gets a summary. A
#   failing hibernate is logged and leaves the machine on. Detached by the caller (setsid nohup); no cron (HK-023).
#   usage: TP_DAEMON=<published daemon> TP_REPO=<its checkout> [TP_CONFIG_NORMAL=..] [TP_CONFIG_DEEP=..] [BOTH_ID=TPBOTH] [IDN=TPNORMAL] [IDD=TPDEEP] [SCEN=<scenarios>] [S6_TIER=standard]
#          [TP_HIBERNATE_CMD="sudo -n /usr/sbin/hibernate-ram"]   tp-both.sh
#   SMOKE TEST: SCEN=S1b IDN=TPSMOKEN IDD=TPSMOKED BOTH_ID=TPSMOKE TP_HIBERNATE_CMD="echo STUB-HIBERNATE" tp-both.sh
BOTH_ID=${BOTH_ID:-TPBOTH}; IDN=${IDN:-TPNORMAL}; IDD=${IDD:-TPDEEP}
HIB=${TP_HIBERNATE_CMD:-sudo -n /usr/sbin/hibernate-ram}
CFGN=${TP_CONFIG_NORMAL:-$HOME/rr-run/config-tp-normal.json}
CFGD=${TP_CONFIG_DEEP:-$HOME/rr-run/config-tp-deep.json}
: "${TP_DAEMON:?set TP_DAEMON}" "${TP_REPO:?set TP_REPO}"
export TP_DAEMON TP_REPO
LOG=$HOME/rr-run/series-$BOTH_ID.log
log() { echo "$(date -u +%FT%TZ) $*" >> "$LOG"; }
SCENARG=""; [ -n "$SCEN" ] && SCENARG="$SCEN"

log "pair start: $IDN (config $CFGN) then $IDD (config $CFGD); scenarios ${SCEN:-the full battery}; S6 tier ${S6_TIER:-standard}; hibernate command: $HIB"
# pre-flight (does not stop the pair; only recorded): the hibernate permission is checked WITHOUT running it
case "$HIB" in
  *hibernate-ram*) if sudo -n -l /usr/sbin/hibernate-ram > /dev/null 2>&1; then log "pre-flight: sudo may run hibernate-ram without a password"; else log "pre-flight WARNING: sudo -n -l hibernate-ram failed; the machine may stay on at the end"; fi;;
  *) log "pre-flight: hibernate command is a stand-in (smoke test): $HIB";;
esac
FREE=$(df -Pk "$HOME" | awk 'NR==2{print int($4/1048576)}'); log "pre-flight: $FREE GiB free in \$HOME"
[ "${FREE:-0}" -ge 20 ] || log "pre-flight WARNING: less than 20 GiB free"

run_one() {   # $1 id, $2 config
  log "== $1 start (TP_CONFIG=$2)"
  if [ -n "$SCENARG" ]; then TP_CONFIG="$2" sh "$HOME/series-tp.sh" 1 "$1" "$SCENARG"; else TP_CONFIG="$2" sh "$HOME/series-tp.sh" 1 "$1"; fi
  rc=$?
  last=$(tail -n 1 "$HOME/rr-run/series-$1.log" 2>/dev/null | cut -c1-200)
  log "== $1 finished: exit $rc; series log ends: $last"
  return $rc
}
run_one "$IDN" "$CFGN"; RCN=$?
if [ "$RCN" -eq 0 ]; then
  log "$IDN OK: starting $IDD now (no hibernate between the runs)"
else
  log "$IDN did NOT complete (exit $RCN): starting $IDD anyway, as asked (no hibernate between the runs)"
fi
run_one "$IDD" "$CFGD"; RCD=$?

# nothing of the rig may be left running when the machine goes to sleep (exact process names, as battery-tp.sh does)
pkill -x OpenWSFZ.Daemon 2>/dev/null; pkill -x wsjtx 2>/dev/null; pkill -x jt9 2>/dev/null; pkill -x Xvfb 2>/dev/null; pkill -f status_poller_tp.py 2>/dev/null; pkill -f wsjtx_monitor.py 2>/dev/null
sleep 5
if [ "$RCN" -eq 0 ] && [ "$RCD" = "0" ]; then OUTCOME="both complete"; else OUTCOME="at least one halted or failed: see their series logs"; fi
log "pair FINISHED: $IDN exit $RCN, $IDD exit $RCD ($OUTCOME)"
log "orphans: $(pgrep -af 'bin/wsjtx|bin/jt9|aplay|Xvfb|OpenWSFZ.Daemon|wsjtx_monitor|status_poller' | grep -v pgrep | wc -l)"
log "hibernating now: $HIB"
sync; sleep 20
sh -c "$HIB" >> "$LOG" 2>&1
HRC=$?
log "hibernate command returned $HRC (the machine has resumed, or the command failed and the machine stayed on)"
