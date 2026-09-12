#!/usr/bin/env python3
"""NHARD40-DEFAULT `NT` ROW 0c -- a second, independent process re-decodes a seeded
~500-cycle sample on all three legs and diffs the result element-wise against
part_nt.py's own persisted arrays (spec Sec.3.5: "a second process re-decodes a
seeded 500-cycle sample on all 3 legs, arrays identical").

Sample selection (disclosed, not spec-mandated beyond "500 cycles"): round-robin
trial-major / rung-minor over every rung part_nt.py actually produced (nominal PLUS
any extension rungs), i.e. trial 0 of every rung, then trial 1 of every rung, etc.,
taking the first 500 (rung, trial) pairs this way. This spreads the sample across
the whole measured ladder (near-threshold AND both tails) rather than concentrating
it at one end, unlike a flat first-500-cycles selection which would only touch the
lowest 2 rungs (250 trials each) -- a stronger determinism check, closer in spirit
to base ROW 0d's own "diff across the whole run" intent.

This process reconstructs each sampled cycle FROM SCRATCH -- same seed formula
(compute_seed(SCENARIO_ID, rung_index, trial_index)), same normalise_rms input
contract, same three nhard settings -- and never reads part_nt.py's own per-cycle
records until the final comparison. A fresh LdpcDecodeLLRs instance is constructed
here (dll_pin.load_decoder), not shared with the original run's process.

Usage:
    python part_nt_replay.py <nt_json> [n_cycles]        # n_cycles default 500
"""
from __future__ import annotations

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "f-nbr-a"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study"))
sys.path.insert(0, HERE)

import dll_pin as P  # noqa: E402
from row0_bc import bind_decode_params  # noqa: E402
import part_nt as NT  # noqa: E402


def select_sample(rungs: dict, n_cycles: int):
    ridxs = sorted(rungs.keys())
    max_t = max(len(rungs[r]["trials"]) for r in ridxs)
    sample = []
    for t in range(max_t):
        for ridx in ridxs:
            if t < len(rungs[ridx]["trials"]):
                sample.append((ridx, t))
                if len(sample) >= n_cycles:
                    return sample
    return sample


def main() -> int:
    nt_json = sys.argv[1]
    n_cycles = int(sys.argv[2]) if len(sys.argv) > 2 else 500

    with open(nt_json, "r", encoding="utf-8") as f:
        state = json.load(f)
    rungs = {int(k): v for k, v in state["rungs"].items()}

    sample = select_sample(rungs, n_cycles)
    print(f"ROW 0c sample: {len(sample)} cycles across {len({r for r, _ in sample})} rungs")

    dec = P.load_decoder(verify=True)
    bind_decode_params(dec.dll)
    truth_texts, truth_bits = NT.build_truth(dec)
    print(f"shim={dec.version}", flush=True)

    n_mismatch = 0
    n_checked = 0
    t0 = time.perf_counter()
    for i, (ridx, trial) in enumerate(sample):
        db = rungs[ridx]["db"]
        original_row = rungs[ridx]["trials"][trial]
        legs = NT.LEGS if "40" in original_row else (("60", (10, 0.10, 60)),)
        replay_out, msg_id = NT.run_trial(dec, truth_texts, truth_bits, db, ridx, trial, legs)

        assert msg_id == original_row["msg_id"], (ridx, trial, msg_id, original_row["msg_id"])
        for leg_name, _ in legs:
            n_checked += 1
            if replay_out[leg_name] != original_row[leg_name]:
                n_mismatch += 1
                print(f"  MISMATCH rung idx={ridx} db={db:+.1f} trial={trial} leg={leg_name}: "
                      f"original={original_row[leg_name]} replay={replay_out[leg_name]}")

        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{len(sample)} cycles ({time.perf_counter() - t0:.0f}s)", flush=True)

    total_wall = time.perf_counter() - t0
    print(f"DONE: {n_checked} (cycle,leg) comparisons, {n_mismatch} mismatches, "
          f"wall={total_wall:.0f}s")
    print(f"ROW 0c: {'PASS' if n_mismatch == 0 else 'FAIL'}")
    return 0 if n_mismatch == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
