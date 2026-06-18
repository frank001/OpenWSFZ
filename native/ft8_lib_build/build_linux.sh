#!/bin/bash
set -e
FT8_ROOT=/mnt/d/Projects/claude/OpenWSFZ
BUILD_DIR=$FT8_ROOT/native/ft8_lib_build
SRC_DIR=$FT8_ROOT/src/OpenWSFZ.Ft8/Native
LIB_SRC=/mnt/c/Temp/ft8_lib_headers
OBJ_DIR=$BUILD_DIR/linux_obj

mkdir -p "$OBJ_DIR"

GCC="gcc -std=c11 -D_GNU_SOURCE -O2 -Wall -fPIC -I$LIB_SRC"

echo "Compiling ft8_lib sources..."
$GCC -c "$LIB_SRC/ft8/constants.c" -o "$OBJ_DIR/constants.o"
$GCC -c "$LIB_SRC/ft8/crc.c"       -o "$OBJ_DIR/crc.o"
$GCC -I"$LIB_SRC/ft8" -c "$BUILD_DIR/patched/ft8/decode.c" -o "$OBJ_DIR/decode.o"
$GCC -c "$LIB_SRC/ft8/encode.c"    -o "$OBJ_DIR/encode.o"
$GCC -c "$LIB_SRC/ft8/ldpc.c"      -o "$OBJ_DIR/ldpc.o"
$GCC -c "$LIB_SRC/ft8/message.c"   -o "$OBJ_DIR/message.o"
$GCC -c "$LIB_SRC/ft8/text.c"      -o "$OBJ_DIR/text.o"
$GCC -c "$LIB_SRC/common/monitor.c" -o "$OBJ_DIR/monitor.o"
$GCC -c "$LIB_SRC/fft/kiss_fft.c"  -o "$OBJ_DIR/kiss_fft.o"
$GCC -c "$LIB_SRC/fft/kiss_fftr.c" -o "$OBJ_DIR/kiss_fftr.o"

echo "Compiling ft8_shim.c..."
$GCC -I"$SRC_DIR" -c "$SRC_DIR/ft8_shim.c" -o "$OBJ_DIR/ft8_shim.o"

echo "Linking libft8.so..."
gcc -shared -o "$BUILD_DIR/libft8.so" \
    "$OBJ_DIR/constants.o" \
    "$OBJ_DIR/crc.o" \
    "$OBJ_DIR/decode.o" \
    "$OBJ_DIR/encode.o" \
    "$OBJ_DIR/ldpc.o" \
    "$OBJ_DIR/message.o" \
    "$OBJ_DIR/text.o" \
    "$OBJ_DIR/monitor.o" \
    "$OBJ_DIR/kiss_fft.o" \
    "$OBJ_DIR/kiss_fftr.o" \
    "$OBJ_DIR/ft8_shim.o" \
    -lm

echo "Verifying exports..."
nm -D "$BUILD_DIR/libft8.so" | grep "ft8_"

echo "Copying to repo..."
cp "$BUILD_DIR/libft8.so" "$FT8_ROOT/src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so"
echo "Linux build SUCCESS"
