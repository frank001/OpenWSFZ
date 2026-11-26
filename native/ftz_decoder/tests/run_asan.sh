#!/bin/bash
# run_asan.sh -- builds the lean decoder (ftz_decode_cycle) and its native test harness under AddressSanitizer and
# UndefinedBehaviorSanitizer (GCC, Linux) and runs it. DR-2 step 2a, D6. Used by the CI job `native-asan` and runnable by hand:
#   native/ftz_decoder/tests/run_asan.sh [--runs=N]
# It compiles the same sources, with the same include flags, as native/ft8_lib_build/build_linux.sh (the vendored ft8_lib tree plus the
# patched decode.c and monitor.c), so the sanitizers see exactly the code the shipped library is built from. Exit status 0 = pass; the
# sanitizers abort the process on the first report. The build is in a scratch directory (FTZ_ASAN_OUT or a mktemp dir).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
LIB_SRC="$ROOT/native/ft8_lib_vendor"
PATCHED="$ROOT/native/ft8_lib_build/patched"
SHIM_DIR="$ROOT/src/OpenWSFZ.Ft8/Native"
OUT="${FTZ_ASAN_OUT:-$(mktemp -d)}"
mkdir -p "$OUT"

SAN="-fsanitize=address,undefined -fno-sanitize-recover=undefined -fno-omit-frame-pointer"
GCC="gcc -std=c11 -D_GNU_SOURCE -g -O1 -Wall -fPIC $SAN -pthread"

echo "ASan build in $OUT"
$GCC -I"$LIB_SRC" -c "$LIB_SRC/ft8/constants.c" -o "$OUT/constants.o"
$GCC -I"$LIB_SRC" -c "$LIB_SRC/ft8/crc.c"       -o "$OUT/crc.o"
$GCC -I"$LIB_SRC" -I"$LIB_SRC/ft8" -c "$PATCHED/ft8/decode.c" -o "$OUT/decode.o"
$GCC -I"$LIB_SRC" -c "$LIB_SRC/ft8/encode.c"    -o "$OUT/encode.o"
$GCC -I"$LIB_SRC" -c "$LIB_SRC/ft8/ldpc.c"      -o "$OUT/ldpc.o"
$GCC -I"$LIB_SRC" -c "$LIB_SRC/ft8/message.c"   -o "$OUT/message.o"
$GCC -I"$LIB_SRC" -c "$LIB_SRC/ft8/text.c"      -o "$OUT/text.o"
$GCC -I"$LIB_SRC" -I"$LIB_SRC/common" -c "$PATCHED/common/monitor.c" -o "$OUT/monitor.o"
$GCC -I"$LIB_SRC" -c "$LIB_SRC/fft/kiss_fft.c"  -o "$OUT/kiss_fft.o"
$GCC -I"$LIB_SRC" -c "$LIB_SRC/fft/kiss_fftr.c" -o "$OUT/kiss_fftr.o"
# ft8_shim.c #includes native/ftz_decoder/ftz_decoder.c at its end: the lean engine is compiled with it.
$GCC -I"$LIB_SRC" -I"$SHIM_DIR" -c "$SHIM_DIR/ft8_shim.c" -o "$OUT/ft8_shim.o"
$GCC -I"$LIB_SRC" -I"$SHIM_DIR" -c "$LIB_SRC/refine/sync_refiner.c"      -o "$OUT/sync_refiner.o"
$GCC -I"$LIB_SRC" -I"$SHIM_DIR" -c "$LIB_SRC/refine/coherent_llr.c"      -o "$OUT/coherent_llr.o"
$GCC -I"$LIB_SRC" -I"$SHIM_DIR" -c "$LIB_SRC/refine/coherent_fallback.c" -o "$OUT/coherent_fallback.o"
$GCC -I"$LIB_SRC" -I"$LIB_SRC/subfeas" -c "$LIB_SRC/subfeas/subfeas_fit.c" -o "$OUT/subfeas_fit.o"
$GCC -I"$ROOT/native/ftz_decoder" -c "$ROOT/native/ftz_decoder/tests/ftz_fuzz.c" -o "$OUT/ftz_fuzz.o"

gcc $SAN -pthread -o "$OUT/ftz_fuzz" "$OUT"/*.o -lm

FIX="$ROOT/tests/OpenWSFZ.Ft8.Tests/Fixtures"
export ASAN_OPTIONS="detect_leaks=1:abort_on_error=0:halt_on_error=1"
export UBSAN_OPTIONS="print_stacktrace=1:halt_on_error=1"
"$OUT/ftz_fuzz" "$FIX/synth-qso-01.wav" "$FIX/synth-qso-02.wav" "$FIX/synth-qso-03.wav" "$@"
