#!/bin/bash
# LATE-SUB L1' B-TOOL-2 (Architect ruling 73dc9036 s4): Replay81 with ThirdProbe first-line-wins, late.csv (--late-out) and the R6 whitelist, against the Developer tree b1d8a06e.
# Refset 20260925_2010, cycles 1-60 of the frozen selection (selection60.json = its first 60 stamps), ONE process per arm: OFF (--late-round absent) then ON (--late-round 1).
# Build (bin_t2): Replay81 -p:RepoRoot=<dev-tree> -p:HasSubfeas -HasMaxThreads -HasTwoStage -HasOsdSignFix -HasThirdPass -HasCohFb -HasCohFb4 -HasLateRound -HasCohMs -HasCohAudio (same as the s3 arms; no Dxped: the Developer tree has no such member).
# Settings = the station's, as lr_arms.sh. Message text lives only under D:\Projects\claude\_qa-scratch (HK-037).
S=/d/Projects/claude/_qa-scratch/late-sub
BIN=$S/bin_t2
DLL=$BIN/libft8.dll
PIN=1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914
SEL=$S/selection60.json
RUN=20260925_2010
WAVROOT=/d/Projects/claude/OpenWSFZ/artefacts
G=$WAVROOT/${RUN}_endurance_run-gathered
ALLTXT=$G/wsjt-x/ALL.TXT
RAW=$S/raw_t2
SCR=$S/scratch_t2
mkdir -p "$RAW" "$SCR"
STATUS_ALL=$RAW/chain_status.txt
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$STATUS_ALL"; }
die() { log "CHAIN HALT: $*"; exit 9; }
w() { cygpath -w "$1"; }
sha() { sha256sum "$1" | cut -d' ' -f1; }
[ "$(sha "$DLL")" = "$PIN" ] || die "libft8.dll differs from its pin at chain start"
[ "$(ls $G/owsfz/wav | wc -l)" = 2884 ] || die "audio folder does not hold 2884 WAVs"
log "B-TOOL-2 arms (off, on) cycles 1-60 start; dll=$PIN; selection sha=$(sha $SEL)"
busy() { tasklist 2>/dev/null | grep -qiE 'wsjtx|jt9|OpenWSFZ.Daemon|Ft8.FitProbe|Replay81'; }

arm() {   # arm <name> <extra args> <expect lateround True|False>
  local NAME=$1 EXTRA=$2 WANTL=$3 O=$RAW/$1 SC=$SCR/$1 ST=$RAW/$1_status.txt
  busy && die "a competing process is running before $NAME"
  rm -rf "$O" "$SC"; mkdir -p "$O" "$SC"
  echo "start $(date -u +%FT%TZ) name=$NAME extra='$EXTRA' dll=$(sha "$DLL")" > "$ST"
  log "arm $NAME start ($EXTRA)"
  dotnet "$(w $BIN/Replay81.dll)" --selection "$(w $SEL)" --run $RUN --stratum FULL --wav-root "$(w $WAVROOT)" --wav-dir "$(w $G/owsfz/wav)" \
    --out "$(w $O/run.csv)" --log "$(w $O/log.log)" --nhard 24 --osd-sign-fix 1 --mode three1 --threads 8 --cohfb 1 --cohms 1 --cohaudio Both $EXTRA --cohfb-out "$(w $O/coh.csv)" \
    --label "t2:$NAME:b1d8a06e" --wsjtx-alltxt "$(w $ALLTXT)" --testb-out "$(w $O/testb.csv)" --matched-out "$(w $O/matched.csv)" --matched-batch-out "$(w $O/matchedbatch.csv)" \
    --third-out "$(w $O/third.csv)" --abandon-out "$(w $O/abandon.csv)" --outcomes "$(w $O/outcomes.csv)" --late-out "$(w $O/late.csv)" --nc-dump "$(w $SC/nc_dump.tsv)" > "$O/stdout.txt" 2>&1
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
  [ "$n" = "60" ] || { ok=0; echo "ROWS $n != 60" >> "$ST"; }
  echo "exit $rc ok=$ok rows=$n at $(date -u +%FT%TZ)" >> "$ST"
  log "arm $NAME done rc=$rc ok=$ok rows=$n"
  [ "$rc" = 0 ] && [ "$ok" = 1 ] || die "arm $NAME failed (rc=$rc ok=$ok)"
}

arm off "" lateround=False
arm on "--late-round 1" lateround=True
busy && log "ORPHAN CHECK: a competing process is still running" || log "orphan check clean"
[ "$(sha "$DLL")" = "$PIN" ] && log "END dll pin OK" || log "END dll pin FAIL"
log "chain done"
