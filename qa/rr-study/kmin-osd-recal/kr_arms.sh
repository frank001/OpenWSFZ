#!/bin/bash
# KMIN-OSD-RECAL arms, PC (spec arch/kmin-osd-recal sections 1-2, Amendments 1 and 2). Night 20260930_1930, the FIRST 400 of the 800-cycle selection 2575e115... (sel_400.json, the COH-RES-CAND file, SHA in the freeze).
# usage:  bash kr_arms.sh dry|A|B      PC EXCLUSIVE, station daemon stopped; run detached (nohup ... & disown), logged, orphan-checked (HK-013/019/023). The run needs the Captain's go (the PC is his).
#   dry  3 cycles OUTSIDE the selection (selection_3n_dry.json): plumbing only, arm A's and arm B's parameter sets; outputs discarded.
#   A    kMinScorePass2 10, osdCorrThreshold 0.10 (the code default, D-009).      B    kMinScorePass2 5, osdCorrThreshold 0.05 (the station's value).
# Both arms: Deep (three1), nhard 24, OSD sign fix 1, multi-set ON, coherentFallbackAudio Both, R-F4 ON (--ungated 1), L1' ON (--late-round 1), 8 threads: today's decoder as it will run after the default-ON deploy.
# Build: Replay81 at the freeze's commit, -p:HasSubfeas -p:HasMaxThreads -p:HasTwoStage -p:HasOsdSignFix -p:HasThirdPass -p:HasCohFb -p:HasCohFb4 -p:HasLateRound -p:HasCohMs -p:HasCohAudio -p:HasInternals -p:HasUngated,
#   RepoRoot = _qa-scratch/kmin-osd-recal/tree at ef2fc84b; libft8.dll = the pin. Message text (nc-dump) lives ONLY under _qa-scratch (HK-037).
MODE=${1:?dry|A|B}
S=/d/Projects/claude/_qa-scratch/kmin-osd-recal
LS=/d/Projects/claude/_qa-scratch/late-sub
PIN=1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914
RUN=20260930_1930
WAVROOT=/d/Projects/claude/OpenWSFZ/artefacts
G=$WAVROOT/${RUN}_endurance_run-gathered
ALLTXT=$G/wsjt-x/ALL.TXT
SEL400=/d/Projects/claude/_qa-scratch/coh-res-cand/sel_400.json
SEL400_SHA=$(sha256sum "$SEL400" | cut -d' ' -f1)
RAW=$S/raw; SCR=$S/scratch
[ "$MODE" = dry ] && { RAW=$S/raw_dry; SCR=$S/scratch_dry; }
mkdir -p "$RAW" "$SCR"
STATUS_ALL=$RAW/chain_status.txt
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$STATUS_ALL"; }
die() { log "CHAIN HALT: $*"; exit 9; }
w() { cygpath -w "$1"; }
sha() { sha256sum "$1" | cut -d' ' -f1; }
BIN=$S/bin
[ "$(sha $BIN/libft8.dll)" = "$PIN" ] || die "libft8.dll differs from its pin at chain start"
[ -s "$ALLTXT" ] || die "WSJT-X ALL.TXT for the night is missing"
busy() { tasklist 2>/dev/null | grep -qiE 'wsjtx|jt9|OpenWSFZ.Daemon|Ft8.FitProbe|Replay81'; }

arm() {   # arm <name> <selection> <rows> <kmin> <osd>
  local NAME=$1 SELF=$2 WANT=$3 KMIN=$4 OSD=$5 O=$RAW/$1 SC=$SCR/$1 ST=$RAW/$1_status.txt
  busy && die "a competing process is running before $NAME"
  [ "$(sha $BIN/libft8.dll)" = "$PIN" ] || die "pin at start of $NAME"
  rm -rf "$O" "$SC"; mkdir -p "$O" "$SC"
  echo "start $(date -u +%FT%TZ) name=$NAME kmin=$KMIN osd=$OSD dll=$(sha $BIN/libft8.dll)" > "$ST"
  log "arm $NAME start (kmin $KMIN osd $OSD)"
  "$(w $BIN/Ft8.FitProbe.exe)" --selection "$(w $SELF)" --run $RUN --stratum FULL --wav-root "$(w $WAVROOT)" --wav-dir "$(w $G/owsfz/wav)" \
    --out "$(w $O/run.csv)" --log "$(w $O/log.log)" --nhard 24 --osd-sign-fix 1 --mode three1 --threads 8 --cohfb 1 --cohms 1 --cohaudio Both \
    --kmin $KMIN --osd-corr $OSD --ungated 1 --late-round 1 --cohfb-out "$(w $O/coh.csv)" \
    --label "kmin-osd-recal:$NAME" --wsjtx-alltxt "$(w $ALLTXT)" --testb-out "$(w $O/testb.csv)" --matched-out "$(w $O/matched.csv)" --matched-batch-out "$(w $O/matchedbatch.csv)" \
    --third-out "$(w $O/third.csv)" --abandon-out "$(w $O/abandon.csv)" --outcomes "$(w $O/outcomes.csv)" --late-out "$(w $O/late.csv)" --nc-dump "$(w $SC/nc_dump.tsv)" > "$O/stdout.txt" 2>&1
  local rc=$? ok=1
  [ "$(sha $BIN/libft8.dll)" = "$PIN" ] || { ok=0; echo "END dll pin mismatch" >> "$ST"; }
  for tag in start end; do   # V-SET: exactly this arm's table values, read back at the start and the end of the process
    local line; line=$(grep "^# readback $tag" "$O/log.log" | head -1)
    for need in "decodingDepth=Deep" "nhard=24" "osdSignFixRead=1" "shim=20260071" "cohfb=True" "cohms=True" "cohaudio=Both" "ungated=True" "lateround=True" "threadsResolved=8" "kMinScorePass2=$KMIN" "osdCorrThreshold=$OSD"; do
      echo "$line" | grep -q -- "$need" || { ok=0; echo "READBACK $tag missing: $need | $line" >> "$ST"; }
    done
  done
  local n; n=$(( $(wc -l < "$O/run.csv") - 1 ))
  [ "$n" = "$WANT" ] || { ok=0; echo "ROWS $n != $WANT" >> "$ST"; }
  local nl; nl=$(grep -c "Late subtraction round:" "$O/log.log"); [ "$nl" -gt 0 ] || { ok=0; echo "no 'Late subtraction round:' line in an L1' ON arm" >> "$ST"; }
  echo "exit $rc preflight_end_ok=$ok rows=$n late_lines=$nl at $(date -u +%FT%TZ)" >> "$ST"
  log "arm $NAME done rc=$rc ok=$ok rows=$n late_lines=$nl"
  [ "$rc" = 0 ] && [ "$ok" = 1 ] || die "arm $NAME failed (rc=$rc ok=$ok)"
}

case $MODE in
  dry)
    SEL_DRY=$LS/selection_3n_dry.json
    arm dry_A $SEL_DRY 3 10 0.10
    arm dry_B $SEL_DRY 3 5 0.05 ;;
  A) arm A $SEL400 400 10 0.10 ;;
  B) arm B $SEL400 400 5 0.05 ;;
esac
busy && log "ORPHAN CHECK: a competing process is still running" || log "orphan check clean"
[ "$(sha $BIN/libft8.dll)" = "$PIN" ] && log "END pin OK" || log "END pin FAIL"
log "$MODE done (selection sha $SEL400_SHA)"
