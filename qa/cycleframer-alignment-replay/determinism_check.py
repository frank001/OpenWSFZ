#!/usr/bin/env python3
"""SPEC.md section 7.4 mandatory determinism control.

Decode one real WAV twice IN THE SAME PROCESS (by feeding the harness a directory
containing two copies of the identical audio under different names) and assert the
resulting decode content (SNR/DT/freq/message, ignoring the ts field which legitimately
differs) is byte-identical between the two copies -- i.e. that decoding earlier WAVs in
the run sequence does not perturb the decoder's behaviour on later, identical audio via
shared mutable state (Ft8Decoder's hashTableRejectCount is process-lifetime cumulative
per the 2026-07-25 QA review; this control is what stands between "probably fine" and
verified).

Usage:
    python3 determinism_check.py --source-wav <path.wav> --work-dir _work/determinism \
        --harness <path to D001ParamSweep.exe>
"""
from __future__ import annotations

import argparse
import csv
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from score_recall import parse_all_txt  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-wav", required=True)
    ap.add_argument("--work-dir", required=True)
    ap.add_argument("--harness", required=True, help="path to D001ParamSweep(.exe)")
    ap.add_argument("--point", default="k10_c0.10_n60")
    ap.add_argument("--n-copies", type=int, default=3,
                     help="how many identical copies to interleave (>2 gives more confidence "
                          "that a *sequence position* effect, not just a two-sample fluke, is absent)")
    args = ap.parse_args()

    work = Path(args.work_dir)
    if work.exists():
        shutil.rmtree(work)
    wav_in = work / "wavs"
    wav_in.mkdir(parents=True)

    base_ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
    manifest_rows = []
    names = []
    for i in range(args.n_copies):
        name = f"copy{i:02d}.wav"
        shutil.copyfile(args.source_wav, wav_in / name)
        ts = base_ts + timedelta(seconds=15 * i)  # well clear of any ts collision
        manifest_rows.append({"wav": name, "cycle_utc": ts.strftime("%Y-%m-%dT%H:%M:%S.000Z")})
        names.append(name)

    manifest_path = wav_in / "manifest.csv"
    with open(manifest_path, "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=["wav", "cycle_utc"])
        wr.writeheader()
        wr.writerows(manifest_rows)

    out_dir = work / "decoded"
    cmd = [args.harness, "--wav-dir", str(wav_in), "--out-dir", str(out_dir),
           "--all-txt-name", "ALL.TXT", "--manifest", str(manifest_path),
           "--points", args.point]
    print("running:", " ".join(cmd))
    subprocess.run(cmd, check=True)

    all_txt = out_dir / args.point / "ALL.TXT"
    rows = parse_all_txt(all_txt)

    # Group by ts (== by copy, since each copy got a unique cycle_utc).
    by_ts: dict[str, list] = {}
    for r in rows:
        by_ts.setdefault(r["ts"], []).append((r["snr"], r["dt"], r["freq"], r["message"]))
    for k in by_ts:
        by_ts[k].sort()

    ts_list = sorted(by_ts.keys())
    if len(ts_list) != args.n_copies:
        print(f"FATAL: expected {args.n_copies} distinct ts groups, got {len(ts_list)} "
              f"({ts_list}) -- cannot run the determinism comparison.")
        sys.exit(2)

    reference = by_ts[ts_list[0]]
    mismatches = []
    for ts in ts_list[1:]:
        if by_ts[ts] != reference:
            mismatches.append(ts)

    print(f"determinism check: {args.n_copies} copies of {Path(args.source_wav).name}, "
          f"decoded at sequence positions {list(range(args.n_copies))}")
    print(f"  copy 0: {len(reference)} decode(s)")
    for i, ts in enumerate(ts_list[1:], start=1):
        status = "MATCH" if ts not in mismatches else "MISMATCH"
        print(f"  copy {i}: {len(by_ts[ts])} decode(s)  [{status}]")

    if mismatches:
        print(f"DETERMINISM CHECK FAILED: {len(mismatches)}/{args.n_copies - 1} later "
              f"copies differ from the first decode of identical audio.")
        sys.exit(1)
    print("DETERMINISM CHECK PASSED: identical audio decoded at different sequence "
          "positions in the same process produces byte-identical output.")


if __name__ == "__main__":
    main()
