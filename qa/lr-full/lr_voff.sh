#!/bin/bash
# LR-FULL V-OFF identity check + 2-cycle dry runs (Q79).  usage: bash lr_voff.sh dry | voff      (under 2 h: 3 arms x 2 cycles, then 3 arms x 20 cycles, about 10 minutes in all; PC exclusive)
# GOAL (HK-020): show that the Developer's diagnostic build 80bbd74b with BOTH switches OFF behaves exactly like the shipped 66b3ddf1 build on the replay path (nc.tsv columns 1-12, outcomes, matched, testb identical; the two timing-free log line families equal), and that the switches ON run and read back.
# CRITICAL CONFIG: BASE = bin_defaults (harness over 66b3ddf1, libft8 = the pin); NEW = bin_lrfull (the same harness source, HasLrFull, over a clean checkout of 80bbd74b, libft8 = the pin); every flag identical (Deep, nhard 24, three1, 8 threads, cohfb/cohms/Both, kmin 5, osd-corr 0.05, ungated 1, late-round 1, cq-ap 1, cohrescand 1, xc-prior 1 shadow 0 xc-defaults 1); only --lr-x1/--lr-x2 differ.
# Text-bearing outputs (nc.tsv, matched.csv) stay under _qa-scratch and are KEPT (Captain, 2026-11-16). Nothing is pushed.
MODE=${1:-dry}
SC=/d/Projects/claude/_qa-scratch
ROOT=$SC/lr-full/voff
BASE=$SC/xc-chain/bin_defaults
NEWB=$SC/lr-full/bin_lrfull
WAVROOT=/d/Projects/claude/OpenWSFZ/artefacts
NIGHT=$WAVROOT/20261114_2312_endurance_run-gathered
PIN=bbde6eb66af4cd429ffc46f67291ba718c1ae36ae39665faac24629bcb6e6528
TE=3.076041980658299
TOOLS=/d/Projects/claude/OpenWSFZ/worktrees/qa/qa/lr-full
w() { cygpath -w "$1"; }
sha() { sha256sum "$1" | cut -d' ' -f1; }
busy() { tasklist 2>/dev/null | grep -qiE 'jt9|OpenWSFZ.Daemon|Ft8.FitProbe|Replay81|testhost|wsjtx'; }
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$ROOT/status.txt"; }
die() { log "HALT: $*"; exit 9; }
mkdir -p "$ROOT"
[ "$(sha $BASE/libft8.dll)" = "$PIN" ] || die "base libft8.dll is not the pin"
[ "$(sha $NEWB/libft8.dll)" = "$PIN" ] || die "new libft8.dll is not the pin"
[ "$(ls $NIGHT/owsfz/wav | wc -l)" = 2834 ] || die "WAV count is not 2834"
busy && die "a competing process is running (testhost, FitProbe, daemon, jt9 or WSJT-X): the replays need the PC to themselves"
case $MODE in dry) N=2;; voff) N=20;; *) die "mode dry|voff";; esac
SEL=$ROOT/sel_$N.json
python -I "$TOOLS/lr_voff_sel.py" "$SC/xc-live-free/sel_full.json" "$SEL" $N || die "selection subset failed"
EXPECT_LR=""
run() {   # run <name> <bin> <extra args...>
  local NAME=$1 BIN=$2; shift 2; local O=$ROOT/${MODE}_$NAME
  [ -e "$O" ] && mv "$O" "$O.$(date -u +%H%M%S).old"; mkdir -p "$O"
  log "arm $MODE/$NAME start ($*)"
  "$(w $BIN/Ft8.FitProbe.exe)" --selection "$(w $SEL)" --run 20261114_2312 --stratum FULL --wav-root "$(w $WAVROOT)" --wav-dir "$(w $NIGHT/owsfz/wav)" \
    --out "$(w $O/run.csv)" --log "$(w $O/log.log)" --nhard 24 --osd-sign-fix 1 --mode three1 --threads 8 --cohfb 1 --cohms 1 --cohaudio Both \
    --kmin 5 --osd-corr 0.05 --ungated 1 --late-round 1 --cq-ap 1 --cohrescand 1 --xc-prior 1 --xc-shadow 0 --xc-defaults 1 "$@" \
    --xc-out "$(w $O/xc.csv)" --xc-probe-out "$(w $O/probe.csv)" --cohfb-out "$(w $O/coh.csv)" \
    --label "lr-full-voff:$MODE/$NAME" --wsjtx-alltxt "$(w $NIGHT/wsjt-x/ALL.TXT)" --testb-out "$(w $O/testb.csv)" --matched-out "$(w $O/matched.csv)" --matched-batch-out "$(w $O/matchedbatch.csv)" \
    --third-out "$(w $O/third.csv)" --abandon-out "$(w $O/abandon.csv)" --outcomes "$(w $O/outcomes.csv)" --late-out "$(w $O/late.csv)" --nc-dump "$(w $O/nc.tsv)" > "$O/stdout.txt" 2>&1
  local rc=$? ok=1 tag need line
  for tag in start end; do
    line=$(grep "^# readback $tag" "$O/log.log" | head -1)
    for need in "decodingDepth=Deep" "nhard=24 " "cohfb=True" "cohms=True" "cohaudio=Both" "ungated=True" "lateround=True" "threadsResolved=8" "cqap=True" "cohrescand=True" "xcprior=True xcshadow=False xcte=$TE" "clock=system" $EXPECT_LR; do
      echo "$line" | grep -q -- "$need" || { ok=0; log "READBACK $tag missing: $need"; }
    done
  done
  [ "$(sha $BIN/libft8.dll)" = "$PIN" ] || { ok=0; log "END dll pin mismatch"; }
  log "arm $MODE/$NAME ended rc=$rc readback_ok=$ok cycles=$(cut -d, -f1 $O/outcomes.csv 2>/dev/null | sort -u | wc -l)"
  [ "$rc" = 0 ] && [ "$ok" = 1 ] || die "arm $MODE/$NAME failed"
}
log "start $MODE (N=$N, as $(whoami)); pins ok"
EXPECT_LR="";                         run base   "$BASE"
EXPECT_LR="lrx1=False lrx2=False";    run new_off "$NEWB" --lr-x1 0 --lr-x2 0
EXPECT_LR="lrx1=True lrx2=True";      run new_on  "$NEWB" --lr-x1 1 --lr-x2 1
busy && log "WARNING: a process is still running after the arms"
python -I "$TOOLS/lr_voff_compare.py" "$ROOT/${MODE}_base" "$ROOT/${MODE}_new_off" "$ROOT/${MODE}_new_on" | tee -a "$ROOT/status.txt"
log "done $MODE"
