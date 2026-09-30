#!/usr/bin/env bash
# SUB-FEAS merge-gate control (spec 5g): flag-OFF managed Ft8Decoder.DecodeAsync, origin/main vs merge head.
# Engineer-owned. Outputs stay in this gitignored directory. NFR-021/HK-037: numeric outcomes only.
set -u
ROOT="D:/Projects/claude/OpenWSFZ/worktrees/eng/artefacts/sub_feas_control"
QA_ART="D:/Projects/claude/OpenWSFZ/worktrees/qa/artefacts"
SEL="$QA_ART/sub_feas_stage_a_e3_baseline/e1_derived_selection.json"
CSPROJ="$ROOT/replay81/Replay81.csproj"
RUNS="20260922_2056 20260923_1730 20260925_2010"
LOG="$ROOT/control.log"
ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }
say() { echo "$(ts) $*" | tee -a "$LOG"; }

say "START control run"
for b in main head; do
  case $b in main) CO="C:/Users/Frank/w-eng-ctl-main"; EXTRA="";; head) CO="C:/Users/Frank/w-eng-ctl-head"; EXTRA="-p:HasSubfeas=true";; esac
  OUT="$ROOT/build_$b"; rm -rf "$OUT"
  say "build $b checkout=$(git -C $CO rev-parse HEAD) extra='$EXTRA'"
  dotnet build "$CSPROJ" -c Release -p:RepoRoot="$CO" $EXTRA -o "$OUT" -nologo -v q >"$ROOT/build_$b.txt" 2>&1 || { say "BUILD FAILED $b"; tail -5 "$ROOT/build_$b.txt"; exit 2; }
  dll=$(find "$OUT" -iname libft8.dll | head -1)
  say "dll $b path=${dll#$ROOT/} sha256=$(sha256sum "$dll" | cut -c1-64)"
done
say "builds done"
for b in main head; do
  OUT="$ROOT/build_$b"; RES="$ROOT/res_$b"; rm -rf "$RES"; mkdir -p "$RES"
  for r in $RUNS; do
    say "decode $b $r (fresh process)"
    dotnet "$OUT/Replay81.dll" --selection "$SEL" --run "$r" --stratum E1 --wav-root "$QA_ART" \
      --out "$RES/$r.csv" --log "$RES/$r.log" --mode off --label "ctl_$b" --outcomes "$RES/$r.outcomes.txt" \
      >"$RES/$r.stdout.txt" 2>"$RES/$r.stderr.txt"
    say "  rc=$? rows=$(($(wc -l <"$RES/$r.csv")-1))"
  done
done
say "compare"
python "$ROOT/flagoff_managed_compare.py" "$SEL" "$ROOT/res_main" "$ROOT/res_head" | tee "$ROOT/compare.json" | tee -a "$LOG"
say "END control run (compare exit=${PIPESTATUS[0]})"
