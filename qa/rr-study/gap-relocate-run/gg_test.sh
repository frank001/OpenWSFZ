#!/bin/bash
# COH-GATE-G TRAIN recording (spec 1b7445e7 + Amendment 1 47294d4d): the BOTH arm on the first 400 cycles, every GATED_OUT / NEW_GATED fallback row recorded (StageProbe.cs, --gate-record 1). PC. Detached, logged, orphan-checked.
# Run: nohup bash gr_arms.sh > chain.out 2>&1 & disown
# Build: Replay81 (qa/refset, -p:HasInternals=true: assembly Ft8.FitProbe, counting pass-through interop) against main 95e69e87; libft8.dll SHA-256 pinned below, re-hashed at the start and end of EVERY arm.
# Settings = the station's: mode three1 (Deep), nhard 24, OSD sign fix 1, 8 threads, multi-set ON, coherentFallbackAudio Both (explicit = the absent-key default).
# Working files with message text (impl-dump, nc-dump) live ONLY under D:\Projects\claude\_qa-scratch (HK-037).
S=/d/Projects/claude/_qa-scratch/coh-gate-g
BIN=$S/bin
DLL=$BIN/libft8.dll
PIN=1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914
SEL=$S/selection_test.json
RUN=20260925_2010
WAVROOT=/d/Projects/claude/OpenWSFZ/artefacts
G=$WAVROOT/${RUN}_endurance_run-gathered
ALLTXT=$G/wsjt-x/ALL.TXT
RAW=$S/raw
SCR=$S/scratch
mkdir -p "$RAW" "$SCR"
STATUS_ALL=$RAW/chain_status.txt
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$STATUS_ALL"; }
die() { log "CHAIN HALT: $*"; exit 9; }
w() { cygpath -w "$1"; }
sha() { sha256sum "$1" | cut -d' ' -f1; }
[ "$(sha "$DLL")" = "$PIN" ] || die "libft8.dll differs from its pin at chain start"
[ "$(ls $G/owsfz/wav | wc -l)" = 2884 ] || die "audio folder does not hold 2884 WAVs"
log "COH-GATE-G TEST replay (cycles 401-1200, after the freeze commit 36df15b1) start; dll=$PIN; selection sha=$(sha $SEL)"
busy() { tasklist 2>/dev/null | grep -qiE 'wsjtx|jt9|OpenWSFZ.Daemon|Ft8.FitProbe|Replay81'; }

arm() {   # arm <name> <cohfb 0|1> <expected rows>
  local NAME=$1 FB=$2 WANT=$3 O=$RAW/$1 SC=$SCR/$1 ST=$RAW/$1_status.txt
  busy && die "a competing process is running before $NAME"
  [ "$(sha "$DLL")" = "$PIN" ] || die "dll pin at start of $NAME"
  rm -rf "$O" "$SC"; mkdir -p "$O" "$SC"
  echo "start $(date -u +%FT%TZ) name=$NAME cohfb=$FB dll=$(sha "$DLL")" > "$ST"
  log "arm $NAME start (cohfb=$FB)"
  "$(w $BIN/Ft8.FitProbe.exe)" --selection "$(w $SEL)" --run $RUN --stratum FULL --wav-root "$(w $WAVROOT)" --wav-dir "$(w $G/owsfz/wav)" \
    --out "$(w $O/run.csv)" --log "$(w $O/log.log)" --nhard 24 --osd-sign-fix 1 --mode three1 --threads 8 --cohfb $FB --cohms 1 --cohaudio Both --cohfb-out "$(w $O/coh.csv)" \
    --label "coh-gate-g:$NAME:95e69e87" --wsjtx-alltxt "$(w $ALLTXT)" --testb-out "$(w $O/testb.csv)" --matched-out "$(w $O/matched.csv)" --matched-batch-out "$(w $O/matchedbatch.csv)" \
    --third-out "$(w $O/third.csv)" --abandon-out "$(w $O/abandon.csv)" --outcomes "$(w $O/outcomes.csv)" --nc-dump "$(w $SC/nc_dump.tsv)" \
    --impl-dump "$(w $SC/impl_dump.tsv)" --gate-record 1 --stage-out "$(w $O/stage.csv)" --stage-dump "$(w $SC/stage_dump.tsv)" > "$O/stdout.txt" 2>&1
  local rc=$?
  local ok=1
  [ "$(sha "$DLL")" = "$PIN" ] || { ok=0; echo "END dll pin mismatch" >> "$ST"; }
  local wantfb; wantfb=$([ "$FB" = 1 ] && echo True || echo False)
  for tag in start end; do
    local line; line=$(grep "^# readback $tag" "$O/log.log" | head -1)
    for need in "decodingDepth=Deep" "nhard=24" "osdSignFixRead=1" "shim=20260071" "cohfb=$wantfb" "cohms=True"; do
      echo "$line" | grep -q "$need" || { ok=0; echo "READBACK $tag missing: $need | $line" >> "$ST"; }
    done
  done
  local n; n=$(( $(wc -l < "$O/run.csv") - 1 ))
  [ "$n" = "$WANT" ] || { ok=0; echo "ROWS $n != $WANT" >> "$ST"; }
  echo "exit $rc preflight_end_ok=$ok rows=$n at $(date -u +%FT%TZ)" >> "$ST"
  log "arm $NAME done rc=$rc ok=$ok rows=$n"
  [ "$rc" = 0 ] && [ "$ok" = 1 ] || die "arm $NAME failed (rc=$rc ok=$ok)"
}

arm test 1 800
busy && log "ORPHAN CHECK: a competing process is still running" || log "orphan check clean"
[ "$(sha "$DLL")" = "$PIN" ] && log "END dll pin OK" || log "END dll pin FAIL"
log "chain done"
