#!/usr/bin/env python3
"""NHARD40-DEFAULT `CC` ROW 0c -- a second, independent process re-decodes a seeded
300-cycle sample on all three legs and diffs the result element-wise against
part_cc.py's own persisted arrays (spec Sec.2.5 ROW 0c: "an independent process
re-decodes a seeded 300-cycle sample on all 3 legs; per-station-cycle arrays
element-wise identical").

Sample selection (disclosed, not spec-mandated beyond "300 cycles"): round-robin
trial-major / part-minor over all 21 parts (trial 0 of every part, then trial 1 of
every part, etc.), taking the first 300 (part, trial) pairs this way -- spreads the
sample across all 5 families rather than concentrating it in the first parts, same
spirit as part_nt_replay.py's own rung-spanning selection.

This process reconstructs each sampled cycle FROM SCRATCH (same seed formula, same
normalise_rms input contract, same three nhard settings) and never reads part_cc.py's
own per-cycle records until the final comparison. A fresh LdpcDecodeLLRs instance is
constructed here (dll_pin.load_decoder), not shared with the original run's process.

Usage:
    python part_cc_replay.py <cc_json> [n_cycles]        # n_cycles default 300
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
import part_cc as CC  # noqa: E402


def select_sample(parts_data: dict, n_cycles: int):
    pidxs = sorted(parts_data.keys())
    max_t = max(len(parts_data[p]["trials"]) for p in pidxs)
    sample = []
    for t in range(max_t):
        for pidx in pidxs:
            if t < len(parts_data[pidx]["trials"]):
                sample.append((pidx, t))
                if len(sample) >= n_cycles:
                    return sample
    return sample


def main() -> int:
    cc_json = sys.argv[1]
    n_cycles = int(sys.argv[2]) if len(sys.argv) > 2 else 300

    with open(cc_json, "r", encoding="utf-8") as f:
        state = json.load(f)
    parts_data = {int(k): v for k, v in state["parts"].items()}

    sample = select_sample(parts_data, n_cycles)
    print(f"ROW 0c sample: {len(sample)} cycles across "
          f"{len({p for p, _ in sample})} parts")

    scenario_parts = CC.load_scenario()
    scenario_by_index = {p["part_index"]: p for p in scenario_parts}
    message_texts = CC.load_message_texts()

    dec = P.load_decoder(verify=True)
    bind_decode_params(dec.dll)
    truth_bits = CC.build_truth(dec, message_texts)
    print(f"shim={dec.version}", flush=True)

    n_mismatch = 0
    n_checked = 0
    t0 = time.perf_counter()
    for i, (pidx, trial) in enumerate(sample):
        part = scenario_by_index[pidx]
        original_row = parts_data[pidx]["trials"][trial]
        replay_out, msg_ids = CC.run_cycle(dec, message_texts, truth_bits, part,
                                            pidx, trial, CC.LEGS)

        assert msg_ids == original_row["msg_ids"], (pidx, trial, msg_ids, original_row["msg_ids"])
        for leg_name, _ in CC.LEGS:
            n_checked += 1
            if replay_out[leg_name] != original_row[leg_name]:
                n_mismatch += 1
                print(f"  MISMATCH part={pidx} trial={trial} leg={leg_name}: "
                      f"original={original_row[leg_name]} replay={replay_out[leg_name]}")

        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{len(sample)} cycles ({time.perf_counter() - t0:.0f}s)", flush=True)

    total_wall = time.perf_counter() - t0
    print(f"DONE: {n_checked} (cycle,leg) comparisons, {n_mismatch} mismatches, "
          f"wall={total_wall:.0f}s")
    print(f"ROW 0c: {'PASS' if n_mismatch == 0 else 'FAIL'}")
    return 0 if n_mismatch == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
