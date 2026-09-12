#!/usr/bin/env python3
"""OSD-FA-A Part B (GATED, base spec Sec.6) -- what does the gate actually remove?

Re-decodes the IDENTICAL rendered PCM from Part A (same 1,000 trials, same seeds via
scene_render.trial_seed -- HK-018, not re-rendered) with the gate disabled (base
Sec.2.5): k_min_score_pass2=10 (UNCHANGED -- moving it would confound the contrast),
osd_corr_threshold=-1.0, osd_nhard_max=174 (unreachable -- FTX_LDPC_N=174).

Match on PAYLOAD (base Sec.5.1, base Sec.6.1's own "(payload, freq within +-4.0 Hz)"),
not displayed text.

No +0.16 offset -- runs the full decoder, extracts nothing (Part D3 acceptance ruling
Sec.4 reminder 1).

Usage:
    python part_b.py <out_json>
"""
from __future__ import annotations

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "f-nbr-a"))
sys.path.insert(0, HERE)

import dll_pin as P  # noqa: E402
import scene_render as SR  # noqa: E402
from row0_bc import bind_decode_params, DEFAULT_PARAMS  # noqa: E402
from part_a import build_truth, N_TRIALS  # noqa: E402
from part_d import cycle_clustered_bootstrap_ci  # noqa: E402

GATE_OFF_PARAMS = (10, -1.0, 174)
FREQ_TOL_HZ = 4.0
POWER_FLOOR = 100  # base Sec.6.2


def payload_key(message: str, dec, truth_bits) -> tuple | None:
    """Returns a hashable payload key (the true_codeword bits as a tuple) for matching,
    or None if the text can't be re-encoded (e.g. a hash-miss placeholder -- not
    expected in this Q-only synthetic population, but guarded)."""
    tb = dec.true_codeword(message)
    if tb is None:
        return None
    return tuple(tb)


def main() -> int:
    out_json = sys.argv[1]
    if not os.path.realpath(out_json).startswith(
            os.path.join(REPO_ROOT, "artefacts") + os.sep):
        raise SystemExit("refusing to write outside artefacts/ (NFR-021)")

    dec = P.load_decoder(verify=True)
    bind_decode_params(dec.dll)
    truth_texts, truth_bits = build_truth(dec)
    truth_key_set = {tuple(v) for v in truth_bits.values()}
    signals = SR.load_s8hn_signals()

    n_caught = 0        # junk correctly removed (gate-off only, not in truth)
    n_killed = 0         # genuine decode the gate destroyed (gate-off only, in truth)
    n_gate_on_only = 0    # present gate-ON, absent gate-OFF (should be rare -- disclose)
    total_gate_on = 0
    total_gate_off = 0
    per_cycle_killed, per_cycle_removed = [], []  # for Q_gate's clustered CI

    t0 = time.perf_counter()
    for t in range(N_TRIALS):
        seed = SR.trial_seed(t, 0)
        pcm = SR.render_scene(signals, seed)

        dec.dll.ft8_set_decode_params(*DEFAULT_PARAMS)
        gate_on = dec.decode_all(pcm) or []
        dec.dll.ft8_set_decode_params(*GATE_OFF_PARAMS)
        gate_off = dec.decode_all(pcm) or []

        total_gate_on += len(gate_on)
        total_gate_off += len(gate_off)

        # Build (payload_key, freq) lists for both legs.
        on_keys = [(payload_key(d["message"], dec, truth_bits), d["freq_hz"]) for d in gate_on]
        off_keys = [(payload_key(d["message"], dec, truth_bits), d["freq_hz"]) for d in gate_off]

        # present gate-OFF, absent gate-ON: match by (payload, |Δf|<=4Hz), consume on match.
        on_remaining = list(on_keys)
        cycle_killed = cycle_removed = 0
        for key, freq in off_keys:
            match_idx = None
            for i, (k2, f2) in enumerate(on_remaining):
                if k2 == key and abs(f2 - freq) <= FREQ_TOL_HZ:
                    match_idx = i
                    break
            if match_idx is not None:
                on_remaining.pop(match_idx)
                continue  # present in both legs -- not a gate-off-only decode
            # present gate-OFF, absent gate-ON:
            cycle_removed += 1
            if key in truth_key_set:
                n_killed += 1
                cycle_killed += 1
            else:
                n_caught += 1
        # whatever's left in on_remaining was present gate-ON but absent gate-OFF.
        n_gate_on_only += len(on_remaining)

        per_cycle_killed.append(cycle_killed)
        per_cycle_removed.append(cycle_removed)

        if (t + 1) % 200 == 0:
            print(f"  {t + 1}/{N_TRIALS} trials ({time.perf_counter() - t0:.0f}s)", flush=True)

    total_wall = time.perf_counter() - t0
    n_removed = n_killed + n_caught
    Q_gate = n_killed / n_removed if n_removed else None
    ci_lo = ci_hi = None
    if n_removed >= POWER_FLOOR:
        ci_lo, ci_hi = cycle_clustered_bootstrap_ci(per_cycle_killed, per_cycle_removed, 2000, 20260911914)

    if n_removed < POWER_FLOOR:
        row = "B3"
    elif ci_hi is not None and ci_hi < 0.05:
        row = "B1"
    elif ci_lo is not None and ci_lo > 0.20:
        row = "B2"
    else:
        row = "B3"

    out = {
        "n_trials": N_TRIALS, "total_gate_on": total_gate_on, "total_gate_off": total_gate_off,
        "n_gate_on_only": n_gate_on_only, "n_caught": n_caught, "n_killed": n_killed,
        "n_removed": n_removed, "Q_gate": Q_gate, "ci_lo": ci_lo, "ci_hi": ci_hi,
        "row": row, "total_wall_s": total_wall,
        "per_cycle_killed": per_cycle_killed, "per_cycle_removed": per_cycle_removed,
    }
    tmp = out_json + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f)
    os.replace(tmp, out_json)

    print(f"DONE gate_on={total_gate_on} gate_off={total_gate_off} gate_on_only={n_gate_on_only} "
          f"caught={n_caught} killed={n_killed} removed={n_removed} Q_gate={Q_gate} "
          f"CI=[{ci_lo},{ci_hi}] ROW={row} wall={total_wall:.0f}s -> {out_json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
