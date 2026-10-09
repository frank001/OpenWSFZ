#!/usr/bin/env python3
"""DENSITY-SUB rows: does the subtraction pass remedy the near-neighbour density cost? (analysis of the replay, nothing else)

Pre-registration: qa/rr-study/2026-10-09-1500-qa-density-sub-preregistration.md (Architect's spec with Amendment 1).
Run data: artefacts/rr_2026-10-09_density_sub/{matched_OFF,matched_ON,abandon_OFF,abandon_ON}.csv (numeric indices, no text).

Stages (the pre-registration requires D_off to be reported to the Architect BEFORE the verdict row is read):
  python density_sub_rows.py offpoint   validity rows for the OFF arm and the OFF point estimate D_off. NO verdict, no ON-arm D.
  python density_sub_rows.py full       everything, including the ON-arm verdict row.

HK-037 / NFR-021: the WSJT-X ALL.TXT is read in load_w(), which keeps SNR and frequency only; the message text is never stored.
The classifier, the 1 dB cells and the direct standardisation are DENSITY-LIVE's (qa/rr-study/density-live/density_live.py), imported
verbatim; the count-array form below is tested against that module's own compute_D.
"""
import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "qa", "rr-study", "density-live"))
sys.path.insert(0, os.path.join(REPO, "qa", "rr-study", "live-gap-now"))
import density_live as dl   # noqa: E402  (classify, cell_index, N_CELLS, MIN_CELL_N, BAR_PRIMARY, BAR_0A, MAX_DROP_FRAC)

RUN = "20260930_1930"
BAR_PRIMARY = 0.170          # DENSITY-LIVE spec section 3 (1.0 pp attributable cost), carried over from the 2026-09-18 live corpus
BAR_0A = dl.BAR_0A           # 0.05
MAX_DROP_FRAC = dl.MAX_DROP_FRAC   # 0.05
MIN_CELL_N = dl.MIN_CELL_N   # 20
MIN_EXPOSED = 200            # V3, Architect's Amendment 1
MAX_EXCEPT_FRAC = 0.05       # V1, Architect's Amendment 1
POP_SNR_MIN = -10            # DENSITY-LIVE population: snr >= -10
BLOCK = 4
N_BOOT = 10000
SEED = 20261009
CLASSES = ("EXPOSED", "GAP", "PL", "PL_TRANS_STRONG", "TRANSITION", "PF", "CLEAR")


# ---------------------------------------------------------------- loading (numeric only)
def load_w(alltxt_path, stamps):
    """{stamp: [(snr, freq_hz), ...]} in ALL.TXT order: the SAME line convention and index as the harness's LoadWsjtx
    (fields: stamp, mhz, Rx, FT8, snr, dt, freq, message...). The message text is discarded here."""
    want = set(stamps)
    out = {s: [] for s in stamps}
    with open(alltxt_path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            f = line.split()
            if len(f) < 8 or f[2] != "Rx" or f[3] != "FT8" or f[0] not in want:
                continue
            try:
                snr, freq = int(f[4]), int(f[6])
            except ValueError:
                continue
            out[f[0]].append((snr, freq))
    return out


def load_matched(path):
    """{stamp: set(line index)} from the harness's --matched-out file (stamp,idx;idx;...)."""
    m = {}
    with open(path, encoding="utf-8") as fh:
        rd = csv.reader(fh)
        next(rd)
        for row in rd:
            m[row[0]] = {int(x) for x in row[1].split(";") if x != ""} if len(row) > 1 else set()
    return m


def load_abandon(path):
    """{stamp: abandoned flag} (the harness's --abandon-out: stamp,ran,abandoned,contained)."""
    a = {}
    with open(path, encoding="utf-8") as fh:
        rd = csv.reader(fh)
        next(rd)
        for row in rd:
            a[row[0]] = int(row[2])
    return a


def load_per_cycle(path):
    """{stamp: (M_off, M_on)} of the 2026-10-01 run."""
    d = {}
    with open(path, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            d[row["stamp"]] = (int(row["M_off"]), int(row["M_on"]))
    return d


# ---------------------------------------------------------------- strata (from W only)
def classify_cycle(w_rows):
    """[(idx, snr, freq, class)] for the population rows (snr >= -10) of one cycle. Neighbours are every OTHER row of the
    cycle by INDEX (the full W list, as in DENSITY-LIVE), so a duplicated (snr, freq) pair cannot hide a neighbour."""
    out = []
    for i, (snr, f) in enumerate(w_rows):
        if snr < POP_SNR_MIN:
            continue
        nb = [(s, nf) for j, (s, nf) in enumerate(w_rows) if j != i]
        out.append((i, snr, f, dl.classify(snr, f, nb)))
    return out


def build_cycles(w_by_stamp, stamps):
    """Per cycle (in sample order): list of (idx, snr, freq, class)."""
    return [classify_cycle(w_by_stamp[s]) for s in stamps]


# ---------------------------------------------------------------- count arrays and D
def cycle_counts(cyc_rows, matched_idx):
    """{class: (n[21], h[21])} for one cycle under one arm's matched set."""
    c = {k: (np.zeros(dl.N_CELLS, dtype=np.int64), np.zeros(dl.N_CELLS, dtype=np.int64)) for k in CLASSES}
    for idx, snr, f, cls in cyc_rows:
        ci = dl.cell_index(snr)
        c[cls][0][ci] += 1
        c[cls][1][ci] += 1 if idx in matched_idx else 0
    return c


def D_from_counts(n_a, h_a, n_b, h_b):
    """DENSITY-LIVE section 3, on count arrays: direct standardisation to A's retained-cell SNR mix.
    Returns (D, dropped_a, total_a, dropped_b, total_b)."""
    keep = (n_a >= MIN_CELL_N) & (n_b >= MIN_CELL_N)
    tot_a, drop_a = int(n_a.sum()), int(n_a[~keep].sum())
    tot_b, drop_b = int(n_b.sum()), int(n_b[~keep].sum())
    if not keep.any() or n_a[keep].sum() == 0:
        return float("nan"), drop_a, tot_a, drop_b, tot_b
    w = n_a[keep].astype(float)
    w = w / w.sum()
    miss_a = 1.0 - h_a[keep] / np.maximum(n_a[keep], 1)
    miss_b = 1.0 - h_b[keep] / np.maximum(n_b[keep], 1)
    return float(np.sum(w * (miss_a - miss_b))), drop_a, tot_a, drop_b, tot_b


def stack(per_cycle_counts):
    """{class: (N[ncyc,21], H[ncyc,21])}"""
    return {k: (np.stack([c[k][0] for c in per_cycle_counts]), np.stack([c[k][1] for c in per_cycle_counts]))
            for k in CLASSES}


def block_ids(ncyc, block=BLOCK):
    return np.arange(ncyc) // block


def block_sums(S, ncyc, block=BLOCK):
    """Collapse the cycle axis into non-overlapping blocks of `block` consecutive SAMPLED cycles (last block may be short)."""
    b = block_ids(ncyc, block)
    nb = int(b.max()) + 1
    out = {}
    for k, (N, H) in S.items():
        Nb = np.zeros((nb, dl.N_CELLS), dtype=np.int64)
        Hb = np.zeros((nb, dl.N_CELLS), dtype=np.int64)
        np.add.at(Nb, b, N)
        np.add.at(Hb, b, H)
        out[k] = (Nb, Hb)
    return out


def total(S, k):
    return S[k][0].sum(axis=0), S[k][1].sum(axis=0)


def D_pair(S, a, b):
    na, ha = total(S, a)
    nb, hb = total(S, b)
    return D_from_counts(na, ha, nb, hb)


def bootstrap(B_off, B_on, pairs, n_boot=N_BOOT, seed=SEED):
    """Paired block bootstrap: one block resample per draw serves both arms and every contrast.
    pairs: [(arm, a, b)] with arm in {'off','on'}. Returns ({(arm,a,b): draws}, draws of D_on(EXPOSED,PL)-D_off(EXPOSED,PL))."""
    nb = next(iter(B_off.values()))[0].shape[0]
    rng = np.random.default_rng(seed)
    out = {p: np.empty(n_boot) for p in pairs}
    dd = np.empty(n_boot)
    arms = {"off": B_off, "on": B_on}
    for d in range(n_boot):
        pick = rng.integers(0, nb, size=nb)
        tot = {arm: {k: (S[k][0][pick].sum(axis=0), S[k][1][pick].sum(axis=0)) for k in S} for arm, S in arms.items()}
        for (arm, a, b) in pairs:
            t = tot[arm]
            out[(arm, a, b)][d] = D_from_counts(*t[a], *t[b])[0]
        t0, t1 = tot["off"], tot["on"]
        dd[d] = D_from_counts(*t1["EXPOSED"], *t1["PL"])[0] - D_from_counts(*t0["EXPOSED"], *t0["PL"])[0]
    return out, dd


def ci95(x):
    x = x[~np.isnan(x)]
    if len(x) == 0:
        return float("nan"), float("nan")
    return float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5))


# ---------------------------------------------------------------- validity rows (pure functions, exercised both ways in tests)
def row_v1(stamps, matched, per_cycle, arm, ab_new, ab_old):
    """Re-run matched count per cycle equals the 10-01 per_cycle.csv value (M_off for OFF, M_on for ON).
    An exception is allowed only when the ON arm's abandonment flag differs between the two runs (explained in exactly one);
    exceptions <= 5% of sampled cycles, unexplained = 0. Returns dict with 'pass'."""
    col = 0 if arm == "off" else 1
    unexplained, explained = [], []
    for s in stamps:
        got = len(matched.get(s, ()))
        if got == per_cycle[s][col]:
            continue
        if arm == "on" and ab_new is not None and ab_old is not None and (ab_new.get(s, 0) != ab_old.get(s, 0)):
            explained.append(s)
        else:
            unexplained.append(s)
    frac = len(explained) / len(stamps)
    return {"explained": len(explained), "unexplained": len(unexplained), "explained_frac": frac,
            "pass": (not unexplained) and frac <= MAX_EXCEPT_FRAC, "unexplained_stamps": unexplained[:10]}


def row_v2(cycles):
    """Every population row is in exactly one class: the per-class counts sum to the number of classified rows, and every class is known."""
    n = sum(len(c) for c in cycles)
    by = {k: 0 for k in CLASSES}
    for c in cycles:
        for (_, _, _, cls) in c:
            by[cls] += 1            # KeyError = unknown class = fail loudly
    return {"n_pop": n, "by_class": by, "pass": sum(by.values()) == n}


def row_v3(cycles, minimum=MIN_EXPOSED):
    n = sum(1 for c in cycles for (_, _, _, cls) in c if cls == "EXPOSED")
    return {"n_exposed": n, "min": minimum, "pass": n >= minimum}


def row_0a(lo, hi):
    return {"ci95": [lo, hi], "bar": BAR_0A, "pass": bool(lo >= -BAR_0A and hi <= BAR_0A)}


def row_0b(drop_exp, n_exp, drop_pl, n_pl):
    fe = drop_exp / n_exp if n_exp else float("nan")
    fp = drop_pl / n_pl if n_pl else float("nan")
    return {"EXPOSED_dropped": drop_exp, "EXPOSED_total": n_exp, "PL_0a_dropped": drop_pl, "PL_0a_total": n_pl,
            "pass": bool(fe <= MAX_DROP_FRAC and fp <= MAX_DROP_FRAC)}


def verdict(lo, hi, bar=BAR_PRIMARY):
    """Exclusive and exhaustive on the ON arm: DS-REMEDIED / DS-PERSISTS / DS-OPEN."""
    if hi < bar:
        return "DS-REMEDIED"
    if lo >= bar:
        return "DS-PERSISTS"
    return "DS-OPEN"


# ---------------------------------------------------------------- driver
def main(argv):
    stage = argv[1] if len(argv) > 1 else "offpoint"
    assert stage in ("offpoint", "full"), stage
    art = os.environ.get("OPENWSFZ_ARTEFACTS", os.path.join(REPO, "artefacts"))
    d = os.path.join(art, "rr_2026-10-09_density_sub")
    old = os.path.join(art, "rr_2026-10-01_onoff_replay")
    sel = json.load(open(os.path.join(REPO, "qa", "rr-study", "results", "2026-10-09-density-sub", "selection.json")))
    stamps = sel["runs"][RUN]["S10"]
    assert len(stamps) == 430
    alltxt = os.path.join(art, f"{RUN}_endurance_run-gathered", "wsjt-x", "ALL.TXT")
    w = load_w(alltxt, stamps)
    cycles = build_cycles(w, stamps)
    per_cycle = load_per_cycle(os.path.join(old, "per_cycle.csv"))
    res = {"stage": stage, "n_cycles": len(stamps), "n_W_total": sum(len(w[s]) for s in stamps)}

    m_off = load_matched(os.path.join(d, "matched_OFF.csv"))
    ab_old_on = load_abandon(os.path.join(old, "abandon_ON.csv"))
    res["V2"] = row_v2(cycles)
    res["V3"] = row_v3(cycles)
    res["V1_OFF"] = row_v1(stamps, m_off, per_cycle, "off", None, None)
    S_off = stack([cycle_counts(c, m_off.get(s, set())) for c, s in zip(cycles, stamps)])
    B_off = block_sums(S_off, len(stamps))
    D_off, da, na, db, nb = D_pair(S_off, "EXPOSED", "PL")
    res["D_off_point"] = D_off
    res["D_off_below_bar"] = bool(D_off < BAR_PRIMARY)   # to be flagged to the Architect BEFORE the verdict is read
    res["EXPOSED_drop_OFF"] = [da, na]

    if stage == "offpoint":
        print(json.dumps(res, indent=1, default=float))
        return 0

    m_on = load_matched(os.path.join(d, "matched_ON.csv"))
    ab_new_on = load_abandon(os.path.join(d, "abandon_ON.csv"))
    res["V1_ON"] = row_v1(stamps, m_on, per_cycle, "on", ab_new_on, ab_old_on)
    S_on = stack([cycle_counts(c, m_on.get(s, set())) for c, s in zip(cycles, stamps)])
    B_on = block_sums(S_on, len(stamps))
    pairs = [("off", "PL", "PF"), ("on", "PL", "PF"), ("off", "EXPOSED", "PL"), ("on", "EXPOSED", "PL")]
    draws, dd = bootstrap(B_off, B_on, pairs)
    for arm, S in (("off", S_off), ("on", S_on)):
        D0, d0a, n0a, _, _ = D_pair(S, "PL", "PF")
        lo0, hi0 = ci95(draws[(arm, "PL", "PF")])
        De, dea, nea, dpl, npl = D_pair(S, "EXPOSED", "PL")
        lo, hi = ci95(draws[(arm, "EXPOSED", "PL")])
        n_exp = int(S["EXPOSED"][0].sum())
        res[arm] = {"row0a": dict(row_0a(lo0, hi0), D=D0), "row0b": row_0b(dea, nea, d0a, n0a),
                    "D": De, "ci95": [lo, hi], "n_exposed": n_exp,
                    "C_pp": De * n_exp / res["n_W_total"] * 100.0,
                    "matched_rate_pct": {k: (100.0 * S[k][1].sum() / S[k][0].sum() if S[k][0].sum() else None) for k in CLASSES},
                    "n": {k: int(S[k][0].sum()) for k in CLASSES}}
    res["net_pp_per_stratum"] = {k: (100.0 * (S_on[k][1].sum() - S_off[k][1].sum()) / S_on[k][0].sum()
                                     if S_on[k][0].sum() else None) for k in CLASSES}
    res["delta_D"] = {"point": res["on"]["D"] - res["off"]["D"], "ci95": list(ci95(dd))}
    res["arm_valid_ON"] = bool(res["V1_ON"]["pass"] and res["V2"]["pass"] and res["V3"]["pass"]
                                and res["on"]["row0a"]["pass"] and res["on"]["row0b"]["pass"])
    res["arm_valid_OFF"] = bool(res["V1_OFF"]["pass"] and res["V2"]["pass"] and res["V3"]["pass"]
                                 and res["off"]["row0a"]["pass"] and res["off"]["row0b"]["pass"])
    res["verdict_ON"] = verdict(*res["on"]["ci95"]) if res["arm_valid_ON"] else "INVALID (a validity row failed; no verdict row is read)"
    out = os.path.join(REPO, "qa", "rr-study", "results", "2026-10-09-density-sub", "rows.json")
    json.dump(res, open(out, "w"), indent=1, default=float)
    print(json.dumps(res, indent=1, default=float))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
