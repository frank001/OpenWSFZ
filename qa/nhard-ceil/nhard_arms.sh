#!/bin/bash
# NHARD-CEIL arms (spec arch/fp-alarm-nhard section 2 + Amendment 1 (A1.3 for TOOL-FAIL, A1.4); the freeze record names this file's blob hash).
# usage:  bash nhard_arms.sh dry|n24|n0|both     PC EXCLUSIVE, station daemon stopped, WSJT-X closed or IDLE (recorded); run detached (nohup ... & disown),
#         logged, orphan-checked (HK-013/019/023). Every arm needs the Captain's go (the PC is his).
#   dry    3 cycles OUTSIDE the selection of the old night 20260930_1930 (late-sub/selection_3n_dry.json): `--nhard 0` then `--nhard 24`, both with `--cq-ap 1 --cohrescand 1`.
#          Plumbing only (A1.4); outputs discarded; the live window is NOT touched.
#   n24    the station stack at --nhard 24      n0   the same at --nhard 0 (OSD off)      both   n24 then n0, one after the other (about 85 min)
# The two arms' command lines are IDENTICAL except --nhard: build bin_v2 (59eb5a8f, source tree identical to main 260190e8, DLL = pin), 500 cycles of
# live-session-cycle-list.txt on the night 20261110_1817, Deep (three1), osd-sign-fix 1, 8 threads, fallback + multi-set ON, Both, kmin 5, osd-corr 0.05, R-F4 ON, L1' ON,
# CQ-AP ON (--cq-ap 1), v2 ON (--cohrescand 1): the stack the station runs (decided by the Captain, 2026-11-12).
# Message text (nc.tsv) lives ONLY under _qa-scratch (HK-037; the harness refuses any other path).
MODE=${1:?dry|n24|n0|both}
SC=/d/Projects/claude/_qa-scratch
V=$SC/nhard-ceil
S=$V/arms
BIN=$SC/coh-res-cand-v2/bin_v2
PIN=bbde6eb66af4cd429ffc46f67291ba718c1ae36ae39665faac24629bcb6e6528
SEL500=$SC/cq-ap/sel_500.json
SEL500_SHA=c618a66e24bb0d129aa6f5df0ecdad978a53f4b0e9e991d308557378fef5de7f
WAVROOT=/d/Projects/claude/OpenWSFZ/artefacts
LIVE=$WAVROOT/20261110_1817_cq-ap-live
RUN=20261110_1817
w() { cygpath -w "$1"; }
sha() { sha256sum "$1" | cut -d' ' -f1; }
mkdir -p "$S"
LOG=$S/chain_status.txt
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$LOG"; }
die() { log "CHAIN HALT: $*"; exit 9; }
busy() { tasklist 2>/dev/null | grep -qiE 'jt9|OpenWSFZ.Daemon|Ft8.FitProbe|Replay81'; }

arm() {   # arm <name> <nhard> <selection> <rows> <run> <wavdir> <wsjtx-alltxt> <outdir>
  local NAME=$1 NH=$2 SEL=$3 WANT=$4 RUNID=$5 WDIR=$6 WALL=$7 O=$8 ST=$8/status.txt
  busy && die "a competing process is running before $NAME"
  [ "$(sha $BIN/libft8.dll)" = "$PIN" ] || die "libft8.dll differs from its pin before $NAME"
  rm -rf "$O"; mkdir -p "$O"
  tasklist 2>/dev/null | grep -qi 'wsjtx' && echo "wsjtx.exe present (open); idle is the Captain's word, recorded in the report" >> "$ST" || echo "wsjtx.exe not running" >> "$ST"
  echo "start $(date -u +%FT%TZ) name=$NAME nhard=$NH cqap=1 cohrescand=1 dll=$(sha $BIN/libft8.dll)" >> "$ST"
  log "arm $NAME start (nhard $NH)"
  "$(w $BIN/Ft8.FitProbe.exe)" --selection "$(w $SEL)" --run $RUNID --stratum FULL --wav-root "$(w $WAVROOT)" --wav-dir "$(w $WDIR)" \
    --out "$(w $O/run.csv)" --log "$(w $O/log.log)" --nhard $NH --osd-sign-fix 1 --mode three1 --threads 8 --cohfb 1 --cohms 1 --cohaudio Both \
    --kmin 5 --osd-corr 0.05 --ungated 1 --late-round 1 --cq-ap 1 --cohrescand 1 --cohfb-out "$(w $O/coh.csv)" \
    --label "nhard-ceil:$NAME" --wsjtx-alltxt "$(w $WALL)" --testb-out "$(w $O/testb.csv)" --matched-out "$(w $O/matched.csv)" --matched-batch-out "$(w $O/matchedbatch.csv)" \
    --third-out "$(w $O/third.csv)" --abandon-out "$(w $O/abandon.csv)" --outcomes "$(w $O/outcomes.csv)" --late-out "$(w $O/late.csv)" --nc-dump "$(w $O/nc.tsv)" > "$O/stdout.txt" 2>&1
  local rc=$? ok=1
  [ "$(sha $BIN/libft8.dll)" = "$PIN" ] || { ok=0; echo "END dll pin mismatch" >> "$ST"; }
  for tag in start end; do   # the arm's readback at the start and at the end of the process
    local line; line=$(grep "^# readback $tag" "$O/log.log" | head -1)
    for need in "decodingDepth=Deep" "nhard=$NH " "osdSignFixRead=1" "cohfb=True" "cohms=True" "cohaudio=Both" "ungated=True" "lateround=True" "threadsResolved=8" "kMinScorePass2=5 " "osdCorrThreshold=0.05" "cqap=True" "cohrescand=True"; do
      echo "$line" | grep -q -- "$need" || { ok=0; echo "READBACK $tag missing: $need" >> "$ST"; }
    done
  done
  local n; n=$(( $(wc -l < "$O/run.csv") - 1 ))
  [ "$n" = "$WANT" ] || { ok=0; echo "ROWS $n != $WANT" >> "$ST"; }
  echo "exit $rc preflight_end_ok=$ok rows=$n at $(date -u +%FT%TZ)" >> "$ST"
  log "arm $NAME done rc=$rc ok=$ok rows=$n"
  [ "$rc" = 0 ] && [ "$ok" = 1 ] || die "arm $NAME failed (rc=$rc ok=$ok)"
}

case $MODE in
  dry)   # old night, plumbing only; the live window is not read
    G=$WAVROOT/20260930_1930_endurance_run-gathered
    S=$V/arms_dry; mkdir -p "$S"; LOG=$S/chain_status.txt
    arm dry_N0  0  $SC/late-sub/selection_3n_dry.json 3 20260930_1930 $G/owsfz/wav $G/wsjt-x/ALL.TXT $S/dry_N0
    arm dry_N24 24 $SC/late-sub/selection_3n_dry.json 3 20260930_1930 $G/owsfz/wav $G/wsjt-x/ALL.TXT $S/dry_N24 ;;
  n24)   [ "$(sha $SEL500)" = "$SEL500_SHA" ] || die "sel_500.json differs from the frozen selection"
         arm N24 24 $SEL500 500 $RUN $LIVE/owsfz/wav $LIVE/wsjt-x/ALL.TXT $S/N24 ;;
  n0)    [ "$(sha $SEL500)" = "$SEL500_SHA" ] || die "sel_500.json differs from the frozen selection"
         arm N0 0 $SEL500 500 $RUN $LIVE/owsfz/wav $LIVE/wsjt-x/ALL.TXT $S/N0 ;;
  both)  [ "$(sha $SEL500)" = "$SEL500_SHA" ] || die "sel_500.json differs from the frozen selection"
         arm N24 24 $SEL500 500 $RUN $LIVE/owsfz/wav $LIVE/wsjt-x/ALL.TXT $S/N24
         arm N0 0 $SEL500 500 $RUN $LIVE/owsfz/wav $LIVE/wsjt-x/ALL.TXT $S/N0 ;;
esac
busy && log "ORPHAN CHECK: a competing process is still running" || log "orphan check clean"
log "$MODE done"
