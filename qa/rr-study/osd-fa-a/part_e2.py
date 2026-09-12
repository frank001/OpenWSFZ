#!/usr/bin/env python3
"""OSD-FA-A E2 (Amendment 1 sec.5.2) -- genuine cost of nhard 60->40 under oracle truth.

Identical PCM to Part A (S8HN, 1,000 cycles, same seeds), decoded at nhard 60 (control)
and 40 (treatment). Pairing key (payload, freq +-4.0 Hz), reused from part_b.py's own
gate-on/gate-off diff (HK-018) -- here comparing 60 vs 40 instead of 60 vs gate-fully-off.

  N_killed40 = genuine decodes (payload in truth) present at 60, absent at 40.
  N_caught40 = false decodes (payload not in truth) present at 60, absent at 40.
  Q40 = N_killed40 / (N_killed40 + N_caught40), cycle-clustered CI.

Rows are Part B's, verbatim (base Sec.6.3): E2-B1 CI_hi<0.05, E2-B2 CI_lo>0.20,
E2-B3 otherwise or <100 removals.

Also reports: genuine decodes lost per 1,000 cycles, and decodes present at 40 but
absent at 60 (expected ~0; any excess is a disclosed confound, base Sec.6.1).

Disclosed consistency check (not a gate, per the Architect's E1/E2 note): the 60-leg's
totals should reproduce Part A's own 12,143/1,143.

DISCLOSED (E1 acceptance ruling sec.3 -- E1 used the same scheme, ruled harmless, one
of the two schemes the ruling accepts): ft8_set_decode_params is called TWICE PER
TRIAL, alternating 60/40, in one process, one thread -- between complete, synchronous
decode_all() returns, never while a decode is in flight. Base Sec.2.5 / Amendment 1
Sec.5's literal "set before the first decode, never mid-run" is written for a single
setting per run; this leg (like E1) switches settings between complete decodes on one
thread, which the E1 ruling confirms is safe (the shim's own documented hazard is a
race between a module-level WRITE and a thread-pool READ DURING a decode -- impossible
here, single thread, no decode in flight when the setter runs) and matches production's
own hot-apply behaviour (Program.cs:867).

Per-cycle killed/removed arrays are persisted (not just aggregate scalars) so
determinism can be DIFFED across two runs, not inferred from matching summary counts
(Architect's E1 acceptance ruling sec.3, "Determinism wording" note).

No +0.16 offset -- runs the full decoder, extracts nothing.

Usage:
    python part_e2.py <out_json>
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
from part_a import build_truth, is_true, N_TRIALS  # noqa: E402
from part_b import payload_key, FREQ_TOL_HZ, POWER_FLOOR  # noqa: E402
from part_d import cycle_clustered_bootstrap_ci  # noqa: E402

NHARD_TREATMENT_PARAMS = (10, 0.10, 40)


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

    n_killed = n_caught = n_60_only_gained_at_40 = 0
    total_60 = total_40 = 0
    per_cycle_killed, per_cycle_removed = [], []

    t0 = time.perf_counter()
    for t in range(N_TRIALS):
        seed = SR.trial_seed(t, 0)
        pcm = SR.render_scene(signals, seed)

        dec.dll.ft8_set_decode_params(*DEFAULT_PARAMS)
        leg60 = dec.decode_all(pcm) or []
        dec.dll.ft8_set_decode_params(*NHARD_TREATMENT_PARAMS)
        leg40 = dec.decode_all(pcm) or []

        total_60 += len(leg60)
        total_40 += len(leg40)

        keys60 = [(payload_key(d["message"], dec, truth_bits), d["freq_hz"]) for d in leg60]
        keys40 = [(payload_key(d["message"], dec, truth_bits), d["freq_hz"]) for d in leg40]

        remaining60 = list(keys60)
        cycle_killed = cycle_removed = 0
        for key, freq in keys40:
            match_idx = None
            for i, (k2, f2) in enumerate(remaining60):
                if k2 == key and abs(f2 - freq) <= FREQ_TOL_HZ:
                    match_idx = i
                    break
            if match_idx is not None:
                remaining60.pop(match_idx)
                continue
            # present at 40, absent at 60 -- expected ~0; a confound if not.
            n_60_only_gained_at_40 += 1
        # whatever's left in remaining60 was present at 60, absent at 40.
        for key, freq in remaining60:
            cycle_removed += 1
            if key in truth_key_set:
                n_killed += 1
                cycle_killed += 1
            else:
                n_caught += 1

        per_cycle_killed.append(cycle_killed)
        per_cycle_removed.append(cycle_removed)

        if (t + 1) % 200 == 0:
            print(f"  {t + 1}/{N_TRIALS} trials ({time.perf_counter() - t0:.0f}s)", flush=True)

    total_wall = time.perf_counter() - t0
    n_removed = n_killed + n_caught
    Q40 = n_killed / n_removed if n_removed else None
    ci_lo = ci_hi = None
    if n_removed >= POWER_FLOOR:
        ci_lo, ci_hi = cycle_clustered_bootstrap_ci(per_cycle_killed, per_cycle_removed, 2000, 20260911920)

    if n_removed < POWER_FLOOR:
        row = "E2-B3"
    elif ci_hi is not None and ci_hi < 0.05:
        row = "E2-B1"
    elif ci_lo is not None and ci_lo > 0.20:
        row = "E2-B2"
    else:
        row = "E2-B3"

    genuine_lost_per_1000 = n_killed / N_TRIALS * 1000

    # Disclosed consistency check (not a gate): does the 60-leg reproduce Part A's own
    # totals (12,143 decodes, 1,143 false)?
    part_a_json_path = os.path.join(REPO_ROOT, "artefacts", "2026-09-11-osd-fa-a-part-a",
                                     "part_a.json")
    consistency = None
    if os.path.isfile(part_a_json_path):
        with open(part_a_json_path, "r", encoding="utf-8") as f:
            pa = json.load(f)
        consistency = {"part_a_total_decodes": pa["total_decodes"], "e2_total_60": total_60,
                        "match": pa["total_decodes"] == total_60}

    out = {
        "n_trials": N_TRIALS, "total_60": total_60, "total_40": total_40,
        "n_60_only_gained_at_40": n_60_only_gained_at_40, "n_caught": n_caught,
        "n_killed": n_killed, "n_removed": n_removed, "Q40": Q40, "ci_lo": ci_lo, "ci_hi": ci_hi,
        "row": row, "genuine_lost_per_1000_cycles": genuine_lost_per_1000,
        "consistency_check_vs_part_a": consistency, "total_wall_s": total_wall,
        "per_cycle_killed": per_cycle_killed, "per_cycle_removed": per_cycle_removed,
    }
    tmp = out_json + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    os.replace(tmp, out_json)

    print(f"DONE total_60={total_60} total_40={total_40} gained_at_40={n_60_only_gained_at_40} "
          f"caught={n_caught} killed={n_killed} removed={n_removed} Q40={Q40} "
          f"CI=[{ci_lo},{ci_hi}] ROW={row} genuine_lost/1000={genuine_lost_per_1000} "
          f"consistency={consistency} wall={total_wall:.0f}s -> {out_json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
