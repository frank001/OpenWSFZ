#!/usr/bin/env python3
"""
FP-REGRESSION -- E1.1/E1.2: pre-registered binary manifest assertion + ROW 0b.

Spec: qa/rr-study/2026-09-04-1432-architect-to-qa-spec-fp-regression-bisect.md, section 4, ROW 0b.
Pack: qa/rr-study/2026-09-04-1441-architect-to-qa-execution-pack-fp-regression.md, E1.

Predicate ships as code (HK-021(r)). Prints every row's inputs, threshold and verdict,
then the first firing verdict. Recomputes every SHA256 independently -- never trusts the
manifest table in the pack. A mismatch is STOP, not a note.

Windows (per spec section 2 / pack E1.1):
  Window A = B1 -> B5 (departure from zero, in-chain rate moved: 0/120 -> 1/120)
  Window B = B6 -> B8 (further rise, in-chain rate moved: 1/120 -> 4/120)

ROW 0b FIRES iff the win-x64 DLL SHA256 is unchanged across an ENTIRE window in which the
in-chain rate moved.
"""
import hashlib
import subprocess
import sys

DLL_PATH = "src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll"

# Pre-registered manifest (pack E1.1 table). Recomputed independently below; this dict is
# the ASSERTION target, not the source of truth.
MANIFEST = [
    ("B1", "2026-08-05", "3bd4cd0", "f2f30c890b253eb6b69aa1a89c26d2991ee70aa2a202c68361130344bb7d4015", "last 0/120 sweep"),
    ("B2", "2026-08-12", "9500e03", "c559a049d103c1f350f1a87b319033d5f8d1a2f91b74d9756d8d7cf03d2e6112", "HASH_TABLE_SIZE 256->4096"),
    ("B3", "2026-08-14", "3bc2b9d", "fa87bd9779c4dba831b792f5bc2608f29db875d7ce8d6c535f93e094b485e6b8", "vendored rebuild, all 11 objects"),
    ("B4", "2026-08-14", "af2f466", "fe0b7d534e06fd4d1f79575739af650f78a524861cb195178a1c1c9036139cdc", "r1 sync refiner"),
    ("B5", "2026-08-14/15", "aa434cb", "04cedc598593e89569b7212deef66efaa413322994216108841525ca2ebc45bf", "r1b; first 1/120 sweep"),
    ("B6", "2026-08-21", "7d36038", "1889408787a2c7ea545dbe8477691b090417a74fc81116cbf1ea52413bfbdb3a", "1/120 sweep"),
    ("B7", "2026-08-22", "7ed8b0c", "a3d32b7839a0fd73dcc8d35bd514d60f962f3267179fd77cbd8a1ebd6ecc8d45", "Phase B / fusion normalisation"),
    ("B8", "2026-08-22", "c3a9ea8", "bc8efcf148046f199c057b62c7987c4b69f2dc62d72509458a671305ab051d7f", "neg. time_offset fix; 4/120 sweep"),
]

# B5 and B8 each have a second equivalent ref in the record (identical content at a second
# commit). Recompute both and confirm they agree, but the manifest row is keyed on the first.
ALT_REFS = {
    "B5": "8d6e1b1",
    "B8": "f5dec23",
}


def sha256_of_git_blob(ref: str, path: str) -> str:
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        capture_output=True, check=True,
    )
    return hashlib.sha256(result.stdout).hexdigest()


def main() -> int:
    print("=== E1.1 -- manifest assertion (recomputed independently, HK-021(p)) ===")
    computed = {}
    mismatch = False
    for label, date, sha, expected, note in MANIFEST:
        try:
            actual = sha256_of_git_blob(sha, DLL_PATH)
        except subprocess.CalledProcessError as e:
            print(f"{label} {sha} : EXTRACTION FAILED: {e}")
            mismatch = True
            continue
        computed[label] = actual
        ok = (actual == expected)
        mismatch = mismatch or not ok
        print(f"{label} {date:14s} {sha}  manifest={expected}")
        print(f"{'':17s}{'':7s}          computed={actual}  {'OK' if ok else 'MISMATCH <-- STOP'}")

    for label, alt_sha in ALT_REFS.items():
        try:
            alt_actual = sha256_of_git_blob(alt_sha, DLL_PATH)
        except subprocess.CalledProcessError as e:
            print(f"{label} alt-ref {alt_sha} : EXTRACTION FAILED: {e}")
            mismatch = True
            continue
        agrees = (alt_actual == computed.get(label))
        mismatch = mismatch or not agrees
        print(f"{label} alt-ref {alt_sha}: computed={alt_actual}  "
              f"{'AGREES with primary ref' if agrees else 'DISAGREES <-- STOP'}")

    print()
    if mismatch:
        print("MANIFEST ASSERTION: MISMATCH FOUND -- STOP per pack E1.1 ('any mismatch is STOP, not a note').")
        return 1
    print("MANIFEST ASSERTION: all 8 rows + both alt-refs match. Proceeding to ROW 0b.")

    print()
    print("=== E1.2 -- ROW 0b ===")
    print("Predicate (spec sec.4 ROW 0b): FIRES iff win-x64 DLL SHA256 is UNCHANGED across an")
    print("entire window in which the in-chain rate moved.")
    print()

    windows = [
        ("Window A", "B1", "B5", "0/120 (2026-08-05) -> 1/120 (2026-08-15)"),
        ("Window B", "B6", "B8", "1/120 (2026-08-21) -> 4/120 (2026-08-22)"),
    ]

    row0b_fires = False
    for wname, start_label, end_label, rate_move in windows:
        start_sha = computed[start_label]
        end_sha = computed[end_label]
        unchanged = (start_sha == end_sha)
        row0b_fires = row0b_fires or unchanged
        print(f"{wname}: {start_label}->{end_label}  in-chain rate moved {rate_move}")
        print(f"  {start_label} SHA256 = {start_sha}")
        print(f"  {end_label} SHA256 = {end_sha}")
        print(f"  binary SHA {'UNCHANGED' if unchanged else 'CHANGED'} across window "
              f"{'<-- fires' if unchanged else '(does not fire on this window)'}")
        print()

    print(f"ROW 0b VERDICT: {'FIRES' if row0b_fires else 'DOES NOT FIRE'}")
    if row0b_fires:
        print("Consequence: movement in the firing window is NOT attributable to the native binary;")
        print("attention moves to managed src/ or harness/config state for that window.")
    else:
        print("Consequence: both windows contain a real binary change; ROW 1 can bisect either.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
