#!/usr/bin/env python3
"""N1 -- population assembly: the candidate-present-and-failed rows (spec Sec.4).

Reuses c2_phase2c_ber_measurement.py's own population/matching functions UNCHANGED
(imported, not re-derived) -- that module is the recovered, reproduced N1 Sec.3.1
precondition instrument and already implements exactly the "candidate-present-and-
failed" selection this spec names: THE 135 (K10/cap140, score>=10) and THE 567
(K4/cap2000, score 5-9), both defined as "WSJT-X reported a message we did not decode,
AND a candidate of ours sits near its (freq, dt) that also did not decode." Re-deriving
this logic here would risk the two implementations drifting (the same risk design.md's
Risks section flags for the inverse-mapping arithmetic) -- importing is the safer path.

ROW 0c ("fewer than 200 paired rows survive") is why both populations are combined:
THE 135 alone measured only 126 of 135 in the precondition report; THE 135 + THE 567
combined comfortably clears 200 from the SAME July corpus (20260725_live_run_1806),
without any new capture (barred, spec Sec.9).

Each output row carries the GRID anchor as the CSV's own recorded (freq_hz, dt) for
that candidate -- i.e. the exact lattice position production's own candidate search
already sits on, not WSJT-X's reported values (the M1/M2 time-base confound this spec
exists specifically to avoid, Sec.1). run_n1.py rounds freq_hz to the nearest int
before calling the refiner (matching FT8Result.freq_hz's own int type, and r1/r1b's own
refiner_ctypes.Refiner.refine(..., coarse_freq_hz: int, ...) convention) -- see run_n1.py's
own comment for why GRID and REFINED must share that exact rounded anchor.
"""
from __future__ import annotations

import os
import sys

_C2_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                        "cycleframer-alignment-replay")
sys.path.insert(0, os.path.abspath(_C2_DIR))
import c2_phase2c_ber_measurement as C2  # noqa: E402

REPO_ROOT = C2.REPO_ROOT
WAV68_DIR = C2.WAV68_DIR
K10_DIAG_CSV = os.path.join(C2.K10_CAP_DIR, "candidate_diag.csv")
K4_DIAG_CSV = os.path.join(C2.K4_CAP_DIR, "candidate_diag.csv")


def _attach_grid_anchor(wsjtx_rows: list[dict], cand_by_cycle: dict[str, list[dict]],
                         pop_label: str) -> list[dict]:
    """For each WSJT-X row (candidate-present-and-failed, per compute_135/567_population),
    find the SAME failed candidate those functions matched against (require_decoded=False,
    identical nearest_candidate tolerance) and attach its own grid freq_hz/dt.

    A row whose candidate cannot be re-matched (should not happen -- compute_*_population
    already proved a nearby failed candidate exists -- but re-derived independently here
    rather than assumed, HK-018) is dropped and counted, not silently skipped."""
    out = []
    n_no_grid_match = 0
    for row in wsjtx_rows:
        cands = [c for c in cand_by_cycle.get(row["ts"], []) if not c["decoded"]]
        cand = C2.nearest_candidate(row["freq"], row["dt"], cands)
        if cand is None:
            n_no_grid_match += 1
            continue
        out.append({
            "ts": row["ts"],
            "message": row["message"],
            "grid_freq_hz": cand["freq_hz"],
            "grid_dt": cand["dt"],
            "population": pop_label,
            # Additive field, N2 Sec.7.3 (tight-match stratification): WSJT-X's own
            # reported freq for this row, kept separate from grid_freq_hz (our
            # candidate's own lattice position) precisely so |diff| can be computed.
            # N1 never reads this key -- byte-for-byte backward compatible.
            "wsjtx_freq_hz": row["freq"],
        })
    if n_no_grid_match:
        print("  [%s] WARNING: %d/%d row(s) could not be re-matched to a grid candidate "
              "(dropped)" % (pop_label, n_no_grid_match, len(wsjtx_rows)))
    return out


def build_paired_population() -> list[dict]:
    """Returns the combined THE-135 + THE-567 candidate-present-and-failed population,
    each row: {ts, message, grid_freq_hz, grid_dt, population}."""
    cycles = sorted(os.path.splitext(f)[0] for f in os.listdir(WAV68_DIR) if f.endswith(".wav"))

    k10_cand_by_cycle = C2.load_candidate_diag_simple(K10_DIAG_CSV)
    pop135_wsjtx = C2.compute_135_population(cycles)
    pop135 = _attach_grid_anchor(pop135_wsjtx, k10_cand_by_cycle, "135")
    print("THE 135: n_wsjtx=%d n_grid_matched=%d" % (len(pop135_wsjtx), len(pop135)))

    k4_cand_by_cycle = C2.load_candidate_diag_simple(K4_DIAG_CSV)
    population_648 = C2.compute_648_population(cycles)
    pop567_wsjtx = C2.compute_567_population(population_648)
    pop567 = _attach_grid_anchor(pop567_wsjtx, k4_cand_by_cycle, "567")
    print("THE 567: n_wsjtx=%d n_grid_matched=%d" % (len(pop567_wsjtx), len(pop567)))

    combined = pop135 + pop567
    print("Combined candidate-present-and-failed population: n=%d" % len(combined))
    return combined


def build_matched_hit_control(limit: int = 200) -> list[dict]:
    """ROW 0b's control population: messages we DID decode (K10/cap140), same shape as
    build_paired_population()'s rows so run_n1.py can extract at the SAME grid anchor for
    both -- but here grid_freq_hz/grid_dt come from OUR OWN ALL.TXT-derived candidate
    match (require_decoded=True), matching c2_phase2c_ber_measurement's own control-
    population discipline (its own docstring: using WSJT-X's freq/dt to pick "the nearest
    decoded candidate" can pick the WRONG one in a busy cycle)."""
    cycles = sorted(os.path.splitext(f)[0] for f in os.listdir(WAV68_DIR) if f.endswith(".wav"))
    control_wsjtx = C2.compute_matched_hit_control(cycles, limit=limit)
    decoded_by_cycle = {ts: [c for c in cs if c["decoded"]] for ts, cs in
                         C2.load_candidate_diag_simple(K10_DIAG_CSV).items()}
    out = []
    n_no_grid_match = 0
    for row in control_wsjtx:
        cand = C2.nearest_candidate(row["freq"], row["dt"], decoded_by_cycle.get(row["ts"], []))
        if cand is None:
            n_no_grid_match += 1
            continue
        out.append({"ts": row["ts"], "message": row["message"],
                     "grid_freq_hz": cand["freq_hz"], "grid_dt": cand["dt"],
                     "population": "control"})
    if n_no_grid_match:
        print("  [control] WARNING: %d/%d row(s) could not be re-matched (dropped)"
              % (n_no_grid_match, len(control_wsjtx)))
    print("MATCHED-HIT CONTROL: n_wsjtx=%d n_grid_matched=%d" % (len(control_wsjtx), len(out)))
    return out


if __name__ == "__main__":
    rows = build_paired_population()
    ctrl = build_matched_hit_control()
    print("\nBy population label:")
    from collections import Counter
    print(dict(Counter(r["population"] for r in rows)))
    print("Control: %d" % len(ctrl))
