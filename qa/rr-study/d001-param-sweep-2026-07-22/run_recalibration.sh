#!/usr/bin/env bash
# D-009 recalibration — full orchestration.
# Executes qa/rr-study/2026-08-05-2003-architect-to-qa-spec-d009-recalibration.md via the
# EXISTING d001-param-sweep-2026-07-22 harness (Program.cs unmodified; sweep_driver.py
# unmodified; only density_stratify.py is new, for spec Sec.5.4 which had no 07-22 precedent).
#
# Differences from run_sweep.sh (the 07-22 precedent this reuses):
#   - Recall arm: ONE full decode over the decisive epoch (no tune/validate split — the
#     recalibration spec's decision rule is defined directly on the whole corpus).
#   - Recall corpus: 20260803_live_run_1713/owsfz/wav, restricted to the epoch starting
#     260803_185914 via --index-start (computed, not hardcoded).
#   - FP arm: s5-noise-wide.json / s7-compounding.json (spec's named files, not ea88d12's
#     s5-noise.json), decoded WITH --debug-log for Sec.5.4; S5 and S7 strictly sequential
#     (spec Sec.4 constraint 1 — CONTAMINATED.md precedent), never concurrent processes.
#   - New Phase G: density_stratify.py per point per scenario -> fp_by_density.csv.
#
# All raw data stays under $WORK (git-ignored, NFR-021); only sweep_grid.csv,
# fp_by_density.csv, report.md are meant to be committed (by the caller, after review).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
QA_RR="$(cd "$HERE/.." && pwd)"
HARN="$HERE/bin/Release/net10.0/D001ParamSweep.exe"
DRV="$HERE/sweep_driver.py"
DENS="$HERE/density_stratify.py"

MAIN_WT="$(git -C "$QA_RR" worktree list --porcelain | awk '/^worktree /{print $2; exit}')"
RUN="$MAIN_WT/artefacts/20260803_live_run_1713"
CORPUS="${CORPUS:-$RUN/owsfz/wav}"
WSJT="${WSJT:-$RUN/wsjt-x/ALL.TXT}"
SCEN="${SCEN:-$QA_RR/scenarios}"
NSHARDS="${NSHARDS:-16}"
WORK="$HERE/_work_recal"
PHASES="${PHASES:-ABCDEFG}"
RESULT_DIR="${RESULT_DIR:-$QA_RR/results/2026-08-05-f6c5b46-d009-recalibration}"

RECALL_NAME="OpenWSFZ ALL.TXT"
FP_NAME="owsfz-all.txt"
EPOCH_CUTOFF="260803_185914"
mkdir -p "$WORK" "$RESULT_DIR"

log() { echo "[$(date -u +%H:%M:%S)] $*"; }

sharded_decode() {
  local wav_dir="$1" istart="$2" iend="$3" out_root="$4" merged="$5" name="$6"; shift 6
  rm -rf "$out_root" "$merged"
  mkdir -p "$out_root" "$(dirname "$out_root")"
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
  [ "$rc" -eq 0 ] || { log "FATAL: a decode shard failed under $out_root"; return 1; }
  python "$DRV" merge-shards --root "$out_root" --out "$merged" --all-txt-name "$name"
}

# Merge per-point decode.log across shards too (density_stratify needs ONE ordered log per
# point; shard N only saw every NSHARDS-th WAV, so shard order != canonical WAV order — for
# the FP arm we therefore decode WITHOUT sharding, see Phase C, so this helper is unused there).

# ── Phase A: plan (epoch index, in-epoch ts list — no tune/validate split) ────────────────
if [[ "$PHASES" == *A* ]]; then
  log "Phase A: plan"
  ALL_TOTAL=$(ls "$CORPUS" | wc -l)
  ISTART=$(ls "$CORPUS" | sort | awk -v c="${EPOCH_CUTOFF}" '$0 < c' | wc -l)
  log "owsfz wav total=$ALL_TOTAL  epoch-start-index=$ISTART (cutoff $EPOCH_CUTOFF)"
  echo "$ISTART" > "$WORK/istart.txt"
  echo "$ALL_TOTAL" > "$WORK/itotal.txt"
  ls "$CORPUS" | sort | awk -v c="${EPOCH_CUTOFF}" '$0 >= c' | sed 's/\.wav$//' > "$WORK/epoch_ts.txt"
  log "in-epoch ts count: $(wc -l < "$WORK/epoch_ts.txt")"
fi
ISTART="$(cat "$WORK/istart.txt")"
ITOTAL="$(cat "$WORK/itotal.txt")"

# ── Phase B: FP synthetic corpora — S5 THEN S7, sequential (spec Sec.4 constraint 1) ───────
if [[ "$PHASES" == *B* ]]; then
  log "Phase B: FP corpora (sequential S5 -> S7)"
  mkdir -p "$WORK/fp"
  for s in s5:s5-noise-wide s7:s7-compounding; do
    tag="${s%%:*}"; file="${s##*:}"
    log "  generating $tag from $file.json"
    rm -rf "$WORK/fp/$tag"
    python "$QA_RR/harness/run_scenario.py" "$SCEN/$file.json" --dry-run \
        --run-dir "$HERE/_work_recal/fp/$tag/gen" --dump-wav-dir "$HERE/_work_recal/fp/$tag/wavs" \
        > "$WORK/fp/$tag.gen.log" 2>&1
    python "$DRV" fp-corpus --wav-dir "$WORK/fp/$tag/wavs" \
        --gen-truth "$WORK/fp/$tag/gen/truth.csv" --out-dir "$WORK/fp/$tag/canon"
    log "  $tag done: $(wc -l < "$WORK/fp/$tag/wavs"/*.wav 2>/dev/null | tail -1 || ls "$WORK/fp/$tag/wavs" | wc -l) wavs"
  done
fi

# ── Phase C: FP decode (45 points, --debug-log, UNSHARDED so decode.log stays WAV-ordered) ─
# S5 then S7 sequential — same constraint as Phase B, never run as concurrent processes.
if [[ "$PHASES" == *C* ]]; then
  log "Phase C: FP decode + score (sequential S5 -> S7, debug-log on)"
  for tag in s5 s7; do
    log "  decoding $tag (45 points, single process for WAV-order decode.log)"
    rm -rf "$WORK/fp/$tag/decoded"
    "$HARN" --wav-dir "$WORK/fp/$tag/wavs" \
        --manifest "$WORK/fp/$tag/canon/manifest.csv" \
        --out-dir "$WORK/fp/$tag/decoded" --all-txt-name "$FP_NAME" \
        --progress-every 20 --debug-log > "$WORK/fp/$tag.decode.log" 2>&1
    log "  $tag decode done"
  done
  python "$DRV" score-fp \
      --s5-corpus "$WORK/fp/s5/canon" --s7-corpus "$WORK/fp/s7/canon" \
      --s5-decoded "$WORK/fp/s5/decoded" --s7-decoded "$WORK/fp/s7/decoded" \
      --work "$WORK/fp/score" --out "$WORK/fp.csv"
fi

# ── Phase D: recall decode — FULL epoch, ONE arm, sharded 16-way ───────────────────────────
if [[ "$PHASES" == *D* ]]; then
  log "Phase D: recall decode (epoch [$ISTART,$ITOTAL), $NSHARDS shards)"
  sharded_decode "$CORPUS" "$ISTART" "$ITOTAL" \
      "$WORK/recall/shards" "$WORK/recall/decoded" "$RECALL_NAME"
  log "Phase D: recall score"
  python "$DRV" score-recall --wsjt "$WSJT" --decoded-dir "$WORK/recall/decoded" \
      --split-ts "$WORK/epoch_ts.txt" --out "$WORK/recall.csv" --label full-epoch
fi

# ── Phase E: assemble grid ──────────────────────────────────────────────────────────────
if [[ "$PHASES" == *E* ]]; then
  log "Phase E: assemble"
  python "$DRV" assemble --recall "$WORK/recall.csv" --fp "$WORK/fp.csv" \
      --out "$WORK/sweep_grid.csv" | tee "$WORK/verdict.txt"
  cp "$WORK/sweep_grid.csv" "$RESULT_DIR/sweep_grid.csv"
fi

# ── Phase F: pre-registered ROW rule (spec Sec.5) ───────────────────────────────────────
if [[ "$PHASES" == *F* ]]; then
  log "Phase F: ROW rule evaluation"
  python "$HERE/apply_row_rule.py" --grid "$WORK/sweep_grid.csv" --out "$WORK/row_verdict.txt"
  cat "$WORK/row_verdict.txt"
fi

# ── Phase G: Sec.5.4 density stratification (FP arm only, reported not gated) ──────────────
if [[ "$PHASES" == *G* ]]; then
  log "Phase G: density stratification"
  rm -f "$WORK/fp_by_density.csv"
  for pd in $(python -c "import sys; sys.path.insert(0,'$HERE'); import sweep_driver as sd; print('\n'.join(sd.point_dir(*p) for p in sd.grid_points()))" | tr -d '\r'); do
    for tag_scen in "s5:S5" "s7:S7"; do
      tag="${tag_scen%%:*}"; scen="${tag_scen##*:}"
      python "$DENS" --point "$pd" --scenario "$scen" \
          --manifest "$WORK/fp/$tag/canon/manifest.csv" \
          --decode-log "$WORK/fp/$tag/decoded/$pd/decode.log" \
          --matched-csv "$WORK/fp/score/${pd}__${scen}/${scen}_matched.csv" \
          --out-append "$WORK/fp_by_density.csv"
    done
  done
  cp "$WORK/fp_by_density.csv" "$RESULT_DIR/fp_by_density.csv"
  log "Phase G done -> $RESULT_DIR/fp_by_density.csv"
fi

log "run_recalibration.sh done (phases: $PHASES)"
