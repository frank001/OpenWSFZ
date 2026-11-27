#!/usr/bin/env python3
"""R1-R4 split (the Architect's follow-up to SUB-PROBE): why were decoded results NEVER subtracted?  Data on disk only: no build, no replay.

  python -I r1r4_split.py            (reads lc-base\\runs\\probe_<slice>_L_n<cycles>\\{probe.tsv, matched.csv, matchedbatch.csv, sel.json, lean.csv, log.log} and the text-bearing result dump)

Privacy (HK-037 / NFR-021): the message text of a result is read INSIDE ONE function (load_results) that returns a boolean only (re-encodable or not); no text is stored, printed or written.
Output: counts and numbers only, to stdout and to _qa-scratch\\lc-base\\r1r4_split.json.

THE CAUSES (code read at main 326538fb, native/ftz_decoder/ftz_decoder.c; the round loop is `for round = 0..3`, round r >= 1 first selects for fitting the results found by round r-1):
  R1  text gate: ftz_text_reencodable(text) is false (the text has '<' or fewer than 3 tokens), line 1029 / 744  -> the result is never fitted (per result, from its text)
  R2  fit skipped by the step-2e rule (line 1031): no candidate of the round that found the result FAILED within [f - 50, f + 100] Hz  -> per result, from the probe's failed CAND rows of that round
  R3  fit tried, no valid fit (rc -3, line 1088): the remainder of the results that pass R1 and R2 and have no SUB row   -> per result by elimination; the cycle totals (fitNone=) check it
  R4  the round that would have fitted it never ran: the result was found in the LAST round (3), or the cycle was abandoned / the fit cancelled  -> per result (round) + cycle flags
  XC  a cross-cycle decode (batch 3): found outside the round loop, never fitted by construction (the Architect's list had R1-R4 only; shown separately)
  SUB the result has a SUB row (it WAS subtracted)
  UNLINKED  no published CAND row within the tolerance of the result (the round could not be read)
"""
import csv
import json
import os
import re
import statistics
import sys
from collections import Counter

sys.argv = [sys.argv[0], "probe"]                      # sub_probe_analyze reads sys.argv[1] at import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sub_probe_analyze as sp                          # noqa: E402  (loaders, constants, the T/N definitions: the SAME code that produced the 157 / 105 / 266)

SC = sp.SC
SLICES = ["S40", "H40", "H20"]
LAST_ROUND = 3                                          # FTZ_MAX_ROUNDS (ftz_decoder.c): rounds 0..3
PATCH_BELOW_HZ, PATCH_ABOVE_HZ = 50.0, 100.0           # FTZ_PATCH_BELOW_HZ / FTZ_PATCH_ABOVE_HZ (ftz_patch_keep, line 692ff)
INHERITED = {                                           # from the committed SUB-PROBE result (sub_probe_probe.json), asserted so a changed input cannot pass unnoticed
    "S40": {"classified": 667, "k2": 436, "k2_not_sub": 157, "k2_batch": {1: 110, 2: 22, 3: 25}},
    "H40": {"classified": 696, "k2": 495, "k2_not_sub": 105, "k2_batch": {1: 36, 2: 17, 3: 52}},
    "H20": {"classified": 914, "k2": 686, "k2_not_sub": 266, "k2_batch": {1: 143, 2: 29, 3: 94}},
}
R_KIND, R_ROUND, R_F, R_T, R_SUPP, R_OUT = sp.R_KIND, sp.R_ROUND, sp.R_F, sp.R_T, sp.R_SUPP, sp.R_OUT


def text_gate(text):
    """ftz_text_reencodable, line for line (no '<' and at least three space-separated tokens), but says WHICH half fails: 'OK', 'HASH' (a '<' placeholder) or 'TOKENS' (fewer than three tokens)."""
    if "<" in text:
        return "HASH"
    return "OK" if len([t for t in text.split(" ") if t]) >= 3 else "TOKENS"


def load_results(path):
    """stamp -> [(freq_hz, dt, reencodable)] for the lean's published results. THE ONLY FUNCTION THAT READS MESSAGE TEXT; it returns a gate code (OK / HASH / TOKENS). One row per (stamp, text), as dr0_run.py does."""
    out, seen = {}, set()
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            c = line.rstrip("\n").split("\t")
            if len(c) < 11:
                continue
            key = (c[0], c[10])
            if key in seen:
                continue
            seen.add(key)
            out.setdefault(c[0], []).append((float(c[3]), float(c[4]), text_gate(c[10])))
    return out


def load_log(path):
    """The lean cycle lines, in order: {hhmmss, per round r1..r3: fits/skipped/subtracted/fitNone/results, abandoned}. Numbers only."""
    cyc = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = re.search(r"Cycle (\d\d):(\d\d):(\d\d): lean:", line)
            if not m or "r1[" not in line:
                continue
            rec = {"hms": m.group(1) + m.group(2) + m.group(3), "abandoned": int(re.search(r"abandoned=(\d+)", line).group(1)), "error": int(re.search(r"error=(\d+)", line).group(1))}
            for r in (1, 2, 3):
                b = re.search(r"r%d\[([^\]]*)\]" % r, line)
                if b:
                    kv = dict(re.findall(r"(\w+)=([\d.]+)", b.group(1)))
                    rec["r%d" % r] = {k: int(float(kv[k])) for k in ("fits", "skipped", "subtracted", "fitNone", "results")}
            cyc.append(rec)
    return cyc


def link_round(prb_rows, f, dt):
    """The published CAND row nearest to a result: (round, row) or None."""
    best = None
    for r in prb_rows:
        if r[R_KIND] == sp.KIND_CAND and r[R_OUT] in sp.PUBLISHED and abs(r[R_F] - f) <= sp.TOL_HZ and abs(r[R_T] - dt) <= sp.TOL_S:
            d = abs(r[R_F] - f) / sp.TOL_HZ + abs(r[R_T] - dt) / sp.TOL_S
            if best is None or d < best[0]:
                best = (d, r)
    return best[1] if best else None


def sub_at(subs, f, dt):
    best = None
    for r in subs:
        if abs(r[R_F] - f) <= sp.TOL_HZ and abs(r[R_T] - dt) <= sp.TOL_S:
            d = abs(r[R_F] - f) / sp.TOL_HZ + abs(r[R_T] - dt) / sp.TOL_S
            if best is None or d < best[0]:
                best = (d, r)
    return best[1] if best else None


def classify(prb_rows, subs, f, dt, gate, batch, cycle_flag):
    """One result -> SUB | XC | R4 | R1 | R2 | R3 | UNLINKED, in this order (each cause is exclusive: a result is in the first class it meets)."""
    if sub_at(subs, f, dt) is not None:
        return "SUB", None
    if batch == 3:
        return "XC", None
    row = link_round(prb_rows, f, dt)
    if row is None:
        return "UNLINKED", None
    rnd = row[R_ROUND]
    if rnd >= LAST_ROUND or cycle_flag:
        return "R4", rnd
    if gate != "OK":
        return "R1h" if gate == "HASH" else "R1t", rnd           # R1 = R1h (hash placeholder) + R1t (fewer than three tokens)
    failed = [r[R_F] for r in prb_rows if r[R_KIND] == sp.KIND_CAND and r[R_ROUND] == rnd and r[R_OUT] in sp.FAILED]
    if not any(f - PATCH_BELOW_HZ <= x <= f + PATCH_ABOVE_HZ for x in failed):       # ftz_fit_needed(result_hz = f, failed_hz)
        return "R2", rnd
    return "R3", rnd


def run_slice(name):
    n, folder = sp.SL[name]
    d = SC + r"\lc-base\runs\probe_%s_L_n%d" % (name, n)
    sel = json.load(open(os.path.join(d, "sel.json")))
    stamps = list(sel["runs"][sel["run"]]["FULL"])
    wl = sp.load_wsjtx(os.path.join(sp.ART, folder, "wsjt-x", "ALL.TXT"), stamps)
    M, MB = sp.load_matched(d), sp.load_batch(d)
    prb, overflow = sp.load_probe(os.path.join(d, "probe.tsv"))
    off = statistics.median(sp.calibrate(wl, M, prb))
    res = load_results(os.path.join(d, "nc" + ".tsv"))
    log = load_log(os.path.join(d, "log.log"))
    lean = list(csv.DictReader(open(os.path.join(d, "lean.csv"), newline="")))
    assert len(log) == len(stamps) == len(lean) == n, (len(log), len(stamps), len(lean), n)
    for st, rec, lr in zip(stamps, log, lean):                  # alignment: the log line, lean.csv row and stamp are the same cycle
        assert lr["stamp"] == st and st[-6:] == rec["hms"], (st, rec["hms"], lr["stamp"])
    flag = {}
    for st, rec in zip(stamps, log):
        cancelled = sum(rec[r]["fits"] - rec[r]["subtracted"] - rec[r]["fitNone"] for r in ("r1", "r2", "r3") if r in rec)
        flag[st] = rec["abandoned"] == 1 or rec["error"] == 1 or cancelled != 0

    # ---- (A) THE BASE RATE: every published result of every cycle ----
    base = Counter()
    base_by_round = {}
    per_cycle = {}
    for st in stamps:
        rows = prb.get(st, [])
        subs = [r for r in rows if r[R_KIND] == sp.KIND_SUB]
        c = Counter()
        for (f, dt, gate) in res.get(st, []):
            cls, rnd = classify(rows, subs, f, dt, gate, 0, flag[st])
            c[cls] += 1
            base[cls] += 1
            if rnd is not None:
                base_by_round.setdefault(cls, Counter())[rnd] += 1
        per_cycle[st] = c

    # ---- (B) CYCLE-TOTAL CHECK: the per-result classes against the log's per-round counts ----
    tot = Counter()
    for st, rec in zip(stamps, log):
        for r in ("r1", "r2", "r3"):
            if r in rec:
                tot["skipped"] += rec[r]["skipped"]; tot["subtracted"] += rec[r]["subtracted"]; tot["fitNone"] += rec[r]["fitNone"]; tot["fits"] += rec[r]["fits"]
    sub_rows = sum(1 for rr in prb.values() for r in rr if r[R_KIND] == sp.KIND_SUB)
    n_res = sum(len(v) for v in res.values())
    xc_flag = sum(1 for lr in lean if int(lr["xc_detected"]) > 0)
    lean_results = sum(int(lr["results"]) for lr in lean)

    # ---- (C) THE K2 NEIGHBOURS, per neighbour: the same T / N definitions as sub_probe_analyze.run_slice ----
    k2_n, k2_ns, k2_cls, k2_round, k2_all = 0, 0, Counter(), Counter(), 0
    nbr_class = {k: Counter() for k in ("K0", "K1", "K2", "K3", "K4")}
    classified = 0
    k2_batch_unsub = Counter()
    for st in stamps:
        w, rows, ml = wl[st], prb.get(st, []), M.get(st, set())
        subs = [r for r in rows if r[R_KIND] == sp.KIND_SUB]
        cand_low = [r for r in rows if r[R_KIND] in (sp.KIND_CAND, sp.KIND_LOW)]
        for j, (snr, f, dt) in enumerate(w):
            others = [(abs(w[i][1] - f), i) for i in range(len(w)) if i != j]
            if not others or sum(1 for dd, _ in others if dd <= sp.CROWD_HZ) < 1 or j in ml:
                continue
            _, ni = min(others)
            if ni not in ml:
                continue
            classified += 1
            nsnr, nf, ndt = w[ni]
            tt = dt + off
            near = [r for r in cand_low if abs(r[R_F] - f) <= sp.TOL_HZ and abs(r[R_T] - tt) <= sp.TOL_S and abs(r[R_F] - f) <= abs(r[R_F] - nf)]
            if any(r[R_KIND] == sp.KIND_CAND and r[R_OUT] in sp.PUBLISHED for r in near):
                cls = "K0"
            elif any(r[R_KIND] == sp.KIND_CAND and r[R_OUT] in sp.DROPPED for r in near):
                cls = "K1"
            elif any(r[R_KIND] == sp.KIND_CAND and r[R_OUT] in sp.FAILED for r in near):
                cls = "K2"
            elif any((r[R_KIND] == sp.KIND_CAND and r[R_OUT] in sp.NOT_KEPT) or r[R_KIND] == sp.KIND_LOW for r in near):
                cls = "K3"
            else:
                cls = "K4"
            # N's lean result: the lean result nearest to N's position in the probe's time convention (nf, ndt + off)
            best = None
            for (rf, rdt, rgate) in res.get(st, []):
                if abs(rf - nf) <= sp.TOL_HZ and abs(rdt - (ndt + off)) <= sp.TOL_S:
                    dd = abs(rf - nf) / sp.TOL_HZ + abs(rdt - (ndt + off)) / sp.TOL_S
                    if best is None or dd < best[0]:
                        best = (dd, rf, rdt, rgate)
            has_sub = sub_at(subs, nf, ndt + off) is not None
            if has_sub:
                nbr_class[cls]["SUB"] += 1
                continue
            batch = MB.get((st, ni), 0)
            if cls == "K2":
                k2_batch_unsub[batch] += 1
            if best is None:
                nbr_class[cls]["NO_LEAN_RESULT"] += 1
                continue
            c, rnd = classify(rows, subs, best[1], best[2], best[3], batch, flag[st])
            if c == "SUB":                                    # the WSJT-X-position match (SUB-PROBE's rule, inherited) missed it, the result's OWN position finds a SUB row: reported, kept inside the inherited 'never subtracted' count
                c = "SUB_FOUND_BY_RESULT_POSITION"
            nbr_class[cls][c] += 1
            if cls == "K2":
                k2_round[(c, rnd)] += 1
    assert classified == INHERITED[name]["classified"], (classified, INHERITED[name])
    k2_total = sum(nbr_class["K2"].values())
    k2_unsub = k2_total - nbr_class["K2"]["SUB"]
    assert k2_total == INHERITED[name]["k2"], (k2_total, INHERITED[name])
    assert dict(k2_batch_unsub) == INHERITED[name]["k2_batch"], (dict(k2_batch_unsub), INHERITED[name]["k2_batch"])
    assert k2_unsub == INHERITED[name]["k2_not_sub"], (k2_unsub, dict(nbr_class["K2"]), INHERITED[name])
    out = {
        "cycles": n, "dt_offset": round(off, 3), "results_in_dump": n_res, "lean_csv_results": lean_results, "sub_rows": sub_rows,
        "flagged_cycles_abandoned_or_cancelled": sum(1 for v in flag.values() if v), "xc_cycles": xc_flag,
        "base_rate_all_results": dict(base), "base_rate_by_round": {k: {str(r): c for r, c in sorted(v.items())} for k, v in base_by_round.items()},
        "cycle_totals_from_log": dict(tot), "derived": {"SUB": base["SUB"], "R2": base["R2"], "R3": base["R3"]},
        "k2_neighbour_class": dict(nbr_class["K2"]), "k2_unsubtracted": k2_unsub,
        "k2_by_round": {"%s@%s" % k: c for k, c in sorted(k2_round.items(), key=lambda kv: (kv[0][0], str(kv[0][1])))},
        "all_classes_neighbour": {k: dict(v) for k, v in nbr_class.items()},
    }
    return out


def main():
    out = {s: run_slice(s) for s in SLICES}
    with open(os.path.join(SC, "lc-base", "r1r4_split.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
