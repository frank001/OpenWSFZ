#!/usr/bin/env python3
"""TA-CHECK scorer: the U' tone test (cf_fbid.locate_and_score, imported through cf_uprime.load_instrument, blob-asserted) at WSJT-X's position, on the ORIGINAL audio of the cycle.
    python tc_score.py ctrl     calibration (80 confirmed controls, the instrument's own procedure on WSJT-X's dt), the B1 and B1m rows, the night's null (descriptive V-NULL)   -> scores_ctrl.json
    python tc_score.py tgt      every other row of the frozen pool (T4, T5, batches 2 and 3)                                                                                 -> scores_tgt.json
`ctrl` may run before the freeze (A1.1); `tgt` runs only after it.  HK-037: text is read in this process, used for tones and the shape class, never written.  Output: stamp:idx -> tone share."""
from __future__ import annotations

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tc_lib as L          # noqa: E402
import tc_groups as G       # noqa: E402

U, F_ = G.U, None
CALIBRATION_CONTROLS, CALIBRATION_MIN_SYNC_HIT, K_NULL, N_NULL_ROWS = 80, 0.6, 20, 100
assert (CALIBRATION_CONTROLS, CALIBRATION_MIN_SYNC_HIT, K_NULL) == (U.CALIBRATION_CONTROLS, U.CALIBRATION_MIN_SYNC_HIT, U.K_NULL)


def texts_by_cycle(stamps):
    return G.load_ref_night(set(stamps))


def main():
    stage = sys.argv[1] if len(sys.argv) > 1 else ""
    if stage not in ("ctrl", "tgt"):
        sys.exit(__doc__)
    grp = json.load(open(G.OUT + "/frozen/tc_groups.json"))
    rows, stamps = grp["rows"], grp["stamps"]
    F, blob = U.load_instrument()
    assert blob == grp["summary"]["blob_cf_fbid"]
    enc = F.encoder(G.DLL)
    ref = texts_by_cycle(stamps)
    mb = {}
    import csv
    for r in csv.reader(open(G.MATCHED)):
        if r and r[0] != "stamp":
            mb[r[0]] = {int(a.split(":")[0]): int(a.split(":")[1]) for a in r[1].split(";") if a}
    pcms = {}

    def pcm_of(s):
        if s not in pcms:
            pcms[s] = F.wavio.load_cycle_pcm(os.path.join(G.WAVS, s + ".wav"))
        return pcms[s]

    # confirmed controls (any batch) with tones, as cf_uprime's `ctl`: sorted by (stamp, freq)
    ctl = []
    for s in stamps:
        for i, (snr, dt, f, text) in enumerate(ref.get(s, [])):
            if mb[s].get(i) is not None:
                t = enc(text)
                if t is not None:
                    ctl.append({"stamp": s, "idx": i, "f": f, "dt": dt, "tones": t})
    ctl.sort(key=lambda r: (r["stamp"], r["f"]))
    cal_path = G.OUT + "/frozen/tc_calib.json"
    if stage == "ctrl":
        offs = []
        for r in ctl[:CALIBRATION_CONTROLS]:
            h, st = U.locate_start(F, pcm_of(r["stamp"]), r["f"], r["dt"] + 0.5, F.CALIB_HALF_WINDOW_S, [r["tones"][i] for i in F.SYNC_IDX])
            if h >= CALIBRATION_MIN_SYNC_HIT:
                offs.append(st - r["dt"])
        c_off = float(np.median(offs)) if offs else 0.5
        json.dump({"controls_used": min(len(ctl), CALIBRATION_CONTROLS), "with_sync_hit_ge_0.6": len(offs), "start_minus_dt_median_s": c_off}, open(cal_path, "w"), indent=1)
    c_off = float(json.load(open(cal_path))["start_minus_dt_median_s"])

    def share_of(s, i, snr, dt, f, text, extra=()):
        tones = enc(text)
        _, outs = F.locate_and_score({}, pcm_of(s), f, dt + c_off, F.DT_HALF_WINDOW_S, [tones[k] for k in F.SYNC_IDX], [tones] + list(extra))
        return outs

    want = {(r["stamp"], r["idx"]) for r in rows if ((r["in_B1"] or r["in_B1m"]) if stage == "ctrl" else not (r["in_B1"] or r["in_B1m"]))}
    scores = {}
    for s in stamps:
        for i, (snr, dt, f, text) in enumerate(ref.get(s, [])):
            if (s, i) in want:
                scores[f"{s}:{i}"] = share_of(s, i, snr, dt, f, text)[0]
    out = {"stage": stage, "c_off": c_off, "n_scored": len(scores), "scores": scores}
    if stage == "ctrl":
        # V-NULL (descriptive): cf_uprime's null, on a seeded sample of N_NULL_ROWS B1 rows, K_NULL mismatched tone sequences each, from other cycles' controls with data agreement <= 0.3
        rng = np.random.default_rng(L.SEED)
        b1 = sorted((r["stamp"], r["idx"]) for r in rows if r["in_B1"])
        pick = [b1[j] for j in sorted(rng.permutation(len(b1))[:N_NULL_ROWS])]
        all_t = [r["tones"] for r in ctl]
        nulls = []
        for (s, i) in pick:
            snr, dt, f, text = ref[s][i]
            own = enc(text)
            cand = [j for j, x in enumerate(ctl) if x["stamp"] != s and float((np.array(x["tones"])[F.DATA_IDX] == np.array(own)[F.DATA_IDX]).mean()) <= 0.3]
            sel = rng.choice(cand, size=K_NULL, replace=False)
            outs = share_of(s, i, snr, dt, f, text, [all_t[j] for j in sel])
            nulls.extend(outs[1:])
        nulls = np.array(nulls)
        p99 = float(np.percentile(nulls, F.NULL_PCTL))
        out["null_this_night"] = {"rows": len(pick), "n": int(nulls.size), "mean": float(nulls.mean()), "p99": p99, "T_frozen": L.T_FROZEN, "abs_diff": abs(p99 - L.T_FROZEN), "within_0.03": bool(abs(p99 - L.T_FROZEN) <= L.NULL_TOL)}
    json.dump(out, open(G.OUT + f"/scores_{stage}.json", "w"))
    print(json.dumps({k: v for k, v in out.items() if k != "scores"}, indent=1))


if __name__ == "__main__":
    main()
