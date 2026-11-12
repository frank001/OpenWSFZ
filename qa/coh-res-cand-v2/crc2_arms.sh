#!/bin/bash
# COH-RES-CAND v2 arms (spec arch/coh-res-cand-v2 section 3 + Amendments 1 to 3; QA review b5e65309; the freeze record names this file's blob hash).
# usage:  bash crc2_arms.sh dry|boff|armb      PC EXCLUSIVE, station daemon stopped, WSJT-X closed or IDLE (recorded); run detached (nohup ... & disown), logged,
#         orphan-checked (HK-013/019/023). Every arm needs the Captain's go (the PC is his).
#   dry    3 cycles OUTSIDE the selection of the old night 20260930_1930 (late-sub/selection_3n_dry.json), --cohrescand 1: plumbing only (the res fields reach coh.csv, the
#          readbacks, the pin). Outputs discarded; the live window is NOT touched.
#   boff   B-OFF: the v2 build, --cohrescand 0, the FIRST 40 cycles of the 500 (same warm-up), compared by `crc2_analyse.py boff` with arm A's rows. STOPS: B-OFF is read BEFORE arm B.
#   armb   arm B: the v2 build, --cohrescand 1, the 500 cycles of live-session-cycle-list.txt.
# Arm A is REUSED, not re-run: _qa-scratch/cq-ap/arms/OFF (build 7ca00264 = 70bc72b1's tree, --cq-ap 0). Its command line is cqap_arms.sh's arm(); this one is IDENTICAL to it except
# for the build (59eb5a8f, bin_v2), the label, the output folder and the one setting under test (--cohrescand): --cq-ap 0 is kept in both legs on purpose (spec section 3).
# Message text (nc.tsv) lives ONLY under _qa-scratch (HK-037; the harness refuses any other path), deleted at v2's job close.
MODE=${1:?dry|boff|armb}
SC=/d/Projects/claude/_qa-scratch
V=$SC/coh-res-cand-v2
S=$V/arms
BIN=$V/bin_v2
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

arm() {   # arm <name> <selection> <rows> <cohrescand 0|1> <run> <wavdir> <wsjtx-alltxt> <outdir>
  local NAME=$1 SEL=$2 WANT=$3 RC=$4 RUNID=$5 WDIR=$6 WALL=$7 O=$8 ST=$8/status.txt
  busy && die "a competing process is running before $NAME"
  [ "$(sha $BIN/libft8.dll)" = "$PIN" ] || die "libft8.dll differs from its pin before $NAME"
  rm -rf "$O"; mkdir -p "$O"
  tasklist 2>/dev/null | grep -qi 'wsjtx' && echo "wsjtx.exe present (open); idle is the Captain's word, recorded in the report" >> "$ST" || echo "wsjtx.exe not running" >> "$ST"
  echo "start $(date -u +%FT%TZ) name=$NAME cqap=0 cohrescand=$RC dll=$(sha $BIN/libft8.dll)" >> "$ST"
  log "arm $NAME start (cohrescand $RC)"
  "$(w $BIN/Ft8.FitProbe.exe)" --selection "$(w $SEL)" --run $RUNID --stratum FULL --wav-root "$(w $WAVROOT)" --wav-dir "$(w $WDIR)" \
    --out "$(w $O/run.csv)" --log "$(w $O/log.log)" --nhard 24 --osd-sign-fix 1 --mode three1 --threads 8 --cohfb 1 --cohms 1 --cohaudio Both \
    --kmin 5 --osd-corr 0.05 --ungated 1 --late-round 1 --cq-ap 0 --cohrescand $RC --cohfb-out "$(w $O/coh.csv)" \
    --label "coh-res-cand-v2:$NAME" --wsjtx-alltxt "$(w $WALL)" --testb-out "$(w $O/testb.csv)" --matched-out "$(w $O/matched.csv)" --matched-batch-out "$(w $O/matchedbatch.csv)" \
    --third-out "$(w $O/third.csv)" --abandon-out "$(w $O/abandon.csv)" --outcomes "$(w $O/outcomes.csv)" --late-out "$(w $O/late.csv)" --nc-dump "$(w $O/nc.tsv)" > "$O/stdout.txt" 2>&1
  local rc=$? ok=1
  [ "$(sha $BIN/libft8.dll)" = "$PIN" ] || { ok=0; echo "END dll pin mismatch" >> "$ST"; }
  local WANTC="cohrescand=False"; [ "$RC" = 1 ] && WANTC="cohrescand=True"
  for tag in start end; do   # the arm's readback at the start and at the end of the process (V-SET of the CQ-AP arms, plus the setting under test)
    local line; line=$(grep "^# readback $tag" "$O/log.log" | head -1)
    for need in "decodingDepth=Deep" "nhard=24" "osdSignFixRead=1" "cohfb=True" "cohms=True" "cohaudio=Both" "ungated=True" "lateround=True" "threadsResolved=8" "kMinScorePass2=5 " "osdCorrThreshold=0.05" "cqap=False" "$WANTC"; do
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
    arm dry_ON $SC/late-sub/selection_3n_dry.json 3 1 20260930_1930 $G/owsfz/wav $G/wsjt-x/ALL.TXT $S/dry_ON ;;
  boff)  # the first 40 of the 500, the same warm-up (the process-global hash table then sees the same sequence as arm A did)
    [ "$(sha $SEL500)" = "$SEL500_SHA" ] || die "sel_500.json differs from the frozen selection"
    python - <<PY || die "selection build failed"
import json
d = json.load(open("$(cygpath -m $SEL500)")); r = d["runs"]["$RUN"]
x = json.loads(json.dumps(d)); x["runs"]["$RUN"] = {"warmup": r["warmup"], "FULL": r["FULL"][:40]}
x["note"] = "COH-RES-CAND v2 B-OFF: the first 40 of the 500 of sel_500.json (sha $SEL500_SHA), same warm-up"
json.dump(x, open("$(cygpath -m $V)/sel_40_live.json", "w"), indent=1, sort_keys=True)
PY
    echo "sel_40_live.json sha256 $(sha $V/sel_40_live.json)" >> "$LOG"
    arm B_OFF $V/sel_40_live.json 40 0 $RUN $LIVE/owsfz/wav $LIVE/wsjt-x/ALL.TXT $S/B_OFF ;;
  armb)  # B-OFF must have passed first
    [ "$(sha $SEL500)" = "$SEL500_SHA" ] || die "sel_500.json differs from the frozen selection"
    [ -s "$V/boff_result.json" ] && grep -q '"PASS": true' "$V/boff_result.json" || die "boff_result.json missing or not PASS: arm B does not start"
    arm B $SEL500 500 1 $RUN $LIVE/owsfz/wav $LIVE/wsjt-x/ALL.TXT $S/B ;;
esac
busy && log "ORPHAN CHECK: a competing process is still running" || log "orphan check clean"
log "$MODE done"
