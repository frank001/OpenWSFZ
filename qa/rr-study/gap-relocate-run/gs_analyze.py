#!/usr/bin/env python3
"""COH-GATE-G R-F4 SECOND NIGHT analysis (freeze record adf335c3; night 20261022_1949, 40 m; sol records pulled to the PC).
Rows (spec section 5 as on TEST, A1.1, A2.3, build spec section 4): N-GO / N-STOP on NET, U-OK / U-FAIL on dU'(tested_absent), H-SHARE; ACCEPT-2N / FAIL-2N / OPEN-2N.
NET = (ON corroborated - OFF corroborated) in pp of the WSJT-X decodes in the selected cycles; both arms are real product outputs (nc dumps) from sol.
dU' is computed as on TEST: the new-text, not-corroborated ON outputs, classified by the frozen instrument (classes from the Original arm) over cycles where WSJT-X decoded something.
Counts only leave this script; text lives in memory (HK-037)."""
import collections
import csv
import importlib.util
import json
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gr_common as C
import gg_lib as L

R = "D:/Projects/claude/_qa-scratch/coh-gate-r-f4"
CF = "D:/Projects/claude/OpenWSFZ/worktrees/qa/qa/rr-study/coh-fallback"
DLL = R + "/bin/libft8.dll"
WAV_ROOT = "D:/Projects/claude/OpenWSFZ/artefacts"
RUN = "20261022_1949"
NIGHT = WAV_ROOT + f"/{RUN}_endurance_run-gathered"
CLASSES = R + "/u2/orig_classes.json"
BAR_G, U_BAR_G, H = 0.5, 0.021, 0.5
B, SEED = 2000, 20261028
assert (BAR_G, U_BAR_G, H, B, SEED) == (0.5, 0.021, 0.5, 2000, 20261028)
HASHED = re.compile(r"<[^>]*>")
TEST_BASELINE_PCT = 81.37                      # the refset TEST baseline corroboration (descriptive comparison only)


def station_key(text):
    t = text.split()
    if not t:
        return ""
    if t[0] == "CQ":
        return t[2] if len(t) > 3 and t[1].isalpha() and len(t[1]) <= 4 else (t[1] if len(t) > 1 else "")
    return t[1] if len(t) > 1 else t[0]


def load_nc(arm):
    d = collections.defaultdict(list)
    for r in C.load_tsv(f"{R}/sol/scratch/{arm}/nc_dump.tsv"):
        if len(r) >= 11:
            d[r[0]].append(dict(kind=int(r[1]), matched=int(r[2]), f=int(r[3]), dt=float(r[4]), snr=int(r[5]), text="\t".join(r[10:])))
    for s in d:
        d[s].sort(key=lambda x: x["kind"])             # stable: kinds 1..4, as Replay81 scores them
    return d


def main():
    sel = json.load(open(R + "/selection_2n.json"))["runs"][RUN]["FULL"]
    stamps = [e if isinstance(e, str) else e[0] for e in sel]
    assert len(stamps) == 800
    C.ALLTXT = NIGHT + "/wsjt-x/ALL.TXT"
    ref = C.load_ref(set(stamps))
    n_ref = sum(len(ref.get(s, [])) for s in stamps)
    refc = np.array([float(len(ref.get(s, []))) for s in stamps])
    w = np.array([1.0 if ref.get(s) else 0.0 for s in stamps])
    off, on = load_nc("off"), load_nc("on")

    spec = importlib.util.spec_from_file_location("cf_uprime_mod", CF + "/cf_uprime.py")
    U = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(U)
    F, _ = U.load_instrument()
    enc = F.encoder(DLL)
    frozen = json.load(open(CLASSES))
    c_off = float(frozen["start_minus_dt_median_s"])
    testable = set(frozen["testable_classes"])
    pcms = {}

    def pcm_of(st):
        if st not in pcms:
            pcms[st] = F.wavio.load_cycle_pcm(os.path.join(NIGHT, "owsfz", "wav", st + ".wav"))
        return pcms[st]

    def status(stamp, text, freq, dt):
        tones = enc(text)
        if any(x.startswith("<") for x in text.split()) or tones is None:
            return "hashed_or_unencodable"
        if F.shape_class(text) not in testable:
            return "untestable_class"
        sh, outs = F.locate_and_score({}, pcm_of(stamp), freq, dt + c_off, F.DT_HALF_WINDOW_S, [tones[i] for i in F.SYNC_IDX], [tones])
        return "tested_present" if outs[0] >= U.T_FROZEN else "tested_absent"

    res = {"night": RUN, "cycles": len(stamps), "n_ref": n_ref, "cycles_with_wsjtx": int(w.sum())}
    cols = {k: np.zeros(len(stamps)) for k in ("net", "ta", "hu", "pres", "unt", "out", "conf", "hashed")}
    corr_off = corr_on = flag_off = flag_on = 0
    b4_off_rows = b4_off_conf = b4_on_rows = b4_on_conf = 0
    moved = same = 0
    by = collections.defaultdict(collections.Counter)
    stations = collections.Counter()
    for ci, s in enumerate(stamps):
        r = ref.get(s, [])
        o_rows, n_rows = off.get(s, []), on.get(s, [])
        o_uw, o_uo = L.match(r, [(x["kind"], x["f"], x["text"]) for x in o_rows])
        n_uw, n_uo = L.match(r, [(x["kind"], x["f"], x["text"]) for x in n_rows])
        corr_off += len(o_uw)
        corr_on += len(n_uw)
        flag_off += sum(x["matched"] for x in o_rows)
        flag_on += sum(x["matched"] for x in n_rows)
        cols["net"][ci] = len(n_uw) - len(o_uw)
        b4_off_rows += sum(1 for x in o_rows if x["kind"] == 4)
        b4_off_conf += sum(1 for i, x in enumerate(o_rows) if x["kind"] == 4 and i in o_uo)
        b4_on_rows += sum(1 for x in n_rows if x["kind"] == 4)
        b4_on_conf += sum(1 for i, x in enumerate(n_rows) if x["kind"] == 4 and i in n_uo)
        off_texts = {x["text"] for x in o_rows}
        off_b4 = {(x["f"], x["text"]) for x in o_rows if x["kind"] == 4}
        for i, x in enumerate(n_rows):
            if x["kind"] != 4:
                continue
            if x["text"] in off_texts:
                if (x["f"], x["text"]) in off_b4:
                    same += 1
                else:
                    moved += 1
                continue
            cols["out"][ci] += 1
            hs = bool(HASHED.search(x["text"]))
            cols["hashed"][ci] += hs
            by["band"][C.band_of(x["snr"])] += 1
            if i in n_uo:
                cols["conf"][ci] += 1
                stations[station_key(x["text"])] += 1
            else:
                sx = status(s, x["text"], x["f"], x["dt"])
                cols[{"tested_absent": "ta", "hashed_or_unencodable": "hu", "tested_present": "pres", "untestable_class": "unt"}[sx]][ci] += 1
    res["match_vs_replay_flag"] = {"off_L_match": corr_off, "off_flag_sum": flag_off, "on_L_match": corr_on, "on_flag_sum": flag_on,
                                   "PASS": corr_off == flag_off and corr_on == flag_on}
    res["baseline_OFF"] = {"corroborated": corr_off, "pct": 100.0 * corr_off / n_ref, "refset_TEST_pct": TEST_BASELINE_PCT,
                           "batch4_rows": b4_off_rows, "batch4_corroborated": b4_off_conf, "batch4_corr_share": b4_off_conf / b4_off_rows if b4_off_rows else None}
    res["ON"] = {"corroborated": corr_on, "pct": 100.0 * corr_on / n_ref, "batch4_rows": b4_on_rows, "batch4_corroborated": b4_on_conf}
    res["chain_rows"] = {"new_text": int(cols["out"].sum()), "moved_frequency": moved, "same_text_same_frequency": same,
                         "net_rows": b4_on_rows - b4_off_rows}

    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, len(stamps), size=(B, len(stamps)))
    den = refc[idx].sum(axis=1)
    net = 100.0 * cols["net"][idx].sum(axis=1) / den
    wcnt = w[idx].sum(axis=1)
    pc = lambda a: [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))]
    ta = cols["ta"][idx].sum(axis=1) / wcnt
    hu = cols["hu"][idx].sum(axis=1) / wcnt
    pres = cols["pres"][idx].sum(axis=1) / wcnt
    outs = cols["out"].sum()
    tot = sum(stations.values())
    r = {"NET_pp": 100.0 * cols["net"].sum() / refc.sum(), "NET_CI": pc(net),
         "dU_ta": cols["ta"].sum() / w.sum(), "dU_ta_CI": pc(ta), "dU_hu": cols["hu"].sum() / w.sum(), "dU_hu_CI": pc(hu),
         "dU_present": cols["pres"].sum() / w.sum(), "dU_present_CI": pc(pres), "dU_untestable_class": cols["unt"].sum() / w.sum(),
         "untestable_class_outputs": int(cols["unt"].sum()),
         "admitted_new_text": int(outs), "admitted_corroborated": int(cols["conf"].sum()),
         "corroborated_share": float(cols["conf"].sum() / outs) if outs else None,
         "hashed_share_of_new": float(cols["hashed"].sum() / outs) if outs else None,
         "by_band": dict(by["band"]),
         "stations_corroborated": {"distinct": len(stations), "top_share": (max(stations.values()) / tot) if tot else None,
                                   "top5_share": (sum(v for _, v in stations.most_common(5)) / tot) if tot else None}}
    res["R-F4"] = r
    rows = {"N-GO": r["NET_CI"][0] >= BAR_G, "N-STOP": r["NET_CI"][1] < BAR_G, "U-OK": r["dU_ta_CI"][1] <= U_BAR_G,
            "U-FAIL": r["dU_ta_CI"][0] > U_BAR_G, "H-SHARE_fires": (r["hashed_share_of_new"] or 0.0) > H}
    res["rows"] = rows
    res["HK026_untestable_class_outputs_need_refreeze"] = r["untestable_class_outputs"] > 0

    # ---- timing from the logs (descriptive) --------------------------------------------------------------------------------------------------
    def fb_end(arm):
        t = open(f"{R}/sol/raw/{arm}/log.log", encoding="utf-8", errors="replace").read()
        e = [int(a) + int(b) for a, b in re.findall(r"fbStartMs=(-?\d+), fbWallMs=(-?\d+)", t) if int(b) >= 0]
        return {"max_fallback_end_ms": max(e), "min_margin_to_13s_ms": 13000 - max(e), "fallback_lines": len(re.findall("Coherent fallback:", t))}
    res["timing"] = {"off": fb_end("off"), "on": fb_end("on")}
    verdict = ("ACCEPT-2N" if rows["N-GO"] and rows["U-OK"] and not rows["H-SHARE_fires"] else
               "FAIL-2N" if rows["N-STOP"] or rows["U-FAIL"] else "OPEN-2N")
    res["verdict"] = verdict
    json.dump(res, open(R + "/second_night_result.json", "w"), indent=1, default=float)
    print(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    main()
