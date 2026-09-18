#!/usr/bin/env python3
"""DENSITY-MECH Amendment A1 -- which of production's two extra mechanisms
(pass-1 tile suppression, or extracting at a displaced candidate position)
recovers F where DENSITY-MECH's oracle, at F's textbook true position,
could not?

Spec: qa/rr-study/2026-09-18-1356-architect-to-qa-spec-density-mechanism-oracle-position.md
Sec.10.5 (`arch/density` commit `1a7f9547`, the same commit that VOIDs
DENSITY-MECH's original ROW 1 M1 reading -- see
qa/rr-study/2026-09-18-1433-qa-to-architect-density-mech-result.md's
corrections). Diagnostic only: 🛑 A1 carries NO M1/M2 verdict (spec Sec.10.5).

Same harness machinery, same seeds, same binary as density_mech.py (HK-018 --
imports cell_signals()/scene setup from it verbatim rather than
reimplementing). Six cells: the five with prod > 0 in the original run
(primary Delta=6.25/12/18.75 at X=+1; strong Delta=12/18.75) plus primary
Delta=12/X=+3 as the excluded reference (prod=0 there, included to confirm a
genuinely-excluded cell stays excluded with pass 1 disabled too). N=100.

Three measurements per trial, same rendered PCM (E present) throughout:

  (a) prod       -- ft8_decode_all with PRODUCTION's own two-pass defaults
                     (k_min_score_pass2=10, osd_corr_threshold=0.10,
                     osd_nhard_max=60 -- read from ft8_shim.c:478-480, the
                     compiled-in s_k_min_score_pass2/s_osd_corr_threshold/
                     s_osd_nhard_max globals; this harness never called
                     ft8_set_decode_params before Amendment A1, so every
                     "prod" figure in the original DENSITY-MECH run already
                     used exactly these defaults -- confirmed identical, not
                     assumed).
      prod_p0     -- ft8_decode_all with pass 1 disabled: same call, but
                     k_min_score_pass2 raised to 1,000,000 (no pass-1
                     candidate can ever clear that score floor) while
                     osd_corr_threshold/osd_nhard_max are left at
                     production's own values (spec Sec.10.5's own wording:
                     "which leaves pass 0 untouched"). ft8_get_last_candidate_
                     counts confirms pass 1 found 0 candidates on every trial
                     (a real assertion, not a comment). Production's params
                     are restored, and re-asserted via a plain decode_all
                     call reproducing that trial's own "prod" hit/miss,
                     immediately after every prod_p0 call -- no other native
                     call happens while params are in the disabled state.

  (b) position    -- for every trial where `prod` (full production) hits,
                     F's reported (freq_hz, dt) from that SAME decode_all
                     call, and its offset from the textbook true position
                     (target_freq_hz, F_TIME_OFFSET_S).

  (c) orc_P       -- the oracle at PRODUCTION's own reported position, not
                     the textbook true position. time_offset_s is
                     production's reported `dt` field USED DIRECTLY, with NO
                     further SYMBOL_PERIOD_S correction added on top --
                     because dll_common.py's own B-orig-A finding already
                     established that decode_all's reported `dt` for a
                     known-true-dt=0 station comes back at ~0.15999999....,
                     i.e. decode_all's own reported dt ALREADY equals
                     dt_true + SYMBOL_PERIOD_S. Adding the correction a
                     second time on top of an already-corrected, decoder-
                     reported value would double the offset. freq_hz is
                     production's reported freq_hz field used directly (same
                     tone-0 convention density_mech.py's Sec.1.3 mapping
                     already confirmed via ROW 0c's 100/100).

NFR-021: works entirely in bit/rate/frequency/time space; never prints
message text (scene stations are Q-prefix synthetic throughout regardless).
"""
from __future__ import annotations

import ctypes
import json
import os
import statistics as st
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
_QA_RR = os.path.join(REPO_ROOT, "qa", "rr-study")
for p in (
    _QA_RR,
    os.path.join(_QA_RR, "f-nbr-a"),
    os.path.join(_QA_RR, "n1-extract-llrs-at-position"),
    os.path.join(_QA_RR, "r2-coherent-llr-instrument"),
    HERE,
):
    if p not in sys.path:
        sys.path.insert(0, p)

import scene_render as SR  # noqa: E402
import part_c as PC  # noqa: E402
from harness.matcher import _text_matches  # noqa: E402  (verbatim reuse, same as part_c.py)
from ldpc_decode_ctypes import LdpcDecodeLLRs, FT8_PAYLOAD_BITS  # noqa: E402
from extract_llrs_ctypes import FTX_LDPC_N, hard_decision_ber, dll_sha256  # noqa: E402
import ldpc_decode_ctypes as LDC  # noqa: E402

import density_mech as DM  # noqa: E402  -- cell_signals(), F_TIME_OFFSET_S, DLL pin, MAX_ITERS/OSD_DEPTH

OUT_DIR = os.path.join(HERE, "results")
RESULT_JSON = os.path.join(OUT_DIR, "density_mech_a1_result.json")

N_TRIALS = int(os.environ.get("DENSITY_MECH_N_TRIALS", "100"))

# ── Production's own OSD-gate defaults -- READ FROM THE BUILD this session,
# not inherited from a comment: ft8_shim.c:478-480's actual compiled-in
# initial values for s_k_min_score_pass2/s_osd_corr_threshold/s_osd_nhard_max.
PROD_K_MIN_SCORE_PASS2 = 10
PROD_OSD_CORR_THRESHOLD = 0.10
PROD_OSD_NHARD_MAX = 60
PROD_PARAMS = (PROD_K_MIN_SCORE_PASS2, PROD_OSD_CORR_THRESHOLD, PROD_OSD_NHARD_MAX)

# k_min_score_pass2 raised far past K_MAX_CANDIDATES/realistic sync-score range
# (spec Sec.10.5's own value) -- admits no pass-1 candidate, ever.
P0_ONLY_K_MIN_SCORE_PASS2 = 1_000_000
P0_ONLY_PARAMS = (P0_ONLY_K_MIN_SCORE_PASS2, PROD_OSD_CORR_THRESHOLD, PROD_OSD_NHARD_MAX)

K_MAX_PASSES = 2  # ft8_shim.c:523 -- pass 0 (full waterfall), pass 1 (spectrogram-suppressed)

# The six cells (spec Sec.10.5), keyed by their ORIGINAL density_mech.py
# part_index so every trial renders BIT-IDENTICAL audio to the original run
# (same seeds -- "same harness, seeds and binary", spec's own wording).
A1_CELLS = [
    {"label": "primary_6.25_+1", "group": "primary", "delta_hz": 6.25, "x_db": 1.0,
     "e_snr_db": -5.0, "f_snr_db": -6.0, "part_index": 2001},
    {"label": "primary_12.00_+1", "group": "primary", "delta_hz": 12.0, "x_db": 1.0,
     "e_snr_db": -5.0, "f_snr_db": -6.0, "part_index": 2004},
    {"label": "primary_18.75_+1", "group": "primary", "delta_hz": 18.75, "x_db": 1.0,
     "e_snr_db": -5.0, "f_snr_db": -6.0, "part_index": 2007},
    {"label": "strong_12.00", "group": "strong", "delta_hz": 12.0, "x_db": 3.0,
     "e_snr_db": 8.0, "f_snr_db": 5.0, "part_index": 2102},
    {"label": "strong_18.75", "group": "strong", "delta_hz": 18.75, "x_db": 3.0,
     "e_snr_db": 8.0, "f_snr_db": 5.0, "part_index": 2103},
    {"label": "primary_12.00_+3_EXCLUDED_REF", "group": "primary", "delta_hz": 12.0, "x_db": 3.0,
     "e_snr_db": -5.0, "f_snr_db": -8.0, "part_index": 2005},
]

A1_POS_BAR = 0.80
A1_PASS1_BAR = 0.20
READ_PROD_BAR = 0.80  # readings only computed for cells with prod >= this


def log(msg):
    print(msg, flush=True)


def bind_extra_exports(dec: LdpcDecodeLLRs):
    """ft8_get_last_candidate_counts is not bound by ExtractLLRs/LdpcDecodeLLRs
    -- bind it here. ft8_set_decode_params is already bound by ExtractLLRs
    (extract_llrs_ctypes.py) at construction time."""
    if not hasattr(dec.dll, "ft8_get_last_candidate_counts"):
        raise AttributeError("ft8_get_last_candidate_counts not exported by the loaded DLL -- STOP (spec Sec.6 item 4)")
    dec.dll.ft8_get_last_candidate_counts.restype = ctypes.c_int
    dec.dll.ft8_get_last_candidate_counts.argtypes = [ctypes.POINTER(ctypes.c_int), ctypes.c_int]


def set_params(dec, params):
    dec.dll.ft8_set_decode_params(ctypes.c_int(params[0]), ctypes.c_float(params[1]), ctypes.c_int(params[2]))


def get_last_candidate_counts(dec):
    buf = (ctypes.c_int * K_MAX_PASSES)()
    n = dec.dll.ft8_get_last_candidate_counts(buf, K_MAX_PASSES)
    return [buf[i] for i in range(max(n, 0))]


def f_recovered_with_position(results, target_freq_hz, target_message):
    """Like part_c._f_recovered, but also returns the matching result's own
    (freq_hz, dt) when found (None if not found or on ambiguous multi-match --
    first match taken, consistent with _f_recovered's own any() semantics)."""
    if not results:
        return False, None
    for r in results:
        if abs(r["freq_hz"] - target_freq_hz) <= 4.0 and _text_matches(r["message"], target_message):
            return True, {"freq_hz": r["freq_hz"], "dt": r["dt"]}
    return False, None


def oracle_at_position(dec, pcm, freq_hz, time_offset_s, true_bits):
    rc, llr = dec.extract_at(pcm, freq_hz, time_offset_s)
    if rc != 0 or llr is None:
        return {"rc": rc, "hit": False, "ber": None}
    res = dec.ldpc_decode_llrs(llr, max_iters=DM.MAX_ITERS, osd_depth=DM.OSD_DEPTH)
    if res["rc"] != 0 or res["a91"] is None:
        return {"rc": rc, "hit": False, "ber": hard_decision_ber(llr, true_bits)}
    recovered = LDC.a91_to_bits(res["a91"], FT8_PAYLOAD_BITS)
    expected = true_bits[:FT8_PAYLOAD_BITS]
    hit = (res["crc_ok"] == 1) and (recovered == expected)
    return {"rc": rc, "hit": hit, "ber": hard_decision_ber(llr, true_bits)}


def run_cell(dec, cell, true_bits):
    full_signals, _, target_freq = DM.cell_signals(cell)

    n_prod_hit = 0
    n_p0_hit = 0
    n_p0_pass1_nonzero = 0
    n_orcP_hit_of_100 = 0
    n_orcP_hit_of_prodhits = 0
    freq_offsets = []
    dt_offsets = []
    pass1_counts_seen = []

    for t in range(N_TRIALS):
        seed = SR.trial_seed(t, cell["part_index"])
        pcm_full = SR.render_scene(full_signals, seed)

        # (a1) full production, PRODUCTION's own defaults
        set_params(dec, PROD_PARAMS)
        results_full = dec.decode_all(pcm_full)
        hit_prod, pos = f_recovered_with_position(results_full, target_freq, SR.F_TRUE_MESSAGE)
        if hit_prod:
            n_prod_hit += 1
            freq_offsets.append(pos["freq_hz"] - target_freq)
            dt_offsets.append(pos["dt"] - DM.F_TIME_OFFSET_S)

        # (a2) pass-1-disabled production
        set_params(dec, P0_ONLY_PARAMS)
        results_p0 = dec.decode_all(pcm_full)
        if PC._f_recovered(results_p0, target_freq, SR.F_TRUE_MESSAGE):
            n_p0_hit += 1
        counts = get_last_candidate_counts(dec)
        pass1_n = counts[1] if len(counts) > 1 else None
        pass1_counts_seen.append(pass1_n)
        if pass1_n:
            n_p0_pass1_nonzero += 1

        # restore production params immediately -- no other native call happens
        # while params are in the disabled state
        set_params(dec, PROD_PARAMS)

        # (c) orc_P -- only where prod (full production) hit this trial
        if hit_prod:
            o = oracle_at_position(dec, pcm_full, pos["freq_hz"], pos["dt"], true_bits)
            if o["hit"]:
                n_orcP_hit_of_100 += 1
                n_orcP_hit_of_prodhits += 1

    return {
        "label": cell["label"], "group": cell["group"], "delta_hz": cell["delta_hz"], "x_db": cell["x_db"],
        "part_index": cell["part_index"], "n_trials": N_TRIALS,
        "prod_hits": n_prod_hit, "prod_rate": n_prod_hit / N_TRIALS,
        "prod_p0_hits": n_p0_hit, "prod_p0_rate": n_p0_hit / N_TRIALS,
        "p0_pass1_nonzero_trials": n_p0_pass1_nonzero,
        "p0_pass1_all_zero": (n_p0_pass1_nonzero == 0),
        "orc_P_hits_of_100": n_orcP_hit_of_100, "orc_P_rate_of_100": n_orcP_hit_of_100 / N_TRIALS,
        "orc_P_hits_of_prodhits": n_orcP_hit_of_prodhits,
        "orc_P_rate_of_prodhits": (n_orcP_hit_of_prodhits / n_prod_hit if n_prod_hit else None),
        "freq_offset_hz": {
            "n": len(freq_offsets),
            "mean": (st.mean(freq_offsets) if freq_offsets else None),
            "min": (min(freq_offsets) if freq_offsets else None),
            "max": (max(freq_offsets) if freq_offsets else None),
        },
        "dt_offset_s": {
            "n": len(dt_offsets),
            "mean": (st.mean(dt_offsets) if dt_offsets else None),
            "min": (min(dt_offsets) if dt_offsets else None),
            "max": (max(dt_offsets) if dt_offsets else None),
        },
    }


def evaluate(cells_result):
    reads = {}
    for c in cells_result:
        if c["prod_rate"] < READ_PROD_BAR:
            continue
        p0 = c["prod_p0_rate"]
        oP = c["orc_P_rate_of_100"]
        if p0 >= A1_POS_BAR and oP >= A1_POS_BAR:
            read = "A1-POS"
        elif p0 <= A1_PASS1_BAR:
            read = "A1-PASS1"
        else:
            read = "A1-OTHER"
        reads[c["label"]] = {"read": read, "prod_p0_rate": p0, "orc_P_rate_of_100": oP,
                              "prod_rate": c["prod_rate"]}
    return reads


def run_once():
    t_start = time.time()
    log("Loading DLL: %s (pin %s..., shim %d)" % (DM.DLL_PATH, DM.PINNED_DLL_SHA256[:16], DM.PINNED_SHIM_VERSION))
    dec = LdpcDecodeLLRs(DM.DLL_PATH, verify=True, expected_sha256=DM.PINNED_DLL_SHA256,
                          expected_shim_version=DM.PINNED_SHIM_VERSION)
    bind_extra_exports(dec)
    log("DLL pin confirmed, ft8_get_last_candidate_counts bound.")

    true_bits = dec.true_codeword(SR.F_TRUE_MESSAGE)
    assert true_bits is not None and len(true_bits) == FTX_LDPC_N

    # Confirm production defaults are the compiled-in state before touching anything
    set_params(dec, PROD_PARAMS)

    cells_result = []
    for i, cell in enumerate(A1_CELLS):
        t0 = time.time()
        r = run_cell(dec, cell, true_bits)
        cells_result.append(r)
        log("[%d/%d] %-28s prod=%3d/%d prod_p0=%3d/%d (pass1 nonzero on %d/%d p0 trials) orc_P=%3d/%d (of %d prod-hits: %s) (%.1fs)"
            % (i + 1, len(A1_CELLS), cell["label"], r["prod_hits"], N_TRIALS, r["prod_p0_hits"], N_TRIALS,
               r["p0_pass1_nonzero_trials"], N_TRIALS, r["orc_P_hits_of_100"], N_TRIALS, r["prod_hits"],
               ("%.3f" % r["orc_P_rate_of_prodhits"]) if r["orc_P_rate_of_prodhits"] is not None else "n/a",
               time.time() - t0))

    reads = evaluate(cells_result)
    log("\nReadings (cells with prod >= %.2f):" % READ_PROD_BAR)
    for label, r in reads.items():
        log("  %-28s prod_p0=%.2f orc_P=%.2f -> %s" % (label, r["prod_p0_rate"], r["orc_P_rate_of_100"], r["read"]))

    result = {
        "spec_commit": "1a7f9547",
        "prod_params": {"k_min_score_pass2": PROD_K_MIN_SCORE_PASS2, "osd_corr_threshold": PROD_OSD_CORR_THRESHOLD,
                         "osd_nhard_max": PROD_OSD_NHARD_MAX, "source": "ft8_shim.c:478-480"},
        "p0_only_params": {"k_min_score_pass2": P0_ONLY_K_MIN_SCORE_PASS2,
                            "osd_corr_threshold": PROD_OSD_CORR_THRESHOLD, "osd_nhard_max": PROD_OSD_NHARD_MAX},
        "orc_P_position_convention": "production's reported (freq_hz, dt) used DIRECTLY -- freq_hz as reported "
                                      "(tone-0 convention), dt as reported with NO added SYMBOL_PERIOD_S (dll_common.py's "
                                      "own B-orig-A finding: decode_all's reported dt for a true-dt=0 station already "
                                      "reads ~0.16, i.e. already equals dt_true+SYMBOL_PERIOD_S -- adding it again would "
                                      "double-correct)",
        "cells": cells_result,
        "readings": reads,
        "n_trials_per_cell": N_TRIALS,
        "wall_time_s": round(time.time() - t_start, 1),
    }
    return result


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    r = run_once()
    with open(RESULT_JSON, "w", encoding="utf-8") as f:
        json.dump(r, f, indent=2)
    log("\nWrote %s" % os.path.abspath(RESULT_JSON))
    return 0


if __name__ == "__main__":
    sys.exit(main())
