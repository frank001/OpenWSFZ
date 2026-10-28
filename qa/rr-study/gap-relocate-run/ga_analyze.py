#!/usr/bin/env python3
"""COH-GATE-G R-F4 acceptance rows B-OFF, B-EQ (A1.2), B-AB on the PC arms (OFF = setting absent, ON = --ungated 1), 1,200 cycles.
References: the recorded main arms of COH-GATE-G (TRAIN 'both' = cycles 1-400, TEST 'test' = cycles 401-1,200; same build 95e69e87, same settings) and the
offline R-F4 publication (gg_lib.publish with the residual-run admit). Counts only; text in memory only (HK-037)."""
import collections
import csv
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gr_common as C
import gg_lib as L

R = r"D:\Projects\claude\_qa-scratch\coh-gate-r-f4"
RUN = "20260925_2010"
HASHED = re.compile(r"<[^>]*>")


def load_nc(arm):
    d = collections.defaultdict(list)
    for r in C.load_tsv(f"{R}\\scratch\\{arm}\\nc_dump.tsv"):
        if len(r) >= 11:
            d[r[0]].append((int(r[1]), int(r[3]), r[10]))
    return d


def main():
    sel = json.load(open(R + "\\selection1200.json"))["runs"][RUN]["FULL"]
    stamps = [e if isinstance(e, str) else e[0] for e in sel]
    assert len(stamps) == 1200
    train, test = L.load_arm("both"), L.load_arm("test")
    ref_main = {}
    for i, s in enumerate(stamps):
        a = train if i < 400 else test
        ref_main[s] = [(x[0], x[2], x[6]) for x in a["nc"].get(s, [])]
    off, on = load_nc("off"), load_nc("on")
    # the STRICT B-OFF reference is the continuous one-process main arm over cycles 1-1200 (QA ledger Q27); the recorded TRAIN/TEST arms are the fallback
    cont = os.path.isfile(R + "\scratch_main\main\nc_dump.tsv")
    if cont:
        main_nc = load_nc("main", "scratch_main")
        ref_main = {s: [(x[0], x[1], x[2]) for x in main_nc.get(s, [])] for s in stamps}
    res = {"cycles": len(stamps)}

    # ---- B-OFF: setting absent == main, per cycle, all batches --------------------------------------------------------------------------------------
    bad = 0
    first_bad = None
    b4_off = {"train": 0, "test": 0}
    for i, s in enumerate(stamps):
        mine = sorted((k, f, t) for k, f, t in off.get(s, []))
        if mine != sorted(ref_main[s]):
            bad += 1
            first_bad = first_bad if first_bad is not None else i + 1
        b4_off["train" if i < 400 else "test"] += sum(1 for k, _, _ in off.get(s, []) if k == 4)
    res["B-OFF"] = {"reference": "continuous main arm (one process, cycles 1-1200)" if cont else "recorded TRAIN/TEST arms (TEST started at cycle 401: hashed text can differ)", "cycles_differing": bad, "first_differing_cycle_index": first_bad, "batch4_train": b4_off["train"], "batch4_test": b4_off["test"],
                    "expected": [1350, 2891], "PASS": bad == 0 and b4_off["train"] == 1350 and b4_off["test"] == 2891}

    # ---- B-EQ: setting ON vs the offline R-F4 publication ---------------------------------------------------------------------------------------------
    plain_diff = hashed_count_diff = 0
    first_plain = first_hash = None
    adds = {"train": 0, "test": 0}
    single_run = 0
    for i, s in enumerate(stamps):
        a = train if i < 400 else test
        two = a["runs"].get(s, 0) == 2
        if not two:
            single_run += 1
        fb = L.publish(a, s, (lambda r, two=two: two and r["run"] == 0))
        off_texts = {t for k, _, t in ref_main[s] if k == 4}
        ref_fb = [(f, t) for f, t, _ in fb]
        mine = [(f, t) for k, f, t in on.get(s, []) if k == 4]
        rp = sorted(x for x in ref_fb if not HASHED.search(x[1]))
        mp = sorted(x for x in mine if not HASHED.search(x[1]))
        if rp != mp:
            plain_diff += 1
            first_plain = first_plain if first_plain is not None else i + 1
        rh = sum(1 for x in ref_fb if HASHED.search(x[1]))
        mh = sum(1 for x in mine if HASHED.search(x[1]))
        if rh != mh:
            hashed_count_diff += 1
            first_hash = first_hash if first_hash is not None else i + 1
        adds["train" if i < 400 else "test"] += sum(1 for _, t in mine if t not in off_texts)
        # batches 1-3 of the ON arm must equal main too (the feature touches batch 4 only)
    b13_bad = sum(1 for s in stamps if sorted(x for x in on.get(s, []) if x[0] != 4) != sorted(x for x in ref_main[s] if x[0] != 4))
    res["B-EQ"] = {"cycles_plain_text_differing": plain_diff, "first_plain_diff_cycle_index": first_plain,
                   "cycles_hashed_count_differing": hashed_count_diff, "first_hashed_diff_cycle_index": first_hash,
                   "new_text_additions_train": adds["train"], "new_text_additions_test": adds["test"], "expected_additions": [255, 522],
                   "single_run_cycles": single_run, "batches_1_3_differing_cycles_ON_vs_main": b13_bad,
                   "PASS": plain_diff == 0 and b13_bad == 0}

    # ---- B-AB and descriptive timing -----------------------------------------------------------------------------------------------------------------
    def ab(arm):
        coh = list(csv.DictReader(open(f"{R}\\raw\\{arm}\\coh.csv")))
        rows = [l.strip().split(",") for l in open(f"{R}\\raw\\{arm}\\abandon.csv") if l[:1].isdigit()]
        ends = [float(r["fb_start_ms"]) + float(r["fb_wall_ms"]) for r in coh if float(r["fb_wall_ms"]) >= 0]
        log = open(f"{R}\\raw\\{arm}\\log.log", encoding="utf-8", errors="replace").read()
        lv = collections.Counter(re.findall(r"audio=both\((\w+)\)", log))
        ung = sum(int(x) for x in re.findall(r"ungated=(\d+)", log))
        return {"fallback_abandoned": sum(int(r["abandoned"]) for r in coh), "residual_ran": sum(int(r[1]) for r in rows),
                "residual_abandoned": sum(int(r[2]) for r in rows), "residual_contained": sum(int(r[3]) for r in rows),
                "max_fallback_end_ms": max(ends) if ends else None, "min_margin_to_13s_ms": 13000 - max(ends) if ends else None,
                "levels": dict(lv), "ungated_total_in_log": ung}
    res["B-AB"] = {"off": ab("off"), "on": ab("on")}

    # ---- the game's effect, descriptive (Architect, 2026-10-28): cycles after the Captain started a game on the PC (18:18:00Z, raw/captain_load_note.txt)
    # against the cycles before it, per arm: abandoned counts, maximum fallback end, elapsed per cycle. The cycle's time stamp is the 'Coherent fallback' log line's.
    import datetime
    GAME = datetime.datetime(2026, 10, 28, 18, 18, 0)
    notes = open(R + "\\raw\\captain_load_note.txt").read()

    def game_effect(arm):
        log = open(f"{R}\\raw\\{arm}\\log.log", encoding="utf-8", errors="replace").read().splitlines()
        stamps_t = [datetime.datetime.strptime(l[:19], "%Y-%m-%dT%H:%M:%S") for l in log if "Coherent fallback:" in l]
        coh = list(csv.DictReader(open(f"{R}\\raw\\{arm}\\coh.csv")))
        run = list(csv.DictReader(open(f"{R}\\raw\\{arm}\\run.csv")))
        ab_rows = [l.strip().split(",") for l in open(f"{R}\\raw\\{arm}\\abandon.csv") if l[:1].isdigit()]
        out = {}
        n = min(len(stamps_t), len(coh), len(run), len(ab_rows))
        for label, pick in (("before", lambda t: t < GAME), ("after", lambda t: t >= GAME)):
            idx = [i for i in range(n) if pick(stamps_t[i])]
            el = sorted(float(run[i]["elapsed_ms"]) for i in idx)
            ends = [float(coh[i]["fb_start_ms"]) + float(coh[i]["fb_wall_ms"]) for i in idx if float(coh[i]["fb_wall_ms"]) >= 0]
            out[label] = {"cycles": len(idx), "fallback_abandoned": sum(int(coh[i]["abandoned"]) for i in idx),
                          "residual_abandoned": sum(int(ab_rows[i][2]) for i in idx),
                          "max_fallback_end_ms": max(ends) if ends else None,
                          "elapsed_ms_median": el[len(el) // 2] if el else None, "elapsed_ms_p95": el[int(0.95 * len(el))] if el else None,
                          "elapsed_ms_max": el[-1] if el else None}
        return out
    res["game_effect"] = {"note": notes.strip(), "off": game_effect("off"), "on": game_effect("on")}
    res["B-AB"]["PASS"] = all(res["B-AB"][a]["fallback_abandoned"] == 0 and res["B-AB"][a]["residual_abandoned"] == 0 for a in ("off", "on"))
    res["ALL_PASS_given_B-NAT"] = res["B-OFF"]["PASS"] and res["B-EQ"]["PASS"] and res["B-AB"]["PASS"]
    json.dump(res, open(R + "\\acceptance.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
