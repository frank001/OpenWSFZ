#!/usr/bin/env python3
"""Paired within-cycle recall(delta) scorer.

Implements SPEC.md section 5.3: for cycle k and offset delta,

    recall_delta(k) = |decodes(window_delta, k) INTERSECT ref(k)| / |ref(k)|

matched by message text, deduplicated, within-cycle. Cycle identity is (segment_index, k)
-- NOT the wall-clock ts field written into ALL.TXT, because two arms at different delta
label the same underlying window with different (sub-second-truncated) timestamps. The
join key comes from each arm's own manifest.csv (segment_index, k columns), which
rewindow.py writes at generation time.

Also implements SPEC.md section 7's shuffled-pairing control (score cycle k against
ref(k+shift) instead of ref(k) -- must collapse to ~0) via --shift.

HK-009: reconfigure stdout to UTF-8 up front (cp1252 console default).
NFR-021: outputs may reference real third-party callsigns only insofar as message text
is echoed into the (git-ignored) --out CSV; keep --out under _work/.
"""
from __future__ import annotations

import argparse
import csv
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# ALL.TXT parsing -- mirrors Program.cs FormatAllTxtLine:
#   "{ts}     {dialMhz:F3} Rx FT8 {snr,6} {dt,4:F1} {freq,4} {message}"
# ---------------------------------------------------------------------------

def parse_all_txt(path: Path) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    with open(path, encoding="ascii", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\r\n")
            if not line.strip():
                continue
            tok = line.split()
            if len(tok) < 8:
                print(f"[WARN] unparsable ALL.TXT line in {path}: {line!r}", file=sys.stderr)
                continue
            ts, _dial, _rx, _ft8, snr, dt, freq = tok[0], tok[1], tok[2], tok[3], tok[4], tok[5], tok[6]
            message = " ".join(tok[7:])
            rows.append({
                "ts": ts, "snr": snr, "dt": dt, "freq": freq, "message": message,
            })
    return rows


# ---------------------------------------------------------------------------
# Manifest parsing -- ts_field is the SAME truncation D001ParamSweep applies
# (DateTime.ToString("yyMMdd_HHmmss")): floor to whole seconds.
# ---------------------------------------------------------------------------

def parse_cycle_utc(s: str) -> datetime:
    s2 = s[:-1] if s.endswith("Z") else s
    if "." in s2:
        dt = datetime.strptime(s2, "%Y-%m-%dT%H:%M:%S.%f")
    else:
        dt = datetime.strptime(s2, "%Y-%m-%dT%H:%M:%S")
    return dt.replace(tzinfo=timezone.utc)


def load_manifest(path: Path) -> dict:
    """Return (ts_field -> (segment_index, k)), raising on any collision -- an ambiguous
    join would silently corrupt every downstream recall figure (SPEC.md section 3's
    standing rule: never trust a comparison whose provenance wasn't checked)."""
    ts_to_cycle: dict[str, tuple[int, int]] = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            cycle_utc = parse_cycle_utc(row["cycle_utc"])
            ts_field = cycle_utc.strftime("%y%m%d_%H%M%S")
            cycle_id = (int(row["segment_index"]), int(row["k"]))
            if ts_field in ts_to_cycle and ts_to_cycle[ts_field] != cycle_id:
                raise SystemExit(
                    f"FATAL: ts_field collision in {path}: {ts_field!r} maps to both "
                    f"{ts_to_cycle[ts_field]} and {cycle_id}. Pairing would be ambiguous -- "
                    f"refusing to score. (See SPEC.md section 3/7 provenance rule.)"
                )
            ts_to_cycle[ts_field] = cycle_id
    return ts_to_cycle


def build_cycle_sets(all_txt_rows: list[dict], ts_to_cycle: dict) -> dict:
    """cycle_id -> set(message text), deduplicated, per SPEC.md 5.3."""
    sets: dict[tuple[int, int], set] = {}
    unmapped = 0
    for r in all_txt_rows:
        cycle_id = ts_to_cycle.get(r["ts"])
        if cycle_id is None:
            unmapped += 1
            continue
        sets.setdefault(cycle_id, set()).add(r["message"])
    if unmapped:
        print(f"[WARN] {unmapped} ALL.TXT row(s) had a ts field absent from the manifest "
              f"(decode of a wav the manifest doesn't cover?)", file=sys.stderr)
    return sets


# ---------------------------------------------------------------------------
# Paired recall
# ---------------------------------------------------------------------------

def paired_recall(numerator_sets: dict, denominator_sets: dict, shift: int = 0,
                   min_ref: int = 5) -> tuple[list[dict], int]:
    results = []
    excluded_low_ref = 0
    for cycle_id, ref_set in denominator_sets.items():
        if len(ref_set) < min_ref:
            excluded_low_ref += 1
            continue
        seg, k = cycle_id
        shifted_id = (seg, k + shift)
        num_set = numerator_sets.get(shifted_id, set())
        inter = num_set & ref_set
        recall = len(inter) / len(ref_set)
        results.append({
            "segment_index": seg, "k": k, "ref_n": len(ref_set), "num_n": len(num_set),
            "inter_n": len(inter), "recall": recall,
        })
    return results, excluded_low_ref


def summarize(results: list[dict]) -> dict:
    if not results:
        return {"n_cycles": 0, "median": None, "q1": None, "q3": None}
    recalls = sorted(r["recall"] for r in results)
    n = len(recalls)
    median = statistics.median(recalls)
    if n >= 4:
        q1 = statistics.median(recalls[: n // 2])
        q3 = statistics.median(recalls[(n + 1) // 2:])
    else:
        q1 = q3 = median
    return {
        "n_cycles": n, "median": median, "q1": q1, "q3": q3,
        "min": recalls[0], "max": recalls[-1],
        "mean": statistics.mean(recalls),
    }


def cmd_recall(args: argparse.Namespace) -> None:
    ref_rows = parse_all_txt(Path(args.ref_all_txt))
    ref_map = load_manifest(Path(args.ref_manifest))
    ref_sets = build_cycle_sets(ref_rows, ref_map)

    test_all_txt = Path(args.test_all_txt) if args.test_all_txt else Path(args.ref_all_txt)
    test_manifest = Path(args.test_manifest) if args.test_manifest else Path(args.ref_manifest)
    test_rows = parse_all_txt(test_all_txt)
    test_map = load_manifest(test_manifest)
    test_sets = build_cycle_sets(test_rows, test_map)

    results, excluded = paired_recall(test_sets, ref_sets, shift=args.shift, min_ref=args.min_ref)
    summary = summarize(results)

    label = args.label or f"shift={args.shift}"
    print(f"recall[{label}]: n_cycles={summary['n_cycles']} excluded(|ref|<{args.min_ref})={excluded}")
    if summary["n_cycles"]:
        print(f"  median={summary['median']:.4f}  IQR=[{summary['q1']:.4f}, {summary['q3']:.4f}]  "
              f"mean={summary['mean']:.4f}  range=[{summary['min']:.4f}, {summary['max']:.4f}]")
    else:
        print("  (no cycles scored -- check manifests / min-ref threshold)")

    if args.out:
        outp = Path(args.out)
        outp.parent.mkdir(parents=True, exist_ok=True)
        with open(outp, "w", newline="", encoding="utf-8") as fh:
            wr = csv.DictWriter(fh, fieldnames=["segment_index", "k", "ref_n", "num_n", "inter_n", "recall"])
            wr.writeheader()
            wr.writerows(results)
        print(f"  -> {outp}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("recall", help="paired within-cycle recall(delta), or a shuffled-pairing control")
    sp.add_argument("--ref-all-txt", required=True, help="reference (denominator) arm's ALL.TXT")
    sp.add_argument("--ref-manifest", required=True, help="reference arm's manifest.csv")
    sp.add_argument("--test-all-txt", default=None, help="test (numerator) arm's ALL.TXT (default: same as ref, for shuffle control)")
    sp.add_argument("--test-manifest", default=None, help="test arm's manifest.csv (default: same as ref)")
    sp.add_argument("--shift", type=int, default=0, help="k-shift for shuffled-pairing control (SPEC.md section 7.2)")
    sp.add_argument("--min-ref", type=int, default=5, help="exclude cycles with |ref(k)| below this")
    sp.add_argument("--label", default=None)
    sp.add_argument("--out", default=None, help="per-cycle CSV output path")
    sp.set_defaults(fn=cmd_recall)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
