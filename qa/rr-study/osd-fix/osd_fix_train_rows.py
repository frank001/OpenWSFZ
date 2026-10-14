#!/usr/bin/env python
"""OSD-FIX TRAIN interim statistics (amendment 2026-10-08-1745 as REVISED, arch/osd-fix 5e771634): reported after every completed round, cumulative over the rounds so far.

For every FIX arm vs REF, on the cycles of the completed rounds (each arm x chunk is paired by cycle stamp):
  NET(n)  = 100 * sum(M_fix - M_ref) / sum(W)           Test B confirmed decodes, pp of WSJT-X's decodes     (spec 5.2)
  dU(n)   = mean over cycles of (not-confirmed_fix - not-confirmed_ref)    not-confirmed = decodes - confirmed, batch 1 + batch 2
  both with a 95 % non-overlapping BLOCK bootstrap, blocks of 40 consecutive cycles in TRAIN order (one block if fewer than 40), B 10,000, seed 20261007 (spec 5.3);
  NET and dU by batch; and the n* the rule WOULD pick, labelled INTERIM: among the grid {24, 30, 40, 50, 60} with dU point estimate <= 0, the largest NET point estimate,
  ties to the lower n; none => FIX-NO-GATE. FIX(0) is descriptive, outside the rule; if its NET exceeds the would-be n*'s it is reported beside it (B1).
  The rule needs >= 4 completed rounds; with fewer the interim line says "no n* (fewer than 4 rounds)".
Everything is marked "interim, k of 7 rounds" and is NOT CITABLE. Nothing about TEST is touched. Numeric only (HK-037): Test B files hold counts, no text.

  python qa/rr-study/osd-fix/osd_fix_train_rows.py            # all rounds with seven valid arms
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "sub-feas"))
sys.path.insert(0, os.path.join(HERE, "..", "nhard-rep"))
import onoff_replay_rows as O  # noqa: E402
import osd_fix_train as T      # noqa: E402

BLOCK, B_RES, SEED = 40, 10_000, 20261007
GRID = (24, 30, 40, 50, 60)
MIN_ROUNDS = 4
RESULTS = T.RESULTS
CHUNKS = os.path.join(T.CHUNK_DIR, "chunks_manifest.json")


def completed_rounds():
    done = []
    for r in range(1, T.N_ROUNDS + 1):
        if all(os.path.exists(os.path.join(T.OUT, f"r{r}", a[0], "process_ok.json")) for a in T.ARMS):
            done.append(r)
        else:
            break
    return done


def load_arm(rounds, name):
    """-> ordered list of per-cycle dicts {stamp, W, M, n1, c1, n2, c2} across the rounds, in TRAIN order. Test B counts only."""
    rows = []
    for r in rounds:
        cyc = O.load_testb(os.path.join(T.OUT, f"r{r}", name, "testb.csv"))
        chunk = json.load(open(os.path.join(T.CHUNK_DIR, f"chunk_{r}.json")))
        for s in chunk["runs"][chunk["run"]]["A"]:
            d = cyc[s]
            rows.append({"stamp": s, "W": d["W"], "M": d["M"], "n1": sum(v[0] for v in d["b1"].values()), "c1": sum(v[1] for v in d["b1"].values()),
                         "n2": sum(v[0] for v in d["b2"].values()), "c2": sum(v[1] for v in d["b2"].values())})
    return rows


def boot(num_by_cycle, den_by_cycle=None, block=BLOCK, B=B_RES, seed=SEED):
    """95 % non-overlapping block bootstrap of a sum/ratio. den None => mean per cycle (denominator = cycle count)."""
    num = np.asarray(num_by_cycle, dtype=float)
    den = np.ones(len(num)) if den_by_cycle is None else np.asarray(den_by_cycle, dtype=float)
    edges = list(range(0, len(num), block))
    bn = np.array([num[i:i + block].sum() for i in edges])
    bd = np.array([den[i:i + block].sum() for i in edges])
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(edges), size=(B, len(edges)))
    ratio = bn[idx].sum(axis=1) / bd[idx].sum(axis=1)
    lo, hi = np.percentile(ratio, [2.5, 97.5])
    return float(lo), float(hi), len(edges)


def compare(ref, fix):
    W = [a["W"] for a in ref]
    assert W == [b["W"] for b in fix], "WSJT-X W differs between arms"
    assert [a["stamp"] for a in ref] == [b["stamp"] for b in fix]
    out = {}
    def stat(label, d_by_cycle, scale, den):
        point = scale * float(np.sum(d_by_cycle)) / float(np.sum(den))
        lo, hi, nb = boot(d_by_cycle, den if scale == 100.0 else None)
        out[label] = {"point": point, "ci": [scale * lo if scale == 100.0 else lo, scale * hi if scale == 100.0 else hi], "blocks": nb}
    dM = [b["M"] - a["M"] for a, b in zip(ref, fix)]
    dM1 = [b["c1"] - a["c1"] for a, b in zip(ref, fix)]
    dM2 = [b["c2"] - a["c2"] for a, b in zip(ref, fix)]
    stat("NET", dM, 100.0, W)
    stat("NET_b1", dM1, 100.0, W)
    stat("NET_b2", dM2, 100.0, W)
    nc = lambda x: (x["n1"] - x["c1"]) + (x["n2"] - x["c2"])
    stat("dU", [nc(b) - nc(a) for a, b in zip(ref, fix)], 1.0, np.ones(len(W)))
    stat("dU_b1", [(b["n1"] - b["c1"]) - (a["n1"] - a["c1"]) for a, b in zip(ref, fix)], 1.0, np.ones(len(W)))
    stat("dU_b2", [(b["n2"] - b["c2"]) - (a["n2"] - a["c2"]) for a, b in zip(ref, fix)], 1.0, np.ones(len(W)))
    out["K"] = None
    return out


def would_pick(res, k):
    if k < MIN_ROUNDS:
        return {"n_star": None, "note": f"no n* (fewer than {MIN_ROUNDS} rounds)"}
    cand = [(res[f"FIX{n}"]["NET"]["point"], -n, n) for n in GRID if res[f"FIX{n}"]["dU"]["point"] <= 0]
    if not cand:
        return {"n_star": None, "note": "FIX-NO-GATE (no grid value has dU <= 0)"}
    best = max(cand)
    n = best[2]
    out = {"n_star": n, "NET": res[f"FIX{n}"]["NET"]["point"], "edge": "lower edge 24" if n == 24 else "upper edge 60 (Architect rules before TEST)" if n == 60 else None}
    if res["FIX0"]["NET"]["point"] > res[f"FIX{n}"]["NET"]["point"]:
        out["B1_fix0_net_exceeds_nstar"] = {"FIX0": res["FIX0"]["NET"]["point"], f"FIX{n}": res[f"FIX{n}"]["NET"]["point"]}
    return out


def main():
    rounds = completed_rounds()
    if not rounds:
        print("no completed round")
        return 1
    k = len(rounds)
    arms = {a[0]: load_arm(rounds, a[0]) for a in T.ARMS}
    res = {"label": f"INTERIM, {k} of 7 rounds. NOT CITABLE.", "rounds": rounds, "cycles": len(arms["REF"]), "seed": SEED, "block": BLOCK}
    for name, _s, _n in T.ARMS[1:]:
        res[name] = compare(arms["REF"], arms[name])
    res["interim_n_star_rule"] = would_pick(res, k)
    st = json.load(open(os.path.join(T.OUT, "status.json")))
    wall = {a[0]: [] for a in T.ARMS}
    ab = {a[0]: [0, 0] for a in T.ARMS}
    for r in rounds:
        for name, rec in st["rounds"][str(r)]["arms"].items():
            wall[name].append(rec["wall_s"])
            ab[name][0] += rec.get("abandoned", 0)
            ab[name][1] += rec.get("cycles", 0)
    res["validity_and_wall"] = {n: {"wall_s_median": float(np.median(w)), "wall_s_all": w, "abandoned_cycles": ab[n][0], "cycles": ab[n][1],
                                    "abandon_share": ab[n][0] / ab[n][1] if ab[n][1] else None, "V6_ok": (ab[n][0] / ab[n][1] <= T.V6_MAX_ABANDON) if ab[n][1] else None}
                                for n, w in wall.items()}
    p = os.path.join(RESULTS, f"train_interim_round{k}.json")
    json.dump(res, open(p, "w"), indent=1, sort_keys=True)
    print(json.dumps(res, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
