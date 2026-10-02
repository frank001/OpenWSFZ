"""LATENESS / EDGE test: renders, and the two pre-playback validity rows P1 and P2.

    python render.py --manifest <manifest.json> --out <render dir> --report <p1p2.json> [--cycles a:b]

Reuses the harness (imported, not rewritten): synth.encoder.encode_message (-> modulate with
extended=True), synth.channel.add_awgn, run_scenario._finalize_playback_samples.

NOISE FLOOR (deviation from `channel.mix_to_shared_floor`, which the spec says to reuse):
  synth/channel.py:196 sets the floor from the mean power of clean_signals[0]'s WHOLE array. Here
  the first signal can be truncated at the slot end or shifted, so that power, and therefore every
  cell's SNR label, would change with L (an HK-026 defect). Instead: scale each unit-amplitude
  clean signal by 10**(snr/20) (channel.py:189-191), sum them, and call channel.add_awgn
  (channel.py:123) with ONE sigma taken from an untruncated unit render at L = 0 in a 15 s slot
  (the S4 convention). The sigma is asserted identical in every one of the 204 cycles.
Noise convention: bandlimited at 4 700 Hz (run_scenario._NOISE_CUTOFF_HZ), the S4/S8 multi-signal
convention (16 simultaneous signals is the S4 case).
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
sys.path.insert(0, str(HERE))
import design as D  # noqa: E402

LAG_TOL_S = 0.002                 # P1 (spec section 4)
CUTOFF_HZ = 4700.0
assert CUTOFF_HZ == 4700.0
REF_TEXT, REF_FREQ_HZ = "Q1ABC Q2DEF FN42", 1500.0
SLOT_N = int(D.SLOT_S * D.FS)                      # 720 000
EARLY_N = int((D.SLOT_S + D.EARLY_ARM_S) * D.FS)   # 864 000: from -3.0 s to +15.0 s
DECIM = 4


def _lower_priority() -> None:
    try:
        import ctypes
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
    except Exception:
        pass


def clean_render(text: str, freq_hz: float, L: float):
    """(unit-amplitude clean array, buffer_start_s) at lateness L, via the harness synthesiser."""
    from synth import encoder
    buf, bs = encoder.encode_message(text, base_freq_hz=float(freq_hz), dt_s=D.dt_for_L(L),
                                     snr_db=None, sample_rate_hz=D.FS, extended=True)
    return buf, bs


def reference_sigma() -> float:
    from synth import channel
    unit, bs = clean_render(REF_TEXT, REF_FREQ_HZ, 0.0)
    assert bs == 0.0 and len(unit) == SLOT_N
    return channel.noise_sigma_for_snr(unit, 0.0, D.FS)


def cycle_seed(index: int) -> int:
    return int(hashlib.sha256(f"lateness|{D.SEED}|{index}".encode()).hexdigest()[:8], 16) % (2 ** 31)


# --------------------------------------------------------------------------- P1
def _xcorr_peak(x: np.ndarray, y: np.ndarray):
    """k (fractional, samples) maximising c[k] = sum x[m+k] y[m]."""
    n = 1 << int(np.ceil(np.log2(len(x) + len(y))))
    c = np.fft.irfft(np.fft.rfft(x, n) * np.conj(np.fft.rfft(y, n)), n)
    lags = np.arange(-(len(y) - 1), len(x))
    cc = c[lags % n]
    i = int(np.argmax(cc))
    if 0 < i < len(cc) - 1:
        a, b, d = cc[i - 1], cc[i], cc[i + 1]
        den = a - 2 * b + d
        frac = 0.5 * (a - d) / den if den != 0 else 0.0
    else:
        frac = 0.0
    return lags[i] + frac


def p1_lag_error_s(text: str, freq_hz: float, L: float) -> float:
    """|estimated lateness - label| in seconds, from the cross-correlation lag between the clean,
    UNTRUNCATED render at L and its own L = 0 render (the spec's P1)."""
    xL, bsL = clean_render(text, freq_hz, L)
    x0, bs0 = clean_render(text, freq_hz, 0.0)
    k = _xcorr_peak(xL[::DECIM].astype("float64"), x0[::DECIM].astype("float64"))
    L_hat = (bsL - bs0) + k * DECIM / D.FS
    return abs(L_hat - L)


# --------------------------------------------------------------------------- one cycle
def render_cycle(design: dict, index: int, sigma: float):
    """Return (float32 playback buffer after finalise, info dict) for a planted cycle."""
    from synth import channel
    import numpy as np
    from harness import run_scenario as rs

    cyc = design["cycles"][index]
    sigs = [design["signals"][i] for i in cyc["signals"]]
    late = cyc["block"] == "LATE"
    n = SLOT_N if late else EARLY_N
    origin_s = 0.0 if late else -D.EARLY_ARM_S
    mixed = np.zeros(n, dtype="float64")
    p2 = []
    for s in sigs:
        buf, bs = clean_render(s["text"], s["freq_hz"], s["L_s"])
        off = int(round((bs - origin_s) * D.FS))
        assert off >= 0, f"signal {s['sig_id']} starts before the buffer"
        energy_full = float(np.sum(buf ** 2))
        if late:
            full = np.zeros(max(n, off + len(buf)))
            full[off:off + len(buf)] = buf
            cut = full[:n].copy()
            tail_max = float(np.max(np.abs(full[n:] * 0.0))) if len(full) > n else 0.0   # post-cut region is not mixed
            # P2 (late): after truncation, nothing lies beyond the slot end; before it, identical.
            beyond = np.zeros(len(full))
            beyond[:n] = cut
            ok_zero = float(np.max(np.abs(beyond[n:]))) == 0.0 if len(beyond) > n else True
            ok_ident = bool(np.array_equal(cut, full[:n]))
            will_cut = s["L_s"] > D.CUT_ONSET_S
            p2.append({"sig_id": s["sig_id"], "L": s["L_s"], "cut": bool(will_cut and len(full) > n),
                       "zero_after_end": ok_zero, "identical_before_end": ok_ident,
                       "energy_kept": float(np.sum(cut ** 2)) / energy_full})
            placed = cut
        else:
            assert off + len(buf) <= n, f"early signal {s['sig_id']} exceeds the buffer"
            placed = np.zeros(n)
            placed[off:off + len(buf)] = buf
            p2.append({"sig_id": s["sig_id"], "L": s["L_s"], "whole_signal_inside": True,
                       "energy_kept": float(np.sum(placed ** 2)) / energy_full})
        mixed += (10.0 ** (s["snr_db"] / 20.0)) * placed
    noisy = channel.add_awgn(mixed, sigma, cycle_seed(index), noise_cutoff_hz=CUTOFF_HZ,
                             sample_rate_hz=D.FS)
    final = rs._finalize_playback_samples(noisy)
    return final, {"cycle": index, "n_samples": int(len(final)), "sigma": sigma,
                   "buffer_start_s": origin_s, "p2": p2}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--report", required=True)
    ap.add_argument("--cycles", default=None, help="a:b slice of cycle indexes (default all)")
    ap.add_argument("--skip-p1", action="store_true")
    a = ap.parse_args()
    _lower_priority()

    design = json.loads(Path(a.manifest).read_text(encoding="utf-8"))
    assert len(design["cycles"]) == D.TOTAL_CYCLES
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    sigma = reference_sigma()
    sel = range(D.TOTAL_CYCLES)
    if a.cycles:
        lo, hi = (int(v) for v in a.cycles.split(":"))
        sel = range(lo, hi)
    index, p2_fail, sigmas = {}, [], set()
    for i in sel:
        if not design["cycles"][i]["planted"]:
            index[str(i)] = {"planted": False}
            continue
        buf, info = render_cycle(design, i, sigma)
        sigmas.add(info["sigma"])
        np.save(out / f"cycle_{i:03d}.npy", buf)
        info["sha256"] = hashlib.sha256(buf.tobytes()).hexdigest()
        for r in info["p2"]:
            if "zero_after_end" in r and not (r["zero_after_end"] and r["identical_before_end"]):
                p2_fail.append(r)
            if r.get("whole_signal_inside") and abs(r["energy_kept"] - 1.0) > 1e-9:
                p2_fail.append(r)
            if "cut" in r and (r["L"] <= D.CUT_ONSET_S) and r["energy_kept"] < 1.0 - 1e-12:
                p2_fail.append(r)
        index[str(i)] = {"planted": True, "sha256": info["sha256"], "n_samples": info["n_samples"],
                         "buffer_start_s": info["buffer_start_s"]}
        if i % 20 == 0:
            print(f"rendered cycle {i}", flush=True)
    assert len(sigmas) <= 1, f"sigma differs between cycles: {sigmas}"
    # P1 over every signal of the selected cycles
    p1 = {"checked": 0, "max_err_ms": 0.0, "fail": []}
    if not a.skip_p1:
        for i in sel:
            for sid in design["cycles"][i]["signals"]:
                s = design["signals"][sid]
                err = p1_lag_error_s(s["text"], s["freq_hz"], s["L_s"])
                p1["checked"] += 1
                p1["max_err_ms"] = max(p1["max_err_ms"], err * 1000.0)
                if err > LAG_TOL_S:
                    p1["fail"].append({"sig_id": sid, "L": s["L_s"], "err_ms": err * 1000.0})
    n_cut = None
    report = {"sigma": sigma, "sigma_identical_all_cycles": len(sigmas) <= 1,
              "P1": {**p1, "tolerance_ms": LAG_TOL_S * 1000.0, "PASS": (not p1["fail"]) and not a.skip_p1},
              "P2": {"fail": p2_fail, "PASS": not p2_fail},
              "renders": index}
    Path(a.report).write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"sigma": sigma, "P1": report["P1"]["PASS"], "P1_checked": p1["checked"],
                      "P1_max_err_ms": round(p1["max_err_ms"], 4), "P2": report["P2"]["PASS"]}))


if __name__ == "__main__":
    main()
