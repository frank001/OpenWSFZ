"""Decode log matcher for the OpenWSFZ R&R study harness.

Usage:
    python harness/matcher.py --run-dir <dir> --scenario <id> [--wsjt <path>] [--owsfz <path>]

Joins injected-truth metadata (truth.csv) with the ALL.TXT decode logs from
WSJT-X and OpenWSFZ, normalising timestamps to the FT8 15-second cycle slot,
and emits a tidy long-format matched CSV for downstream analysis.
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# Resolve qa/rr-study as package root
_QA_ROOT = Path(__file__).resolve().parent.parent
if str(_QA_ROOT) not in sys.path:
    sys.path.insert(0, str(_QA_ROOT))

from harness.common import AllTxtRecord, normalise_slot, parse_all_txt

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

APPRAISERS = ("WSJT-X", "OpenWSFZ")
FREQ_TOLERANCE_HZ = 4.0

MATCHED_COLUMNS = [
    "scenario_id", "part_index", "trial_index", "seed", "appraiser", "message_text",
    "true_snr_db", "true_dt_s", "true_freq_hz",
    "reported_snr_db", "reported_dt_s", "reported_freq_hz",
    "matched", "false_positive", "cycle_utc",
]

_TRUTH_COLUMNS_REQUIRED = {
    "scenario_id", "part_index", "trial_index", "seed",
    "true_snr_db", "true_dt_s", "true_freq_hz", "message_text", "cycle_utc",
}

# ---------------------------------------------------------------------------
# Input loading
# ---------------------------------------------------------------------------

def _resolve_paths(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    """Return (truth_path, wsjt_path, owsfz_path), resolving from --run-dir if needed."""
    if args.run_dir:
        run_dir = Path(args.run_dir)
        truth_path = run_dir / "truth.csv"
        wsjt_path = run_dir / "wsjt-all.txt"
        owsfz_path = run_dir / "owsfz-all.txt"
    else:
        truth_path = Path(args.truth) if args.truth else None
        wsjt_path = Path(args.wsjt) if args.wsjt else None
        owsfz_path = Path(args.owsfz) if args.owsfz else None

    # Allow explicit overrides regardless of --run-dir
    if args.wsjt:
        wsjt_path = Path(args.wsjt)
    if args.owsfz:
        owsfz_path = Path(args.owsfz)
    if args.truth:
        truth_path = Path(args.truth)

    if not truth_path or not truth_path.exists():
        sys.exit(f"ERROR: truth.csv not found: {truth_path}")
    if not wsjt_path or not wsjt_path.exists():
        sys.exit(f"ERROR: WSJT-X ALL.TXT not found: {wsjt_path}")
    if not owsfz_path or not owsfz_path.exists():
        sys.exit(f"ERROR: OpenWSFZ ALL.TXT not found: {owsfz_path}")

    return truth_path, wsjt_path, owsfz_path


def _load_truth(path: Path, scenario_filter: str | None) -> list[dict]:
    """Load truth.csv into a list of row-dicts, optionally filtering by scenario_id."""
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            sys.exit("ERROR: truth.csv is empty or has no header")
        missing = _TRUTH_COLUMNS_REQUIRED - set(reader.fieldnames)
        if missing:
            sys.exit(f"ERROR: truth.csv missing required columns: {', '.join(sorted(missing))}")
        rows = list(reader)

    if scenario_filter:
        rows = [r for r in rows if r["scenario_id"] == scenario_filter]

    # Parse cycle_utc to datetime for slot-key comparison
    for row in rows:
        try:
            row["_cycle_dt"] = datetime.strptime(
                row["cycle_utc"], "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=timezone.utc)
        except ValueError:
            row["_cycle_dt"] = None

    return rows


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def _build_slot_buckets(
    records: list[AllTxtRecord],
) -> dict[datetime, list[AllTxtRecord]]:
    """Group AllTxtRecord list by normalised UTC slot (the ``utc`` field is already normalised)."""
    buckets: dict[datetime, list[AllTxtRecord]] = defaultdict(list)
    for rec in records:
        buckets[rec.utc].append(rec)
    return buckets


def _text_matches(candidate_msg: str, truth_msg: str) -> bool:
    """Case-sensitive whitespace-normalised message equality."""
    return " ".join(candidate_msg.split()) == " ".join(truth_msg.split())


def _freq_matches(candidate_freq: float, true_freq: float) -> bool:
    return abs(candidate_freq - true_freq) <= FREQ_TOLERANCE_HZ


def _match_appraiser(
    truth_rows: list[dict],
    records: list[AllTxtRecord],
    appraiser: str,
    scenario_id: str,
) -> list[dict]:
    """Match truth rows against one appraiser's decode log.

    Returns a list of output row-dicts for this appraiser, including:
      - matched rows (matched=True)
      - miss rows (matched=False, false_positive=False)
      - false-positive rows (matched=False, false_positive=True)
    """
    buckets = _build_slot_buckets(records)
    # Track which candidate records have been consumed (prevent double-counting).
    # Key: (cycle_dt, bucket_index) so indices don't collide across different slots.
    consumed: set[tuple] = set()

    output_rows: list[dict] = []

    # Pass 1: match each truth row to candidates
    for truth in truth_rows:
        cycle_dt = truth.get("_cycle_dt")
        if cycle_dt is None:
            # Unparseable cycle timestamp — treat as miss
            output_rows.append(_miss_row(truth, appraiser, scenario_id))
            continue

        candidates = buckets.get(cycle_dt, [])
        match_found = False
        for idx, cand in enumerate(candidates):
            if (cycle_dt, idx) in consumed:
                continue
            # Try to match single truth message; S4 has multiple messages per part
            truth_msg = truth["message_text"]
            true_freq_str = truth["true_freq_hz"]
            # For S4/S5, freq and message matching behaves differently
            if not true_freq_str:
                if truth_msg == "":
                    # S5: signal-free slot — nothing is expected; no match possible
                    pass
                else:
                    # S4: truth_msg is a "; "-joined pool of individual messages.
                    # A candidate matches if its decoded text equals any one pool entry.
                    pool_msgs = [m.strip() for m in truth_msg.split(";")]
                    if any(_text_matches(cand.message, m) for m in pool_msgs):
                        consumed.add((cycle_dt, idx))
                        output_rows.append(_matched_row(truth, appraiser, scenario_id, cand))
                        match_found = True
                        break
            else:
                true_freq = float(true_freq_str)
                if _text_matches(cand.message, truth_msg) and _freq_matches(cand.freq_hz, true_freq):
                    consumed.add((cycle_dt, idx))
                    output_rows.append(_matched_row(truth, appraiser, scenario_id, cand))
                    match_found = True
                    break

        if not match_found:
            output_rows.append(_miss_row(truth, appraiser, scenario_id))

    # Pass 2: unconsumed candidates → false positives
    for cycle_dt, candidates in buckets.items():
        for idx, cand in enumerate(candidates):
            if (cycle_dt, idx) not in consumed:
                output_rows.append(_fp_row(cand, appraiser, scenario_id))

    return output_rows


def _matched_row(truth: dict, appraiser: str, scenario_id: str, cand: AllTxtRecord) -> dict:
    return {
        "scenario_id": scenario_id,
        "part_index": truth["part_index"],
        "trial_index": truth["trial_index"],
        "seed": truth["seed"],
        "appraiser": appraiser,
        "message_text": truth["message_text"],
        "true_snr_db": truth["true_snr_db"],
        "true_dt_s": truth["true_dt_s"],
        "true_freq_hz": truth["true_freq_hz"],
        "reported_snr_db": cand.snr_db,
        "reported_dt_s": cand.dt_s,
        "reported_freq_hz": cand.freq_hz,
        "matched": True,
        "false_positive": False,
        "cycle_utc": truth["cycle_utc"],
    }


def _miss_row(truth: dict, appraiser: str, scenario_id: str) -> dict:
    return {
        "scenario_id": scenario_id,
        "part_index": truth["part_index"],
        "trial_index": truth["trial_index"],
        "seed": truth["seed"],
        "appraiser": appraiser,
        "message_text": truth["message_text"],
        "true_snr_db": truth["true_snr_db"],
        "true_dt_s": truth["true_dt_s"],
        "true_freq_hz": truth["true_freq_hz"],
        "reported_snr_db": float("nan"),
        "reported_dt_s": float("nan"),
        "reported_freq_hz": float("nan"),
        "matched": False,
        "false_positive": False,
        "cycle_utc": truth["cycle_utc"],
    }


def _fp_row(cand: AllTxtRecord, appraiser: str, scenario_id: str) -> dict:
    return {
        "scenario_id": scenario_id,
        "part_index": "",
        "trial_index": "",
        "seed": "",
        "appraiser": appraiser,
        "message_text": cand.message,
        "true_snr_db": float("nan"),
        "true_dt_s": float("nan"),
        "true_freq_hz": float("nan"),
        "reported_snr_db": cand.snr_db,
        "reported_dt_s": cand.dt_s,
        "reported_freq_hz": cand.freq_hz,
        "matched": False,
        "false_positive": True,
        "cycle_utc": cand.utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


# ---------------------------------------------------------------------------
# CSV output
# ---------------------------------------------------------------------------

def _write_matched(run_dir: Path, scenario_id: str, rows: list[dict]) -> Path:
    out_path = run_dir / f"{scenario_id}_matched.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=MATCHED_COLUMNS)
        writer.writeheader()
        for row in rows:
            # Convert NaN to empty string for CSV readability
            clean = {k: ("" if isinstance(v, float) and v != v else v)
                     for k, v in row.items()}
            writer.writerow(clean)
    return out_path


# ---------------------------------------------------------------------------
# Summary printing
# ---------------------------------------------------------------------------

def _print_summary(appraiser: str, rows: list[dict], skipped: int) -> None:
    truth_rows = [r for r in rows if not r["false_positive"]]
    matched = sum(1 for r in truth_rows if r["matched"])
    misses = sum(1 for r in truth_rows if not r["matched"])
    fp = sum(1 for r in rows if r["false_positive"])
    total = matched + misses
    pct = 100.0 * matched / total if total > 0 else 0.0
    print(
        f"  {appraiser}: {matched}/{total} matched ({pct:.1f}%);  "
        f"{misses} miss{'es' if misses != 1 else ''};  {fp} FP"
        + (f"  (skipped {skipped} non-FT8/malformed lines)" if skipped else "")
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="R&R study decode matcher — join truth.csv with ALL.TXT logs"
    )
    parser.add_argument("--run-dir", help="Run directory (resolves default paths)")
    parser.add_argument("--scenario", help="Scenario ID to filter (e.g. S1)")
    parser.add_argument("--truth", help="Explicit path to truth.csv")
    parser.add_argument("--wsjt", help="Explicit path to WSJT-X ALL.TXT")
    parser.add_argument("--owsfz", help="Explicit path to OpenWSFZ ALL.TXT")
    args = parser.parse_args()

    if not args.run_dir and not (args.truth and args.wsjt and args.owsfz):
        parser.error("Provide --run-dir OR all of --truth, --wsjt, --owsfz")

    truth_path, wsjt_path, owsfz_path = _resolve_paths(args)

    # Load truth
    scenario_filter = args.scenario
    truth_rows = _load_truth(truth_path, scenario_filter)
    if not truth_rows:
        sys.exit(
            f"ERROR: no truth rows found"
            + (f" for scenario '{scenario_filter}'" if scenario_filter else "")
        )

    scenario_id = scenario_filter or truth_rows[0]["scenario_id"]
    print(f"Matching scenario {scenario_id} — {len(truth_rows)} truth rows")

    # Determine run directory for output
    run_dir = Path(args.run_dir) if args.run_dir else truth_path.parent

    # Parse ALL.TXT files
    wsjt_records, wsjt_skipped = parse_all_txt(wsjt_path)
    owsfz_records, owsfz_skipped = parse_all_txt(owsfz_path)
    print(f"  WSJT-X:    {len(wsjt_records)} FT8 lines parsed, {wsjt_skipped} skipped")
    print(f"  OpenWSFZ:  {len(owsfz_records)} FT8 lines parsed, {owsfz_skipped} skipped")

    # Match each appraiser
    all_rows: list[dict] = []
    wsjt_rows = _match_appraiser(truth_rows, wsjt_records, "WSJT-X", scenario_id)
    owsfz_rows = _match_appraiser(truth_rows, owsfz_records, "OpenWSFZ", scenario_id)
    all_rows = wsjt_rows + owsfz_rows

    # Write output
    out_path = _write_matched(run_dir, scenario_id, all_rows)
    print(f"  Written: {out_path}")

    # Summary
    print("\nMatch summary:")
    _print_summary("WSJT-X", wsjt_rows, wsjt_skipped)
    _print_summary("OpenWSFZ", owsfz_rows, owsfz_skipped)


if __name__ == "__main__":
    main()
