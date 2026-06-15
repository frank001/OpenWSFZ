#!/usr/bin/env python3
"""
check_native_version.py — verify that a committed native binary contains the
expected FT8_SHIM_VERSION before the CI native-build step overwrites it.

Usage:
  python3 tools/check_native_version.py <binary_path> <expected_version>

Called by CI immediately before the native rebuild step so that a developer
who bumps FT8_SHIM_VERSION without refreshing the committed binary gets a
hard CI failure with a clear remediation message rather than silently running
tests against a freshly-rebuilt binary that masks the stale committed one.

Supported binary formats
  ELF   (Linux  x86_64) — version stored as a contiguous LE int32 literal.
  PE    (Windows x64  ) — version stored as a contiguous LE int32 literal.
  Mach-O (macOS ARM64) — version encoded as a mov w0,#lo / movk w0,#hi,lsl16
                          ARM64 instruction pair; NOT a contiguous byte sequence.
                          Both halves must be present to avoid false positives on
                          the shared high-half (0x0135 across all shim versions
                          in the 20260001–20269999 range).

Exit codes
  0  binary is current (contains expected version)
  1  binary is stale   (does not contain expected version) — fails the CI step
  2  usage / argument error
"""
import os
import struct
import sys


# ---------------------------------------------------------------------------
# Format-specific scanners
# ---------------------------------------------------------------------------

def _find_le_int32(data: bytes, value: int) -> bool:
    """True if *value* appears as a contiguous little-endian int32 anywhere."""
    return data.find(struct.pack("<i", value)) != -1


def _find_arm64_mov_pair(data: bytes, value: int) -> bool:
    """True if an ARM64 mov/movk pair encoding *value* is present.

    ARM64 mov  w0, #imm16       (hw=00, Rd=0): 0x52800000 | (imm16 << 5)
    ARM64 movk w0, #imm16,lsl16 (hw=01, Rd=0): 0x72A00000 | (imm16 << 5)

    Both halves are required so that coincidental matches on the shared
    high-half across shim versions cannot produce a false positive.
    """
    lo = value & 0xFFFF
    hi = (value >> 16) & 0xFFFF
    mov_instr  = struct.pack("<I", 0x52800000 | (lo << 5))
    movk_instr = struct.pack("<I", 0x72A00000 | (hi << 5))
    return data.find(mov_instr) != -1 and data.find(movk_instr) != -1


# ---------------------------------------------------------------------------
# Binary format detection
# ---------------------------------------------------------------------------

def _detect_format(data: bytes) -> str:
    if data[:4] == b"\xcf\xfa\xed\xfe":   # Mach-O 64-bit LE (arm64 / x86_64)
        return "macho-arm64"
    if data[:4] == b"\x7fELF":
        return "elf"
    if data[:2] == b"MZ":
        return "pe"
    return "unknown"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <binary_path> <expected_version>",
              file=sys.stderr)
        return 2

    path, version_str = sys.argv[1], sys.argv[2]

    try:
        expected = int(version_str)
    except ValueError:
        print(f"ERROR: expected_version must be an integer, got {version_str!r}",
              file=sys.stderr)
        return 2

    if not os.path.exists(path):
        print(f"MISSING: {path}", file=sys.stderr)
        print("The committed native binary was not found.  Rebuild it locally "
              "and commit before pushing a FT8_SHIM_VERSION bump.",
              file=sys.stderr)
        return 1

    with open(path, "rb") as fh:
        data = fh.read()

    fmt = _detect_format(data)
    print(f"Binary : {path}")
    print(f"Size   : {len(data):,} bytes")
    print(f"Format : {fmt}")
    print(f"Expect : FT8_SHIM_VERSION = {expected}")

    if fmt == "macho-arm64":
        found = _find_arm64_mov_pair(data, expected)
    elif fmt in ("elf", "pe"):
        found = _find_le_int32(data, expected)
    else:
        # Unknown format — skip silently rather than block an unrelated push.
        print(f"WARNING: unrecognised binary format (magic {data[:4].hex()}) "
              f"— version check skipped")
        return 0

    if found:
        print(f"Result : OK — binary contains shim version {expected}")
        return 0

    # Stale binary — fail loudly with actionable remediation.
    print(f"Result : STALE — binary does NOT contain shim version {expected}",
          file=sys.stderr)
    print("", file=sys.stderr)
    print("The committed native binary is out of date with FT8_SHIM_VERSION "
          f"in ft8_shim.h / Ft8LibInterop.cs (expected {expected}).",
          file=sys.stderr)
    print("Rebuild the library locally and commit the updated binary, then "
          "re-push.  See src/OpenWSFZ.Ft8/Native/BUILD.md for instructions.",
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
