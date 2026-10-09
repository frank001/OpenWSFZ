#!/usr/bin/env python3
"""COH-GAIN row V2 (spec section 6): 200 synthetic isolated signals, OFF-LATTICE on purpose, rendered by our own modulator (scene_render).

Guards the history's stall 1 (a one-symbol origin error, rounding, a lattice-reconstructed frequency): the coherent arms are only trusted on real audio
once they decode CLEAN signals whose true carrier/time sit between lattice points.

Construction (frozen in synthetic_set.json BEFORE any real-audio extraction; Q-prefix synthetic messages only, NFR-021):
  - nominal carrier f_nom: uniform integer Hz in [500, 2500] (WSJT-X logs whole Hz), nominal symbol time dt_nom: uniform in [0.2, 1.0] s (modulator convention);
  - the ANCHOR is the centre lattice cell of (f_nom, dt_nom + 0.16 s) exactly as GAP-LOCATE's lattice.snap_and_neighbours defines it, and this SAME anchor is
    handed to G (which snaps and reads its 9 cells) and to the coherent arms (which search +-2 Hz / +-0.12 s around it): the same anchor mapping as real rows;
  - the TRUE carrier is anchor + df_off, df_off ~ U[-1.5, +1.5] Hz, the TRUE time offset is anchor + dt_off, dt_off ~ U[-0.06, +0.06] s;
  - nominal SNR -14 dB (well above our threshold), one shared seeded AWGN floor, normalise_rms(., 0.20) as production does.
Seeds: compute_seed('COH-GAIN-V2', 0, i).
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cg_common as CG  # noqa: E402

sys.path.insert(0, os.path.join(CG.RR, "f-nbr-a"))
sys.path.insert(0, CG.RR)
import scene_render as SR  # noqa: E402
from harness.common import compute_seed  # noqa: E402
import lattice  # noqa: E402
import wavio  # noqa: E402

LABEL = "COH-GAIN-V2"
LABEL_T = "COH-GAIN-V2T"        # AMENDMENT 1: the descriptive -20 dB tier
MESSAGES = ["CQ Q1ABC FN42", "Q4XYZ Q1ABC -07", "Q1ABC Q4XYZ FN42", "Q5DEF Q1ABC +03", "Q1ABC Q4XYZ RR73", "CQ Q2DEF FN31"]
SET_PATH = os.path.join(HERE, "synthetic_set.json")
SET_T_PATH = os.path.join(HERE, "synthetic_set_t.json")


def build_set(label: str = LABEL, n: int = CG.V2_N, snr_db: float = CG.V2_SNR_DB) -> list:
    out = []
    for i in range(n):
        rng = np.random.default_rng(compute_seed(label, 0, i))
        f_nom = int(rng.integers(500, 2501))
        dt_nom = float(rng.uniform(0.2, 1.0))
        centre = lattice.snap_and_neighbours(float(f_nom), dt_nom + lattice.SYMBOL_PERIOD_S)[0]
        df_off = float(rng.uniform(-CG.V2_DF_MAX_HZ, CG.V2_DF_MAX_HZ))
        dt_off = float(rng.uniform(-CG.V2_DT_MAX_S, CG.V2_DT_MAX_S))
        out.append({"i": i, "message": MESSAGES[i % len(MESSAGES)], "anchor_f": centre["freq_hz"], "anchor_t": centre["time_offset_s"],
                    "df_off": df_off, "dt_off": dt_off, "snr_db": snr_db, "seed": compute_seed(label, 1, i)})
    return out


def serialise(spec: list) -> bytes:
    return (json.dumps(spec, indent=1, sort_keys=True) + "\n").encode("utf-8")


def render_signal(s: dict) -> np.ndarray:
    """True carrier = anchor_f + df_off; modulator dt_s = (anchor_t + dt_off) - 0.16 (extraction convention is dt_s + 0.16)."""
    sig = [{"station": "N", "message_text": s["message"], "freq_hz": s["anchor_f"] + s["df_off"], "snr_db": s["snr_db"],
            "dt_s": s["anchor_t"] + s["dt_off"] - lattice.SYMBOL_PERIOD_S}]
    raw = SR.render_scene(sig, s["seed"])
    return wavio.normalise_rms(np.asarray(raw, dtype=np.float32), wavio.PROD_TARGET_RMS)


def evaluate(dec, s: dict) -> dict:
    """Numeric record for one synthetic signal: arms' success plus the estimator's error against the TRUE offsets."""
    pcm = render_signal(s)
    r = CG.evaluate_signal(dec, pcm, s["anchor_f"], s["anchor_t"], s["message"])
    if r.get("fault"):
        return {"i": s["i"], "fault": 1}
    r["i"] = s["i"]
    r["err_df"] = abs(r["C3_df"] - s["df_off"])
    r["err_dt"] = abs(r["C3_dt"] - s["dt_off"])
    r["err_df_oracle"] = abs(r["C3S_df"] - s["df_off"])
    r["err_dt_oracle"] = abs(r["C3S_dt"] - s["dt_off"])
    return r


def main() -> int:
    import hashlib
    for path, spec in ((SET_PATH, build_set()), (SET_T_PATH, build_set(LABEL_T, CG.V2T_N, CG.V2T_SNR_DB))):
        data = serialise(spec)
        with open(path, "wb") as fh:
            fh.write(data)
        print("wrote", path, "n =", len(spec), "sha256(LF)", hashlib.sha256(data).hexdigest())
    return 0


if __name__ == "__main__":
    sys.exit(main())
