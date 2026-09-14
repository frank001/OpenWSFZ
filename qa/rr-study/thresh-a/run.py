#!/usr/bin/env python3
"""THRESH-A: isolated-threshold candidate-vs-bits split.

Spec: qa/rr-study/2026-09-12-1724-architect-to-qa-spec-thresh-a-isolated-threshold-locus.md

NT's scene, verbatim (part_nt.py's MESSAGES/compute_seed('NHARD40-NT', ...)/
normalise_rms), on the osd-fa-a-pinned current binary (6b2e16a6..., shim 20260050).
Two legs per cycle, one process, one thread (spec sec.2):
  P (production): decode_all(pcm) at (10, 0.10, 60) -- NT's own control leg.
  F (forced): row0._forced_success(dec, pcm, f_inj, msg_text, true_dt_s=0.0) --
              reused verbatim from f-nbr-a (HK-018), which applies dll_common's
              +0.16s waterfall-origin correction internally.

All 21 nominal rungs get the P leg (so ROW 0b can reproduce NT's committed
per-rung genuine counts exactly). Only the 5 primary rungs R* = -21.0..-19.0 dB
also get the F leg, every trial regardless of P's own outcome (M = R*-misses,
H = R*-hits are both computed AFTER, from the same per-trial P-leg record).

Persists per-rung, per-cycle records (spec: "so a second process can diff them
... and every number in the report is reproducible from its own JSON").

NFR-021: Q-prefix synthetic messages only (part_nt.MESSAGES).

Usage:
    python run.py <out_json>                      # phase 1 (all 21 rungs, P leg;
                                                     R* rungs also get F leg)
    python run.py <out_json> --topup <rung,rung>   # one extra 250-trial block on
                                                     named R* rungs (dB), continuing
                                                     that rung's own trial counter
"""
from __future__ import annotations

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "osd-fa-a"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "f-nbr-a"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study"))
sys.path.insert(0, HERE)

import numpy as np  # noqa: E402

import dll_pin as P  # noqa: E402  (osd-fa-a's own -- current-binary pin)
from row0 import _forced_success  # noqa: E402  (f-nbr-a, reused verbatim)
from part_nt import MESSAGES, build_truth, rung_index, rung_db  # noqa: E402
from part_a import is_true  # noqa: E402
from part_b import FREQ_TOL_HZ  # noqa: E402
from harness.common import compute_seed  # noqa: E402
import scene_render as SR  # noqa: E402

SCENARIO_ID = "NHARD40-NT"          # NT's scene, verbatim (same seed namespace)
PROD_TARGET_RMS = 0.20
TRIALS_PER_RUNG = 250
P_PARAMS = (10, 0.10, 60)           # production, NT's control leg

# NT's committed per-rung genuine counts, all 21 nominal rungs (-26.0..-16.0),
# reproduced independently here (ROW 0b), not trusted from the spec's own prose.
NT_COMMITTED_COUNTS = [0, 0, 0, 0, 0, 0, 0, 1, 0, 5, 30, 78, 155, 207, 234,
                       248, 250, 250, 250, 250, 250]

R_STAR_DB = [-21.0, -20.5, -20.0, -19.5, -19.0]  # fixed from NT's committed table (HK-021(y))

MAX_TOPUP_BLOCKS = 2


def normalise_rms(pcm: np.ndarray, target: float = PROD_TARGET_RMS) -> np.ndarray:
    src_rms = float(np.sqrt(np.mean(pcm.astype(np.float64) ** 2)))
    if src_rms < 1e-6:
        return pcm
    return (pcm * (target / src_rms)).astype(np.float64)


def run_trial(dec, truth_texts, truth_bits, db, ridx, trial, want_forced):
    msg_id, msg_text, freq_hz = MESSAGES[trial % 4]
    seed = compute_seed(SCENARIO_ID, ridx, trial)
    signal = [{"station": "N", "message_text": msg_text, "freq_hz": freq_hz,
               "snr_db": db, "dt_s": 0.0}]
    raw = SR.render_scene(signal, seed)
    pcm = normalise_rms(raw, PROD_TARGET_RMS)

    dec.dll.ft8_set_decode_params(*P_PARAMS)
    decodes = dec.decode_all(pcm) or []
    genuine_p = any(
        is_true(d["message"], truth_texts, truth_bits, dec) and abs(d["freq_hz"] - freq_hz) <= FREQ_TOL_HZ
        for d in decodes)
    row = {"trial": trial, "msg_id": msg_id, "genuine_p": genuine_p, "n_decodes": len(decodes)}

    if want_forced:
        r = _forced_success(dec, pcm, freq_hz, msg_text, true_dt_s=0.0)
        row["forced"] = r

    return row


def main() -> int:
    out_json = sys.argv[1]
    if not os.path.realpath(out_json).startswith(os.path.join(REPO_ROOT, "artefacts") + os.sep):
        raise SystemExit("refusing to write outside artefacts/ (NFR-021)")

    def log(msg):
        print(msg, flush=True)

    dec = P.load_decoder(verify=True)  # ROW 0a
    truth_texts, truth_bits = build_truth(dec)
    log(f"ROW 0a: PASS (shim={dec.version})")

    r_star_idx = {rung_index(db) for db in R_STAR_DB}

    if os.path.isfile(out_json):
        with open(out_json, "r", encoding="utf-8") as f:
            state = json.load(f)
        rungs_data = {int(k): v for k, v in state["rungs"].items()}
        log(f"resuming from existing {out_json}: {len(rungs_data)} rungs present")
    else:
        rungs_data = {}
        state = {"scenario_id": SCENARIO_ID, "r_star_db": R_STAR_DB,
                 "nt_committed_counts": NT_COMMITTED_COUNTS,
                 "topup_blocks": {}, "wall_s_total": 0.0}

    wall_s_baseline = state.get("wall_s_total", 0.0)
    t_start = time.perf_counter()

    def save():
        state["rungs"] = {str(k): v for k, v in rungs_data.items()}
        state["wall_s_total"] = wall_s_baseline + (time.perf_counter() - t_start)
        tmp = out_json + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f)
        os.replace(tmp, out_json)

    # --- --topup mode: one extra 250-trial block on named R* rungs ---
    if len(sys.argv) > 2 and sys.argv[2] == "--topup":
        rung_dbs = [float(x) for x in sys.argv[3].split(",")]
        for db in rung_dbs:
            ridx = rung_index(db)
            if ridx not in r_star_idx:
                raise SystemExit(f"--topup: {db} dB is not an R* rung")
            rec = rungs_data.get(ridx)
            if rec is None:
                raise SystemExit(f"--topup: rung {db} has no phase-1 data yet")
            n_done = state["topup_blocks"].get(str(ridx), 0)
            if n_done >= MAX_TOPUP_BLOCKS:
                log(f"rung {db}: MAX_TOPUP_BLOCKS reached, skipping")
                continue
            start = len(rec["trials"])
            t0 = time.perf_counter()
            for t in range(start, start + TRIALS_PER_RUNG):
                rec["trials"].append(run_trial(dec, truth_texts, truth_bits, db, ridx, t, True))
            state["topup_blocks"][str(ridx)] = n_done + 1
            save()
            log(f"  topup rung db={db:+.1f} trials {start}..{start + TRIALS_PER_RUNG - 1} "
                f"({time.perf_counter() - t0:.0f}s)")
        log(f"DONE (topup) -> {out_json}")
        return 0

    # --- Phase 1: all 21 nominal rungs, P leg; R* rungs also get F leg ---
    n_nominal = len(NT_COMMITTED_COUNTS)
    for i in range(n_nominal):
        db = rung_db(i)
        rec = rungs_data.setdefault(i, {"db": db, "trials": []})
        if len(rec["trials"]) >= TRIALS_PER_RUNG:
            log(f"  rung idx={i} db={db:+.1f} already complete, skipping")
            continue
        want_forced = i in r_star_idx
        t0 = time.perf_counter()
        start = len(rec["trials"])
        for t in range(start, TRIALS_PER_RUNG):
            rec["trials"].append(run_trial(dec, truth_texts, truth_bits, db, i, t, want_forced))
        save()
        n_genuine = sum(1 for row in rec["trials"] if row["genuine_p"])
        log(f"  rung idx={i} db={db:+.1f} P-genuine={n_genuine}/{TRIALS_PER_RUNG} "
            f"forced={'yes' if want_forced else 'no'} ({time.perf_counter() - t0:.0f}s)")

    save()
    log(f"DONE phase 1 -> {out_json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
