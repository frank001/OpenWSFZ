#!/bin/sh
# Unattended queue on sol (QA, 2026-10-11; the Captain: "the tests on sol complete without any attention").
# Runs AFTER the three corrected-chain S1-S8 repeats (~/repeats.sh) end, then builds and runs the FIRST REFERENCE-SET RUN:
#   build = main 76aa48cd (v0.57) + the replay-only budget override (Developer f6a1aa79 src, patch SHA recorded), Linux .so built on sol;
#   standard tier (rounds 1-3 = 33 blocks), legs A for every block, D on round 1 (the quick tier), B (decode only) for every block;
#   OPENWSFZ_SUBTRACTION_BUDGET=unlimited, labelled "first run, baseline" (spec 2l item 5, 2m).
# Safety rules (spec 2l item 2): the driver re-runs an abandoning block once alone; a second abandonment stops it (exit 10) and the queue
# STOPS (never relaxes the deadline). A pin failure (native library SHA, corpus verification) also stops it. Other failures retry up to 3
# times; every finished block is a checkpoint, so a retry resumes.
# State for a human: ~/QUEUE-STATUS.txt (append-only log), ~/QUEUE-RESULT.txt (at the end). Detached by the caller (nohup); no cron (HK-023).
HARNESS=$HOME/refset-src/qa/rr-study/refset/harness
BIN=$HOME/refset-bin-main76aa48cd
ST=$HOME/QUEUE-STATUS.txt
COMMIT=76aa48cd
log() { echo "$(date -u +%FT%TZ) $*" >> "$ST"; }

export DOTNET_ROOT=$HOME/.dotnet PATH=$PATH:$HOME/.dotnet DOTNET_CLI_TELEMETRY_OPTOUT=1

log "queue started (pid $$); waiting for the corrected-chain repeats"
while pgrep -f "repeats.sh" > /dev/null 2>&1; do sleep 60; done
if grep -q "all repeats done" "$HOME/rr-run/repeats.log" 2>/dev/null; then log "repeats ended: all three done"; else log "repeats ended WITHOUT 'all repeats done' (see ~/rr-run/repeats.log); continuing with the reference-set run"; fi
sleep 120   # let the last battery's processes and post-processing settle before compiling

FULL=$(git -C "$HOME/OpenWSFZ" rev-parse "$COMMIT^{commit}" 2>/dev/null)
[ -n "$FULL" ] || { git -C "$HOME/OpenWSFZ" fetch -q origin; FULL=$(git -C "$HOME/OpenWSFZ" rev-parse "$COMMIT^{commit}"); }
log "building $FULL (+ override patch) and the harness"
APPLY_PATCH=$HOME/override-src.patch REPO=$HOME/OpenWSFZ bash "$HARNESS/build_native_linux.sh" "$FULL" - "$HARNESS" "$BIN" > "$HOME/queue-build.log" 2>&1
rc=$?
if [ $rc -ne 0 ]; then log "STOP: build failed rc=$rc (see ~/queue-build.log)"; exit 1; fi
SHA=$(sha256sum "$BIN/libft8.so" | cut -d' ' -f1)
log "built: .so SHA-256 $SHA; $(grep -E 'managed_patch_sha256|gcc=' "$BIN/NATIVE-BUILD.txt" | tr '\n' ' ')"

RUNLOG=$HOME/queue-run.log
export OPENWSFZ_SUBTRACTION_BUDGET=unlimited
try=1
while [ $try -le 3 ]; do
  log "reference-set run: attempt $try"
  "$HOME/rr-venv/bin/python" -s -E "$HARNESS/run_refset.py" --corpus "$HOME/rr-s6-refset-corpus" --bin "$BIN" --scratch "$HOME/qa-scratch/refset-first" \
    --pass "first-run-$COMMIT-standard" --tier standard --legs A,D,B --d-scope quick --expect-native-sha "$SHA" \
    --jit-wav "$HOME/refset-src/tests/OpenWSFZ.Ft8.Tests/Fixtures/synth-qso-01.wav" \
    --label "first run, baseline: main $COMMIT + replay-only subtraction budget override (unlimited), Linux .so built on sol, sol FX-8350" >> "$RUNLOG" 2>&1
  rc=$?
  [ $rc -eq 0 ] && break
  if [ $rc -eq 10 ]; then log "STOP AND ASK: a residual-pass abandonment at one process under the override (exit 10). Nothing relaxed; see $RUNLOG"; exit 10; fi
  if tail -5 "$RUNLOG" | grep -qE "PIN FAILED|native library SHA|corpus verification"; then log "STOP: a pin or corpus check failed (rc=$rc); see $RUNLOG"; exit 11; fi
  log "driver failed rc=$rc on attempt $try; retrying (finished blocks are checkpoints)"
  try=$((try + 1)); sleep 60
done
if [ $rc -ne 0 ]; then log "STOP: driver failed 3 times (last rc=$rc); see $RUNLOG"; exit 12; fi

AGG="$HOME/qa-scratch/refset-first/first-run-$COMMIT-standard/aggregate.json"
{
  echo "FIRST RUN COMPLETE $(date -u +%FT%TZ)"
  echo "aggregate: $AGG"
  "$HOME/rr-venv/bin/python" -s -E - "$AGG" <<'PY'
import json, sys
a = json.load(open(sys.argv[1]))
print(a["banner"]); print("blocks", a["blocks"], "legs", a["legs"], "abandonments", a["abandonments_first"])
print("timing", a["timing_seconds_per_block"]); print("residual ms", a["residual_pass_ms_scored_cycles"])
print("leg A vs live OWS shares", a["leg_A_vs_live_ows"]["shares"]); print("leg D vs A shares", a.get("leg_D_vs_A", {}).get("shares"))
PY
} > "$HOME/QUEUE-RESULT.txt" 2>&1
log "FIRST RUN COMPLETE; see ~/QUEUE-RESULT.txt (working files with message text stay in ~/qa-scratch/refset-first until job close)"
