"""#194 scan: PC1 rerun after re-freeze 3 (rulings A3' + A10, Architect 2026-10-02 1955).

Cells run: the three A8 cells, every cell whose ambiguity set changed (single and multi, both sides:
tau_ms, drift_ppm, hiccup), and the lag_lost cells (reached through the drift and hiccup injections, which may
pass on drift_ppm OR lag_lost, and hiccup also on step_db_max). Terminal rule (fixed by the ruling): a cell that
FAILS becomes DESCRIPTIVE-PC1-FAIL (a hole; never flags; no further ruling), and the scan proceeds.

Lag-family copies come only from slots whose reference is NOT ambiguous (A8/A3'). The original seed-20261002 draw
is reproduced; an ambiguous drawn copy is replaced by the first non-ambiguous, unflagged, undrawn element of
default_rng(20261002).permutation(len(candidates)).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scan_core as sc  # noqa: E402
import scan_freeze as fz  # noqa: E402
import scan_pc1 as pc  # noqa: E402

LEVELS = (0.5, 1.0, 2.0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sidecars", required=True)
    ap.add_argument("--thresholds", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--audio", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    thp = Path(a.thresholds)
    th = json.loads(thp.read_text(encoding="utf-8"))
    assert fz.sha_lf(thp) == [ln for ln in (thp.parent / "FREEZE.sha256").read_text().splitlines()
                              if ln.startswith("thresholds.json")][0].split()[1]
    assert th["scan_core_py_sha256"] == fz.sha_lf(Path(sc.__file__))
    desc = set(th["descriptive"])
    rng = np.random.default_rng(pc.SEED)
    results = []
    for side in fz.SIDES:
        rows = [r for r in fz.load(Path(a.sidecars) / f"sidecar_{side}.csv") if not r["ref_mismatch"]]
        wavdir = Path(a.audio) / ("owsfz" if side == "owsfz" else "wsjt-x") / "wav"
        for group in sc.GROUPS:
            cand = sorted((r for r in rows if r["group"] == group
                           and not any(fz.slot_flags(th, side, r).values())), key=lambda r: r["slot"])
            pick = [cand[i] for i in sorted(rng.choice(len(cand), size=min(pc.N_DRAW, len(cand)), replace=False))]
            if group in ("tone2", "tone3"):
                results.append({"cell": f"{side}:{group}:lag family", "status": "BLIND", "why": "reference ambiguous (A3')"})
                continue
            picked = {r["slot"] for r in pick}
            amb = [r for r in pick if r["lag_ambiguous"]]
            order = np.random.default_rng(pc.SEED).permutation(len(cand))
            repl = [cand[i] for i in order if cand[i]["slot"] not in picked and not cand[i]["lag_ambiguous"]]
            copies = [r for r in pick if not r["lag_ambiguous"]] + repl[:len(amb)]
            replaced = [(x["slot"], y["slot"]) for x, y in zip(amb, repl)]

            def load(r):
                dt = datetime.strptime(r["cycle_utc"], "%Y-%m-%dT%H:%M:%SZ").strftime("%y%m%d_%H%M%S")
                w = sc.read_wav(wavdir / f"{dt}.wav")
                return w["x"], np.load(Path(a.ref) / f"{r['slot']}.npy").astype("float64")

            data = [(r, *load(r)) for r in copies]
            Td = pc.cell_T(th, side, group, "drift_ppm")
            Tt = pc.cell_T(th, side, group, "tau_ms")

            def active(*ms):
                return [m for m in ms if f"{side}:{group}:{m}" not in desc and m in th["sides"][side][group]]

            specs = {
                "drift_ppm": (pc.inj_drift, Td, active("drift_ppm", "lag_lost")),
                "hiccup": (pc.inj_hiccup, Td, active("drift_ppm", "step_db_max", "lag_lost")),
                "tau_ms": (pc.inj_tau, Tt, active("tau_ms")),
            }
            for name, (fn, T, exp) in specs.items():
                key = f"{side}:{group}:{name}"
                if T is None or not exp:
                    results.append({"cell": key, "status": "DESCRIPTIVE" if key in desc or not exp else "BLIND"})
                    continue
                rates, via = {}, {"drift_ppm": 0, "lag_lost": 0, "step_db_max": 0, "tau_ms": 0}
                for k in LEVELS:
                    hit = tot = 0
                    for r, x, ref in data:
                        y, note = fn(x, k, T, {"base_tail_samples": 0})
                        if y is None:
                            continue
                        fl = fz.slot_flags(th, side, {**sc.measure(y, ref), "group": group})
                        tot += 1
                        got = [m for m in exp if fl[m]]
                        hit += int(bool(got))
                        if k == 2.0:
                            for m in got:
                                via[m] += 1
                    rates[str(k)] = {"flagged": hit, "of": tot}
                two = rates["2.0"]
                ok = two["of"] == len(data) and two["flagged"] == two["of"]
                results.append({"cell": key, "status": "PASS" if ok else "DESCRIPTIVE-PC1-FAIL",
                                "expected_any_of": exp, "T": T, "rates": rates, "flagged_via_at_2x": via,
                                "n_copies": len(data), "replaced_ambiguous": replaced})
            print(side, group, "done", flush=True)
    summary = {}
    for r in results:
        summary[r["status"]] = summary.get(r["status"], 0) + 1
    Path(a.out).write_text(json.dumps({"summary": summary, "results": results}, indent=1), encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
