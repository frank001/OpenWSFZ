#!/usr/bin/env python3
"""LATE-SUB L1' analysis (spec 8152d4ce + Amendment 1 e3fd391e). usage: l1p_analyse.py <name> verdict|refset
verdict : the verdict night 20261022_1949 (R-F4 frozen 800-cycle 2N selection and 2N U' classes); the ONE block is all selected cycles; the rows are evaluated here.
refset  : DESCRIPTIVE ONLY, refset 20260925_2010 TEST cycles 401-1,200 of a run that began at cycle 1; no verdict row is written.
NET = (matched reference rows with the L1' rows added) - (matched with the product alone), pp of n_ref, cycle bootstrap B = 2000, seed 20261030.
dU' = per cycle on tested_absent (U' instrument, classes frozen). H-SHARE = hashed/unencodable share of L1' outputs.
Bars (COH-GATE-G, re-used; the Captain's 'agreed' and 'go with your recommendations'): BAR_G 0.5 pp, U_bar_G 0.021 (tested_absent only), h 0.5. Counts and rates only; text is read in memory."""
from __future__ import annotations

import collections
import csv
import hashlib
import importlib.util
import json
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "gap-relocate-run"))
import gr_common as C       # noqa: E402
import gg_lib as L          # noqa: E402

cfg, kind = sys.argv[1], sys.argv[2]
assert kind in ("verdict", "refset")
S = "D:/Projects/claude/_qa-scratch/late-sub"
R4 = "D:/Projects/claude/_qa-scratch/coh-gate-r-f4"
CF = os.path.join(HERE, "..", "coh-fallback")
DLL = S + "/bin_l1p/libft8.dll"
ART = "D:/Projects/claude/OpenWSFZ/artefacts"
BAR_G, U_BAR_G, H = 0.5, 0.021, 0.5
B, SEED = 2000, 20261030
assert (BAR_G, U_BAR_G, H, B, SEED) == (0.5, 0.021, 0.5, 2000, 20261030)
if kind == "verdict":
    RUN, SELF, CLASSES = "20261022_1949", R4 + "/selection_2n.json", R4 + "/u2/orig_classes.json"
    PINS = {SELF: "cf9908a5dcc66ef8966693b2d29ae5bd04fc357d3e1af5058b0e35d7eea6726e", CLASSES: "0d83d685db2aee961211b022d5b563c0b5b24a83e51f16c126d0f6cff870ab25"}
    N_REF_EXPECTED = 20753
else:
    RUN, SELF, CLASSES = "20260925_2010", R4 + "/selection1200.json", "D:/Projects/claude/_qa-scratch/coh-gate-g/u/uprime_orig_classes.json"
    PINS = {SELF: None, CLASSES: None}
    N_REF_EXPECTED = None
for p, want in PINS.items():
    if want:
        assert hashlib.sha256(open(p, "rb").read()).hexdigest() == want, f"{p} differs from the frozen hash"
C.ALLTXT = f"{ART}/{RUN}_endurance_run-gathered/wsjt-x/ALL.TXT"
WAVDIR = f"{ART}/{RUN}_endurance_run-gathered/owsfz/wav"


def main():
    sel = json.load(open(SELF))["runs"][RUN]["FULL"]
    stamps = [e if isinstance(e, str) else e[0] for e in sel]
    cyc = {r["stamp"]: r for r in csv.DictReader(open(f"{S}/ls/l1p_{cfg}/ls_cycle.tsv", encoding="utf-8"), delimiter="\t")}
    assert list(cyc) == stamps[:len(cyc)], "ls_cycle.tsv is not the selection's cycles in order"
    full = len(cyc) == len(stamps)
    stamps = stamps[:len(cyc)]
    ref = C.load_ref(set(stamps))
    refc = np.array([float(len(ref.get(s, []))) for s in stamps])
    w = np.array([1.0 if ref.get(s) else 0.0 for s in stamps])
    if kind == "verdict" and full:
        assert int(refc.sum()) == N_REF_EXPECTED, f"n_ref {refc.sum()} != {N_REF_EXPECTED} (V8)"
    nc = collections.defaultdict(list)
    for r in C.load_tsv(f"{S}/scratch/l1p_{cfg}/nc_dump.tsv"):
        if len(r) >= 11:
            nc[r[0]].append((int(r[1]), int(r[2]), int(r[3]), float(r[4]), int(r[5]), int(r[9]), r[10]))
    arm_rows = collections.defaultdict(list)
    for line in open(f"{S}/ls/l1p_{cfg}/ls_rows.tsv", encoding="utf-8"):
        p = line.rstrip("\n").split("\t")
        assert p[1] == "L1", "L1' mode must hold L1 rows only"
        arm_rows[p[0]].append((int(p[2]), float(p[3]), int(p[4]), p[5]))
    spec = importlib.util.spec_from_file_location("cf_uprime_mod", CF + "/cf_uprime.py")
    U = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(U)
    F, blob = U.load_instrument()
    frozen = json.load(open(CLASSES))
    assert frozen["instrument_blob"] == blob, "the class file was frozen with another instrument"
    enc = F.encoder(DLL)
    c_off = float(frozen["start_minus_dt_median_s"])
    testable = set(frozen["testable_classes"])
    pcms = {}

    def pcm_of(st):
        if st not in pcms:
            pcms[st] = F.wavio.load_cycle_pcm(os.path.join(WAVDIR, st + ".wav"))
        return pcms[st]
    cache = {}

    def status(stamp, text, freq, dt):
        key = (stamp, text, freq, dt)
        if key in cache:
            return cache[key]
        tones = enc(text)
        if any(x.startswith("<") for x in text.split()) or tones is None:
            r = "hashed_or_unencodable"
        elif F.shape_class(text) not in testable:
            r = "untestable_class"
        else:
            sh, outs = F.locate_and_score({}, pcm_of(stamp), freq, dt + c_off, F.DT_HALF_WINDOW_S, [tones[i] for i in F.SYNC_IDX], [tones])
            r = "tested_present" if outs[0] >= U.T_FROZEN else "tested_absent"
        cache[key] = r
        return r

    n = len(stamps)
    cols = {k: np.zeros(n) for k in ("net", "ta", "hu", "pres", "unt", "out", "conf", "hashed")}
    for ci, s in enumerate(stamps):
        base = [(x[0], x[2], x[6]) for x in nc.get(s, [])]
        uw0, _ = L.match(ref.get(s, []), base)
        extra = [(6, f, t) for f, dt, snr, t in arm_rows[s]]
        uw, uo = L.match(ref.get(s, []), base + extra)
        cols["net"][ci] = len(uw) - len(uw0)
        for k0, (f, dt, snr, t) in enumerate(arm_rows[s]):
            idx = len(base) + k0
            cols["out"][ci] += 1
            if "<" in t:
                cols["hashed"][ci] += 1
            if idx in uo:
                cols["conf"][ci] += 1
            else:
                sx = status(s, t, f, dt)
                cols[{"tested_absent": "ta", "hashed_or_unencodable": "hu", "tested_present": "pres", "untestable_class": "unt"}[sx]][ci] += 1
    out = {"config": cfg, "kind": kind, "night": RUN, "cycles": n, "full_selection": full, "n_ref": float(refc.sum()), "cycles_with_ref": int(w.sum()),
           "level_counts": dict(collections.Counter(r["level"] for r in cyc.values())), "l_outcomes": dict(collections.Counter(r["l_outcome"] for r in cyc.values())),
           "fit_list": {"entries": int(sum(int(r["fit_n"]) for r in cyc.values())), "refused_by_IsReencodable_or_Encode": int(sum(int(r["fit_refused"]) for r in cyc.values()))},
           "classes": {"file": os.path.basename(CLASSES), "testable_classes": len(testable), "instrument_blob": blob}}
    rng = np.random.default_rng(SEED)

    def block(lo, hi):
        idx = rng.integers(lo, hi, size=(B, hi - lo))
        den = refc[idx].sum(axis=1)
        wc = w[idx].sum(axis=1)
        pc = lambda a: [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))]
        net = 100.0 * cols["net"][idx].sum(axis=1) / den
        ta = cols["ta"][idx].sum(axis=1) / wc
        outs = cols["out"][lo:hi].sum()
        res = {"cycles": hi - lo, "n_ref": float(refc[lo:hi].sum()),
               "NET_pp": 100.0 * cols["net"][lo:hi].sum() / refc[lo:hi].sum(), "NET_CI": pc(net),
               "dU_ta": cols["ta"][lo:hi].sum() / w[lo:hi].sum(), "dU_ta_CI": pc(ta),
               "dU_hu": cols["hu"][lo:hi].sum() / w[lo:hi].sum(), "dU_present": cols["pres"][lo:hi].sum() / w[lo:hi].sum(),
               "added_outputs": int(outs), "added_corroborated": int(cols["conf"][lo:hi].sum()),
               "added_tested_absent": int(cols["ta"][lo:hi].sum()), "added_hashed_or_unencodable": int(cols["hu"][lo:hi].sum()), "added_hashed_flag": int(cols["hashed"][lo:hi].sum()),
               "unconfirmed_in_untestable_class": int(cols["unt"][lo:hi].sum()),
               "hashed_share_of_added": float(cols["hashed"][lo:hi].sum() / outs) if outs else None,
               "cycles_L_ran": sum(1 for r in list(cyc.values())[lo:hi] if r["l_outcome"] == "ran"),
               "cycles_L_skipped": sum(1 for r in list(cyc.values())[lo:hi] if r["l_outcome"] != "ran")}
        return res

    if kind == "verdict":
        r = block(0, n)
        out["block"] = r
        # HK-026 (mechanical): an unconfirmed L1' output in untestable_class => re-freeze from all 800 cycles BEFORE the U rows are computed. The verdict rows are withheld.
        if r["unconfirmed_in_untestable_class"] > 0:
            out["HK026_REFREEZE_REQUIRED"] = True
            out["verdict"] = "WITHHELD: re-freeze the classes from all 800 cycles first (Amendment 1 E3)"
        else:
            out["HK026_REFREEZE_REQUIRED"] = False
            go = r["NET_CI"][0] >= BAR_G
            ok = r["dU_ta_CI"][1] <= U_BAR_G and (r["hashed_share_of_added"] or 0.0) <= H
            out["verdict"] = "L1p-GO" if go and ok else "L1p-COST" if go else "L1p-STOP" if r["NET_CI"][1] < BAR_G else "L1p-OPEN"
    else:
        if os.environ.get("L1P_SMOKE") == "1":                   # code smoke test on the already-read refset pilot only: never on the verdict night
            out["SMOKE_all_cycles"] = block(0, n)
        else:
            assert n >= 1200, "the descriptive refset leg needs the run from cycle 1 to cycle 1,200"
            out["TEST_401_1200"] = block(400, 1200)
        out["verdict"] = "none (descriptive)"

    # timing (descriptive; the PC)
    log = open(f"{S}/raw/l1p_{cfg}/log.log", encoding="utf-8", errors="replace").read()
    fb = [(int(a), int(b_)) for a, b_ in re.findall(r"fbStartMs=(-?\d+), fbWallMs=(-?\d+)", log)]
    q = lambda v: {"median": float(np.median(v)), "p90": float(np.percentile(v, 90)), "max": float(np.max(v)), "n": len(v)} if len(v) else None
    ms_l = np.array([float(r["ms_Lround"]) for r in cyc.values() if r["level"] != "O"])
    out["timing_ms"] = {"L1p_round": q(ms_l)}
    if len(fb) == n:
        end = np.array([a + b_ for a, b_ in fb], dtype=float)
        out["timing_ms"]["T2_end_of_work_vs_13s"] = {"product_fallback_end": q(end), "with_L1p": q(end + ms_l[:n] if len(ms_l) == n else end), "budget_ms": 13000}
    json.dump(out, open(f"{S}/l1p_result_{cfg}.json", "w"), indent=1, default=float)
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
