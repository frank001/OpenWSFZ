#!/usr/bin/env python3
"""C-ASYM-A -- is D-001 a decoder deficit, or one arm of a two-sided disagreement?

Spec: qa/rr-study/2026-08-23-0959-architect-to-qa-spec-c-asym-a-decode-set-asymmetry.md
Parts A, B, D only (re-analysis of the corpus already on disk). Part C (the S8HN
synthetic run) is a separate live-capture harness, not this script.

Population: artefacts/20260803_live_run_1713/ (owsfz + wsjt-x ALL.TXT), decisive epoch
ts >= 260803_185914, exactly as the 2026-08-05 scouting pass and the spec's Sec.2 require
(HK-018 -- reused verbatim, not re-derived). Matching convention: distinct (ts, message)
with bracketed callsign tokens (resolved or not) collapsed to a canonical <HASH> marker,
via callsign_recurrence_proxy.normalise_for_match(), imported unmodified.

Unit of independence is the cycle (ts), never the decode (HK-021(i)). Every CI in this
script is a cluster bootstrap over ts, 2000 draws, seed 20260823, sharing one master
cycle index (the union of both legs' epoch ts's) across Parts A/B/D so "the same 2000
draws" has one consistent meaning throughout this run.

NFR-021: Parts A/B/D read live ALL.TXT with real off-air callsigns. No message text and
no callsign is ever printed, logged, or written to any file. Every identity Part B
extracts is SHA-256-hashed (truncated) at first use via callsign_recurrence_proxy._anon,
and even the hash is never persisted past this process -- only counts/fractions/CIs are
written to the output JSON. Reuses callsign_recurrence_proxy.py's extractor and hashing
discipline verbatim (spec Sec.4.2) rather than re-deriving a second one.

ROW 0e (mechanical determinism): main() runs the whole computation twice from the same
seed and byte-diffs the JSON, exactly as C-GAP-D does.

ASCII-only stdout (HK-009).
"""
from __future__ import annotations

import io
import json
import os
import random
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="ascii", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
RR_STUDY = os.path.dirname(HERE)
sys.path.insert(0, RR_STUDY)

from harness.common import parse_all_txt  # noqa: E402
from callsign_recurrence_proxy import (  # noqa: E402 -- reused unmodified, HK-018/spec Sec.4.2
    extract_identities,
    normalise_for_match,
    _anon,
)

REPO_ROOT = os.path.dirname(os.path.dirname(RR_STUDY))  # .../qa/rr-study -> .../qa -> repo root
CORPUS = os.path.join(REPO_ROOT, "artefacts", "20260803_live_run_1713")
EPOCH_START = datetime(2026, 8, 3, 18, 59, 14, tzinfo=timezone.utc)  # ts >= 260803_185914, verbatim (Sec.2)

SEED = 20260823
N_BOOT = 2000

# ROW 0 bars (Sec.3)
ROW0C_LO, ROW0C_HI = 0.10, 0.90
ROW0D_MIN_CYCLES = 500

# Gate bars (Sec.5)
GATE_A_SYM_BAR = 0.50
GATE_A_DOMINANCE_BAR = 0.65
GATE_B_BAR = 0.10

# Gate D bar (Sec.6)
GATE_D_BAR = 0.10


def log(msg):
    print(msg)


# ── population load ─────────────────────────────────────────────────────────────────────

def load_epoch_records():
    owsfz_path = os.path.join(CORPUS, "owsfz", "ALL.TXT")
    wsjtx_path = os.path.join(CORPUS, "wsjt-x", "ALL.TXT")
    owsfz_all, owsfz_skipped = parse_all_txt(owsfz_path)
    wsjtx_all, wsjtx_skipped = parse_all_txt(wsjtx_path)
    ours = [r for r in owsfz_all if r.utc >= EPOCH_START]
    theirs = [r for r in wsjtx_all if r.utc >= EPOCH_START]
    log("parsed: owsfz %d (%d skipped), wsjt-x %d (%d skipped)"
        % (len(owsfz_all), owsfz_skipped, len(wsjtx_all), wsjtx_skipped))
    log("epoch-filtered (ts >= %s): owsfz %d rows, wsjt-x %d rows"
        % (EPOCH_START.isoformat(), len(ours), len(theirs)))
    return ours, theirs


def rec_key(r):
    return (r.utc, normalise_for_match(r.message))


# ── ROW 0 ────────────────────────────────────────────────────────────────────────────────

def row0_checks(ours, theirs):
    ours_keys_list = [rec_key(r) for r in ours]
    theirs_keys_list = [rec_key(r) for r in theirs]
    ours_keys = set(ours_keys_list)
    theirs_keys = set(theirs_keys_list)

    both = ours_keys & theirs_keys
    ours_only = ours_keys - theirs_keys
    theirs_only = theirs_keys - ours_keys
    union = ours_keys | theirs_keys

    # 0a -- internal join consistency (independent recount: classify every distinct key
    # by membership test, then compare the tally against the set-arithmetic totals).
    ours_only_tally = sum(1 for k in ours_keys if k not in theirs_keys)
    both_tally_via_ours = sum(1 for k in ours_keys if k in theirs_keys)
    theirs_only_tally = sum(1 for k in theirs_keys if k not in ours_keys)
    both_tally_via_theirs = sum(1 for k in theirs_keys if k in ours_keys)
    row0a_pass = (
        both_tally_via_ours + ours_only_tally == len(ours_keys)
        and both_tally_via_theirs + theirs_only_tally == len(theirs_keys)
        and both_tally_via_ours == len(both)
        and both_tally_via_theirs == len(both)
    )

    # 0b -- duplicate emission: distinct(ts,message) == rows, each leg, epoch population.
    row0b_ours = {"rows": len(ours), "distinct": len(set(ours_keys_list))}
    row0b_theirs = {"rows": len(theirs), "distinct": len(set(theirs_keys_list))}
    row0b_pass = row0b_ours["rows"] == row0b_ours["distinct"] and row0b_theirs["rows"] == row0b_theirs["distinct"]

    # 0c -- two-sided join sanity.
    both_over_union = (len(both) / len(union)) if union else float("nan")
    row0c_pass = ROW0C_LO <= both_over_union <= ROW0C_HI

    # 0d -- cluster floor: distinct ts across the union of both legs' epoch records.
    all_ts = set(r.utc for r in ours) | set(r.utc for r in theirs)
    row0d_pass = len(all_ts) >= ROW0D_MIN_CYCLES

    result = {
        "0a": {"pass": row0a_pass, "both": len(both), "ours_only": len(ours_only),
               "theirs_only": len(theirs_only), "total_ours": len(ours_keys),
               "total_theirs": len(theirs_keys)},
        "0b": {"pass": row0b_pass, "ours": row0b_ours, "theirs": row0b_theirs},
        "0c": {"pass": row0c_pass, "both_over_union": both_over_union,
               "bar_lo": ROW0C_LO, "bar_hi": ROW0C_HI},
        "0d": {"pass": row0d_pass, "n_cycles": len(all_ts), "bar": ROW0D_MIN_CYCLES},
    }
    result["void"] = not (row0a_pass and row0b_pass and row0c_pass and row0d_pass)
    populations = {
        "both": both, "ours_only": ours_only, "theirs_only": theirs_only, "all_ts": all_ts,
    }
    return result, populations


# ── shared cluster index (HK-021(i)) ────────────────────────────────────────────────────

def build_cycle_index(all_ts):
    cycles = sorted(all_ts)  # sort at construction -- hash-randomised set iteration note
    cyc_index = {ts: i for i, ts in enumerate(cycles)}
    return cycles, cyc_index


def draw_mult(rng, n_cycles):
    """One cluster-bootstrap draw's per-cycle multiplicity vector. Same index-level
    construction as C-GAP-D's draw_mult (algorithmically identical to resampling whole
    cycles with replacement)."""
    idx = rng.choices(range(n_cycles), k=n_cycles)
    return np.bincount(idx, minlength=n_cycles).astype(np.float64)


def percentile(sorted_vals, p):
    """Nearest-rank percentile -- same convention as C-GAP-D's percentile()."""
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


# ── Part A -- pooled asymmetry A ────────────────────────────────────────────────────────

def part_a(ours, theirs, ours_only, theirs_only, cyc_index, n_cycles, rng):
    # sorted() at construction -- hash-randomised set iteration has silently broken
    # cross-invocation determinism on this project before; float-sum order depends on it.
    theirs_only_cyc = np.array([cyc_index[k[0]] for k in sorted(theirs_only)], dtype=np.int64)
    ours_only_cyc = np.array([cyc_index[k[0]] for k in sorted(ours_only)], dtype=np.int64)

    m_ours_pt = float(len(theirs_only))
    m_theirs_pt = float(len(ours_only))
    a_pt = m_ours_pt / (m_ours_pt + m_theirs_pt) if (m_ours_pt + m_theirs_pt) else float("nan")

    boot_a = []
    for _ in range(N_BOOT):
        mult = draw_mult(rng, n_cycles)
        m_ours_w = float(mult[theirs_only_cyc].sum()) if len(theirs_only_cyc) else 0.0
        m_theirs_w = float(mult[ours_only_cyc].sum()) if len(ours_only_cyc) else 0.0
        denom = m_ours_w + m_theirs_w
        boot_a.append(m_ours_w / denom if denom else float("nan"))
    ci_lo, ci_hi, hw, n_valid = boot_ci(boot_a)

    if ci_hi < GATE_A_SYM_BAR:
        row = "A1"
    elif ci_lo <= GATE_A_SYM_BAR <= ci_hi:
        row = "A2"
    elif GATE_A_SYM_BAR < ci_lo <= GATE_A_DOMINANCE_BAR:
        row = "A3"
    else:
        row = "A4"

    # Stratified view -- DESCRIPTIVE ONLY, never gated (Sec.4.1). Each half binned on its
    # own finder's SNR (a WSJT-X-only decode has only WSJT-X's SNR, an OpenWSFZ-only
    # decode has only ours). 5 dB bins.
    def bin5(snr):
        return 5 * int(np.floor(snr / 5.0))

    theirs_only_by_bin = defaultdict(int)
    for r in theirs:
        if rec_key(r) in theirs_only:
            theirs_only_by_bin[bin5(r.snr_db)] += 1
    ours_only_by_bin = defaultdict(int)
    for r in ours:
        if rec_key(r) in ours_only:
            ours_only_by_bin[bin5(r.snr_db)] += 1
    all_bins = sorted(set(theirs_only_by_bin) | set(ours_only_by_bin))
    stratified = []
    for b in all_bins:
        mo = theirs_only_by_bin.get(b, 0)
        mt = ours_only_by_bin.get(b, 0)
        a_bin = mo / (mo + mt) if (mo + mt) else float("nan")
        stratified.append({"bin_lo_db": b, "m_ours": mo, "m_theirs": mt, "a": a_bin})

    return {
        "m_ours": m_ours_pt, "m_theirs": m_theirs_pt, "a_point": a_pt,
        "ci_lo": ci_lo, "ci_hi": ci_hi, "halfwidth": hw, "n_boot_valid": n_valid,
        "row": row, "stratified_descriptive_only": stratified,
    }


# ── Part B -- singleton-fraction control ────────────────────────────────────────────────

def build_identity_pairs(records, key_filter, cyc_index):
    """identity(sha256[:16]) -> set(ts) for records whose rec_key is in key_filter.
    Returns (pair_ident_idx, pair_cyc_idx, n_ident, n_no_identity, n_records_used) as
    plain int arrays -- no identity string, hashed or otherwise, is ever returned or
    persisted past this function's local dict."""
    cycles_per_identity = defaultdict(set)
    n_no_identity = 0
    n_used = 0
    for r in records:
        if rec_key(r) not in key_filter:
            continue
        n_used += 1
        ids = extract_identities(r.message)
        if not ids:
            n_no_identity += 1
            continue
        for ident in ids:
            cycles_per_identity[_anon(ident)].add(r.utc)
    identities = sorted(cycles_per_identity.keys())  # sort at construction (determinism note)
    ident_index = {h: i for i, h in enumerate(identities)}
    pair_ident, pair_cyc = [], []
    for h, ts_set in cycles_per_identity.items():
        ii = ident_index[h]
        for ts in sorted(ts_set):
            pair_ident.append(ii)
            pair_cyc.append(cyc_index[ts])
    return (
        np.array(pair_ident, dtype=np.int64),
        np.array(pair_cyc, dtype=np.int64),
        len(identities),
        n_no_identity,
        n_used,
    )


def singleton_frac_point(pair_ident, n_ident):
    if n_ident == 0:
        return float("nan"), 0
    counts = np.bincount(pair_ident, minlength=n_ident)
    n_present = int((counts > 0).sum())
    n_single = int((counts == 1).sum())
    return (n_single / n_present if n_present else float("nan")), n_present


def singleton_frac_boot(pair_ident, pair_cyc, n_ident, mult):
    """NAIVE multiplicity-weighted cluster bootstrap, literally 'resample whole cycles
    with replacement, recount.' Kept for disclosure -- see part_b()'s docstring note on
    why this is NOT used for the gate: when a real cycle is drawn k>1 times, an identity
    that appeared in it mechanically gets recurrence count k in that replicate, which
    manufactures non-singletons out of true singletons at a rate having nothing to do
    with sampling uncertainty. This is the same pathology documented for bootstrapping
    Chao-type singleton-based richness estimators."""
    if n_ident == 0 or len(pair_ident) == 0:
        return float("nan")
    w = mult[pair_cyc]
    counts = np.bincount(pair_ident, weights=w, minlength=n_ident)
    present = counts > 0
    n_present = int(present.sum())
    if n_present == 0:
        return float("nan")
    n_single = int(np.isclose(counts, 1.0).sum())
    return n_single / n_present


def singleton_frac_boot_presence(pair_ident, pair_cyc, n_ident, mult):
    """PRESENCE (hit/miss) cluster bootstrap -- the correction. An identity's recurrence
    count in a replicate is the number of its DISTINCT original cycles drawn at least
    once (mult>0), not the multiplicity-weighted sum. This is the standard fix for
    bootstrapping recurrence/richness statistics under cluster resampling: what varies
    across replicates is WHICH of the real cycles got represented, not how many extra
    copies a repeat draw contributes -- a duplicate draw of the same real 15 s window
    does not create a second physically-distinct occasion on which the station could
    have been heard again."""
    if n_ident == 0 or len(pair_ident) == 0:
        return float("nan")
    hit = (mult[pair_cyc] > 0).astype(np.float64)
    counts = np.bincount(pair_ident, weights=hit, minlength=n_ident)
    present = counts > 0
    n_present = int(present.sum())
    if n_present == 0:
        return float("nan")
    n_single = int(np.isclose(counts, 1.0).sum())
    return n_single / n_present


def part_b(ours, theirs, both, ours_only, theirs_only, cyc_index, n_cycles, rng):
    # S_both uses OpenWSFZ-side message text for matched decodes, matching Task 4's
    # existing convention (its "matched" population is always drawn from owsfz_recs).
    pi_both, pc_both, ni_both, nnid_both, nused_both = build_identity_pairs(ours, both, cyc_index)
    pi_ours, pc_ours, ni_ours, nnid_ours, nused_ours = build_identity_pairs(ours, ours_only, cyc_index)
    pi_theirs, pc_theirs, ni_theirs, nnid_theirs, nused_theirs = build_identity_pairs(theirs, theirs_only, cyc_index)

    s_both_pt, np_both = singleton_frac_point(pi_both, ni_both)
    s_ours_pt, np_ours = singleton_frac_point(pi_ours, ni_ours)
    s_theirs_pt, np_theirs = singleton_frac_point(pi_theirs, ni_theirs)
    delta_s_pt = s_ours_pt - s_theirs_pt

    # Two bootstrap constructions, drawn from ONE shared stream of mult vectors so both
    # are computed against literally the same 2000 resamples (not two independent RNG
    # calls). See singleton_frac_boot / singleton_frac_boot_presence docstrings.
    boot_delta_naive, boot_delta_presence = [], []
    for _ in range(N_BOOT):
        mult = draw_mult(rng, n_cycles)
        s_ours_n = singleton_frac_boot(pi_ours, pc_ours, ni_ours, mult)
        s_theirs_n = singleton_frac_boot(pi_theirs, pc_theirs, ni_theirs, mult)
        boot_delta_naive.append(s_ours_n - s_theirs_n)
        s_ours_p = singleton_frac_boot_presence(pi_ours, pc_ours, ni_ours, mult)
        s_theirs_p = singleton_frac_boot_presence(pi_theirs, pc_theirs, ni_theirs, mult)
        boot_delta_presence.append(s_ours_p - s_theirs_p)

    n_ci_lo, n_ci_hi, n_hw, n_valid_naive = boot_ci(boot_delta_naive)
    p_ci_lo, p_ci_hi, p_hw, n_valid_presence = boot_ci(boot_delta_presence)

    # GATE READS ON THE PRESENCE-CORRECTED CI. The naive multiplicity-weighted CI is
    # disclosed alongside it but NOT used to determine the row: its own point estimate
    # (delta_s_pt) falls entirely outside its 95% interval -- a mechanical tell (akin to
    # HK-021(n): ask which way a broken instrument would move this number) that the
    # naive construction is not measuring sampling uncertainty here, it is measuring an
    # artefact of with-replacement duplication colliding with an exactly-one-count
    # statistic. See docstrings on both boot functions.
    naive_point_outside_own_ci = not (n_ci_lo <= delta_s_pt <= n_ci_hi)

    def classify(ci_lo, ci_hi):
        if ci_hi < GATE_B_BAR:
            return "B1"
        if ci_lo <= GATE_B_BAR <= ci_hi:
            return "B2"
        return "B3"

    row = classify(p_ci_lo, p_ci_hi)
    row_naive_uncorrected = classify(n_ci_lo, n_ci_hi)

    return {
        "s_both": s_both_pt, "s_ours": s_ours_pt, "s_theirs": s_theirs_pt,
        "delta_s_point": delta_s_pt,
        "ci_lo": p_ci_lo, "ci_hi": p_ci_hi, "halfwidth": p_hw, "n_boot_valid": n_valid_presence,
        "row": row,
        "bootstrap_construction_used_for_row": "presence (hit/miss on distinct original cycles)",
        "naive_multiplicity_boot": {
            "ci_lo": n_ci_lo, "ci_hi": n_ci_hi, "halfwidth": n_hw, "n_boot_valid": n_valid_naive,
            "row_if_used": row_naive_uncorrected,
            "point_estimate_outside_own_ci": naive_point_outside_own_ci,
            "disclosure": "NOT used for the gate -- see singleton_frac_boot() docstring.",
        },
        "n_identities": {"both": ni_both, "ours_only": ni_ours, "theirs_only": ni_theirs},
        "n_present_at_point": {"both": np_both, "ours_only": np_ours, "theirs_only": np_theirs},
        "n_no_extractable_identity": {"both": nnid_both, "ours_only": nnid_ours, "theirs_only": nnid_theirs},
        "n_records_used": {"both": nused_both, "ours_only": nused_ours, "theirs_only": nused_theirs},
    }


# ── Part D -- scope check ───────────────────────────────────────────────────────────────

def _sorted_ref(values_ref, cyc_ref):
    """Precompute the value-sort order once; only the WEIGHTS change per bootstrap draw."""
    order = np.argsort(values_ref, kind="mergesort")
    return values_ref[order], cyc_ref[order]


def _weighted_percentile_vec(sorted_vals, sorted_cyc, mult, p):
    """Nearest-rank percentile on cumulative weighted mass -- vectorised (no per-draw
    Python-level loop over rows; `values_ref`'s sort order is fixed, only `mult` varies)."""
    w = mult[sorted_cyc]
    cumw = np.cumsum(w)
    total = cumw[-1] if len(cumw) else 0.0
    if total <= 0:
        return float("nan")
    idx = int(np.searchsorted(cumw, p * total, side="left"))
    idx = min(idx, len(sorted_vals) - 1)
    return float(sorted_vals[idx])


def part_d(ours, theirs, theirs_only, cyc_index, n_cycles, rng):
    ours_freq = np.array([r.freq_hz for r in ours], dtype=np.float64)
    ours_dt = np.array([r.dt_s for r in ours], dtype=np.float64)
    ours_cyc = np.array([cyc_index[r.utc] for r in ours], dtype=np.int64)

    theirs_only_recs = [r for r in theirs if rec_key(r) in theirs_only]
    to_freq = np.array([r.freq_hz for r in theirs_only_recs], dtype=np.float64)
    to_dt = np.array([r.dt_s for r in theirs_only_recs], dtype=np.float64)
    to_cyc = np.array([cyc_index[r.utc] for r in theirs_only_recs], dtype=np.int64)

    freq_sorted_vals, freq_sorted_cyc = _sorted_ref(ours_freq, ours_cyc)
    dt_sorted_vals, dt_sorted_cyc = _sorted_ref(ours_dt, ours_cyc)

    def band_and_out(sorted_vals, sorted_cyc, values_test, cyc_test, mult):
        lo = _weighted_percentile_vec(sorted_vals, sorted_cyc, mult, 0.01)
        hi = _weighted_percentile_vec(sorted_vals, sorted_cyc, mult, 0.99)
        w_test = mult[cyc_test]
        out_mask = (values_test < lo) | (values_test > hi)
        w_out = float(w_test[out_mask].sum())
        w_total = float(w_test.sum())
        frac_out = (w_out / w_total) if w_total > 0 else float("nan")
        return lo, hi, frac_out

    unit_mult = np.ones(n_cycles, dtype=np.float64)
    f_lo_pt, f_hi_pt, f_out_pt = band_and_out(freq_sorted_vals, freq_sorted_cyc, to_freq, to_cyc, unit_mult)
    t_lo_pt, t_hi_pt, t_out_pt = band_and_out(dt_sorted_vals, dt_sorted_cyc, to_dt, to_cyc, unit_mult)

    boot_f_out, boot_t_out = [], []
    for _ in range(N_BOOT):
        mult = draw_mult(rng, n_cycles)
        _, _, f_out = band_and_out(freq_sorted_vals, freq_sorted_cyc, to_freq, to_cyc, mult)
        _, _, t_out = band_and_out(dt_sorted_vals, dt_sorted_cyc, to_dt, to_cyc, mult)
        boot_f_out.append(f_out)
        boot_t_out.append(t_out)
    f_ci_lo, f_ci_hi, f_hw, f_nv = boot_ci(boot_f_out)
    t_ci_lo, t_ci_hi, t_hw, t_nv = boot_ci(boot_t_out)

    if f_out_pt >= GATE_D_BAR or t_out_pt >= GATE_D_BAR:
        row = "D1"
    else:
        row = "D2"

    return {
        "band_ours_freq_hz": {"p1": f_lo_pt, "p99": f_hi_pt},
        "band_ours_dt_s": {"p1": t_lo_pt, "p99": t_hi_pt},
        "f_out": f_out_pt, "f_out_ci_lo": f_ci_lo, "f_out_ci_hi": f_ci_hi, "f_out_halfwidth": f_hw,
        "t_out": t_out_pt, "t_out_ci_lo": t_ci_lo, "t_out_ci_hi": t_ci_hi, "t_out_halfwidth": t_hw,
        "row": row,
        "n_theirs_only": len(theirs_only_recs),
        "freq_quantum_note": "WSJT-X reports integer Hz; our lattice is 3.125 Hz -- both "
                              "negligible against a [P1,P99] span of hundreds of Hz (HK-021(o)).",
    }


# ── top-level ────────────────────────────────────────────────────────────────────────────

def compute_all(seed):
    ours, theirs = load_epoch_records()
    row0, pops = row0_checks(ours, theirs)

    result = {"row0": row0}
    if row0["void"]:
        result["gate_b"] = None
        result["gate_a"] = None
        result["gate_d"] = None
        result["reading_order_note"] = "ROW 0 VOID -- no gate evaluated, per spec Sec.3/Sec.5."
        return result

    cycles, cyc_index = build_cycle_index(pops["all_ts"])
    n_cycles = len(cycles)
    rng = random.Random(seed)

    # Reading order: B first, then A, then D is independent of both (spec Sec.5 "Reading
    # order" covers A/B/C; D is a separate section evaluated on its own merits).
    gate_b = part_b(ours, theirs, pops["both"], pops["ours_only"], pops["theirs_only"],
                     cyc_index, n_cycles, rng)
    gate_a = part_a(ours, theirs, pops["ours_only"], pops["theirs_only"], cyc_index, n_cycles, rng)
    gate_d = part_d(ours, theirs, pops["theirs_only"], cyc_index, n_cycles, rng)

    result["gate_b"] = gate_b
    result["gate_a"] = gate_a
    result["gate_d"] = gate_d
    result["meta"] = {
        "seed": seed, "n_boot": N_BOOT, "n_cycles": n_cycles,
        "epoch_start": EPOCH_START.isoformat(),
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
    log("C-ASYM-A -- decode-set asymmetry (Parts A/B/D). Seed %d, N_BOOT %d." % (SEED, N_BOOT))
    log("corpus: %s" % CORPUS)

    log("\nRun 1 (ROW 0e determinism check, pass 1)...")
    run1 = compute_all(SEED)
    log("Run 1 done in %.1fs" % (time.time() - t0))

    t1 = time.time()
    log("\nRun 2 (ROW 0e determinism check, pass 2, independent RNG re-seed)...")
    run2 = compute_all(SEED)
    log("Run 2 done in %.1fs" % (time.time() - t1))

    j1 = json.dumps(to_jsonable(run1), sort_keys=True)
    j2 = json.dumps(to_jsonable(run2), sort_keys=True)
    row0e_pass = (j1 == j2)
    log("\nROW 0e (mechanical diff, not a claim): %s"
        % ("PASS -- byte-identical" if row0e_pass else "FAIL -- runs differ"))

    final = to_jsonable(run1)
    final["row0e"] = {"pass": row0e_pass}

    ts = time.strftime("%Y%m%d_%H%M%SZ", time.gmtime())
    out_dir = os.path.join(HERE, "results")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "%s-c_asym_a_report.json" % ts)  # N14: timestamp-derived, never clobbers
    with io.open(out_path, "w", encoding="utf-8") as fh:
        json.dump(final, fh, indent=2, sort_keys=True)
    log("\nWrote %s" % out_path)

    log("\n" + "=" * 90)
    if final["row0"]["void"]:
        log("ROW 0 VOID -- see JSON for which check(s) failed. No gate evaluated.")
        log("=" * 90)
        log("\nTotal wall time: %.1fs" % (time.time() - t0))
        return 1 if not row0e_pass else 2

    gb, ga, gd = final["gate_b"], final["gate_a"], final["gate_d"]
    log("GATE B: Delta_S=%.4f  presence-CI=[%.4f, %.4f] hw=%.4f -> ROW %s  "
        "(naive-CI=[%.4f, %.4f] would read %s, point outside own CI=%s)"
        % (gb["delta_s_point"], gb["ci_lo"], gb["ci_hi"], gb["halfwidth"], gb["row"],
           gb["naive_multiplicity_boot"]["ci_lo"], gb["naive_multiplicity_boot"]["ci_hi"],
           gb["naive_multiplicity_boot"]["row_if_used"],
           gb["naive_multiplicity_boot"]["point_estimate_outside_own_ci"]))
    log("GATE A: A=%.4f CI=[%.4f, %.4f] halfwidth=%.4f -> ROW %s"
        % (ga["a_point"], ga["ci_lo"], ga["ci_hi"], ga["halfwidth"], ga["row"]))
    log("GATE D: F_out=%.4f (CI [%.4f, %.4f])  T_out=%.4f (CI [%.4f, %.4f]) -> ROW %s"
        % (gd["f_out"], gd["f_out_ci_lo"], gd["f_out_ci_hi"],
           gd["t_out"], gd["t_out_ci_lo"], gd["t_out_ci_hi"], gd["row"]))
    log("=" * 90)
    log("\nTotal wall time: %.1fs" % (time.time() - t0))
    return 0 if row0e_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
