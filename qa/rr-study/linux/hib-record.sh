#!/bin/sh
# Stand-in for 'sudo -n /usr/sbin/hibernate-ram' in the pair-driver tests (QA 2026-10-18): records WHEN it was called and what was still running, and does nothing else.
echo "$(date -u +%FT%TZ) HIBERNATE-STAND-IN CALLED; rig processes still running: $(ps -eo cmd | grep -E 'OpenWSFZ.Daemon|bin/wsjtx|bin/jt9|Xvfb|battery-tp|series-tp|run_study' | grep -v grep | wc -l)" >> "$HOME/rr-run/hib-record.log"
exit 0
