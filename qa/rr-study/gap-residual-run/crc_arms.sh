#!/bin/bash
# COH-RES-CAND (#272) acceptance arms, PC (spec section 3 + Amendments 1 to 3). Night 20260930_1930 (L1' third night), the FIRST 400 of the 800-cycle selection 2575e115...
# usage:  bash crc_arms.sh dry|stage1|stage2        PC; run detached (nohup ... & disown), logged, orphan-checked (HK-013/019/023). The run needs the Captain's go (given 2026-11-08).
#   dry     3 cycles OUTSIDE the selection (selection_3n_dry.json): plumbing only (the new fallback-line fields reach log.log, the readbacks, the row counts). Outputs discarded.
#   stage1  B-OFF (40 cycles: main fe1454c1 build, then the new build with --cohrescand 0) then arm A (new build, --cohrescand 0, 400 cycles). STOPS: V1-3N is read before arm B.
#   stage2  arm B (new build, --cohrescand 1, 400 cycles).
# Builds: Replay81 (harness commit recorded in the freeze) built with -p:HasSubfeas=true -p:HasMaxThreads=true -p:HasTwoStage=true -p:HasOsdSignFix=true -p:HasThirdPass=true -p:HasCohFb=true
#   -p:HasCohFb4=true -p:HasLateRound=true -p:HasCohMs=true -p:HasCohAudio=true -p:HasInternals=true -p:HasUngated=true [-p:HasCohResCand=true] against
#   bin_new = b0d01f4f (feat/coh-res-cand, v0.69, the build under test), bin_main = fe1454c1 (main, v0.68, the B-OFF reference). Both carry libft8.dll = the pin.
# Settings = the L1' PC arms' (f5_arm.sh): mode three1 (Deep), nhard 24, OSD sign fix 1, 8 threads, multi-set ON, coherentFallbackAudio Both, R-F4 OFF, late round OFF (flags absent).
# Message text (nc-dump) lives ONLY under _qa-scratch (HK-037); deleted at job close.
MODE=${1:?dry|stage1|stage2}
S=/d/Projects/claude/_qa-scratch/coh-res-cand
LS=/d/Projects/claude/_qa-scratch/late-sub
PIN=1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914
RUN=20260930_1930
WAVROOT=/d/Projects/claude/OpenWSFZ/artefacts
G=$WAVROOT/${RUN}_endurance_run-gathered
ALLTXT=$G/wsjt-x/ALL.TXT
SEL_FULL=$LS/selection_3n.json
SEL_FULL_SHA=2575e115378c71c068cd250d26dd002a17d7d365366cd00e6aaa3a99d2329c4f
RAW=$S/raw; SCR=$S/scratch
[ "$MODE" = dry ] && { RAW=$S/raw_dry; SCR=$S/scratch_dry; }
mkdir -p "$RAW" "$SCR"
STATUS_ALL=$RAW/chain_status.txt
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$STATUS_ALL"; }
die() { log "CHAIN HALT: $*"; exit 9; }
w() { cygpath -w "$1"; }
sha() { sha256sum "$1" | cut -d' ' -f1; }
for b in bin_new bin_main; do [ "$(sha $S/$b/libft8.dll)" = "$PIN" ] || die "$b libft8.dll differs from its pin at chain start"; done
[ "$(sha $SEL_FULL)" = "$SEL_FULL_SHA" ] || die "selection_3n.json differs from the frozen one"
[ -s "$ALLTXT" ] || die "WSJT-X ALL.TXT for the night is missing"
busy() { tasklist 2>/dev/null | grep -qiE 'wsjtx|jt9|OpenWSFZ.Daemon|Ft8.FitProbe|Replay81'; }
# selections: the first N of the frozen selection (same warm-up), written once, SHA-256 in the freeze
python - <<PY || die "selection build failed"
import json
d = json.load(open("$(cygpath -m $SEL_FULL)")); r = d["runs"]["$RUN"]
for n, name in ((400, "sel_400.json"), (40, "sel_40.json")):
    x = json.loads(json.dumps(d)); x["runs"]["$RUN"] = {"warmup": r["warmup"], "FULL": r["FULL"][:n]}
    x["note"] = "COH-RES-CAND: the first %d of the 800-cycle selection 2575e115" % n
    json.dump(x, open("$(cygpath -m $S)/" + name, "w"), indent=1, sort_keys=True)
PY

arm() {   # arm <name> <bin> <selection> <rows> <extra: --cohrescand 0|1 or empty> <expect cohrescand True|False|none>
  local NAME=$1 BIN=$2 SELF=$3 WANT=$4 EXTRA=$5 WANTC=$6 O=$RAW/$1 SC=$SCR/$1 ST=$RAW/$1_status.txt
  busy && die "a competing process is running before $NAME"
  [ "$(sha $S/$BIN/libft8.dll)" = "$PIN" ] || die "$BIN pin at start of $NAME"
  rm -rf "$O" "$SC"; mkdir -p "$O" "$SC"
  echo "start $(date -u +%FT%TZ) name=$NAME bin=$BIN extra='$EXTRA' dll=$(sha $S/$BIN/libft8.dll)" > "$ST"
  log "arm $NAME start ($BIN $EXTRA)"
  "$(w $S/$BIN/Ft8.FitProbe.exe)" --selection "$(w $SELF)" --run $RUN --stratum FULL --wav-root "$(w $WAVROOT)" --wav-dir "$(w $G/owsfz/wav)" \
    --out "$(w $O/run.csv)" --log "$(w $O/log.log)" --nhard 24 --osd-sign-fix 1 --mode three1 --threads 8 --cohfb 1 --cohms 1 --cohaudio Both $EXTRA --cohfb-out "$(w $O/coh.csv)" \
    --label "coh-res-cand:$NAME:$BIN" --wsjtx-alltxt "$(w $ALLTXT)" --testb-out "$(w $O/testb.csv)" --matched-out "$(w $O/matched.csv)" --matched-batch-out "$(w $O/matchedbatch.csv)" \
    --third-out "$(w $O/third.csv)" --abandon-out "$(w $O/abandon.csv)" --outcomes "$(w $O/outcomes.csv)" --nc-dump "$(w $SC/nc_dump.tsv)" > "$O/stdout.txt" 2>&1
  local rc=$? ok=1
  [ "$(sha $S/$BIN/libft8.dll)" = "$PIN" ] || { ok=0; echo "END dll pin mismatch" >> "$ST"; }
  for tag in start end; do
    local line; line=$(grep "^# readback $tag" "$O/log.log" | head -1)
    for need in "decodingDepth=Deep" "nhard=24" "osdSignFixRead=1" "shim=20260071" "cohfb=True" "cohms=True" "cohaudio=Both" "ungated=False" "lateround=False" "threadsResolved=8"; do
      echo "$line" | grep -q "$need" || { ok=0; echo "READBACK $tag missing: $need | $line" >> "$ST"; }
    done
    if [ "$WANTC" != none ]; then echo "$line" | grep -q "cohrescand=$WANTC" || { ok=0; echo "READBACK $tag missing: cohrescand=$WANTC | $line" >> "$ST"; }; fi
  done
  local n; n=$(( $(wc -l < "$O/run.csv") - 1 ))
  [ "$n" = "$WANT" ] || { ok=0; echo "ROWS $n != $WANT" >> "$ST"; }
  local nl; nl=$(grep -c "Late subtraction round:" "$O/log.log"); [ "$nl" = "0" ] || { ok=0; echo "R6 lines $nl != 0" >> "$ST"; }
  local nrc; nrc=$(grep -c "resCand=" "$O/log.log")
  if [ "$WANTC" = True ]; then [ "$nrc" -gt 0 ] || { ok=0; echo "no resCand field in an ON arm" >> "$ST"; }; else [ "$nrc" = "0" ] || { ok=0; echo "resCand fields $nrc in an OFF arm" >> "$ST"; }; fi
  echo "exit $rc preflight_end_ok=$ok rows=$n resCand_lines=$nrc at $(date -u +%FT%TZ)" >> "$ST"
  log "arm $NAME done rc=$rc ok=$ok rows=$n resCand_lines=$nrc"
  [ "$rc" = 0 ] && [ "$ok" = 1 ] || die "arm $NAME failed (rc=$rc ok=$ok)"
}

case $MODE in
  dry)
    SEL_DRY=$LS/selection_3n_dry.json
    arm dry_off bin_new $SEL_DRY 3 "--cohrescand 0" False
    arm dry_on  bin_new $SEL_DRY 3 "--cohrescand 1" True ;;
  stage1)
    arm bo_main bin_main $S/sel_40.json  40  ""                none
    arm bo_new  bin_new  $S/sel_40.json  40  "--cohrescand 0"  False
    arm A       bin_new  $S/sel_400.json 400 "--cohrescand 0"  False ;;
  stage2)
    arm B       bin_new  $S/sel_400.json 400 "--cohrescand 1"  True ;;
esac
busy && log "ORPHAN CHECK: a competing process is still running" || log "orphan check clean"
for b in bin_new bin_main; do [ "$(sha $S/$b/libft8.dll)" = "$PIN" ] && log "END $b pin OK" || log "END $b pin FAIL"; done
log "$MODE done"
