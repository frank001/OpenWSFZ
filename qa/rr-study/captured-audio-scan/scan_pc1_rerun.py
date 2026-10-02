"""#194 scan: PC1 rerun under rulings A8 and A9 (Architect, 2026-10-02 1925). Only the A8 cells and the
new resid_db cells are run; the draws of every (side, group) are reproduced exactly (same rng sequence as
scan_pc1.py), so the earlier PASS cells are untouched.

A8: the three 9/10 cells (wsjtx:single:drift_ppm, wsjtx:multi:drift_ppm, owsfz:single:hiccup). Name the
    missed copy. Ambiguous => replace it by the next slot of the seeded sequence (20261002) that is
    unflagged and not lag_ambiguous, rerun those cells. NOT ambiguous => real miss: STOP, no redraw.
    "Next slot of the seeded sequence" is defined here as: the first element of
    default_rng(20261002).permutation(len(candidates)) that is not already drawn and is not ambiguous.
A9: resid_db injection = seeded white Gaussian noise (seed 20261002 + copy index) added over the support,
    power such that the slot's expected resid_db = median + m (T - median), m in {0.5, 1, 2}.
    Representable iff no sample clips after adding the noise; not representable at 2x in ANY copy =>
    DESCRIPTIVE-ABOVE-RANGE (A7).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scan_core as sc  # noqa: E402
import scan_freeze as fz  # noqa: E402
import scan_pc1 as pc  # noqa: E402

A8_CELLS = ["wsjtx:single:drift_ppm", "wsjtx:multi:drift_ppm", "owsfz:single:hiccup"]
LEVELS = (0.5, 1.0, 2.0)


def fit_support(x_i16: np.ndarray, ref: np.ndarray):
    """(P_sig over the support, n_support, support index range) from an approximate fit; used only to
    size the injected noise (the flag decision is scan_core.measure)."""
    x = x_i16.astype("float64") / 32768.0
    r = np.asarray(ref, dtype="float64")[:sc.SLOT_N]
    lags, c, rho = sc._xcorr(x, r)
    i = int(np.argmax(rho))
    tau = float(lags[0]) + sc._parabolic(c, i)
    t0 = int(round(tau))
    rs = sc.shift_ref(r, tau, len(x))
    n_fade = int(sc.FADE_S * sc.FS)
    sup_ref = r != 0.0
    sup_ref[max(0, len(r) - n_fade):] = False
    sup = np.zeros(len(x), dtype=bool)
    lo, hi = max(0, t0), min(len(x), len(r) + t0)
    sup[lo:hi] = sup_ref[lo - t0:hi - t0]
    zero = x_i16 == 0
    for st, ln in sc._runs(zero):
        if st == 0:
            sup[:ln] = False
        if st + ln == len(x):
            sup[len(x) - ln:] = False
    g = float(np.dot(x[sup], rs[sup]) / np.dot(rs[sup], rs[sup]))
    return float(np.sum((g * rs[sup]) ** 2)), int(sup.sum()), sup


def inject_resid(x_i16, ref, m, med, T, copy_index, r0):
    p_sig, n_sup, sup = fit_support(x_i16, ref)
    target = med + m * (T - med)
    add_ratio = 10 ** (target / 10) - 10 ** (r0 / 10)
    if add_ratio <= 0:
        return x_i16.copy(), "no-op (slot already at or above target)", True
    sigma = math.sqrt(add_ratio * p_sig / n_sup) * 32768.0
    rng = np.random.default_rng(pc.SEED + copy_index)
    noise = np.zeros(len(x_i16))
    noise[sup] = rng.standard_normal(int(sup.sum())) * sigma
    y = x_i16.astype("float64") + noise
    clipped = int(np.sum((np.abs(np.round(y)) > 32767) & (np.abs(x_i16.astype("float64")) <= 32767)))
    return pc.to_i16(y), f"sigma {sigma:.0f} LSB, target {target:.1f} dB", clipped == 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sidecars", required=True)
    ap.add_argument("--thresholds", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--audio", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    th_path = Path(a.thresholds)
    th = json.loads(th_path.read_text(encoding="utf-8"))
    assert fz.sha_lf(th_path) == [ln for ln in (th_path.parent / "FREEZE.sha256").read_text().splitlines()
                                  if ln.startswith("thresholds.json")][0].split()[1]
    assert th["scan_core_py_sha256"] == fz.sha_lf(Path(sc.__file__))
    desc = set(th["descriptive"])
    rng = np.random.default_rng(pc.SEED)
    out = {"a8": [], "a9": [], "stop": None}
    for side in fz.SIDES:
        rows = [r for r in fz.load(Path(a.sidecars) / f"sidecar_{side}.csv") if not r["ref_mismatch"]]
        wavdir = Path(a.audio) / ("owsfz" if side == "owsfz" else "wsjt-x") / "wav"
        for group in sc.GROUPS:
            cand = sorted((r for r in rows if r["group"] == group
                           and not any(fz.slot_flags(th, side, r).values())), key=lambda r: r["slot"])
            pick = [cand[i] for i in sorted(rng.choice(len(cand), size=min(pc.N_DRAW, len(cand)), replace=False))]

            def load(r):
                dt = datetime.strptime(r["cycle_utc"], "%Y-%m-%dT%H:%M:%SZ").strftime("%y%m%d_%H%M%S")
                w = sc.read_wav(wavdir / f"{dt}.wav")
                return (r, w["x"], np.load(Path(a.ref) / f"{r['slot']}.npy").astype("float64"))

            # ---------------- A8
            for cell in A8_CELLS:
                if not cell.startswith(f"{side}:{group}:"):
                    continue
                metric = cell.split(":")[2]
                T = pc.cell_T(th, side, group, "drift_ppm")
                data = [load(r) for r in pick]
                copies = []
                for r, x, ref in data:
                    y, _ = pc.inj_hiccup(x, 2.0, T, {}) if metric == "hiccup" else pc.inj_drift(x, 2.0, T, {})
                    fl = fz.slot_flags(th, side, {**sc.measure(y, ref), "group": group})
                    ok = (fl["drift_ppm"] or fl["step_db_max"]) if metric == "hiccup" else fl["drift_ppm"]
                    copies.append({"slot": r["slot"], "lag_ambiguous": int(r["lag_ambiguous"]), "flagged_2x": bool(ok)})
                missed = [c for c in copies if not c["flagged_2x"]]
                rec = {"cell": cell, "copies_2x": copies, "missed": [c["slot"] for c in missed],
                       "missed_ambiguous": [c["lag_ambiguous"] for c in missed]}
                if missed and not all(c["lag_ambiguous"] for c in missed):
                    rec["verdict"] = "REAL MISS: STOP (A8 step 3)"
                    out["stop"] = cell
                elif missed:
                    picked = {r["slot"] for r in pick}
                    order = np.random.default_rng(pc.SEED).permutation(len(cand))
                    repl = [cand[i] for i in order if cand[i]["slot"] not in picked and not cand[i]["lag_ambiguous"]]
                    new_pick = [r for r in pick if r["slot"] not in {c["slot"] for c in missed}] + repl[:len(missed)]
                    rates = {}
                    for k in LEVELS:
                        hit = tot = 0
                        for r in new_pick:
                            _, x, ref = load(r)
                            y, _ = pc.inj_hiccup(x, k, T, {}) if metric == "hiccup" else pc.inj_drift(x, k, T, {})
                            fl = fz.slot_flags(th, side, {**sc.measure(y, ref), "group": group})
                            ok = (fl["drift_ppm"] or fl["step_db_max"]) if metric == "hiccup" else fl["drift_ppm"]
                            tot += 1
                            hit += int(ok)
                        rates[str(k)] = {"flagged": hit, "of": tot}
                    rec.update({"replacement": [r["slot"] for r in repl[:len(missed)]], "rates": rates,
                                "verdict": "PASS" if rates["2.0"]["flagged"] == rates["2.0"]["of"] else "FAIL"})
                else:
                    rec["verdict"] = "no miss on reproduction"
                out["a8"].append(rec)
                print(rec["cell"], rec["verdict"], flush=True)
            # ---------------- A9
            key = f"{side}:{group}:resid_db"
            row = th["sides"][side][group].get("resid_db")
            if row is None or key in desc:
                out["a9"].append({"cell": key, "status": "DESCRIPTIVE" if key in desc else "BLIND"})
                continue
            med, T = row["median"], row["T"]
            data = [load(r) for r in pick]
            rates, notes, unrep = {}, [], 0
            for k in LEVELS:
                hit = tot = 0
                for j, (r, x, ref) in enumerate(data):
                    base = sc.measure(x, ref)
                    y, note, rep = inject_resid(x, ref, k, med, T, j, base["resid_db"])
                    if k == 2.0 and not rep:
                        unrep += 1
                    if not rep:
                        notes.append(note)
                        continue
                    fl = fz.slot_flags(th, side, {**sc.measure(y, ref), "group": group})
                    tot += 1
                    hit += int(fl["resid_db"])
                rates[str(k)] = {"flagged": hit, "of": tot}
            two = rates["2.0"]
            status = ("DESCRIPTIVE-ABOVE-RANGE" if unrep else
                      "PASS" if two["of"] == len(data) and two["flagged"] == two["of"] else "FAIL")
            out["a9"].append({"cell": key, "status": status, "median": med, "T": T, "rates": rates,
                              "unrepresentable_copies_at_2x": unrep, "n_slots": len(data), "note": sorted(set(notes))[:1]})
            print(key, status, flush=True)
    Path(a.out).write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
