#!/usr/bin/env python3
"""
check_glibc_floor.py -- fail if a Linux ELF shared object needs a newer glibc than the declared floor.

Usage:
  python3 tools/check_glibc_floor.py <path-to-libft8.so>   # the guard
  python3 tools/check_glibc_floor.py --self-test           # the guard's own tests (stdlib only, no binutils)

Why it exists: the committed src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so is built on the CI runner, and the
glibc symbol versions it needs are the BUILD HOST's. When `ubuntu-latest` moved to an image with glibc 2.43 the
bot committed a .so that needs GLIBC_2.43, and every older host (WSL Debian 13 = 2.41, Ubuntu 24.04 = 2.39)
failed to load it with "version 'GLIBC_2.43' not found". Nothing noticed for a day. This guard makes the
next occurrence fail in CI on the push that causes it (Architect ruling arch/cross-cycle-prior c414bdb1, R-G3).

How: reads the ELF's .gnu.version_r (the "version needs" table) directly, so it needs neither objdump nor
readelf and runs anywhere Python does. The highest GLIBC_x.y[.z] it finds is printed and compared with
GLIBC_FLOOR.

Exit codes: 0 highest needed glibc <= floor; 1 above the floor; 2 usage error or not a readable x86-64/ELF64 LE file.
"""
import re
import struct
import sys

# The ONE place the floor is named: the lowest glibc the committed Linux libft8.so must load on (Ubuntu 24.04).
# The CI build image (ubuntu-24.04 in .github/workflows/ci.yml) is what keeps the build at or below it.
GLIBC_FLOOR = (2, 39)

_SHT_GNU_VERNEED = 0x6FFFFFFE
_GLIBC_RE = re.compile(rb"^GLIBC_(\d+)\.(\d+)(?:\.(\d+))?$")


def _cstr(blob: bytes, off: int) -> bytes:
    end = blob.index(b"\0", off)
    return blob[off:end]


def glibc_versions_needed(data: bytes) -> list[tuple[int, ...]]:
    """Every GLIBC_x.y[.z] named in the ELF's version-needs table, as tuples (e.g. (2, 43))."""
    if data[:4] != b"\x7fELF" or data[4] != 2 or data[5] != 1:
        raise ValueError("not a 64-bit little-endian ELF file")
    e_shoff, = struct.unpack_from("<Q", data, 0x28)
    e_shentsize, e_shnum = struct.unpack_from("<HH", data, 0x3A)
    sections = []
    for i in range(e_shnum):
        # name, type, flags, addr, offset, size, link, info, addralign, entsize
        sections.append(struct.unpack_from("<IIQQQQIIQQ", data, e_shoff + i * e_shentsize))
    found: list[tuple[int, ...]] = []
    for (_n, sh_type, _f, _a, sh_off, sh_size, sh_link, sh_info, _al, _es) in sections:
        if sh_type != _SHT_GNU_VERNEED:
            continue
        strtab_off = sections[sh_link][4]
        pos = sh_off
        for _ in range(sh_info):                      # sh_info = number of Verneed entries
            _ver, cnt, _file, aux, nxt = struct.unpack_from("<HHIII", data, pos)
            apos = pos + aux
            for _j in range(cnt):
                _hash, _flags, _other, name, anext = struct.unpack_from("<IHHII", data, apos)
                m = _GLIBC_RE.match(_cstr(data, strtab_off + name))
                if m:
                    found.append(tuple(int(g) for g in m.groups() if g is not None))
                apos += anext
            pos += nxt
    return found


def highest_glibc(data: bytes) -> tuple[int, ...] | None:
    v = glibc_versions_needed(data)
    return max(v) if v else None


def fmt(v: tuple[int, ...] | None) -> str:
    return "none" if v is None else ".".join(str(x) for x in v)


def check(data: bytes, floor: tuple[int, ...] = GLIBC_FLOOR) -> tuple[bool, tuple[int, ...] | None]:
    """(ok, highest). A .so needing no GLIBC version at all is ok."""
    hi = highest_glibc(data)
    return (hi is None or hi <= floor), hi


# ---------------------------------------------------------------------------------------------------------------------
# Self-test: a synthetic ELF carrying a chosen set of GLIBC_ versions, so the guard is tested both ways with no
# binutils and no real binary. (The negative test on the REAL 2.43 blob is a command in the change's report.)
# ---------------------------------------------------------------------------------------------------------------------

def _synthetic_elf(needs: list[bytes]) -> bytes:
    strtab = b"\0libc.so.6\0" + b"".join(n + b"\0" for n in needs)
    name_off = [strtab.index(n + b"\0") for n in needs]
    libc_off = 1
    verneed = struct.pack("<HHIII", 1, len(needs), libc_off, 16, 0)
    for i, no in enumerate(name_off):
        verneed += struct.pack("<IHHII", 0, 0, 2 + i, no, 0 if i == len(needs) - 1 else 16)
    shstr = b"\0.dynstr\0.gnu.version_r\0"
    off_str, off_vn, off_sh = 64, 64 + len(strtab), 64 + len(strtab) + len(verneed)
    off_sh = (off_sh + 7) & ~7
    hdr = bytearray(64)
    hdr[0:4] = b"\x7fELF"; hdr[4] = 2; hdr[5] = 1; hdr[6] = 1
    struct.pack_into("<HHIQQQIHHHHHH", hdr, 16, 3, 62, 1, 0, 0, off_sh, 0, 64, 0, 0, 64, 4, 3)
    body = strtab + verneed
    body += b"\0" * (off_sh - 64 - len(body))
    sh = [struct.pack("<IIQQQQIIQQ", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
          struct.pack("<IIQQQQIIQQ", 1, 3, 2, 0, off_str, len(strtab), 0, 0, 1, 0),                       # .dynstr
          struct.pack("<IIQQQQIIQQ", 9, _SHT_GNU_VERNEED, 2, 0, off_vn, len(verneed), 1, 1, 8, 0),        # .gnu.version_r -> .dynstr
          struct.pack("<IIQQQQIIQQ", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)]
    return bytes(hdr) + body + b"".join(sh) + shstr


def self_test() -> int:
    failures = []

    def expect(name: str, cond: bool) -> None:
        print(("ok   " if cond else "FAIL ") + name)
        if not cond:
            failures.append(name)

    below = _synthetic_elf([b"GLIBC_2.2.5", b"GLIBC_2.34", b"GLIBC_2.38"])
    at = _synthetic_elf([b"GLIBC_2.2.5", b"GLIBC_2.39"])
    above = _synthetic_elf([b"GLIBC_2.2.5", b"GLIBC_2.43", b"GLIBC_2.34"])
    plain = _synthetic_elf([b"GCC_3.0"])
    expect("floor constant is 2.39", GLIBC_FLOOR == (2, 39))
    expect("highest of 2.2.5/2.34/2.38 is 2.38", highest_glibc(below) == (2, 38))
    expect("below the floor passes", check(below)[0])
    expect("exactly at the floor passes", check(at)[0] and highest_glibc(at) == (2, 39))
    expect("2.43 fails and is reported", check(above) == (False, (2, 43)))
    expect("2.40 fails (one above the floor)", not check(_synthetic_elf([b"GLIBC_2.40"]))[0])
    expect("2.9 is below 2.39 (numeric, not text, comparison)", check(_synthetic_elf([b"GLIBC_2.9"]))[0])
    expect("no GLIBC version at all passes", check(plain) == (True, None))
    try:
        highest_glibc(b"MZ not an elf")
        expect("a non-ELF file is refused", False)
    except ValueError:
        expect("a non-ELF file is refused", True)
    print("self-test:", "FAILED" if failures else "all passed")
    return 1 if failures else 0


def main(argv: list[str]) -> int:
    if argv == ["--self-test"]:
        return self_test()
    if len(argv) != 1 or argv[0].startswith("-"):
        print(__doc__, file=sys.stderr)
        return 2
    try:
        with open(argv[0], "rb") as f:
            data = f.read()
        ok, hi = check(data)
    except (OSError, ValueError, struct.error, IndexError) as e:
        print(f"ERROR: cannot read {argv[0]}: {e}", file=sys.stderr)
        return 2
    floor = fmt(GLIBC_FLOOR)
    print(f"{argv[0]}: highest GLIBC_ symbol version needed = {fmt(hi)} (floor {floor})")
    if ok:
        print(f"OK: loads on glibc >= {floor}.")
        return 0
    print(f"FAIL: needs GLIBC_{fmt(hi)}, above the floor GLIBC_{floor}. The build image is newer than the floor: "
          f"build on ubuntu-24.04 (see .github/workflows/ci.yml) so the .so loads on glibc {floor} and later.",
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
