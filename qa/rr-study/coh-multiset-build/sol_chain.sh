#!/bin/bash
# COH-MULTISET-BUILD decision replay on sol (Architect Amendment 3, 2026-10-24; the Captain: "sol can be started immediately").
# REF -> MS -> MS-repeat (first 320 cycles) as ONE unattended chain, detached, logged, orphan-checked (HK-013 / HK-019 / HK-023). Run: nohup bash sol_chain.sh > chain.out 2>&1 & disown
# Build: Replay81 (qa/refset 14f7ad6f) against ~/_msb/tree = the Developer's d7750bde source + the .so built on sol from it; libft8.so SHA-256 pinned below, re-hashed at the start and the end of EVERY arm.
# Settings (spec 6.2): mode three1 (Deep, subtraction ON), nhard 24, OSD sign fix 1, 8 threads, coherentFallbackEnabled TRUE in every arm; REF cohms 0, MS and MS-repeat cohms 1.
# Selection: the frozen whole-night selection.json (qa/refset 81372df5, SHA-256(LF) 53d9ba4e...); MS-repeat uses its first 320 cycles (derived below, SHA recorded).
# Working files with message text (nc-dump) live ONLY under ~/_qa-scratch (HK-037, Replay81 refuses elsewhere).
B=$HOME/_msb
SO=$B/out/libft8.so
PIN=488bfa0b90a570ad0bc9f285d871147f62f4a71165fcf6dc39bd31eb584f58d0
SELPIN=53d9ba4ec52b0f6bca8f4a4cb03a92ad3493387dfb1f4d11e7a29709857331c4
RUN=20260925_2010
G=$B/wav/${RUN}_endurance_run-gathered
RAW=$B/raw
SCR=$HOME/_qa-scratch/msb
export PATH=$HOME/.dotnet:$PATH DOTNET_CLI_TELEMETRY_OPTOUT=1
mkdir -p "$RAW" "$SCR"
STATUS_ALL=$RAW/chain_status.txt
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$STATUS_ALL"; }
die() { log "CHAIN HALT: $*"; exit 9; }

sha() { sha256sum "$1" | cut -d' ' -f1; }
sha_lf() { python3 -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read().replace(b'\r\n',b'\n')).hexdigest())" "$1"; }

[ "$(sha "$SO")" = "$PIN" ] || die "libft8.so differs from its pin at chain start"
[ "$(sha_lf $B/selection.json)" = "$SELPIN" ] || die "selection.json differs from the freeze (81372df5)"
[ "$(ls $G/owsfz/wav | wc -l)" = 2884 ] || die "audio folder does not hold 2884 WAVs"
python3 - <<'PY' || die "selection build"
import json, os
b = os.path.expanduser("~/_msb")
sel = json.load(open(f"{b}/selection.json"))
run = "20260925_2010"
full = sel["runs"][run]["FULL"]
assert len(full) == 2882
out = {"note": "MS-repeat: the first 320 cycles of the frozen whole-night selection", "run": run, "runs": {run: {"warmup": sel["runs"][run]["warmup"], "FULL": full[:320]}}}
json.dump(out, open(f"{b}/selection_rep320.json", "w"), indent=1, sort_keys=True)
print("rep320 written", len(out["runs"][run]["FULL"]))
PY
log "chain start; so=$PIN; selection sha_lf=$SELPIN; rep320 sha_lf=$(sha_lf $B/selection_rep320.json)"

busy() { pgrep -x Replay81 > /dev/null || pgrep -f 'Replay81.dll' > /dev/null || pgrep -x wsjtx > /dev/null || pgrep -x jt9 > /dev/null || pgrep -x OpenWSFZ.Daemon > /dev/null; }

arm() {   # arm <name> <cohms 0|1> <selection json> <expected stamps>
  local NAME=$1 MS=$2 SEL=$3 WANT=$4 O=$RAW/$1 S=$SCR/$1 ST=$RAW/$1_status.txt
  busy && die "a competing process is running before $NAME"
  [ "$(sha "$SO")" = "$PIN" ] || die "so pin at start of $NAME"
  rm -rf "$O" "$S"; mkdir -p "$O" "$S"
  echo "start $(date -u +%FT%TZ) name=$NAME cohms=$MS dll=$(sha "$SO") selection=$(sha_lf "$SEL")" > "$ST"
  log "arm $NAME start (cohms=$MS)"
  dotnet $B/out/Replay81.dll --selection "$SEL" --run $RUN --stratum FULL --wav-root "$B/wav" --wav-dir "$G/owsfz/wav" \
    --out "$O/run.csv" --log "$O/log.log" --nhard 24 --osd-sign-fix 1 --mode three1 --threads 8 --cohfb 1 --cohms $MS --cohfb-out "$O/coh.csv" \
    --label "msb:$NAME:d7750bde" --wsjtx-alltxt "$B/wsjtx_ALL.TXT" --testb-out "$O/testb.csv" --matched-out "$O/matched.csv" --matched-batch-out "$O/matchedbatch.csv" \
    --third-out "$O/third.csv" --abandon-out "$O/abandon.csv" --outcomes "$O/outcomes.csv" --nc-dump "$S/nc_dump.tsv" > "$O/stdout.txt" 2>&1
  local rc=$?
  local ok=1
  [ "$(sha "$SO")" = "$PIN" ] || { ok=0; echo "END so pin mismatch" >> "$ST"; }
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

arm ref   0 $B/selection.json        2882
arm ms    1 $B/selection.json        2882
arm msrep 1 $B/selection_rep320.json 320

busy && log "ORPHAN CHECK: a competing process is still running" || log "orphan check clean"
[ "$(sha "$SO")" = "$PIN" ] && log "END so pin OK" || log "END so pin FAIL"
log "chain done"
