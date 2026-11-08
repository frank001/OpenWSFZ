#!/bin/bash
# LATE-SUB L1 build acceptance rows B-NAT / B-OFF / B-EQ-1 / B-EQ-2 / B-AB on the PC (build spec 33c50bd6 section 3; HK-039 record c55276ae for b1d8a06e). Arms: off (--late-round absent) then on (--late-round 1).
# Run: nohup bash lr_arms.sh > chain_lr.out 2>&1 & disown
# Build: stock Replay81 (qa/refset, -p:HasLateRound=true, NO internals wrapper) against the Developer tree b1d8a06e (_qa-scratch/late-sub/dev-tree) -> bin_dev; libft8.dll SHA-256 pinned below, re-hashed at the start and end of EVERY arm.
# Settings = the station's: mode three1 (Deep), nhard 24, OSD sign fix 1, 8 threads, multi-set ON, coherentFallbackAudio Both.
#   arm off : --late-round NOT passed (the setting absent = false)          arm on : --late-round 1
# Cycles 1-1200 of the frozen selection (TRAIN 1-400 + TEST 401-1200). Working files with message text live ONLY under D:\Projects\claude\_qa-scratch (HK-037).
S=/d/Projects/claude/_qa-scratch/late-sub
BIN=$S/bin_dev
DLL=$BIN/libft8.dll
PIN=1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914
SEL=/d/Projects/claude/_qa-scratch/coh-gate-r-f4/selection1200.json
RUN=20260925_2010
WAVROOT=/d/Projects/claude/OpenWSFZ/artefacts
G=$WAVROOT/${RUN}_endurance_run-gathered
ALLTXT=$G/wsjt-x/ALL.TXT
RAW=$S/raw_lr
SCR=$S/scratch_lr
mkdir -p "$RAW" "$SCR"
STATUS_ALL=$RAW/chain_status.txt
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$STATUS_ALL"; }
die() { log "CHAIN HALT: $*"; exit 9; }
w() { cygpath -w "$1"; }
sha() { sha256sum "$1" | cut -d' ' -f1; }
[ "$(sha "$DLL")" = "$PIN" ] || die "libft8.dll differs from its pin at chain start"
[ "$(ls $G/owsfz/wav | wc -l)" = 2884 ] || die "audio folder does not hold 2884 WAVs"
log "L1 build b1d8a06e arms (off, on) (cycles 1-1200, one process) start; dll=$PIN; selection sha=$(sha $SEL)"
busy() { tasklist 2>/dev/null | grep -qiE 'wsjtx|jt9|OpenWSFZ.Daemon|Ft8.FitProbe|Replay81'; }

arm() {   # arm <name> <extra args> <expect ungated True|False>
  local NAME=$1 EXTRA=$2 WANTL=$3 O=$RAW/$1 SC=$SCR/$1 ST=$RAW/$1_status.txt
  busy && die "a competing process is running before $NAME"
  [ "$(sha "$DLL")" = "$PIN" ] || die "dll pin at start of $NAME"
  rm -rf "$O" "$SC"; mkdir -p "$O" "$SC"
  echo "start $(date -u +%FT%TZ) name=$NAME extra='$EXTRA' dll=$(sha "$DLL")" > "$ST"
  log "arm $NAME start ($EXTRA)"
  dotnet "$(w $BIN/Replay81.dll)" --selection "$(w $SEL)" --run $RUN --stratum FULL --wav-root "$(w $WAVROOT)" --wav-dir "$(w $G/owsfz/wav)" \
    --out "$(w $O/run.csv)" --log "$(w $O/log.log)" --nhard 24 --osd-sign-fix 1 --mode three1 --threads 8 --cohfb 1 --cohms 1 --cohaudio Both $EXTRA --cohfb-out "$(w $O/coh.csv)" \
    --label "late-round:$NAME:b1d8a06e" --wsjtx-alltxt "$(w $ALLTXT)" --testb-out "$(w $O/testb.csv)" --matched-out "$(w $O/matched.csv)" --matched-batch-out "$(w $O/matchedbatch.csv)" \
    --third-out "$(w $O/third.csv)" --abandon-out "$(w $O/abandon.csv)" --outcomes "$(w $O/outcomes.csv)" --nc-dump "$(w $SC/nc_dump.tsv)" > "$O/stdout.txt" 2>&1
  local rc=$?
  local ok=1
  [ "$(sha "$DLL")" = "$PIN" ] || { ok=0; echo "END dll pin mismatch" >> "$ST"; }
  for tag in start end; do
    local line; line=$(grep "^# readback $tag" "$O/log.log" | head -1)
    for need in "decodingDepth=Deep" "nhard=24" "osdSignFixRead=1" "shim=20260071" "cohfb=True" "cohms=True" "cohaudio=Both" "$WANTL"; do
      echo "$line" | grep -q "$need" || { ok=0; echo "READBACK $tag missing: $need | $line" >> "$ST"; }
    done
  done
  local n; n=$(( $(wc -l < "$O/run.csv") - 1 ))
  [ "$n" = "1200" ] || { ok=0; echo "ROWS $n != 1200" >> "$ST"; }
  echo "exit $rc preflight_end_ok=$ok rows=$n at $(date -u +%FT%TZ)" >> "$ST"
  log "arm $NAME done rc=$rc ok=$ok rows=$n"
  [ "$rc" = 0 ] && [ "$ok" = 1 ] || die "arm $NAME failed (rc=$rc ok=$ok)"
}

arm off "" lateround=False
arm on "--late-round 1" lateround=True
busy && log "ORPHAN CHECK: a competing process is still running" || log "orphan check clean"
[ "$(sha "$DLL")" = "$PIN" ] && log "END dll pin OK" || log "END dll pin FAIL"
log "chain done"
