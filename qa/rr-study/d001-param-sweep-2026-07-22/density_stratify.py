"""D-009 recalibration -- spec Sec.5.4 density stratification (NEW; no 07-22 precedent).

For one grid point's --debug-log decode.log (FP arm only, S5 or S7), pair consecutive
"pass 1 of 2" / "pass 2 of 2" lines exactly as candidate_saturation_check.py already does
(same regex, same consecutive-pairing method -- reused, not reinvented). Each pair corresponds
to exactly one WAV decode call, in WAV-iteration order, which is also canonical-slot order for
the FP arm (fp-corpus assigns synthetic cycle_utc in the same sorted-WAV order). candidates per
slot = pass-0 + pass-1 count (the total raw OSD load for that cycle).

Joined against that point's <scenario>_matched.csv false_positive=True rows (by slot index, via
the canonical manifest.csv wav->cycle_utc mapping already produced by `sweep_driver.py
fp-corpus`) to get FP-per-slot, then bucketed into the pre-registered
0-9/10-24/25-49/50-99/100+ buckets.

Reported column only (spec Sec.5.4) -- carries no ROW, cannot VOID anything.

Usage:
    python density_stratify.py --point k10_c0.10_n60 \
        --scenario S5 --manifest _work/fp/s5/canon/manifest.csv \
        --decode-log _work/fp/s5/dec_shards_merged/k10_c0.10_n60/decode.log \
        --matched-csv _work/fp/score/k10_c0.10_n60__S5/S5_matched.csv \
        --out-append fp_by_density.csv
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="ascii", errors="replace")

LINE_RE = re.compile(
    r"Iterative subtraction: pass (\d) of 2, (\d+) candidates found, (\d+) decoded\.")

BUCKETS = [(0, 9), (10, 24), (25, 49), (50, 99), (100, None)]


def bucket_label(n: int) -> str:
    for lo, hi in BUCKETS:
        if hi is None and n >= lo:
            return f"{lo}+"
        if hi is not None and lo <= n <= hi:
            return f"{lo}-{hi}"
    raise AssertionError(f"candidate count {n} matched no bucket")


def pair_cycles(decode_log: Path) -> list[int]:
    """Return per-WAV total candidate count (pass-0 + pass-1), in log order."""
    cycles: list[int] = []
    pending = None
    with open(decode_log, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = LINE_RE.search(line)
            if not m:
                continue
            pass_no, cand = int(m.group(1)), int(m.group(2))
            if pass_no == 1:
                if pending is not None:
                    cycles.append(pending)  # unpaired pass-1 -- record alone, not dropped
                pending = cand
            elif pass_no == 2:
                if pending is None:
                    cycles.append(cand)  # unpaired pass-2 -- record alone
                else:
                    cycles.append(pending + cand)
                    pending = None
    if pending is not None:
        cycles.append(pending)
    return cycles


def load_manifest_order(manifest: Path) -> list[str]:
    """wav filenames in the same sorted order fp-corpus assigned canonical ts to."""
    rows = list(csv.DictReader(open(manifest, encoding="utf-8")))
    return [r["wav"] for r in sorted(rows, key=lambda r: r["wav"])]


def load_fp_cycle_utcs(matched_csv: Path) -> set[str]:
    fps = set()
    with open(matched_csv, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["appraiser"] == "OpenWSFZ" and r["false_positive"] == "True":
                fps.add(r["cycle_utc"])
    return fps


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--point", required=True)
    ap.add_argument("--scenario", required=True, choices=["S5", "S7"])
    ap.add_argument("--manifest", required=True, type=Path)
    ap.add_argument("--decode-log", required=True, type=Path)
    ap.add_argument("--matched-csv", required=True, type=Path)
    ap.add_argument("--out-append", required=True, type=Path)
    args = ap.parse_args()

    wav_order = load_manifest_order(args.manifest)
    cycles = pair_cycles(args.decode_log)
    if len(cycles) != len(wav_order):
        print(f"WARNING [{args.point}/{args.scenario}]: {len(cycles)} decode.log cycle-pairs "
              f"vs {len(wav_order)} manifest WAVs -- counts disagree, truncating to the shorter "
              f"(unpaired lines at EOF are the likely cause; not silently ignored).",
              file=sys.stderr)
    n = min(len(cycles), len(wav_order))

    # canonical cycle_utc per WAV index, matching sweep_driver.fp_corpus's _FP_BASE + 15*i scheme
    from datetime import datetime, timedelta, timezone
    fp_base = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    idx_to_ts = {i: (fp_base + timedelta(seconds=15 * i)).strftime("%Y-%m-%dT%H:%M:%SZ")
                 for i in range(n)}

    fp_ts = load_fp_cycle_utcs(args.matched_csv)

    bucket_slots: dict[str, int] = {}
    bucket_fps: dict[str, int] = {}
    for i in range(n):
        b = bucket_label(cycles[i])
        bucket_slots[b] = bucket_slots.get(b, 0) + 1
        if idx_to_ts[i] in fp_ts:
            bucket_fps[b] = bucket_fps.get(b, 0) + 1

    write_header = not args.out_append.exists()
    with open(args.out_append, "a", newline="", encoding="ascii") as fh:
        wr = csv.writer(fh)
        if write_header:
            wr.writerow(["point", "scenario", "bucket", "slot_count", "fp_count",
                         "fp_per_100_slots"])
        for lo, hi in BUCKETS:
            b = f"{lo}+" if hi is None else f"{lo}-{hi}"
            slots = bucket_slots.get(b, 0)
            fps = bucket_fps.get(b, 0)
            rate = round(100.0 * fps / slots, 2) if slots else 0.0
            wr.writerow([args.point, args.scenario, b, slots, fps, rate])

    print(f"density_stratify[{args.point}/{args.scenario}]: {n} slots -> {args.out_append}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
