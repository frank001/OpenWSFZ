#!/usr/bin/env python3
"""Zero the LC_UUID field of a Mach-O dylib and re-apply an ad-hoc code
signature, so repeated builds from identical object files produce a
byte-identical output.

Background: Apple's ld64/ld-prime embeds a fresh, randomly-generated
LC_UUID load command into every linked Mach-O binary. This made
libft8.dylib differ byte-for-byte between otherwise-identical CI builds
(same source, same shim version) and repeatedly triggered spurious
"binaries changed" auto-PRs from the commit-native-binaries CI job (see
PR #23 and four earlier no-op merges under the label "shim 20260030").

Omitting the load command entirely via `-Wl,-no_uuid` is NOT viable:
dyld refuses to dlopen a Mach-O image with no LC_UUID at all ("missing
LC_UUID load command"), which broke every macOS unit test that loads
libft8.dylib via P/Invoke. dyld only requires the load command to be
*present* — it does not require the UUID value to be unique — so
zeroing the 16-byte value in place (leaving the load command itself
intact) satisfies both constraints: loadable AND reproducible.

Zeroing the UUID changes file bytes, which invalidates ld64's
automatically-applied ad-hoc code signature (its CodeDirectory hashes
cover the whole file). This script re-applies an ad-hoc signature
(`codesign -s -`) after the patch, which is deterministic for identical
input content since no timestamp authority is contacted for ad-hoc
signing.

Usage: zero_dylib_uuid.py <path-to-dylib>
"""
import struct
import subprocess
import sys

MH_MAGIC_64 = 0xFEEDFACF
LC_UUID = 0x1B


def zero_uuid(path: str) -> None:
    with open(path, "r+b") as f:
        data = bytearray(f.read())
        magic = struct.unpack_from("<I", data, 0)[0]
        if magic != MH_MAGIC_64:
            raise SystemExit(f"unexpected Mach-O magic 0x{magic:x} in {path} (expected 64-bit Mach-O)")
        ncmds = struct.unpack_from("<I", data, 16)[0]
        offset = 32  # sizeof(mach_header_64)
        for _ in range(ncmds):
            cmd, cmdsize = struct.unpack_from("<2I", data, offset)
            if cmd == LC_UUID:
                uuid_off = offset + 8  # skip cmd (4) + cmdsize (4)
                data[uuid_off:uuid_off + 16] = b"\x00" * 16
                with open(path, "wb") as out:
                    out.write(data)
                return
            offset += cmdsize
        raise SystemExit(f"no LC_UUID load command found in {path}")


def resign(path: str) -> None:
    subprocess.run(["codesign", "--remove-signature", path], check=False)
    subprocess.run(["codesign", "-s", "-", "-f", path], check=True)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: zero_dylib_uuid.py <path-to-dylib>")
    zero_uuid(sys.argv[1])
    resign(sys.argv[1])
    print(f"Zeroed LC_UUID and re-signed {sys.argv[1]}")
