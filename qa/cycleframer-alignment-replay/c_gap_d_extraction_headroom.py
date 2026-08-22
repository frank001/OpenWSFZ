#!/usr/bin/env python3
"""C-GAP-D -- how much of D-001 is reachable by extraction quality at all?

Spec: qa/rr-study/2026-08-22-1902-architect-to-qa-spec-c-gap-d-extraction-headroom-
decomposition.md. Verifies, with proper cluster inference and a null control, an
Architect-exploratory single-leg/single-band finding: that a perfect 3 dB extraction
gain (Route B2's whole remaining ceiling) closes only ~16% of D-001's 43.8 pp gap.

Population: X1's own `build_band()`/`load_band_raw()`, imported and called UNMODIFIED
(HK-018) -- no re-derivation of REF, exclusions, or the reference-SNR convention.
SNR is always the reference's (`DEFECT-snr-reported-gain-error.md`). Legs (`8080`,
`8081`) are always reported separately, never pooled.

Part A (Sec.3): G(delta)_pp, the upper-bound estimator for what a uniform Δ dB
extraction-quality improvement could recover, expressed as pp of the reference
population. Cluster bootstrap by `ts` (HK-021(i)), 2000 draws, fixed seed 20260822,
resampling whole cycles WITHIN each band independently (implemented as an index-level
resample over `range(n_cycles)` -- algorithmically identical to `rng.choices(cycles,
k=len(cycles))`: `random.choices` draws the same underlying `random()` sequence
regardless of what the equal-weight population contains, only its length matters).

Part B (Sec.4): the excess-over-null "near" rate -- misses that are actually decodes
we made and mislabelled (a text mismatch scores as a miss under the `(ts, message)`
join). Null control shifts the miss's frequency by a fixed offset (mod the 200-3000 Hz
band, same convention X1 already applies) before repeating the identical proximity
test, so the excess isolates genuine co-location from cycle-density coincidence.

NFR-021: message text is read only in-process (T1-T4 classification, Sec.4.2) and is
NEVER written to any row dict, JSON field, or log line -- only counts/types leave this
process, per spec Sec.4.2's explicit instruction.

N14: every output path below is derived from this run's own UTC timestamp; nothing is
ever overwritten by a bare re-run, so no separate guard module is needed.
"""
from __future__ import annotations

import collections
import io
import json
import os
import random
import statistics
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from x1_cross_band_decomposition import (  # noqa: E402 -- reused unmodified, HK-018
    EXPECT_CLEAN_REF,
    build_band,
    load_band_raw,
)

SEED = 20260822
N_BOOT = 2000
BANDS = ("20m", "17m", "80m")
LEGS = ("8080", "8081")
DELTAS = (1, 2, 3, 6, 10)
MIN_N = 30                     # readout-quantum floor for a usable R(s) cell (Sec.3.1)
CLUSTER_FLOOR_CYCLES = 200      # Sec.5.1 ROW 0e
CLUSTER_FLOOR_ROWS = 5000
GATE_BAND = "20m"
GATE_LEG = "8080"
ROW1_BAR = 10.0
ROW3_BAR = 25.0
ESCALATE_HALFWIDTH_PP = 2.0     # Sec.5.2
NULL_SHIFTS = (700, 1300)
NEAR_TOL_HZ = 5.0
FREQ_FLOOR, FREQ_CEIL = 200, 3000   # matches X1's own band exclusion (Sec 2)
BAND_WIDTH = FREQ_CEIL - FREQ_FLOOR
BIN_WIDTH_DB = 5
CLASSIFY_MIN_SNR = 0            # Sec.4.2 -- "misses flagged near at reference SNR >= 0 dB"

# SNR index range: generous vs the observed -25..+20 (Architect's disclosure, Sec.6).
S_MIN, S_MAX = -40, 40
S_SIZE = S_MAX - S_MIN + 1


def s_to_idx(s):
    return s - S_MIN


# ── Part A substrate ────────────────────────────────────────────────────────────────────

def prepare_band_arrays(band):
    """Per-row numpy arrays shared by both legs: SNR index, cycle index, frequency.
    Matched flags are per-leg and built separately (prepare_matched)."""
    cycles = band.cycles
    cyc_index = {ts: i for i, ts in enumerate(cycles)}
    n = len(band.rows)
    s_arr = np.empty(n, dtype=np.int64)
    cyc_arr = np.empty(n, dtype=np.int64)
    freq_arr = np.empty(n, dtype=np.float64)
    clamped = 0
    for i, r in enumerate(band.rows):
        s = r["snr"]
        if s < S_MIN or s > S_MAX:
            clamped += 1
            s = max(S_MIN, min(S_MAX, s))
        s_arr[i] = s_to_idx(s)
        cyc_arr[i] = cyc_index[r["ts"]]
        freq_arr[i] = r["freq_hz"]
    return {
        "cycles": cycles, "cyc_index": cyc_index, "s_arr": s_arr, "cyc_arr": cyc_arr,
        "freq_arr": freq_arr, "clamped": clamped, "n": n,
    }


def prepare_matched(band, leg):
    key = "matched" + leg
    return np.array([1.0 if r[key] else 0.0 for r in band.rows], dtype=np.float64)


def draw_mult(rng, n_cycles):
    """One cluster-bootstrap draw's per-cycle multiplicity vector.

    `rng.choices(range(n_cycles), k=n_cycles)` draws the same underlying random()
    sequence `rng.choices(cycles, k=len(cycles))` would (population contents don't
    affect which random() calls are made for equal-weight sampling, only len(population)
    does) -- so this is the index-level form of "resample whole cycles with
    replacement," not a different method.
    """
    idx = rng.choices(range(n_cycles), k=n_cycles)
    return np.bincount(idx, minlength=n_cycles).astype(np.float64)


def g_delta_pp(n_by_s, matched_by_s, delta):
    """Sec.3.1's G(delta)_pp, vectorised over the SNR-index axis."""
    valid = n_by_s >= MIN_N
    R = np.full(S_SIZE, np.nan)
    R[valid] = matched_by_s[valid] / n_by_s[valid]
    R_shift = np.full(S_SIZE, np.nan)
    if delta < S_SIZE:
        R_shift[: S_SIZE - delta] = R[delta:]
    miss_by_s = n_by_s - matched_by_s
    with np.errstate(invalid="ignore", divide="ignore"):
        ok = np.isfinite(R) & np.isfinite(R_shift) & (R < 1.0)
        gain = np.where(ok, np.maximum(0.0, (R_shift - R) / (1.0 - R)), 0.0)
    G = float(np.sum(gain * miss_by_s))
    N_ref = float(n_by_s.sum())
    return (100.0 * G / N_ref) if N_ref > 0 else float("nan")


def recall_curve(n_by_s, matched_by_s):
    """R(s) dict for reporting, s in real dB, only where n(s) >= MIN_N."""
    out = {}
    for i in range(S_SIZE):
        if n_by_s[i] >= MIN_N:
            out[S_MIN + i] = matched_by_s[i] / n_by_s[i]
    return out


# ── Part B substrate ─────────────────────────────────────────────────────────────────────

def build_freq_index(o_dict):
    """{ts: [(freq_hz, message), ...]} from an X1 load_band_raw() OpenWSFZ-side dict."""
    idx = collections.defaultdict(list)
    for (ts, msg), (snr, freq_hz) in o_dict.items():
        idx[ts].append((freq_hz, msg))
    return idx


def wrapped_freq(f_ref, shift):
    return FREQ_FLOOR + ((f_ref - FREQ_FLOOR + shift) % BAND_WIDTH)


def nearest_within(freq_index, ts, target_hz, tol=NEAR_TOL_HZ):
    """Nearest (freq,message) within tol Hz of target_hz among ts's OWSFZ decodes, or
    None. Used both for the real "near" test and, with the wrapped frequency, for the
    null control -- identical detector, only the target frequency differs."""
    best = None
    best_d = tol + 1.0
    for f, msg in freq_index.get(ts, ()):
        d = abs(f - target_hz)
        if d <= tol and d < best_d:
            best = (f, msg)
            best_d = d
    return best


def classify_mismatch(msg_ref, msg_ours):
    """T1-T4 per spec Sec.4.2. Heuristic: the last whitespace token is treated as the
    variable exchange field (report/RR73/73/grid) in both CQ and directed forms; every
    token before it is the "callsign part". Returns one of "T1".."T4"; never returns or
    logs either message string (NFR-021 -- caller must not log its inputs either)."""
    ref_has_hash = "<...>" in msg_ref
    ours_has_hash = "<...>" in msg_ours
    if ours_has_hash and not ref_has_hash:
        return "T1"
    tok_ref = msg_ref.split()
    tok_ours = msg_ours.split()
    call_ref, call_ours = tok_ref[:-1], tok_ours[:-1]
    if call_ref == call_ours and len(tok_ref) == len(tok_ours) and tok_ref[-1:] != tok_ours[-1:]:
        return "T2"
    if call_ref and call_ours and len(call_ref) == len(call_ours) and call_ref != call_ours:
        return "T3"
    return "T4"


def bin_label(s):
    return BIN_WIDTH_DB * (s // BIN_WIDTH_DB)


def prepare_partb_arrays(band, leg, o_dict):
    """Per-miss (for this leg) arrays: SNR index, cycle index, near/null flags at the
    POINT estimate (mult=1 for every cycle) -- the flags themselves don't change across
    bootstrap draws (they're a property of the row + the fixed OWSFZ index), only which
    rows get resampled does, so we precompute once and let the draw reweight them."""
    key = "matched" + leg
    freq_index = build_freq_index(o_dict)
    s_list, cyc_list, near_list, null_lists = [], [], [], {sh: [] for sh in NULL_SHIFTS}
    cyc_index = {ts: i for i, ts in enumerate(band.cycles)}
    msg_ref_by_row = []
    msg_ours_by_row = []
    for (ts, msg_ref), r in zip(band.kept, band.rows):
        if r[key]:
            continue
        f_ref = r["freq_hz"]
        s = max(S_MIN, min(S_MAX, r["snr"]))
        hit = nearest_within(freq_index, ts, f_ref)
        s_list.append(s_to_idx(s))
        cyc_list.append(cyc_index[ts])
        near_list.append(1.0 if hit is not None else 0.0)
        for sh in NULL_SHIFTS:
            fp = wrapped_freq(f_ref, sh)
            null_lists[sh].append(1.0 if nearest_within(freq_index, ts, fp) is not None else 0.0)
        if r["snr"] >= CLASSIFY_MIN_SNR and hit is not None:
            msg_ref_by_row.append(msg_ref)
            msg_ours_by_row.append(hit[1])
    return {
        "s_arr": np.array(s_list, dtype=np.int64),
        "cyc_arr": np.array(cyc_list, dtype=np.int64),
        "near_arr": np.array(near_list, dtype=np.float64),
        "null_arr": {sh: np.array(null_lists[sh], dtype=np.float64) for sh in NULL_SHIFTS},
        "classify_pairs": list(zip(msg_ref_by_row, msg_ours_by_row)),  # in-process only
    }


def rate_by_bin(s_arr, flag_arr, weight):
    """Weighted rate of flag_arr==1, grouped by 5 dB SNR bin, plus pooled."""
    out = {}
    if len(s_arr) == 0:
        return out, float("nan")
    real_s = s_arr + S_MIN
    bins = np.array([bin_label(int(s)) for s in real_s])
    for b in sorted(set(bins.tolist())):
        m = bins == b
        wsum = weight[m].sum()
        if wsum <= 0:
            continue
        out[int(b)] = float((flag_arr[m] * weight[m]).sum() / wsum)
    wsum_all = weight.sum()
    pooled = float((flag_arr * weight).sum() / wsum_all) if wsum_all > 0 else float("nan")
    return out, pooled


# ── ROW 0 validity ───────────────────────────────────────────────────────────────────────

def isotonic_pava(values, weights):
    """Weighted pool-adjacent-violators, non-decreasing fit. `values`/`weights` are
    parallel lists in x-order; returns the fitted values, same length/order."""
    level_vals = list(values)
    level_w = list(weights)
    level_n = [1] * len(values)
    i = 0
    while i < len(level_vals) - 1:
        if level_vals[i] > level_vals[i + 1]:
            merged_w = level_w[i] + level_w[i + 1]
            merged_v = (level_vals[i] * level_w[i] + level_vals[i + 1] * level_w[i + 1]) / merged_w
            level_vals[i:i + 2] = [merged_v]
            level_w[i:i + 2] = [merged_w]
            level_n[i:i + 2] = [level_n[i] + level_n[i + 1]]
            i = max(i - 1, 0)
        else:
            i += 1
    out = []
    for v, cnt in zip(level_vals, level_n):
        out.extend([v] * cnt)
    return out


def row0_checks(band_name, band, n_by_s_leg, matched_by_s_leg):
    checks = {}

    # 0a -- reproduces X1's own committed n_ref_clean (20m/17m only; 80m has no
    # committed baseline in x1_cross_band_decomposition.py, reported not gated).
    expected = EXPECT_CLEAN_REF.get(band_name)
    checks["0a"] = {
        "n_ref_clean": band.n_ref_clean,
        "expected": expected,
        "pass": (expected is None) or (band.n_ref_clean == expected),
        "gated": expected is not None,
    }

    # 0b -- both legs' pooled recall agree within 5 pp.
    pooled = {leg: (matched_by_s_leg[leg].sum() / n_by_s_leg[leg].sum()) * 100.0 for leg in LEGS}
    diff = abs(pooled["8080"] - pooled["8081"])
    checks["0b"] = {"pooled_pct": pooled, "abs_diff_pp": diff, "pass": diff <= 5.0}

    # 0c -- R(s) monotone non-decreasing after isotonic smoothing, bins n>=30.
    row0c = {}
    for leg in LEGS:
        n_by_s = n_by_s_leg[leg]
        matched_by_s = matched_by_s_leg[leg]
        idxs = [i for i in range(S_SIZE) if n_by_s[i] >= MIN_N]
        raw = [matched_by_s[i] / n_by_s[i] for i in idxs]
        w = [n_by_s[i] for i in idxs]
        smoothed = isotonic_pava(raw, w) if raw else []
        max_violation = max((abs(a - b) for a, b in zip(raw, smoothed)), default=0.0)
        row0c[leg] = {"max_violation": max_violation, "flag": max_violation > 0.05}
    checks["0c"] = row0c

    # 0e -- cluster floor.
    checks["0e"] = {
        "n_cycles": len(band.cycles), "n_rows": len(band.rows),
        "pass": len(band.cycles) >= CLUSTER_FLOOR_CYCLES and len(band.rows) >= CLUSTER_FLOOR_ROWS,
    }

    return checks


# ── per-band-leg pipeline ────────────────────────────────────────────────────────────────

def percentile(sorted_vals, p):
    """Nearest-rank percentile -- same convention as X1's own percentile() helper."""
    n = len(sorted_vals)
    if n == 0:
        return float("nan")
    idx = max(0, min(n - 1, int(round(p * (n - 1)))))
    return sorted_vals[idx]


def run_band_leg(band, arrays, leg, matched_arr, rng):
    """Point estimate + N_BOOT bootstrap draws for one (band, leg): Part A's G(delta)_pp
    ladder and its per-draw n_by_s/matched_by_s (returned for ROW 0 use)."""
    n_cycles = len(arrays["cycles"])
    s_arr, cyc_arr = arrays["s_arr"], arrays["cyc_arr"]

    # point estimate (every cycle weight 1)
    n_by_s_pt = np.bincount(s_arr, minlength=S_SIZE).astype(np.float64)
    matched_by_s_pt = np.bincount(s_arr, weights=matched_arr, minlength=S_SIZE)
    point = {d: g_delta_pp(n_by_s_pt, matched_by_s_pt, d) for d in DELTAS}
    recall_pt = recall_curve(n_by_s_pt, matched_by_s_pt)

    boot = {d: [] for d in DELTAS}
    for _ in range(N_BOOT):
        mult = draw_mult(rng, n_cycles)
        w = mult[cyc_arr]
        n_by_s = np.bincount(s_arr, weights=w, minlength=S_SIZE)
        matched_by_s = np.bincount(s_arr, weights=w * matched_arr, minlength=S_SIZE)
        for d in DELTAS:
            boot[d].append(g_delta_pp(n_by_s, matched_by_s, d))

    ci = {}
    for d in DELTAS:
        vals = sorted(v for v in boot[d] if not np.isnan(v))
        ci[d] = {
            "point": point[d],
            "ci_lo": percentile(vals, 0.025),
            "ci_hi": percentile(vals, 0.975),
            "halfwidth": (percentile(vals, 0.975) - percentile(vals, 0.025)) / 2.0 if vals else float("nan"),
            "n_boot_valid": len(vals),
        }
    return {
        "ci": ci, "recall": recall_pt,
        "n_by_s_point": n_by_s_pt, "matched_by_s_point": matched_by_s_pt,
    }


def run_partb(band, leg, o_dict, rng, n_cycles):
    pb = prepare_partb_arrays(band, leg, o_dict)
    s_arr, cyc_arr, near_arr = pb["s_arr"], pb["cyc_arr"], pb["near_arr"]
    w_pt = np.ones(len(s_arr))
    near_by_bin_pt, near_pooled_pt = rate_by_bin(s_arr, near_arr, w_pt)
    null_pt = {}
    for sh in NULL_SHIFTS:
        by_bin, pooled = rate_by_bin(s_arr, pb["null_arr"][sh], w_pt)
        null_pt[sh] = {"by_bin": by_bin, "pooled": pooled}

    excess_by_shift = {}
    for sh in NULL_SHIFTS:
        by_bin = {}
        for b, near_v in near_by_bin_pt.items():
            null_v = null_pt[sh]["by_bin"].get(b)
            if null_v is not None:
                by_bin[b] = near_v - null_v
        excess_by_shift[sh] = {
            "by_bin": by_bin,
            "pooled": near_pooled_pt - null_pt[sh]["pooled"],
        }
    shift_diffs = [
        abs(excess_by_shift[NULL_SHIFTS[0]]["by_bin"].get(b, 0.0) - excess_by_shift[NULL_SHIFTS[1]]["by_bin"].get(b, 0.0))
        for b in near_by_bin_pt
    ]
    shift_sensitive = any(d > 0.02 for d in shift_diffs)

    # classification (point estimate only, in-process; NFR-021 -- never store message text)
    counts = collections.Counter()
    for msg_ref, msg_ours in pb["classify_pairs"]:
        counts[classify_mismatch(msg_ref, msg_ours)] += 1
    del pb["classify_pairs"]  # never persisted past this function

    # bootstrap CI on the pooled excess (primary shift only, 700 Hz, per Sec.4.1)
    boot_excess = []
    for _ in range(N_BOOT):
        mult = draw_mult(rng, n_cycles)
        w = mult[cyc_arr]
        wsum = w.sum()
        if wsum <= 0:
            continue
        near_rate = float((near_arr * w).sum() / wsum)
        null_rate = float((pb["null_arr"][NULL_SHIFTS[0]] * w).sum() / wsum)
        boot_excess.append(near_rate - null_rate)
    boot_excess.sort()

    return {
        "near_by_bin": near_by_bin_pt, "near_pooled": near_pooled_pt,
        "null": {sh: null_pt[sh] for sh in NULL_SHIFTS},
        "excess_by_shift": excess_by_shift,
        "shift_sensitive": shift_sensitive,
        "excess_pooled_ci": {
            "point": near_pooled_pt - null_pt[NULL_SHIFTS[0]]["pooled"],
            "ci_lo": percentile(boot_excess, 0.025),
            "ci_hi": percentile(boot_excess, 0.975),
        },
        "classification_counts": dict(counts),
        "n_misses": int(len(s_arr)),
    }


# ── top-level ────────────────────────────────────────────────────────────────────────────

def compute_all(seed):
    rng = random.Random(seed)
    bands = {name: build_band(name) for name in BANDS}
    raw = {name: load_band_raw(name) for name in BANDS}  # a, b, o8080, o8081

    result = {"bands": {}}
    n_by_s_leg_all = {}
    matched_by_s_leg_all = {}

    for name in BANDS:
        band = bands[name]
        arrays = prepare_band_arrays(band)
        band_result = {"legs": {}, "clamped_snr_rows": arrays["clamped"]}
        n_by_s_leg, matched_by_s_leg = {}, {}
        for leg in LEGS:
            matched_arr = prepare_matched(band, leg)
            leg_result = run_band_leg(band, arrays, leg, matched_arr, rng)
            n_by_s_leg[leg] = leg_result.pop("n_by_s_point")
            matched_by_s_leg[leg] = leg_result.pop("matched_by_s_point")
            o_dict = raw[name][2] if leg == "8080" else raw[name][3]
            leg_result["part_b"] = run_partb(band, leg, o_dict, rng, len(arrays["cycles"]))
            band_result["legs"][leg] = leg_result
        band_result["row0"] = row0_checks(name, band, n_by_s_leg, matched_by_s_leg)
        result["bands"][name] = band_result

    # gate, on the primary band/leg only
    gate_ci = result["bands"][GATE_BAND]["legs"][GATE_LEG]["ci"][3]
    ci_lo, ci_hi = gate_ci["ci_lo"], gate_ci["ci_hi"]
    row0_fired = any(
        (not result["bands"][b]["row0"]["0a"]["pass"])
        or (not result["bands"][b]["row0"]["0b"]["pass"])
        or (not result["bands"][b]["row0"]["0e"]["pass"])
        for b in BANDS
    )
    halfwidth = gate_ci["halfwidth"]
    if row0_fired:
        gate_row = 0
    elif halfwidth is not None and not np.isnan(halfwidth) and halfwidth > ESCALATE_HALFWIDTH_PP:
        gate_row = 4  # escalate per Sec.5.2, do not read ROW 1 on an underpowered CI
    elif ci_hi < ROW1_BAR:
        gate_row = 1
    elif ci_lo >= ROW1_BAR and ci_hi < ROW3_BAR:
        gate_row = 2
    elif ci_lo >= ROW3_BAR:
        gate_row = 3
    else:
        gate_row = 4
    result["gate"] = {
        "band": GATE_BAND, "leg": GATE_LEG, "delta_db": 3,
        "ci_lo": ci_lo, "ci_hi": ci_hi, "halfwidth": halfwidth,
        "row0_fired": row0_fired, "row": gate_row,
    }
    result["meta"] = {
        "seed": seed, "n_boot": N_BOOT, "bands": list(BANDS), "legs": list(LEGS),
        "deltas": list(DELTAS),
    }
    return result


def to_jsonable(obj):
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, float) and np.isnan(obj):
        return None
    return obj


def main():
    t0 = time.time()
    print("C-GAP-D -- extraction-headroom decomposition. Seed %d, N_BOOT %d." % (SEED, N_BOOT))

    print("\nRun 1 (ROW 0d determinism check, pass 1)...")
    run1 = compute_all(SEED)
    print("Run 1 done in %.1fs" % (time.time() - t0))

    t1 = time.time()
    print("\nRun 2 (ROW 0d determinism check, pass 2, independent RNG re-seed)...")
    run2 = compute_all(SEED)
    print("Run 2 done in %.1fs" % (time.time() - t1))

    j1 = json.dumps(to_jsonable(run1), sort_keys=True)
    j2 = json.dumps(to_jsonable(run2), sort_keys=True)
    row0d_pass = (j1 == j2)
    print("\nROW 0d (mechanical diff, not a claim): %s" % ("PASS -- byte-identical" if row0d_pass else "FAIL -- runs differ"))

    final = to_jsonable(run1)
    final["row0d"] = {"pass": row0d_pass}

    ts = time.strftime("%Y%m%d_%H%M%SZ", time.gmtime())
    out_dir = os.path.join(HERE, "results")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "%s-c_gap_d_report.json" % ts)  # N14: timestamp-derived, never clobbers
    with io.open(out_path, "w", encoding="utf-8") as fh:
        json.dump(final, fh, indent=2, sort_keys=True)
    print("\nWrote %s" % out_path)

    gate = final["gate"]
    print("\n" + "=" * 90)
    print("GATE (band=%s leg=%s delta=3dB): CI=[%.3f, %.3f] halfwidth=%.3f row0_fired=%s"
          % (gate["band"], gate["leg"], gate["ci_lo"] or float("nan"), gate["ci_hi"] or float("nan"),
             gate["halfwidth"] or float("nan"), gate["row0_fired"]))
    print("ROW %s FIRES" % gate["row"])
    print("=" * 90)
    print("\nTotal wall time: %.1fs" % (time.time() - t0))
    return 0 if row0d_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
