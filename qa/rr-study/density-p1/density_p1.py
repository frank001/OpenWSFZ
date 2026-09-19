#!/usr/bin/env python
"""DENSITY-P1 Stage 2 -- after production's pass-1 suppression, are the crowded victim's bits at its
position CLEAN (pass 1's search/ranking misses a decodable signal) or still DIRTY (suppression leaves
too much of the neighbour, or damages the victim)?

================================================================================
PRE-REGISTRATION -- committed BEFORE any Stage 2 verdict run (HK-021: mechanical bars)
================================================================================
Spec  : qa/rr-study/2026-09-18-1758-architect-to-qa-spec-density-pass1-probe.md  Sec.2, AS AMENDED BY Sec.7
        (arch/density c0270a83, Architect ruling 2026-09-19T11:48Z on QA's A1-A4). Captain's go: "proceed with stage 2".
Binary: Stage 1 DLL, SHA-256 50e94e7d73e33050ac37145ac675ad467415324b9cbc5183dc47f3e361829bb7, shim 20260053
        (Developer commit 3ad5504e), extracted with `git show` and SHA-checked IN EVERY RUN (ROW 0a). Stage 1 acceptance: S1-a/b/c/e + S1-d.
Params: ft8_set_decode_params(10, 0.10, 40) = the LIVE app's (DecoderConfig.cs: KMinScorePass2 10, OsdCorrThreshold 0.10,
        OsdNhardMax 40), NOT the shim default 60 that DENSITY-MECH ran at. 🔴 READ-BACK IS IMPOSSIBLE (no getter among the 26 exports;
        Sec.7.1 A3): the values are SET and RECORDED, never verified by reading. Set AFTER the wrappers are built.
Scene : DENSITY-MECH's, verbatim: the 12-station f-nbr-a scene (stations A-L; E = "Q1AW Q1ABC +05" @1150 Hz; F = "Q1ABC Q1AW RR73"),
        seeds SR.trial_seed(t, part_index), F's true position (E_FREQ+delta, dt+0.16 s). All callsigns are synthetic Q-prefix (NFR-021).
Cells : 14 = DENSITY-MECH's 9 primary (delta {6.25,12,18.75} x X {1,3,6}, E -5) + 3 strong-victim (F +5, E +8) + 2 E+15 (E +15, F +12,
        delta {6.25,12}; part_index 2301/2302). N = 100 trials/cell. ALL 14 ARE GATED (Sec.7.1 A4); the 12-cell variant is reporting only.
Runs  : TWO full runs, A and B, one PROCESS per cell (fixed call order). Readings come from run A; run B exists for ROW 0b.

PER TRIAL (fixed call order, deterministic fields only, one JSON line):
  1. decode DISARMED (E present)                       -> ROW 0b comparator
  2. arm(F true position) ; decode (E present)         -> the ONE production call the readings use
     then read P0, P1 (probe STATUS FIRST, Stage 1 carry-forward), then ft8_get_last_suppression
  3. paired control: arm ; decode with E REMOVED, same seed -> P0_0, P1_0, and F's own applied factor
  P0/P1/P0_0/P1_0 hit  <=>  ft8_ldpc_decode_llrs(llr, max_iters 50, osd_depth 2) returns CRC-OK AND payload == F's.
  prod    = PC._f_recovered(results, F's freq, F's message)   (verbatim reuse).
  pass_F  = 0 if F's result index < pass_counts[0] else 1 (results[] is decode-ordered, verified in Stage 1) ; None if not decoded.
  E's suppression record = record[E's result index] (all_supp[i] and results[i] are appended together in pass 0); guarded per trial by
  supp_n == pass_counts[0].
  excluded cell  <=>  prod <= 0.20.
  control F factor (per trial) = the factor pass 1 APPLIED to F if F was decoded in pass 0 in the control, else 1.0 (F not decoded => not
  suppressed). Fixed by geometry; independent of prod and o1 (Sec.7.2, HK-021(y)). Cell value = median over its 100 trials.
  o1 (Sec.7.1 A2) = P1 hit rate over trials with pass_F != 0. The UNCONDITIONAL rate and the per-cell denominator are reported.

ROW 0 (any fires => STOP, report, NO re-cut)
  0a   SHA-256 of the DLL on disk AND in every run = pin; shim version = 20260053; params SET = (10, 0.10, 40) and recorded; read-back impossible (stated).
  0b   (i) armed-run canonical output == disarmed-run canonical output, EVERY trial, EVERY cell, both runs;
       (ii) run A and run B JSONL files byte-identical (sha256), all 14 cells + the 0d leg.
  0c   AGREEMENT ON THE VERDICT AXIS: over trials (pooled, all 14 cells, run A) with pass_F == 1, the P1 oracle also decodes F in >= 0.95,
       with >= 50 such trials. (One direction only: production-yes => oracle-yes.)
  0d   F alone at -30 dB (E absent, delta 12, part_index 2201): P1_0 hit rate <= 0.20.
  0e-i over EXCLUDED cells whose control median F factor >= 0.90: P1_0 >= 0.90 in each. Fires if any such cell is below 0.90 OR if NO
       excluded cell qualifies (the row may not go decorative).  An excluded cell with control factor < 0.90 is still READ and is flagged.
  0e-ii P0_0 >= 0.90 in EVERY one of the 14 cells.
  0f   n(excluded cells) >= 6.
  0g   (QA-ADDED, STRICTER ONLY -- can turn a verdict into STOP, never into a reading) no probe status != 0 for P0, P1, P1_0 at F's true
       (in-band) position, and supp_n == pass_counts[0] in every trial. Disclosed here, not in the spec.

READINGS (per EXCLUDED cell, on o1)   DIRTY: o1 <= 0.20 | CLEAN: o1 >= 0.80 | MIXED: otherwise
  ROW 1 DIRTY : every excluded cell DIRTY   -> suppression route
  ROW 2 CLEAN : every excluded cell CLEAN   -> candidate-stage route (CLOSED x2) => Captain
  ROW 3 SPLIT : otherwise                   -> full cell map (delta x X x E level, with E's applied factor); NO averaging, NO majority
  The predicate is cmd_verdict() below, verbatim; rows are mutually exclusive.

REPORTING ONLY (gates nothing): per cell prod / P0 / P1 / P1_0 / P0_0 hit rates; paired BER (P1 - P1_0) and (P0 - P1); E's reported SNR
  and APPLIED FACTOR per cell (median, IQR) -- read this BEFORE reading any DIRTY: an E at factor 1.0 means NO suppression was applied;
  pass_F distribution; the 12-cell variant; unconditional o1; and, if the verdict is DIRTY or SPLIT, collateral-vs-residual (BER on F's
  data symbols where E's attenuated bins +-1 overlap F's tone bin vs where they do not).

WHAT THIS CANNOT SEE (Sec.3 + QA): one synthetic 12-station AWGN scene; the probe reads at F's TRUE position, so CLEAN means "decodable
  there", not "pass 1 would rank that lattice point"; it tests no remedy; nhard 40 here vs 60 in DENSITY-MECH (prod rates NOT comparable);
  the control's pass-1 YES test is invalid wherever F is self-suppressed (that is why 0e-i is gated on the control factor);
  params cannot be read back.
PREDICTIONS: the Architect's #3-#6 stand (Sec.7.3). QA writes none.
"""
import argparse
import ctypes
import hashlib
import json
import os
import statistics as st
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
QA_RR = os.path.join(REPO_ROOT, "qa", "rr-study")
for _p in (HERE, os.path.join(QA_RR, "density-mech"), QA_RR, os.path.join(QA_RR, "f-nbr-a"),
           os.path.join(QA_RR, "n1-extract-llrs-at-position"), os.path.join(QA_RR, "r2-coherent-llr-instrument")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import stage1_acceptance as S1  # noqa: E402  (Shim, FT8Result, SuppRec, PINS: the SAME instrument Stage 1 accepted)
import density_mech as DM  # noqa: E402  (scene, cells, seeds, oracle constants: verbatim reuse)
from ldpc_decode_ctypes import LdpcDecodeLLRs, FT8_PAYLOAD_BITS  # noqa: E402
from extract_llrs_ctypes import FTX_LDPC_N, hard_decision_ber  # noqa: E402
import ldpc_decode_ctypes as LDC  # noqa: E402

SR, PC = DM.SR, DM.PC
OUT_ROOT = os.environ.get("DENSITY_P1_OUT") or os.path.join(REPO_ROOT, "artefacts", "density-p1-stage2")   # env override: PLUMBING SMOKE ONLY
DLL_PATH = os.path.join(S1.BIN_DIR, "libft8_NEW.dll")
NEW_SHA, NEW_VER = S1.PINS["NEW"]
LIVE = {"k_min_score_pass2": S1.LIVE_PASS2, "osd_corr_threshold": S1.LIVE_OSD, "osd_nhard_max": S1.LIVE_NHARD}
N_TRIALS = int(os.environ.get("DENSITY_P1_N", "100"))
E_MESSAGE = "Q1AW Q1ABC +05"          # scene_render's station E (load_s8hn_signals)
E15_PART_INDEX_BASE = 2301            # disjoint from DM's 2001-2009 / 2101-2103 / 2201
ROW0D_F_SNR_DB, ROW0D_DELTA_HZ, ROW0D_PART_INDEX = DM.ROW0D_F_SNR_DB, DM.ROW0D_DELTA_HZ, DM.ROW0D_PART_INDEX
BAR_0C, MIN_0C_TRIALS, BAR_0D, BAR_0E, MIN_0F, FACTOR_QUAL = 0.95, 50, 0.20, 0.90, 6, 0.90
PROD_EXCLUDED, DIRTY_MAX, CLEAN_MIN = 0.20, 0.20, 0.80
N_SYM, DATA_SYM_BASE = 79, (7, 43)     # ft8: Costas at 0-6, 36-42, 72-78; 2x29 data symbols


def build_cells():
    cells = [dict(c) for c in DM.build_cells()]                       # 9 primary + 3 strong-victim
    for i, d in enumerate((6.25, 12.0)):                              # E +15 (full suppression), F +12 (X +3)
        cells.append({"group": "e15", "delta_hz": d, "x_db": 3.0, "e_snr_db": 15.0, "f_snr_db": 12.0,
                      "part_index": E15_PART_INDEX_BASE + i})
    for c in cells:
        c["key"] = "%s,%.2f,%.1f" % (c["group"], c["delta_hz"], c["x_db"])
    return cells


# ── one production call, with or without the probe ─────────────────────────────
def decode(sh, pcm, arm=None):
    buf = np.ascontiguousarray(pcm, dtype=np.float32)
    res = (S1.FT8Result * S1.MAX_RESULTS)()
    if arm is not None:
        sh.dll.ft8_set_probe(ctypes.c_float(arm[0]), ctypes.c_float(arm[1]))
    n = sh.dll.ft8_decode_all(buf.ctypes.data_as(ctypes.POINTER(ctypes.c_float)), S1.N_SAMPLES, res, S1.MAX_RESULTS)
    rows = [{"freq_hz": res[i].freq_hz, "dt": float(res[i].dt), "snr": res[i].snr,
             "message": res[i].message.decode("ascii", "replace").strip()} for i in range(max(n, 0))]
    pc = (ctypes.c_int * 8)()
    k = sh.dll.ft8_get_last_pass_counts(pc, 8)
    pcl = [pc[i] for i in range(max(0, min(k, 8)))]
    canon = "|".join("%d,%s,%d,%s" % (r["freq_hz"], S1.fbits(r["dt"]), r["snr"], r["message"]) for r in rows) \
        + "|pc=" + ",".join(map(str, pcl))
    return n, rows, pcl, canon


def read_probe(sh, p):
    out = (ctypes.c_float * S1.N_LLR)()
    rc = sh.dll.ft8_get_probe_llrs(p, out)                       # STATUS FIRST (Stage 1 carry-forward)
    return rc, ([float(x) for x in out] if rc == 0 else None)


def read_supp(sh):
    recs = (S1.SuppRec * S1.K_MAX_CANDIDATES)()
    n = sh.dll.ft8_get_last_suppression(recs, S1.K_MAX_CANDIDATES)
    return n, [(r.freq_offset, r.time_offset, r.freq_sub, r.time_sub, r.snr_db, r.factor) for r in recs[:min(n, S1.K_MAX_CANDIDATES)]]


def oracle(dec, llr, true_bits):
    if llr is None:
        return {"hit": False, "ber": None, "signs": None}
    ber = hard_decision_ber(llr, true_bits)
    res = dec.ldpc_decode_llrs(llr, max_iters=DM.MAX_ITERS, osd_depth=DM.OSD_DEPTH)
    hit = False
    if res["rc"] == 0 and res["a91"] is not None:
        rec = LDC.a91_to_bits(res["a91"], FT8_PAYLOAD_BITS)
        hit = (res["crc_ok"] == 1) and (rec == true_bits[:FT8_PAYLOAD_BITS])
    return {"hit": bool(hit), "ber": ber, "signs": "".join("1" if x > 0.0 else "0" for x in llr)}


def find_msg(rows, freq, msg):
    for i, r in enumerate(rows):
        if abs(r["freq_hz"] - freq) <= PC.FREQ_TOLERANCE_HZ and PC._text_matches(r["message"], msg):
            return i
    return None


def probe_block(sh, dec, true_bits):
    """Reads P0/P1 (status first) and the suppression list of the LAST armed call."""
    out = {}
    for p in (0, 1):
        rc, llr = read_probe(sh, p)
        o = oracle(dec, llr, true_bits)
        out["P%d" % p] = {"rc": rc, "hit": o["hit"], "ber": o["ber"], "signs": o["signs"]}
    out["supp_n"], out["supp"] = read_supp(sh)
    return out


def run_trial(sh, dec, cell, t, full, abl, target, true_bits):
    seed = SR.trial_seed(t, cell["part_index"])
    pcm_full = SR.render_scene(full, seed)
    pcm_abl = SR.render_scene(abl, seed)
    arm = (float(target), float(DM.F_TIME_OFFSET_S))
    # 1) disarmed (ROW 0b's comparator), 2) ARMED = the ONE production call the readings use
    _n0, _r0, _pc0, canon_dis = decode(sh, pcm_full)
    _n1, rows, pcl, canon_arm = decode(sh, pcm_full, arm=arm)
    pb = probe_block(sh, dec, true_bits)
    f_i = find_msg(rows, target, SR.F_TRUE_MESSAGE)
    e_i = find_msg(rows, SR.E_FREQ_HZ, E_MESSAGE)
    n_p0 = pcl[0] if pcl else 0
    supp_map_ok = (pb["supp_n"] == n_p0) if n_p0 < S1.K_MAX_CANDIDATES else True
    e_rec = pb["supp"][e_i] if (e_i is not None and e_i < n_p0 and e_i < len(pb["supp"])) else None
    f_rec = pb["supp"][f_i] if (f_i is not None and f_i < n_p0 and f_i < len(pb["supp"])) else None
    # paired control: same seed, E removed
    _nc, rows_c, pcl_c, _cc = decode(sh, pcm_abl, arm=arm)
    pbc = probe_block(sh, dec, true_bits)
    fc_i = find_msg(rows_c, target, SR.F_TRUE_MESSAGE)
    n_p0c = pcl_c[0] if pcl_c else 0
    fc_rec = pbc["supp"][fc_i] if (fc_i is not None and fc_i < n_p0c and fc_i < len(pbc["supp"])) else None
    return {
        "cell": cell["key"], "t": t, "seed": seed,
        "prod": bool(PC._f_recovered(rows, target, SR.F_TRUE_MESSAGE)),
        "pass_F": (None if f_i is None else (0 if f_i < n_p0 else 1)),
        "pc": pcl, "armed_eq_disarmed": canon_arm == canon_dis, "canon_sha": hashlib.sha256(canon_arm.encode()).hexdigest()[:16],
        "P0": pb["P0"], "P1": pb["P1"], "supp_n": pb["supp_n"], "supp_map_ok": bool(supp_map_ok),
        "E_decoded_p0": e_rec is not None, "E_snr_db": (e_rec[4] if e_rec else None), "E_factor": (e_rec[5] if e_rec else None),
        "E_rec": e_rec, "F_snr_db": (f_rec[4] if f_rec else None), "F_factor": (f_rec[5] if f_rec else None),
        "C_pc": pcl_c, "C_pass_F": (None if fc_i is None else (0 if fc_i < n_p0c else 1)),
        "C_F_factor": (fc_rec[5] if fc_rec else None), "C_F_snr_db": (fc_rec[4] if fc_rec else None),
        "P0_0": pbc["P0"], "P1_0": pbc["P1"],
    }


def make_instrument():
    dec = LdpcDecodeLLRs(DLL_PATH, verify=True, expected_sha256=NEW_SHA, expected_shim_version=NEW_VER)
    sh = S1.Shim(DLL_PATH, "NEW", has_probe=True)
    sh.set_params(LIVE["k_min_score_pass2"])          # ALWAYS after the wrappers are built, never before
    true_bits = dec.true_codeword(SR.F_TRUE_MESSAGE)
    assert true_bits is not None and len(true_bits) == FTX_LDPC_N
    return sh, dec, true_bits


def rate(recs, key, sub=None):
    xs = [(r[key][sub] if sub else r[key]) for r in recs]
    return sum(1 for x in xs if x) / len(xs) if xs else None


def cell_summary(cell, recs):
    n = len(recs)
    fac = sorted(r["E_factor"] for r in recs if r["E_factor"] is not None)
    snr = sorted(r["E_snr_db"] for r in recs if r["E_snr_db"] is not None)
    q = lambda xs, f: (xs[min(len(xs) - 1, int(f * len(xs)))] if xs else None)
    bers = lambda a, b: sorted(x[a]["ber"] - x[b]["ber"] for x in recs if x[a]["ber"] is not None and x[b]["ber"] is not None)
    d10, d01 = bers("P1", "P1_0"), bers("P0", "P1")
    return {"key": cell["key"], "group": cell["group"], "delta_hz": cell["delta_hz"], "x_db": cell["x_db"],
            "e_snr_db": cell["e_snr_db"], "f_snr_db": cell["f_snr_db"], "n": n,
            "prod": sum(r["prod"] for r in recs) / n, "prod_hits": sum(r["prod"] for r in recs),
            "passF0": sum(1 for r in recs if r["pass_F"] == 0), "passF1": sum(1 for r in recs if r["pass_F"] == 1),
            "P0": rate(recs, "P0", "hit"), "P1": rate(recs, "P1", "hit"),
            "P0_0": rate(recs, "P0_0", "hit"), "P1_0": rate(recs, "P1_0", "hit"),
            "probe_rc_bad": sum(1 for r in recs if r["P0"]["rc"] != 0 or r["P1"]["rc"] != 0 or r["P1_0"]["rc"] != 0),
            "armed_ne_disarmed": sum(1 for r in recs if not r["armed_eq_disarmed"]),
            "supp_map_bad": sum(1 for r in recs if not r["supp_map_ok"]),
            "E_decoded_p0": sum(r["E_decoded_p0"] for r in recs),
            "E_factor_median": st.median(fac) if fac else None, "E_factor_q1": q(fac, 0.25), "E_factor_q3": q(fac, 0.75),
            "E_snr_median": st.median(snr) if snr else None,
            "ber_P1_minus_P1_0_median": (st.median(d10) if d10 else None),
            "ber_P0_minus_P1_median": (st.median(d01) if d01 else None),
            "C_passF0": sum(1 for r in recs if r["C_pass_F"] == 0),
            # §7.2: the control's F factor per trial = the factor pass 1 APPLIED to F if F was decoded in pass 0, else 1.0
            # (F not decoded => F not suppressed). Fixed by the cell's geometry; independent of prod and o1.
            "C_F_factor_eff_median": st.median([(r["C_F_factor"] if r["C_F_factor"] is not None else 1.0) for r in recs])}


def cell_signals_for(cell):
    full, abl, target = DM.cell_signals(cell)
    return full, abl, target


def cmd_cell(a):
    cells = build_cells()
    cell = cells[a.idx]
    outdir = os.path.join(OUT_ROOT, "run" + a.run)
    os.makedirs(outdir, exist_ok=True)
    S1.ensure_ignored(os.path.join(outdir, "cell_%02d.jsonl" % a.idx))
    sh, dec, true_bits = make_instrument()
    full, abl, target = cell_signals_for(cell)
    recs = []
    with open(os.path.join(outdir, "cell_%02d.jsonl" % a.idx), "w", newline="\n") as f:
        for t in range(a.n):
            r = run_trial(sh, dec, cell, t, full, abl, target, true_bits)
            recs.append(r)
            f.write(json.dumps(r, sort_keys=True) + "\n")
            if (t + 1) % 25 == 0:
                print("%s cell %d: %d/%d" % (a.run, a.idx, t + 1, a.n), flush=True)
    S = cell_summary(cell, recs)
    S.update({"dll_sha": sh.sha, "version": sh.version, "params_set": LIVE, "params_readback": "IMPOSSIBLE: no getter export"})
    with open(os.path.join(outdir, "cell_%02d.json" % a.idx), "w") as f:
        json.dump(S, f, indent=1, sort_keys=True)
    print("DONE %s cell %d %s: prod=%.2f P0=%.2f P1=%.2f P1_0=%.2f" % (a.run, a.idx, cell["key"], S["prod"], S["P0"], S["P1"], S["P1_0"]), flush=True)


def cmd_row0d(a):
    outdir = os.path.join(OUT_ROOT, "run" + a.run)
    os.makedirs(outdir, exist_ok=True)
    S1.ensure_ignored(os.path.join(outdir, "row0d.jsonl"))
    sh, dec, true_bits = make_instrument()
    base = SR.load_s8hn_signals()
    base = SR.set_station_snr(base, SR.STATION_F, ROW0D_F_SNR_DB)
    target = SR.E_FREQ_HZ + ROW0D_DELTA_HZ
    full = SR.move_station_freq(base, SR.STATION_F, target)
    abl = SR.remove_station(full, SR.STATION_E)
    arm = (float(target), float(DM.F_TIME_OFFSET_S))
    recs = []
    with open(os.path.join(outdir, "row0d.jsonl"), "w", newline="\n") as f:
        for t in range(a.n):
            pcm = SR.render_scene(abl, SR.trial_seed(t, ROW0D_PART_INDEX))
            _n, rows, pcl, _c = decode(sh, pcm, arm=arm)
            pb = probe_block(sh, dec, true_bits)
            r = {"t": t, "P1_0": pb["P1"], "P0_0": pb["P0"], "pc": pcl}
            recs.append(r)
            f.write(json.dumps(r, sort_keys=True) + "\n")
    S = {"n": len(recs), "P1_0_hits": sum(r["P1_0"]["hit"] for r in recs), "P1_0_rate": sum(r["P1_0"]["hit"] for r in recs) / len(recs),
         "P0_0_rate": sum(r["P0_0"]["hit"] for r in recs) / len(recs), "f_snr_db": ROW0D_F_SNR_DB, "probe_rc_bad": sum(1 for r in recs if r["P1_0"]["rc"] != 0)}
    with open(os.path.join(outdir, "row0d.json"), "w") as f:
        json.dump(S, f, indent=1, sort_keys=True)
    print("DONE %s row0d: P1_0=%d/%d" % (a.run, S["P1_0_hits"], S["n"]), flush=True)


def cmd_pilot(a):
    """ROW 0e FEASIBILITY PILOT: control legs ONLY (E removed). Computes NO verdict quantity: no P1 with E present,
    no prod, no o1. Its only purpose is to learn whether the pre-registered ROW 0e can ever be satisfied."""
    cells = build_cells()
    sh, dec, true_bits = make_instrument()
    print("%-22s %6s %6s %8s %10s %9s" % ("cell", "P0_0", "P1_0", "F_pass0", "F_factor", "F_snr"))
    for idx in a.cells:
        cell = cells[idx]
        _full, abl, target = cell_signals_for(cell)
        arm = (float(target), float(DM.F_TIME_OFFSET_S))
        p00 = p10 = f0 = 0
        facs, snrs = [], []
        for t in range(a.n):
            pcm = SR.render_scene(abl, SR.trial_seed(t, cell["part_index"]))
            _n, rows, pcl, _c = decode(sh, pcm, arm=arm)
            pb = probe_block(sh, dec, true_bits)
            p00 += pb["P0"]["hit"]; p10 += pb["P1"]["hit"]
            fi = find_msg(rows, target, SR.F_TRUE_MESSAGE)
            n0 = pcl[0] if pcl else 0
            if fi is not None and fi < n0 and fi < len(pb["supp"]):
                f0 += 1; facs.append(pb["supp"][fi][5]); snrs.append(pb["supp"][fi][4])
        print("%-22s %6.2f %6.2f %5d/%-3d %10s %9s" % (cell["key"], p00 / a.n, p10 / a.n, f0, a.n,
              ("%.3f" % st.median(facs)) if facs else "-", ("%.1f" % st.median(snrs)) if snrs else "-"), flush=True)


def _load_run(run):
    d = os.path.join(OUT_ROOT, "run" + run)
    cells = build_cells()
    summ, recs, shas = {}, {}, {}
    for i, c in enumerate(cells):
        with open(os.path.join(d, "cell_%02d.json" % i)) as f:
            summ[c["key"]] = json.load(f)
        p = os.path.join(d, "cell_%02d.jsonl" % i)
        with open(p) as f:
            recs[c["key"]] = [json.loads(l) for l in f]
        shas[c["key"]] = S1.sha256_file(p)
    with open(os.path.join(d, "row0d.json")) as f:
        r0d = json.load(f)
    shas["row0d"] = S1.sha256_file(os.path.join(d, "row0d.jsonl"))
    return cells, summ, recs, r0d, shas


def _o1(recs):
    """A2: the reading rate is over trials where F was NOT decoded in pass 0 (F still present for pass 1)."""
    sub = [r for r in recs if r["pass_F"] != 0]
    return (sum(r["P1"]["hit"] for r in sub) / len(sub) if sub else None), len(sub)


def _tones(dec, msg):
    buf = (ctypes.c_uint8 * N_SYM)()
    rc = dec.dll.ft8_encode_message(msg.encode("ascii"), buf, N_SYM)
    assert rc == N_SYM
    return list(buf)


def _data_symbol(k):
    return DATA_SYM_BASE[0] + k if k < 29 else DATA_SYM_BASE[1] + (k - 29)


def collateral_vs_residual(dec, cell, recs, true_bits):
    """Reporting only. BER of F's data bits on symbols where E's attenuated bins (E tone +-1) OVERLAP F's tone bin
    vs symbols where they do not, from the pass-1 probe sign bits. Descriptive; gates nothing."""
    tE, tF = _tones(dec, E_MESSAGE), _tones(dec, SR.F_TRUE_MESSAGE)
    errs = {"overlap": [0, 0], "no_overlap": [0, 0]}
    for r in recs:
        if r["pass_F"] == 0 or r["E_rec"] is None or r["P1"]["signs"] is None:
            continue
        e_off = r["E_rec"][0]
        f_off = e_off + int(round(cell["delta_hz"] / 6.25))
        for i in range(FTX_LDPC_N):
            s = _data_symbol(i // 3)
            ov = abs((f_off + tF[s]) - (e_off + tE[s])) <= 1
            k = "overlap" if ov else "no_overlap"
            errs[k][1] += 1
            errs[k][0] += int((r["P1"]["signs"][i] == "1") != bool(true_bits[i]))
    return {k: {"bit_errors": v[0], "bits": v[1], "ber": (v[0] / v[1] if v[1] else None)} for k, v in errs.items()}


def cmd_verdict(a):
    cellsA, sA, rA, r0dA, shaA = _load_run("A")
    _cB, sB, rB, r0dB, shaB = _load_run("B")
    _sh, dec, true_bits = make_instrument()
    keys = [c["key"] for c in cellsA]
    R = {"row0": {}}
    disk_sha = S1.sha256_file(DLL_PATH)
    R["row0"]["0a"] = (disk_sha == NEW_SHA and all(s["dll_sha"] == NEW_SHA and s["version"] == NEW_VER and s["params_set"] == LIVE
                                                     for S in (sA, sB) for s in S.values()))
    R["row0"]["0b"] = (all(s["armed_ne_disarmed"] == 0 for S in (sA, sB) for s in S.values())
                       and all(shaA[k] == shaB[k] for k in shaA))
    pooled = [r for k in keys for r in rA[k] if r["pass_F"] == 1]
    p_agree = (sum(r["P1"]["hit"] for r in pooled) / len(pooled)) if pooled else None
    R["row0"]["0c"] = bool(len(pooled) >= MIN_0C_TRIALS and p_agree is not None and p_agree >= BAR_0C)
    R["row0"]["0d"] = bool(r0dA["P1_0_rate"] <= BAR_0D)
    excl = [k for k in keys if sA[k]["prod"] <= PROD_EXCLUDED]
    # §7.2 0e-i: over excluded cells whose control median F factor >= 0.90, P1_0 >= 0.90 in each; fires if any such
    # cell is below the bar OR if NO excluded cell qualifies (the row may not go decorative).
    qual = [k for k in excl if sA[k]["C_F_factor_eff_median"] >= FACTOR_QUAL]
    R["row0"]["0e_i"] = bool(len(qual) >= 1 and all(sA[k]["P1_0"] >= BAR_0E for k in qual))
    R["row0"]["0e_ii"] = all(sA[k]["P0_0"] >= BAR_0E for k in keys)
    R["row0"]["0f"] = len(excl) >= MIN_0F
    R["row0"]["0g_qa_added"] = all(s["probe_rc_bad"] == 0 and s["supp_map_bad"] == 0 for S in (sA, sB) for s in S.values())
    R["row0_detail"] = {"0c_pooled_pass1_trials": len(pooled), "0c_agreement": p_agree, "0d_P1_0_rate": r0dA["P1_0_rate"],
                        "n_excluded": len(excl), "excluded": excl, "0e_i_qualifying_cells": qual,
                        "0e_i_excluded_but_not_qualifying": [k for k in excl if k not in qual],
                        "control_F_factor_eff_median": {k: sA[k]["C_F_factor_eff_median"] for k in keys}, "dll_disk_sha": disk_sha}
    reads = {}
    for k in excl:
        o1, n_o1 = _o1(rA[k])          # A2: gating o1 = P1 hit rate over trials with pass_F != 0 (denominator reported)
        reads[k] = {"o1": o1, "n_o1": n_o1, "o1_unconditional": sA[k]["P1"],
                    "control_F_factor_lt_0.90_flag": k not in qual,
                    "read": ("MIXED" if o1 is None else "DIRTY" if o1 <= DIRTY_MAX else "CLEAN" if o1 >= CLEAN_MIN else "MIXED")}
    R["readings"] = reads
    if not all(R["row0"].values()):
        R["verdict"] = "ROW 0 STOP: " + ",".join(x for x, v in R["row0"].items() if not v)
    elif all(v["read"] == "DIRTY" for v in reads.values()):
        R["verdict"] = "ROW 1 DIRTY"
    elif all(v["read"] == "CLEAN" for v in reads.values()):
        R["verdict"] = "ROW 2 CLEAN"
    else:
        R["verdict"] = "ROW 3 SPLIT"
    # ---- reporting only ----
    R["reporting"] = {"per_cell": {k: sA[k] for k in keys},
                      "unconditional_o1_excluded": {k: sA[k]["P1"] for k in excl},
                      "row0d": r0dA,
                      "verdict_12_cell_variant_readings": {k: v["read"] for k, v in reads.items() if not k.startswith("e15")}}
    if R["verdict"] in ("ROW 1 DIRTY", "ROW 3 SPLIT"):
        R["reporting"]["collateral_vs_residual"] = {k: collateral_vs_residual(dec, next(c for c in cellsA if c["key"] == k), rA[k], true_bits)
                                                     for k in excl}
    out = os.path.join(OUT_ROOT, "verdict.json")
    S1.ensure_ignored(out)
    with open(out, "w") as f:
        json.dump(R, f, indent=1, sort_keys=True)
    print(json.dumps({k: R[k] for k in ("row0", "row0_detail", "readings", "verdict")}, indent=1, sort_keys=True))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("verdict").set_defaults(fn=cmd_verdict)
    c = sub.add_parser("cell"); c.add_argument("--idx", type=int, required=True); c.add_argument("--run", default="A"); c.add_argument("--n", type=int, default=N_TRIALS); c.set_defaults(fn=cmd_cell)
    r = sub.add_parser("row0d"); r.add_argument("--run", default="A"); r.add_argument("--n", type=int, default=N_TRIALS); r.set_defaults(fn=cmd_row0d)
    p = sub.add_parser("pilot"); p.add_argument("--cells", type=int, nargs="+", required=True); p.add_argument("--n", type=int, default=20); p.set_defaults(fn=cmd_pilot)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
