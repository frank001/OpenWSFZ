#!/usr/bin/env python3
"""C-ASYM-A Part C -- does the D-001 metric manufacture a gap where an oracle says there
is none? Computed on the S8HN high-N synthetic run (Sec.4.3/Gate C of the spec).

Reads <run_dir>/S8HN_matched.csv, produced by harness/matcher.py against
scenarios/s8hn-band-scene-highn.json's truth.csv (12 stations x 25 trials = 300 injected
messages per appraiser). No privacy concern -- synthetic callsigns (Q-prefix, NFR-021-
compliant), no live ALL.TXT involved.

recovery_ours   = injected messages recovered by OpenWSFZ / injected
recovery_theirs = injected messages recovered by WSJT-X   / injected
M_syn           = of the injected messages WSJT-X recovered, fraction OpenWSFZ did not
                  (the D-001 statistic, computed where truth is known)

Station F (1162 Hz, near-collision with E) is reported separately and the gate is
evaluated on the F-EXCLUDED M_syn per spec Sec.4.3/Gate C footnote.

Cluster bootstrap over trial_index (the unit sharing one rendered slot -- HK-021(i)),
2000 draws, seed 20260823 (same seed as the rest of this arm).
"""
from __future__ import annotations

import csv
import glob
import io
import json
import os
import random
import sys
import time
from collections import defaultdict

import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="ascii", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
RR_STUDY = os.path.dirname(HERE)

SEED = 20260823
N_BOOT = 2000
GATE_C_BAR = 0.10
STATION_F_FREQ_HZ = 1162.0


def find_matched_csv():
    candidates = sorted(glob.glob(os.path.join(RR_STUDY, "results", "*", "S8HN_matched.csv")))
    if not candidates:
        sys.exit("ERROR: no S8HN_matched.csv found under qa/rr-study/results/*/")
    return candidates[-1]


def load_rows(path):
    with io.open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def build_per_signal(rows):
    """{(trial_index, message_text, true_freq_hz): {appraiser: matched_bool}}.

    matcher.py's matched.csv also carries pure false-positive rows (a candidate decode
    that matched no truth signal) -- these have NO trial_index/true_* fields (blank) and
    are not part of the truth-row population Gate C is defined over. They are counted
    separately in count_false_positives() below, not folded into recovery/M_syn."""
    per_signal = defaultdict(dict)
    for r in rows:
        if r["trial_index"] == "":
            continue  # pure FP row, not a truth-signal outcome
        key = (int(r["trial_index"]), r["message_text"], float(r["true_freq_hz"]))
        per_signal[key][r["appraiser"]] = (r["matched"] == "True")
    return per_signal


def count_false_positives(rows, valid_cycle_utcs):
    """Pure FP rows per appraiser (candidate decodes matching no injected truth signal),
    RESTRICTED to cycle_utc values that are actually one of this run's trial cycles.

    matcher.py's Pass 2 (unconsumed-candidate -> FP) iterates every slot bucket present in
    the WHOLE parsed ALL.TXT file, not just the cycles this scenario actually played --
    if ALL.TXT was not cleared since a previous session (it was not, here: the OpenWSFZ
    copy for this run spans 260822_2033.. through 260823_1047..), every leftover decode
    from that prior session gets counted as an S8HN false positive. This is the exact
    "uncleared ALL.TXT contaminates every matched.csv" failure mode already on record for
    this project (2026-08-15, 203,920 contaminated rows) -- caught here by cross-checking
    the parsed ALL.TXT date range against truth.csv's cycle_utc column before trusting the
    FP tally, and fixed by restricting to the known-good cycle set rather than by editing
    matcher.py's own (separately, historically-accepted) behaviour."""
    counts = defaultdict(int)
    total = defaultdict(int)
    excluded_stale = defaultdict(int)
    for r in rows:
        total[r["appraiser"]] += 1
        if r["trial_index"] == "" and r["false_positive"] == "True":
            if r["cycle_utc"] in valid_cycle_utcs:
                counts[r["appraiser"]] += 1
            else:
                excluded_stale[r["appraiser"]] += 1
    return dict(counts), dict(total), dict(excluded_stale)


def percentile(sorted_vals, p):
    n = len(sorted_vals)
    if n == 0:
        return float("nan")
    idx = max(0, min(n - 1, int(round(p * (n - 1)))))
    return sorted_vals[idx]


def boot_ci(values):
    vals = sorted(v for v in values if not (isinstance(v, float) and np.isnan(v)))
    lo = percentile(vals, 0.025)
    hi = percentile(vals, 0.975)
    hw = (hi - lo) / 2.0 if vals else float("nan")
    return lo, hi, hw, len(vals)


def main():
    path = find_matched_csv()
    rows = load_rows(path)
    print("matched csv: %s (%d rows)" % (path, len(rows)))

    per_signal = build_per_signal(rows)
    n_signals = len(per_signal)
    print("distinct injected signals (trial x station): %d" % n_signals)

    # The set of cycle_utc values that are genuinely one of THIS run's trials (truth-
    # derived rows only, i.e. trial_index != "") -- see count_false_positives() docstring.
    valid_cycle_utcs = set(r["cycle_utc"] for r in rows if r["trial_index"] != "")
    print("distinct trial cycle_utc values (expect 25): %d" % len(valid_cycle_utcs))

    fp_counts, candidate_totals, fp_excluded_stale = count_false_positives(rows, valid_cycle_utcs)
    print("false-positive candidates within this run's cycles: %s" % fp_counts)
    print("false-positive-shaped rows EXCLUDED as stale/uncleared-ALL.TXT contamination "
          "(outside this run's 25 cycles): %s" % fp_excluded_stale)
    print("total candidate rows per appraiser (matched+miss+FP, all cycles in the file): %s"
          % candidate_totals)

    trials = sorted(set(k[0] for k in per_signal))
    n_trials = len(trials)
    trial_index_map = {t: i for i, t in enumerate(trials)}
    print("trials: %d" % n_trials)

    keys = sorted(per_signal.keys())
    is_f = np.array([1.0 if k[2] == STATION_F_FREQ_HZ else 0.0 for k in keys])
    ours_matched = np.array([1.0 if per_signal[k].get("OpenWSFZ") else 0.0 for k in keys])
    theirs_matched = np.array([1.0 if per_signal[k].get("WSJT-X") else 0.0 for k in keys])
    trial_idx = np.array([trial_index_map[k[0]] for k in keys], dtype=np.int64)

    def stats(mult):
        w = mult[trial_idx]
        n_inj = w.sum()
        recovery_ours = float((ours_matched * w).sum() / n_inj) if n_inj > 0 else float("nan")
        recovery_theirs = float((theirs_matched * w).sum() / n_inj) if n_inj > 0 else float("nan")

        def m_syn(mask):
            ww = w * mask
            denom = float((theirs_matched * ww).sum())
            if denom <= 0:
                return float("nan")
            numer = float((theirs_matched * (1.0 - ours_matched) * ww).sum())
            return numer / denom

        not_f = 1.0 - is_f
        return {
            "recovery_ours": recovery_ours, "recovery_theirs": recovery_theirs,
            "m_syn_incl_f": m_syn(np.ones_like(is_f)), "m_syn_excl_f": m_syn(not_f),
        }

    unit_mult = np.ones(n_trials, dtype=np.float64)
    point = stats(unit_mult)

    rng = random.Random(SEED)
    boot = {k: [] for k in point}
    for _ in range(N_BOOT):
        idx = rng.choices(range(n_trials), k=n_trials)
        mult = np.bincount(idx, minlength=n_trials).astype(np.float64)
        d = stats(mult)
        for k in point:
            boot[k].append(d[k])

    ci = {}
    for k in point:
        lo, hi, hw, nv = boot_ci(boot[k])
        ci[k] = {"point": point[k], "ci_lo": lo, "ci_hi": hi, "halfwidth": hw, "n_boot_valid": nv}

    m_syn_gate = ci["m_syn_excl_f"]["point"]
    if m_syn_gate >= GATE_C_BAR and point["recovery_ours"] >= point["recovery_theirs"]:
        row = "C1"
    elif m_syn_gate >= GATE_C_BAR and point["recovery_ours"] < point["recovery_theirs"]:
        row = "C2"
    else:
        row = "C3"

    n_f_signals = int(is_f.sum())
    station_f = {
        "n_signals": n_f_signals,
        "ours_recovered": int(ours_matched[is_f == 1.0].sum()),
        "theirs_recovered": int(theirs_matched[is_f == 1.0].sum()),
    }

    result = {
        "meta": {"seed": SEED, "n_boot": N_BOOT, "n_trials": n_trials, "n_signals": n_signals,
                  "matched_csv": path},
        "ci": ci, "row": row, "station_f": station_f,
        "false_positives_informational_not_gated": {
            "counts": fp_counts, "candidate_totals": candidate_totals,
            "excluded_stale_all_txt_contamination": fp_excluded_stale,
            "valid_cycle_count": len(valid_cycle_utcs),
        },
    }

    ts = time.strftime("%Y%m%d_%H%M%SZ", time.gmtime())
    out_dir = os.path.join(HERE, "results")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "%s-c_asym_a_part_c_report.json" % ts)
    with io.open(out_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, sort_keys=True)
    print("Wrote %s" % out_path)

    print("\n" + "=" * 90)
    print("recovery_ours=%.4f (CI [%.4f,%.4f])  recovery_theirs=%.4f (CI [%.4f,%.4f])"
          % (ci["recovery_ours"]["point"], ci["recovery_ours"]["ci_lo"], ci["recovery_ours"]["ci_hi"],
             ci["recovery_theirs"]["point"], ci["recovery_theirs"]["ci_lo"], ci["recovery_theirs"]["ci_hi"]))
    print("M_syn (incl F)=%.4f (CI [%.4f,%.4f])" % (
        ci["m_syn_incl_f"]["point"], ci["m_syn_incl_f"]["ci_lo"], ci["m_syn_incl_f"]["ci_hi"]))
    print("M_syn (excl F, GATED)=%.4f (CI [%.4f,%.4f]) halfwidth=%.4f -> ROW %s" % (
        ci["m_syn_excl_f"]["point"], ci["m_syn_excl_f"]["ci_lo"], ci["m_syn_excl_f"]["ci_hi"],
        ci["m_syn_excl_f"]["halfwidth"], row))
    print("Station F: %d/%d OpenWSFZ, %d/%d WSJT-X" % (
        station_f["ours_recovered"], station_f["n_signals"],
        station_f["theirs_recovered"], station_f["n_signals"]))
    print("Pure FP candidates (informational, NOT gated): %s" % fp_counts)
    print("=" * 90)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
