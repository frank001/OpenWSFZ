#!/usr/bin/env bash
# OWS-REPLAY-CONSISTENCY step 3 driver (QA, sol): decode the Z, S and K arms built by `ows_shift_test.py build`, one fresh harness process per arm, R-W's pins and settings.
#   run_shift_arms.sh <shift-dir> <harness-bin-dir> <expect-native-sha>
# Exit 2 = pin failed. <shift-dir> holds audio and lists only (no message text until the decodes.tsv files are written; delete it at job close, HK-037).
set -euo pipefail
SH=$1; BIN=$2; PIN=$3
DOTNET=${DOTNET:-$HOME/.dotnet/dotnet}
HERE=$(cd "$(dirname "$0")" && pwd)
JIT=${JIT_WAV:-$HERE/../../../tests/OpenWSFZ.Ft8.Tests/Fixtures/synth-qso-01.wav}   # the committed SYNTHETIC fixture, discarded
actual=$(sha256sum "$BIN/libft8.so" | cut -d' ' -f1)
[ "$actual" = "$PIN" ] || { echo "PIN FAILED: actual $actual pinned $PIN"; exit 2; }
for arm in Z S K; do
  "$DOTNET" "$BIN/RefSet.dll" --wavlist "$SH/$arm.tsv" --out-dir "$SH" --run-id "SH-$arm" --jit-wav "$JIT" --nhard 24 --osd-sign-fix 1 --threads 8 --label "SH-$arm"
done
echo "pin actual $actual pinned $PIN"
