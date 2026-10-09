#!/usr/bin/env python
"""COH-GAIN Amendment 7 (Q-GATE), spec section 16: thresholds on TRAIN, evaluation on TEST, the rows, as code. U_max = 0.15 unexplained outputs per cycle (Captain, FROZEN); BAR_G = 1.0 pp (Captain).

MECHANICAL ORDER (enforced here, not by promise):
  1. features exist for every row (cg_gate_run.py --features); NO label is read by that step.
  2. `--train`  loads labels for the TRAIN samples ONLY (5, 1, 2, 4), picks the three thresholds, writes gate_thresholds.json with their TRAIN figures.
  3. gate_thresholds.json is COMMITTED.
  4. `--test`   REFUSES to run unless gate_thresholds.json is tracked and unchanged in git; only then are the TEST samples' (6, 8, 9) labels loaded and the rows computed.

Labels (never a gate input): RIGHT = the persisted C3_ok; for a wrong BP output the WRONG-ID class: M-NEAR -> NEAR (a real neighbour, NOT unexplained); M-NONE and M-OWS -> UNEXPL (note: M-OWS counts against the gate, OWS is not
independent). A path-1 (OSD) output counts as NO output (the fallback runs with OSD off): it is never kept, and its F2 is only reported.

Threshold rule per form on TRAIN: maximise kept RIGHT subject to UNEXPL kept per TRAIN cycle <= 0.15; candidates are the observed TRAIN feature values (GC: the full grid); ties -> fewer UNEXPL, then more rows kept (the looser threshold);
no feasible threshold -> the form is GATE-FAIL without a test. Rows on TEST per form: GATE-OK iff CI_lo(KG) >= 1.0 AND CI_hi(UPC) <= 0.15; GATE-FAIL iff CI_hi(KG) < 1.0 OR CI_lo(UPC) > 0.15; else GATE-OPEN. Three forms are three tests.
"""
from __future__ import annotations

import csv
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cg_common as CG  # noqa: E402
import cg_gate_run as GR  # noqa: E402
import cg_rows as R  # noqa: E402
import cg_select as SEL  # noqa: E402
import cg_wrongid as W  # noqa: E402

U_MAX = GR.U_MAX
BAR_KG = CG.BAR_G
THRESHOLDS_PATH = os.path.join(SEL.OUT_DIR, "gate_thresholds.json")
ANALYSIS_NAME = "analysis_gate.json"
FORMS = ("GA", "GB", "GC")
assert U_MAX == 0.15 and BAR_KG == 1.0 and GR.TRAIN == (5, 1, 2, 4) and GR.TEST == (6, 8, 9)


# ------------------------------------------------------------------------------------------------------------------ loading
def load_features(path=None):
    out = {}
    for r in csv.DictReader(open(path or GR.FEATURES_CSV, newline="", encoding="utf-8")):
        key = (int(r["sample"]), int(r["cycle_index"]), int(r["widx"]))
        out[key] = {"kind": r["kind"], "q1_ok": int(r["q1_ok"]), "f1b": float(r["f1b"]) if r["f1b"] != "" else None,
                    "f2": float(r["f2"]) if r["f2"] != "" else None, "f3": float(r["f3"]) if r["f3"] != "" else None}
    return out


def load_labels(samples, wrongid_csv=None, rows_by_sample=None):
    """{(sample, cycle, widx): 'RIGHT' | 'NEAR' | 'UNEXPL' | 'OSD'} for the given samples ONLY. Called with TRAIN before the thresholds are committed; the TEST labels are never requested earlier."""
    import cg_wrongid_rows as WR
    wr = {(r["sample"], r["cycle_index"], r["widx"]): r for r in WR.load_out(wrongid_csv or W.OUT_CSV) if r["set"] == "C3" and r["sample"] in samples}
    labels = {}
    rbs = rows_by_sample or {res: R.load_rows(os.path.join(W.ART, W.SAMPLES[res], "rows.csv")) for res in samples}
    for res in samples:
        for x in rbs[res]:
            if x["fault"] or int(x["G_ok"]) or int(x["C3_crc"]) != 1:
                continue
            key = (res, int(x["cycle_index"]), int(x["widx"]))
            if int(x["C3_path"]) == 1:
                labels[key] = "OSD"
            elif int(x["C3_ok"]):
                labels[key] = "RIGHT"
            else:
                c = wr[key]["cls"]
                labels[key] = "NEAR" if c == "M-NEAR" else "UNEXPL"
    return labels


def sample_cycle_orders(samples):
    return {res: sorted({r[0] for r in json.load(open(SEL.rows_path(res)))["rows"]}) for res in samples}


def rows_per_cycle(samples, rows_by_sample=None):
    out = {}
    for res in samples:
        rows = rows_by_sample[res] if rows_by_sample else R.load_rows(os.path.join(W.ART, W.SAMPLES[res], "rows.csv"))
        c = {}
        for x in rows:
            if not x["fault"]:
                c[int(x["cycle_index"])] = c.get(int(x["cycle_index"]), 0) + 1
        out[res] = c
    return out


def joined(samples, features, labels):
    """BP rows with a feature and a label: [(sample, cycle, widx, f1b, f2, f3, label)] (OSD rows excluded: they are 'no output')."""
    return [(k[0], k[1], k[2], f["f1b"], f["f2"], f["f3"], labels[k]) for k, f in features.items()
            if k[0] in samples and f["kind"] == "bp" and k in labels and f["f1b"] is not None]


# ------------------------------------------------------------------------------------------------------------------ thresholds (TRAIN only)
def _pick(feasible_right, feasible_unexpl, feasible_kept, order_key):
    """Index of the best feasible candidate: max kept RIGHT, then fewer UNEXPL, then more rows kept (looser), then the deterministic order key."""
    best = None
    for i in range(len(feasible_right)):
        k = (feasible_right[i], -feasible_unexpl[i], feasible_kept[i], -order_key[i])
        if best is None or k > best[0]:
            best = (k, i)
    return None if best is None else best[1]


def select_thresholds(train_rows, n_train_cycles, umax=U_MAX):
    """train_rows: joined() rows of the TRAIN samples only. Returns {'GA': {...}|None, 'GB': ..., 'GC': ...}; None means no feasible threshold (GATE-FAIL without a test)."""
    assert train_rows and {r[0] for r in train_rows} <= set(GR.TRAIN), "TRAIN rows only"
    f1 = np.array([r[3] for r in train_rows])
    f2 = np.array([r[4] for r in train_rows])
    right = np.array([r[6] == "RIGHT" for r in train_rows], dtype=np.int64)
    unexp = np.array([r[6] == "UNEXPL" for r in train_rows], dtype=np.int64)
    near = np.array([r[6] == "NEAR" for r in train_rows], dtype=np.int64)
    cap = umax * n_train_cycles
    out = {}

    def figs(mask):
        return {"kept_right": int(right[mask].sum()), "kept_unexplained": int(unexp[mask].sum()), "kept_near": int(near[mask].sum()), "kept_rows": int(mask.sum()),
                "upc": float(unexp[mask].sum() / n_train_cycles)}

    # GA: keep F1b <= T1.  Candidates = observed values, ascending.
    cand = np.unique(f1)
    cum_r = np.array([right[f1 <= t].sum() for t in cand])
    cum_u = np.array([unexp[f1 <= t].sum() for t in cand])
    cum_k = np.array([(f1 <= t).sum() for t in cand])
    ok = [i for i in range(len(cand)) if cum_u[i] <= cap]
    i = _pick([cum_r[j] for j in ok], [cum_u[j] for j in ok], [cum_k[j] for j in ok], [cand[j] for j in ok]) if ok else None
    out["GA"] = None if i is None else {"T1": float(cand[ok[i]]), **figs(f1 <= cand[ok[i]])}
    # GB: keep F2 >= T2.  Candidates = observed values, descending.
    cand2 = np.unique(f2)[::-1]
    cum_r2 = np.array([right[f2 >= t].sum() for t in cand2])
    cum_u2 = np.array([unexp[f2 >= t].sum() for t in cand2])
    cum_k2 = np.array([(f2 >= t).sum() for t in cand2])
    ok2 = [i for i in range(len(cand2)) if cum_u2[i] <= cap]
    i2 = _pick([cum_r2[j] for j in ok2], [cum_u2[j] for j in ok2], [cum_k2[j] for j in ok2], [-cand2[j] for j in ok2]) if ok2 else None
    out["GB"] = None if i2 is None else {"T2": float(cand2[ok2[i2]]), **figs(f2 >= cand2[ok2[i2]])}
    # GC: the FULL grid (T1, T2) of observed values, by 2-D cumulative counts (rank space).
    u1 = np.unique(f1)                       # ascending: kept if F1b <= T1 -> cumulative over axis 0
    u2 = np.unique(f2)[::-1]                 # descending: kept if F2 >= T2 -> cumulative over axis 1
    r1 = np.searchsorted(u1, f1)
    r2 = np.searchsorted(-u2, -f2)           # position of f2 in the descending list
    shape = (len(u1), len(u2))
    mats = []
    for v in (right, unexp, np.ones_like(right)):
        h = np.zeros(shape, dtype=np.int64)
        np.add.at(h, (r1, r2), v)
        mats.append(h.cumsum(axis=0).cumsum(axis=1))
    mr, mu, mk = mats
    feas = mu <= cap
    if feas.any():
        best_r = np.where(feas, mr, -1).max()
        cand_mask = feas & (mr == best_r)
        min_u = np.where(cand_mask, mu, np.iinfo(np.int64).max).min()
        cand_mask &= mu == min_u
        max_k = np.where(cand_mask, mk, -1).max()
        cand_mask &= mk == max_k
        ii, jj = np.argwhere(cand_mask)[0]                       # deterministic: first in (T1 ascending, T2 descending) order
        t1, t2 = float(u1[ii]), float(u2[jj])
        out["GC"] = {"T1": t1, "T2": t2, **figs((f1 <= t1) & (f2 >= t2))}
    else:
        out["GC"] = None
    return out


def keep_mask(form, th, f1b, f2):
    f1b, f2 = np.asarray(f1b), np.asarray(f2)
    if th is None:
        return np.zeros(len(f1b), dtype=bool)
    if form == "GA":
        return f1b <= th["T1"]
    if form == "GB":
        return f2 >= th["T2"]
    return (f1b <= th["T1"]) & (f2 >= th["T2"])


# ------------------------------------------------------------------------------------------------------------------ evaluation (blocks within sample, pooled)
def per_cycle_counts(rows, form, th, samples, cycles, rpc):
    """For each sample, per cycle of the FULL order: (rows in cycle, kept RIGHT, kept UNEXPL, kept NEAR)."""
    sel = [r for r in rows if r[0] in samples]
    keep = keep_mask(form, th, [r[3] for r in sel], [r[4] for r in sel])
    acc = {res: {c: [0, 0, 0] for c in cycles[res]} for res in samples}
    for r, k in zip(sel, keep):
        if k:
            a = acc[r[0]].setdefault(r[1], [0, 0, 0])
            a[0] += r[6] == "RIGHT"
            a[1] += r[6] == "UNEXPL"
            a[2] += r[6] == "NEAR"
    out = {}
    for res in samples:
        order = cycles[res]
        out[res] = np.array([[rpc[res].get(c, 0)] + acc[res].get(c, [0, 0, 0]) for c in order], dtype=float)
    return out


def evaluate(rows, form, th, samples, cycles, rpc, block=CG.BLOCK_CYCLES):
    """KG = 100 * kept RIGHT / sum rows; UPC = kept UNEXPL / cycles; 95 % CIs from blocks of `block` cycles WITHIN each sample, pooled, B and seed as the primary."""
    pc = per_cycle_counts(rows, form, th, samples, cycles, rpc)
    nums_k, dens_k, nums_u, dens_u = [], [], [], []
    tot = np.zeros(4)
    for res in samples:
        a = pc[res]
        edges = list(range(0, len(a), block))
        nums_k.append(np.array([a[i:i + block, 1].sum() for i in edges]))
        dens_k.append(np.array([a[i:i + block, 0].sum() for i in edges]))
        nums_u.append(np.array([a[i:i + block, 2].sum() for i in edges]))
        dens_u.append(np.array([len(a[i:i + block]) for i in edges], dtype=float))
        tot += np.array([a[:, 0].sum(), a[:, 1].sum(), a[:, 2].sum(), a[:, 3].sum()])
    nk, dk, nu, du = (np.concatenate(x) for x in (nums_k, dens_k, nums_u, dens_u))
    rng = np.random.default_rng(CG.SEED)
    idx = rng.integers(0, len(nk), size=(CG.B_RESAMPLES, len(nk)))
    kg = 100.0 * nk[idx].sum(axis=1) / dk[idx].sum(axis=1)
    upc = nu[idx].sum(axis=1) / du[idx].sum(axis=1)
    n_cycles = int(sum(len(cycles[r]) for r in samples))
    return {"KG_pp": 100.0 * tot[1] / tot[0], "KG_ci95": [float(x) for x in np.percentile(kg, [2.5, 97.5])],
            "UPC": float(tot[2] / n_cycles), "UPC_ci95": [float(x) for x in np.percentile(upc, [2.5, 97.5])],
            "kept_right": int(tot[1]), "kept_unexplained": int(tot[2]), "kept_near": int(tot[3]), "n_rows": int(tot[0]), "n_cycles": n_cycles, "n_blocks": len(nk)}


def gate_row(kg_lo, kg_hi, upc_lo, upc_hi, bar=BAR_KG, umax=U_MAX):
    """Exclusive, first match wins (spec 16.6)."""
    if kg_lo >= bar and upc_hi <= umax:
        return "GATE-OK"
    if kg_hi < bar or upc_lo > umax:
        return "GATE-FAIL"
    return "GATE-OPEN"


# ------------------------------------------------------------------------------------------------------------------ order enforcement and the two commands
def git_committed_unchanged(path):
    try:
        rel = os.path.relpath(path, CG.REPO_ROOT).replace("\\", "/")
    except ValueError:
        return False                                        # another drive: cannot be this repo's tracked file
    if rel.startswith(".."):
        return False
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", "--", rel], cwd=CG.REPO_ROOT, capture_output=True, text=True).returncode == 0
    clean = subprocess.run(["git", "status", "--porcelain", "--", rel], cwd=CG.REPO_ROOT, capture_output=True, text=True).stdout.strip() == ""
    return tracked and clean


def cmd_train(features_path=None, labels=None, results_dir=None):
    feats = load_features(features_path)
    q1_bad = [k for k, f in feats.items() if not f["q1_ok"]]
    labels = labels if labels is not None else load_labels(set(GR.TRAIN))
    assert all(k[0] in GR.TRAIN for k in labels), "TRAIN labels only before the thresholds are committed"
    cyc = sample_cycle_orders(GR.TRAIN)
    n_cycles = sum(len(v) for v in cyc.values())
    th = select_thresholds(joined(set(GR.TRAIN), feats, labels), n_cycles)
    out = {"U_max": U_MAX, "train_samples": list(GR.TRAIN), "train_cycles": n_cycles, "thresholds": th,
           "features_csv_sha256": CG.file_sha256(features_path or GR.FEATURES_CSV), "q1_not_reproduced_rows_all_samples": len(q1_bad),
           "note": "chosen on TRAIN only; commit this file BEFORE cg_gate_rows.py --test (the test refuses otherwise)"}
    p = os.path.join(results_dir or SEL.OUT_DIR, "gate_thresholds.json")
    json.dump(out, open(p, "w"), indent=1, sort_keys=True)
    return out


def cmd_test(features_path=None, results_dir=None, labels=None, rows_by_sample=None, cycles=None, check_commit=True, thresholds_path=None):
    tp = thresholds_path or THRESHOLDS_PATH
    if check_commit:
        assert git_committed_unchanged(tp), "gate_thresholds.json must be COMMITTED and unchanged before any TEST label is read (spec 16.4 order)"
    spec = json.load(open(tp))
    feats = load_features(features_path)
    labels = labels if labels is not None else load_labels(set(GR.TEST))
    cycles = cycles or sample_cycle_orders(GR.TEST)
    rpc = rows_per_cycle(GR.TEST, rows_by_sample)
    test_rows = joined(set(GR.TEST), feats, labels)
    q1_ok = all(f["q1_ok"] for f in feats.values())
    result = {"validity": {"Q1": {"pass": q1_ok, "rows": len(feats), "not_reproduced": sum(1 for f in feats.values() if not f["q1_ok"])}},
              "U_max": U_MAX, "BAR_G": BAR_KG, "forms": {}}
    for form in FORMS:
        th = spec["thresholds"][form]
        if th is None:
            result["forms"][form] = {"threshold": None, "row": "GATE-FAIL", "why": "no threshold met U_max on TRAIN"}
            continue
        ev = evaluate(test_rows, form, th, set(GR.TEST), cycles, rpc)
        row = gate_row(ev["KG_ci95"][0], ev["KG_ci95"][1], ev["UPC_ci95"][0], ev["UPC_ci95"][1]) if q1_ok else "NO READING"
        result["forms"][form] = {"threshold": th, "test": ev, "row": row}
    oks = [(f, v["test"]["KG_pp"]) for f, v in result["forms"].items() if v["row"] == "GATE-OK"]
    result["gate_ok_forms"] = [f for f, _ in oks]
    result["step3_form"] = max(oks, key=lambda x: x[1])[0] if oks else None
    if results_dir:
        os.makedirs(results_dir, exist_ok=True)
        json.dump(result, open(os.path.join(results_dir, ANALYSIS_NAME), "w"), indent=1, sort_keys=True, default=str)
    return result


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "--train":
        r = cmd_train()
        print(json.dumps({"thresholds": r["thresholds"], "q1_not_reproduced": r["q1_not_reproduced_rows_all_samples"]}, indent=1))
    elif mode == "--test":
        r = cmd_test(results_dir=SEL.OUT_DIR)
        print(json.dumps({"gate_ok_forms": r["gate_ok_forms"], "step3_form": r["step3_form"], "rows": {f: v["row"] for f, v in r["forms"].items()}}, indent=1))
    else:
        print("usage: cg_gate_rows.py --train | --test")
