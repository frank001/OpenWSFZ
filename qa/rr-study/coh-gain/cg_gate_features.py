#!/usr/bin/env python
"""COH-GAIN Q-GATE (QA's proposal to the Architect, UNRULED until his spec): per-output strength / consistency features, computable in the product with no truth, no WSJT-X and no other decoder.

  F1  costas_snr_db        the coherent 21-symbol Costas peak over the MEDIAN of the same (df, dt) surface, in dB. SATURATES above ~0 dB (found by test; kept as a peak-to-sidelobe measure only).
  F1b costas_snr_noise_ref_db  the same peak over the median of the same peak at 24 far-off reference frequencies: the data-free strength of the signal at the anchor, rising with signal strength (the gate's F1).
  F2  tone_match_fraction  for a CRC-valid C3 output: the share of the 58 DATA symbols whose strongest tone at the C3 estimate equals the tone of the DECODED message (a data-aided consistency check).
  F3  tone_energy_ratio    mean energy at the decoded data tones over mean energy at the 21 Costas tones (the same idea in energy).

The decoded message's tones are rebuilt from its 77-bit PAYLOAD alone (CRC-14 + LDPC encode + the Gray map: sub-feas/ldpc_encode.py), which the product also has after a decode. Nothing here reads a truth,
a label or ALL.TXT. NO feature has been looked at against any outcome on the real rows: that waits for the pre-registered spec (HK-021).
"""
from __future__ import annotations

import importlib
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cg_common as CG  # noqa: E402
import fine_sync as FS  # noqa: E402

CE = FS.CE


def _load_ldpc_encode():
    """sub-feas/ldpc_encode.py imports a sibling module called 'common': put sub-feas FIRST while importing it, then restore sys.path (another 'common' exists elsewhere on the path)."""
    sub = os.path.join(CG.REPO_ROOT, "qa", "rr-study", "sub-feas")
    saved = list(sys.path)
    saved_mod = sys.modules.pop("common", None)
    sys.path.insert(0, sub)
    try:
        return importlib.import_module("ldpc_encode")
    finally:
        sys.path[:] = saved
        sys.modules.pop("common", None)
        if saved_mod is not None:
            sys.modules["common"] = saved_mod


LE = _load_ldpc_encode()


def costas_snr_db(pcm, anchor_f: float, anchor_t: float) -> float:
    """F1. Peak of the data-free Costas surface over its own median, in dB. A pure-noise surface sits near its median-relative maxima (a few dB); a strong signal is far above."""
    bb = CE.downconvert_decimate(pcm, anchor_f)
    surf = FS.objective_surface(bb, anchor_t, FS.SYNC_SYMBOLS)
    med = float(np.median(surf))
    return float(20.0 * np.log10(float(surf.max()) / med)) if med > 0 else float("inf")


NOISE_OFFSETS_HZ = tuple(sign * (40.0 + 10.0 * k) for k in range(12) for sign in (-1, 1))      # +-40 ... +-150 Hz: 24 reference positions, well clear of the 50 Hz signal bandwidth


def costas_snr_noise_ref_db(pcm, anchor_f: float, anchor_t: float) -> float:
    """F1b (replaces F1 as the strength estimate). The anchor's Costas peak over the MEDIAN of the same peak measured at 24 reference frequencies far from the signal (the same data-free statistic where no
    signal of ours sits, so a robust noise-floor reference even if a few of them hit other stations). F1 (peak over the median of its OWN surface) saturates above about 0 dB, because a strong signal's sidelobes
    fill the whole surface and lift its median; this one keeps rising with strength."""
    def peak(f):
        return float(FS.objective_surface(CE.downconvert_decimate(pcm, f), anchor_t, FS.SYNC_SYMBOLS).max())
    ref = float(np.median([peak(anchor_f + d) for d in NOISE_OFFSETS_HZ if 200.0 <= anchor_f + d <= 3000.0] or [float("nan")]))
    return float(20.0 * np.log10(peak(anchor_f) / ref)) if ref > 0 else float("inf")


def decoded_tones(payload77) -> list:
    """The 79 tones of the message a 77-bit payload encodes (CRC-14, LDPC(174,91) systematic encode, Gray map)."""
    return LE.codeword174_to_tones(LE.encode174_bits(list(payload77)))


def _x_matrix(pcm, anchor_f, anchor_t, est):
    bb = CE.downconvert_decimate(pcm, anchor_f + est["est_df_hz"])
    return CE.correlate_symbols(bb, FS.symbol_start_samples(FS.anchor_dt_for_step(anchor_t, est["dt_step"])))


def tone_features(pcm, anchor_f, anchor_t, est, payload77) -> dict:
    """F2 and F3 for a decoded payload, at the C3 estimate `est` (fine_sync.estimate's dict)."""
    tones = decoded_tones(payload77)
    X = _x_matrix(pcm, anchor_f, anchor_t, est)
    e = np.abs(X) ** 2                                              # (79, 8) energy per symbol per tone
    data = CE.DATA_SYM_IDX
    match = sum(1 for p in data if int(np.argmax(e[p])) == int(tones[p]))
    d_en = float(np.mean([e[p, int(tones[p])] for p in data]))
    s_en = float(np.mean([e[p, t] for p, t in FS.SYNC_SYMBOLS.items()]))
    return {"tone_match_fraction": match / len(data), "tone_energy_ratio": (d_en / s_en) if s_en > 0 else float("inf")}
