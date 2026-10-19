#!/usr/bin/env python3
"""#225 phase 2 (type 0.1 DXpedition decode): QA's replay analysis. AGGREGATES ONLY (HK-037 / NFR-021): the per-message working
file written by Replay81 --dxped-dump lives in D:\\Projects\\claude\\_qa-scratch\\ (outside git) and is read here by code only; nothing in
this script prints, returns or saves a callsign or message text. Delete the scratch folder at job close.

Rows (fixed before any data was read; spec dev-tasks/2026-10-19-dxpedition-fox-hound-decode-225.md section 6 + the Architect's review):
  V1   every NON-0.1 decode is identical between OLD (main 5229beec) and NEW (87beed94) in its OUTCOME FIELDS (stamp, batch, freq, dt, snr);
       cycles abandoned in any pass in either arm are excluded pairwise and counted. (A hashed <...> token cannot change an outcome field.)
  V2   each NEW 0.1 decode is matched to a WSJT-X type-0.1 row of the SAME cycle (tokens 0, 2 and the report equal, token 3 compatible, frequency
       within 4 Hz); the count of NEW 0.1 decodes with no WSJT-X match (OWS-only) is reported.
  V2b  for each matched decode, token 3 (the Fox) against WSJT-X: same call / OWS <...> with WSJT-X a call / OWS a call with WSJT-X <...> /
       different calls. ANY "different calls" => STOP and report to the Architect.
  V2c  the report of every decode that matches on tokens 0, 2, 3 must equal WSJT-X's. Any mismatch => STOP (a formula error).
  M1   the share of WSJT-X's type-0.1 rows in the replayed cycles that NEW matched, by WSJT-X SNR band (descriptive, no bar; Wilson 95 % CI).
  M2   expected false 0.1 rows = (cell (i3 0, n3 7) of the native unsupported-type counter) x (acceptance share of the plausibility rule on
       random payloads, 0.71822, Developer's N = 100,000 seed 20261019). The counter is per decode ATTEMPT (a payload seen again in a later pass
       counts again), so M2 is an UPPER bound on distinct false rows. STOP if V2's OWS-only count > 3 x M2 and > 5 (the Architect's judgement).
Usage: python dxped_analyse.py <quick-dir> <wsjtx ALL.TXT> <selection.json>
"""
import csv, json, math, os, sys
from collections import Counter, defaultdict

ACCEPT = 0.71822


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def load_outcomes(path):
    d = defaultdict(list)
    with open(path, encoding="utf-8") as fh:
        for row in csv.reader(fh):
            if len(row) >= 6:
                d[row[0]].append((row[1], row[3], row[4], row[5]))   # kind, freq, dt, snr
    return d


def load_abandon(path):
    s = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            rd = csv.reader(fh)
            next(rd, None)
            for row in rd:
                # columns: stamp,ran,abandoned,contained -- a cycle is excluded when ANY pass was abandoned or contained an exception
                if len(row) >= 4 and (row[2] not in ("0", "") or row[3] not in ("0", "")):
                    s.add(row[0])
    return s


def load_dxped(path):
    rows = []
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            p = line.rstrip("\n").split("\t")
            if len(p) == 6:
                rows.append({"stamp": p[0], "kind": p[1], "freq_s": p[2], "freq": float(p[2]), "dt": p[3], "snr": p[4], "tok": p[5].split(" ")})
    return rows


def load_wsjtx_01(path, stamps):
    d = defaultdict(list)
    for line in open(path, encoding="utf-8", errors="replace"):
        parts = line.split()
        if len(parts) < 12 or parts[0] not in stamps:
            continue
        m = parts[7:]
        if len(m) == 5 and m[1] == "RR73;":
            d[parts[0]].append({"snr": int(parts[4]), "freq": float(parts[6]), "tok": m, "matched": False})
    return d


def band(snr):
    return ">0" if snr > 0 else "-10..0" if snr > -10 else "-20..-10" if snr > -20 else "<=-20"


def main():
    qd, wsp, selp = sys.argv[1:4]
    stamps = set(json.load(open(selp))["runs"]["20261009_1752"]["Y40"])
    old, new = load_outcomes(os.path.join(qd, "outcomes_OLD.csv")), load_outcomes(os.path.join(qd, "outcomes_NEW.csv"))
    ab = load_abandon(os.path.join(qd, "abandon_OLD.csv")) | load_abandon(os.path.join(qd, "abandon_NEW.csv"))
    dx = load_dxped(os.path.join(qd, "dxped_NEW.tsv"))
    out = {"cycles_in_selection": len(stamps), "cycles_old": len(old), "cycles_new": len(new), "abandoned_cycles_excluded": len(ab & stamps)}

    # ---- V1: NEW minus its 0.1 decodes == OLD, per cycle, by outcome fields
    dx_keys = Counter((r["stamp"], r["kind"], r["freq_s"], r["dt"], r["snr"]) for r in dx)
    differing, compared = 0, 0
    for st in sorted(stamps - ab):
        o = Counter(old.get(st, []))
        n = Counter(new.get(st, []))
        for (s, k, f, dt, snr), c in dx_keys.items():
            if s == st:
                n[(k, f, dt, snr)] -= c
        n = +n
        compared += 1
        if o != n:
            differing += 1
    out["V1"] = {"cycles_compared": compared, "cycles_differing": differing, "result": "PASS" if differing == 0 else "FAIL"}

    # ---- WSJT-X type-0.1 rows in the replayed cycles
    ws = load_wsjtx_01(wsp, stamps)
    n_ws = sum(len(v) for v in ws.values())
    out["wsjtx_type01_rows_in_replayed_cycles"] = n_ws
    out["new_type01_decodes"] = len(dx)
    classes = Counter(); report_mismatch = 0; matched_new = 0; ows_only = 0
    for r in dx:
        cand = [w for w in ws.get(r["stamp"], []) if abs(w["freq"] - r["freq"]) <= 4.0]
        hit = None
        for w in cand:
            t, u = r["tok"], w["tok"]
            if t[0] == u[0] and t[2] == u[2]:
                a, b = t[3], u[3]
                if a == b or a == "<...>" or b == "<...>":
                    hit = w
                    break
        if hit is None:
            # same hounds but a different Fox call is the dangerous case: look for it explicitly
            for w in cand:
                if r["tok"][0] == w["tok"][0] and r["tok"][2] == w["tok"][2]:
                    hit = ("different", w)
                    break
        if hit is None:
            ows_only += 1
            continue
        if isinstance(hit, tuple):
            classes["different calls"] += 1
            continue
        matched_new += 1
        hit["matched"] = True
        a, b = r["tok"][3], hit["tok"][3]
        classes["same call" if a == b and a != "<...>" else "both <...>" if a == b else "OWS <...>, WSJT-X a call" if a == "<...>" else "OWS a call, WSJT-X <...>"] += 1
        if r["tok"][4] != hit["tok"][4]:
            report_mismatch += 1
    out["V2"] = {"new_type01_decodes": len(dx), "matched_to_wsjtx": matched_new, "ows_only": ows_only}
    out["V2b_call3_classes"] = dict(classes)
    out["V2b_stop"] = classes["different calls"] > 0
    out["V2c_report_mismatches"] = report_mismatch
    out["V2c_stop"] = report_mismatch > 0

    # ---- M1 by SNR band
    by = defaultdict(lambda: [0, 0])
    for v in ws.values():
        for w in v:
            by[band(w["snr"])][1] += 1
            by[band(w["snr"])][0] += 1 if w["matched"] else 0
    tot_k = sum(k for k, _ in by.values()); tot_n = sum(n for _, n in by.values())
    out["M1"] = {"overall": {"matched": tot_k, "of": tot_n, "share": round(tot_k / tot_n, 4) if tot_n else None, "wilson95": [round(x, 4) for x in wilson(tot_k, tot_n)]},
                 "by_snr_band": {b: {"matched": k, "of": n} for b, (k, n) in sorted(by.items())}}

    # ---- M2
    up = os.path.join(qd, "run_NEW.unsupported.json")
    if os.path.exists(up):
        u = json.load(open(up))
        c7 = u["i0n3_7"]
        m2 = c7 * ACCEPT
        out["M2"] = {"unsupported_total_attempts": u["total"], "cell_i0n3_7_attempts": c7, "acceptance_share": ACCEPT,
                     "expected_false_type01_rows_upper_bound": round(m2, 2),
                     "ows_only_over_m2": (round(ows_only / m2, 2) if m2 > 0 else None),
                     "stop_ows_only_gt_3xM2_and_gt_5": bool(ows_only > 3 * m2 and ows_only > 5)}
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
