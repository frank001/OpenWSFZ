#!/usr/bin/env python3
"""M1 -- build the HIT/MISS/NULL population manifest.

Spec S3/S4. Basis: cycles present in BOTH ALL.TXTs within the corpus's decisive
18.96h window, with a matching owsfz WAV on disk. `<...>`-bearing messages
excluded; 200-3000 Hz only (applied to WSJT-X's own reported frequency, the
basis-defining leg, per T1 precedent). Both real arms anchored at WSJT-X's
reported (freq, DT) -- deliberately not our own, per spec S4's own wording.

HIT   = message decoded by both, this cycle.
MISS  = message decoded by WSJT-X only, this cycle.
NULL  = K=4 positions/cycle: freq drawn uniform 200-3000 Hz, >=50 Hz from ANY
        reported decode in that cycle (union of both legs' frequencies, the
        conservative reading -- avoids ever landing near a real signal on
        either side); DT AND its SNR label inherited together from one
        uniformly-drawn row of this cycle's own (HIT union MISS) pool -- this
        is what "the cycle's own hit/miss DT empirical distribution" means
        operationalised, and it is what gives a NULL row a well-defined SNR
        stratum for the matched-SNR ROW 0c check (spec S2's trap applies
        symmetrically to HIT-vs-NULL, not just HIT-vs-MISS).

NFR-021: message text is used in memory only, for the HIT/MISS text-match
test, and is NEVER written into the manifest or any other tracked artefact --
only counts, frequencies, DTs, SNRs and cycle timestamps are persisted.

No src/ change, no capture run (spec S8).
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from m1_common import (  # noqa: E402
    BAND_LO_HZ, BAND_HI_HZ, OWSFZ_ALL_TXT, WSJTX_ALL_TXT, OWSFZ_WAV_DIR,
    WINDOW, SEED, assert_field_mapping, has_unresolved_hash, load_all_txt,
    owsfz_wav_path, write_json,
)

K_NULL_PER_CYCLE = 4
NULL_EXCLUSION_HZ = 50.0
NULL_MAX_ATTEMPTS = 2000

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
MANIFEST_PATH = os.path.join(RESULTS_DIR, "m1_manifest.json")


def in_band_no_hash(entries):
    return [(m, s, d, f) for (m, s, d, f) in entries
            if not has_unresolved_hash(m) and BAND_LO_HZ <= f <= BAND_HI_HZ]


def no_hash_only(entries):
    """For the owsfz-side match set: hash exclusion applies (unreliable text),
    but NOT the WSJT-X-anchored band filter (that filter is defined against the
    reference leg's own frequency, per T1 precedent; owsfz's frequency is not
    the basis-defining one here)."""
    return {m for (m, s, d, f) in entries if not has_unresolved_hash(m)}


def build():
    assert_field_mapping()
    lo, hi = WINDOW

    owsfz_by_ts = load_all_txt(OWSFZ_ALL_TXT, lo, hi)
    wsjtx_by_ts = load_all_txt(WSJTX_ALL_TXT, lo, hi)

    wav_ts = {fn[:-4] for fn in os.listdir(OWSFZ_WAV_DIR) if fn.endswith(".wav")}

    # HK-018/R0-D3 discipline: sort, never iterate a raw set.
    cycle_keys = sorted(set(owsfz_by_ts) & set(wsjtx_by_ts) & wav_ts)

    print("cycles in window (owsfz)         : %d" % len(owsfz_by_ts))
    print("cycles in window (wsjt-x)         : %d" % len(wsjtx_by_ts))
    print("cycles with owsfz WAV on disk      : %d" % len(wav_ts & (set(owsfz_by_ts) | set(wsjtx_by_ts))))
    print("basis cycles (A n B n WAV)         : %d" % len(cycle_keys))

    rows = []
    trial_index = 0
    n_hit = n_miss = n_null = 0
    n_excl_hash_wsjtx = n_excl_band_wsjtx = 0
    cycles_no_null_pool = 0

    rng = np.random.default_rng(SEED)  # single stream, consumed in fixed cycle order

    for ts in cycle_keys:
        wsjtx_entries = wsjtx_by_ts[ts]
        owsfz_entries = owsfz_by_ts[ts]

        # Basis exclusions counted against the raw wsjtx entries for this cycle.
        for (m, s, d, f) in wsjtx_entries:
            if has_unresolved_hash(m):
                n_excl_hash_wsjtx += 1
            elif not (BAND_LO_HZ <= f <= BAND_HI_HZ):
                n_excl_band_wsjtx += 1

        wsjtx_pool = in_band_no_hash(wsjtx_entries)          # basis-filtered reference pool
        owsfz_msgs = no_hash_only(owsfz_entries)             # match set (text only)

        all_freqs_this_cycle = [f for (_, _, _, f) in wsjtx_entries] + \
                                [f for (_, _, _, f) in owsfz_entries]

        for (msg, snr_db, dt_s, freq_hz) in wsjtx_pool:
            arm = "HIT" if msg in owsfz_msgs else "MISS"
            rows.append({
                "trial_index": trial_index, "cycle_id": ts, "arm": arm,
                "anchor_freq_hz": freq_hz, "anchor_dt_s": dt_s, "snr_db": snr_db,
            })
            trial_index += 1
            if arm == "HIT":
                n_hit += 1
            else:
                n_miss += 1

        if not wsjtx_pool:
            cycles_no_null_pool += 1
            continue

        for _ in range(K_NULL_PER_CYCLE):
            # DT + SNR label inherited together from one uniformly-drawn pool row.
            src_idx = int(rng.integers(0, len(wsjtx_pool)))
            _, src_snr, src_dt, _ = wsjtx_pool[src_idx]

            null_freq = None
            for _attempt in range(NULL_MAX_ATTEMPTS):
                # Rounded to integer Hz here (not left float) so the manifest records
                # exactly the coarse_freq_hz value the refiner will actually be called
                # with -- ft8_refine_candidate's coarse_freq_hz parameter is int, and
                # WSJT-X's own reported frequencies (the HIT/MISS anchors) are integer
                # Hz too, so this keeps all three arms on the same granularity.
                cand = float(round(rng.uniform(BAND_LO_HZ, BAND_HI_HZ)))
                if all(abs(cand - f) >= NULL_EXCLUSION_HZ for f in all_freqs_this_cycle):
                    null_freq = cand
                    break
            if null_freq is None:
                # Exhausted -- band is 2800 Hz wide, this cycle's exclusion zones would
                # have to cover essentially the whole band. Record and skip rather than
                # silently accept a contaminated draw.
                continue

            rows.append({
                "trial_index": trial_index, "cycle_id": ts, "arm": "NULL",
                "anchor_freq_hz": null_freq, "anchor_dt_s": src_dt, "snr_db": src_snr,
            })
            trial_index += 1
            n_null += 1

    print("\nexclusions (wsjt-x pool): <...> hash = %d ; out-of-band = %d"
          % (n_excl_hash_wsjtx, n_excl_band_wsjtx))
    print("cycles with empty basis-filtered pool (no NULL drawn): %d" % cycles_no_null_pool)
    print("\nrows: HIT=%d MISS=%d NULL=%d  total=%d" % (n_hit, n_miss, n_null, len(rows)))

    manifest = {
        "spec": "2026-08-14-2217-architect-to-qa-spec-m1-sync-limited-or-extraction-limited.md",
        "seed": SEED, "window": list(WINDOW),
        "n_cycles_basis": len(cycle_keys),
        "n_hit": n_hit, "n_miss": n_miss, "n_null": n_null,
        "n_excl_hash_wsjtx": n_excl_hash_wsjtx, "n_excl_band_wsjtx": n_excl_band_wsjtx,
        "cycles_no_null_pool": cycles_no_null_pool,
        "rows": rows,
    }
    os.makedirs(RESULTS_DIR, exist_ok=True)
    write_json(MANIFEST_PATH, manifest)
    print("\nmanifest written: %s" % MANIFEST_PATH)


if __name__ == "__main__":
    build()
