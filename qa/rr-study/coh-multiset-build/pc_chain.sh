#!/bin/bash
# COH-MULTISET-BUILD decision replay on the PC (Amendment 3 / 4: the build of record; V8 compares its outcomes with sol's).
# REF -> MS only (no MS-repeat: V6 is judged on sol). Detached, logged, orphan-checked (HK-013 / HK-019 / HK-023).
# Run: nohup bash pc_chain.sh > chain.out 2>&1 & disown
# Build: Replay81 (qa/refset 14f7ad6f) against the Developer's d7750bde Windows build; libft8.dll SHA-256 pinned below, re-hashed at the start and end of EVERY arm.
# Settings identical to sol (spec 6.2): mode three1 (Deep, subtraction ON), nhard 24, OSD sign fix 1, 8 threads, coherentFallbackEnabled TRUE; REF cohms 0, MS cohms 1.
# Working files with message text (nc-dump) live ONLY under D:\Projects\claude\_qa-scratch (HK-037).
S=/d/Projects/claude/_qa-scratch
B=$S/coh-multiset/pc_chain
BIN=$B/bin
DLL=$BIN/libft8.dll
PIN=1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914
SELPIN=53d9ba4ec52b0f6bca8f4a4cb03a92ad3493387dfb1f4d11e7a29709857331c4
SEL=/d/Projects/claude/OpenWSFZ/worktrees/qa/qa/rr-study/results/2026-10-24-coh-multiset-build/selection.json
RUN=20260925_2010
WAVROOT=/d/Projects/claude/OpenWSFZ/artefacts
G=$WAVROOT/${RUN}_endurance_run-gathered
ALLTXT=$G/wsjt-x/ALL.TXT
RAW=$B/raw
SCR=$S/msb-pc
mkdir -p "$RAW" "$SCR"
STATUS_ALL=$RAW/chain_status.txt
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$STATUS_ALL"; }
die() { log "CHAIN HALT: $*"; exit 9; }
w() { cygpath -w "$1"; }
sha() { sha256sum "$1" | cut -d' ' -f1; }
sha_lf() { python -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read().replace(b'\r\n',b'\n')).hexdigest())" "$1"; }

[ "$(sha "$DLL")" = "$PIN" ] || die "libft8.dll differs from its pin at chain start"
[ "$(sha_lf "$SEL")" = "$SELPIN" ] || die "selection.json differs from the freeze (81372df5)"
[ "$(ls $G/owsfz/wav | wc -l)" = 2884 ] || die "audio folder does not hold 2884 WAVs"
log "PC chain start; dll=$PIN; selection sha_lf=$SELPIN"

busy() { tasklist 2>/dev/null | grep -qiE 'wsjtx|jt9|OpenWSFZ.Daemon|Replay81'; }

arm() {   # arm <name> <cohms 0|1> <expected rows>
  local NAME=$1 MS=$2 WANT=$3 O=$RAW/$1 SC=$SCR/$1 ST=$RAW/$1_status.txt
  busy && die "a competing process is running before $NAME"
  [ "$(sha "$DLL")" = "$PIN" ] || die "dll pin at start of $NAME"
  rm -rf "$O" "$SC"; mkdir -p "$O" "$SC"
  echo "start $(date -u +%FT%TZ) name=$NAME cohms=$MS dll=$(sha "$DLL")" > "$ST"
  log "arm $NAME start (cohms=$MS)"
  dotnet "$(w $BIN/Replay81.dll)" --selection "$(w $SEL)" --run $RUN --stratum FULL --wav-root "$(w $WAVROOT)" --wav-dir "$(w $G/owsfz/wav)" \
    --out "$(w $O/run.csv)" --log "$(w $O/log.log)" --nhard 24 --osd-sign-fix 1 --mode three1 --threads 8 --cohfb 1 --cohms $MS --cohfb-out "$(w $O/coh.csv)" \
    --label "msb-pc:$NAME:d7750bde" --wsjtx-alltxt "$(w $ALLTXT)" --testb-out "$(w $O/testb.csv)" --matched-out "$(w $O/matched.csv)" --matched-batch-out "$(w $O/matchedbatch.csv)" \
    --third-out "$(w $O/third.csv)" --abandon-out "$(w $O/abandon.csv)" --outcomes "$(w $O/outcomes.csv)" --nc-dump "$(w $SC/nc_dump.tsv)" > "$O/stdout.txt" 2>&1
  local rc=$?
  local ok=1
  [ "$(sha "$DLL")" = "$PIN" ] || { ok=0; echo "END dll pin mismatch" >> "$ST"; }
  local wantms; wantms=$([ "$MS" = 1 ] && echo True || echo False)
  for tag in start end; do
    local line; line=$(grep "^# readback $tag" "$O/log.log" | head -1)
    for need in "decodingDepth=Deep" "nhard=24" "osdSignFixRead=1" "shim=20260071" "cohfb=True" "cohms=$wantms"; do
      echo "$line" | grep -q "$need" || { ok=0; echo "READBACK $tag missing: $need | $line" >> "$ST"; }
    done
  done
  local n; n=$(( $(wc -l < "$O/run.csv") - 1 ))
  [ "$n" = "$WANT" ] || { ok=0; echo "ROWS $n != $WANT" >> "$ST"; }
  echo "exit $rc preflight_end_ok=$ok rows=$n at $(date -u +%FT%TZ)" >> "$ST"
  log "arm $NAME done rc=$rc ok=$ok rows=$n"
  [ "$rc" = 0 ] && [ "$ok" = 1 ] || die "arm $NAME failed (rc=$rc ok=$ok)"
}

arm ref 0 2882
arm ms  1 2882

busy && log "ORPHAN CHECK: a competing process is still running" || log "orphan check clean"
[ "$(sha "$DLL")" = "$PIN" ] && log "END dll pin OK" || log "END dll pin FAIL"
log "chain done"
