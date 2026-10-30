#!/bin/bash
# LATE-SUB L1' THIRD NIGHT, HK-026 CONTINGENCY (freeze item 7; Architect 2026-10-30): the Original arm on the OTHER 600 selected cycles (201-800), one separate process, same pin and checks.
# (derived from tn_arms.sh; run after it: SO_PIN=... bash tn_orig600.sh > ~/_l1p/chain600.out). Original of the third night on sol (build spec section 4 + Amendment 1 + the ruling 2026-10-30-1802 section 4). Night 20260930_1930, 40 m.
# Run ON SOL, detached:   SO_PIN=<sha256 of the libft8.so built on sol from b1d8a06e> nohup bash tn_arms.sh > ~/_l1p/chain.out 2>&1 & disown
# NOT to be started before: the Captain has woken sol and given the run go in QA's window; the freeze commit (selection, .so SHA-256, build commit, Replay81 commit, analysis code) exists.
# Selection (frozen before this replay): selection_3n.json = mk_selection_3n.py (stride 3, offset 1, the first 800 slots of the gap-inclusive 15 s grid).
# Arms (sequence as the R-F4 second night): off (setting absent), on (--late-round 1), orig (--cohaudio Original, first 200 selected cycles, setting absent: the U-prime class freeze, HK-026).
# Build: Replay81 at the freeze's commit (cfdf724c: first-line ThirdProbe, late.csv, R6 whitelist) built with
#   dotnet build qa/rr-study/sub-feas/replay81/Replay81.csproj -c Release -p:RepoRoot=$B/tree -p:HasSubfeas=true -p:HasMaxThreads=true -p:HasTwoStage=true -p:HasOsdSignFix=true
#     -p:HasThirdPass=true -p:HasCohFb=true -p:HasCohFb4=true -p:HasLateRound=true -p:HasCohMs=true -p:HasCohAudio=true -o $B/out
# against $B/tree = the Developer's b1d8a06e source; libft8.so built ON SOL from it by native/ft8_lib_build/build_linux.sh and copied to $B/out/libft8.so.
# Settings = the station's: mode three1 (Deep), nhard 24, OSD sign fix 1, 8 threads, multi-set ON, coherentFallbackAudio Both (orig arm: Original), R-F4 OFF (no --ungated).
# Working files with message text (nc-dump) live ONLY under ~/_qa-scratch (HK-037). Logged, orphan-checked (HK-013/019/023). No hibernate (not asked for this run).
: "${SO_PIN:?set SO_PIN to the SHA-256 of the libft8.so built on sol (recorded in the freeze commit)}"
B=${B:-$HOME/_l1p}
SO=$B/out/libft8.so
PIN=$SO_PIN
RUN=20260930_1930
WAVROOT=${WAVROOT:-$B/wav}
G=$WAVROOT/${RUN}_endurance_run-gathered
SEL=$B/selection_3n.json
SEL600=$B/selection_3n_600.json
# (F-DRY unused here) F-DRY (Architect ruling 2026-10-30-1802 s7): TN_DRY=1 runs all three arms on the 3 dry cycles (selection_3n_dry.json, outside the selection), outputs under raw_dry / l1p3n_dry, to be discarded.
# The frozen run is TN_DRY unset: 800 / 800 / 200 rows. The expectations come from N_MAIN / N_ORIG, which TN_DRY sets to 3.
SEL_SHA=${SEL_SHA:-}      # optional: the selection's SHA-256 from the freeze commit (2575e115378c71c068cd250d26dd002a17d7d365366cd00e6aaa3a99d2329c4f at the time of writing)
ALLTXT=$B/wsjtx_ALL_3n.TXT
RAW=$B/raw
SCR=$HOME/_qa-scratch/l1p3n
export PATH=$HOME/.dotnet:$PATH DOTNET_CLI_TELEMETRY_OPTOUT=1
mkdir -p "$RAW" "$SCR"
STATUS_ALL=$RAW/chain600_status.txt
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$STATUS_ALL"; }
die() { log "CHAIN HALT: $*"; exit 9; }
sha() { sha256sum "$1" | cut -d' ' -f1; }
[ "$(sha "$SO")" = "$PIN" ] || die "libft8.so differs from its pin at chain start"
[ -z "$SEL_SHA" ] || [ "$(sha "$SEL")" = "$SEL_SHA" ] || die "selection differs from the frozen one"
[ -s "$ALLTXT" ] || die "WSJT-X ALL.TXT for the night is missing"
python3 - <<PY || die "selected WAVs missing on sol"
import json, os
d = json.load(open("$SEL"))
r = d["runs"]["$RUN"]
assert len(r["FULL"]) == 800, len(r["FULL"])
d["runs"]["$RUN"] = {"warmup": r["warmup"], "FULL": r["FULL"][200:]}
d["note"] = "selected cycles 201-800 (Original arm, HK-026 contingency)"
json.dump(d, open("$SEL600", "w"), indent=1, sort_keys=True)
PY
log "orig600 chain start; so=$PIN; selection sha=$(sha $SEL); sel600 sha=$(sha $SEL600)"
busy() { pgrep -f 'Replay81.dll' > /dev/null || pgrep -x wsjtx > /dev/null || pgrep -x jt9 > /dev/null || pgrep -x OpenWSFZ.Daemon > /dev/null; }

arm() {   # arm <name> <selection> <rows> <audio> <extra> <expect lateround True|False>
  local NAME=$1 SELF=$2 WANT=$3 AUD=$4 EXTRA=$5 WANTL=$6 O=$RAW/$1 S=$SCR/$1 ST=$RAW/$1_status.txt
  busy && die "a competing process is running before $NAME"
  [ "$(sha "$SO")" = "$PIN" ] || die "so pin at start of $NAME"
  rm -rf "$O" "$S"; mkdir -p "$O" "$S"
  echo "start $(date -u +%FT%TZ) name=$NAME audio=$AUD extra='$EXTRA' so=$(sha "$SO")" > "$ST"
  log "arm $NAME start (audio=$AUD $EXTRA)"
  dotnet $B/out/Replay81.dll --selection "$SELF" --run $RUN --stratum FULL --wav-root "$WAVROOT" --wav-dir "$G/owsfz/wav" \
    --out "$O/run.csv" --log "$O/log.log" --nhard 24 --osd-sign-fix 1 --mode three1 --threads 8 --cohfb 1 --cohms 1 --cohaudio $AUD $EXTRA --cohfb-out "$O/coh.csv" \
    --label "l1p-3n:$NAME:b1d8a06e" --wsjtx-alltxt "$ALLTXT" --testb-out "$O/testb.csv" --matched-out "$O/matched.csv" --matched-batch-out "$O/matchedbatch.csv" \
    --third-out "$O/third.csv" --abandon-out "$O/abandon.csv" --outcomes "$O/outcomes.csv" --late-out "$O/late.csv" --nc-dump "$S/nc_dump.tsv" > "$O/stdout.txt" 2>&1
  local rc=$?
  local ok=1
  [ "$(sha "$SO")" = "$PIN" ] || { ok=0; echo "END so pin mismatch" >> "$ST"; }
  for tag in start end; do
    local line; line=$(grep "^# readback $tag" "$O/log.log" | head -1)
    for need in "decodingDepth=Deep" "nhard=24" "osdSignFixRead=1" "shim=20260071" "cohfb=True" "cohms=True" "cohaudio=$AUD" "lateround=$WANTL"; do
      echo "$line" | grep -q "$need" || { ok=0; echo "READBACK $tag missing: $need | $line" >> "$ST"; }
    done
  done
  local n; n=$(( $(wc -l < "$O/run.csv") - 1 ))
  [ "$n" = "$WANT" ] || { ok=0; echo "ROWS $n != $WANT" >> "$ST"; }
  # the instrument must have recorded the round: one R6 line per cycle in the ON arm, none in the others (B-TOOL-2 T2-2 on the real night)
  local nl; nl=$(grep -c "Late subtraction round:" "$O/log.log")
  if [ "$WANTL" = "True" ]; then [ "$nl" = "$WANT" ] || { ok=0; echo "R6 lines $nl != $WANT" >> "$ST"; }; else [ "$nl" = "0" ] || { ok=0; echo "R6 lines $nl != 0" >> "$ST"; }; fi
  echo "exit $rc preflight_end_ok=$ok rows=$n r6_lines=$nl at $(date -u +%FT%TZ)" >> "$ST"
  log "arm $NAME done rc=$rc ok=$ok rows=$n r6_lines=$nl"
  [ "$rc" = 0 ] && [ "$ok" = 1 ] || die "arm $NAME failed (rc=$rc ok=$ok)"
}

arm orig600 $SEL600 600 Original ""                False
busy && log "ORPHAN CHECK: a competing process is still running" || log "orphan check clean"
[ "$(sha "$SO")" = "$PIN" ] && log "END so pin OK" || log "END so pin FAIL"
log "chain done"
