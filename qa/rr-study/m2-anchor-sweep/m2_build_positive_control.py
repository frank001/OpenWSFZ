#!/usr/bin/env python3
"""M2 -- build the mandatory 400-row positive control.

Spec 4.1: "synthetic FT8 signals from the existing QA encoder-only synth, injected
at known (f, dt) into real captured WAV noise from this corpus, run through the
identical M2 sweep path... without it, 'HIT does not concentrate' cannot be
distinguished from 'the harness is miswired' (HK-022)."

Design: for each control row, pick a real captured 15 s WAV (a basis cycle -- both
ALL.TXTs present in-window, WAV on disk, same set M1 already validated) as the noise
floor, then inject a clean synthesised FT8 tone at a lattice frequency drawn away
from any REAL reported signal in that cycle (>=50 Hz, same exclusion M1's NULL arm
uses) plus a small in-aperture offset -- the exact (freq_offset, time_offset) grid
r1-sync-refiner/population.py already validated the instrument against, so the one
thing under test here is real noise vs synthetic AWGN, nothing else.

This module only builds the deterministic MANIFEST (no PCM is rendered or persisted
here -- population.py's on-demand-render precedent). m2_run_harness.py renders each
control row's PCM at run time via m2_synth.render_control_pcm().
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from m2_common import (  # noqa: E402
    CONTROL_BASE_DT_S, CONTROL_BASE_EXCLUSION_HZ, CONTROL_BASE_FREQ_BAND_HZ,
    CONTROL_BASE_MAX_ATTEMPTS, CONTROL_FREQ_OFFSETS_HZ, CONTROL_SNR_DB_LEVELS,
    CONTROL_TIME_OFFSETS_S, M2_SEED, N_CONTROL_PER_LEVEL, OWSFZ_ALL_TXT,
    OWSFZ_WAV_DIR, RESULTS_DIR, WINDOW, WSJTX_ALL_TXT, assert_field_mapping,
    control_message_for_index, load_all_txt, write_json,
)

MANIFEST_PATH = os.path.join(RESULTS_DIR, "m2_control_manifest.json")

# Distinct RNG stream from M2's real-population draw (m2_build_population.py
# consumes M2_SEED directly) -- offset so the two draws don't interleave/collide.
CONTROL_SEED = M2_SEED + 1_000_000


def build():
    assert_field_mapping()
    lo, hi = WINDOW

    owsfz_by_ts = load_all_txt(OWSFZ_ALL_TXT, lo, hi)
    wsjtx_by_ts = load_all_txt(WSJTX_ALL_TXT, lo, hi)
    wav_ts = {fn[:-4] for fn in os.listdir(OWSFZ_WAV_DIR) if fn.endswith(".wav")}

    # HK-018/R0-D3: sorted intersection, never a raw set walk -- identical basis
    # construction to m1_build_population.py's cycle_keys.
    basis_cycles = sorted(set(owsfz_by_ts) & set(wsjtx_by_ts) & wav_ts)
    print("basis cycles available as noise-floor sources: %d" % len(basis_cycles))

    def all_freqs_for_cycle(ts: str) -> list[float]:
        entries = owsfz_by_ts.get(ts, []) + wsjtx_by_ts.get(ts, [])
        return [f for (_m, _s, _d, f) in entries]

    n_total = N_CONTROL_PER_LEVEL * len(CONTROL_SNR_DB_LEVELS)
    rng = np.random.default_rng(CONTROL_SEED)

    # Draw n_total distinct background cycles without replacement, deterministically.
    bg_pick = rng.choice(len(basis_cycles), size=n_total, replace=False)
    bg_cycles = [basis_cycles[i] for i in sorted(bg_pick.tolist())]
    # Re-shuffle assignment order (independent draw) so cycle order isn't correlated
    # with sorted trial order -- but keep it deterministic.
    rng.shuffle(bg_cycles)

    grid_combos = [(f, t) for f in CONTROL_FREQ_OFFSETS_HZ for t in CONTROL_TIME_OFFSETS_S]  # 81, fixed order

    rows = []
    trial_index = 0
    n_exclusion_failures = 0
    for snr_db in CONTROL_SNR_DB_LEVELS:
        for i in range(N_CONTROL_PER_LEVEL):
            bg_ts = bg_cycles[trial_index]
            exclude_freqs = all_freqs_for_cycle(bg_ts)

            base_freq_hz = None
            for _attempt in range(CONTROL_BASE_MAX_ATTEMPTS):
                cand = float(round(rng.uniform(*CONTROL_BASE_FREQ_BAND_HZ)))
                if all(abs(cand - f) >= CONTROL_BASE_EXCLUSION_HZ for f in exclude_freqs):
                    base_freq_hz = cand
                    break
            if base_freq_hz is None:
                n_exclusion_failures += 1
                # Fall back to band centre -- vanishingly rare (band is 2400 Hz wide);
                # recorded so it's auditable, not silently accepted.
                base_freq_hz = 1500.0

            freq_offset_hz, time_offset_s = grid_combos[trial_index % len(grid_combos)]

            rows.append({
                "trial_index": trial_index, "population": "control",
                "cycle_id": bg_ts, "target_snr_db": snr_db,
                "base_freq_hz": base_freq_hz, "base_dt_s": CONTROL_BASE_DT_S,
                "freq_offset_hz": freq_offset_hz, "time_offset_s": time_offset_s,
                "true_freq_hz": base_freq_hz + freq_offset_hz,
                "true_dt_s": CONTROL_BASE_DT_S + time_offset_s,
                "message": control_message_for_index(trial_index),
                "render_seed": CONTROL_SEED + 1 + trial_index,
            })
            trial_index += 1

    print("control rows built: %d (exclusion-band fallbacks: %d)" % (len(rows), n_exclusion_failures))

    manifest = {
        "spec": "2026-08-15-1301-architect-to-qa-m1-ruling-and-m2-anchor-sweep-spec.md",
        "seed": CONTROL_SEED, "window": list(WINDOW),
        "snr_db_levels": list(CONTROL_SNR_DB_LEVELS),
        "n_per_level": N_CONTROL_PER_LEVEL,
        "n_exclusion_failures": n_exclusion_failures,
        "n_rows": len(rows),
        "rows": rows,
    }
    os.makedirs(RESULTS_DIR, exist_ok=True)
    write_json(MANIFEST_PATH, manifest)
    print("manifest written: %s" % MANIFEST_PATH)


if __name__ == "__main__":
    build()
