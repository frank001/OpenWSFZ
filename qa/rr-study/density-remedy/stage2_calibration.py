#!/usr/bin/env python
"""DENSITY-REMEDY Stage 2 -- INSTRUMENT CALIBRATION (nominal E level -> the decoder's REPORTED SNR). NOT a verdict run.

Why: spec S14.2 defines the interior-of-ramp coverage in the decoder's REPORTED SNR (S11.3's live RB sub-bands: E in [+5,+9], [+10,+14],
>= +15), but a bench cell is specified by a NOMINAL E level.  The two differ (Stage 1 measured E nominal -5 dB reporting about -4 dB), so the
cell list cannot be fixed by hand-waving; it needs this mapping, measured on seeds that are NEVER classification or measurement seeds.

What it records: ONLY E's reported (integer) SNR, taken from the decoded row for E's message at E's frequency.  It records NO F outcome and
computes no recovery rate, so it cannot peek at the quantity Stage 2 measures.  Decoder: the merged DLL (SHA-256 38a21f84...), params
(10, 0.10, 40) set explicitly, setter NEVER called (V0 path), Delta = 12 Hz, F = E - 3 dB, the ORIGINAL message pair, N = 12 per level,
seeds SR.trial_seed(t, 33000 + level_index).  Levels are a fixed list below.  Output: results/stage2_calibration.json (counts and numbers only).
"""
import json
import os
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stage1_accept_readout as H  # noqa: E402  (re-pinned instrument; sets sys.path for the rr-study helpers)

S1, DM, DP, SR, PC = H.S1, H.DM, H.DP, H.DM.SR, H.DM.PC

LEVELS_DB = [-5.0, 0.0, 5.0, 8.0, 10.0, 12.0, 15.0, 18.0]   # nominal E levels (fixed before the run)
N = 12
PART_BASE = 33000                                            # disjoint from every classification / measurement part_index (asserted in stage2)
DELTA_HZ = 12.0
X_DB = 3.0
E_MESSAGE = "Q1AW Q1ABC +05"


def main():
    sh = S1.Shim(os.path.join(H.BIN_DIR, "libft8_NEW.dll"), "NEW", has_probe=False)
    S1.LIVE_NHARD = 40
    sh.set_params(S1.LIVE_PASS2)                      # (10, 0.10, 40); the suppression setter is NEVER called
    out = {"dll_sha256": sh.sha, "shim_version": sh.version, "delta_hz": DELTA_HZ, "x_db": X_DB, "n_per_level": N, "levels": []}
    for li, e_db in enumerate(LEVELS_DB):
        base = SR.load_s8hn_signals()
        base = SR.set_station_snr(base, SR.STATION_E, e_db)
        base = SR.set_station_snr(base, SR.STATION_F, e_db - X_DB)
        sig = SR.move_station_freq(base, SR.STATION_F, SR.E_FREQ_HZ + DELTA_HZ)
        snrs, missing = [], 0
        for t in range(N):
            pcm = SR.render_scene(sig, SR.trial_seed(t, PART_BASE + li))
            _n, rows, _pcl, _canon = DP.decode(sh, pcm)
            hit = [r for r in rows if abs(r["freq_hz"] - SR.E_FREQ_HZ) <= PC.FREQ_TOLERANCE_HZ and PC._text_matches(r["message"], E_MESSAGE)]
            if hit:
                snrs.append(hit[0]["snr"])
            else:
                missing += 1
        out["levels"].append({"nominal_e_db": e_db, "n": N, "e_not_decoded": missing, "reported_snr_median": (st.median(snrs) if snrs else None),
                              "reported_snr_min": (min(snrs) if snrs else None), "reported_snr_max": (max(snrs) if snrs else None)})
        print("nominal %+5.1f dB -> reported median %s  [%s .. %s]  E not decoded %d/%d" % (
            e_db, out["levels"][-1]["reported_snr_median"], out["levels"][-1]["reported_snr_min"], out["levels"][-1]["reported_snr_max"], missing, N), flush=True)
    p = os.path.join(HERE, "results", "stage2_calibration.json")
    with open(p, "w") as f:
        json.dump(out, f, indent=1)
    print("wrote", p)


if __name__ == "__main__":
    main()
