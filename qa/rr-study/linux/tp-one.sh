#!/bin/sh
# tp-one.sh - ONE unattended sweep on sol, then ONE hibernate (QA 2026-10-19; Captain: "start a sweep on sol" and "be sure that the hibernate is used correctly").
# The single-run sibling of tp-both.sh: the same run_one, the same cleanup and the same hibernate block, copied statement for statement (that block already hibernated sol for real on 2026-10-19
# after TPDEEP). RULES: (1) the system hibernates exactly ONCE, after the sweep, WHATEVER happened (OK, voided by a pin or depth check, failed after its retries); (2) never before the sweep has
# ended and its run folder is renamed; (3) nothing of the rig is left running when it sleeps; (4) a failing hibernate is logged and leaves the machine on; (5) NOTHING alerts on a halt
# (the Captain wakes sol and QA reads the logs). Detached by the caller (setsid nohup); no cron (HK-023).
#   usage: TP_DAEMON=<published daemon> TP_REPO=<its checkout> [TP_CONFIG=<sweep config, default ~/rr-run/config.json>] [ID=MAINDEEP] [SCEN=<scenarios>] [S6_TIER=standard]
#          [TP_HIBERNATE_CMD="sudo -n /usr/sbin/hibernate-ram"]   tp-one.sh
#   SMOKE TEST: SCEN=S1b ID=MAINSMOKE TP_HIBERNATE_CMD="echo STUB-HIBERNATE" tp-one.sh
ID=${ID:-MAINDEEP}
HIB=${TP_HIBERNATE_CMD:-sudo -n /usr/sbin/hibernate-ram}
CFG=${TP_CONFIG:-$HOME/rr-run/config.json}
: "${TP_DAEMON:?set TP_DAEMON}" "${TP_REPO:?set TP_REPO}"
export TP_DAEMON TP_REPO
LOG=$HOME/rr-run/series-$ID-ONE.log
log() { echo "$(date -u +%FT%TZ) $*" >> "$LOG"; }
SCENARG=""; [ -n "$SCEN" ] && SCENARG="$SCEN"

log "one-run start: $ID (config $CFG); scenarios ${SCEN:-the full battery}; S6 tier ${S6_TIER:-standard}; hibernate command: $HIB"
# pre-flight (does not stop the run; only recorded): the hibernate permission is checked WITHOUT running it
case "$HIB" in
  *hibernate-ram*) if sudo -n -l /usr/sbin/hibernate-ram > /dev/null 2>&1; then log "pre-flight: sudo may run hibernate-ram without a password"; else log "pre-flight WARNING: sudo -n -l hibernate-ram failed; the machine may stay on at the end"; fi;;
  *) log "pre-flight: hibernate command is a stand-in (smoke test): $HIB";;
esac
FREE=$(df -Pk "$HOME" | awk 'NR==2{print int($4/1048576)}'); log "pre-flight: $FREE GiB free in \$HOME"
[ "${FREE:-0}" -ge 20 ] || log "pre-flight WARNING: less than 20 GiB free"

log "== $ID start (TP_CONFIG=$CFG)"
if [ -n "$SCENARG" ]; then TP_CONFIG="$CFG" sh "$HOME/series-tp.sh" 1 "$ID" "$SCENARG"; else TP_CONFIG="$CFG" sh "$HOME/series-tp.sh" 1 "$ID"; fi
RC=$?
last=$(tail -n 1 "$HOME/rr-run/series-$ID.log" 2>/dev/null | cut -c1-200)
log "== $ID finished: exit $RC; series log ends: $last"

# nothing of the rig may be left running when the machine goes to sleep (exact process names, as battery-tp.sh does)
pkill -x OpenWSFZ.Daemon 2>/dev/null; pkill -x wsjtx 2>/dev/null; pkill -x jt9 2>/dev/null; pkill -x Xvfb 2>/dev/null; pkill -f status_poller_tp.py 2>/dev/null; pkill -f wsjtx_monitor.py 2>/dev/null
sleep 5
if [ "$RC" -eq 0 ]; then OUTCOME="complete"; else OUTCOME="halted or failed: see the series log"; fi
log "run FINISHED: $ID exit $RC ($OUTCOME)"
log "orphans: $(pgrep -af 'bin/wsjtx|bin/jt9|aplay|Xvfb|OpenWSFZ.Daemon|wsjtx_monitor|status_poller' | grep -v pgrep | wc -l)"
log "hibernating now: $HIB"
sync; sleep 20
sh -c "$HIB" >> "$LOG" 2>&1
HRC=$?
log "hibernate command returned $HRC (the machine has resumed, or the command failed and the machine stayed on)"
