#!/bin/bash
# Shipped-defaults check for the frozen thresholds (the Architect's exact comparison).  PC EXCLUSIVE (nothing else running).  usage: bash xc_defaults_replay.sh   (about 20 minutes: two replays of 100 cycles)
# GOAL (HK-020): show that a build with crossCyclePrior ON and NO threshold or veto setters (the product's own defaults) publishes exactly what the acceptance ON-T arm published on its first 100 cycles.
# CRITICAL CONFIG: the harness build of the FINAL hash in $BIN (libft8.dll = the pin); the TEST night 20260808_0016 from the same warm-up cycle (selection sel_test_100.json, the first 100 FULL cycles of sel_test_1000.json);
#   REF arm: setters T_E 3.076041980658299, T_P 2.2220253019230114, veto 1 (exactly the acceptance ON-T flags);  DEF arm: --xc-defaults 1 (no setters).  Everything else identical.
# Text-bearing outputs (nc.tsv, matched.csv) stay under _qa-scratch and are KEPT, never deleted (Captain, 2026-11-16).  Nothing is pushed.
SC=/d/Projects/claude/_qa-scratch
ROOT=$SC/xc-chain/defaults
BIN=${BIN:-$SC/xc-chain/bin_defaults}
WAVROOT=/d/Projects/claude/OpenWSFZ/artefacts
TEST=$WAVROOT/20260808_live_run_0016-8080
SEL=$SC/xc-build/sel_test_100.json
SEL_SHA=8f8073f806dcc9a9
PIN=bbde6eb66af4cd429ffc46f67291ba718c1ae36ae39665faac24629bcb6e6528
SURV=$SC/xc-chain/remedy/T/ON
TOOLS=/d/Projects/claude/OpenWSFZ/worktrees/qa/qa/xc-build
TE=3.076041980658299
TP=2.2220253019230114
w() { cygpath -w "$1"; }
sha() { sha256sum "$1" | cut -d' ' -f1; }
busy() { tasklist 2>/dev/null | grep -qiE 'jt9|OpenWSFZ.Daemon|Ft8.FitProbe|Replay81|dotnet'; }
mkdir -p "$ROOT"; [ -e "$ROOT/REF" ] && mv "$ROOT/REF" "$ROOT/REF.$(date -u +%H%M%S).old"; [ -e "$ROOT/DEF" ] && mv "$ROOT/DEF" "$ROOT/DEF.$(date -u +%H%M%S).old"
LOG=$ROOT/status.txt
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$LOG"; }
die() { log "HALT: $*"; exit 9; }
[ -f "$BIN/Ft8.FitProbe.exe" ] || die "no $BIN"
[ "$(sha $BIN/libft8.dll)" = "$PIN" ] || die "libft8.dll is not the pin"
[ "$(sha $SEL | cut -c1-16)" = "$SEL_SHA" ] || die "sel_test_100.json differs from its recorded hash"
busy && die "a competing process is running (dotnet, FitProbe, the daemon or WSJT-X): the replays need the PC to themselves"
run() {   # run <name> <xc args...>
  local N=$1; shift; local O=$ROOT/$N; mkdir -p "$O"
  log "arm $N start ($*)"
  "$(w $BIN/Ft8.FitProbe.exe)" --selection "$(w $SEL)" --run 20260808_0016 --stratum FULL --wav-root "$(w $WAVROOT)" --wav-dir "$(w $TEST/owsfz/wav)" \
    --out "$(w $O/run.csv)" --log "$(w $O/log.log)" --nhard 24 --osd-sign-fix 1 --mode three1 --threads 8 --cohfb 1 --cohms 1 --cohaudio Both \
    --kmin 5 --osd-corr 0.05 --ungated 1 --late-round 1 --cq-ap 1 --cohrescand 1 --xc-prior 1 --xc-shadow 1 "$@" --xc-out "$(w $O/xc.csv)" --xc-probe-out "$(w $O/probe.csv)" --cohfb-out "$(w $O/coh.csv)" \
    --label "defaults-check:$N" --wsjtx-alltxt "$(w $TEST/wsjt-x/ALL.TXT)" --testb-out "$(w $O/testb.csv)" --matched-out "$(w $O/matched.csv)" --matched-batch-out "$(w $O/matchedbatch.csv)" \
    --third-out "$(w $O/third.csv)" --abandon-out "$(w $O/abandon.csv)" --outcomes "$(w $O/outcomes.csv)" --late-out "$(w $O/late.csv)" --nc-dump "$(w $O/nc.tsv)" > "$O/stdout.txt" 2>&1
  local rc=$?
  local line; line=$(grep "^# readback end" "$O/log.log" | head -1)
  log "arm $N ended rc=$rc; readback: $(echo "$line" | grep -o 'xcprior=[A-Za-z]* xcshadow=[A-Za-z]* xcte=[^ ]* xcveto=[A-Za-z]* xctp=[^ ]*')"
  [ "$rc" = 0 ] || die "arm $N failed rc=$rc"
}
run REF --xc-te $TE --xc-veto 1 --xc-tp $TP
run DEF --xc-defaults 1
# the defaults arm must read back the frozen values itself (no setter was called)
R=$(grep "^# readback end" "$ROOT/DEF/log.log" | head -1)
for need in "xcte=$TE" "xcveto=True" "xctp=$TP"; do echo "$R" | grep -q -- "$need" || die "the DEF arm's readback does not show $need (the defaults are not the frozen values)"; done
log "DEF readback shows the frozen values with no setter called"
python -I "$TOOLS/xc_defaults_cmp.py" cmp "$(w $ROOT/DEF)" "$(w $ROOT/REF)" 100 "$(w $SURV)" > "$ROOT/compare.json" 2>&1; rc=$?
log "comparison rc=$rc (0 = EQUAL); see $ROOT/compare.json"
cat "$ROOT/compare.json" | tr -d '\n' | cut -c1-900; echo
exit $rc
