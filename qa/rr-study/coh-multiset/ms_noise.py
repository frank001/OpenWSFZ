#!/usr/bin/env python3
"""COH-MULTISET noise leg (spec section 7, DESCRIPTIVE; HK-026: this leg has read 0 at every setting ever tried, so it bounds gross failure only and cannot rank sets).

The 200 scored pure-noise WAVs of NHARD-REP (label NHARD-REP-PC, indices 1..200; index 0 is the warm-up and is not used), each verified against the per-file SHA-256 pins in
results/2026-10-06-nhard-rep/selection.json. 10 seeded positions per WAV (seed 20261024): carrier uniform integer Hz in [500, 2500], ws_dt uniform in [-0.3, 0.8] s
(anchor t = ws_dt + 0.7, as for real rows). At each position: G (nine lattice cells, BP then OSD depth 2), C3 (BP only), and C1/J2/J3/N1 each BP-only and BP+OSD, all from C3's
estimate. Reported: CRC-valid outputs per arm (there is no truth in noise, so every CRC-valid output is a false decode). Numbers only.

  python qa/rr-study/coh-multiset/ms_noise.py --out <result.json> [--dll <dll>]
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ms_run as R  # noqa: E402
import ms_metrics as MM  # noqa: E402
import fine_sync as FS  # noqa: E402
import lattice  # noqa: E402
import wavio  # noqa: E402

CG = R.CG
NOISE_DIR = r"D:\Projects\claude\OpenWSFZ\artefacts\rr_2026-10-06_nhard_rep\noise"
NH_SEL = os.path.join(CG.REPO_ROOT, "qa", "rr-study", "results", "2026-10-06-nhard-rep", "selection.json")
POSITIONS = 10
SEED = 20261024
F_LO, F_HI = 500, 2500
DT_LO, DT_HI = -0.3, 0.8
assert (POSITIONS, SEED) == (10, 20261024)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--dll", default=r"D:\Projects\claude\_qa-scratch\coh-multiset\bin\libft8.dll")
    a = ap.parse_args()
    dec = R.load_decoder(a.dll)
    sel = json.load(open(NH_SEL))
    pins = sel["noise"]["wav_sha256"]
    stamps = sorted(pins)[1:201]
    assert len(stamps) == 200
    n = collections.Counter()
    total = 0
    for k, stamp in enumerate(stamps):
        path = os.path.join(NOISE_DIR, stamp + ".wav")
        assert CG.file_sha256(path) == pins[stamp], ("noise WAV differs from its pin", stamp)
        pcm = wavio.load_cycle_pcm(path)
        rng = np.random.default_rng([SEED, k])
        for _ in range(POSITIONS):
            f = float(rng.integers(F_LO, F_HI + 1))
            t = float(rng.uniform(DT_LO, DT_HI)) + CG.DELTA_S
            total += 1
            g_any = 0
            for cell in lattice.snap_and_neighbours(f, t):
                rc, llr = dec.extract_at(pcm, cell["freq_hz"], cell["time_offset_s"])
                if rc == 0:
                    r = R.decode(dec, llr, CG.OSD_DEPTH)
                    if r["rc"] == 0 and r["crc_ok"] == 1:
                        g_any = 1
                        n["G_bp_or_osd"] += 1
                        n["G_osd_path1"] += int(r["path"] == 1)
                        break
            est = FS.estimate(pcm, f, t)
            X = MM.spectra(pcm, f, t, est)
            v3 = CG.coherent_llrs(pcm, f, t, est)["V3"]
            arms = {"C3": v3}
            arms.update({name: MM.SETS[name](X) for name in MM.ORDER})
            for name, v in arms.items():
                r = R.decode(dec, v, -1)
                n[f"{name}_bp"] += int(r["rc"] == 0 and r["crc_ok"] == 1 and r["path"] == 0)
                r = R.decode(dec, v, CG.OSD_DEPTH)
                ok = r["rc"] == 0 and r["crc_ok"] == 1
                n[f"{name}_bp_or_osd"] += int(ok)
                n[f"{name}_osd_path1"] += int(ok and r["path"] == 1)
    out = {"noise_wavs": 200, "positions_per_wav": POSITIONS, "positions_total": total, "seed": SEED, "dll_pin": R.DLL_PIN, "crc_valid_outputs": dict(sorted(n.items())),
           "reading": "descriptive only (HK-026): zero here bounds gross failure and cannot rank sets"}
    json.dump(out, open(a.out, "w"), indent=1, sort_keys=True)
    print(json.dumps(out, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
