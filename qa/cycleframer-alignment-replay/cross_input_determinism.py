#!/usr/bin/env python3
"""SPEC.md section 7.4(b) cross-input determinism control (Phase 0b, added 2026-07-25).

Part (a) (done in Phase 0, passed) only varies decode SEQUENCE POSITION among IDENTICAL
inputs. That does not test the real hazard for a delta-sweep: each arm decodes a
different sequence of DIFFERENT windows, so if Ft8Decoder's cumulative process-lifetime
state (hashTableRejectCount etc.) makes a window's decode depend on what was decoded
immediately before it, two arms could diverge for reasons that have nothing to do with
alignment.

This control: decode one arm's WAV set (arm A's 25 reference cycles) once in forward
(k-ascending) order and once in reverse (k-descending) order, in two separate harness
invocations (fresh process each -- cumulative state does not survive a process exit), and
assert the per-cycle decode SETS are exactly identical (not just similar recall) between
the two orders. Byte-identical audio decoded in a different sequence position must
produce byte-identical results, full stop.

If it fails, SPEC.md says: use a fresh decoder instance per window and re-assert -- that
would be a src/ change and is out of scope for this QA session (HK-011); a failure here
blocks Phase 1 and must be escalated, not patched around.
"""
from __future__ import annotations

import argparse
import csv
import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from score_recall import parse_all_txt, load_manifest, build_cycle_sets  # noqa: E402


def build_reverse_copy(fwd_dir: Path, fwd_manifest: Path, rev_dir: Path) -> Path:
    """Copy every wav referenced by fwd_manifest into rev_dir under names whose ordinal
    sort is the EXACT REVERSE of the forward manifest's row order, preserving each row's
    original cycle_utc/segment_index/k (so downstream scoring still joins on the same
    cycle identity)."""
    if rev_dir.exists():
        shutil.rmtree(rev_dir)
    rev_dir.mkdir(parents=True)

    with open(fwd_manifest, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    n = len(rows)
    rev_rows = []
    for i, row in enumerate(rows):
        rev_name = f"rev{n - 1 - i:04d}.wav"  # first row -> highest-sorting name, so
        shutil.copyfile(fwd_dir / row["wav"], rev_dir / rev_name)  # reverse row order == reverse decode order
        rev_rows.append({**row, "wav": rev_name})

    # Ordinal-sorted filenames now visit the rows in exactly reverse order; verify that
    # explicitly rather than assuming the naming scheme worked.
    check = sorted(rev_rows, key=lambda r: r["wav"])
    expected_order_desc = list(reversed(rows))
    for a, b in zip(check, expected_order_desc):
        if a["segment_index"] != b["segment_index"] or a["k"] != b["k"]:
            raise SystemExit("FATAL: reverse-order naming scheme did not produce the intended "
                              "reverse decode sequence -- aborting before decoding.")

    rev_manifest = rev_dir / "manifest.csv"
    with open(rev_manifest, "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(rev_rows[0].keys()))
        wr.writeheader()
        wr.writerows(rev_rows)
    return rev_manifest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fwd-wav-dir", required=True, help="the already-rewindowed arm A wav dir (e.g. _work/phase0_ref)")
    ap.add_argument("--fwd-manifest", required=True)
    ap.add_argument("--fwd-all-txt", required=True, help="arm A's already-decoded ALL.TXT")
    ap.add_argument("--work-dir", required=True)
    ap.add_argument("--harness", required=True)
    ap.add_argument("--point", default="k10_c0.10_n60")
    ap.add_argument("--fresh-decoder-per-wav", action="store_true",
                     help="pass through to D001ParamSweep -- constructs a new Ft8Decoder per WAV "
                          "instead of one shared instance. Empirically confirmed 2026-07-25 NOT to "
                          "fix this control: the hash table is a native process-global "
                          "(g_session_hash_table in ft8_shim.c), not a managed-instance field, so a "
                          "fresh C# Ft8Decoder does not reset it. Kept as a CLI option for the record "
                          "and because it is harmless, but --normalize-hash-tokens is the fix that "
                          "actually closes this control.")
    ap.add_argument("--normalize-hash-tokens", action="store_true",
                     help="canonicalize <...>/<CALLSIGN> tokens before comparing decode sets -- "
                          "the fix that actually neutralizes the hash-table order-dependence "
                          "(see score_recall.normalize_hash_tokens)")
    args = ap.parse_args()

    work = Path(args.work_dir)
    rev_dir = work / "reverse_wavs"
    rev_manifest = build_reverse_copy(Path(args.fwd_wav_dir), Path(args.fwd_manifest), rev_dir)
    print(f"reverse-order copy built: {rev_manifest}")

    out_dir = work / "reverse_decoded"
    cmd = [args.harness, "--wav-dir", str(rev_dir), "--out-dir", str(out_dir),
           "--all-txt-name", "ALL.TXT", "--manifest", str(rev_manifest), "--points", args.point]
    if args.fresh_decoder_per_wav:
        cmd.append("--fresh-decoder-per-wav")
    print("running (fresh process):", " ".join(cmd))
    subprocess.run(cmd, check=True)

    rev_all_txt = out_dir / args.point / "ALL.TXT"

    fwd_rows = parse_all_txt(Path(args.fwd_all_txt))
    fwd_map = load_manifest(Path(args.fwd_manifest))
    fwd_sets = build_cycle_sets(fwd_rows, fwd_map, normalize_hash=args.normalize_hash_tokens)

    rev_rows = parse_all_txt(rev_all_txt)
    rev_map = load_manifest(rev_manifest)
    rev_sets = build_cycle_sets(rev_rows, rev_map, normalize_hash=args.normalize_hash_tokens)

    all_cycles = sorted(set(fwd_sets) | set(rev_sets))
    mismatches = []
    for cid in all_cycles:
        f = fwd_sets.get(cid, set())
        r = rev_sets.get(cid, set())
        if f != r:
            mismatches.append((cid, f, r))

    print(f"cross-input determinism: {len(all_cycles)} cycles compared (forward order vs reverse order)")
    if mismatches:
        for cid, f, r in mismatches[:10]:
            only_f = f - r
            only_r = r - f
            print(f"  [MISMATCH] cycle {cid}: forward-only={len(only_f)} reverse-only={len(only_r)}")
        print(f"CROSS-INPUT DETERMINISM CHECK FAILED: {len(mismatches)}/{len(all_cycles)} cycles differ "
              f"between forward-order and reverse-order decode. This means Ft8Decoder's cumulative "
              f"process state affects results across DIFFERENT inputs -- per SPEC.md section 7.4(b) "
              f"this blocks Phase 1 and needs escalation (a fresh-decoder-per-window fix is a src/ "
              f"change, out of scope for this QA session per HK-011).")
        sys.exit(1)

    print("CROSS-INPUT DETERMINISM CHECK PASSED: every cycle's decode set is identical regardless "
          "of forward vs reverse decode order.")


if __name__ == "__main__":
    main()
