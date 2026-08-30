"""NBR-A Amendment 2 -- readable-window probe (ROW 0c'), predicate power
check (ROW 0f, NEW), and the rewritten periodicity predicate (ROW 1').

Spec: qa/rr-study/2026-08-29-2329-architect-to-qa-nbr-a-amendment-2-
readable-window-probe-and-row1-rewrite.md. Supersedes spec 427a5cf
(qa/rr-study/2026-08-27-2100-...) Sec.4.4 ROW 0c and Sec.4.5 ROW 1 ONLY.
Amendment 1 (6757586) and everything else in 427a5cf stand unchanged.

Reuses nbr_a.py verbatim (HK-018) for ROW 0a, ROW 0d, ROW 0e, the main
sweep (run_sweep) and its ROW 3 sign-check / first-sustained-recovery
helper -- none of those rows changed under Amendment 2. This module
supplies only what the amendment actually replaces or adds: ROW 0b'
(narrowed determinism check, disclosed), ROW 0c' (readable-window probe),
ROW 0f (predicate power, NEW), and ROW 1' (detrend + named-lag
autocorrelation + measured permutation null, evaluated only over the
window W that ROW 0c' fixes).

── Implementation choice, disclosed per this project's own standing
convention (nbr_a.py's own L-convention disclosure; F-NBR-A's row0.py
Sec. on ROW 0b) -- ROW 0b' EXECUTION ORDER vs. the spec's document order.
Sec.4 lists ROW 0b' (Sec.4.1) before ROW 0c' (Sec.4.2), and this module
respects that as the GATING order (0b' failing invalidates 0c' before
0c' is interpreted). But Sec.7's own cost table prices ROW 0b' at 1100
trials and ROW 0c' at 5500 -- 1100 is exactly ONE independent re-run of
the 11 L=0dB points, not two, and 5500+1100=6600 matches the table's own
subtotal exactly. The only construction that reconciles "twice,
independently" with a 1100-trial price is: the probe's own L=0dB row
(part of the 5500) stands as the FIRST run, and this module spends 1100
NEW trials re-running those same 11 conditions (same part_index, hence
same compute_seed) a second time, diffing the two. This is why the probe
is computed before the diff is evaluated below, even though the
determinism check is reported and gates first, per Sec.4's stated order.
If QA judges this reconciliation wrong, the safe fallback is to run the
full 2200-trial double instead -- flagged in the report either way.

Seed convention (implementation-only, per HK-021 identifiability), part_index
ranges disjoint from every one already in use (row0.py: 0; part_c.py: 101,
201-207, 301-304; nbr_a.py: 90000-90011, 90100-90132, 90200-90207):
  91000-91010  ROW 0b' second independent run, L=0dB, 11 probe deltas
                (SAME part_index as the probe's own L=0dB row below --
                determinism means the SAME seed reproduces the SAME
                decode, not a different seed)
  92000-92054  ROW 0c' probe, 5 levels x 11 deltas: 92000 + level_idx*11
                + delta_idx, level_idx over PROBE_LEVELS_DB in listed order
                (+3, 0, -3, -6, -9)
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
_QA_ROOT = os.path.join(REPO_ROOT, "qa", "rr-study")
if _QA_ROOT not in sys.path:
    sys.path.insert(0, _QA_ROOT)

import dll_common as DC  # noqa: E402
import nbr_a as NA  # noqa: E402  -- reused rows/helpers, HK-018

RESULTS_DIR = os.path.join(HERE, "results")

# ── ROW 0c' grid -- every 3rd point of the sweep's own 1.5625 Hz lattice,
# so the measurement transfers to the sweep without re-interpolation. ──────
PROBE_DELTAS_HZ = [round(i * NA.SWEEP_STEP_HZ * 3, 6) for i in range(11)]
assert PROBE_DELTAS_HZ == [0.0, 4.6875, 9.375, 14.0625, 18.75, 23.4375,
                            28.125, 32.8125, 37.5, 42.1875, 46.875], PROBE_DELTAS_HZ
PROBE_LEVELS_DB = [3.0, 0.0, -3.0, -6.0, -9.0]
N_PROBE = 100
PROBE_STEP_HZ = 4.6875

READABLE_LO, READABLE_HI = 0.15, 0.85
READABLE_RUN_MIN_POINTS = 5        # span >= 18.75 Hz = 3 x 6.25 Hz periods

ROW1P_LAG_STEPS = 4                 # 4 x 1.5625 Hz = 6.25 Hz, the NAMED lag
ROW1P_LAG_HZ = ROW1P_LAG_STEPS * NA.SWEEP_STEP_HZ
assert abs(ROW1P_LAG_HZ - NA.ROW1_PERIOD_HZ) < 1e-9
ROW1P_N_PERM = 10_000
ROW1P_PERM_SEED = 20260830          # per spec Sec.5.3
ROW1P_P_THRESHOLD = 0.01

POWER_AMPLITUDES_PP = [0.0, 10.0, 20.0, 30.0, 40.0]
POWER_N_DRAWS = 100
POWER_TARGET_FRACTION = 0.90
POWER_A_MIN_CEILING = 30.0


def _log_ts():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── ROW 0c' part_index allocation ───────────────────────────────────────────
def _row0cp_part_index(level_idx, delta_idx):
    return 92000 + level_idx * 11 + delta_idx


def _row0bp_part_index(delta_idx):
    """SAME part_index as the probe's L=0dB row (level_idx=1) -- determinism
    tests whether the SAME seed reproduces the SAME decode, not a new draw."""
    return _row0cp_part_index(1, delta_idx)


def _run_probe_row(dec, level_db, delta_hz, part_index, log):
    hits, r = NA._run_f_condition(dec, delta_hz, level_db, part_index, N_PROBE, log, "ROW0c'")
    return {"level_deficit_db": level_db, "delta_hz": delta_hz, "hits": hits,
            "n_trials": N_PROBE, "r": r}


# ── ROW 0c': the readable-window probe ──────────────────────────────────────
def run_probe(dec, log) -> list[dict]:
    all_rows = []
    for li, level in enumerate(PROBE_LEVELS_DB):
        for di, delta in enumerate(PROBE_DELTAS_HZ):
            row = _run_probe_row(dec, level, delta, _row0cp_part_index(li, di), log)
            all_rows.append(row)
    return all_rows


def _readable_runs(rows_at_level):
    rows_sorted = sorted(rows_at_level, key=lambda r: r["delta_hz"])
    runs, current = [], []
    for row in rows_sorted:
        if READABLE_LO <= row["r"] <= READABLE_HI:
            current.append(row)
        else:
            if current:
                runs.append(current)
            current = []
    if current:
        runs.append(current)
    return runs


def evaluate_row0cp(all_rows, log) -> dict:
    per_level = {}
    for level in PROBE_LEVELS_DB:
        rows_at_level = [r for r in all_rows if r["level_deficit_db"] == level]
        runs = _readable_runs(rows_at_level)
        best_run = max(runs, key=len) if runs else []
        span_hz = (len(best_run) - 1) * PROBE_STEP_HZ if best_run else 0.0
        mean_r = (sum(r["r"] for r in best_run) / len(best_run)) if best_run else None
        per_level[level] = {
            "rows": rows_at_level,
            "readable_runs_hz": [[r["delta_hz"] for r in run] for run in runs],
            "longest_run_points": len(best_run),
            "longest_run_span_hz": span_hz,
            "longest_run_mean_r": mean_r,
            "longest_run_deltas_hz": [r["delta_hz"] for r in best_run],
        }
        log("ROW 0c': L=%.1fdB longest readable run = %d points, span=%.4fHz, mean R=%s"
            % (level, len(best_run), span_hz, ("%.3f" % mean_r) if mean_r is not None else "n/a"))

    qualifying = {lvl: info for lvl, info in per_level.items()
                  if info["longest_run_points"] >= READABLE_RUN_MIN_POINTS}

    if not qualifying:
        log("ROW 0c': FIRES -- no level has a readable run of >=%d consecutive points (span >=18.75Hz)"
            % READABLE_RUN_MIN_POINTS)
        return {"fires": True, "pass": False, "l_star": None, "window_hz": None, "per_level": per_level}

    def _tiebreak_key(item):
        lvl, info = item
        return (-info["longest_run_points"], abs(info["longest_run_mean_r"] - 0.50), lvl)

    l_star, info_star = min(qualifying.items(), key=_tiebreak_key)
    log("ROW 0c': PASS -- L*=%.1fdB, W span=%.4fHz (%d points), mean R=%.3f"
        % (l_star, info_star["longest_run_span_hz"], info_star["longest_run_points"],
           info_star["longest_run_mean_r"]))
    return {
        "fires": False, "pass": True, "l_star": l_star,
        "window_hz": info_star["longest_run_deltas_hz"], "per_level": per_level,
    }


# ── ROW 0b': narrowed determinism check (disclosed reconciliation above) ───
def run_row0bp(dec, probe_rows, log) -> dict:
    l0_rows_run1 = sorted(
        [r for r in probe_rows if r["level_deficit_db"] == 0.0], key=lambda r: r["delta_hz"])
    assert len(l0_rows_run1) == 11, len(l0_rows_run1)

    log("=" * 78)
    log("ROW 0b': independent second run, L=0dB, all 11 probe deltas")
    log("=" * 78)
    run2_rows = []
    for di, delta in enumerate(PROBE_DELTAS_HZ):
        row = _run_probe_row(dec, 0.0, delta, _row0bp_part_index(di), log)
        run2_rows.append(row)

    j1 = json.dumps(l0_rows_run1, sort_keys=True, indent=2)
    j2 = json.dumps(run2_rows, sort_keys=True, indent=2)
    with open(os.path.join(RESULTS_DIR, "_nbr_a_row0bp_run1_l0.json"), "w") as fh:
        fh.write(j1)
    with open(os.path.join(RESULTS_DIR, "_nbr_a_row0bp_run2_l0.json"), "w") as fh:
        fh.write(j2)
    identical = (j1 == j2)
    log("ROW 0b': two independent L=0dB runs byte-identical: %s" % identical)
    return {"pass": identical, "fires": not identical, "run1": l0_rows_run1, "run2": run2_rows}


# ── shared statistic: LS-detrend + normalised autocorrelation at a named lag,
# vectorised permutation null (fast enough for ROW 0f's 500 repeated calls). ─
def _row1p_autocorr_stat(deltas, rs):
    x = np.asarray(deltas, dtype=float)
    y = np.asarray(rs, dtype=float)
    n = len(y)
    if n <= ROW1P_LAG_STEPS + 1:
        return None, None
    design = np.vstack([x, np.ones_like(x)]).T
    (slope, intercept), *_ = np.linalg.lstsq(design, y, rcond=None)
    resid = y - (slope * x + intercept)
    lag = ROW1P_LAG_STEPS
    den = float(np.sum(resid ** 2))
    if den == 0.0:
        return None, resid
    num = float(np.sum(resid[:-lag] * resid[lag:]))
    return num / den, resid


def _row1p_permutation_p(resid, p_obs, seed):
    """Vectorised: all ROW1P_N_PERM permutations generated and scored at once
    via argsort-of-random-floats (no Python-level shuffle loop, no set/dict
    iteration -- deterministic given `seed`, per the hash-randomised-iteration
    trap on the board)."""
    if p_obs is None or resid is None:
        return None
    n = len(resid)
    lag = ROW1P_LAG_STEPS
    rng = np.random.default_rng(seed)
    rand_vals = rng.random((ROW1P_N_PERM, n))
    perm_idx = np.argsort(rand_vals, axis=1)
    shuffled = resid[perm_idx]
    num = np.sum(shuffled[:, :-lag] * shuffled[:, lag:], axis=1)
    den = np.sum(shuffled ** 2, axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        p_perm = np.where(den != 0, num / den, 0.0)
    count_ge = int(np.sum(p_perm >= p_obs))
    return (1 + count_ge) / (ROW1P_N_PERM + 1)


# ── ROW 0f: predicate power (NEW) ───────────────────────────────────────────
def _dense_lattice_within(w_lo, w_hi):
    n = int(round((w_hi - w_lo) / NA.SWEEP_STEP_HZ)) + 1
    return [round(w_lo + i * NA.SWEEP_STEP_HZ, 6) for i in range(n)]


def _synthetic_r_curve(dense_deltas, trend, amplitude_pp, w_lo, rng):
    phase = 2.0 * np.pi * (np.asarray(dense_deltas) - w_lo) / NA.ROW1_PERIOD_HZ
    p = trend + (amplitude_pp / 100.0) * np.sin(phase)
    p = np.clip(p, 0.0, 1.0)
    hits = rng.binomial(N_PROBE, p)
    return hits / float(N_PROBE)


def run_row0f(window_hz, l_star_probe_rows, log) -> dict:
    w_lo, w_hi = min(window_hz), max(window_hz)
    dense_deltas = _dense_lattice_within(w_lo, w_hi)

    l_star_rows_sorted = sorted(l_star_probe_rows, key=lambda r: r["delta_hz"])
    probe_deltas = [r["delta_hz"] for r in l_star_rows_sorted]
    probe_rs = [r["r"] for r in l_star_rows_sorted]
    trend = np.interp(dense_deltas, probe_deltas, probe_rs)

    fraction_by_amp = {}
    for amp in POWER_AMPLITUDES_PP:
        n_fire = 0
        for draw in range(POWER_N_DRAWS):
            seed = ROW1P_PERM_SEED * 100_000 + int(amp) * 1_000 + draw
            rng = np.random.default_rng(seed)
            r_curve = _synthetic_r_curve(dense_deltas, trend, amp, w_lo, rng)
            p_obs, resid = _row1p_autocorr_stat(dense_deltas, r_curve)
            if p_obs is None:
                continue
            p_value = _row1p_permutation_p(resid, p_obs, seed + 1)
            if p_value is not None and p_obs > 0 and p_value <= ROW1P_P_THRESHOLD:
                n_fire += 1
        frac = n_fire / POWER_N_DRAWS
        fraction_by_amp[amp] = frac
        log("ROW 0f: A=%.0fpp fraction(P_obs>0 and p<=0.01)=%.2f (%d/%d)"
            % (amp, frac, n_fire, POWER_N_DRAWS))

    a_min = None
    for amp in POWER_AMPLITUDES_PP:
        if fraction_by_amp[amp] >= POWER_TARGET_FRACTION:
            a_min = amp
            break
    fp_rate_at_a0 = fraction_by_amp[0.0]
    fires = (a_min is None) or (a_min > POWER_A_MIN_CEILING)
    log("ROW 0f: A_min=%s, FP rate at A=0 is %.2f -- %s"
        % (a_min, fp_rate_at_a0, "FIRES -- STOP" if fires else "PASS"))
    return {
        "fires": fires, "pass": not fires, "a_min": a_min,
        "fp_rate_at_a0": fp_rate_at_a0, "fraction_by_amplitude_pp": fraction_by_amp,
        "dense_deltas_hz": dense_deltas,
    }


# ── ROW 1': the rewritten periodicity predicate, evaluated only over W ─────
def evaluate_row1p(sweep, window_hz, log) -> dict:
    base = NA.evaluate_reading_rows(sweep)  # reused (HK-018): ROW3 sign-check,
                                             # first_sustained_recovery_hz, etc.
    pos_rows = sweep["positive"]
    w_lo, w_hi = min(window_hz), max(window_hz)
    w_rows = sorted(
        [r for r in pos_rows if w_lo - 1e-6 <= r["delta_hz"] <= w_hi + 1e-6],
        key=lambda r: r["delta_hz"])
    deltas = [r["delta_hz"] for r in w_rows]
    rs = [r["r"] for r in w_rows]

    p_obs, resid = _row1p_autocorr_stat(deltas, rs)
    p_value = _row1p_permutation_p(resid, p_obs, ROW1P_PERM_SEED) if p_obs is not None else None
    periodicity_row1p = (p_obs is not None and p_obs > 0
                          and p_value is not None and p_value <= ROW1P_P_THRESHOLD)

    first_recovery_hz = base["first_sustained_recovery_hz"]
    in_far_window = (first_recovery_hz is not None
                      and NA.ROW1_FAR_WINDOW_HZ[0] <= first_recovery_hz <= NA.ROW1_FAR_WINDOW_HZ[1])
    row3_fires = base["row3_fires"]

    row1p_fires = periodicity_row1p and in_far_window and not row3_fires
    row2_fires = (not periodicity_row1p) and base["first_recovery_outside_tone_span_window"] and not row3_fires

    if row1p_fires:
        verdict = "ROW1"
    elif row2_fires:
        verdict = "ROW2"
    elif row3_fires:
        verdict = "ROW3"
    else:
        verdict = "ROW4"

    log("ROW 1': window=[%.4f,%.4f]Hz (%d dense points), P_obs=%s, p=%s, periodicity=%s"
        % (w_lo, w_hi, len(w_rows),
           ("%.4f" % p_obs) if p_obs is not None else "n/a",
           ("%.4g" % p_value) if p_value is not None else "n/a",
           periodicity_row1p))
    log("ROW 1'/2/3/4 verdict: %s (in_far_window=%s, row3_fires=%s)"
        % (verdict, in_far_window, row3_fires))

    return {
        "verdict": verdict,
        "window_hz": [w_lo, w_hi], "window_n_points": len(w_rows),
        "deltas_in_window_hz": deltas, "r_in_window": rs,
        "detrend_residuals": resid.tolist() if resid is not None else None,
        "p_obs": p_obs, "p_value": p_value,
        "periodicity_row1p": periodicity_row1p,
        "first_sustained_recovery_hz": first_recovery_hz,
        "in_far_window_43.75pm6.25hz": in_far_window,
        "row3_fires": row3_fires,
        "n_sign_fires_ge_0.30": base["n_sign_fires_ge_0.30"],
        "sign_check": base["sign_check"],
        "first_recovery_outside_tone_span_window": base["first_recovery_outside_tone_span_window"],
    }


_DEC = None


def _dec_singleton():
    global _DEC
    if _DEC is None:
        _DEC = DC.load_decoder()
    return _DEC


# ── Orchestration ────────────────────────────────────────────────────────
def main():
    force = "--force" in sys.argv[1:]

    def log(msg):
        print("[%s] %s" % (_log_ts(), msg), flush=True)

    os.makedirs(RESULTS_DIR, exist_ok=True)
    result = {"run_started_utc": _log_ts()}

    log("ROW 0a")
    ok0a = NA.row0a(log)
    result["0a"] = ok0a
    if not ok0a:
        result["stopped_at"] = "0a"
        _write(result, force, log)
        sys.exit(1)

    dec = _dec_singleton()

    log("ROW 0c' probe -- 5 levels x 11 deltas x N=100 = 5500 trials")
    probe_rows = run_probe(dec, log)
    result["0cp_probe_rows"] = probe_rows

    row0bp_result = run_row0bp(dec, probe_rows, log)
    result["0bp"] = row0bp_result
    if not row0bp_result["pass"]:
        result["stopped_at"] = "0bp"
        result["note"] = ("ROW 0b' FIRES -- the two independent L=0dB runs differ; every R "
                           "collected above, including the 0c' probe, is unreadable. STOP.")
        _write(result, force, log)
        sys.exit(1)

    row0cp_result = evaluate_row0cp(probe_rows, log)
    result["0cp"] = row0cp_result
    if row0cp_result["fires"]:
        result["stopped_at"] = "0cp"
        result["hard_close"] = ("ROW 0c' FIRES -- the near-neighbour delta-response is a cliff, "
                                 "not a gradient: at every level tested the unsaturated window is "
                                 "too narrow to carry a 6.25Hz reading at N=100. NBR-A is CLOSED "
                                 "per Amendment 2 Sec.8. No third calibration re-spec is authorised.")
        _write(result, force, log)
        log("HARD CLOSE at ROW 0c' -- see result['hard_close']")
        sys.exit(0)

    l_star = row0cp_result["l_star"]
    l_star_rows = row0cp_result["per_level"][l_star]["rows"]
    window_hz = row0cp_result["window_hz"]

    log("ROW 0f -- predicate power check (numpy only, no decoder)")
    row0f_result = run_row0f(window_hz, l_star_rows, log)
    result["0f"] = row0f_result
    if row0f_result["fires"]:
        result["stopped_at"] = "0f"
        result["hard_close"] = ("ROW 0f FIRES -- the predicate cannot see an effect of a size the "
                                 "mechanism plausibly produces; a null would be uninterpretable. "
                                 "NBR-A is CLOSED per Amendment 2 Sec.8. No third calibration "
                                 "re-spec is authorised.")
        _write(result, force, log)
        log("HARD CLOSE at ROW 0f -- see result['hard_close']")
        sys.exit(0)

    row0d_result = NA.row0d(dec, l_star, log)
    result["0d"] = row0d_result
    if not row0d_result["pass"]:
        result["stopped_at"] = "0d"
        _write(result, force, log)
        sys.exit(1)

    row0e_result = NA.row0e(dec, log)
    result["0e"] = row0e_result
    if not row0e_result["pass"]:
        result["stopped_at"] = "0e"
        _write(result, force, log)
        sys.exit(1)

    log("Main sweep at L*=%.1fdB (33+8 points, unchanged from 427a5cf)" % l_star)
    sweep = NA.run_sweep(dec, l_star, log)
    result["sweep"] = sweep

    row1p_result = evaluate_row1p(sweep, window_hz, log)
    result["reading"] = row1p_result
    result["stopped_at"] = None

    result["dll_sha256"] = DC.PINNED_DLL_SHA256
    result["dll_shim_version"] = DC.PINNED_SHIM_VERSION
    _write(result, force, log)


def _write(result, force, log):
    result["run_finished_utc"] = _log_ts()
    out_path = os.path.join(RESULTS_DIR, "nbr-a-amendment2-results.json")
    if os.path.exists(out_path) and not force:
        raise SystemExit("refusing to overwrite existing %s without --force" % out_path)
    with open(out_path, "w") as fh:
        json.dump(result, fh, sort_keys=True, indent=2, default=str)
    log("Wrote %s" % out_path)


if __name__ == "__main__":
    main()
