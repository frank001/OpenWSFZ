#!/usr/bin/env python3
"""COH-GATE-G TEST analysis (frozen record 36df15b1): V2/V3/V4, rows N-GO/N-STOP, U-OK/U-FAIL, H-SHARE, verdict, D1/D2/D5.
Rules: R-F4 (admit G rows of the residual run, two-run cycles only), f1 alone (F1b <= 31.18 dB, frozen from TRAIN), no gate.
Counts only; text in memory only."""
import collections
import importlib.util
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gr_common as C
import gg_lib as L

CF = r"D:\Projects\claude\OpenWSFZ\worktrees\qa\qa\rr-study\coh-fallback"
DLL = r"D:\Projects\claude\_qa-scratch\coh-gate-g\bin\libft8.dll"
WAV_ROOT = r"D:\Projects\claude\OpenWSFZ\artefacts"
RUN = "20260925_2010"
CLASSES = r"D:\Projects\claude\_qa-scratch\coh-gate-g\u\uprime_orig_classes.json"
PIN = "1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914"
BAR_G, U_BAR_G, H = 0.5, 0.021, 0.5          # frozen (36df15b1)
T2_F1 = 31.18                                 # frozen from TRAIN
TRAIN_NET_RF4 = 1.905311778290993             # rules.json
B, SEED = 2000, 20261028
assert (BAR_G, U_BAR_G, H, B, SEED) == (0.5, 0.021, 0.5, 2000, 20261028)


def test_stamps():
    d = json.load(open(L.S + "\\selection_test.json", encoding="utf-8"))
    return [e if isinstance(e, str) else e[0] for e in d["runs"][RUN]["FULL"]]


def station_key(text):
    t = text.split()
    if not t:
        return ""
    if t[0] == "CQ":
        return t[2] if len(t) > 3 and t[1].isalpha() and len(t[1]) <= 4 else (t[1] if len(t) > 1 else "")
    return t[1] if len(t) > 1 else t[0]


def main():
    spec = importlib.util.spec_from_file_location("cf_uprime_mod", CF + "\\cf_uprime.py")
    U = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(U)
    F, _ = U.load_instrument()
    enc = F.encoder(DLL)
    frozen = json.load(open(CLASSES))
    c_off = float(frozen["start_minus_dt_median_s"])
    testable = set(frozen["testable_classes"])
    stamps = test_stamps()
    assert len(stamps) == 800
    ref = C.load_ref(set(stamps))
    n_cyc_all = len(stamps)
    arm = L.load_arm("test")
    pcms = {}

    def pcm_of(st):
        if st not in pcms:
            pcms[st] = F.wavio.load_cycle_pcm(os.path.join(WAV_ROOT, f"{RUN}_endurance_run-gathered", "owsfz", "wav", st + ".wav"))
        return pcms[st]

    def status(stamp, text, freq, dt):
        tones = enc(text)
        if any(x.startswith("<") for x in text.split()) or tones is None:
            return "hashed_or_unencodable"
        if F.shape_class(text) not in testable:
            return "untestable_class"
        sh, outs = F.locate_and_score({}, pcm_of(stamp), freq, dt + c_off, F.DT_HALF_WINDOW_S, [tones[i] for i in F.SYNC_IDX], [tones])
        return "tested_present" if outs[0] >= U.T_FROZEN else "tested_absent"

    res = {"cycles": n_cyc_all}
    NONE = lambda r: False
    # ---- validity ---------------------------------------------------------------------------------------------------------------------------
    v2_bad = 0
    b4 = 0
    n_ref = sum(len(ref[s]) for s in stamps)
    w = np.array([1.0 if ref[s] else 0.0 for s in stamps])        # cycles where WSJT-X decoded something (U' denominator)
    refc = np.array([float(len(ref[s])) for s in stamps])
    base_matched_prod = 0
    for s in stamps:
        prod4 = [(x[2], x[6]) for x in arm["nc"].get(s, []) if x[0] == 4]
        b4 += len(prod4)
        if [(f, t) for f, t, _ in L.publish(arm, s, NONE)] != prod4:
            v2_bad += 1
        ows = [(x[0], x[2], x[6]) for x in arm["nc"].get(s, [])]
        base_matched_prod += len(L.match(ref[s], ows)[0])
    st = open(L.S + "\\raw\\test_status.txt").read()
    import csv
    coh = list(csv.DictReader(open(L.S + "\\raw\\test\\coh.csv")))
    ab = [l.strip().split(",") for l in open(L.S + "\\raw\\test\\abandon.csv") if l[:1].isdigit()]
    res["V2"] = {"cycles_not_reproduced": v2_bad, "PASS": v2_bad == 0}
    res["V3"] = {"status_has_pin_and_ok": (PIN in st and "preflight_end_ok=1" in st), "PASS": (PIN in st and "preflight_end_ok=1" in st)}
    res["V4"] = {"fallback_abandoned": sum(int(r["abandoned"]) for r in coh), "residual_ran": sum(int(r[1]) for r in ab),
                 "residual_abandoned": sum(int(r[2]) for r in ab), "residual_contained": sum(int(r[3]) for r in ab)}
    res["V4"]["PASS"] = res["V4"]["fallback_abandoned"] == 0 and res["V4"]["residual_abandoned"] == 0 and res["V4"]["residual_contained"] == 0
    res["test_baseline"] = {"batch4_published": b4, "corroborated": base_matched_prod, "n_ref": n_ref, "pct": 100.0 * base_matched_prod / n_ref}
    valid = res["V2"]["PASS"] and res["V3"]["PASS"] and res["V4"]["PASS"]
    res["validity_all_pass"] = valid

    # ---- rules -----------------------------------------------------------------------------------------------------------------------------
    rules = {"R-F4": lambda s: (lambda r, two=(arm["runs"].get(s, 0) == 2): two and r["run"] == 0),
             "f1_alone_31.18": lambda s: (lambda r: r["f1b"] <= T2_F1),
             "no_gate": lambda s: (lambda r: True)}
    per = {}
    for name, mk in rules.items():
        cols = {k: np.zeros(n_cyc_all) for k in ("net", "ta", "hu", "pres", "unt", "out", "conf", "hashed")}
        by = collections.defaultdict(collections.Counter)
        stations = collections.Counter()
        for ci, s in enumerate(stamps):
            admit = mk(s)
            base13 = [(x[0], x[2], x[6]) for x in arm["nc"].get(s, []) if x[0] in (1, 2, 3)]
            none = L.publish(arm, s, NONE)
            fb = L.publish(arm, s, admit)
            mn, _ = L.match(ref[s], base13 + [(4, f, t) for f, t, _ in none])
            ma, mo = L.match(ref[s], base13 + [(4, f, t) for f, t, _ in fb])
            cols["net"][ci] = len(ma) - len(mn)
            none_texts = {t for _, t, _ in none}
            nb = len(base13)
            for k, (f, t, r) in enumerate(fb):
                if t in none_texts or r["state"] != "G":
                    continue
                cols["out"][ci] += 1
                hs = "<" in t
                cols["hashed"][ci] += hs
                snr = r["snr"]
                band = "A" if snr >= 0 else "B" if snr >= -10 else "C" if snr >= -15 else "D"
                by["band"][band] += 1
                by["i3"][str(r["i3"])] += 1
                by["run"]["residual" if (r["run"] == 0 and arm["runs"].get(s, 0) == 2) else "original"] += 1
                if (nb + k) in mo:
                    cols["conf"][ci] += 1
                    stations[station_key(t)] += 1
                else:
                    sx = status(s, t, f, r["dt"] + r["ddt"])
                    cols[{"tested_absent": "ta", "hashed_or_unencodable": "hu", "tested_present": "pres", "untestable_class": "unt"}[sx]][ci] += 1
        per[name] = (cols, by, stations)
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, n_cyc_all, size=(B, n_cyc_all))
    out_rules = {}
    for name, (cols, by, stations) in per.items():
        den = refc[idx].sum(axis=1)
        net = 100.0 * cols["net"][idx].sum(axis=1) / den
        wcnt = w[idx].sum(axis=1)
        ta = cols["ta"][idx].sum(axis=1) / wcnt
        hu = cols["hu"][idx].sum(axis=1) / wcnt
        pres = cols["pres"][idx].sum(axis=1) / wcnt
        pt_net = 100.0 * cols["net"].sum() / refc.sum()
        outs = cols["out"].sum()
        tot = sum(stations.values())
        out_rules[name] = {
            "NET_pp": pt_net, "NET_CI": [float(np.percentile(net, 2.5)), float(np.percentile(net, 97.5))],
            "dU_ta": cols["ta"].sum() / w.sum(), "dU_ta_CI": [float(np.percentile(ta, 2.5)), float(np.percentile(ta, 97.5))],
            "dU_hu": cols["hu"].sum() / w.sum(), "dU_hu_CI": [float(np.percentile(hu, 2.5)), float(np.percentile(hu, 97.5))],
            "dU_present": cols["pres"].sum() / w.sum(), "dU_present_CI": [float(np.percentile(pres, 2.5)), float(np.percentile(pres, 97.5))],
            "dU_untestable_class": cols["unt"].sum() / w.sum(),
            "admitted_new_text": int(outs), "admitted_corroborated": int(cols["conf"].sum()),
            "corroborated_share": float(cols["conf"].sum() / outs) if outs else None,
            "hashed_share_of_admitted": float(cols["hashed"].sum() / outs) if outs else None,
            "admitted_by": {k: dict(v) for k, v in by.items()},
            "stations_corroborated": {"distinct": len(stations), "top_share": (max(stations.values()) / tot) if tot else None,
                                      "top5_share": (sum(v for _, v in stations.most_common(5)) / tot) if tot else None}}
    res["rules"] = out_rules
    r = out_rules["R-F4"]
    res["rows_R-F4"] = {
        "N-GO": r["NET_CI"][0] >= BAR_G, "N-STOP": r["NET_CI"][1] < BAR_G,
        "U-OK": r["dU_ta_CI"][1] <= U_BAR_G, "U-FAIL": r["dU_ta_CI"][0] > U_BAR_G,
        "H-SHARE_fires": (r["hashed_share_of_admitted"] or 0.0) > H}
    rr = res["rows_R-F4"]
    rr["N"] = "N-GO" if rr["N-GO"] else "N-STOP" if rr["N-STOP"] else "N-OPEN"
    rr["U"] = "U-OK" if rr["U-OK"] else "U-FAIL" if rr["U-FAIL"] else "U-OPEN"
    verdict = "G-BUILD" if (rr["N-GO"] and rr["U-OK"] and not rr["H-SHARE_fires"]) else "G-STOP" if (rr["N-STOP"] or rr["U-FAIL"]) else "G-OPEN"
    res["verdict"] = verdict if valid else "VOID (validity row failed)"
    res["D5"] = {"train_NET_pp": TRAIN_NET_RF4, "test_NET_pp": r["NET_pp"], "ratio": r["NET_pp"] / TRAIN_NET_RF4,
                 "GG6_test_le_0.8_train": r["NET_pp"] <= 0.8 * TRAIN_NET_RF4}
    json.dump(res, open(L.S + "\\test_result.json", "w"), indent=1, default=float)
    print(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    main()
