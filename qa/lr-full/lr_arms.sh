#!/bin/bash
# LR-FULL arms for one fresh night: the PILOT arms (first 10 % of cycles) or the TEST arms (OFF then ON), both replays of the night's archived WAVs through the shipped build with the LR-FULL diagnostic switches.
#   usage: nohup bash lr_arms.sh <night_stamp> pilot|test > <log> 2>&1 & disown          (the Captain's go, 2026-11-18: "the 2 hours restraint is lifted" for this work)
# GOAL (HK-020): OFF = the shipped 66b3ddf1 configuration (--lr-x1 0 --lr-x2 0); ON = OFF + X1 + X2 (--lr-x1 1 --lr-x2 1); everything else identical; both on the SAME selection, one process each.
# CRITICAL CONFIG: bin_lrfull (harness over a clean checkout of 80bbd74b, libft8 = the pin bbde6eb6, HK-039 APPROVED e6062139), Deep, nhard 24, three1, 8 threads, cohfb/cohms/Both, kmin 5, osd-corr 0.05, ungated 1, late-round 1, cq-ap 1,
#   cohrescand 1, xc-prior 1 shadow 0 xc-defaults 1 (xcte read back = 3.076041980658299). The PC should be otherwise idle (WSJT-X may keep running; both arms see the same load; noted in the report).
# Text-bearing outputs (nc.tsv, matched.csv) stay under _qa-scratch and are KEPT (Captain, 2026-11-16). Nothing is pushed.  STOP: create $ROOT/arms.stop (checked between arms).
NIGHT=$1; MODE=$2
SC=/d/Projects/claude/_qa-scratch
ROOT=$SC/lr-full/$NIGHT
BIN=$SC/lr-full/bin_lrfull
ART=/d/Projects/claude/OpenWSFZ/artefacts
G=$ART/${NIGHT}_endurance_run-gathered
PIN=bbde6eb66af4cd429ffc46f67291ba718c1ae36ae39665faac24629bcb6e6528
TE=3.076041980658299
TOOLS=/d/Projects/claude/OpenWSFZ/worktrees/qa/qa/lr-full
w() { cygpath -w "$1"; }
sha() { sha256sum "$1" | cut -d' ' -f1; }
mkdir -p "$ROOT"
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$ROOT/status_$MODE.txt"; }
die() { log "HALT: $*"; exit 9; }
busy() { tasklist 2>/dev/null | grep -qiE 'OpenWSFZ.Daemon|Ft8.FitProbe|testhost|msbuild|VBCSCompiler'; }
[ "$MODE" = pilot ] || [ "$MODE" = test ] || [ "$MODE" = dry ] || [ "$MODE" = rerun20 ] || die "mode dry|pilot|test|rerun20"
[ -d "$G/owsfz/wav" ] && [ -f "$G/wsjt-x/ALL.TXT" ] || die "no gathered night at $G"
[ "$(sha $BIN/libft8.dll)" = "$PIN" ] || die "libft8.dll is not the pin"
busy && die "a competing process is running (daemon, FitProbe, testhost or a build server)"
SEL=$ROOT/sel_$MODE.json
python -I "$TOOLS/lr_night_sel.py" "$G/owsfz/wav" "$SEL" "$NIGHT" $MODE | tee -a "$ROOT/status_$MODE.txt" || die "selection failed"
run() {   # run <name> <extra args...>
  local NAME=$1; shift; local O=$ROOT/${MODE}_$NAME EXPECT="$EXPECT_LR"
  [ -e "$ROOT/arms.stop" ] && die "arms.stop"
  [ -e "$O" ] && mv "$O" "$O.$(date -u +%H%M%S).old"; mkdir -p "$O"
  log "arm $MODE/$NAME start ($*) free_d=$(df -h /d | tail -1 | awk '{print $4}')"
  "$(w $BIN/Ft8.FitProbe.exe)" --selection "$(w $SEL)" --run $NIGHT --stratum FULL --wav-root "$(w $ART)" --wav-dir "$(w $G/owsfz/wav)" \
    --out "$(w $O/run.csv)" --log "$(w $O/log.log)" --nhard 24 --osd-sign-fix 1 --mode three1 --threads 8 --cohfb 1 --cohms 1 --cohaudio Both \
    --kmin 5 --osd-corr 0.05 --ungated 1 --late-round 1 --cq-ap 1 --cohrescand 1 --xc-prior 1 --xc-shadow 0 --xc-defaults 1 "$@" \
    --xc-out "$(w $O/xc.csv)" --xc-probe-out "$(w $O/probe.csv)" --cohfb-out "$(w $O/coh.csv)" \
    --label "lr-full:$NIGHT:$MODE/$NAME" --wsjtx-alltxt "$(w $G/wsjt-x/ALL.TXT)" --testb-out "$(w $O/testb.csv)" --matched-out "$(w $O/matched.csv)" --matched-batch-out "$(w $O/matchedbatch.csv)" \
    --third-out "$(w $O/third.csv)" --abandon-out "$(w $O/abandon.csv)" --outcomes "$(w $O/outcomes.csv)" --late-out "$(w $O/late.csv)" --nc-dump "$(w $O/nc.tsv)" > "$O/stdout.txt" 2>&1
  local rc=$? ok=1 tag need line
  for tag in start end; do
    line=$(grep "^# readback $tag" "$O/log.log" | head -1)
    for need in "decodingDepth=Deep" "nhard=24 " "cohfb=True" "cohms=True" "cohaudio=Both" "ungated=True" "lateround=True" "threadsResolved=8" "cqap=True" "cohrescand=True" "xcprior=True xcshadow=False xcte=$TE" "clock=system" $EXPECT; do
      echo "$line" | grep -q -- "$need" || { ok=0; log "READBACK $tag missing: $need"; }
    done
  done
  [ "$(sha $BIN/libft8.dll)" = "$PIN" ] || { ok=0; log "END dll pin mismatch"; }
  log "arm $MODE/$NAME ended rc=$rc readback_ok=$ok cycles=$(cut -d, -f1 $O/outcomes.csv 2>/dev/null | sort -u | wc -l)"
  [ "$rc" = 0 ] && [ "$ok" = 1 ] || die "arm $MODE/$NAME failed"
}
log "start $MODE for $NIGHT (as $(whoami)); pin ok; selection above"
EXPECT_LR="lrx1=False lrx2=False"; run OFF --lr-x1 0 --lr-x2 0
[ "$MODE" = rerun20 ] || { EXPECT_LR="lrx1=True lrx2=True";   run ON  --lr-x1 1 --lr-x2 1; }   # rerun20 is OFF only
busy && log "WARNING: a process is still running after the arms"
log "done $MODE"
