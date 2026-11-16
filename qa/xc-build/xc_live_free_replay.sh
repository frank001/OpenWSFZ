#!/bin/bash
# XC-LIVE-FREE step 0 replay (spec arch/cross-cycle-prior 50d2ae3c, 2026-11-16-1302, section 1 and 5).  PC EXCLUSIVE.  usage: nohup bash xc_live_free_replay.sh > live_free.out 2>&1 & disown
# GOAL (HK-020): the XC rows of the live night 20261114_2312 are not tagged anywhere, so replay its 2,834 archived WAVs through the shipped build with XC ON (shipped defaults, shadow OFF as live), then XC OFF.
# CRITICAL CONFIG: harness build of 66b3ddf1's source (libft8.dll = the pin; src/native diff 4fe85cc5..66b3ddf1 empty), --xc-defaults 1 (no setters; frozen T_E/T_P read back), shadow 0, Deep, nhard 24, CQ-AP, multi-set, late round, residual candidates, 8 threads.
# Text-bearing outputs stay under _qa-scratch\xc-live-free (HK-037) and are KEPT, never deleted (Captain, 2026-11-16).  STOP: create $ROOT/chain.stop.  Nothing is pushed.
SC=/d/Projects/claude/_qa-scratch
ROOT=$SC/xc-live-free
BIN=$SC/xc-chain/bin_defaults
WAVROOT=/d/Projects/claude/OpenWSFZ/artefacts
NIGHT=$WAVROOT/20261114_2312_endurance_run-gathered
SEL=$ROOT/sel_full.json; SEL_SHA=8644488047fde86c
PIN=bbde6eb66af4cd429ffc46f67291ba718c1ae36ae39665faac24629bcb6e6528
TE=3.076041980658299; TP=2.2220253019230114
w() { cygpath -w "$1"; }
sha() { sha256sum "$1" | cut -d' ' -f1; }
busy() { tasklist 2>/dev/null | grep -qiE 'jt9|OpenWSFZ.Daemon|Ft8.FitProbe|Replay81|dotnet'; }
LOG=$ROOT/status.txt
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$LOG"; }
die() { log "HALT: $*"; exit 9; }
[ "$(sha $BIN/libft8.dll)" = "$PIN" ] || die "libft8.dll is not the pin"
[ "$(sha $SEL | cut -c1-16)" = "$SEL_SHA" ] || die "selection differs from its registered hash"
[ "$(ls $NIGHT/owsfz/wav | wc -l)" = 2834 ] || die "WAV count is not 2834"
busy && die "a competing process is running"
run() {   # run <name> <toks required> <xc args...>
  local N=$1 TOKS=$2; shift 2; local O=$ROOT/$N; [ -e "$ROOT/chain.stop" ] && die "chain.stop"
  [ -e "$O" ] && mv "$O" "$O.$(date -u +%H%M%S).old"; mkdir -p "$O"
  log "arm $N start ($*) free_d=$(df -h /d | tail -1 | awk '{print $4}')"
  "$(w $BIN/Ft8.FitProbe.exe)" --selection "$(w $SEL)" --run 20261114_2312 --stratum FULL --wav-root "$(w $WAVROOT)" --wav-dir "$(w $NIGHT/owsfz/wav)" \
    --out "$(w $O/run.csv)" --log "$(w $O/log.log)" --nhard 24 --osd-sign-fix 1 --mode three1 --threads 8 --cohfb 1 --cohms 1 --cohaudio Both \
    --kmin 5 --osd-corr 0.05 --ungated 1 --late-round 1 --cq-ap 1 --cohrescand 1 "$@" --xc-out "$(w $O/xc.csv)" --xc-probe-out "$(w $O/probe.csv)" --cohfb-out "$(w $O/coh.csv)" \
    --label "xc-live-free:$N" --wsjtx-alltxt "$(w $NIGHT/wsjt-x/ALL.TXT)" --testb-out "$(w $O/testb.csv)" --matched-out "$(w $O/matched.csv)" --matched-batch-out "$(w $O/matchedbatch.csv)" \
    --third-out "$(w $O/third.csv)" --abandon-out "$(w $O/abandon.csv)" --outcomes "$(w $O/outcomes.csv)" --late-out "$(w $O/late.csv)" --nc-dump "$(w $O/nc.tsv)" > "$O/stdout.txt" 2>&1
  local rc=$? ok=1 tag need line
  for tag in start end; do
    line=$(grep "^# readback $tag" "$O/log.log" | head -1)
    for need in "decodingDepth=Deep" "nhard=24 " "osdSignFixRead=1" "cohfb=True" "cohms=True" "cohaudio=Both" "ungated=True" "lateround=True" "threadsResolved=8" "kMinScorePass2=5 " "osdCorrThreshold=0.05" "cqap=True" "cohrescand=True" "clock=system" $TOKS; do
      echo "$line" | grep -q -- "$need" || { ok=0; log "READBACK $tag missing: $need"; }
    done
  done
  [ "$(sha $BIN/libft8.dll)" = "$PIN" ] || { ok=0; log "END dll pin mismatch"; }
  log "arm $N ended rc=$rc readback_ok=$ok"
  [ "$rc" = 0 ] && [ "$ok" = 1 ] || die "arm $N failed"
}
log "start (as $(whoami)); selection sha $SEL_SHA, pin ok"
run ON  "xcprior=True xcshadow=False xcte=$TE xcveto=True xctp=$TP" --xc-prior 1 --xc-shadow 0 --xc-defaults 1
run OFF "xcprior=False xcshadow=False"                              --xc-prior 0 --xc-shadow 0
log "both arms done"
busy && log "ORPHAN CHECK: a process is still running" || log "orphan check clean"
