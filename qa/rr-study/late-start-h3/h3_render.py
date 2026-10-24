"""H3 renders + the A1.1 placement check (required before any decode).

    python h3_render.py --manifest M --out <render dir> --report <placement.json>

Reuses the harness synthesiser and the lateness-edge noise convention (imported, not rewritten):
synth.encoder.encode_message (extended=True), synth.channel.add_awgn, run_scenario._finalize_playback_samples,
lateness-edge/render.py reference_sigma (ONE sigma from an untruncated unit render at DT 0, so the SNR label does not
depend on how much of the clip a style removes: HK-026).

Placement check (per clean, noise-free clip): cross-correlate against the DT = 0 render and assert the measured lag:
  O at t: +(t - 0.5) s;  A: 0 s (leading part absent);  M: +1.86 s;  F: +(t - 0.5) s. Tolerance 2 ms.
Structure asserts: A and M are exactly zero before t, the first RAMP_N samples after t rise monotonically from 0
(raised cosine), and from t + RAMP_N on A/M equal the unramped source; O is cut at the slot end; at t <= 2.36 s the
three styles are bit-identical.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RR = HERE.parent
sys.path.insert(0, str(RR))
sys.path.insert(0, str(RR / "lateness-edge"))
sys.path.insert(0, str(HERE))
import h3_design as H  # noqa: E402
import render as LR    # noqa: E402  (lateness-edge/render.py)

SLOT_N = int(H.SLOT_S * H.FS)
LAG_TOL_S = 0.002
assert LR.CUTOFF_HZ == H.CUTOFF_HZ


def source(dt_s: float) -> np.ndarray:
    """Clean unit-amplitude clip placed at slot time dt_s in a 15 s buffer; the part beyond the slot end is cut."""
    buf, bs = LR.clean_render(H.TEXT, H.FREQ_HZ, dt_s - H.NOMINAL_S)     # clean_render takes L = dt - 0.5
    off = int(round(bs * H.FS))
    full = np.zeros(max(SLOT_N, off + len(buf)))
    full[off:off + len(buf)] = buf
    return full[:SLOT_N].copy()


def ramp() -> np.ndarray:
    i = np.arange(H.RAMP_N)
    return 0.5 * (1.0 - np.cos(np.pi * i / (H.RAMP_N - 1)))      # the C# helper: 0.5 x (1 - cos(pi x i / 239))


def clean(style: str, t: float) -> np.ndarray:
    if style in ("O", "F"):
        return source(t)
    if style == "A":
        dt0, play_at = H.NOMINAL_S, int(round(H.NOMINAL_S * H.FS)) + H.skip_samples(t)
    elif style == "M":
        dt0, play_at = H.M_DT_S, int(round(t * H.FS))
    else:
        raise ValueError(style)
    x = source(dt0)
    x[:play_at] = 0.0
    x[play_at:play_at + H.RAMP_N] *= ramp()
    return x


def _lag_s(x: np.ndarray, ref: np.ndarray) -> float:
    k = LR._xcorr_peak(x[::LR.DECIM].astype("float64"), ref[::LR.DECIM].astype("float64"))
    return k * LR.DECIM / H.FS


def check_placement(style: str, t: float, x: np.ndarray, ref0: np.ndarray, ref_src: dict) -> dict:
    expect = {"O": t - H.NOMINAL_S, "F": t - H.NOMINAL_S, "A": 0.0, "M": H.M_DT_S - H.NOMINAL_S}[style]
    lag = _lag_s(x, ref0)
    row = {"style": style, "t": t, "expected_lag_s": expect, "measured_lag_s": lag,
           "lag_err_ms": abs(lag - expect) * 1000.0, "ok_lag": bool(abs(lag - expect) <= LAG_TOL_S)}
    if style in ("A", "M"):
        play_at = (int(round(H.NOMINAL_S * H.FS)) + H.skip_samples(t)) if style == "A" else int(round(t * H.FS))
        src = ref_src[H.NOMINAL_S if style == "A" else H.M_DT_S]
        r = ramp()
        row["ok_zero_before_t"] = bool(np.all(x[:play_at] == 0.0))
        row["ok_ramp"] = bool(np.allclose(x[play_at:play_at + H.RAMP_N], src[play_at:play_at + H.RAMP_N] * r)
                              and x[play_at] == 0.0 and np.all(np.diff(r) > 0))
        row["ok_rest_identical"] = bool(np.array_equal(x[play_at + H.RAMP_N:], src[play_at + H.RAMP_N:]))
        row["samples_loaded_equiv"] = int(H.TX_N - (play_at - (int(round(H.NOMINAL_S * H.FS)) if style == "A"
                                                                else int(round(H.M_DT_S * H.FS)))))
        row["energy_kept"] = float(np.sum(x ** 2) / np.sum(src ** 2))
    else:
        row["energy_kept"] = float(np.sum(x ** 2) / np.sum(ref0 ** 2))
        row["ok_tail_cut"] = bool(len(x) == SLOT_N)
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--report", required=True)
    a = ap.parse_args()
    from synth import channel
    from harness import run_scenario as rs

    man = json.loads(Path(a.manifest).read_text(encoding="utf-8"))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    sigma = LR.reference_sigma()
    ref0 = source(H.NOMINAL_S)
    ref_src = {H.NOMINAL_S: ref0, H.M_DT_S: source(H.M_DT_S)}

    # clean renders and the placement check, once per (style, t)
    rows, clean_cache, fail = [], {}, []
    for cyc in man["cycles"]:
        key = (cyc["style"], cyc["t"])
        if key in clean_cache:
            continue
        x = clean(*key)
        clean_cache[key] = x
        row = check_placement(*key, x, ref0, ref_src)
        rows.append(row)
        if not all(v for k, v in row.items() if k.startswith("ok_")):
            fail.append(row)
    # at t <= 2.36 s the three styles are one audio: R1 skips 0 samples and applies no ramp, and the clip must fit whole
    for t in H.T_FULL:
        assert H.skip_samples(t) == 0
        e = float(np.sum(clean_cache[("F", t)] ** 2) / np.sum(ref0 ** 2))
        if abs(e - 1.0) > 1e-9:                      # t = 2.36 s ends exactly at the slot end: still whole
            fail.append({"t": t, "full_clip_energy": e})

    index = {}
    sigmas = set()
    for cyc in man["cycles"]:
        x = clean_cache[(cyc["style"], cyc["t"])]
        mixed = (10.0 ** (cyc["snr"] / 20.0)) * x
        noisy = channel.add_awgn(mixed, sigma, cyc["noise_seed"], noise_cutoff_hz=H.CUTOFF_HZ, sample_rate_hz=H.FS)
        final = rs._finalize_playback_samples(noisy)
        assert len(final) == SLOT_N
        sigmas.add(sigma)
        np.save(out / f"cycle_{cyc['cycle']:03d}.npy", final)
        index[str(cyc["cycle"])] = {"sha256": hashlib.sha256(final.tobytes()).hexdigest(), "n": int(len(final))}

    report = {"sigma": sigma, "A1_1_placement": {"tolerance_ms": LAG_TOL_S * 1000, "rows": rows,
                                                  "max_lag_err_ms": max(r["lag_err_ms"] for r in rows),
                                                  "fail": fail, "PASS": not fail},
              "renders": index}
    Path(a.report).write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"A1_1_PASS": not fail, "n_rows": len(rows), "max_lag_err_ms": round(report["A1_1_placement"]["max_lag_err_ms"], 4),
                      "sigma": sigma, "cycles": len(index)}))


if __name__ == "__main__":
    main()
