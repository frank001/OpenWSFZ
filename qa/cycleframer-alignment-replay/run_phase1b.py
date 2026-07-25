#!/usr/bin/env python3
"""Phase 1b -- confirm-and-cut (SPEC.md section 5.2 second amendment / section 9 / tasks.md
11.5-11.7).

Single consolidated driver, run once (this is a ~60-70 min job): decodes the FULL arm-A
baseline (all ~2,827 cycles at delta=0, needed for both the session-wide DT_med and the
per-cycle |ref(k)| counts), stratified-selects 400 qualifying cycles across the session,
decodes those 400 cycles at each of the 11 non-anchor offsets, scores paired recall with
the section 7.4(b-i)/(b-ii) guards, and runs the section 5.2 falsification criterion
against the model -- printing the verdict, per the SPEC's own "state the verdict before
looking" requirement, only after all the numbers are in, never partway.

Deltas (SPEC.md section 5.2 second amendment, 11 non-anchor points):
  positive cliff: +2.00, +2.25, +2.50, +2.75, +3.00
  negative cliff: -2.00, -2.25, -2.50, -2.75
  plateau:        -1.00
  shoulder:       +3.50

HK-009: reconfigure stdout to UTF-8. NFR-021: everything under --work-dir must be
git-ignored (see .gitignore -- _work/ already is).
"""
from __future__ import annotations

import argparse
import csv
import json
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
from falsification_check import predict_recall, dt_median, crossing, LOW, HIGH, \
    OUTSIDE_TOL, INSIDE_TOL, CROSSING_TOL, TRANSITION_LO, TRANSITION_HI  # noqa: E402

DELTAS_1B = [2.00, 2.25, 2.50, 2.75, 3.00, -2.00, -2.25, -2.50, -2.75, -1.00, 3.50]
MIN_REF_DEFAULT = 5
N_STRATIFIED_DEFAULT = 400


def run_harness(harness: str, wav_dir: Path, out_dir: Path, manifest: Path, point: str) -> Path:
    cmd = [harness, "--wav-dir", str(wav_dir), "--out-dir", str(out_dir),
           "--all-txt-name", "ALL.TXT", "--manifest", str(manifest), "--points", point]
    print(f"  decoding {wav_dir.name} -> {out_dir.name} ...", flush=True)
    subprocess.run(cmd, check=True)
    return out_dir / point / "ALL.TXT"


def read_reject_count(out_dir: Path, point: str) -> int | None:
    p = out_dir / point / "hash_reject_count.txt"
    if not p.exists():
        return None
    line = p.read_text().strip()
    return int(line.split("=")[1])


def step_baseline(args: argparse.Namespace) -> None:
    wav_dir = Path(args.wav_dir)
    work = Path(args.work_dir)
    out_dir = work / "baseline"
    dec_dir = work / "baseline_decoded"
    seg_idx = [int(x) for x in args.segment_index.split(",")] if getattr(args, "segment_index", None) else None
    print(f"=== Phase 1b step 1: arm-A baseline (segments={seg_idx or 'ALL'}, delta=0) ===")
    manifest, prov = rw.do_rewindow(wav_dir, out_dir, 0.0, seg_idx, None, None, clean=True)
    print(f"rewindowed {prov['n_windows']} windows across segments {prov['segment_indices']}")
    all_txt = run_harness(args.harness, out_dir, dec_dir, manifest, args.point)
    rc = read_reject_count(dec_dir, args.point)
    print(f"baseline decode done. hashTableRejectCount={rc}")
    print(f"-> {manifest}\n-> {all_txt}")


def step_select(args: argparse.Namespace) -> None:
    work = Path(args.work_dir)
    manifest = work / "baseline" / "manifest.csv"
    all_txt = work / "baseline_decoded" / args.point / "ALL.TXT"
    min_ref = getattr(args, "min_ref", MIN_REF_DEFAULT) or MIN_REF_DEFAULT
    n_stratified = getattr(args, "n_stratified", N_STRATIFIED_DEFAULT) or N_STRATIFIED_DEFAULT
    print(f"=== Phase 1b step 2: stratified selection (min_ref={min_ref}, n_stratified={n_stratified}) ===")

    rows = parse_all_txt(all_txt)
    ts_to_cycle = load_manifest(manifest)
    sets, merges = build_cycle_sets(rows, ts_to_cycle, normalize_hash=True)
    check_no_collisions(merges, "baseline (full session)")

    # ts_to_cycle: ts_field -> (segment, k). Need segment,k -> (n_ref, cycle_utc-order).
    # Recover cycle_utc per (segment,k) from the manifest directly for chronological sort.
    cycle_utc_by_id: dict[tuple[int, int], str] = {}
    with open(manifest, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            cid = (int(row["segment_index"]), int(row["k"]))
            cycle_utc_by_id[cid] = row["cycle_utc"]

    qualifying = [(cid, len(sets.get(cid, set()))) for cid in cycle_utc_by_id if len(sets.get(cid, set())) >= min_ref]
    qualifying.sort(key=lambda x: cycle_utc_by_id[x[0]])  # chronological
    n_qual = len(qualifying)
    print(f"{len(cycle_utc_by_id)} total cycles, {n_qual} qualifying (|ref(k)|>={min_ref})")

    if n_qual <= n_stratified:
        selected = [cid for cid, _n in qualifying]
    else:
        step = n_qual / n_stratified
        idxs = sorted(set(int(i * step) for i in range(n_stratified)))
        selected = [qualifying[i][0] for i in idxs]
    print(f"selected {len(selected)} cycles, evenly spaced across the qualifying chronological list")

    by_segment: dict[int, list[int]] = {}
    for seg, k in selected:
        by_segment.setdefault(seg, []).append(k)

    sel_path = work / "selection.json"
    sel_path.write_text(json.dumps({
        "n_total_cycles": len(cycle_utc_by_id), "n_qualifying": n_qual,
        "n_selected": len(selected), "min_ref": min_ref,
        "by_segment": {str(s): sorted(ks) for s, ks in by_segment.items()},
    }, indent=2))

    dt_pop = [float(r["dt"]) for r in rows if r["dt"]]
    dmed = dt_median(dt_pop)
    dt_path = work / "baseline_dt_population.json"
    dt_path.write_text(json.dumps({"n": len(dt_pop), "median": dmed, "values": dt_pop}))
    print(f"session-wide DT: n={len(dt_pop)} median={dmed:.4f}")
    print(f"-> {sel_path}\n-> {dt_path}")


def step_sweep(args: argparse.Namespace) -> None:
    wav_dir = Path(args.wav_dir)
    work = Path(args.work_dir)
    min_ref = getattr(args, "min_ref", MIN_REF_DEFAULT) or MIN_REF_DEFAULT
    deltas = DELTAS_1B if not getattr(args, "deltas", None) else [float(x) for x in args.deltas.split(",")]
    print(f"=== Phase 1b step 3: sweep on the selected cycles (deltas={deltas}) ===")

    sel = json.loads((work / "selection.json").read_text())
    cycle_selection = {int(s): set(ks) for s, ks in sel["by_segment"].items()}
    selected_ids = {(int(s), k) for s, ks in sel["by_segment"].items() for k in ks}
    print(f"{len(selected_ids)} cycles across {len(cycle_selection)} segments")

    ref_manifest = work / "baseline" / "manifest.csv"
    ref_all_txt = work / "baseline_decoded" / args.point / "ALL.TXT"
    ref_rows = parse_all_txt(ref_all_txt)
    ref_map = load_manifest(ref_manifest)
    ref_sets_full, ref_merges = build_cycle_sets(ref_rows, ref_map, normalize_hash=True)
    check_no_collisions(ref_merges, "reference arm (full baseline, re-checked for sweep)")
    ref_sets = {cid: s for cid, s in ref_sets_full.items() if cid in selected_ids}

    rows_out = []
    reject_counts = {}
    for delta in deltas:
        out_dir = work / f"sweep_d{str(delta).replace('.', 'p').replace('-', 'n')}"
        dec_dir = work / f"sweep_d{str(delta).replace('.', 'p').replace('-', 'n')}_decoded"
        manifest, prov = rw.do_rewindow(wav_dir, out_dir, delta, None, None, None,
                                         clean=True, cycle_selection=cycle_selection)
        all_txt = run_harness(args.harness, out_dir, dec_dir, manifest, args.point)
        rc = read_reject_count(dec_dir, args.point)
        reject_counts[delta] = rc

        test_rows = parse_all_txt(all_txt)
        test_map = load_manifest(manifest)
        test_sets, test_merges = build_cycle_sets(test_rows, test_map, normalize_hash=True)
        check_no_collisions(test_merges, f"test arm delta={delta}")

        is_identity = check_provenance(ref_manifest, manifest, shift=0)
        results, excluded = paired_recall(test_sets, ref_sets, shift=0, min_ref=min_ref)
        summary = summarize(results)
        print(f"delta={delta:+.3f}: n_cycles={summary['n_cycles']} excluded={excluded} "
              f"median={summary['median']} p10={sorted(r['recall'] for r in results)[max(0, len(results)//10 - 1)] if results else None} "
              f"zero_recall_n={sum(1 for r in results if r['recall'] == 0.0)} "
              f"hashTableRejectCount={rc}")
        rows_out.append({
            "delta": delta, "n_cycles": summary["n_cycles"], "excluded_low_ref": excluded,
            "median": summary["median"], "q1": summary["q1"], "q3": summary["q3"],
            "mean": summary["mean"], "min": summary["min"], "max": summary["max"],
            "zero_recall_n": sum(1 for r in results if r["recall"] == 0.0),
            "hashTableRejectCount": rc,
        })

        # p10 (SPEC.md section 5.3 amendment)
        if results:
            rs = sorted(r["recall"] for r in results)
            p10_idx = max(0, int(0.10 * len(rs)) - 1)
            rows_out[-1]["p10"] = rs[p10_idx]
        else:
            rows_out[-1]["p10"] = None

    baseline_rc = read_reject_count(work / "baseline_decoded", args.point)
    print(f"\nbaseline hashTableRejectCount={baseline_rc}, sweep arms={reject_counts}")

    out = work / "phase1b_summary.csv"
    with open(out, "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(rows_out[0].keys()))
        wr.writeheader()
        wr.writerows(rows_out)
    print(f"-> {out}")


def step_falsify(args: argparse.Namespace) -> None:
    work = Path(args.work_dir)
    print("=== Phase 1b step 4: falsification criterion (session-wide DT_med) ===")
    dt_data = json.loads((work / "baseline_dt_population.json").read_text())
    dt_pop = dt_data["values"]
    dmed = dt_data["median"]
    print(f"session-wide DT: n={len(dt_pop)} median={dmed:.4f} (vs segment-0-only +0.80 used in Phase 0/1a)")

    measured = []
    with open(work / "phase1b_summary.csv", newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            measured.append((float(row["delta"]), float(row["median"])))
    measured.sort()

    print(f"\n{'delta':>8} {'measured':>10} {'predicted':>10} {'resid':>8} {'zone':>10} {'tol':>6} {'ok':>4}")
    all_ok = True
    resid_sq = []
    for d, meas in measured:
        pred = predict_recall(d, dt_pop)
        resid = meas - pred
        resid_sq.append(resid * resid)
        inside = TRANSITION_LO < pred < TRANSITION_HI
        tol = INSIDE_TOL if inside else OUTSIDE_TOL
        ok = abs(resid) <= tol
        all_ok = all_ok and ok
        print(f"{d:8.3f} {meas:10.4f} {pred:10.4f} {resid:+8.4f} "
              f"{'inside' if inside else 'outside':>10} {tol:6.2f} {'OK' if ok else 'FAIL':>4}")
    rms = (sum(resid_sq) / len(resid_sq)) ** 0.5 if resid_sq else float("nan")
    print(f"\nRMS error: {rms:.4f}")

    peak_delta = max(measured, key=lambda p: p[1])[0]
    neg_side = [(d, r) for d, r in measured if d <= peak_delta]
    pos_side = [(d, r) for d, r in measured if d >= peak_delta]
    neg_crossing = crossing(neg_side)
    pos_crossing = crossing(pos_side)
    pred_pos_centre = dmed + LOW
    pred_neg_centre = dmed - HIGH

    crit2_ok = pos_crossing is not None and abs(pos_crossing - pred_pos_centre) <= CROSSING_TOL
    crit3_ok = neg_crossing is not None and abs(neg_crossing - pred_neg_centre) <= CROSSING_TOL
    print(f"\nPositive 50% crossing: measured={pos_crossing}  predicted={pred_pos_centre:.3f}  "
          f"tol=+/-{CROSSING_TOL}  {'PASS' if crit2_ok else 'FAIL'}")
    print(f"Negative 50% crossing: measured={neg_crossing}  predicted={pred_neg_centre:.3f}  "
          f"tol=+/-{CROSSING_TOL}  {'PASS' if crit3_ok else 'FAIL'}")
    print(f"Criterion 1 (per-point tolerance): {'PASS' if all_ok else 'FAIL'}")

    verdict = all_ok and crit2_ok and crit3_ok
    print(f"\n{'='*70}")
    print(f"PHASE 1B FALSIFICATION VERDICT: {'MODEL SURVIVES' if verdict else 'MODEL FALSIFIED -- fall back to the full 27-point grid before quoting deliverables #2/#5'}")
    print(f"{'='*70}")

    (work / "phase1b_verdict.json").write_text(json.dumps({
        "verdict": "MODEL SURVIVES" if verdict else "MODEL FALSIFIED",
        "criterion1_ok": all_ok, "criterion2_ok": crit2_ok, "criterion3_ok": crit3_ok,
        "rms": rms, "dt_med_session_wide": dmed, "n_dt_population": len(dt_pop),
        "pos_crossing_measured": pos_crossing, "pos_crossing_predicted": pred_pos_centre,
        "neg_crossing_measured": neg_crossing, "neg_crossing_predicted": pred_neg_centre,
    }, indent=2))


def step_all(args: argparse.Namespace) -> None:
    for fn in (step_baseline, step_select, step_sweep, step_falsify):
        fn(args)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    for name, fn in [("baseline", step_baseline), ("select", step_select),
                      ("sweep", step_sweep), ("falsify", step_falsify), ("all", step_all)]:
        sp = sub.add_parser(name)
        sp.add_argument("--wav-dir", default=None)
        sp.add_argument("--work-dir", required=True)
        sp.add_argument("--harness", default=None)
        sp.add_argument("--point", default="k10_c0.10_n60")
        sp.add_argument("--segment-index", default=None,
                         help="[baseline/all only, TESTING] comma-separated segment indices; "
                              "default (omit) = ALL segments, required for a real Phase 1b run")
        sp.add_argument("--min-ref", type=int, default=MIN_REF_DEFAULT)
        sp.add_argument("--n-stratified", type=int, default=N_STRATIFIED_DEFAULT)
        sp.add_argument("--deltas", default=None,
                         help="[sweep/all, TESTING] override the 11-point SPEC.md section 5.2 grid "
                              "with a comma-separated list; default (omit) = the real grid")
        sp.set_defaults(fn=fn)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
