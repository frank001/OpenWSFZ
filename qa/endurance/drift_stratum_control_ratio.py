#!/usr/bin/env python3
"""Drift-stratified decode-ratio vs a zero-drift control -- Table C of the 2026-08-02-1721
grid-snapped ANOVA re-run spec.

Answers: "what does the drift defect actually cost, in decodes?" -- as a per-stratum ratio
against a same-instant, same-antenna, zero-drift CONTROL instance, not as a raw per-cycle
count. This is a cycle-level computation (decode_count per 15s cycle, from cycle-archive.csv),
not a decode-level matched-message comparison -- deliberately a separate script from
endurance_anova_wsjtx.py/endurance_anova_two_alltxt.py, which both operate on ALL.TXT rows.

WHY THE CONTROL MATTERS (per the spec's §3): drift strata correlate with hours-since-restart,
which correlates with time of day, which correlates with propagation. A drifted instance's
raw per-stratum decode count is confounded by all of that. Matching each of the drifted
instance's cycles against a same-instant zero-drift control's decode count for the identical
15s window removes the propagation confound, because both instances are listening to the
same physical antenna at the same instant -- only the drift-affected instance's capture
window is misaligned, not the actual signal that arrived.

Method (mechanical, per HK-021):
  1. Snap BOTH instances' cycle_start_utc timestamps to the enclosing 15s FT8 grid boundary
     (floor). This is needed even for a near-fully-on-grid control (e.g. 8081 at 99.8%) so a
     rare off-grid control cycle doesn't spuriously fail to match its drifted counterpart.
  2. Record the TARGET instance's ORIGINAL (pre-snap) offset (seconds mod 15) per cycle --
     this is the stratification factor.
  3. Match cycles by snapped timestamp between target and control.
  4. Aggregate decode_count as SUM over each stratum for target and control separately (ratio
     of sums, not mean of per-cycle ratios -- avoids small-denominator cycles dominating the
     average), then ratio = sum(target)/sum(control) per stratum.

Also reports the RAW (unmatched, propagation-confounded) per-stratum decode-count comparison
alongside, explicitly labelled as the wrong number to use for the actual cost -- per the
spec's own note that raw counts and control-matched counts disagree in both magnitude and
(for one stratum) direction.

NFR-021: only decode_count integers and timestamps are read from cycle-archive.csv -- no
message text exists in that file at all, so there is nothing to leak.

Usage:
    python drift_stratum_control_ratio.py \\
        --target-cycle-archive artefacts/20260731_live_run_2004-8080/owsfz/cycle-archive.csv \\
        --target-label 8080 \\
        --control-cycle-archive artefacts/20260731_live_run_2004-8081/owsfz/cycle-archive.csv \\
        --control-label 8081 \\
        --out qa/endurance/2026-08-02-multiday-20m-anova/table_c_drift_stratified_decode_ratio.md
"""
from __future__ import annotations

import argparse
import csv
import datetime
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

FT8_CYCLE_SECONDS = 15
_ISO_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"


def parse_iso(ts: str) -> datetime.datetime:
    return datetime.datetime.strptime(ts, _ISO_FMT)


def offset_seconds(dt: datetime.datetime) -> int:
    total = dt.hour * 3600 + dt.minute * 60 + dt.second
    return total % FT8_CYCLE_SECONDS


def snap_to_grid(dt: datetime.datetime) -> datetime.datetime:
    """Floor to the enclosing 15s boundary -- floor, not round, matching anova_common.py's
    snap_ts_to_grid() rationale (the drift is one-directional/late)."""
    total = dt.hour * 3600 + dt.minute * 60 + dt.second
    snapped_total = total - (total % FT8_CYCLE_SECONDS)
    return dt.replace(hour=0, minute=0, second=0, microsecond=0) + \
        datetime.timedelta(seconds=snapped_total)


def load_cycle_archive(path: str) -> list[dict]:
    rows = []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            dt = parse_iso(row["cycle_start_utc"])
            rows.append({
                "orig_dt": dt,
                "offset": offset_seconds(dt),
                "snapped_dt": snap_to_grid(dt),
                "decode_count": int(row["decode_count"]),
            })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target-cycle-archive", required=True,
                     help="cycle-archive.csv for the drift-affected instance.")
    ap.add_argument("--target-label", required=True)
    ap.add_argument("--control-cycle-archive", required=True,
                     help="cycle-archive.csv for the zero-drift control instance.")
    ap.add_argument("--control-label", required=True)
    ap.add_argument("--out", required=True, help="Output path for the Table C markdown.")
    ap.add_argument("--run-label", default=None)
    args = ap.parse_args()

    target_rows = load_cycle_archive(args.target_cycle_archive)
    control_rows = load_cycle_archive(args.control_cycle_archive)
    print(f"{args.target_label}: {len(target_rows)} cycles")
    print(f"{args.control_label}: {len(control_rows)} cycles")

    # Collision check: snapping must not merge two distinct target cycles onto one snapped
    # timestamp -- if it does, the drift exceeded half a cycle somewhere and this method's
    # assumptions need revisiting rather than silently picking one and discarding the other.
    target_by_snap: dict[datetime.datetime, list[dict]] = {}
    for r in target_rows:
        target_by_snap.setdefault(r["snapped_dt"], []).append(r)
    collisions = {k: v for k, v in target_by_snap.items() if len(v) > 1}
    if collisions:
        print(f"[WARN] {len(collisions)} snapped timestamp(s) in {args.target_label} have "
              f">1 original cycle mapped to them -- drift may exceed half a cycle somewhere; "
              f"first colliding snap: {sorted(collisions)[0]}", file=sys.stderr)

    control_by_snap: dict[datetime.datetime, int] = {}
    control_collisions = 0
    for r in control_rows:
        if r["snapped_dt"] in control_by_snap:
            control_collisions += 1
        control_by_snap[r["snapped_dt"]] = r["decode_count"]
    if control_collisions:
        print(f"[WARN] {control_collisions} collision(s) in {args.control_label}'s own "
              f"snapped timestamps", file=sys.stderr)

    # Control-matched aggregation: sum decode_count per stratum, over cycles present in BOTH.
    strata: dict[int, dict] = {}
    matched_cycles = 0
    for snap, target_list in target_by_snap.items():
        if snap not in control_by_snap:
            continue
        r = target_list[0]  # first if a collision occurred (warned above)
        s = strata.setdefault(r["offset"], {
            "n_matched": 0, "target_sum": 0, "control_sum": 0,
            "target_raw_sum": 0, "target_raw_n": 0,
        })
        s["n_matched"] += 1
        s["target_sum"] += r["decode_count"]
        s["control_sum"] += control_by_snap[snap]
        matched_cycles += 1
    print(f"matched cycles (target present in control): {matched_cycles}")

    # Raw (unmatched, propagation-confounded) per-stratum mean -- ALL target cycles in that
    # stratum, whether or not the control has a matching cycle. Reported explicitly as the
    # number NOT to use for "what does drift cost", per the spec's §3.
    for r in target_rows:
        s = strata.setdefault(r["offset"], {
            "n_matched": 0, "target_sum": 0, "control_sum": 0,
            "target_raw_sum": 0, "target_raw_n": 0,
        })
        s["target_raw_sum"] += r["decode_count"]
        s["target_raw_n"] += 1

    run_label = args.run_label or (
        f"{args.target_label} (drift-affected) vs {args.control_label} (zero-drift control)"
    )
    generated = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    L = []
    L.append("# Table C -- drift-stratified decode-ratio vs zero-drift control")
    L.append("")
    L.append(f"**Run:** {run_label}  ")
    L.append(f"**Generated:** {generated} (`date -u`, HK-017)  ")
    L.append(f"**Method:** cycle-level, not decode-level -- {args.target_label}'s "
              f"decode_count per 15s cycle, grid-snapped and stratified by its own ORIGINAL "
              f"(pre-snap) offset, matched against {args.control_label}'s decode_count for "
              f"the identical snapped cycle (same antenna, same instant -- propagation is "
              f"common-mode by construction, per the Captain's splitter fact). Ratio is "
              f"SUM(target decode_count)/SUM(control decode_count) per stratum, not a mean "
              f"of per-cycle ratios, to avoid small-denominator cycles dominating.")
    L.append("")
    if collisions or control_collisions:
        L.append(f"**Collision warning:** {len(collisions)} {args.target_label} / "
                  f"{control_collisions} {args.control_label} snapped-timestamp collision(s) "
                  f"detected -- see stderr for detail if this run was not captured in a log.")
        L.append("")

    L.append("## Control-matched ratio (the number that isolates drift's cost)")
    L.append("")
    L.append(f"| {args.target_label} drift stratum | matched cycles | "
              f"{args.target_label} decodes (matched cycles) | "
              f"{args.control_label} decodes (matched cycles) | ratio | vs +0s |")
    L.append("|---|---:|---:|---:|---:|---:|")
    baseline_ratio = None
    for s in sorted(strata):
        d = strata[s]
        if d["n_matched"] == 0:
            continue
        ratio = d["target_sum"] / d["control_sum"] if d["control_sum"] else float("nan")
        if baseline_ratio is None:
            baseline_ratio = ratio
            vs = "--"
        else:
            vs = f"{100.0 * (ratio - baseline_ratio) / baseline_ratio:+.1f}%"
        L.append(f"| +{s}s | {d['n_matched']} | {d['target_sum']} | {d['control_sum']} | "
                  f"{ratio:.3f} | {vs} |")
    L.append("")

    L.append("## Raw per-stratum mean decode count (propagation-confounded -- do NOT use "
              "this for \"what does drift cost\")")
    L.append("")
    L.append(f"| {args.target_label} drift stratum | cycles | mean decodes/cycle | vs +0s |")
    L.append("|---|---:|---:|---:|")
    baseline_raw = None
    for s in sorted(strata):
        d = strata[s]
        if d["target_raw_n"] == 0:
            continue
        mean = d["target_raw_sum"] / d["target_raw_n"]
        if baseline_raw is None:
            baseline_raw = mean
            vs = "--"
        else:
            vs = f"{100.0 * (mean - baseline_raw) / baseline_raw:+.1f}%"
        L.append(f"| +{s}s | {d['target_raw_n']} | {mean:.2f} | {vs} |")
    L.append("")
    L.append("**Why these two tables disagree:** drift strata correlate with hours-since-"
              "restart, which correlates with time of day, which correlates with "
              "propagation. The raw table above inherits that confound; the control-matched "
              "table does not, because both instances hear the same antenna at the same "
              "instant regardless of which stratum the target's clock happens to be in.")
    L.append("")

    report = "\n".join(L) + "\n"
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(report)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
