#!/bin/bash
# Build the Linux libft8.so of a given commit's native source, and the replay harness against that checkout. (QA; no src/ or native/ change.)
# Gate RS-V2P (REFERENCE-SET 2l item 2): the native source of the anchor DLL `a14fe354`, built for Linux.
#
#   build_native_linux.sh <commit> <expected-win-dll-sha256|-> <harness-csproj-dir> <out-dir>
#
# 1. Identify the source MECHANICALLY: <commit> must be the commit that tracks win-x64/libft8.dll with the expected SHA-256
#    (`git show <commit>:src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll | sha256sum`). If it does not match: exit 2 = STOP AND ASK.
# 2. Build with the repo's own recipe (native/ft8_lib_build/build_linux.sh), record the .so SHA-256, compiler and host.
# 3. Build the harness against that checkout into <out-dir>, and check that the library beside the harness is the one just built.
# Must NOT run while a study run or a replay is on (the machine is one resource; compiling loads the CPU).
set -euo pipefail
COMMIT="$1"; EXPECT_DLL="$2"; HARNESS_DIR="$3"; OUT="$4"
REPO="${REPO:-$HOME/OpenWSFZ}"
SRC="${SRC:-$HOME/native-src-${COMMIT:0:8}}"

git -C "$REPO" fetch -q origin
if [ ! -d "$SRC" ]; then git -C "$REPO" worktree add -q --detach "$SRC" "$COMMIT"; fi
HEAD_SHA=$(git -C "$SRC" rev-parse HEAD)
[ "$HEAD_SHA" = "$(git -C "$REPO" rev-parse "$COMMIT^{commit}")" ] || { echo "checkout is not $COMMIT"; exit 2; }
DLL_SHA=$(git -C "$SRC" show "HEAD:src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll" | sha256sum | cut -d' ' -f1)
if [ "$EXPECT_DLL" != "-" ] && [ "$DLL_SHA" != "$EXPECT_DLL" ]; then
  echo "STOP AND ASK: commit $HEAD_SHA tracks a Windows DLL with SHA $DLL_SHA, not $EXPECT_DLL"; exit 2
fi
COMMITTED_SO_SHA=$(git -C "$SRC" show "HEAD:src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so" | sha256sum | cut -d' ' -f1)

bash "$SRC/native/ft8_lib_build/build_linux.sh" > "$OUT.native-build.log" 2>&1 || { tail -20 "$OUT.native-build.log"; exit 3; }
BUILT="$SRC/native/ft8_lib_build/libft8.so"
SO_SHA=$(sha256sum "$BUILT" | cut -d' ' -f1)

# Optional: a source patch applied to the managed code before the harness build (the replay-only budget override, spec 2m).
# The patch SHA-256 is recorded; an already-applied patch is accepted (reverse check), anything else that does not apply stops the build.
PATCH_SHA="none"
if [ -n "${APPLY_PATCH:-}" ]; then
  PATCH_SHA=$(sha256sum "$APPLY_PATCH" | cut -d' ' -f1)
  if git -C "$SRC" apply --check "$APPLY_PATCH" 2>/dev/null; then git -C "$SRC" apply "$APPLY_PATCH";
  elif git -C "$SRC" apply --check -R "$APPLY_PATCH" 2>/dev/null; then echo "patch already applied";
  else echo "STOP: the patch does not apply to $HEAD_SHA"; exit 6; fi
fi

mkdir -p "$OUT"
dotnet build "$HARNESS_DIR/RefSet.csproj" -c Release -p:RepoRoot="$SRC" -o "$OUT" > "$OUT.harness-build.log" 2>&1 || { tail -20 "$OUT.harness-build.log"; exit 4; }
cp "$BUILT" "$OUT/libft8.so"
[ "$(sha256sum "$OUT/libft8.so" | cut -d' ' -f1)" = "$SO_SHA" ] || { echo "library beside the harness is not the one just built"; exit 5; }

cat > "$OUT/NATIVE-BUILD.txt" <<EOF
source_commit=$HEAD_SHA
windows_dll_sha256_tracked_at_commit=$DLL_SHA
expected_windows_dll_sha256=$EXPECT_DLL
linux_so_sha256_built_here=$SO_SHA
linux_so_sha256_committed_at_commit=$COMMITTED_SO_SHA
gcc=$(gcc --version | head -1)
host=$(uname -srm)
recipe=native/ft8_lib_build/build_linux.sh at the source commit (-O2, no -march)
managed_patch_sha256=$PATCH_SHA
built_utc=$(date -u +%FT%TZ)
EOF
cat "$OUT/NATIVE-BUILD.txt"
