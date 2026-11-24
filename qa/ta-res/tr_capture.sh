#!/bin/bash
# TA-RES R1: the capture replay of 20261110 arm B (spec arch/accept-gate cae3015c + Amendment 1 ef0b6e51; the Captain's go, 2026-11-13). PC: daemon stopped, WSJT-X closed or idle. Detached, logged, orphan-checked (HK-013/019/023).
# Run: nohup bash tr_capture.sh > chain.out 2>&1 & disown
# IDENTICAL to coh-res-cand-v2/crc2_arms.sh's arm B (same build bin_v2 = tree 59eb5a8f, same 500-cycle selection with its warm-up, same flags) PLUS the capture and the provenance dumps:
#   --cap-dir (O, R2, R3, X3 buffers, natives, hash states, plan, capture_index), --stage-out + --gate-record 1 + --stage-dump (G/R/U/X lines: which run found which payload, payload -> text).
# Working files with message text (natives, stage dump, nc dump) live ONLY under D:\Projects\claude\_qa-scratch\ta-res (HK-037); deleted at job close.
SC=/d/Projects/claude/_qa-scratch
V=$SC/coh-res-cand-v2
R=$SC/ta-res
BIN=$V/bin_v2
PIN=bbde6eb66af4cd429ffc46f67291ba718c1ae36ae39665faac24629bcb6e6528
SEL500=$SC/cq-ap/sel_500.json
SEL500_SHA=c618a66e24bb0d129aa6f5df0ecdad978a53f4b0e9e991d308557378fef5de7f
WAVROOT=/d/Projects/claude/OpenWSFZ/artefacts
LIVE=$WAVROOT/20261110_1817_cq-ap-live
RUN=20261110_1817
O=$R/cap_run
w() { cygpath -w "$1"; }
sha() { sha256sum "$1" | cut -d' ' -f1; }
mkdir -p "$R"
LOG=$R/chain_status.txt
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$LOG"; }
die() { log "CHAIN HALT: $*"; exit 9; }
busy() { tasklist 2>/dev/null | grep -qiE 'jt9|OpenWSFZ.Daemon|Ft8.FitProbe|Replay81'; }
busy && die "a competing process is running before the capture arm"
[ "$(sha $BIN/libft8.dll)" = "$PIN" ] || die "libft8.dll differs from its pin before the arm"
[ "$(sha $SEL500)" = "$SEL500_SHA" ] || die "sel_500.json differs from the frozen selection"
rm -rf "$O"; mkdir -p "$O"
ST=$O/status.txt
tasklist 2>/dev/null | grep -qi 'wsjtx' && echo "wsjtx.exe present (open); idle is the Captain's word, recorded in the report" >> "$ST" || echo "wsjtx.exe not running" >> "$ST"
echo "start $(date -u +%FT%TZ) name=ta-res-capture cqap=0 cohrescand=1 dll=$(sha $BIN/libft8.dll)" >> "$ST"
log "TA-RES capture arm start (cohrescand 1, capture + provenance dumps)"
"$(w $BIN/Ft8.FitProbe.exe)" --selection "$(w $SEL500)" --run $RUN --stratum FULL --wav-root "$(w $WAVROOT)" --wav-dir "$(w $LIVE/owsfz/wav)" \
  --out "$(w $O/run.csv)" --log "$(w $O/log.log)" --nhard 24 --osd-sign-fix 1 --mode three1 --threads 8 --cohfb 1 --cohms 1 --cohaudio Both \
  --kmin 5 --osd-corr 0.05 --ungated 1 --late-round 1 --cq-ap 0 --cohrescand 1 --cohfb-out "$(w $O/coh.csv)" \
  --label "ta-res:capture" --wsjtx-alltxt "$(w $LIVE/wsjt-x/ALL.TXT)" --testb-out "$(w $O/testb.csv)" --matched-out "$(w $O/matched.csv)" --matched-batch-out "$(w $O/matchedbatch.csv)" \
  --third-out "$(w $O/third.csv)" --abandon-out "$(w $O/abandon.csv)" --outcomes "$(w $O/outcomes.csv)" --late-out "$(w $O/late.csv)" --nc-dump "$(w $O/nc.tsv)" \
  --cap-dir "$(w $O/cap)" --stage-out "$(w $O/stage.csv)" --gate-record 1 --stage-dump "$(w $O/stage_dump.tsv)" > "$O/stdout.txt" 2>&1
rc=$?; ok=1
[ "$(sha $BIN/libft8.dll)" = "$PIN" ] || { ok=0; echo "END dll pin mismatch" >> "$ST"; }
for tag in start end; do
  line=$(grep "^# readback $tag" "$O/log.log" | head -1)
  for need in "decodingDepth=Deep" "nhard=24" "osdSignFixRead=1" "cohfb=True" "cohms=True" "cohaudio=Both" "ungated=True" "lateround=True" "threadsResolved=8" "kMinScorePass2=5 " "osdCorrThreshold=0.05" "cqap=False" "cohrescand=True"; do
    echo "$line" | grep -q -- "$need" || { ok=0; echo "READBACK $tag missing: $need" >> "$ST"; }
  done
done
n=$(( $(wc -l < "$O/run.csv") - 1 ))
[ "$n" = "500" ] || { ok=0; echo "ROWS $n != 500" >> "$ST"; }
echo "exit $rc preflight_end_ok=$ok rows=$n at $(date -u +%FT%TZ)" >> "$ST"
log "capture arm done rc=$rc ok=$ok rows=$n"
busy && log "ORPHAN CHECK: a competing process is still running" || log "orphan check clean"
[ "$rc" = 0 ] && [ "$ok" = 1 ] || die "capture arm failed (rc=$rc ok=$ok)"
log "done"
