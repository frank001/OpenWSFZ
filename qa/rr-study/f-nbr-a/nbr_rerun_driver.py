"""NBR-RERUN (spec: qa/rr-study/2026-09-16-1745-architect-to-qa-spec-nbr-rerun-
current-binary.md) -- ROW 0a-0d, then C1/C2/C3 on OLD and NEW binaries.

Deliberately reuses part_c.run_part_c() verbatim (HK-018) -- the exact same
scenes/seeds F-NBR-A measured with. Does NOT import or call part_b (spec Sec.0.4:
"part_b.py reads a live ALL.TXT -- DO NOT RUN PART B", out of scope here) or
part_a/row0 (NBR-RERUN Sec.2 measures C1/C2/C3 only).

DLL selection is done by pointing dll_common.DLL_PATH at the file under test
before calling dll_common.load_decoder() -- no shared file (native/ft8_lib_build/
libft8.dll) is ever modified by this script.
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "r2-coherent-llr-instrument"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n1-extract-llrs-at-position"))
sys.path.insert(0, HERE)

import dll_common as DC  # noqa: E402
import part_c as PC  # noqa: E402
from extract_llrs_ctypes import dll_sha256  # noqa: E402
from ldpc_decode_ctypes import LdpcDecodeLLRs  # noqa: E402

OLD_DLL_CANDIDATES = [
    # Not in THIS worktree's own artefacts/ -- gitignored data does not travel
    # between worktrees (operational-note-persona-worktrees-2026-09-06.md).
    # Located instead in the Architect's worktree root (D:\...\OpenWSFZ\artefacts\...),
    # copied here 2026-09-17 and hash-verified immediately after copy (both
    # candidates independently match the F-NBR-A pin -- disclosed in the report).
    os.path.join(REPO_ROOT, "artefacts", "nbr-rerun-2026-09-17", "old-dll-input", "base_libft8.dll"),
    os.path.join(REPO_ROOT, "artefacts", "nbr-rerun-2026-09-17", "old-dll-input", "B8_c3a9ea8_libft8.dll"),
]
OLD_DLL_SHA256 = "bc8efcf148046f199c057b62c7987c4b69f2dc62d72509458a671305ab051d7f"
OLD_SHIM_VERSION = 20260046

# native/ft8_lib_build/libft8.dll does not exist in THIS worktree (per-worktree
# native build artefact, never built here since the 2026-09-06 worktree split --
# dll_common.py's own default assumes the pre-split single-tree layout). The
# actual shipped binary this worktree's src/ was built against lives here
# instead, hash-verified below against the same pin (91997e38...).
NEW_DLL_PATH = os.path.join(REPO_ROOT, "src", "OpenWSFZ.Ft8", "Native", "win-x64", "libft8.dll")
NEW_DLL_SHA256 = "91997e38038d9328edcb49cd1e8661706d0092ed2c73e808094c96c3980ad2c6"
NEW_SHIM_VERSION = 20260051

BASELINE_JSON = os.path.join(HERE, "results", "f-nbr-a-results.json")


def log(msg):
    print(msg, flush=True)


def find_old_dll() -> "str | None":
    for p in OLD_DLL_CANDIDATES:
        if os.path.exists(p) and dll_sha256(p) == OLD_DLL_SHA256:
            return p
    return None


def run_part_c_with(dll_path: str, expected_sha256: str, expected_shim: int) -> dict:
    actual = dll_sha256(dll_path)
    if actual != expected_sha256:
        raise RuntimeError(f"{dll_path}: SHA mismatch, expected {expected_sha256}, got {actual}")
    dec = LdpcDecodeLLRs(dll_path, verify=True, expected_sha256=expected_sha256,
                          expected_shim_version=expected_shim, check_version=True)
    return PC.run_part_c(dec, log)


def diff_against_baseline(new_part_c: dict, baseline_part_c: dict) -> list:
    diffs = []
    if new_part_c["c1"] != baseline_part_c["c1"]:
        diffs.append(("c1", baseline_part_c["c1"], new_part_c["c1"]))
    for i, (a, b) in enumerate(zip(baseline_part_c["c2"]["rows"], new_part_c["c2"]["rows"])):
        if a != b:
            diffs.append((f"c2[{i}]", a, b))
    for i, (a, b) in enumerate(zip(baseline_part_c["c3"]["rows"], new_part_c["c3"]["rows"])):
        if a != b:
            diffs.append((f"c3[{i}]", a, b))
    return diffs


def main():
    log("=" * 78)
    log("ROW 0a -- retrieve + reproduce with the OLD (F-NBR-A, 08-23) binary")
    log("=" * 78)
    old_path = find_old_dll()
    if old_path is None:
        log("STOP: old DLL (sha256=%s) not found at any known location. "
            "Per spec Sec.1 ROW 0a, do not proceed with a one-sided comparison." % OLD_DLL_SHA256)
        sys.exit(2)
    log(f"Old DLL found: {old_path}  (sha256 verified = {OLD_DLL_SHA256})")

    baseline = json.load(open(BASELINE_JSON, encoding="utf-8"))
    baseline_part_c = baseline["part_c"]

    part_c_old = run_part_c_with(old_path, OLD_DLL_SHA256, OLD_SHIM_VERSION)
    diffs_0a = diff_against_baseline(part_c_old, baseline_part_c)
    row_0a_pass = len(diffs_0a) == 0
    log(f"\nROW 0a: reproduces f-nbr-a-results.json part_c exactly: "
        f"{'PASS' if row_0a_pass else 'FAIL'}")
    if diffs_0a:
        for d in diffs_0a:
            log(f"  MISMATCH {d[0]}: baseline={d[1]} vs old-DLL-rerun={d[2]}")
        log("\nSTOP per ROW 0a: cannot interpret any old-vs-new difference "
            "(confounded with harness/interpreter drift). Not proceeding to the new binary.")
        sys.exit(3)

    log("\n" + "=" * 78)
    log("ROW 0b -- pin the NEW (shipped) binary")
    log("=" * 78)
    actual_new_sha = dll_sha256(NEW_DLL_PATH)
    row_0b_pass = actual_new_sha == NEW_DLL_SHA256
    log(f"New DLL: {NEW_DLL_PATH}")
    log(f"  expected sha256={NEW_DLL_SHA256}")
    log(f"  actual   sha256={actual_new_sha}")
    log(f"ROW 0b: {'PASS' if row_0b_pass else 'FAIL'}")
    if not row_0b_pass:
        log("STOP per ROW 0b.")
        sys.exit(4)

    log("\n" + "=" * 78)
    log("ROW 0c -- determinism on the NEW binary (two full Part-C runs)")
    log("=" * 78)
    part_c_new_1 = run_part_c_with(NEW_DLL_PATH, NEW_DLL_SHA256, NEW_SHIM_VERSION)
    part_c_new_2 = run_part_c_with(NEW_DLL_PATH, NEW_DLL_SHA256, NEW_SHIM_VERSION)
    j1 = json.dumps(part_c_new_1, sort_keys=True)
    j2 = json.dumps(part_c_new_2, sort_keys=True)
    row_0c_pass = (j1 == j2)
    log(f"ROW 0c: two new-binary runs byte-identical: {'PASS' if row_0c_pass else 'FAIL'}")
    if not row_0c_pass:
        log("STOP per ROW 0c: non-deterministic result invalidates the exact-match logic.")
        sys.exit(5)

    out = {
        "row_0a_pass": row_0a_pass,
        "row_0b_pass": row_0b_pass,
        "row_0c_pass": row_0c_pass,
        "old_dll_path": old_path,
        "old_dll_sha256": OLD_DLL_SHA256,
        "new_dll_path": NEW_DLL_PATH,
        "new_dll_sha256": NEW_DLL_SHA256,
        "part_c_old": part_c_old,
        "part_c_new": part_c_new_1,
        "baseline_part_c": baseline_part_c,
    }
    out_dir = os.path.join(REPO_ROOT, "artefacts", "nbr-rerun-2026-09-17")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "nbr_rerun_result.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    log(f"\nWrote {out_dir}/nbr_rerun_result.json (NFR-021: synthetic Q-prefix scene, no real callsigns)")

    log("\n" + "=" * 78)
    log("C1/C2/C3 -- OLD vs NEW, side by side")
    log("=" * 78)
    log(f"C1 (E present/removed): old={part_c_old['c1']}  new={part_c_new_1['c1']}")
    for i, (o, n) in enumerate(zip(part_c_old["c2"]["rows"], part_c_new_1["c2"]["rows"])):
        log(f"C2 delta={o['delta_hz']:>7.2f}Hz: old={o['hits']:3d}/100  new={n['hits']:3d}/100")
    for i, (o, n) in enumerate(zip(part_c_old["c3"]["rows"], part_c_new_1["c3"]["rows"])):
        log(f"C3 snr_F={o['snr_f_db']:>6.1f}dB: old={o['hits']:3d}/100  new={n['hits']:3d}/100")

    r_f_baseline_new = part_c_new_1["c1"]["r_baseline"] / 100.0
    c2_hits_new = [r["hits"] for r in part_c_new_1["c2"]["rows"]]
    c2_deltas = [r["delta_hz"] for r in part_c_new_1["c2"]["rows"]]
    first_ge_90 = next((d for d, h in zip(c2_deltas, c2_hits_new) if h >= 90), None)

    log(f"\nR(F) baseline on new binary = {r_f_baseline_new:.2f}")
    log(f"First delta with R>=0.90 on new binary = {first_ge_90} Hz")

    if r_f_baseline_new <= 0.05 and first_ge_90 is not None and abs(first_ge_90 - 31.25) <= 6.25:
        reading = "G1 -- UNCHANGED. The defect survives the current binary."
    elif r_f_baseline_new >= 0.50:
        reading = "G2 -- MATERIALLY REDUCED. The assessment is STALE."
    else:
        reading = "G3 -- MOVED, NOT RESOLVED."
    log(f"\nREADING: {reading}")


if __name__ == "__main__":
    main()
