"""#194 scan: PC1, the positive control (spec section 6, ruling 1915 step 3).

    python scan_pc1.py --sidecars <_out/run dir> --thresholds <thresholds.json> --ref <ref dir> \
        --audio <...-captured-audio dir> --out <_out/pc1.json>

Injects known faults into IN-MEMORY COPIES of 10 unflagged 09-23 slots per side and group
(seed 20261002) at 0.5x / 1x / 2x of the frozen threshold T and re-measures through exactly
`scan_core.measure`. PASS iff, for every non-DESCRIPTIVE cell, 2x is flagged on the expected
metric in every drawn copy and the unmodified copies are flagged 0/N. No WAV is written.

Injections 1-6 are the spec's table. Injections 7-11 are EXTENSIONS (the ruling asks for PC1 on
every non-DESCRIPTIVE metric and the spec's six reach only five metrics): tau shift, click,
clip, head zeros, tail zeros. resid_db has no injection defined: reported UNTESTED.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
from scipy.interpolate import CubicSpline
from scipy.signal import medfilt

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scan_core as sc  # noqa: E402
import scan_freeze as fz  # noqa: E402

SEED = 20261002
N_DRAW = 10
LEVELS = (0.5, 1.0, 2.0)
FS = sc.FS
assert (SEED, N_DRAW, FS) == (20261002, 10, 12000)
STEP_AT_S, DROP_AT_S, TONE_AT_S, HICCUP_AT_S = 7.0, 5.0, 9.0, 6.0   # spec section 6
TONE_HZ, TONE_LEN_S = 1000.0, 0.5
DRIFT_ELAPSED_S = 10.8          # support span used to convert ppm to samples for the hiccup
CLICK_AT_S = 3.0
SEC = FS


def to_i16(x: np.ndarray) -> np.ndarray:
    return np.clip(np.round(x), -32768, 32767).astype("<i2")


def baseline_residual(x_i16: np.ndarray, ref: np.ndarray):
    """Approximate residual (used only to SIZE injections; the measurement is scan_core.measure)."""
    x = x_i16.astype("float64") / 32768.0
    r = np.asarray(ref, dtype="float64")[:sc.SLOT_N]
    lags, c, rho = sc._xcorr(x, r)
    i = int(np.argmax(rho))
    tau = float(lags[0]) + sc._parabolic(c, i)
    rs = sc.shift_ref(r, tau, len(x))
    m = np.abs(rs) > 0
    g = float(np.dot(x[m], rs[m]) / np.dot(rs[m], rs[m]))
    return x - g * rs


def tile_powers(e: np.ndarray, seg_from: int = 0, seg_to: int = 14):
    win = np.hanning(FS)
    edges = np.arange(sc.TILE_FREQ_LO, sc.TILE_FREQ_HI + 1, sc.TILE_BW)
    out = []
    for s in range(seg_from, seg_to):
        P = np.abs(np.fft.rfft(e[s * FS:(s + 1) * FS] * win)) ** 2
        out.extend(float(P[p:q].sum()) for p, q in zip(edges[:-1], edges[1:]))
    return np.asarray(out)


# --------------------------------------------------------------------------- injections
# Each returns (new int16 array, note) or (None, reason) when the injection is not feasible.
def inj_step(x, k, T, ctx):
    y = x.astype("float64").copy()
    y[int(STEP_AT_S * SEC):] *= 10 ** (-(k * T) / 20)
    return to_i16(y), ""


def inj_gain(x, k, T, ctx):
    return to_i16(x.astype("float64") * 10 ** (-(k * T) / 20)), ""


def inj_zero(x, k, T, ctx):
    n = int(round(k * T * FS / 1000.0))
    y = x.copy()
    a = int(DROP_AT_S * SEC)
    y[a:a + n] = 0
    return y, f"{n} samples"


def inj_tone(x, k, T, ctx):
    e = ctx["resid"]
    med = float(np.median(tile_powers(e)))
    unit = np.zeros(len(x))
    a = int(TONE_AT_S * SEC)
    n = int(TONE_LEN_S * SEC)
    t = np.arange(n) / FS
    unit[a:a + n] = np.sin(2 * np.pi * TONE_HZ * t)
    up = float(np.max(tile_powers(unit, 9, 10)))
    amp = math.sqrt(med * 10 ** ((k * T) / 10) / up)             # in float units (full scale 1.0)
    if amp > 0.95:
        return None, f"tone amplitude {amp:.2f} FS needed (> full scale): not injectable"
    y = x.astype("float64") + amp * 32768.0 * unit
    return to_i16(y), f"amp {amp:.4f} FS"


def inj_drift(x, k, T, ctx):
    d = k * T * 1e-6
    t = np.arange(len(x))
    cs = CubicSpline(t, x.astype("float64"))
    tn = np.clip(t * (1 + d), 0, len(x) - 1)
    return to_i16(cs(tn)), ""


def inj_hiccup(x, k, T, ctx):
    n = int(round(k * T * 1e-6 * DRIFT_ELAPSED_S * FS))
    if n < 1:
        return None, "rounds to 0 samples"
    a = int(HICCUP_AT_S * SEC)
    y = np.concatenate([x[:a], x[a - n:a], x[a:]])[:len(x)]
    return y.astype("<i2"), f"{n} samples inserted"


def inj_tau(x, k, T, ctx):
    n = int(round(k * T * FS / 1000.0))
    y = np.concatenate([np.zeros(n, dtype="<i2"), x])[:len(x)]
    return y, f"{n} samples"


def inj_click(x, k, T, ctx):
    e = ctx["resid"]
    ehf = e - medfilt(e, 31)
    sig = float(np.median(np.abs(ehf - np.median(ehf))) * 1.4826)
    amp = k * T * sig * 32768.0
    if amp > 32000:
        return None, f"spike {amp:.0f} LSB needed (> full scale): not injectable"
    y = x.astype("float64").copy()
    y[int(CLICK_AT_S * SEC)] += amp
    return to_i16(y), f"spike {amp:.0f} LSB"


def inj_clip(x, k, T, ctx):
    n = int(math.ceil(k))
    y = x.copy()
    y[int(CLICK_AT_S * SEC):int(CLICK_AT_S * SEC) + n] = 32767
    return y, f"{n} samples"


def inj_head(x, k, T, ctx):
    n = int(round(k * sc.TAIL_HEAD_TOL_MS * FS / 1000.0))
    y = x.copy()
    y[:n] = 0
    return y, f"{n} samples"


def inj_tail(x, k, T, ctx):
    n = int(round(k * sc.TAIL_HEAD_TOL_MS * FS / 1000.0)) + ctx["base_tail_samples"]
    y = x.copy()
    y[len(y) - n:] = 0
    return y, f"{n} samples total tail"


# metric -> (injection, expected-flag metrics (any), uses the metric's calibrated T?)
SPEC_SIX = {"step_db_max": inj_step, "g_db": inj_gain, "zero_run_ms": inj_zero,
            "tile_excess_db": inj_tone, "drift_ppm": inj_drift}
EXTENSIONS = {"tau_ms": inj_tau, "click_max": inj_click, "clip_n": inj_clip,
              "head_zero_ms": inj_head, "tail_zero_ms": inj_tail}
INJ = {**SPEC_SIX, **EXTENSIONS}
UNIT_T = {"clip_n": 1.0, "head_zero_ms": 1.0, "tail_zero_ms": 1.0}   # k scales a fixed unit, not a T


def cell_T(th, side, group, metric):
    if metric in UNIT_T:
        return UNIT_T[metric]
    row = th["sides"][side][group].get(metric)
    return None if row is None else row["T"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sidecars", required=True)
    ap.add_argument("--thresholds", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--audio", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    th_path = Path(a.thresholds)
    got = fz.sha_lf(th_path)
    th = json.loads(th_path.read_text(encoding="utf-8"))
    freeze_line = [ln for ln in (th_path.parent / "FREEZE.sha256").read_text().splitlines()
                   if ln.startswith("thresholds.json")][0].split()[1]
    assert got == freeze_line, f"thresholds.json SHA {got} != FREEZE.sha256 {freeze_line}"
    assert th["scan_core_py_sha256"] == fz.sha_lf(Path(sc.__file__)), "scan_core.py changed since the freeze"
    desc = set(th["descriptive"])
    rng = np.random.default_rng(SEED)
    results = []
    for side in fz.SIDES:
        rows = fz.load(Path(a.sidecars) / f"sidecar_{side}.csv")
        rows = [r for r in rows if not r["ref_mismatch"]]
        wavdir = Path(a.audio) / ("owsfz" if side == "owsfz" else "wsjt-x") / "wav"
        for group in sc.GROUPS:
            cand = sorted((r for r in rows if r["group"] == group
                           and not any(fz.slot_flags(th, side, r).values())), key=lambda r: r["slot"])
            pick = [cand[i] for i in sorted(rng.choice(len(cand), size=min(N_DRAW, len(cand)), replace=False))]
            data = []
            for r in pick:
                dt = datetime.strptime(r["cycle_utc"], "%Y-%m-%dT%H:%M:%SZ").strftime("%y%m%d_%H%M%S")
                w = sc.read_wav(wavdir / f"{dt}.wav")
                ref = np.load(Path(a.ref) / f"{r['slot']}.npy").astype("float64")
                data.append((r, w["x"], ref))
            # unmodified copies
            unmod = 0
            for r, x, ref in data:
                m = sc.measure(x, ref)
                if any(fz.slot_flags(th, side, {**m, "group": group}).values()):
                    unmod += 1
            for metric, fn in INJ.items():
                T = cell_T(th, side, group, metric)
                key = f"{side}:{group}:{metric}"
                if T is None:
                    results.append({"cell": key, "status": "BLIND", "why": "no valid values in this group (A3)"})
                    continue
                if key in desc:
                    results.append({"cell": key, "status": "DESCRIPTIVE"})
                    continue
                rates, notes = {}, []
                for k in LEVELS:
                    hit = tot = 0
                    for r, x, ref in data:
                        base = sc.measure(x, ref) if metric == "tail_zero_ms" else None
                        ctx = {"resid": baseline_residual(x, ref) if metric in ("tile_excess_db", "click_max") else None,
                               "base_tail_samples": int(round(base["tail_zero_ms"] * FS / 1000.0)) if base else 0}
                        y, note = fn(x, k, T, ctx)
                        if y is None:
                            notes.append(note)
                            continue
                        m = sc.measure(y, ref)
                        fl = fz.slot_flags(th, side, {**m, "group": group})
                        tot += 1
                        hit += int(fl[metric])
                    rates[str(k)] = {"flagged": hit, "of": tot}
                two = rates["2.0"]
                status = ("PASS" if two["of"] == len(data) and two["flagged"] == two["of"]
                          else "NOT-INJECTABLE" if two["of"] == 0 else "FAIL")
                results.append({"cell": key, "status": status, "T": T, "rates": rates,
                                "n_slots": len(data), "unmodified_flagged": unmod,
                                "note": sorted(set(notes))[:2]})
            # hiccup: expected drift_ppm OR step_db_max
            Td = cell_T(th, side, group, "drift_ppm")
            exp = [mm for mm in ("drift_ppm", "step_db_max") if f"{side}:{group}:{mm}" not in desc
                   and cell_T(th, side, group, mm) is not None]
            if Td is not None and exp:
                rates = {}
                for k in LEVELS:
                    hit = tot = 0
                    for r, x, ref in data:
                        y, note = inj_hiccup(x, k, Td, {})
                        if y is None:
                            continue
                        fl = fz.slot_flags(th, side, {**sc.measure(y, ref), "group": group})
                        tot += 1
                        hit += int(any(fl[mm] for mm in exp))
                    rates[str(k)] = {"flagged": hit, "of": tot}
                two = rates["2.0"]
                results.append({"cell": f"{side}:{group}:hiccup", "status": "PASS" if two["of"] and two["flagged"] == two["of"] == len(data) else "FAIL",
                                "T": Td, "expected_any_of": exp, "rates": rates, "n_slots": len(data)})
            results.append({"cell": f"{side}:{group}:resid_db", "status": "UNTESTED", "why": "no injection defined"})
            print(side, group, "done", flush=True)
    summary = {s: sum(1 for r in results if r["status"] == s) for s in
               ("PASS", "FAIL", "NOT-INJECTABLE", "DESCRIPTIVE", "BLIND", "UNTESTED")}
    out = {"seed": SEED, "levels": LEVELS, "thresholds_sha256_lf": got, "summary": summary, "results": results}
    Path(a.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
