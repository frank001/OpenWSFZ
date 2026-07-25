#!/usr/bin/env python3
"""Phase 1 orchestrating driver -- ties rewindow.py + D001ParamSweep + score_recall.py
together across a list of delta offsets against one reference arm.

Explicitly the piece flagged as "not yet built" in the Phase 0 findings and confirmed
still open in the Architect's ruling (SPEC.md section 14/section 9). Reusable for Phase
1a (asymmetry probe, a handful of deltas) and Phase 1b (the full 27-point grid) -- same
mechanics, just a longer --deltas list and (for 1b) --segment-index/--k-range covering
the stratified 400-cycle sample instead of one segment's first 25 cycles.

Applies the SPEC.md section 7.3 provenance guard and section 7.4(b)'s hash-token
normalization fix (score_recall.normalize_hash_tokens) by default for every comparison
-- see 2026-07-25-phase0b-findings.md for why the latter is recommended going forward
even though it did not move Phase 0's own figures.

HK-009: reconfigure stdout to UTF-8. NFR-021: all outputs stay under --work-dir, which
callers must keep git-ignored (see .gitignore in this directory -- _work/ is covered).
"""
from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import rewindow as rw  # noqa: E402
from score_recall import (  # noqa: E402
    parse_all_txt, load_manifest, build_cycle_sets, paired_recall, summarize,
    check_provenance, check_no_collisions,
)


def delta_tag(delta: float) -> str:
    sign = "p" if delta >= 0 else "n"
    return f"{sign}{abs(delta):06.3f}".replace(".", "")


def rewindow_and_decode(wav_dir: Path, work_dir: Path, delta: float, segment_index: int,
                         k_start: int, k_end: int, harness: str, point: str) -> tuple[Path, Path]:
    """Returns (manifest_path, all_txt_path). Idempotent-ish: reuses an existing decode
    if the target directory already has an ALL.TXT (cheap re-run safety for a long sweep)."""
    tag = delta_tag(delta)
    out_dir = work_dir / f"d{tag}"
    manifest_path, _prov = rw.do_rewindow(
        wav_dir, out_dir, delta, [segment_index], k_start, k_end, clean=True,
    )
    decoded_dir = work_dir / f"d{tag}_decoded"
    all_txt = decoded_dir / point / "ALL.TXT"
    cmd = ["dotnet" if harness.endswith(".dll") else harness]
    if harness.endswith(".dll"):
        cmd.append(harness)
    cmd += ["--wav-dir", str(out_dir), "--out-dir", str(decoded_dir), "--all-txt-name", "ALL.TXT",
            "--manifest", str(manifest_path), "--points", point]
    print(f"[delta={delta}] decoding {out_dir} -> {decoded_dir}")
    subprocess.run(cmd, check=True)
    return manifest_path, all_txt


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--wav-dir", required=True)
    ap.add_argument("--work-dir", required=True)
    ap.add_argument("--harness", required=True)
    ap.add_argument("--segment-index", type=int, required=True)
    ap.add_argument("--k-start", type=int, required=True)
    ap.add_argument("--k-end", type=int, required=True)
    ap.add_argument("--deltas", required=True, help="comma-separated delta values, e.g. -1.0,-1.375,-1.75")
    ap.add_argument("--ref-delta", type=float, default=0.0)
    ap.add_argument("--point", default="k10_c0.10_n60")
    ap.add_argument("--min-ref", type=int, default=5)
    ap.add_argument("--no-normalize-hash-tokens", action="store_true",
                     help="disable the section 7.4(b) hash-token fix (kept as an escape hatch; "
                          "not recommended, see 2026-07-25-phase0b-findings.md)")
    ap.add_argument("--out", required=True, help="summary CSV path")
    args = ap.parse_args()

    wav_dir = Path(args.wav_dir)
    work_dir = Path(args.work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    normalize = not args.no_normalize_hash_tokens

    deltas = [float(x) for x in args.deltas.split(",")]

    # Reference arm.
    ref_manifest, ref_all_txt = rewindow_and_decode(
        wav_dir, work_dir, args.ref_delta, args.segment_index, args.k_start, args.k_end,
        args.harness, args.point,
    )
    ref_rows = parse_all_txt(ref_all_txt)
    ref_map = load_manifest(ref_manifest)
    ref_sets, ref_merges = build_cycle_sets(ref_rows, ref_map, normalize_hash=normalize)
    check_no_collisions(ref_merges, "reference arm")

    rows_out = []
    for delta in deltas:
        if delta == args.ref_delta:
            # The whitelisted identity anchor -- reuse the already-decoded reference arm
            # rather than re-decoding (also the only way check_provenance's manifest-path
            # equality test can recognise it as the anchor).
            test_manifest, test_all_txt = ref_manifest, ref_all_txt
        else:
            test_manifest, test_all_txt = rewindow_and_decode(
                wav_dir, work_dir, delta, args.segment_index, args.k_start, args.k_end,
                args.harness, args.point,
            )

        is_identity = check_provenance(ref_manifest, test_manifest, shift=0)

        test_rows = parse_all_txt(test_all_txt)
        test_map = load_manifest(test_manifest)
        test_sets, test_merges = build_cycle_sets(test_rows, test_map, normalize_hash=normalize)
        check_no_collisions(test_merges, f"test arm delta={delta}")

        results, excluded = paired_recall(test_sets, ref_sets, shift=0, min_ref=args.min_ref)
        summary = summarize(results)

        if is_identity and not (summary["n_cycles"] and summary["min"] == 1.0 and summary["max"] == 1.0):
            raise SystemExit(f"FATAL: identity anchor (delta={delta}) did not return exactly 1.0000.")

        label = "IDENTITY" if is_identity else ""
        print(f"delta={delta:+.3f} {label}: n_cycles={summary['n_cycles']} "
              f"excluded={excluded} median={summary['median']}")
        rows_out.append({
            "delta": delta, "is_identity": is_identity,
            "n_cycles": summary["n_cycles"], "excluded_low_ref": excluded,
            "median": summary["median"], "q1": summary["q1"], "q3": summary["q3"],
            "mean": summary["mean"], "min": summary["min"], "max": summary["max"],
        })

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(rows_out[0].keys()))
        wr.writeheader()
        wr.writerows(rows_out)
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
