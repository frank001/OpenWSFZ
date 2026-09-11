#!/usr/bin/env python3
"""OSD-FA-A Part A (PRIMARY, GATED, base spec Sec.5) -- the oracle false-accept rate.

HK-020: 1,000 S8HN cycles (base Sec.2.1), production defaults (10, 0.10, 60, base
Sec.5.1), match on PAYLOAD not displayed text (base Sec.5.1 -- the RR73 finding from
Part D is exactly why: two different bit patterns can render identical text). No +0.16
offset anywhere -- this leg runs the full decoder and extracts nothing (Part D3
acceptance ruling Sec.4 reminder 1).

Reused verbatim (HK-018): scene_render.load_s8hn_signals/render_scene/trial_seed,
dll_pin.load_decoder (current-binary pin).

NFR-021: not engaged -- Q-prefix synthetic scenes only.

Usage:
    python part_a.py <out_json>
"""
from __future__ import annotations

import ctypes
import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "f-nbr-a"))
sys.path.insert(0, HERE)

import dll_pin as P  # noqa: E402
import scene_render as SR  # noqa: E402
from row0_bc import bind_decode_params, DEFAULT_PARAMS  # noqa: E402
from part_d import cycle_clustered_bootstrap_ci  # noqa: E402

N_TRIALS = 1000
BAR = 0.10


def build_truth(dec):
    signals = SR.load_s8hn_signals()
    texts = [s["message_text"] for s in signals]

    def _is_report_or_signoff(tok: str) -> bool:
        if tok in ("RR73", "73", "RRR"):
            return True
        core = tok[1:] if tok and tok[0] in "R+-" else tok
        return core.lstrip("+-").isdigit()

    def _is_grid(tok: str) -> bool:
        return len(tok) == 4 and tok[:2].isalpha() and tok[2:].isdigit()

    for t in texts:
        toks = t.split()
        assert len(toks) == 3, t
        for tok in toks:
            if tok == "CQ" or _is_report_or_signoff(tok) or _is_grid(tok):
                continue
            assert tok.startswith("Q"), (t, tok)  # every callsign-shaped token is Q-prefixed
    bits = {t: dec.true_codeword(t) for t in texts}
    for t, b in bits.items():
        assert b is not None, t
    return texts, bits


def is_true(message: str, truth_texts, truth_bits, dec) -> bool:
    """Match on PAYLOAD, not displayed text (base Sec.5.1)."""
    if message in truth_texts:
        return True
    tb = dec.true_codeword(message)
    if tb is None:
        return False
    return any(tb == v for v in truth_bits.values())


def main() -> int:
    out_json = sys.argv[1]
    if not os.path.realpath(out_json).startswith(
            os.path.join(REPO_ROOT, "artefacts") + os.sep):
        raise SystemExit("refusing to write outside artefacts/ (NFR-021)")

    dec = P.load_decoder(verify=True)
    bind_decode_params(dec.dll)
    dec.dll.ft8_set_decode_params(*DEFAULT_PARAMS)  # set once, before first decode (base Sec.2.5)

    truth_texts, truth_bits = build_truth(dec)
    signals = SR.load_s8hn_signals()

    per_cycle_true, per_cycle_all = [], []
    n_av = 0
    total_decodes = 0
    total_false = 0

    t0 = time.perf_counter()
    for t in range(N_TRIALS):
        seed = SR.trial_seed(t, 0)
        pcm = SR.render_scene(signals, seed)
        decodes = dec.decode_all(pcm)
        if decodes is None:
            n_av += 1
            per_cycle_true.append(0)
            per_cycle_all.append(0)
            continue
        n_true = 0
        for d in decodes:
            ok = is_true(d["message"], truth_texts, truth_bits, dec)
            if ok:
                n_true += 1
            else:
                total_false += 1
        per_cycle_true.append(n_true)
        per_cycle_all.append(len(decodes))
        total_decodes += len(decodes)

        if (t + 1) % 200 == 0:
            print(f"  {t + 1}/{N_TRIALS} trials ({time.perf_counter() - t0:.0f}s)", flush=True)

    total_wall = time.perf_counter() - t0
    # P_fa = FALSE / all -- clustered bootstrap needs per-cycle (false, all), not (true, all).
    per_cycle_false = [a - tr for tr, a in zip(per_cycle_true, per_cycle_all)]
    P_fa = total_false / total_decodes if total_decodes else None
    ci_lo = ci_hi = None
    if total_decodes:
        ci_lo, ci_hi = cycle_clustered_bootstrap_ci(per_cycle_false, per_cycle_all, 2000, 20260911913)

    if ci_hi is not None and ci_hi < BAR:
        row = "A1"
    elif ci_lo is not None and ci_lo > BAR:
        row = "A2"
    else:
        row = "A3"

    out = {
        "n_trials": N_TRIALS, "n_av": n_av, "total_decodes": total_decodes,
        "total_false": total_false, "P_fa": P_fa, "ci_lo": ci_lo, "ci_hi": ci_hi,
        "row": row, "total_wall_s": total_wall,
        "per_cycle_true": per_cycle_true, "per_cycle_all": per_cycle_all,
    }
    tmp = out_json + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f)
    os.replace(tmp, out_json)

    print(f"DONE trials={N_TRIALS} av={n_av} decodes={total_decodes} false={total_false} "
          f"P_fa={P_fa} CI=[{ci_lo},{ci_hi}] ROW={row} wall={total_wall:.0f}s -> {out_json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
