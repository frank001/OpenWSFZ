#!/usr/bin/env python3
"""FD-PROXY pilot (spec s7): the night's first 283 cycles; P (confirmed batch 4+5, judgeable) and the N-FIELD synthetic set ONLY.
Q (unconfirmed) rows are NEVER passed to the instrument here: `assert r['m'] == 1` guards every judge() call. Q enters only as STRUCTURE
(stratum counts for the s weights: SNR band x buried), which reads no instrument output.
N-RAND needs the product's unpacker and plausibility filter (a harness, a separate step): not in this file.
HK-037: text stays in memory; the output JSON is counts and rates only.

  python -I fd_pilot.py <nc.tsv> <ALL.TXT> <out.json>
"""
from __future__ import annotations

import collections
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fd_lib as L

SEED = 20261118
PILOT_CYCLES = 283
N_PER_FIELD = 1000           # spec s4.2 (1,000 per field); pilot draws with replacement from the pilot's P rows
DF_SPREAD_HZ = 50.0          # spec s4.2 (TA-CHECK burial neighbourhood)
BATCHES = (4, 5)
assert (SEED, PILOT_CYCLES, N_PER_FIELD, DF_SPREAD_HZ) == (20261118, 283, 1000, 50.0)
STEP_TOKENS = ("grid", "report", "rreport", "RRR", "RR73", "73")
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def load_nc(path):
    rows = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            p = ln.rstrip("\n").split("\t")
            if len(p) < 11:
                continue
            rows.append(dict(st=p[0], k=int(p[1]), m=int(p[2]), f=int(p[3]), snr=int(p[5]), tx=p[10].strip(), ap=int(p[11]) if len(p) > 11 else None))
    return rows


def rand_call(rng):
    """A random call-shaped value (the spec's literal 'random valid value'): 1-2 prefix chars, a digit, 1-3 suffix letters."""
    pre = "".join(rng.choice(LETTERS) for _ in range(rng.choice((1, 2))))
    return pre + str(rng.randrange(10)) + "".join(rng.choice(LETTERS) for _ in range(rng.choice((1, 2, 3))))


def rand_payload(rng, avoid):
    while True:
        k = rng.choice(STEP_TOKENS)
        if k == "grid":
            v = rng.choice("ABCDEFGHIJKLMNOPQR") + rng.choice("ABCDEFGHIJKLMNOPQR") + str(rng.randrange(10)) + str(rng.randrange(10))
        elif k == "report":
            v = "%+03d" % rng.randrange(-30, 32)
        elif k == "rreport":
            v = "R%+03d" % rng.randrange(-30, 32)
        else:
            v = k
        if v != avoid:
            return v


def render(pr, text, field, rng, e_calls):
    """Replace ONE field of the P row's text; -> new text or None when the row has no such field."""
    t = text.split()
    if pr["kind"] == "CQ":
        if field == "A":
            return None
        if field == "B":
            i = t.index(pr["B"]); t[i] = rand_call(rng) if e_calls is None else rng.choice(e_calls)
            return " ".join(t) if t[i] != pr["B"] else None
        if field == "X":
            if pr["X"] is None:
                return None
            t[-1] = rand_payload(rng, t[-1])
            return " ".join(t)
    else:
        if field == "A":
            t[0] = rand_call(rng) if e_calls is None else rng.choice(e_calls)
            return " ".join(t) if t[0] != pr["A"] else None
        if field == "B":
            t[1] = rand_call(rng) if e_calls is None else rng.choice(e_calls)
            return " ".join(t) if t[1] != pr["B"] else None
        if field == "X":
            if pr["X"] is None:
                return None
            t[2] = rand_payload(rng, t[2])
            return " ".join(t)
    return None


def main(nc_path, all_path, out_path):
    t0 = time.time()
    rows = load_nc(nc_path)
    E = L.Evidence(L.load_E(all_path))
    stamps = sorted({r["st"] for r in rows})
    pil = set(stamps[:PILOT_CYCLES])
    t_load = time.time() - t0
    res = {"pilot_cycles": len(pil), "E_rows": E.n}

    # unjudgeable share by batch (all unconfirmed + confirmed rows, structural: a parse, not an instrument output)
    unj = {}
    for k in range(1, 7):
        R = [r for r in rows if r["k"] == k]
        nj = sum(1 for r in R if L.parse(r["tx"]) is None)
        unj[str(k)] = dict(n=len(R), unjudgeable=nj, share=round(nj / len(R), 4) if R else None)
    uq = [r for r in rows if r["k"] in BATCHES and not r["m"]]
    res["unjudgeable_by_batch_all_rows"] = unj
    res["Q_whole_night_unconfirmed_b45"] = dict(n=len(uq), unjudgeable=sum(1 for r in uq if L.parse(r["tx"]) is None))

    # Q stratum STRUCTURE (counts only; no judge() call on a Q row)
    qj = [r for r in uq if L.parse(r["tx"]) is not None]
    qstr = collections.Counter()
    for r in qj:
        qstr[(L.band(r["snr"]), "buried" if E.buried(L.cycle_of(r["st"]), r["f"], r["snr"]) else "isolated")] += 1
    wsum = sum(qstr.values())
    W = {k: v / wsum for k, v in qstr.items()}
    res["Q_strata_counts_whole_night"] = {f"{a}|{b}": v for (a, b), v in sorted(qstr.items())}

    # P in the pilot cycles
    P = []
    for r in rows:
        if r["k"] in BATCHES and r["m"] == 1 and r["st"] in pil:
            assert r["m"] == 1
            pr = L.parse(r["tx"])
            if pr is None:
                continue
            cyc = L.cycle_of(r["st"])
            j = E.judge(cyc, r["f"], r["tx"])
            bur = E.buried(cyc, r["f"], r["snr"], text=r["tx"], confirmed=True)
            bur_sh = E.buried(cyc, r["f"], r["snr"], text=r["tx"], confirmed=True, snr_shift=3.2)
            P.append(dict(r=r, pr=pr, cyc=cyc, j=j, stratum=(L.band(r["snr"]), "buried" if bur else "isolated"), bur_shift=bur_sh,
                          r15=E.R(cyc, pr, window=60), r60=E.R(cyc, pr, window=240)))
    res["P_pilot_n"] = len(P)
    res["P_strata_counts"] = {f"{a}|{b}": v for (a, b), v in sorted(collections.Counter(p["stratum"] for p in P).items())}

    def rates(items, key=lambda p: p["j"]):
        n = len(items)
        if not n:
            return None
        j = [key(p) for p in items]
        return dict(n=n, plausible=round(sum(x["plausible"] for x in j) / n, 4), C=round(sum(x["C"] for x in j) / n, 4),
                    R_fail=round(sum(not x["R"] for x in j) / n, 4), F_fail=round(sum(x["F"] == "FAIL" for x in j) / n, 4),
                    F_unseen=round(sum(x["F"] == "UNSEEN" for x in j) / n, 4), S_behind=round(sum(x["S"] for x in j) / n, 4))

    def weighted(items, key, strata_w):
        """weighted PLAUSIBLE share, weights = Q's stratum shares; a stratum with no P rows is reported, its weight dropped and the rest renormalised."""
        by = collections.defaultdict(list)
        for p in items:
            by[p["stratum"]].append(key(p)["plausible"])
        num = den = 0.0
        missing = []
        for st, w in strata_w.items():
            if st in by and by[st]:
                num += w * (sum(by[st]) / len(by[st])); den += w
            else:
                missing.append(f"{st[0]}|{st[1]}")
        return (num / den if den else None), missing

    res["P_components_all"] = rates(P)
    s_w, miss = weighted(P, lambda p: p["j"], W)
    res["s_weighted_to_Q_strata"] = None if s_w is None else round(s_w, 4)
    res["s_weight_strata_missing_in_P"] = miss
    res["P_by_stratum"] = {f"{a}|{b}": rates([p for p in P if p["stratum"] == (a, b)]) for (a, b) in sorted({p["stratum"] for p in P})}
    iso = [p for p in P if p["stratum"][1] == "isolated"]
    bur = [p for p in P if p["stratum"][1] == "buried"]
    res["P_iso_vs_buried_plausible"] = dict(isolated=rates(iso)["plausible"] if iso else None, buried=rates(bur)["plausible"] if bur else None,
                                            diff=round(rates(iso)["plausible"] - rates(bur)["plausible"], 4) if iso and bur else None)
    res["P_R_at_15min_vs_60min_pass"] = dict(r15=round(sum(p["r15"] for p in P) / len(P), 4), r60=round(sum(p["r60"] for p in P) / len(P), 4))
    # F's moved-sender rate: among rows with a nearest e, the share beyond 10 Hz
    seen = [p for p in P if p["j"]["F"] != "UNSEEN"]
    res["P_F_moved_sender_rate"] = dict(n_seen=len(seen), moved=round(sum(p["j"]["F"] == "FAIL" for p in seen) / len(seen), 4) if seen else None)
    res["P_buried_share_literal_vs_plus3p2dB"] = dict(literal=round(sum(p["stratum"][1] == "buried" for p in P) / len(P), 4), shifted=round(sum(p["bur_shift"] for p in P) / len(P), 4))

    # N-FIELD (ghost mode): a P row, ONE field replaced, at its frequency + df; same cycle; E unchanged (the real station stays in E)
    e_calls = sorted({c for c in E.call_cycles})
    out_f = {}
    for variant, calls, hide_src in (("randcall", None, False), ("Ecall", e_calls, False), ("randcall_MISS", None, True), ("Ecall_MISS", e_calls, True)):
        rng = random.Random(SEED)     # each variant draws the same sequence of seeds-from-SEED
        per = {}
        for field in ("B", "A", "X"):
            pool = [p for p in P if render(p["pr"], p["r"]["tx"], field, random.Random(0), calls) is not None]
            made = []
            tries = 0
            while len(made) < N_PER_FIELD and pool and tries < N_PER_FIELD * 20:
                tries += 1
                p = rng.choice(pool)
                t = render(p["pr"], p["r"]["tx"], field, rng, calls)
                if t is None:
                    continue
                df = rng.uniform(-DF_SPREAD_HZ, DF_SPREAD_HZ)
                j = E.judge(p["cyc"], p["r"]["f"] + df, t, hide=((p["r"]["tx"], p["r"]["f"]) if hide_src else None))
                made.append((j, abs(df) <= L.GATE_HZ))
            judged = [j for (j, _) in made if j is not None]
            n = len(judged)
            blind = [j for (j, near) in made if j is not None and near]
            per[field] = dict(drawn=len(made), unjudgeable=len(made) - n, n=n,
                              f=round(sum(j["plausible"] for j in judged) / n, 4) if n else None,
                              C=round(sum(j["C"] for j in judged) / n, 4) if n else None,
                              R_fail=round(sum(not j["R"] for j in judged) / n, 4) if n else None,
                              F_fail=round(sum(j["F"] == "FAIL" for j in judged) / n, 4) if n else None,
                              S_behind=round(sum(j["S"] for j in judged) / n, 4) if n else None,
                              within10Hz_n=len(blind), within10Hz_f=round(sum(j["plausible"] for j in blind) / len(blind), 4) if blind else None)
        allj = [per[f] for f in per if per[f]["n"]]
        per["f_FIELD_equal_shares"] = round(sum(x["f"] for x in allj) / len(allj), 4) if allj else None
        out_f[variant] = per
    res["N_FIELD"] = out_f
    res["run_seconds"] = dict(load=round(t_load, 1), total=round(time.time() - t0, 1))
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:4])
