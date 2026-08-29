"""NBR-A -- near-neighbour exclusion mechanism discriminator.

Spec: qa/rr-study/2026-08-27-2100-architect-to-qa-spec-nbr-a-near-neighbour-
exclusion-fix-route.md (commit 427a5cf), amended by
qa/rr-study/2026-08-29-2023-architect-to-qa-nbr-a-AUTHORISED-amendment-1.md
(commit 6757586). AUTHORISED by the Captain 2026-08-29 20:23:55Z, spec S5
option 1. Gate (ROW 0a-0e, ROW 1-4) is unchanged character for character by
the amendment; Part D is a new, explicitly NON-GATING addition.

Reuses the F-NBR-A instrument verbatim (HK-018): dll_common.py (pinned DLL,
decoder loader), scene_render.py (S8HN scene + mutation helpers, render_scene,
trial_seed/compute_seed), stats_common.py (Clopper-Pearson), and part_c.py's
own C2/C3 pattern for "interferer E fixed, victim F moved/releveled" -- this
IS that pattern, recalibrated (spec Sec.4.2) and extended to a fine ΔF sweep
with an autocorrelation read plus a new three-signal Part D.

── Implementation choice, disclosed per this project's own standing
convention (F-NBR-A's row0.py Sec. on ROW 0b; Amendment 1 Sec.0): the spec's
Metric R(Delta, L) names "victim level deficit L" and Amendment 1 Sec.2
independently confirms Sec.4.2's own worked example ("F-NBR-A swept ΔF at a
-3 dB level deficit ... 0/100 at 6.25, 12.00 and 18.75 Hz") reproduces
EXACTLY the already-committed C2 sweep, which ran the UNMODIFIED S8HN scene
(F snr_db=-8, E snr_db=-5). -8 - (-5) = -3. This fixes L's definition
unambiguously: L = victim_snr_db - interferer_snr_db (E's own snr_db, -5,
held fixed throughout -- "interferer fixed"). Applied uniformly to ROW 0c's
calibration, ROW 0d's positive control, ROW 0e's Delta=0 reproduction (its own
"-6 dB" is stated as the SAME deficit convention used to describe the S8 G/H
observation it reproduces: G snr_db=0, H snr_db=-6, deficit -6), and the main
sweep at L*. Part D's three-signal scenes state their own SNRs as plain
absolute 0 dB values (spec Sec.3), so Part D does NOT use this convention --
implemented literally as absolute snr_db=0.0 for every Part D station.

Seed convention (implementation-only, not a gated methodology choice, per
HK-021 identifiability): all S8HN-scene conditions (0c/0d/0e/sweep) use
scene_render.trial_seed (scenario_id "S8HN" fixed inside that helper) with a
distinct part_index per condition, disjoint from every part_index already
used by row0.py (0) and part_c.py (101, 201-207, 301-304):
  90000-90003  0c calibration, one per L in [0, -1, -2, -3] dB, in that order
  90010        0d positive control (Delta=100 Hz at L*)
  90011        0e Delta=0 reproduction (L=-6 dB deficit)
  90100-90132  main sweep, positive Delta, 0..50 Hz in 1.5625 Hz steps (33 pts)
  90200-90207  main sweep, mirrored negative Delta, -6.25..-50 Hz (8 pts)
Part D builds wholly synthetic scenes not derived from S8HN, so it calls
harness.common.compute_seed('NBR-A', part_index, trial_index) directly rather
than going through scene_render.trial_seed's hardcoded 'S8HN' scenario id:
  1  D1 (P2 replica, 3 signals scored separately)
  2  D2 pair 1 (0/+8 Hz)      3  D2 pair 2 (0/+11 Hz)
  4  D3 (3 signals, wide, E/E+100/E+200 Hz)
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np
from scipy.stats import beta as _beta_dist

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
_QA_ROOT = os.path.join(REPO_ROOT, "qa", "rr-study")
if _QA_ROOT not in sys.path:
    sys.path.insert(0, _QA_ROOT)

import dll_common as DC  # noqa: E402
import scene_render as SR  # noqa: E402
from harness.common import compute_seed  # noqa: E402
from harness.matcher import FREQ_TOLERANCE_HZ, _text_matches  # noqa: E402

RESULTS_DIR = os.path.join(HERE, "results")

N_TRIALS = 100
CAL_LEVELS_DB = [0.0, -1.0, -2.0, -3.0]          # ROW 0c, deficit relative to E
CAL_DELTA_HZ = 12.0                                # ROW 0c fixed Delta
POS_CTRL_DELTA_HZ = 100.0                          # ROW 0d
ROW0E_DELTA_HZ = 0.0                               # ROW 0e
ROW0E_LEVEL_DB = -6.0                              # ROW 0e deficit
SWEEP_STEP_HZ = 1.5625
SWEEP_MAX_HZ = 50.0
MIRROR_DELTAS_HZ = [-6.25, -12.5, -18.75, -25.0, -31.25, -37.5, -43.75, -50.0]
AUTOCORR_DOMAIN_HZ = (3.0, 44.0)
ROW1_PERIOD_HZ = 6.25
ROW1_PERIOD_TOL_HZ = 1.6
ROW1_FAR_WINDOW_HZ = (37.5, 50.0)                  # 43.75 +/- 6.25
ROW1_FAR_POINT_HZ = 43.75


def _log_ts():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _victim_recovered(results, target_freq_hz, target_message):
    if not results:
        return False
    return any(
        abs(r["freq_hz"] - target_freq_hz) <= FREQ_TOLERANCE_HZ
        and _text_matches(r["message"], target_message)
        for r in results
    )


def _f_scene(delta_hz, level_deficit_db):
    """S8HN scene with F moved to E_FREQ_HZ+delta_hz and F's snr_db set to
    E_SNR_DB + level_deficit_db (E itself untouched -- 'interferer fixed')."""
    signals = SR.load_s8hn_signals()
    signals = SR.move_station_freq(signals, SR.STATION_F, SR.E_FREQ_HZ + delta_hz)
    signals = SR.set_station_snr(signals, SR.STATION_F, SR.E_SNR_DB + level_deficit_db)
    return signals


def _run_f_condition(dec, delta_hz, level_deficit_db, part_index, n_trials, log, label):
    signals = _f_scene(delta_hz, level_deficit_db)
    target_freq = SR.E_FREQ_HZ + delta_hz
    hits = 0
    for t in range(n_trials):
        seed = SR.trial_seed(t, part_index)
        pcm = SR.render_scene(signals, seed)
        results = dec.decode_all(pcm)
        if _victim_recovered(results, target_freq, SR.F_TRUE_MESSAGE):
            hits += 1
    r = hits / n_trials
    log("%s: delta=%.4fHz L=%.1fdB (F snr=%.1fdB) hits=%d/%d R=%.3f"
        % (label, delta_hz, level_deficit_db, SR.E_SNR_DB + level_deficit_db, hits, n_trials, r))
    return hits, r


# ── ROW 0a ────────────────────────────────────────────────────────────────
def row0a(log) -> bool:
    a_ok, b_ok, a_hash, b_hash = DC.both_copies_match_pin()
    log("ROW 0a: native/ft8_lib_build/libft8.dll sha256=%s match=%s" % (a_hash, a_ok))
    log("ROW 0a: src/.../win-x64/libft8.dll      sha256=%s match=%s" % (b_hash, b_ok))
    ok = a_ok and b_ok
    log("ROW 0a: %s" % ("PASS" if ok else "VOID -- SHA256 mismatch"))
    return ok


# ── ROW 0c: level calibration, choose L* ────────────────────────────────────
def row0c(dec, log) -> dict:
    rows = []
    for i, level in enumerate(CAL_LEVELS_DB):
        part_index = 90000 + i
        hits, r = _run_f_condition(dec, CAL_DELTA_HZ, level, part_index, N_TRIALS, log, "ROW 0c")
        rows.append({"level_deficit_db": level, "hits": hits, "n_trials": N_TRIALS, "r": r})

    candidates = [row for row in rows if 0.15 <= row["r"] <= 0.60]
    if candidates:
        l_star = min(candidates, key=lambda row: abs(row["r"] - 0.35))["level_deficit_db"]
        ok = True
    else:
        l_star = None
        ok = False
    log("ROW 0c: L* = %s" % l_star)
    log("ROW 0c: %s" % ("PASS" if ok else "VOID -- no L in the calibration set yields 0.15<=R<=0.60"))
    return {"pass": ok, "l_star": l_star, "rows": rows}


# ── ROW 0d: positive control ────────────────────────────────────────────────
def row0d(dec, l_star, log) -> dict:
    hits, r = _run_f_condition(dec, POS_CTRL_DELTA_HZ, l_star, 90010, N_TRIALS, log, "ROW 0d")
    ok = r >= 0.95
    log("ROW 0d: %s" % ("PASS" if ok else "VOID -- R < 0.95 at Delta=100Hz, L*"))
    return {"pass": ok, "hits": hits, "r": r}


# ── ROW 0e: Delta=0 reproduction ────────────────────────────────────────────
def row0e(dec, log) -> dict:
    hits, r = _run_f_condition(dec, ROW0E_DELTA_HZ, ROW0E_LEVEL_DB, 90011, N_TRIALS, log, "ROW 0e")
    ok = r >= 0.80
    log("ROW 0e: %s" % ("PASS" if ok else "VOID -- R < 0.80 at Delta=0, L=-6dB deficit"))
    return {"pass": ok, "hits": hits, "r": r}


# ── Main sweep ───────────────────────────────────────────────────────────
def _sweep_positive_deltas():
    n_points = int(round(SWEEP_MAX_HZ / SWEEP_STEP_HZ)) + 1  # 0..50 inclusive
    return [round(i * SWEEP_STEP_HZ, 6) for i in range(n_points)]


def run_sweep(dec, l_star, log) -> dict:
    pos_deltas = _sweep_positive_deltas()
    pos_rows = []
    for i, delta in enumerate(pos_deltas):
        part_index = 90100 + i
        hits, r = _run_f_condition(dec, delta, l_star, part_index, N_TRIALS, log, "SWEEP+")
        pos_rows.append({"delta_hz": delta, "hits": hits, "n_trials": N_TRIALS, "r": r})

    neg_rows = []
    for j, delta in enumerate(MIRROR_DELTAS_HZ):
        part_index = 90200 + j
        hits, r = _run_f_condition(dec, delta, l_star, part_index, N_TRIALS, log, "SWEEP-")
        neg_rows.append({"delta_hz": delta, "hits": hits, "n_trials": N_TRIALS, "r": r})

    return {"l_star": l_star, "positive": pos_rows, "negative": neg_rows}


def _r_at(pos_rows, delta_hz, tol=1e-6):
    for row in pos_rows:
        if abs(row["delta_hz"] - delta_hz) <= tol:
            return row["r"]
    return None


def _autocorr_first_peak_hz(pos_rows):
    lo, hi = AUTOCORR_DOMAIN_HZ
    xs = [row["delta_hz"] for row in pos_rows if lo <= row["delta_hz"] <= hi]
    ys = [row["r"] for row in pos_rows if lo <= row["delta_hz"] <= hi]
    if len(ys) < 4:
        return None, xs, ys
    y = np.asarray(ys, dtype=float)
    y = y - y.mean()
    n = len(y)
    ac = np.correlate(y, y, mode="full")[n - 1:]
    if ac[0] == 0:
        return None, xs, ys
    ac = ac / ac[0]
    # first local maximum at lag >= 1
    peak_lag = None
    for lag in range(1, n - 1):
        if ac[lag] > ac[lag - 1] and ac[lag] >= ac[lag + 1] and ac[lag] > 0:
            peak_lag = lag
            break
    if peak_lag is None:
        return None, xs, ys
    peak_hz = peak_lag * SWEEP_STEP_HZ
    return peak_hz, xs, ys


def _first_sustained_recovery_hz(pos_rows, threshold=0.90):
    """Smallest |Delta| at which R reaches >= threshold and stays >= threshold
    for every subsequent swept point (sustained recovery, not a one-point
    fluctuation)."""
    rows_sorted = sorted(pos_rows, key=lambda row: row["delta_hz"])
    for i, row in enumerate(rows_sorted):
        if row["r"] >= threshold and all(r2["r"] >= threshold for r2 in rows_sorted[i:]):
            return row["delta_hz"]
    return None


def evaluate_reading_rows(sweep) -> dict:
    pos_rows = sweep["positive"]
    neg_rows = sweep["negative"]

    peak_hz, ac_xs, ac_ys = _autocorr_first_peak_hz(pos_rows)
    periodicity_at_625 = (
        peak_hz is not None
        and abs(peak_hz - ROW1_PERIOD_HZ) <= ROW1_PERIOD_TOL_HZ
    )

    r_at_far_point = _r_at(pos_rows, ROW1_FAR_POINT_HZ)
    far_window_rows = [r for r in pos_rows
                        if ROW1_FAR_WINDOW_HZ[0] <= r["delta_hz"] <= ROW1_FAR_WINDOW_HZ[1]]
    recovers_in_far_window = bool(far_window_rows) and all(r["r"] >= 0.90 for r in far_window_rows)

    # ROW 3: sign check at the 8 mirrored magnitudes
    sign_diffs = []
    for neg_row in neg_rows:
        mag = abs(neg_row["delta_hz"])
        r_pos = _r_at(pos_rows, mag)
        r_neg = neg_row["r"]
        diff = None if r_pos is None else abs(r_pos - r_neg)
        sign_diffs.append({"abs_delta_hz": mag, "r_pos": r_pos, "r_neg": r_neg, "abs_diff": diff})
    n_sign_fires = sum(1 for d in sign_diffs if d["abs_diff"] is not None and d["abs_diff"] >= 0.30)
    row3_fires = n_sign_fires >= 3

    first_recovery_hz = _first_sustained_recovery_hz(pos_rows)
    outside_tone_span_window = (
        first_recovery_hz is not None
        and not (ROW1_FAR_WINDOW_HZ[0] <= first_recovery_hz <= ROW1_FAR_WINDOW_HZ[1])
    )

    row1_fires = (
        periodicity_at_625
        and r_at_far_point is not None and r_at_far_point >= 0.90
        and not row3_fires
    )
    row2_fires = (
        (not periodicity_at_625)
        and outside_tone_span_window
        and not row3_fires
    )

    if row1_fires:
        verdict = "ROW1"
    elif row2_fires:
        verdict = "ROW2"
    elif row3_fires:
        verdict = "ROW3"
    else:
        verdict = "ROW4"

    return {
        "verdict": verdict,
        "autocorr_first_peak_hz": peak_hz,
        "autocorr_domain_hz": list(AUTOCORR_DOMAIN_HZ),
        "autocorr_xs": ac_xs,
        "autocorr_ys": ac_ys,
        "periodicity_at_6.25hz": periodicity_at_625,
        "r_at_43.75hz": r_at_far_point,
        "recovers_ge_0.90_in_far_window": recovers_in_far_window,
        "first_sustained_recovery_hz": first_recovery_hz,
        "first_recovery_outside_tone_span_window": outside_tone_span_window,
        "sign_check": sign_diffs,
        "n_sign_fires_ge_0.30": n_sign_fires,
        "row3_fires": row3_fires,
    }


# ── Part D (non-gating) ─────────────────────────────────────────────────────
def _q_signal(station, message_text, freq_hz, snr_db=0.0, dt_s=0.0):
    return {"station": station, "message_text": message_text, "freq_hz": float(freq_hz),
            "snr_db": float(snr_db), "dt_s": float(dt_s)}


D1_BASE_HZ = 1492.0  # mirrors real S7 P2's own frequencies for realism (not required)
D1_SIGNALS = [
    _q_signal("V1", "CQ Q2AAA FN20", D1_BASE_HZ),
    _q_signal("V2", "Q2AAA Q2BBB -10", D1_BASE_HZ + 8.0),
    _q_signal("V3", "Q2BBB Q2AAA R-08", D1_BASE_HZ + 19.0),
]

D3_BASE_HZ = 1492.0
D3_SIGNALS = [
    _q_signal("W1", "CQ Q2CCC FN20", D3_BASE_HZ),
    _q_signal("W2", "Q2CCC Q2DDD -10", D3_BASE_HZ + 100.0),
    _q_signal("W3", "Q2DDD Q2CCC R-08", D3_BASE_HZ + 200.0),
]


def _score_multi(dec, signals, part_index, n_trials, log, label):
    """Renders n_trials scenes of `signals` together; for each station in
    `signals`, counts trials in which THAT station's own (freq, message) is
    present in the decode result set. Returns one hit-count per station."""
    hits = {s["station"]: 0 for s in signals}
    for t in range(n_trials):
        seed = compute_seed("NBR-A", part_index, t)
        pcm = SR.render_scene(signals, seed)
        results = dec.decode_all(pcm)
        for s in signals:
            if _victim_recovered(results, s["freq_hz"], s["message_text"]):
                hits[s["station"]] += 1
    for s in signals:
        h = hits[s["station"]]
        log("%s: station %s (%.2fHz) hits=%d/%d R=%.3f"
            % (label, s["station"], s["freq_hz"], h, n_trials, h / n_trials))
    return hits


def _cp_upper_95_one_sided(k: int, n: int, conf: float = 0.95) -> float:
    """One-sided upper Clopper-Pearson bound -- the HK-021(o) 'rule of three'
    convention cited verbatim in Amendment 1 Sec.3.1 ('0/100 -> UB 3%').
    Deliberately NOT stats_common.clopper_pearson, which is two-sided (its own
    docstring: 'Gate A/rows C1-C3 need both bounds') and gives a materially
    different, more conservative number at k=0 (~3.6%, rounds to 4%) than the
    one-sided bound this project's own convention names (~3.0%). Same
    construction as harness/analyse.py's _cp_upper_95, reimplemented locally
    rather than importing a same-module-private name across packages."""
    if k >= n:
        return 1.0
    return float(_beta_dist.ppf(conf, k + 1, n - k))


def _ub_report(hits, n):
    if hits == 0:
        hi = _cp_upper_95_one_sided(0, n)
        return "0/%d, UB %.0f%%" % (n, hi * 100)
    return "%d/%d" % (hits, n)


def run_part_d(dec, log) -> dict:
    log("--- Part D (non-gating) ---")

    d1_hits = _score_multi(dec, D1_SIGNALS, 1, N_TRIALS, log, "D1")
    d1_report = {s: _ub_report(h, N_TRIALS) for s, h in d1_hits.items()}

    pair1 = [
        _q_signal("V1", "CQ Q2AAA FN20", D1_BASE_HZ),
        _q_signal("V2", "Q2AAA Q2BBB -10", D1_BASE_HZ + 8.0),
    ]
    pair2 = [
        _q_signal("V1", "CQ Q2AAA FN20", D1_BASE_HZ),
        _q_signal("V3", "Q2BBB Q2AAA R-08", D1_BASE_HZ + 11.0),
    ]
    d2_pair1_hits = _score_multi(dec, pair1, 2, N_TRIALS, log, "D2 pair1(0/+8)")
    d2_pair2_hits = _score_multi(dec, pair2, 3, N_TRIALS, log, "D2 pair2(0/+11)")

    d3_hits = _score_multi(dec, D3_SIGNALS, 4, N_TRIALS, log, "D3")
    d3_report = {s: _ub_report(h, N_TRIALS) for s, h in d3_hits.items()}

    d1_r = {s: h / N_TRIALS for s, h in d1_hits.items()}
    d3_r = {s: h / N_TRIALS for s, h in d3_hits.items()}
    d1_mean_r = sum(d1_r.values()) / len(d1_r)
    d3_mean_r = sum(d3_r.values()) / len(d3_r)
    d2_all_r = list(d2_pair1_hits.values()) + list(d2_pair2_hits.values())
    d2_mean_r = sum(h / N_TRIALS for h in d2_all_r) / len(d2_all_r)

    if d2_mean_r < 0.90:
        reading = "D2<0.90: harness invalid for this question -- Part D stopped, Parts A-C (i.e. ROW0/sweep) unaffected"
    elif d1_mean_r < 0.10 and d3_mean_r >= 0.90:
        reading = "density, not count: P2 belongs to the near-neighbour family"
    elif d1_mean_r < 0.10 and d3_mean_r < 0.10:
        reading = "count, not density: contradicts S8 (12 simultaneous at 91.67%) -- ESCALATE, do not interpret Parts A-C until resolved"
    elif d1_mean_r >= 0.10:
        reading = "harness does not reproduce P2's zero -- ESCALATE"
    else:
        reading = "ambiguous -- ESCALATE"

    return {
        "d1_hits": d1_hits, "d1_report": d1_report, "d1_mean_r": d1_mean_r,
        "d2_pair1_hits": d2_pair1_hits, "d2_pair2_hits": d2_pair2_hits, "d2_mean_r": d2_mean_r,
        "d3_hits": d3_hits, "d3_report": d3_report, "d3_mean_r": d3_mean_r,
        "reading": reading,
    }


# ── Orchestration ────────────────────────────────────────────────────────
def run_pipeline_once(dec, log) -> dict:
    out = {}
    row0c_result = row0c(dec, log)
    out["0c"] = row0c_result
    if not row0c_result["pass"]:
        out["stopped_at"] = "0c"
        return out

    l_star = row0c_result["l_star"]
    row0d_result = row0d(dec, l_star, log)
    out["0d"] = row0d_result
    if not row0d_result["pass"]:
        out["stopped_at"] = "0d"
        return out

    row0e_result = row0e(dec, log)
    out["0e"] = row0e_result
    if not row0e_result["pass"]:
        out["stopped_at"] = "0e"
        return out

    sweep = run_sweep(dec, l_star, log)
    out["sweep"] = sweep
    out["reading"] = evaluate_reading_rows(sweep)
    out["part_d"] = run_part_d(dec, log)
    out["stopped_at"] = None
    return out


def _strip_nondeterministic(d):
    """Nothing in this module's returned dicts carries a wall-clock value --
    timestamps are only ever logged via `log()`, never placed in the returned
    structures -- so no stripping is needed. Kept as an explicit no-op for
    parity with run_all.py's own documented guarantee (HK-022 auditability)."""
    return d


def main():
    args = sys.argv[1:]
    determinism_check = "--determinism-check" in args
    force = "--force" in args

    def log(msg):
        print("[%s] %s" % (_log_ts(), msg), flush=True)

    os.makedirs(RESULTS_DIR, exist_ok=True)

    log("ROW 0a")
    ok0a = row0a(log)
    if not ok0a:
        result = {"0a": ok0a, "stopped_at": "0a"}
        with open(os.path.join(RESULTS_DIR, "nbr-a-results.json"), "w") as fh:
            json.dump(result, fh, sort_keys=True, indent=2)
        log("STOP at ROW 0a. Wrote nbr-a-results.json")
        sys.exit(1)

    if determinism_check:
        dec = DC.load_decoder()
        log("=" * 78)
        log("RUN 1 of 2 (ROW 0b determinism check)")
        log("=" * 78)
        r1 = run_pipeline_once(dec, log)
        log("=" * 78)
        log("RUN 2 of 2 (ROW 0b determinism check)")
        log("=" * 78)
        r2 = run_pipeline_once(dec, log)

        j1 = json.dumps(_strip_nondeterministic(r1), sort_keys=True, indent=2)
        j2 = json.dumps(_strip_nondeterministic(r2), sort_keys=True, indent=2)
        with open(os.path.join(RESULTS_DIR, "_nbr_a_determinism_run1.json"), "w") as fh:
            fh.write(j1)
        with open(os.path.join(RESULTS_DIR, "_nbr_a_determinism_run2.json"), "w") as fh:
            fh.write(j2)
        identical = (j1 == j2)
        log("ROW 0b: two full runs byte-identical: %s" % identical)
        sys.exit(0 if identical else 1)

    dec = DC.load_decoder()
    log("0a=PASS, 0b already validated separately via --determinism-check")
    result = {"0a": True, "run_started_utc": _log_ts()}
    result.update(run_pipeline_once(dec, log))
    result["dll_sha256"] = DC.PINNED_DLL_SHA256
    result["dll_shim_version"] = DC.PINNED_SHIM_VERSION
    result["run_finished_utc"] = _log_ts()

    out_path = os.path.join(RESULTS_DIR, "nbr-a-results.json")
    if os.path.exists(out_path) and not force:
        raise SystemExit("refusing to overwrite existing %s without --force" % out_path)
    with open(out_path, "w") as fh:
        json.dump(result, fh, sort_keys=True, indent=2)
    log("Wrote %s" % out_path)


if __name__ == "__main__":
    main()
