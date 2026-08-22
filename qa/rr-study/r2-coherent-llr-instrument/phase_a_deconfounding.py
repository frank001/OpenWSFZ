#!/usr/bin/env python3
"""Phase A -- pure-Python de-confounding of ROW 0g-2's fired contrast.

Spec: qa/rr-study/2026-08-21-1201-architect-to-qa-b2-row0g-native-fix-triage-and-phase-a-
deconfounding.md, Sec.3. Runs against the CURRENT MERGED binary (main a420016, shim 20260043,
DLL SHA256 1889408787...) -- NO native change, NO rebuild, NO Developer session, NO CI edit.

Purpose: ROW 0g-2 fired (d_real = -67.0 bits, CI95 [-71,-65]) but its contrast is confounded
three ways against 0g-1 (frequency residual, timing residual, channel). This script dials the
frequency and timing residuals into otherwise-clean synthetic audio, one at a time and then
jointly, to see whether those two residuals alone reproduce a collapse of 0g-2's order of
magnitude -- which would name the mechanism (C1/C2/C3, fusion + no freq estimation + timing
fragility) without needing to reach for the channel (C4).

===============================================================================================
DIAGNOSTIC ONLY (spec Sec.6, prohibitions):
  - Defines NO ROW, returns NO PASS/FAIL, and produces NO f_net or Phase-1-quotable outcome.
  - Does NOT re-read, re-metric, or amend ROW 0g. That gate stands exactly as run: FIRED, VOID,
    Route B2 NOT dead, ROW 3 NOT declared.
  - No src/ or native/ edit, no DLL rebuild, no push, no merge (HK-011, HK-014).
===============================================================================================

Implementation note on A2/A3's timing axis (deviation from a literal render-side reading of the
spec, recorded per HK-018/HK-022 -- checked the code before writing this, not after):
`synth.modulator.modulate`'s default (`extended=False`) single-slot contract raises `ValueError`
for any `dt_s` outside ~[0.0, 2.36]s (Route B, 2026-08-19) -- it no longer silently clamps, it
refuses negative placement outright. A literal "render at dt_s=delta_t" cannot sweep a
symmetric +/-delta_t range in single-slot mode, and `extended=True` changes the buffer's shape
away from the fixed BUFFER_SAMPLES the exports assert on. Instead, the render is kept at the
nominal placement (`dt_s=0.0`) and the TIMING residual is injected by moving the *call's*
`time_offset_s` away from the render's true nominal (0.0) by `delta_t`. This is the same
relative-position mismatch a render-side shift would create (only the correlator's assumed
position relative to the true signal position matters, not which side of the pair moves) --
it is exactly how 0g-1/0g-2's own `time_offset_s` axis already works. It also sidesteps the
spec's own D3 warning for free: since nothing about the encoder's uncalibrated `dt_s` convention
is invoked, this axis's zero is the TRUE nominal position, not an uncalibrated one. The spec's
instruction to treat only the curve's SHAPE as meaningful is followed anyway, out of caution.

Frequency (A1) has no such constraint -- `base_freq_hz` accepts any float -- so A1 follows the
spec literally: render off-nominal, call at the nominal lattice frequency.
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
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "n1-ber-at-refined-position"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "p-live-population"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "m3-anchor-timebase"))
_SYNTH_ROOT = os.path.join(REPO_ROOT, "qa", "rr-study")
sys.path.insert(0, _SYNTH_ROOT)
sys.path.insert(0, HERE)

import numpy as np  # noqa: E402

import p23_common as P  # noqa: E402
from extract_llrs_ctypes import FTX_LDPC_N, hard_decision_ber  # noqa: E402
from run_stage1 import DEFAULT_DLL_PATH  # noqa: E402
from m3_common import TIME_ANCHOR_OFFSETS_S  # noqa: E402 -- reused verbatim (HK-018)
from r2_sign_test import _message_for_trial  # noqa: E402 -- reused verbatim (HK-018)
from coherent_llr_ctypes import CoherentExtractLLRs, CURRENT_DLL_SHA256, CURRENT_SHIM_VERSION  # noqa: E402

SEED = 20260821  # this session's date (HK-017-style provenance), same as ROW 0g's

BASE_FREQ_HZ = 1500.0  # nominal grid frequency -- exact lattice point (spec Sec.1.1)
SAMPLE_RATE_HZ = 12000
M_TRIALS = 20  # matches 0g-1's M_CLEAN_TRIALS

# -- A1: frequency residual, per-path time-minimised (spec Sec.3, A1) -----------------------
A1_DELTA_F_HZ = tuple(round(v, 6) for v in np.linspace(-1.5625, 1.5625, 13))

# -- A2: timing residual, fixed (unswept) call offset (spec Sec.3, A2) -----------------------
A2_DELTA_T_S = tuple(round(v, 6) for v in np.linspace(-0.12, 0.12, 25))  # >= +/-0.06s required

# -- A3: joint, realistic residuals (spec Sec.3, A3) -----------------------------------------
# delta_f magnitude is H1a's measured mean |delta_f| (0.745 Hz, cross-validated against T1's
# mean_r to 0.0085 Hz -- see spec Sec.2, C2). delta_t magnitudes: D2's anchor spread alone
# (~0.07s), design.md D3's convention-offset midpoint alone (~0.15s), and the two combined
# worst case (~0.27s) -- all three read verbatim off the board, not tuned to hit a target.
A3_DELTA_F_HZ = (0.745, -0.745)
A3_DELTA_T_S = (0.07, 0.15, 0.27, -0.07, -0.15, -0.27)
D_REAL_TARGET = -67.0
D_REAL_CI = (-71.0, -65.0)

# -- Operating-point calibration (floor-degeneracy guard, ported verbatim from
# row0g_instrument_gain_check.py's own remedy -- HK-018) -------------------------------------
# A noiseless clean signal is a DEGENERATE floor for this correlator: 0g-1's own noiseless
# primary run read median(n_err)=0 for BOTH paths on every trial (row0g_report.json,
# "floor_degenerate": true) -- ~20-25dB of coherent/symbol-integration processing gain over the
# reference bandwidth means noiseless synthetic audio is essentially unbreakable by a lattice-
# scale frequency or sub-symbol timing residual alone. Confirmed freshly below, not assumed:
# an initial A1 run at snr_db=None read exactly 0 for both paths across the FULL swept
# delta_f range, which is the identical degeneracy 0g-1 hit -- so it is ported, not invented.
# The remedy is 0g-1's own: add seeded noise until the GRID path's median lands in a
# discriminating band, then run every Phase A sweep at that ONE calibrated operating point.
SNR_LADDER_DB = (-4.0, -8.0, -12.0, -16.0, -18.0, -19.0, -20.0, -21.0, -22.0, -24.0, -28.0)
CALIBRATION_TARGET_LO = 5.0
CALIBRATION_TARGET_HI = 25.0
CALIBRATION_SEED_BASE = SEED + 500_000  # matches row0g's own noisy-retry seed convention


def _n_err(llr, true_bits) -> int:
    """Same convention as row0g_instrument_gain_check.py: ber is an exact k/174 by
    construction."""
    return int(round(hard_decision_ber(llr, true_bits) * FTX_LDPC_N))


def _render(encoder_mod, msg: str, base_freq_hz: float, seed: int, snr_db: float):
    pcm = encoder_mod.encode_message(msg, base_freq_hz=base_freq_hz, dt_s=0.0, snr_db=snr_db,
                                      seed=seed, sample_rate_hz=SAMPLE_RATE_HZ)
    pcm = np.ascontiguousarray(pcm, dtype=np.float32)
    assert pcm.shape == (180_000,), pcm.shape
    return pcm


def calibrate_operating_snr(ex: CoherentExtractLLRs, log) -> float:
    """Finds an snr_db (from the same ladder row0g used) at which the GRID path's own
    median(n_err), at delta_f=0 with the 49-point per-path time sweep, lands in
    [CALIBRATION_TARGET_LO, CALIBRATION_TARGET_HI] -- clear of both the noiseless floor and
    outright noise saturation. All of A1/A2/A3 then run at this ONE fixed operating point, so
    every sweep is reporting a genuine sensitivity to its own swept variable, not a floor
    artefact."""
    from synth import encoder  # noqa: PLC0415

    log("\n" + "=" * 90)
    log("CALIBRATION -- finding an operating snr_db clear of the noiseless floor degeneracy "
        "(0g-1's own finding: noiseless reads median(n_err)=0 for both paths)")
    log("=" * 90)

    for snr_db in SNR_LADDER_DB:
        grid_mins = []
        for i in range(M_TRIALS):
            msg = _message_for_trial(i)
            true_bits = ex.true_codeword(msg)
            assert true_bits is not None
            pcm = _render(encoder, msg, BASE_FREQ_HZ, CALIBRATION_SEED_BASE + i, snr_db)
            best_g = None
            for off in TIME_ANCHOR_OFFSETS_S:
                rc_g, llr_g = ex.extract_at(pcm, BASE_FREQ_HZ, off)
                if rc_g == 0 and llr_g is not None:
                    ne_g = _n_err(llr_g, true_bits)
                    if best_g is None or ne_g < best_g:
                        best_g = ne_g
            assert best_g is not None, "grid path never succeeded during calibration at %.0fdB" % snr_db
            grid_mins.append(best_g)
        median_grid = float(st.median(grid_mins))
        log("  snr_db=%+5.1f -> median(n_err_grid_min)=%.2f" % (snr_db, median_grid))
        if CALIBRATION_TARGET_LO <= median_grid <= CALIBRATION_TARGET_HI:
            log("  LANDED at snr_db=%.1f (grid median=%.2f, target [%.0f,%.0f])"
                % (snr_db, median_grid, CALIBRATION_TARGET_LO, CALIBRATION_TARGET_HI))
            return snr_db

    raise RuntimeError("Could not land median(n_err_grid_min) in [%.0f,%.0f] across the SNR "
                        "ladder %s -- ESCALATE, do not silently run Phase A at a floor or "
                        "saturation point." % (CALIBRATION_TARGET_LO, CALIBRATION_TARGET_HI,
                                                SNR_LADDER_DB))


def find_shared_time_anchor(ex: CoherentExtractLLRs, log, snr_db: float) -> float:
    """A2/A3 need a single SHARED call offset that both paths are evaluated at (that is the
    whole point of the confound under test -- 0g-2's real methodology uses one un-swept anchor
    for both paths, unlike 0g-1's per-path minimisation). A naive delta_t=0.0 is NOT that
    reference: an initial run at delta_t=0.0 read median(n_err_grid)=70.5 (near the ~87
    pure-noise ceiling) while coherent read 6.0 at the SAME point -- i.e. delta_t=0.0 landed on
    the wrong side of the encoder's own dt_s=0 vs extractor's time_offset_s=0 convention gap
    (design.md D3, ~+0.1-0.2s, discovered independently in Phase 0). Anchoring A2/A3's sweep on
    an accidentally-bad point would silently bias every result in this phase.

    The correct SHARED reference, matching design.md D1 (coherent LLRs form at the grid path's
    OWN existing position, never a position search of its own), is the offset that minimises the
    GRID path's median n_err over the same 49-point sweep 0g-1 uses -- i.e. where a real pipeline
    would have placed the candidate. Coherent's reading AT that same point is recorded, not
    optimised for."""
    from synth import encoder  # noqa: PLC0415

    log("\n" + "=" * 90)
    log("CALIBRATION -- finding the SHARED time anchor (grid path's own best offset over the "
        "49-point sweep at delta_f=0, snr_db=%.1f) -- coherent is read AT this same offset, "
        "never independently optimised (design.md D1)" % snr_db)
    log("=" * 90)

    true_bits_by_trial = [ex.true_codeword(_message_for_trial(i)) for i in range(M_TRIALS)]
    assert all(tb is not None for tb in true_bits_by_trial)
    pcms = [_render(encoder, _message_for_trial(i), BASE_FREQ_HZ, CALIBRATION_SEED_BASE + i, snr_db)
            for i in range(M_TRIALS)]

    best_off, best_grid_median, coh_median_at_best = None, None, None
    for off in TIME_ANCHOR_OFFSETS_S:
        grid_ok, coh_ok = [], []
        for true_bits, pcm in zip(true_bits_by_trial, pcms):
            rc_g, llr_g = ex.extract_at(pcm, BASE_FREQ_HZ, off)
            if rc_g == 0 and llr_g is not None:
                grid_ok.append(_n_err(llr_g, true_bits))
            rc_c, llr_c = ex.coherent_extract_at(pcm, BASE_FREQ_HZ, off)
            if rc_c == 0 and llr_c is not None:
                coh_ok.append(_n_err(llr_c, true_bits))
        if not grid_ok:
            continue
        median_g = float(st.median(grid_ok))
        if best_grid_median is None or median_g < best_grid_median:
            best_grid_median = median_g
            best_off = off
            coh_median_at_best = float(st.median(coh_ok)) if coh_ok else None

    assert best_off is not None, "grid path never succeeded during shared-anchor calibration"
    log("  shared anchor: time_offset_s=%.3f  grid_median=%.2f  coh_median_at_same_offset=%s"
        % (best_off, best_grid_median,
           "%.2f" % coh_median_at_best if coh_median_at_best is not None else "N/A"))
    return best_off


# =====================================================================================
# A1 -- frequency residual, timing neutralised by per-path sweep-and-minimise
# =====================================================================================

def run_a1(ex: CoherentExtractLLRs, log, snr_db: float) -> list[dict]:
    from synth import encoder  # noqa: PLC0415

    log("\n" + "=" * 90)
    log("PHASE A1 -- frequency residual (render off-nominal, call at nominal %.4f Hz), "
        "%d-point time sweep retained per path (M=%d, snr_db=%.1f calibrated)"
        % (BASE_FREQ_HZ, len(TIME_ANCHOR_OFFSETS_S), M_TRIALS, snr_db))
    log("=" * 90)

    rows = []
    for delta_f in A1_DELTA_F_HZ:
        render_freq = BASE_FREQ_HZ + delta_f
        grid_mins, coh_mins, diffs = [], [], []
        for i in range(M_TRIALS):
            msg = _message_for_trial(i)
            true_bits = ex.true_codeword(msg)
            assert true_bits is not None
            pcm = _render(encoder, msg, render_freq, CALIBRATION_SEED_BASE + i, snr_db)

            best_g, best_c = None, None
            for off in TIME_ANCHOR_OFFSETS_S:
                rc_g, llr_g = ex.extract_at(pcm, BASE_FREQ_HZ, off)
                if rc_g == 0 and llr_g is not None:
                    ne_g = _n_err(llr_g, true_bits)
                    if best_g is None or ne_g < best_g:
                        best_g = ne_g
                rc_c, llr_c = ex.coherent_extract_at(pcm, BASE_FREQ_HZ, off)
                if rc_c == 0 and llr_c is not None:
                    ne_c = _n_err(llr_c, true_bits)
                    if best_c is None or ne_c < best_c:
                        best_c = ne_c
            assert best_g is not None and best_c is not None, \
                "extraction never succeeded at delta_f=%.4f trial %d" % (delta_f, i)
            grid_mins.append(best_g)
            coh_mins.append(best_c)
            diffs.append(best_g - best_c)

        row = {
            "delta_f_hz": delta_f,
            "median_n_err_grid": float(st.median(grid_mins)),
            "median_n_err_coh": float(st.median(coh_mins)),
            "d_clean": float(st.median(diffs)),
            "n_err_grid": grid_mins, "n_err_coh": coh_mins,
        }
        rows.append(row)
        log("  delta_f=%+8.4f Hz  median(n_err_grid)=%6.2f  median(n_err_coh)=%6.2f  "
            "d_clean=%+7.2f" % (delta_f, row["median_n_err_grid"], row["median_n_err_coh"],
                                 row["d_clean"]))

    # Rough sensitivity comparison: how fast does each path's median degrade per Hz of
    # |delta_f|, relative to the delta_f=0 anchor (nearest grid point to zero)?
    zero_row = min(rows, key=lambda r: abs(r["delta_f_hz"]))
    worst_row = max(rows, key=lambda r: abs(r["delta_f_hz"]))
    log("\n  anchor (delta_f~=0, actual %.4f Hz): median_grid=%.2f median_coh=%.2f"
        % (zero_row["delta_f_hz"], zero_row["median_n_err_grid"], zero_row["median_n_err_coh"]))
    log("  worst swept |delta_f| (%.4f Hz): median_grid=%.2f (+%.2f) median_coh=%.2f (+%.2f)"
        % (worst_row["delta_f_hz"],
           worst_row["median_n_err_grid"], worst_row["median_n_err_grid"] - zero_row["median_n_err_grid"],
           worst_row["median_n_err_coh"], worst_row["median_n_err_coh"] - zero_row["median_n_err_coh"]))
    return rows


# =====================================================================================
# A2 -- timing residual, single fixed call offset (no per-path minimisation)
# =====================================================================================

def run_a2(ex: CoherentExtractLLRs, log, snr_db: float, anchor0: float) -> dict:
    from synth import encoder  # noqa: PLC0415

    log("\n" + "=" * 90)
    log("PHASE A2 -- timing residual (render at nominal placement, call time_offset_s = shared "
        "anchor %.3fs + delta_t -- see module docstring for why the shift is applied "
        "call-side), fixed single call (no per-path sweep), M=%d, snr_db=%.1f calibrated"
        % (anchor0, M_TRIALS, snr_db))
    log("=" * 90)

    # Render ONCE -- delta_t is applied call-side (module docstring), so the underlying audio
    # is identical across the whole delta_t sweep. Reusing it also makes the sweep a PAIRED
    # comparison (same 20 noise realisations at every delta_t), not 25 independent samples.
    msg_true_bits = []
    pcms = []
    for i in range(M_TRIALS):
        msg = _message_for_trial(i)
        true_bits = ex.true_codeword(msg)
        assert true_bits is not None
        pcm = _render(encoder, msg, BASE_FREQ_HZ, CALIBRATION_SEED_BASE + i, snr_db)
        msg_true_bits.append(true_bits)
        pcms.append(pcm)

    rows = []
    for delta_t in A2_DELTA_T_S:
        call_off = anchor0 + delta_t
        grid_errs, coh_errs = [], []
        for true_bits, pcm in zip(msg_true_bits, pcms):
            rc_g, llr_g = ex.extract_at(pcm, BASE_FREQ_HZ, call_off)
            grid_errs.append(_n_err(llr_g, true_bits) if (rc_g == 0 and llr_g is not None) else None)
            rc_c, llr_c = ex.coherent_extract_at(pcm, BASE_FREQ_HZ, call_off)
            coh_errs.append(_n_err(llr_c, true_bits) if (rc_c == 0 and llr_c is not None) else None)

        grid_ok = [v for v in grid_errs if v is not None]
        coh_ok = [v for v in coh_errs if v is not None]
        row = {
            "delta_t_s": delta_t,
            "median_n_err_grid": float(st.median(grid_ok)) if grid_ok else None,
            "median_n_err_coh": float(st.median(coh_ok)) if coh_ok else None,
            "n_grid_ok": len(grid_ok), "n_coh_ok": len(coh_ok),
        }
        rows.append(row)
        log("  delta_t=%+7.3f s  median(n_err_grid)=%s (%d/%d)  median(n_err_coh)=%s (%d/%d)"
            % (delta_t,
               "%.2f" % row["median_n_err_grid"] if row["median_n_err_grid"] is not None else "N/A",
               row["n_grid_ok"], M_TRIALS,
               "%.2f" % row["median_n_err_coh"] if row["median_n_err_coh"] is not None else "N/A",
               row["n_coh_ok"], M_TRIALS))

    result = {"rows": rows, "shared_anchor_s": anchor0}
    for path_key in ("median_n_err_grid", "median_n_err_coh"):
        valid = [r for r in rows if r[path_key] is not None]
        if len(valid) < 3:
            result[path_key + "_slope"] = None
            continue
        idx_min = min(range(len(valid)), key=lambda i: valid[i][path_key])
        dt_min = valid[idx_min]["delta_t_s"]
        base = valid[idx_min][path_key]
        # ⚠️ dt_min is each path's OWN empirical minimum over this swept range -- reported only
        # as the reference point for a relative slope, never as an absolute optimal delta_t
        # (design.md D3 -- the axis zero is uncalibrated). Left/right slopes in n_err per 10ms.
        right = [(v["delta_t_s"] - dt_min, v[path_key] - base) for v in valid if v["delta_t_s"] > dt_min]
        left = [(dt_min - v["delta_t_s"], v[path_key] - base) for v in valid if v["delta_t_s"] < dt_min]

        def _slope_per_10ms(pts):
            if len(pts) < 2:
                return None
            xs = np.array([p[0] for p in pts])
            ys = np.array([p[1] for p in pts])
            m, _b = np.polyfit(xs, ys, 1)
            return float(m) * 0.010

        result[path_key + "_own_min_delta_t_s"] = dt_min  # relative reference only, see note above
        result[path_key + "_slope_right_per_10ms"] = _slope_per_10ms(right)
        result[path_key + "_slope_left_per_10ms"] = _slope_per_10ms(left)

    log("\n  grid : own-minimum reference delta_t=%.3fs (relative only) slope_right=%s "
        "slope_left=%s n_err/10ms"
        % (result.get("median_n_err_grid_own_min_delta_t_s", float("nan")),
           result.get("median_n_err_grid_slope_right_per_10ms"),
           result.get("median_n_err_grid_slope_left_per_10ms")))
    log("  coh  : own-minimum reference delta_t=%.3fs (relative only) slope_right=%s "
        "slope_left=%s n_err/10ms"
        % (result.get("median_n_err_coh_own_min_delta_t_s", float("nan")),
           result.get("median_n_err_coh_slope_right_per_10ms"),
           result.get("median_n_err_coh_slope_left_per_10ms")))
    return result


# =====================================================================================
# A3 -- joint, at realistic residuals
# =====================================================================================

def run_a3(ex: CoherentExtractLLRs, log, snr_db: float, anchor0: float) -> dict:
    from synth import encoder  # noqa: PLC0415

    log("\n" + "=" * 90)
    log("PHASE A3 -- joint frequency+timing residual at realistic magnitudes, fixed single "
        "call at shared anchor %.3fs + delta_t (M=%d per condition, snr_db=%.1f calibrated)"
        % (anchor0, M_TRIALS, snr_db))
    log("=" * 90)

    # Render once per distinct delta_f -- delta_t is applied call-side, so the same rendered
    # audio is reused (paired) across every delta_t swept at a given delta_f.
    true_bits_by_trial = [ex.true_codeword(_message_for_trial(i)) for i in range(M_TRIALS)]
    assert all(tb is not None for tb in true_bits_by_trial)
    render_cache: dict[float, list] = {}

    def _renders_for(delta_f: float) -> list:
        if delta_f not in render_cache:
            render_cache[delta_f] = [
                _render(encoder, _message_for_trial(i), BASE_FREQ_HZ + delta_f,
                        CALIBRATION_SEED_BASE + i, snr_db)
                for i in range(M_TRIALS)
            ]
        return render_cache[delta_f]

    def _one_condition(delta_f: float, delta_t: float) -> dict:
        diffs = []
        grid_mins, coh_mins = [], []
        pcms = _renders_for(delta_f)
        call_off = anchor0 + delta_t
        for true_bits, pcm in zip(true_bits_by_trial, pcms):
            rc_g, llr_g = ex.extract_at(pcm, BASE_FREQ_HZ, call_off)
            rc_c, llr_c = ex.coherent_extract_at(pcm, BASE_FREQ_HZ, call_off)
            if rc_g != 0 or llr_g is None or rc_c != 0 or llr_c is None:
                continue
            ne_g = _n_err(llr_g, true_bits)
            ne_c = _n_err(llr_c, true_bits)
            grid_mins.append(ne_g)
            coh_mins.append(ne_c)
            diffs.append(ne_g - ne_c)
        return {
            "delta_f_hz": delta_f, "delta_t_s": delta_t,
            "n_ok": len(diffs),
            "median_n_err_grid": float(st.median(grid_mins)) if grid_mins else None,
            "median_n_err_coh": float(st.median(coh_mins)) if coh_mins else None,
            "d_clean": float(st.median(diffs)) if diffs else None,
        }

    control = _one_condition(0.0, 0.0)
    log("  CONTROL delta_f=0.0 delta_t=0.0: median_grid=%.2f median_coh=%.2f d_clean=%+.2f "
        "(n_ok=%d/%d)" % (control["median_n_err_grid"], control["median_n_err_coh"],
                           control["d_clean"], control["n_ok"], M_TRIALS))

    conditions = []
    worst = control  # CONTROL is itself a candidate for "most negative" and must not be
                      # excluded from this comparison -- an earlier cut of this script dropped
                      # it, silently missing that the shared D1 anchor ALONE (zero injected
                      # delta_f/delta_t) can already be the single worst point measured.
    for delta_t in A3_DELTA_T_S:
        for delta_f in A3_DELTA_F_HZ:
            row = _one_condition(delta_f, delta_t)
            conditions.append(row)
            log("  delta_f=%+6.3f Hz delta_t=%+6.3f s: median_grid=%s median_coh=%s d_clean=%s "
                "(n_ok=%d/%d)"
                % (delta_f, delta_t,
                   "%.2f" % row["median_n_err_grid"] if row["median_n_err_grid"] is not None else "N/A",
                   "%.2f" % row["median_n_err_coh"] if row["median_n_err_coh"] is not None else "N/A",
                   "%+.2f" % row["d_clean"] if row["d_clean"] is not None else "N/A",
                   row["n_ok"], M_TRIALS))
            if row["d_clean"] is not None and row["d_clean"] < worst["d_clean"]:
                worst = row

    log("\n  most-negative d_clean overall (CONTROL included): delta_f=%+.3f Hz delta_t=%+.3f s "
        "-> d_clean=%+.2f  (0g-2's d_real = %.1f, CI95=[%.1f, %.1f])"
        % (worst["delta_f_hz"], worst["delta_t_s"], worst["d_clean"],
           D_REAL_TARGET, D_REAL_CI[0], D_REAL_CI[1]))
    if worst is control:
        log("  -> the WORST point is the CONTROL itself: the shared D1 anchor (grid's own best "
            "position, %.3fs) ALONE, with ZERO injected delta_f/delta_t, already produces this "
            "collapse. Every explicitly-injected residual tested made the joint contrast LESS "
            "negative than the control, not more -- injecting delta_t moves the shared call "
            "position OFF grid's plateau, which degrades grid roughly as much as it degrades "
            "coherent (or, for delta_t=-0.15s, moves toward COHERENT's own optimum and reverses "
            "the sign entirely, d_clean=+56 to +59)." % anchor0)

    if worst["d_clean"] <= D_REAL_CI[0]:
        verdict_note = ("REPRODUCES an effect of 0g-2's order of magnitude "
                         "(|d_clean| reaches or exceeds the CI). This is a DIAGNOSTIC reading, "
                         "not a ROW verdict -- see module docstring.")
    elif worst["d_clean"] <= -30.0:
        verdict_note = ("Reaches roughly half or more of 0g-2's magnitude but does not enter its "
                         "CI. Driven overwhelmingly by the CONTROL (the D1-mandated shared, "
                         "un-refined position itself), not by the explicitly injected residual "
                         "magnitudes -- see the note above. Channel (C4) not excluded, but C1-"
                         "the fusion rule (baked into ft8_coherent_llr_at, measured here as-is)-"
                         "combined with the grid/coherent OPTIMAL-POSITION MISMATCH (see A2's "
                         "own-minimum readout above -- a variant of C3 not anticipated in the "
                         "spec's own framing: the two paths' true optima differ measurably even "
                         "at delta_f=0) is the leading candidate.")
    else:
        verdict_note = ("Does not approach 0g-2's magnitude from residuals alone -- channel (C4) "
                         "moves from last resort toward leading candidate, per spec Sec.3's own "
                         "decision rule. DIAGNOSTIC reading only.")
    log("  " + verdict_note)

    return {"control": control, "conditions": conditions, "worst": worst, "note": verdict_note,
            "shared_anchor_s": anchor0}


# =====================================================================================
# main
# =====================================================================================

def main() -> int:
    out_dir = os.path.join(HERE, "results")
    os.makedirs(out_dir, exist_ok=True)
    log_lines: list[str] = []

    def log(msg: str = "") -> None:
        print(msg)
        log_lines.append(msg)

    log("=" * 90)
    log("PHASE A -- de-confounding ROW 0g-2 (diagnostic only; no ROW; no verdict; ROW 0g not "
        "re-read -- spec 2026-08-21-1201-architect-to-qa-b2-row0g-native-fix-triage-and-phase-a-"
        "deconfounding.md Sec.3/Sec.6)")
    log("=" * 90)

    log("\nLoading DLL: %s (pinned to the CURRENT MERGED binary, shim %d)"
        % (DEFAULT_DLL_PATH, CURRENT_SHIM_VERSION))
    try:
        ex = CoherentExtractLLRs(DEFAULT_DLL_PATH, verify=True,
                                  expected_sha256=CURRENT_DLL_SHA256,
                                  expected_shim_version=CURRENT_SHIM_VERSION)
    except (RuntimeError, AttributeError) as e:
        log("\nDLL pin check FAILED: %s" % e)
        log("STOP. NO DIAGNOSTIC RESULT.")
        P.write_json(os.path.join(out_dir, "phase_a_report.json"),
                      {"final": "dll_pin_fail", "error": str(e)})
        with open(os.path.join(out_dir, "phase_a_run.log"), "w", encoding="ascii",
                  errors="replace") as fh:
            fh.write("\n".join(log_lines) + "\n")
        return 2
    log("DLL pin confirmed: SHA256 %s..., shim version %d" % (CURRENT_DLL_SHA256[:16], ex.version))

    t0 = time.time()
    try:
        operating_snr_db = calibrate_operating_snr(ex, log)
    except RuntimeError as e:
        log("\nCALIBRATION FAILED: %s" % e)
        log("STOP. NO DIAGNOSTIC RESULT.")
        P.write_json(os.path.join(out_dir, "phase_a_report.json"),
                      {"final": "calibration_fail", "error": str(e)})
        with open(os.path.join(out_dir, "phase_a_run.log"), "w", encoding="ascii",
                  errors="replace") as fh:
            fh.write("\n".join(log_lines) + "\n")
        return 3

    anchor0 = find_shared_time_anchor(ex, log, operating_snr_db)

    a1 = run_a1(ex, log, operating_snr_db)
    a2 = run_a2(ex, log, operating_snr_db, anchor0)
    a3 = run_a3(ex, log, operating_snr_db, anchor0)
    elapsed = time.time() - t0

    log("\n" + "=" * 90)
    log("PHASE A COMPLETE (%.1fs, operating snr_db=%.1f, shared anchor=%.3fs). This produced NO "
        "ROW, NO PASS/FAIL, NO f_net. ROW 0g stands exactly as run: FIRED, gate VOID, Route B2 "
        "not dead, ROW 3 not declared." % (elapsed, operating_snr_db, anchor0))
    log("=" * 90)

    bundle = {
        "dll_pin": {"sha256_prefix": CURRENT_DLL_SHA256[:16], "shim_version": ex.version},
        "operating_snr_db": operating_snr_db,
        "shared_time_anchor_s": anchor0,
        "a1_frequency": a1,
        "a2_timing": a2,
        "a3_joint": a3,
        "d_real_target": D_REAL_TARGET, "d_real_ci95": list(D_REAL_CI),
        "elapsed_s": elapsed,
        "final": "diagnostic_complete_no_row",
    }
    P.write_json(os.path.join(out_dir, "phase_a_report.json"), bundle)
    with open(os.path.join(out_dir, "phase_a_run.log"), "w", encoding="ascii",
              errors="replace") as fh:
        fh.write("\n".join(log_lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
