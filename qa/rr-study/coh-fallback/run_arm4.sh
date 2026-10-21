#!/bin/bash
# COH-FALLBACK step 4 replay arm (spec sections 14-17): run_arm4.sh <name> <cohfb 0|1> <selection json> <expected selection sha256_lf|-> [smoke]
# Build = feat/coh-fallback-stage1 b8fc732e (shim 20260069, libft8.dll aaf6b03e...); Replay81 --mode three1 (Deep), nhard 24, OSD sign fix 1, 8 threads.
# PRE-FLIGHT (HK-020, spec A16.3), all FAIL CLOSED: exactly one arm at a time; DLL pin re-hashed at the START and the END; selection SHA; flag, Deep, nhard 24 and the OSD fix READ BACK at both ends.
# Working files (message text) live ONLY under _qa-scratch (HK-037); nothing here is written under the repository.
S=D:/Projects/claude/_qa-scratch/coh-fallback
BIN=$S/out_step4_b8fc
PIN=aaf6b03edb8eea1933bf7ab71d4c0bc4e67af214d9834c9030de769cc1826aef
RUN=20260922_2056
ART=D:/Projects/claude/OpenWSFZ/worktrees/qa/artefacts
NAME=$1; FLAG=$2; SEL=$3; SELSHA=$4; SMOKE=$5
O=$S/step4/$NAME
die() { echo "PREFLIGHT FAIL: $*" | tee -a "$S/step4/${NAME}_status.txt"; exit 9; }

[ "$FLAG" = 0 ] || [ "$FLAG" = 1 ] || die "flag must be 0 or 1"
n=$(tasklist 2>/dev/null | grep -ci "replay81\|A2ep"); [ "$n" = 0 ] || die "another Replay81/A2ep process is running ($n)"
h0=$(sha256sum "$BIN/libft8.dll" | cut -d' ' -f1); [ "$h0" = "$PIN" ] || die "DLL pin at start: $h0"
if [ "$SELSHA" != "-" ]; then
  s=$(python -I -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read().replace(b'\r\n',b'\n')).hexdigest())" "$SEL")
  [ "$s" = "$SELSHA" ] || die "selection sha256_lf $s != $SELSHA"
fi
rm -rf "$O"; mkdir -p "$O"
echo "start $(date -u +%FT%TZ) name=$NAME flag=$FLAG dll=$h0 sel_sha=${s:--} smoke=${SMOKE:-no}" > "$S/step4/${NAME}_status.txt"

"$BIN/Replay81.exe" \
  --selection "$SEL" --run $RUN --stratum Y40 \
  --wav-root "$ART" \
  --out "$O/run.csv" --log "$O/log.log" \
  --nhard 24 --osd-sign-fix 1 --mode three1 --threads 8 --cohfb "$FLAG" --cohfb-out "$O/coh.csv" --label "cohfb-step4:$NAME" \
  --wsjtx-alltxt "$ART/${RUN}_endurance_run-gathered/wsjt-x/ALL.TXT" --testb-out "$O/testb.csv" \
  --matched-out "$O/matched.csv" --matched-batch-out "$O/matchedbatch.csv" \
  --third-out "$O/third.csv" --abandon-out "$O/abandon.csv" --outcomes "$O/outcomes.csv" \
  --nc-dump "$O/nc_dump.tsv" > "$O/stdout.txt" 2>&1
rc=$?

# END checks: the pin again, and the read-backs at both ends of the log.
h1=$(sha256sum "$BIN/libft8.dll" | cut -d' ' -f1)
want_flag=$([ "$FLAG" = 1 ] && echo True || echo False)
ok=1
[ "$h1" = "$PIN" ] || { ok=0; echo "END DLL pin mismatch: $h1" >> "$S/step4/${NAME}_status.txt"; }
for tag in start end; do
  line=$(grep "^# readback $tag" "$O/log.log" | head -1)
  for need in "decodingDepth=Deep" "nhard=24" "osdSignFixRead=1" "shim=20260069" "cohfb=$want_flag"; do
    echo "$line" | grep -q "$need" || { ok=0; echo "READBACK $tag missing: $need | $line" >> "$S/step4/${NAME}_status.txt"; }
  done
done
echo "exit $rc preflight_end_ok=$ok at $(date -u +%FT%TZ)" >> "$S/step4/${NAME}_status.txt"
[ "$rc" = 0 ] && [ "$ok" = 1 ]
