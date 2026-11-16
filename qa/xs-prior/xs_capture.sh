#!/bin/bash
# XS-TEMPLATE buffer capture (spec arch/exchange-step-prior 982ffb45 section 1 and 7).  PC free (not CPU-exclusive per the spec; the Captain is away).  About 4.7 h for 2,834 cycles.
# usage: bash xs_capture.sh preflight | nohup bash xs_capture.sh run > capture.out 2>&1 & disown          STOP: create $ROOT/capture.stop (read before the arm only).  Never hibernates, never pushes.
# GOAL (HK-020): dump, for every cycle of the live night 20261114_2312, the buffers the late stage sees (O original, R2 / R3 residuals, X3) with the SHIPPED stack (XC ON as live, shadow OFF), so the template detector is scored on the
#   residual the live stage would see.  CRITICAL CONFIG: bin_defaults (libft8.dll pin bbde6eb6...), --xc-defaults 1 (frozen T_E / T_P read back), Deep, nhard 24, CQ-AP, multi-set, late round, residual candidates, 8 threads, clock=system;
#   the read-back at the start AND the end must show them.  The 2-cycle dry run passed on 2026-11-16 (rc 0; four 720,000-byte buffers per cycle plus hash, native, plan, capture_index).
# Working files hold message text (native, hash, nc.tsv): under _qa-scratch ONLY and KEPT, never deleted (Captain, 2026-11-16).
MODE=${1:?preflight|run}
SC=/d/Projects/claude/_qa-scratch
ROOT=$SC/xs-template
BIN=$SC/xc-chain/bin_defaults
WAVROOT=/d/Projects/claude/OpenWSFZ/artefacts
NIGHT=$WAVROOT/20261114_2312_endurance_run-gathered
SEL=$SC/xc-live-free/sel_full.json; SEL_SHA=8644488047fde86c
PIN=bbde6eb66af4cd429ffc46f67291ba718c1ae36ae39665faac24629bcb6e6528
TE=3.076041980658299; TP=2.2220253019230114
w() { cygpath -w "$1"; }
sha() { sha256sum "$1" | cut -d' ' -f1; }
busy() { tasklist 2>/dev/null | grep -qiE 'jt9|OpenWSFZ.Daemon|Ft8.FitProbe|Replay81'; }
mkdir -p "$ROOT"; LOG=$ROOT/capture_status.txt
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$LOG"; }
finish() { busy && log "ORPHAN CHECK: a process is still running" || log "orphan check clean"; [ "$(sha $BIN/libft8.dll)" = "$PIN" ] && log "END pin OK" || log "END pin FAIL"; log "capture $MODE finished; halted=$HALTED"; }
HALTED=0
die() { log "CAPTURE HALT: $*"; HALTED=1; finish; exit 9; }
[ "$(sha $BIN/libft8.dll)" = "$PIN" ] || die "libft8.dll is not the pin"
[ "$(sha $SEL | cut -c1-16)" = "$SEL_SHA" ] || die "selection differs from its registered hash"
[ "$(ls $NIGHT/owsfz/wav | wc -l)" = 2834 ] || die "WAV count is not 2834"
[ "$(df -m /d | tail -1 | awk '{print $4}')" -gt 40000 ] || die "less than 40 GB free on D:"
busy && die "a competing process is running"
log "preflight ok"
[ "$MODE" = preflight ] && exit 0
[ -e "$ROOT/capture.stop" ] && die "capture.stop present"
O=$ROOT/cap_run
[ -e "$O" ] && mv "$O" "$O.$(date -u +%Y%m%dT%H%M%SZ).old"; mkdir -p "$O"
log "capture arm start (xc-prior 1 xc-shadow 0 xc-defaults 1, --cap-dir) free_d=$(df -h /d | tail -1 | awk '{print $4}')"
"$(w $BIN/Ft8.FitProbe.exe)" --selection "$(w $SEL)" --run 20261114_2312 --stratum FULL --wav-root "$(w $WAVROOT)" --wav-dir "$(w $NIGHT/owsfz/wav)" \
  --out "$(w $O/run.csv)" --log "$(w $O/log.log)" --nhard 24 --osd-sign-fix 1 --mode three1 --threads 8 --cohfb 1 --cohms 1 --cohaudio Both \
  --kmin 5 --osd-corr 0.05 --ungated 1 --late-round 1 --cq-ap 1 --cohrescand 1 --xc-prior 1 --xc-shadow 0 --xc-defaults 1 --xc-out "$(w $O/xc.csv)" --xc-probe-out "$(w $O/probe.csv)" --cohfb-out "$(w $O/coh.csv)" \
  --label "xs-template:capture" --wsjtx-alltxt "$(w $NIGHT/wsjt-x/ALL.TXT)" --testb-out "$(w $O/testb.csv)" --matched-out "$(w $O/matched.csv)" --matched-batch-out "$(w $O/matchedbatch.csv)" \
  --third-out "$(w $O/third.csv)" --abandon-out "$(w $O/abandon.csv)" --outcomes "$(w $O/outcomes.csv)" --late-out "$(w $O/late.csv)" --nc-dump "$(w $O/nc.tsv)" \
  --cap-dir "$(w $O/cap)" > "$O/stdout.txt" 2>&1
rc=$?; ok=1
for tag in start end; do
  line=$(grep "^# readback $tag" "$O/log.log" | head -1)
  for need in "decodingDepth=Deep" "nhard=24 " "osdSignFixRead=1" "cohfb=True" "cohms=True" "cohaudio=Both" "ungated=True" "lateround=True" "threadsResolved=8" "kMinScorePass2=5 " "osdCorrThreshold=0.05" "cqap=True" "cohrescand=True" "clock=system" "xcprior=True" "xcshadow=False" "xcte=$TE" "xctp=$TP"; do
    echo "$line" | grep -q -- "$need" || { ok=0; log "READBACK $tag missing: $need"; }
  done
done
[ "$(sha $BIN/libft8.dll)" = "$PIN" ] || { ok=0; log "END dll pin mismatch"; }
nidx=$(wc -l < "$O/cap/capture_index.tsv" 2>/dev/null); nbuf=$(ls "$O/cap/buffers" 2>/dev/null | wc -l)
log "capture arm ended rc=$rc readback_ok=$ok index_rows=$nidx buffers=$nbuf (expect 2833 index rows and 4 buffers per cycle)"
[ "$rc" = 0 ] && [ "$ok" = 1 ] || die "capture arm failed"
log "capture done"
finish
