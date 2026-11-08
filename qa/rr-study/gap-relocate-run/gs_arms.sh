#!/bin/bash
# COH-GATE-G R-F4 SECOND NIGHT on sol (build spec Amendment 2 section 8; the Captain agreed 2026-10-28). Night 20261022_1949, 40 m.
# Selection (frozen before this replay): systematic, stride 3, offset 1, the first 800 slots of the gap-inclusive 15 s grid (selection_2n.json).
# Arms: off (setting absent), on (--ungated 1), orig (--cohaudio Original, first 200 selected cycles: the U-prime class freeze, HK-026 condition in A1.4).
# Build: Replay81 (qa/refset cf32b52a+, --ungated switch, stock harness) against ~/_rf4/tree = the Developer's 7d93c1e7 source; libft8.so built ON SOL from it by build_linux.sh.
# Settings = the station's: mode three1 (Deep), nhard 24, OSD sign fix 1, 8 threads, multi-set ON, coherentFallbackAudio Both (orig arm: Original).
# Working files with message text (nc-dump) live ONLY under ~/_qa-scratch (HK-037). Detached, logged, orphan-checked (HK-013/019/023). No hibernate.
B=$HOME/_rf4
SO=$B/out/libft8.so
PIN=488bfa0b90a570ad0bc9f285d871147f62f4a71165fcf6dc39bd31eb584f58d0
RUN=20261022_1949
WAVROOT=$HOME/_msb/wav
G=$WAVROOT/${RUN}_endurance_run-gathered
SEL=$B/selection_2n.json
SEL200=$B/selection_2n_200.json
RAW=$B/raw
SCR=$HOME/_qa-scratch/rf4
export PATH=$HOME/.dotnet:$PATH DOTNET_CLI_TELEMETRY_OPTOUT=1
mkdir -p "$RAW" "$SCR"
STATUS_ALL=$RAW/chain_status.txt
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$STATUS_ALL"; }
die() { log "CHAIN HALT: $*"; exit 9; }
sha() { sha256sum "$1" | cut -d' ' -f1; }
[ "$(sha "$SO")" = "$PIN" ] || die "libft8.so differs from its pin at chain start"
python3 - <<PY
import json
d = json.load(open("$SEL"))
r = d["runs"]["$RUN"]
assert len(r["FULL"]) == 800
d["runs"]["$RUN"] = {"warmup": r["warmup"], "FULL": r["FULL"][:200]}
d["note"] = "first 200 selected cycles (Original arm for the U-prime classes)"
json.dump(d, open("$SEL200", "w"), indent=1, sort_keys=True)
PY
log "second-night chain start; so=$PIN; selection sha=$(sha $SEL); sel200 sha=$(sha $SEL200)"
busy() { pgrep -f 'Replay81.dll' > /dev/null || pgrep -x wsjtx > /dev/null || pgrep -x jt9 > /dev/null || pgrep -x OpenWSFZ.Daemon > /dev/null; }

arm() {   # arm <name> <selection> <rows> <audio> <extra> <expect ungated>
  local NAME=$1 SELF=$2 WANT=$3 AUD=$4 EXTRA=$5 WANTU=$6 O=$RAW/$1 S=$SCR/$1 ST=$RAW/$1_status.txt
  busy && die "a competing process is running before $NAME"
  [ "$(sha "$SO")" = "$PIN" ] || die "so pin at start of $NAME"
  rm -rf "$O" "$S"; mkdir -p "$O" "$S"
  echo "start $(date -u +%FT%TZ) name=$NAME audio=$AUD extra='$EXTRA' so=$(sha "$SO")" > "$ST"
  log "arm $NAME start (audio=$AUD $EXTRA)"
  dotnet $B/out/Replay81.dll --selection "$SELF" --run $RUN --stratum FULL --wav-root "$WAVROOT" --wav-dir "$G/owsfz/wav" \
    --out "$O/run.csv" --log "$O/log.log" --nhard 24 --osd-sign-fix 1 --mode three1 --threads 8 --cohfb 1 --cohms 1 --cohaudio $AUD $EXTRA --cohfb-out "$O/coh.csv" \
    --label "r-f4-2n:$NAME:7d93c1e7" --wsjtx-alltxt "$B/wsjtx_ALL_2n.TXT" --testb-out "$O/testb.csv" --matched-out "$O/matched.csv" --matched-batch-out "$O/matchedbatch.csv" \
    --third-out "$O/third.csv" --abandon-out "$O/abandon.csv" --outcomes "$O/outcomes.csv" --nc-dump "$S/nc_dump.tsv" > "$O/stdout.txt" 2>&1
  local rc=$?
  local ok=1
  [ "$(sha "$SO")" = "$PIN" ] || { ok=0; echo "END so pin mismatch" >> "$ST"; }
  for tag in start end; do
    local line; line=$(grep "^# readback $tag" "$O/log.log" | head -1)
    for need in "decodingDepth=Deep" "nhard=24" "osdSignFixRead=1" "shim=20260071" "cohfb=True" "cohms=True" "cohaudio=$AUD" "ungated=$WANTU"; do
      echo "$line" | grep -q "$need" || { ok=0; echo "READBACK $tag missing: $need | $line" >> "$ST"; }
    done
  done
  local n; n=$(( $(wc -l < "$O/run.csv") - 1 ))
  [ "$n" = "$WANT" ] || { ok=0; echo "ROWS $n != $WANT" >> "$ST"; }
  echo "exit $rc preflight_end_ok=$ok rows=$n at $(date -u +%FT%TZ)" >> "$ST"
  log "arm $NAME done rc=$rc ok=$ok rows=$n"
  [ "$rc" = 0 ] && [ "$ok" = 1 ] || die "arm $NAME failed (rc=$rc ok=$ok)"
}

arm off  $SEL    800 Both     ""             False
arm on   $SEL    800 Both     "--ungated 1"  True
arm orig $SEL200 200 Original ""             False
busy && log "ORPHAN CHECK: a competing process is still running" || log "orphan check clean"
[ "$(sha "$SO")" = "$PIN" ] && log "END so pin OK" || log "END so pin FAIL"
log "chain done"
