#!/bin/bash
# COH-MULTISET V4' (Architect Amendment 1.10; = COH-GAIN Amendment 3): replay the sampled cycles (974 with rows) of night 20261022_1949 through the current build's
# two-stage/Deep decode on a CLEAN checkout of main 5a9667ee, with batch-labelled matched output. Committed BEFORE V4' is evaluated.
# Build: Replay81 against _qa-scratch/coh-multiset/main-tree (5a9667ee, clean), libft8.dll aaf6b03e (shim 20260069). Mode three1 (Deep, subtraction ON), nhard 24, OSD sign fix 1,
# 8 threads, coherent fallback flag ON (as shipped since f684277f), Test B match rule inside the harness. Message text stays in _qa-scratch (HK-037).
S=D:/Projects/claude/_qa-scratch/coh-multiset
BIN=$S/out_v4p
O=$S/v4p
PIN=aaf6b03edb8eea1933bf7ab71d4c0bc4e67af214d9834c9030de769cc1826aef
RUN=20261022_1949
ART=D:/Projects/claude/OpenWSFZ/artefacts
G=$ART/${RUN}_endurance_run-gathered
STATUS=$S/v4p_status.txt
die() { echo "PREFLIGHT FAIL: $*" | tee -a "$STATUS"; exit 9; }

n=$(tasklist 2>/dev/null | grep -ci "replay81\|A2ep\|jt9\|wsjtx\|OpenWSFZ.Daemon"); [ "$n" = 0 ] || die "a competing process is running ($n)"
h0=$(sha256sum "$BIN/libft8.dll" | cut -d' ' -f1); [ "$h0" = "$PIN" ] || die "DLL pin at start: $h0"
[ "$(git -C $S/main-tree rev-parse HEAD)" = "5a9667eefb570d6aa551a86f95ff5f1683584e9c" ] || die "checkout is not 5a9667ee"
[ -z "$(git -C $S/main-tree status --porcelain)" ] || die "checkout not clean"
rm -rf "$O"; mkdir -p "$O"
python -I - "$O/v4p_selection.json" <<'PY' || die "selection build"
import json, sys
sel = json.load(open("D:/Projects/claude/OpenWSFZ/worktrees/qa/qa/rr-study/results/2026-10-24-coh-multiset/selection.json"))
cycles = [s for _, s in sel["sample"]]
out = {"note": "COH-MULTISET V4' replay list: the sampled cycles", "run": "20261022_1949",
       "runs": {"20261022_1949": {"warmup": sel["pilot"][0][1], "V4P": cycles}}}
json.dump(out, open(sys.argv[1], "w"), indent=1, sort_keys=True)
print(len(cycles), "cycles; warm-up = first pilot stamp (not a sample cycle)")
PY
echo "start $(date -u +%FT%TZ) dll=$h0 checkout=5a9667ee" > "$STATUS"

"$BIN/Replay81.exe" \
  --selection "$O/v4p_selection.json" --run $RUN --stratum V4P \
  --wav-root "$ART" --wav-dir "$G/owsfz/wav" \
  --out "$O/run.csv" --log "$O/log.log" \
  --nhard 24 --osd-sign-fix 1 --mode three1 --threads 8 --cohfb 1 --cohfb-out "$O/coh.csv" --label "coh-multiset-v4p:5a9667ee" \
  --wsjtx-alltxt "$G/wsjt-x/ALL.TXT" --testb-out "$O/testb.csv" \
  --matched-out "$O/matched.csv" --matched-batch-out "$O/matchedbatch.csv" \
  --third-out "$O/third.csv" --abandon-out "$O/abandon.csv" --outcomes "$O/outcomes.csv" > "$O/stdout.txt" 2>&1
rc=$?

h1=$(sha256sum "$BIN/libft8.dll" | cut -d' ' -f1)
ok=1
[ "$h1" = "$PIN" ] || { ok=0; echo "END DLL pin mismatch: $h1" >> "$STATUS"; }
for tag in start end; do
  line=$(grep "^# readback $tag" "$O/log.log" | head -1)
  for need in "decodingDepth=Deep" "nhard=24" "osdSignFixRead=1" "shim=20260069" "cohfb=True"; do
    echo "$line" | grep -q "$need" || { ok=0; echo "READBACK $tag missing: $need | $line" >> "$STATUS"; }
  done
done
echo "exit $rc preflight_end_ok=$ok at $(date -u +%FT%TZ)" >> "$STATUS"
[ "$rc" = 0 ] && [ "$ok" = 1 ]
