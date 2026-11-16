#!/bin/bash
# XC-BUILD K4 gate (spec Amendment 3 s10, A2.1 determinism guard, K4): run the pre-change build ce5734b6 TWICE (A1, A2) on the first 100 TRAIN cycles on sol and compare.
# GOAL: decide whether replay on sol is repeatable (A1 == A2) so that V-OFF can be decided there. CRITICAL CONFIG: one libft8.so (pinned below), the station-stack flags, 100 cycles.
# Run ON SOL, detached:   SO_PIN=<sha256> nohup bash xc_k4_gate.sh > ~/_xc/k4.out 2>&1 & disown
# Message text (nc.tsv) lives ONLY under ~/_qa-scratch (HK-037); KEPT, never deleted (Captain, 2026-11-16). Nothing is read from sol except the comparison verdict and counts.
: "${SO_PIN:?set SO_PIN}"
B=$HOME/_xc
BIN=$B/out_ref
SO=$BIN/libft8.so
SEL=${SEL_OVERRIDE:-$B/sel/sel_train_100.json}
NROWS=${NROWS:-100}
R=${RDIR:-$B/k4}
SCRN=${SCRN:-xc-k4}
RUN=20261110_1817
WAVROOT=$B/wav
WDIR=$B/wav/20261110_1817_cq-ap-live/owsfz/wav
ALLTXT=$B/ref/wsjtx_ALL_train.TXT
SCR=$HOME/_qa-scratch/$SCRN
export PATH=$HOME/.dotnet:$PATH DOTNET_ROOT=$HOME/.dotnet DOTNET_CLI_TELEMETRY_OPTOUT=1
mkdir -p "$SCR" "$R"
LOG=$R/chain_status.txt
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$LOG"; }
die() { log "CHAIN HALT: $*"; exit 9; }
sha() { sha256sum "$1" | cut -d' ' -f1; }
busy() { pgrep -f "Ft8.FitProbe.dll" > /dev/null || pgrep -x wsjtx > /dev/null || pgrep -x jt9 > /dev/null || pgrep -x OpenWSFZ.Daemon > /dev/null; }
[ "$(sha $SO)" = "$SO_PIN" ] || die "libft8.so differs from its pin at start"
python3 - <<PY || die "selected WAVs missing"
import json, os
r = json.load(open("$SEL"))["runs"]["$RUN"]
assert len(r["FULL"]) == $NROWS
miss = [s for s in r["FULL"] + [r["warmup"]] if not os.path.exists("$WDIR/" + s + ".wav")]
assert not miss, miss[:3]
PY
log "K4 gate start; so=$SO_PIN; sel sha=$(sha $SEL); cores=$(nproc); build ce5734b6 (out_ref)"

arm() {   # arm <name>
  local NAME=$1 O=$R/$1 S=$SCR/$1 ST=$R/$1/status.txt
  busy && die "a competing process is running before $NAME"
  [ "$(sha $SO)" = "$SO_PIN" ] || die "so pin at start of $NAME"
  rm -rf "$O" "$S"; mkdir -p "$O" "$S"
  echo "start $(date -u +%FT%TZ) name=$NAME so=$(sha $SO) load=$(cut -d' ' -f1-3 /proc/loadavg)" > "$ST"
  log "arm $NAME start"
  dotnet $BIN/Ft8.FitProbe.dll --selection "$SEL" --run $RUN --stratum FULL --wav-root "$WAVROOT" --wav-dir "$WDIR" \
    --out "$O/run.csv" --log "$O/log.log" --nhard 24 --osd-sign-fix 1 --mode three1 --threads 8 --cohfb 1 --cohms 1 --cohaudio Both \
    --kmin 5 --osd-corr 0.05 --ungated 1 --late-round 1 --cq-ap 1 --cohrescand 1 --cohfb-out "$O/coh.csv" \
    --label "xc-k4:$NAME:ce5734b6" --wsjtx-alltxt "$ALLTXT" --testb-out "$O/testb.csv" --matched-out "$O/matched.csv" --matched-batch-out "$O/matchedbatch.csv" \
    --third-out "$O/third.csv" --abandon-out "$O/abandon.csv" --outcomes "$O/outcomes.csv" --late-out "$O/late.csv" --nc-dump "$S/nc.tsv" > "$O/stdout.txt" 2>&1
  local rc=$? ok=1
  [ "$(sha $SO)" = "$SO_PIN" ] || { ok=0; echo "END so pin mismatch" >> "$ST"; }
  for tag in start end; do
    local line; line=$(grep "^# readback $tag" "$O/log.log" | head -1)
    for need in "decodingDepth=Deep" "nhard=24" "osdSignFixRead=1" "cohfb=True" "cohms=True" "cohaudio=Both" "ungated=True" "lateround=True" "kMinScorePass2=5 " "osdCorrThreshold=0.05"; do
      echo "$line" | grep -q -- "$need" || { ok=0; echo "READBACK $tag missing: $need" >> "$ST"; }
    done
    echo "$tag: $(echo "$line" | grep -o 'threadsResolved=[0-9]*')" >> "$ST"
  done
  local n; n=$(( $(wc -l < "$O/run.csv") - 1 ))
  [ "$n" = "$NROWS" ] || { ok=0; echo "ROWS $n != $NROWS" >> "$ST"; }
  # VALIDITY (HK-022: a row count says nothing if every cycle threw): no exception, every decode count >= 0, text outputs non-empty, batch-4 column present
  local nex nneg; nex=$(awk -F, 'NR>1 && $8!=""' "$O/run.csv" | wc -l); nneg=$(awk -F, 'NR>1 && $7<0' "$O/run.csv" | wc -l)
  [ "$nex" = 0 ] || { ok=0; echo "EXCEPTIONS in $nex cycles" >> "$ST"; }
  [ "$nneg" = 0 ] || { ok=0; echo "NEGATIVE decode counts in $nneg cycles" >> "$ST"; }
  head -1 "$O/run.csv" | grep -q "b4_n" || { ok=0; echo "run.csv has no b4_n column (build lacks HasCohFb4)" >> "$ST"; }
  [ -s "$S/nc.tsv" ] || { ok=0; echo "nc.tsv empty" >> "$ST"; }
  [ "$(wc -l < "$O/outcomes.csv")" -gt 0 ] || { ok=0; echo "outcomes.csv empty" >> "$ST"; }
  [ "$(wc -l < "$O/matchedbatch.csv")" -gt 1 ] || { ok=0; echo "matchedbatch.csv has no rows" >> "$ST"; }
  echo "validity: exceptions=$nex negative=$nneg nc_bytes=$(wc -c < "$S/nc.tsv") outcomes_lines=$(wc -l < "$O/outcomes.csv")" >> "$ST"
  echo "exit $rc ok=$ok rows=$n end=$(date -u +%FT%TZ)" >> "$ST"
  log "arm $NAME done rc=$rc ok=$ok rows=$n"
  [ "$rc" = 0 ] && [ "$ok" = 1 ] || die "arm $NAME failed (rc=$rc ok=$ok)"
}
arm A1
arm A2
busy && log "ORPHAN CHECK: a competing process is still running" || log "orphan check clean"
[ "$(sha $SO)" = "$SO_PIN" ] && log "END so pin OK" || log "END so pin FAIL"

# K3 equality: the per-cycle published rows (nc.tsv carries batch, text, freq, dt, snr) and the matched / outcome / test-B files, timing excluded. Counts only are printed.
python3 - <<PY | tee -a "$LOG"
import os
S1, S2, R1, R2 = "$SCR/A1", "$SCR/A2", "$R/A1", "$R/A2"
files = [(S1 + "/nc.tsv", S2 + "/nc.tsv")] + [(R1 + "/" + f, R2 + "/" + f) for f in ("matched.csv", "matchedbatch.csv", "outcomes.csv", "testb.csv")]
diff = {}
for a, b in files:
    la, lb = open(a, encoding="utf-8").read().splitlines(), open(b, encoding="utf-8").read().splitlines()
    nd = sum(1 for x, y in zip(la, lb) if x != y) + abs(len(la) - len(lb))
    diff[os.path.basename(a)] = (len(la), len(lb), nd)
import csv
def cols(path):
    rows = list(csv.DictReader(open(path)))
    keep = ["stamp", "decodes", "b1_n", "b2_n", "b3_n", "b4_n", "b5_n"]
    return [tuple(r[k] for k in keep) for r in rows]
ra, rb = cols(R1 + "/run.csv"), cols(R2 + "/run.csv")
dec = sum(1 for x, y in zip(ra, rb) if x != y)
print("K4 compare (lines A1, lines A2, lines differing):", diff)
print("K4 cycles whose (decodes, b1..b5 counts) differ:", dec, "of", len(ra))
print("K4 VERDICT:", "A1 == A2 (repeatable on 100 cycles)" if all(v[2] == 0 for v in diff.values()) and dec == 0 else "A1 != A2 (NOT repeatable: V-OFF undecidable on sol, arms go to the PC)")
PY
log "chain done"
