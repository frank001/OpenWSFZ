#!/usr/bin/env python3
"""COH-GATE-G TRAIN, part 2: U' status of every GATED_OUT output that the ceiling would publish, V5, the DU' split, and the rule search.

Needs: the Original arm's frozen U' classes (cf_uprime.py `off` stage, written next to this script's output as classes json) and the BOTH arm.
Per-row U' status uses the frozen instrument exactly as cf_uprime.py does (tone presence of the 58 data symbols, T = 0.276, classes from the
Original arm alone). A row is 'confirmed' when the one-to-one Replay81 match (admit-all) pairs it with a WSJT-X decode; otherwise it is
tested_absent / tested_present / hashed_or_unencodable / untestable_class.

Rule search (section 4, as amended): conditions "feature <= / >= threshold" or "feature in set", at most two, thresholds on every 5th percentile of the
TRAIN G rows' own values. SELECTION uses an additive per-row proxy (each G row's contribution under the ceiling's publication), then the best
PROXY_TOP rules are re-evaluated EXACTLY (full offline publication, one-to-one match, exact DU') and the chosen rule is the exact best of them.
The proxy and the exact re-evaluation are both reported. Counts only.
"""
import collections
import importlib.util
import itertools
import json
import math
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
BAR_G_PP = 0.5
U_BAR_G = 0.021
PROXY_TOP = 300
PCT_STEP = 5
BAND = lambda snr: "A" if snr >= 0 else "B" if snr >= -10 else "C" if snr >= -15 else "D"


def load_cf_uprime():
    spec = importlib.util.spec_from_file_location("cf_uprime_mod", CF + "\\cf_uprime.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main(classes_json, out_json):
    U = load_cf_uprime()
    F, blob = U.load_instrument()
    enc = F.encoder(DLL)
    frozen = json.load(open(classes_json))
    c_off = float(frozen["start_minus_dt_median_s"])
    testable = set(frozen["testable_classes"])
    stamps = C.selection_stamps()
    ref = C.load_ref(set(stamps))
    n_ref = sum(len(v) for v in ref.values())
    arm = L.load_arm("both")
    pcms = {}

    def pcm_of(st):
        if st not in pcms:
            pcms[st] = F.wavio.load_cycle_pcm(os.path.join(WAV_ROOT, f"{RUN}_endurance_run-gathered", "owsfz", "wav", st + ".wav"))
        return pcms[st]

    def status(stamp, text, freq, dt):
        tones = enc(text)
        hashed = any(x.startswith("<") for x in text.split())
        if hashed or tones is None:
            return "hashed_or_unencodable"
        if F.shape_class(text) not in testable:
            return "untestable_class"
        sh, outs = F.locate_and_score({}, pcm_of(stamp), freq, dt + c_off, F.DT_HALF_WINDOW_S, [tones[i] for i in F.SYNC_IDX], [tones])
        return "tested_present" if outs[0] >= U.T_FROZEN else "tested_absent"

    ALL = lambda r: True
    NONE = lambda r: False
    # ---- per-row contributions under the ceiling's publication ----------------------------------------------------------------------------
    contrib = {}          # id(row) -> dict(confirmed, status, text, freq)
    rowlist = []
    base_matched = ceil_matched = 0
    v2_bad = 0
    for s in stamps:
        base13 = [(x[0], x[2], x[6]) for x in arm["nc"].get(s, []) if x[0] in (1, 2, 3)]
        none = L.publish(arm, s, NONE)
        prod4 = [(x[2], x[6]) for x in arm["nc"].get(s, []) if x[0] == 4]
        if [(f, t) for f, t, _ in none] != prod4:
            v2_bad += 1
        mn, _ = L.match(ref[s], base13 + [(4, f, t) for f, t, _ in none])
        base_matched += len(mn)
        allp = L.publish(arm, s, ALL)
        ows = base13 + [(4, f, t) for f, t, _ in allp]
        ma, mo = L.match(ref[s], ows)
        ceil_matched += len(ma)
        nb = len(base13)
        none_keys = {(f, t) for f, t, _ in none}
        for k, (f, t, r) in enumerate(allp):
            if r["state"] != "G" or (f, t) in none_keys:
                continue
            conf = (nb + k) in mo
            st = "confirmed" if conf else status(s, t, f, r["dt"] + r["ddt"])
            contrib[id(r)] = dict(confirmed=conf, status=st, stamp=s)
        for r in arm["rows"].get(s, []):
            if r["state"] == "G":
                rowlist.append((s, r))
    res = {"V2_cycles_not_reproduced": v2_bad, "n_ref": n_ref, "NET_all_pp": 100.0 * (ceil_matched - base_matched) / n_ref}
    n_cyc = sum(1 for s in stamps if ref[s])
    cnt = collections.Counter(c["status"] for c in contrib.values())
    res["ceiling_added_outputs"] = dict(cnt)
    res["ceiling_dU_per_cycle"] = {k: cnt[k] / n_cyc for k in ("tested_absent", "hashed_or_unencodable", "untestable_class", "tested_present")}
    res["ceiling_NET_confirmed_rows"] = cnt["confirmed"]

    # ---- features of every G row -------------------------------------------------------------------------------------------------------------
    for s, r in rowlist:
        f13 = [x[2] for x in arm["nc"].get(s, []) if x[0] in (1, 2, 3)]
        r["of"] = r["freq"] + r["dfreq"]
        r["nb50"] = any(abs(of - r["of"]) <= 50 for of in f13)
        r["absdf"] = abs(r["dfreq"])
        r["absdt"] = abs(r["ddt"])
        r["type4"] = (r["i3"] == 4)
        r["resid"] = (r["run"] == 0 and arm["runs"].get(s, 0) == 2)
        r["walk"] = (r["prov"] != 0)
        r["stamp"] = s
    Gs = [r for _, r in rowlist]
    num = {"f1b": ("f1b", "<="), "snr": ("snr", ">="), "absdf": ("absdf", "<="), "absdt": ("absdt", "<=")}
    conds = []
    for name, (key, op) in num.items():
        vals = np.array([r[key] for r in Gs], dtype=float)
        for q in range(PCT_STEP, 100, PCT_STEP):
            th = float(np.percentile(vals, q))
            conds.append((f"{name}{op}{th:.4g}", (lambda r, key=key, op=op, th=th: (r[key] <= th) if op == "<=" else (r[key] >= th))))
        if name == "snr":
            for q in range(PCT_STEP, 100, PCT_STEP):
                th = float(np.percentile(vals, q))
                conds.append((f"snr<={th:.4g}", (lambda r, th=th: r["snr"] <= th)))
    for name, fn in (("type4", lambda r: r["type4"]), ("not_type4", lambda r: not r["type4"]), ("residual_run", lambda r: r["resid"]),
                     ("original_run", lambda r: not r["resid"]), ("V3", lambda r: not r["walk"]), ("walk_set", lambda r: r["walk"]),
                     ("no_edge", lambda r: not r["edge"]), ("edge", lambda r: r["edge"]), ("nb50_yes", lambda r: r["nb50"]), ("nb50_no", lambda r: not r["nb50"])):
        conds.append((name, fn))
    rules = [((n,), (lambda r, f=f: f(r))) for n, f in conds]
    for (n1, f1), (n2, f2) in itertools.combinations(conds, 2):
        rules.append(((n1, n2), (lambda r, f1=f1, f2=f2: f1(r) and f2(r))))
    res["family_size"] = len(rules)

    def proxy(fn):
        net = ta = hu = 0
        adm = 0
        for r in Gs:
            c = contrib.get(id(r))
            if c is None or not fn(r):
                continue
            adm += 1
            if c["confirmed"]:
                net += 1
            elif c["status"] == "tested_absent":
                ta += 1
            elif c["status"] == "hashed_or_unencodable":
                hu += 1
        return net, ta, hu, adm
    scored = []
    for names, fn in rules:
        net, ta, hu, adm = proxy(fn)
        scored.append((net, -ta, names, fn, ta, hu, adm))
    cap = U_BAR_G * n_cyc
    ok = [x for x in scored if x[4] <= cap]
    ok.sort(key=lambda x: (-x[0], len(x[2]), x[4]))
    top = ok[:PROXY_TOP]
    res["proxy_best_rule"] = {"rule": list(top[0][2]), "NET_rows": top[0][0], "ta": top[0][4], "hu": top[0][5], "admitted": top[0][6]} if top else None

    # ---- exact re-evaluation of the proxy's top rules -----------------------------------------------------------------------------------------------
    def exact(fn):
        matched = 0
        ta = hu = 0
        adm_outputs = 0
        for s in stamps:
            base13 = [(x[0], x[2], x[6]) for x in arm["nc"].get(s, []) if x[0] in (1, 2, 3)]
            none = L.publish(arm, s, NONE)
            fb = L.publish(arm, s, fn)
            ows = base13 + [(4, f, t) for f, t, _ in fb]
            ma, mo = L.match(ref[s], ows)
            matched += len(ma)
            none_keys = {(f, t) for f, t, _ in none}
            nb = len(base13)
            for k, (f, t, r) in enumerate(fb):
                if (f, t) in none_keys:
                    continue
                adm_outputs += 1
                if (nb + k) in mo:
                    continue
                st = status_cache(s, t, f, r)
                if st == "tested_absent":
                    ta += 1
                elif st == "hashed_or_unencodable":
                    hu += 1
        return matched, ta, hu, adm_outputs
    sc = {}

    def status_cache(s, t, f, r):
        c = contrib.get(id(r))
        if c is not None and c["status"] != "confirmed":
            return c["status"]
        key = (s, t, f)
        if key not in sc:
            sc[key] = status(s, t, f, r["dt"] + r["ddt"])
        return sc[key]
    ex = []
    for net, nta, names, fn, ta, hu, adm in top:
        m, eta, ehu, eadm = exact(fn)
        ex.append(dict(rule=list(names), NET_pp=100.0 * (m - base_matched) / n_ref, dU_ta=eta / n_cyc, dU_hu=ehu / n_cyc, admitted_outputs=eadm,
                       proxy_net_rows=net, proxy_ta=ta))
    ex = [e for e in ex if e["dU_ta"] <= U_BAR_G]
    ex.sort(key=lambda e: (-e["NET_pp"], len(e["rule"]), e["dU_ta"]))
    res["exact_top"] = ex[:10]
    res["chosen"] = ex[0] if ex else None
    # f1 alone at its best T2 (D1 baseline)
    f1 = [x for x in ok if len(x[2]) == 1 and x[2][0].startswith("f1b")]
    f1.sort(key=lambda x: -x[0])
    if f1:
        m, eta, ehu, eadm = exact(f1[0][3])
        res["f1_alone_best"] = dict(rule=list(f1[0][2]), NET_pp=100.0 * (m - base_matched) / n_ref, dU_ta=eta / n_cyc, dU_hu=ehu / n_cyc)
    json.dump(res, open(out_json, "w"), indent=1, default=float)
    print(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
