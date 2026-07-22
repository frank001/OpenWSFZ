#!/usr/bin/env bash
# D-001 runtime-parameter recall/false-positive Pareto sweep — full orchestration.
#
# Ties together the C# decode harness (D001ParamSweep) and the Python scorer
# (sweep_driver.py) into the complete sweep. All raw inputs/outputs are local and
# git-ignored (NFR-021) under $WORK; only the final 45-row CSV (committed by the
# caller) and report.md are published.
#
# Inputs (env overridable):
#   CORPUS   — 07-07 off-air per-slot WAV dir (recall arm). Local/git-ignored.
#   WSJT     — 07-07 WSJT-X ALL.TXT (recall reference). Local/git-ignored.
#   SCEN     — qa/rr-study/scenarios (S5/S7 definitions, committed).
#   NSHARDS  — parallel decode processes (default 12; separate processes = separate
#              native globals, so no shared-global race — see harness Program.cs).
#
# Usage:  bash run_sweep.sh            (runs every phase A-F)
#         PHASES=CDE bash run_sweep.sh (runs only the named phases)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"       # .../d001-param-sweep-2026-07-22
QA_RR="$(cd "$HERE/.." && pwd)"
HARN="$HERE/bin/Release/net10.0/D001ParamSweep.exe"

# The 07-07 recall corpus is local/git-ignored (NFR-021) and therefore lives ONLY in the
# main working tree, not in this git worktree. Resolve the main worktree via git so the
# default CORPUS/WSJT point at the real data regardless of which worktree we run from.
MAIN_WT="$(git -C "$QA_RR" worktree list --porcelain | awk '/^worktree /{print $2; exit}')"
CORPUS="${CORPUS:-$MAIN_WT/artefacts/20260706_live_run_2308/save}"
WSJT="${WSJT:-$MAIN_WT/artefacts/20260706_live_run_2308/WSJT-X ALL.TXT}"
SCEN="${SCEN:-$QA_RR/scenarios}"
NSHARDS="${NSHARDS:-12}"
WORK="$HERE/_work"
DRV="$HERE/sweep_driver.py"
PHASES="${PHASES:-ABCDEF}"

RECALL_NAME="OpenWSFZ ALL.TXT"
FP_NAME="owsfz-all.txt"
mkdir -p "$WORK"

# Decode one WAV index-range across NSHARDS parallel processes, then merge per-point outputs.
# args: <wav-dir> <index-start> <index-end> <out-root> <merged-out> <all-txt-name> [extra harness args...]
sharded_decode() {
  local wav_dir="$1" istart="$2" iend="$3" out_root="$4" merged="$5" name="$6"; shift 6
  rm -rf "$out_root" "$merged"
  mkdir -p "$out_root" "$(dirname "$out_root")"   # ensure the shard-log redirect target dir exists
  local pids=()
  for ((i=0; i<NSHARDS; i++)); do
    "$HARN" --wav-dir "$wav_dir" --index-start "$istart" --index-end "$iend" \
            --shard-index "$i" --shard-count "$NSHARDS" \
            --out-dir "$out_root/shard$i" --all-txt-name "$name" \
            --progress-every 200 "$@" > "$out_root.shard$i.log" 2>&1 &
    pids+=($!)
  done
  local rc=0
  for p in "${pids[@]}"; do wait "$p" || rc=1; done
  [ "$rc" -eq 0 ] || { echo "FATAL: a decode shard failed under $out_root"; return 1; }
  python "$DRV" merge-shards --root "$out_root" --out "$merged" --all-txt-name "$name"
}

# ── Phase A — plan + tune/validate split ──────────────────────────────────────────────
if [[ "$PHASES" == *A* ]]; then
  echo "== Phase A: plan/split =="
  python "$DRV" plan --wav-dir "$CORPUS" | tee "$WORK/plan.txt"
  python "$DRV" split-ts --wav-dir "$CORPUS" \
      --out-tune "$WORK/tune_ts.txt" --out-validate "$WORK/validate_ts.txt"
fi
HALF="$(sed -n 's/^HALF=//p' "$WORK/plan.txt")"
TOTAL="$(sed -n 's/^TOTAL=//p' "$WORK/plan.txt")"

# ── Phase B — FP synthetic corpora (S5, S7) + canonical per-slot alignment ─────────────
if [[ "$PHASES" == *B* ]]; then
  echo "== Phase B: FP corpora =="
  mkdir -p "$WORK/fp"
  for s in s5:s5-noise s7:s7-compounding; do
    tag="${s%%:*}"; file="${s##*:}"
    rm -rf "$WORK/fp/$tag"
    python "$SCEN/../harness/run_scenario.py" "$SCEN/$file.json" --dry-run \
        --run-dir "$HERE/_work/fp/$tag/gen" --dump-wav-dir "$HERE/_work/fp/$tag/wavs" \
        > "$WORK/fp/$tag.gen.log" 2>&1
    python "$DRV" fp-corpus --wav-dir "$WORK/fp/$tag/wavs" \
        --gen-truth "$WORK/fp/$tag/gen/truth.csv" --out-dir "$WORK/fp/$tag/canon"
  done
fi

# ── Phase C — FP decode (45 points) + score ───────────────────────────────────────────
if [[ "$PHASES" == *C* ]]; then
  echo "== Phase C: FP decode + score =="
  for tag in s5 s7; do
    sharded_decode "$WORK/fp/$tag/wavs" 0 100000 \
        "$WORK/fp/$tag/dec_shards" "$WORK/fp/$tag/decoded" "$FP_NAME" \
        --manifest "$WORK/fp/$tag/canon/manifest.csv"
  done
  python "$DRV" score-fp \
      --s5-corpus "$WORK/fp/s5/canon" --s7-corpus "$WORK/fp/s7/canon" \
      --s5-decoded "$WORK/fp/s5/decoded" --s7-decoded "$WORK/fp/s7/decoded" \
      --work "$WORK/fp/score" --out "$WORK/fp.csv"
fi

# ── Phase D — recall TUNE decode (45 points over [0,HALF)) + score ─────────────────────
if [[ "$PHASES" == *D* ]]; then
  echo "== Phase D: recall TUNE decode + score =="
  sharded_decode "$CORPUS" 0 "$HALF" \
      "$WORK/recall/tune_shards" "$WORK/recall/tune_decoded" "$RECALL_NAME"
  python "$DRV" score-recall --wsjt "$WSJT" --decoded-dir "$WORK/recall/tune_decoded" \
      --split-ts "$WORK/tune_ts.txt" --out "$WORK/recall_tune.csv" --label tune
fi

# ── Phase E — assemble tune verdict, pick candidate ───────────────────────────────────
if [[ "$PHASES" == *E* ]]; then
  echo "== Phase E: assemble (tune) =="
  python "$DRV" assemble --recall "$WORK/recall_tune.csv" --fp "$WORK/fp.csv" \
      --out "$WORK/sweep_tune.csv" | tee "$WORK/verdict_tune.txt"
fi

# ── Phase F — recall VALIDATE decode (baseline + candidate over [HALF,TOTAL)) + score ──
if [[ "$PHASES" == *F* ]]; then
  echo "== Phase F: recall VALIDATE decode + score =="
  CAND="${CANDIDATE:-}"
  if [ -z "$CAND" ]; then
    # Best Pareto win on tune, else fall back to the highest-recall point (still reported
    # as out-of-sample even when it is not a clean win — honesty over the tune result).
    CAND="$(python "$DRV" assemble --recall "$WORK/recall_tune.csv" --fp "$WORK/fp.csv" \
             --out /dev/null 2>/dev/null | sed -n 's/.*Best: \([a-z0-9_.]*\).*/\1/p' | head -1)"
  fi
  if [ -z "$CAND" ]; then
    echo "No candidate (baseline dominates on tune) — validate arm scores baseline only."
    POINTS="k10_c0.10_n60"
  else
    echo "Validate candidate: $CAND"
    POINTS="k10_c0.10_n60,$CAND"
  fi
  sharded_decode "$CORPUS" "$HALF" "$TOTAL" \
      "$WORK/recall/val_shards" "$WORK/recall/val_decoded" "$RECALL_NAME" \
      --points "$POINTS"
  python "$DRV" score-recall --wsjt "$WSJT" --decoded-dir "$WORK/recall/val_decoded" \
      --split-ts "$WORK/validate_ts.txt" --out "$WORK/recall_validate.csv" --label validate
fi

echo "== run_sweep done (phases: $PHASES) =="
