#!/usr/bin/env python3
"""B2 Phase 0 -- ROW 0d, ber_grid measurement harness.

Deliberately NOT run_stage2.measure_stage2_row copied+trimmed: this is a clean re-write
that drops the refiner call entirely. Route B2's own spec (2026-08-19-1850 Sec.0.3/Sec.1)
is explicit that Phase 1 forms coherent LLRs AT THE EXISTING GRID POSITION, with "no
dependence on ft8_refine_candidate()'s position estimate" -- limb 1 (the refiner) is dead
three times over (M4/N1/Stage2) and Phase 1 must not import that dependency even
diagnostically. This harness therefore only ever calls `ft8_extract_llrs_at` (the
existing, already-validated grid export) -- never `ft8_refine_candidate`.

This IS the harness Phase 1 will extend: once `ft8_coherent_llr_at()` exists, the same
per-row loop gains a second extraction call (coherent, at the SAME (freq_idx, time_idx)
per the spec's own ROW 0e candidate-identity requirement) and reports ber_coh alongside
ber_grid. Phase 0's job is to prove the ber_grid half is correct BEFORE that second call
is added, against the one number already on the board for this exact population at this
exact offset: Stage 2's own median_ber_grid = 31.03% (population.py's
STAGE2_MEDIAN_BER_GRID, full precision 0.3103448275862069).

n_err (int, 0-174) is reported alongside ber_grid (float) because Phase 1's primary
statistic f_net thresholds on n_err <= 19 / > 19 bits (spec Sec.3, "Mechanical
definitions ... correctable <=> n_err <= 19"), not on the float BER directly.
"""
from __future__ import annotations

import os
import statistics as st
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "cycleframer-alignment-replay"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n1-extract-llrs-at-position"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "p-live-population"))

from extract_llrs_ctypes import ExtractLLRs, FTX_LDPC_N, hard_decision_ber  # noqa: E402
from run_stage1 import WavCache  # noqa: E402 -- reused verbatim (HK-018), not reimplemented


def measure_ber_grid_row(ex: ExtractLLRs, wav_cache: WavCache, row: dict, offset: float) -> dict:
    """row: {ts, message, anchor_freq_hz, anchor_dt, corpus} from
    plive_population.build_p_live_population(). Returns a result dict (message text
    never included, NFR-021) or a {"reason": ...} drop record, matching run_stage2's
    own drop-reason vocabulary so the two harnesses' drop tables are directly
    comparable."""
    try:
        pcm = wav_cache.get(row["ts"])
    except FileNotFoundError:
        return {"reason": "no_wav"}

    freq_int = round(row["anchor_freq_hz"])  # WSJT-X freq is already int Hz (no-op)
    corrected_dt = float(row["anchor_dt"]) + offset

    true_bits = ex.true_codeword(row["message"])
    if true_bits is None:
        return {"reason": "no_true_codeword"}

    rc, llr_grid = ex.extract_at(pcm, float(freq_int), corrected_dt)
    if rc != 0 or llr_grid is None:
        return {"reason": "grid_extract_rc_%d" % rc}

    ber_grid = hard_decision_ber(llr_grid, true_bits)
    n_err_grid = int(round(ber_grid * FTX_LDPC_N))  # ber_grid is an exact k/174 by construction

    return {
        "ts": row["ts"],
        "corpus": row["corpus"],
        "ber_grid": ber_grid,
        "n_err_grid": n_err_grid,
        "anchor_freq_hz": freq_int,
        "corrected_dt": corrected_dt,
    }


def run_population(ex: ExtractLLRs, wav_dir: str, population: list[dict], offset: float, log) -> dict:
    wav_cache = WavCache(wav_dir)
    t0 = time.time()
    rows: list[dict] = []
    reasons: dict[str, int] = {}
    for i, row in enumerate(population):
        r = measure_ber_grid_row(ex, wav_cache, row, offset)
        if "reason" in r:
            reasons[r["reason"]] = reasons.get(r["reason"], 0) + 1
            continue
        rows.append(r)
        if (i + 1) % 3000 == 0:
            log("  ... %d/%d processed (%d measured, %.1fs elapsed)"
                % (i + 1, len(population), len(rows), time.time() - t0))
    elapsed = time.time() - t0
    n_clusters_measured = len({r["ts"] for r in rows})
    log("  measured %d/%d rows (%.1fs). n_clusters_measured=%d. drop_reasons=%s"
        % (len(rows), len(population), elapsed, n_clusters_measured, reasons))
    return {
        "n_measured": len(rows), "n_clusters_measured": n_clusters_measured,
        "drop_reasons": reasons, "elapsed_s": elapsed, "rows": rows,
    }


def median_ber_grid(rows: list[dict]) -> float:
    return float(st.median(r["ber_grid"] for r in rows))
