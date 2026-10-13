#!/bin/bash
# OLD-CPU SPEED step 0, the PROFILING build on sol (QA tooling; spec 2026-10-13-1630 section 3 + amendment 1 C5). No src/ or native/ change in the repo:
# the first run's source (main 76aa48cd + the replay-only override patch) is checked out into a SCRATCH worktree, and only that scratch copy of
# native/ft8_lib_build/build_linux.sh gets two extra flags: -g -fno-omit-frame-pointer. Everything else is the first build's recipe, same compiler.
#
#   build_profile_linux.sh          (HOME-relative; refuses while any other job is on)
#
# Outputs under ~/qa-scratch/old-cpu-profile/: src/ (scratch worktree), bin/ (RefSet harness + the profiling libft8.so), PIN.txt (its SHA-256),
# FLAGS.diff (the one changed line), BUILD-NOTES.txt. The profiling .so is a pin of its own and never a product pin.
set -euo pipefail
BASE="$HOME/qa-scratch/old-cpu-profile"
SRC="$BASE/src"
OUT="$BASE/bin"
HARNESS="$HOME/refset-src/qa/rr-study/refset/harness"
REPO="$HOME/OpenWSFZ"
COMMIT=76aa48cd
PATCH="$HOME/override-src.patch"
EXPECT_PATCH_SHA=af42583b33fb9869adfda8dc86fbe157c612fcd36e90e20f473d2cd2063ec1bf

if pgrep -f "run_refset|run_leg_e|OpenWSFZ.Daemon|aplay|bin/wsjtx|bin/jt9|queue_" > /dev/null 2>&1; then echo "REFUSED: another job is on this machine (a compile loads the CPU)"; exit 1; fi
mkdir -p "$BASE"
[ "$(sha256sum "$PATCH" | cut -d' ' -f1)" = "$EXPECT_PATCH_SHA" ] || { echo "STOP: $PATCH is not the first run's managed patch ($EXPECT_PATCH_SHA)"; exit 2; }
FULL=$(git -C "$REPO" rev-parse "$COMMIT^{commit}")
[ -d "$SRC" ] || git -C "$REPO" worktree add -q --detach "$SRC" "$FULL"
[ "$(git -C "$SRC" rev-parse HEAD)" = "$FULL" ] || { echo "STOP: scratch worktree is not $FULL"; exit 2; }

RECIPE="$SRC/native/ft8_lib_build/build_linux.sh"
cp "$RECIPE" "$BASE/build_linux.sh.original"
OLD='-O2 -Wall -fPIC'
NEW='-O2 -g -fno-omit-frame-pointer -Wall -fPIC'
[ "$(grep -c -- "$OLD" "$RECIPE")" = "1" ] || { echo "STOP: the recipe does not contain exactly one '$OLD'"; exit 2; }
sed -i "s/$OLD/$NEW/" "$RECIPE"
diff -u "$BASE/build_linux.sh.original" "$RECIPE" > "$BASE/FLAGS.diff" || true
[ "$(grep -c '^[-+][^-+]' "$BASE/FLAGS.diff")" = "2" ] || { echo "STOP: the flag change is not exactly one line"; cat "$BASE/FLAGS.diff"; exit 2; }

nice -n 10 env SRC="$SRC" APPLY_PATCH="$PATCH" REPO="$REPO" bash "$HARNESS/build_native_linux.sh" "$FULL" - "$HARNESS" "$OUT"

SO_SHA=$(sha256sum "$OUT/libft8.so" | cut -d' ' -f1)
echo "$SO_SHA  libft8.so (PROFILING build: -g -fno-omit-frame-pointer; never a product pin)" > "$BASE/PIN.txt"
{
  echo "built_utc=$(date -u +%FT%TZ)"
  echo "source_commit=$FULL (main 76aa48cd) + managed override patch sha256=$EXPECT_PATCH_SHA"
  echo "profile_so_sha256=$SO_SHA"
  echo "first_run_so_sha256=dc517dc9ba88b78618535fcf9da4ad8bcf3db18cfd4a68e186459520bd618e6c (built from the same recipe without the two flags)"
  echo "gcc=$(gcc --version | head -1)"
  echo "recipe_changed_line:"; grep '^[-+][^-+]' "$BASE/FLAGS.diff"
  echo "harness_Program_cs_sha256=$(sha256sum "$HARNESS/Program.cs" | cut -d' ' -f1)  (adds per-cycle fittedSignals and --cycle-range; otherwise the first run's)"
} > "$BASE/BUILD-NOTES.txt"
cat "$BASE/BUILD-NOTES.txt"
