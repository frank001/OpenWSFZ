#!/usr/bin/env bash
# OWS-REPLAY-CONSISTENCY driver (QA, runs on sol). ONE sweep, one named run set. Nothing else may run on sol during R-D8 / R-D1 (the deadline is wall-clock).
#   run_ows_consistency.sh <sweep-dir> <audio-dir> <work-dir> <harness-bin-dir> <expect-native-sha> <runs...>
#   runs: any of  A  W  D8  D1   (D8 / D1 = 3 fresh processes each)         env: PILOT=<n> limits the lists to the first n plays
# <work-dir> must be OUTSIDE git (HK-037: it holds message text); delete it at job close. Exit 2 = pin failed (the SHA of libft8.so differs), exit 10 = a run abandoned a pass
# (reported, never "fixed" by relaxing the deadline: the spec counts abandonments).
set -euo pipefail
SWEEP=$1; AUDIO=$2; WORK=$3; BIN=$4; PIN=$5; shift 5
DOTNET=${DOTNET:-$HOME/.dotnet/dotnet}
HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$WORK"
python3 "$HERE/ows_replay_consistency.py" lists --sweep-dir "$SWEEP" --audio-dir "$AUDIO" --out "$WORK" ${PILOT:+--pilot "$PILOT"}
JIT=${JIT_WAV:-$HERE/../../../tests/OpenWSFZ.Ft8.Tests/Fixtures/synth-qso-01.wav}   # the committed SYNTHETIC fixture (Q-prefix calls), discarded
actual=$(sha256sum "$BIN/libft8.so" | cut -d' ' -f1)
[ "$actual" = "$PIN" ] || { echo "PIN FAILED: actual $actual pinned $PIN"; exit 2; }
one() {  # run-id list threads
  "$DOTNET" "$BIN/RefSet.dll" --wavlist "$WORK/$2" --out-dir "$WORK" --run-id "$1" --jit-wav "$JIT" --nhard 24 --osd-sign-fix 1 --threads "$3" --label "$1"
}
for r in "$@"; do
  case "$r" in
    A)  one R-A  archive_o.tsv 8 ;;
    W)  one R-W  savewav_w.tsv 8 ;;
    D8) for i in 1 2 3; do one "R-D8-$i" archive_o.tsv 8; done ;;
    D1) for i in 1 2 3; do one "R-D1-$i" archive_o.tsv 1; done ;;
    *)  echo "unknown run $r"; exit 1 ;;
  esac
done
echo "pin actual $actual pinned $PIN"
