#!/bin/bash
# CQ-AP arms (spec arch/cq-ap, Amendments 1-3; freeze Part 1 342d320b, Part 2 = the addendum that names this file's blob hash).
# usage:  bash cqap_arms.sh dry|OFF|ON|OFF2|REF       PC EXCLUSIVE, station daemon stopped, WSJT-X IDLE (the Captain's word); run detached
#         (nohup ... & disown), logged, orphan-checked (HK-013/019/023). Every arm needs the Captain's go (the PC is his).
#   dry   40 cycles of the OLD night 20260930_1930 (sel_40.json, the same plumbing check as the first dry run), OFF then ON; outputs discarded; the live window is NOT touched.
#   OFF   build 7ca00264, --cq-ap 0, the 500 cycles of live-session-cycle-list.txt.      ON    the same build and DLL, --cq-ap 1.
#   OFF2  OFF again (the OFF-vs-OFF repeat line).                                        REF   build 98332f2a (no --cq-ap), the FIRST 50 cycles (V-OFF reference).
# Both CQ-AP arms use the live configuration of the session: Deep (three1), nhard 24, OSD sign fix 1, multi-set ON, coherentFallbackAudio Both, kMinScorePass2 5,
# osdCorrThreshold 0.05, R-F4 ON (--ungated 1), L1' ON (--late-round 1), 8 threads (read back and compared by V-SET).
# Message text (nc.tsv) lives ONLY under _qa-scratch (HK-037; the harness refuses any other path).
MODE=${1:?dry|OFF|ON|OFF2|REF}
SC=/d/Projects/claude/_qa-scratch
S=$SC/cq-ap/arms
WAVROOT=/d/Projects/claude/OpenWSFZ/artefacts
PIN_ON=bbde6eb66af4cd429ffc46f67291ba718c1ae36ae39665faac24629bcb6e6528
PIN_REF=1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914
BIN_ON=$SC/cq-ap/bin_on
BIN_REF=$SC/cq-ap/bin_ref
LIVE=$WAVROOT/20261110_1817_cq-ap-live
RUN=20261110_1817
SEL500=$SC/cq-ap/sel_500.json
SEL50=$SC/cq-ap/sel_50.json
w() { cygpath -w "$1"; }
sha() { sha256sum "$1" | cut -d' ' -f1; }
mkdir -p "$S"
LOG=$S/chain_status.txt
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$LOG"; }
die() { log "CHAIN HALT: $*"; exit 9; }
busy() { tasklist 2>/dev/null | grep -qiE 'jt9|OpenWSFZ.Daemon|Ft8.FitProbe|Replay81'; }

arm() {   # arm <name> <bin> <pin> <selection> <rows> <cqap|none> <run> <wavdir> <wsjtx-alltxt> <expect-cqap-token>
  local NAME=$1 BIN=$2 PIN=$3 SEL=$4 WANT=$5 CQ=$6 RUNID=$7 WDIR=$8 WALL=$9 TOK=${10} O=$S/$1 ST=$S/$1/status.txt
  busy && die "a competing process is running before $NAME"
  [ "$(sha $BIN/libft8.dll)" = "$PIN" ] || die "libft8.dll differs from its pin before $NAME"
  rm -rf "$O"; mkdir -p "$O"
  tasklist 2>/dev/null | grep -qi 'wsjtx' && echo "wsjtx.exe present (open); idle is the Captain's word, recorded in the Part 2 addendum" >> "$ST" || echo "wsjtx.exe not running" >> "$ST"
  echo "start $(date -u +%FT%TZ) name=$NAME cqap=$CQ dll=$(sha $BIN/libft8.dll)" >> "$ST"
  log "arm $NAME start (cqap $CQ)"
  local CQARG=""; [ "$CQ" != none ] && CQARG="--cq-ap $CQ"
  "$(w $BIN/Ft8.FitProbe.exe)" --selection "$(w $SEL)" --run $RUNID --stratum FULL --wav-root "$(w $WAVROOT)" --wav-dir "$(w $WDIR)" \
    --out "$(w $O/run.csv)" --log "$(w $O/log.log)" --nhard 24 --osd-sign-fix 1 --mode three1 --threads 8 --cohfb 1 --cohms 1 --cohaudio Both \
    --kmin 5 --osd-corr 0.05 --ungated 1 --late-round 1 $CQARG --cohfb-out "$(w $O/coh.csv)" \
    --label "cq-ap:$NAME" --wsjtx-alltxt "$(w $WALL)" --testb-out "$(w $O/testb.csv)" --matched-out "$(w $O/matched.csv)" --matched-batch-out "$(w $O/matchedbatch.csv)" \
    --third-out "$(w $O/third.csv)" --abandon-out "$(w $O/abandon.csv)" --outcomes "$(w $O/outcomes.csv)" --late-out "$(w $O/late.csv)" --nc-dump "$(w $O/nc.tsv)" > "$O/stdout.txt" 2>&1
  local rc=$? ok=1
  [ "$(sha $BIN/libft8.dll)" = "$PIN" ] || { ok=0; echo "END dll pin mismatch" >> "$ST"; }
  for tag in start end; do   # preflight copy of V-SET (the analysis recomputes it): this arm's readback at the start and at the end of the process
    local line; line=$(grep "^# readback $tag" "$O/log.log" | head -1)
    for need in "decodingDepth=Deep" "nhard=24" "osdSignFixRead=1" "cohfb=True" "cohms=True" "cohaudio=Both" "ungated=True" "lateround=True" "threadsResolved=8" "kMinScorePass2=5 " "osdCorrThreshold=0.05" $TOK; do
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
  dry)   # old night, plumbing only (outputs discarded); the live window is not read
    SCD=$SC/cq-ap-review; G=$WAVROOT/20260930_1930_endurance_run-gathered
    S=$SC/cq-ap/arms_dry; mkdir -p "$S"; LOG=$S/chain_status.txt
    arm dry_OFF $BIN_ON $PIN_ON $SCD/sel_40.json 40 0 20260930_1930 $G/owsfz/wav $G/wsjt-x/ALL.TXT "cqap=False"
    arm dry_ON  $BIN_ON $PIN_ON $SCD/sel_40.json 40 1 20260930_1930 $G/owsfz/wav $G/wsjt-x/ALL.TXT "cqap=True" ;;
  OFF)  arm OFF  $BIN_ON  $PIN_ON  $SEL500 500 0    $RUN $LIVE/owsfz/wav $LIVE/wsjt-x/ALL.TXT "cqap=False" ;;
  ON)   arm ON   $BIN_ON  $PIN_ON  $SEL500 500 1    $RUN $LIVE/owsfz/wav $LIVE/wsjt-x/ALL.TXT "cqap=True" ;;
  OFF2) arm OFF2 $BIN_ON  $PIN_ON  $SEL500 500 0    $RUN $LIVE/owsfz/wav $LIVE/wsjt-x/ALL.TXT "cqap=False" ;;
  REF)  arm REF  $BIN_REF $PIN_REF $SEL50  50  none $RUN $LIVE/owsfz/wav $LIVE/wsjt-x/ALL.TXT "shim=20260071" ;;
esac
busy && log "ORPHAN CHECK: a competing process is still running" || log "orphan check clean"
log "$MODE done"
