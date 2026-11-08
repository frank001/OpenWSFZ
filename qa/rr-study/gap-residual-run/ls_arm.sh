#!/bin/bash
# LATE-SUB (spec 5c33391f + Amendment 1 e2f7c5b2). ONE process, the selection's cycles in order, from cycle 1; the product's batches 1-4 then the arm work per cycle (LateSub.cs).
# usage: ls_arm.sh <name> <selection json> [ungated 0|1]       PC; detached, logged, orphan-checked (HK-013/019/023). Captain's go: "go", 2026-10-29.
# Build: Replay81 (qa/refset, -p:HasInternals=true -p:HasUngated=true) against main c2c85c45; libft8.dll SHA-256 pinned below, re-hashed at the start and end.
# Settings = the station's: mode three1 (Deep), nhard 24, OSD sign fix 1, 8 threads, multi-set ON, coherentFallbackAudio Both; --ungated only when asked (ON); absent = the shipped default (OFF).
# Message text lives ONLY under D:\Projects\claude\_qa-scratch (HK-037); deleted at job close.
NAME=${1:?name}; SEL=${2:?selection json}; UNG=${3:-}
S=/d/Projects/claude/_qa-scratch/late-sub
BIN=$S/bin
DLL=$BIN/libft8.dll
PIN=1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914
RUN=20260925_2010
WAVROOT=/d/Projects/claude/OpenWSFZ/artefacts
G=$WAVROOT/${RUN}_endurance_run-gathered
ALLTXT=$G/wsjt-x/ALL.TXT
O=$S/raw/$NAME; SC=$S/scratch/$NAME; LS=$S/ls/$NAME
STATUS_ALL=$S/raw/chain_status.txt
mkdir -p "$S/raw" "$S/scratch" "$S/ls"
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$STATUS_ALL"; }
die() { log "CHAIN HALT: $*"; exit 9; }
w() { cygpath -w "$1"; }
sha() { sha256sum "$1" | cut -d' ' -f1; }
[ "$(sha "$DLL")" = "$PIN" ] || die "libft8.dll differs from its pin at start"
[ "$(ls $G/owsfz/wav | wc -l)" = 2884 ] || die "audio folder does not hold 2884 WAVs"
tasklist 2>/dev/null | grep -qiE 'wsjtx|jt9|OpenWSFZ.Daemon|Ft8.FitProbe|Replay81' && die "a competing process is running"
rm -rf "$O" "$SC" "$LS"; mkdir -p "$O" "$SC" "$LS"
EXTRA=""; [ -n "$UNG" ] && EXTRA="--ungated $UNG"
log "LATE-SUB arm $NAME start; dll=$PIN; selection sha=$(sha $SEL); ungated=${UNG:-absent}"
"$(w $BIN/Ft8.FitProbe.exe)" --selection "$(w $SEL)" --run $RUN --stratum FULL --wav-root "$(w $WAVROOT)" --wav-dir "$(w $G/owsfz/wav)" \
  --out "$(w $O/run.csv)" --log "$(w $O/log.log)" --nhard 24 --osd-sign-fix 1 --mode three1 --threads 8 --cohfb 1 --cohms 1 --cohaudio Both --cohfb-out "$(w $O/coh.csv)" \
  --label "late-sub:$NAME:c2c85c45" --wsjtx-alltxt "$(w $ALLTXT)" --testb-out "$(w $O/testb.csv)" --matched-out "$(w $O/matched.csv)" --matched-batch-out "$(w $O/matchedbatch.csv)" \
  --third-out "$(w $O/third.csv)" --abandon-out "$(w $O/abandon.csv)" --outcomes "$(w $O/outcomes.csv)" --nc-dump "$(w $SC/nc_dump.tsv)" \
  --impl-dump "$(w $SC/impl_dump.tsv)" --stage-out "$(w $O/stage.csv)" --stage-dump "$(w $SC/stage_dump.tsv)" --late-sub-dir "$(w $LS)" $EXTRA > "$O/stdout.txt" 2>&1
rc=$?
ok=1
[ "$(sha "$DLL")" = "$PIN" ] || { ok=0; log "END dll pin mismatch"; }
for tag in start end; do
  line=$(grep "^# readback $tag" "$O/log.log" | head -1)
  for need in "decodingDepth=Deep" "nhard=24" "osdSignFixRead=1" "shim=20260071" "cohfb=True" "cohms=True"; do
    echo "$line" | grep -q "$need" || { ok=0; log "READBACK $tag missing: $need | $line"; }
  done
done
n=$(( $(wc -l < "$O/run.csv") - 1 ))
log "arm $NAME done rc=$rc ok=$ok rows=$n"
tasklist 2>/dev/null | grep -qiE 'Ft8.FitProbe|Replay81' && log "ORPHAN CHECK: a process is still running" || log "orphan check clean"
[ "$rc" = 0 ] && [ "$ok" = 1 ] || die "arm $NAME failed (rc=$rc ok=$ok)"
log "chain done"
