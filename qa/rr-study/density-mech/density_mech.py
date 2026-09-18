#!/usr/bin/env python3
"""DENSITY-MECH -- is the near-neighbour live loss in EXTRACTION (M1) or
upstream of it (M2)?

Spec: qa/rr-study/2026-09-18-1356-architect-to-qa-spec-density-mechanism-oracle-position.md
(branch arch/density, commit 1b0d7d20). Captain: "1. go".

Offline, synthetic (Q-prefix), F-NBR-A's own S8HN scene. No src/native change,
no station time, no Developer, no live corpus. Every entry point is already
exported by the shipped shim.

======================================================================
SEC.1.3 POSITION MAPPING -- required by spec Sec.1.3, stated here AND in the
results JSON (deliverable 1's "write it down" requirement; ROW 0c is the
MECHANICAL check that this mapping is right -- an unobstructed victim at its
"true position" must decode >=90% of the time).

  freq_hz passed to ft8_extract_llrs_at = F's TONE-0 BASE FREQUENCY, i.e. the
  exact value scene_render.py's F_TRUE_FREQ_HZ / move_station_freq() sets, and
  the same value passed as synth.encoder.encode_message()'s own base_freq_hz
  argument. synth/modulator.py:153 documents that convention explicitly:
  "base_freq_hz is the audio frequency of tone 0; tone k sits at base + k *
  6.25 Hz." This is also the SAME convention ft8_decode_all reports in its
  own FT8Result.freq_hz (confirmed by the r2-coherent-llr-instrument B-pos-A/
  B-orig-A precedent, both GATED arms, which feed decode_all-reported
  frequencies straight into ft8_extract_llrs_at with no offset -- see
  b_pos_a_lattice_position.py's build_sample_and_deliver(): freq_int =
  round(row["anchor_freq_hz"]), passed unmodified to _extract_cell()).

  NOTE the shim header's OWN doc comment (ft8_shim.h ~line 1092) calls this
  parameter "requested centre frequency, Hz" -- that is native-side language
  for "the signal's reference audio frequency" (FT8/WSJT-X convention), NOT
  the arithmetic midpoint of the 8-tone span (which would be base + 3.5*6.25
  = base + 21.875 Hz). Every existing verbatim-reused harness treats it as
  tone-0. This is exactly the kind of terminology trap the spec asks to be
  named rather than assumed -- ROW 0c is the check that catches it if wrong.

  time_offset_s passed to ft8_extract_llrs_at = F's true dt_s (0.0 in the
  S8HN scenario) PLUS SYMBOL_PERIOD_S (0.16 s). This is the CONFIRMED
  B-orig-A finding (qa/rr-study/2026-08-21-1412-architect-to-qa-origin-
  convention-finding-and-spec-b-orig-a.md, ROW 1 FIRED): the waterfall index
  ft8_extract_llrs_at reads runs exactly ONE FT8 symbol AHEAD of raw-PCM
  time (monitor.c's look-back window). Reused verbatim via
  f-nbr-a/dll_common.py's own extraction_time_offset_s()/SYMBOL_PERIOD_S
  (NOT re-derived here -- HK-018). dt_true=0.0 -> time_offset_s=0.16.
======================================================================

Binary: src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll, SHA-256
91997e38038d9328edcb49cd1e8661706d0092ed2c73e808094c96c3980ad2c6 (shim
20260051) -- spec Sec.1.2's pin. Confirmed on disk before this script was
written (this session), and independently already used at this same pin by
qa/rr-study/f-nbr-a/nbr_rerun_driver.py (NEW_DLL_SHA256, same worktree).

max_iters=50, osd_depth=2 -- READ FROM THE BUILD (this session, not
inherited from a comment), spec Sec.1.2's requirement:
  - K_LDPC_ITERATIONS = 50 (src/OpenWSFZ.Ft8/Native/ft8_shim.c:509), wired as
    pass 0's max_iterations via k_pass_cfg (ft8_shim.c:1579) into
    ftx_decode_candidate(..., pass_ldpc, ...) (ft8_shim.c:1625) -- this is
    PRODUCTION's own pass-0 (full-waterfall) LDPC iteration count, confirmed
    still current at shim 20260051 by reading the actual source, not assumed.
  - osd_depth: production's ftx_decode_candidate (decode.c:666) calls
    osd_decode(llr_for_osd, 2, plain174) on BP failure -- ndeep=2 hardcoded
    in the production path itself (not the caller-supplied osd_depth
    parameter that ft8_ldpc_decode_llrs exposes for diagnostic use -- that
    parameter must be set to match production's hardcoded 2, per spec
    Sec.1.2: "An oracle decode on weaker LDPC settings than production's
    would bias toward M1").

NOT in scope anywhere in this module: ft8_coherent_llr_at (spec Sec.4 item 5
-- a remedy trial, not this arm's question). Not imported, not called.
"""
from __future__ import annotations

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
):
    if p not in sys.path:
        sys.path.insert(0, p)

import scene_render as SR  # noqa: E402  (verbatim reuse)
import part_c as PC  # noqa: E402  (verbatim reuse -- _f_recovered)
import dll_common as DC  # noqa: E402  (verbatim reuse -- extraction_time_offset_s / SYMBOL_PERIOD_S ONLY; NOT its stale DLL pin)
from ldpc_decode_ctypes import LdpcDecodeLLRs, FT8_PAYLOAD_BITS  # noqa: E402  (verbatim reuse)
from extract_llrs_ctypes import FTX_LDPC_N, hard_decision_ber, dll_sha256  # noqa: E402  (verbatim reuse)
import ldpc_decode_ctypes as LDC  # noqa: E402  (a91_to_bits)

OUT_DIR = os.path.join(HERE, "results")
RESULT_JSON = os.path.join(OUT_DIR, "density_mech_result.json")

# ── This arm's own DLL pin (spec Sec.1.2 -- D4 discipline: never inherit
# dll_common.py's/ldpc_decode_ctypes.py's own stale module-level pins) ──────
DLL_PATH = os.path.join(REPO_ROOT, "src", "OpenWSFZ.Ft8", "Native", "win-x64", "libft8.dll")
PINNED_DLL_SHA256 = "91997e38038d9328edcb49cd1e8661706d0092ed2c73e808094c96c3980ad2c6"
PINNED_SHIM_VERSION = 20260051

# ── Read from the build, this session (module docstring above cites the exact
# source lines) -- NOT inherited from dll_common.py's own K_LDPC_ITERATIONS/
# OSD_DEPTH comment (which cites the SAME source lines independently; the two
# values agreeing is expected, not assumed). ────────────────────────────────
MAX_ITERS = 50    # ft8_shim.c:509 K_LDPC_ITERATIONS, wired ft8_shim.c:1579/1625
OSD_DEPTH = 2      # decode.c:666 osd_decode(..., 2, ...) production hardcode

N_TRIALS = int(os.environ.get("DENSITY_MECH_N_TRIALS", "100"))  # spec Sec.1.4; env override for smoke-testing ONLY

# Position mapping (see module docstring) -- time_offset_s for F's true dt_s=0.0
F_TIME_OFFSET_S = DC.extraction_time_offset_s(0.0)  # = 0.16 (DC.SYMBOL_PERIOD_S)

PRIMARY_E_SNR_DB = -5.0     # spec Sec.1.4 -- the bench's own E level, held fixed
PRIMARY_DELTAS_HZ = [6.25, 12.0, 18.75]
PRIMARY_X_DB = [1.0, 3.0, 6.0]

STRONG_F_SNR_DB = 5.0
STRONG_E_SNR_DB = 8.0       # X = +3
STRONG_DELTAS_HZ = [6.25, 12.0, 18.75]

ROW0D_F_SNR_DB = -30.0
ROW0D_DELTA_HZ = 12.0       # E is removed for 0d -- Delta only fixes F's frequency for consistency
ROW0D_PART_INDEX = 2201

ROW0C_BAR = 0.90
ROW0D_BAR = 0.20
ROW0E_MIN_EXCLUDED = 6      # of 9 primary cells
M1_BAR = 0.20
M2_BAR = 0.80
PROD_EXCLUDED_BAR = 0.20


def log(msg):
    print(msg, flush=True)


def build_cells():
    """Returns the 9 primary + 3 strong-victim cell specs, each with its own
    part_index (disjoint from F-NBR-A's own 0/101/201-207/301-304 range)."""
    cells = []
    idx = 2001
    for delta in PRIMARY_DELTAS_HZ:
        for x in PRIMARY_X_DB:
            f_snr = PRIMARY_E_SNR_DB - x
            cells.append({"group": "primary", "delta_hz": delta, "x_db": x,
                          "e_snr_db": PRIMARY_E_SNR_DB, "f_snr_db": f_snr, "part_index": idx})
            idx += 1
    idx = 2101
    for delta in STRONG_DELTAS_HZ:
        cells.append({"group": "strong", "delta_hz": delta, "x_db": STRONG_E_SNR_DB - STRONG_F_SNR_DB,
                      "e_snr_db": STRONG_E_SNR_DB, "f_snr_db": STRONG_F_SNR_DB, "part_index": idx})
        idx += 1
    return cells


def cell_signals(cell):
    """Returns (full_signals, ablated_signals, target_freq_hz) for one cell."""
    base = SR.load_s8hn_signals()
    base = SR.set_station_snr(base, SR.STATION_E, cell["e_snr_db"])
    base = SR.set_station_snr(base, SR.STATION_F, cell["f_snr_db"])
    target_freq = SR.E_FREQ_HZ + cell["delta_hz"]
    full_signals = SR.move_station_freq(base, SR.STATION_F, target_freq)
    ablated_signals = SR.remove_station(full_signals, SR.STATION_E)
    return full_signals, ablated_signals, target_freq


def oracle_trial(dec, pcm, freq_hz, true_bits):
    """Returns dict: rc, hit (bool), ber (float or None)."""
    rc, llr = dec.extract_at(pcm, freq_hz, F_TIME_OFFSET_S)
    if rc != 0 or llr is None:
        return {"rc": rc, "hit": False, "ber": None}
    res = dec.ldpc_decode_llrs(llr, max_iters=MAX_ITERS, osd_depth=OSD_DEPTH)
    if res["rc"] != 0 or res["a91"] is None:
        return {"rc": rc, "ldpc_rc": res["rc"], "hit": False, "ber": hard_decision_ber(llr, true_bits)}
    recovered = LDC.a91_to_bits(res["a91"], FT8_PAYLOAD_BITS)
    expected = true_bits[:FT8_PAYLOAD_BITS]
    hit = (res["crc_ok"] == 1) and (recovered == expected)
    return {"rc": rc, "ldpc_rc": res["rc"], "crc_ok": res["crc_ok"], "hit": hit,
            "ber": hard_decision_ber(llr, true_bits)}


def run_cell(dec, cell, true_bits, log_every=None):
    full_signals, ablated_signals, target_freq = cell_signals(cell)
    n_prod_hit = n_e_hit = n_0_hit = 0
    n_e_extract_fail = n_0_extract_fail = 0
    ber_pairs = []  # (ber_E, ber_0) where both are not None

    for t in range(N_TRIALS):
        seed = SR.trial_seed(t, cell["part_index"])
        pcm_full = SR.render_scene(full_signals, seed)
        pcm_ablated = SR.render_scene(ablated_signals, seed)

        prod_results = dec.decode_all(pcm_full)
        if PC._f_recovered(prod_results, target_freq, SR.F_TRUE_MESSAGE):
            n_prod_hit += 1

        oe = oracle_trial(dec, pcm_full, target_freq, true_bits)
        o0 = oracle_trial(dec, pcm_ablated, target_freq, true_bits)
        if oe["hit"]:
            n_e_hit += 1
        if o0["hit"]:
            n_0_hit += 1
        if oe["ber"] is None:
            n_e_extract_fail += 1
        if o0["ber"] is None:
            n_0_extract_fail += 1
        if oe["ber"] is not None and o0["ber"] is not None:
            ber_pairs.append((oe["ber"], o0["ber"]))

    diffs = sorted(b_e - b_0 for b_e, b_0 in ber_pairs)
    ber_shift = {
        "n_paired": len(diffs),
        "median": (st.median(diffs) if diffs else None),
        "q1": (diffs[len(diffs) // 4] if diffs else None),
        "q3": (diffs[(3 * len(diffs)) // 4] if diffs else None),
    }

    return {
        "group": cell["group"], "delta_hz": cell["delta_hz"], "x_db": cell["x_db"],
        "e_snr_db": cell["e_snr_db"], "f_snr_db": cell["f_snr_db"], "part_index": cell["part_index"],
        "n_trials": N_TRIALS,
        "prod_hits": n_prod_hit, "prod_rate": n_prod_hit / N_TRIALS,
        "orc_E_hits": n_e_hit, "orc_E_rate": n_e_hit / N_TRIALS,
        "orc_0_hits": n_0_hit, "orc_0_rate": n_0_hit / N_TRIALS,
        "orc_E_extract_fail": n_e_extract_fail, "orc_0_extract_fail": n_0_extract_fail,
        "ber_shift_E_minus_0": ber_shift,
    }


def run_row0d(dec, true_bits):
    base = SR.load_s8hn_signals()
    base = SR.set_station_snr(base, SR.STATION_F, ROW0D_F_SNR_DB)
    target_freq = SR.E_FREQ_HZ + ROW0D_DELTA_HZ
    full_signals = SR.move_station_freq(base, SR.STATION_F, target_freq)
    ablated_signals = SR.remove_station(full_signals, SR.STATION_E)

    n_hit = 0
    n_fail = 0
    for t in range(N_TRIALS):
        seed = SR.trial_seed(t, ROW0D_PART_INDEX)
        pcm = SR.render_scene(ablated_signals, seed)
        o0 = oracle_trial(dec, pcm, target_freq, true_bits)
        if o0["hit"]:
            n_hit += 1
        if o0["ber"] is None:
            n_fail += 1
    return {"n_trials": N_TRIALS, "hits": n_hit, "rate": n_hit / N_TRIALS,
            "extract_fail": n_fail, "f_snr_db": ROW0D_F_SNR_DB, "delta_hz": ROW0D_DELTA_HZ}


def codeword_position_ber(dec, cell, true_bits):
    """Sec.4 item 4: BER split by codeword position class (payload [0:77),
    CRC [77:91), parity [91:174)), orc_E only, only computed for cells that
    read M1 or MIXED (caller decides which cells to call this for)."""
    full_signals, _, target_freq = cell_signals(cell)
    n = [0, 0, 0]
    err = [0, 0, 0]
    ranges = [(0, 77), (77, 91), (91, FTX_LDPC_N)]
    for t in range(N_TRIALS):
        seed = SR.trial_seed(t, cell["part_index"])
        pcm_full = SR.render_scene(full_signals, seed)
        rc, llr = dec.extract_at(pcm_full, target_freq, F_TIME_OFFSET_S)
        if rc != 0 or llr is None:
            continue
        hd = [1 if x > 0.0 else 0 for x in llr]
        for i, (lo, hi) in enumerate(ranges):
            for j in range(lo, hi):
                n[i] += 1
                if hd[j] != true_bits[j]:
                    err[i] += 1
    return {
        "payload": {"n": n[0], "errors": err[0], "ber": (err[0] / n[0] if n[0] else None)},
        "crc": {"n": n[1], "errors": err[1], "ber": (err[1] / n[1] if n[1] else None)},
        "parity": {"n": n[2], "errors": err[2], "ber": (err[2] / n[2] if n[2] else None)},
    }


def evaluate(cells_result, row0d):
    primary = [c for c in cells_result if c["group"] == "primary"]
    strong = [c for c in cells_result if c["group"] == "strong"]

    row0c_cells = [c for c in primary if c["orc_0_rate"] < ROW0C_BAR]
    row0c_pass = len(row0c_cells) == 0
    row0d_pass = row0d["rate"] <= ROW0D_BAR
    excluded_primary = [c for c in primary if c["prod_rate"] <= PROD_EXCLUDED_BAR]
    row0e_pass = len(excluded_primary) >= ROW0E_MIN_EXCLUDED

    row0_fires = not (row0c_pass and row0d_pass and row0e_pass)

    def cell_read(c):
        if c["orc_E_rate"] <= M1_BAR:
            return "M1"
        if c["orc_E_rate"] >= M2_BAR:
            return "M2"
        return "MIXED"

    reads = {("%.2f,%.1f" % (c["delta_hz"], c["x_db"])): cell_read(c) for c in excluded_primary}

    if row0_fires:
        verdict = "ROW 0 STOP"
    elif not excluded_primary:
        verdict = "ROW 0e SHOULD HAVE STOPPED"  # defensive; row0e_pass implies >=6 excluded
    elif all(reads[k] == "M1" for k in reads):
        verdict = "ROW 1 M1"
    elif all(reads[k] == "M2" for k in reads):
        verdict = "ROW 2 M2"
    else:
        verdict = "ROW 3 MIXED"

    return {
        "row0c": {"pass": row0c_pass, "bar": ROW0C_BAR,
                  "failing_cells": [{"delta_hz": c["delta_hz"], "x_db": c["x_db"], "orc_0_rate": c["orc_0_rate"]}
                                     for c in row0c_cells]},
        "row0d": {"pass": row0d_pass, "bar": ROW0D_BAR, "rate": row0d["rate"]},
        "row0e": {"pass": row0e_pass, "min_excluded": ROW0E_MIN_EXCLUDED,
                  "n_excluded": len(excluded_primary), "n_primary": len(primary)},
        "row0_fires": row0_fires,
        "excluded_primary_cells": [{"delta_hz": c["delta_hz"], "x_db": c["x_db"], "prod_rate": c["prod_rate"],
                                     "orc_E_rate": c["orc_E_rate"], "read": reads.get("%.2f,%.1f" % (c["delta_hz"], c["x_db"]))}
                                    for c in excluded_primary],
        "cell_reads": reads,
        "verdict": verdict,
    }


def run_once():
    t_start = time.time()
    log("Loading DLL: %s (pin %s..., shim %d)" % (DLL_PATH, PINNED_DLL_SHA256[:16], PINNED_SHIM_VERSION))
    try:
        dec = LdpcDecodeLLRs(DLL_PATH, verify=True, expected_sha256=PINNED_DLL_SHA256,
                              expected_shim_version=PINNED_SHIM_VERSION)
    except (RuntimeError, AttributeError, OSError) as e:
        log("ROW 0a STOP: %s" % e)
        return {"row0a": {"pass": False, "error": str(e)}, "final": "row0a_stop"}

    row0a = {"pass": True, "sha256": dll_sha256(DLL_PATH), "shim_version": dec.version,
             "max_iters": MAX_ITERS, "osd_depth": OSD_DEPTH,
             "has_extract_llrs_at": hasattr(dec.dll, "ft8_extract_llrs_at"),
             "has_ldpc_decode_llrs": hasattr(dec.dll, "ft8_ldpc_decode_llrs"),
             "has_decode_all": hasattr(dec.dll, "ft8_decode_all")}
    log("ROW 0a: sha256=%s... shim=%d max_iters=%d osd_depth=%d -> PASS"
        % (row0a["sha256"][:16], row0a["shim_version"], MAX_ITERS, OSD_DEPTH))

    true_bits = dec.true_codeword(SR.F_TRUE_MESSAGE)
    assert true_bits is not None and len(true_bits) == FTX_LDPC_N

    cells = build_cells()
    cells_result = []
    for i, cell in enumerate(cells):
        t0 = time.time()
        r = run_cell(dec, cell, true_bits)
        cells_result.append(r)
        log("[%d/%d] %s Delta=%.2fHz X=%.1fdB (F=%.1fdB E=%.1fdB): prod=%d/%d orc_E=%d/%d orc_0=%d/%d (%.1fs)"
            % (i + 1, len(cells), cell["group"], cell["delta_hz"], cell["x_db"], cell["f_snr_db"], cell["e_snr_db"],
               r["prod_hits"], N_TRIALS, r["orc_E_hits"], N_TRIALS, r["orc_0_hits"], N_TRIALS, time.time() - t0))

    t0 = time.time()
    row0d = run_row0d(dec, true_bits)
    log("ROW 0d (F alone, E removed, %.0fdB): orc_0=%d/%d (%.1fs)"
        % (ROW0D_F_SNR_DB, row0d["hits"], N_TRIALS, time.time() - t0))

    ev = evaluate(cells_result, row0d)
    log("\nROW 0c: %s | ROW 0d: %s | ROW 0e: %d/%d excluded (need >=%d) -> %s"
        % ("PASS" if ev["row0c"]["pass"] else "STOP",
           "PASS" if ev["row0d"]["pass"] else "STOP",
           ev["row0e"]["n_excluded"], ev["row0e"]["n_primary"], ROW0E_MIN_EXCLUDED,
           "PASS" if ev["row0e"]["pass"] else "STOP"))
    log(">>> VERDICT: %s <<<" % ev["verdict"])
    if ev["cell_reads"]:
        log("Cell reads: " + ", ".join("(Delta=%s,X=%s)=%s" % (k.split(",")[0], k.split(",")[1], v)
                                        for k, v in sorted(ev["cell_reads"].items())))

    # Sec.4 item 4: codeword-position BER, only if any excluded cell reads M1/MIXED
    position_ber = {}
    need_position = any(v in ("M1", "MIXED") for v in ev["cell_reads"].values())
    if need_position:
        log("\nAt least one excluded cell reads M1/MIXED -- computing codeword-position BER (Sec.4 item 4) ...")
        for c in cells:
            key = "%.2f,%.1f" % (c["delta_hz"], c["x_db"])
            if c["group"] == "primary" and ev["cell_reads"].get(key) in ("M1", "MIXED"):
                position_ber[key] = codeword_position_ber(dec, c, true_bits)

    result = {
        "spec_commit": "1b0d7d20",
        "position_mapping": {
            "freq_hz_convention": "F's tone-0 base frequency (encoder.encode_message's base_freq_hz; "
                                   "same convention ft8_decode_all reports); NOT the 8-tone-span midpoint "
                                   "despite the shim header's 'centre frequency' wording -- see module docstring",
            "time_offset_s_convention": "dt_true + SYMBOL_PERIOD_S (0.16s), confirmed B-orig-A one-symbol "
                                         "waterfall-origin correction, reused verbatim from dll_common.py",
            "f_true_dt_s": 0.0,
            "f_time_offset_s_used": F_TIME_OFFSET_S,
        },
        "row0a": row0a,
        "cells": cells_result,
        "row0d": row0d,
        "evaluation": ev,
        "position_ber": position_ber,
        "n_trials_per_cell": N_TRIALS,
        "wall_time_s": round(time.time() - t_start, 1),
    }
    return result


def _strip_nondeterministic(d):
    """Deep-copies result, dropping fields that legitimately vary run-to-run
    for reasons unrelated to correctness (wall clock only) -- ROW 0b diffs
    everything else byte-for-byte."""
    out = json.loads(json.dumps(d))
    out.pop("wall_time_s", None)
    return out


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    log("=" * 90)
    log("DENSITY-MECH run 1/2 (ROW 0b needs two byte-identical full runs)")
    log("=" * 90)
    r1 = run_once()

    log("\n" + "=" * 90)
    log("DENSITY-MECH run 2/2")
    log("=" * 90)
    r2 = run_once()

    d1 = _strip_nondeterministic(r1)
    d2 = _strip_nondeterministic(r2)
    row0b_pass = (d1 == d2)
    log("\nROW 0b (determinism, mechanically diffed, wall_time_s excluded): %s"
        % ("PASS -- byte-identical" if row0b_pass else "FAIL -- runs differ"))

    final = dict(r1)
    final["row0b"] = {"pass": row0b_pass}
    if not row0b_pass:
        final["row0b"]["run2"] = r2
        final["final"] = "row0b_stop"
        log(">>> OVERALL: ROW 0 STOP (0b failed) <<<")
    else:
        final["final"] = "complete"

    with open(RESULT_JSON, "w", encoding="utf-8") as f:
        json.dump(final, f, indent=2)
    log("\nWrote %s" % os.path.abspath(RESULT_JSON))
    return 0


if __name__ == "__main__":
    sys.exit(main())
