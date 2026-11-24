#!/usr/bin/env python3
"""XC-PARITY (Architect ruling addendum section 7.4, E194/E195).  Desk feasibility of an R15 parity-block gate.  COUNTS ONLY (HK-037): message text is read inside functions, never written.
Usage:  python -I xc_parity.py p0 <out json>
        python -I xc_parity.py p1 <out json> [limit]        (limit = rows per class, for a timing smoke only)
Inputs: ON arm of the PC chain (nc.tsv, batch-6 publishes), WSJT-X ALL.TXT of the TEST night, the TEST night's ORIGINAL audio (O).

FRAME (FT8, 79 symbols): sync S7 [0..6], data block 1 [7..35], sync [36..42], data block 2 [43..71] (data symbols 30..58 = codeword bits 87..173: CRC tail + LDPC parity), sync [72..78].
P0  the 583 sender-sharing SUP-W pairs (template text, co-located WSJT-X text): equal tones per block.  Expected block 2 about 29/8 = 3.6.  If not near chance: STOP.
P1  S_P = the XC-TEMPLATE statistic (mean over symbols of P[tone]/mean_b P) over block 2 ONLY, evaluated AT THE ARGMAX of the full S_E search (R15's definition), on O.  dt handled with the 0.6 s convention offset (Q69).
    PREDICATE (pre-registered by the Architect before any S_P exists): FEASIBLE iff some T_P keeps >= 90 % of COR AND removes >= 90 % of SUP-W.  Report T_P, both fractions, and the FREE fraction removed.
    O understates buried COR rows, so the verdict is conservative for the gate.  The bars size a build; they never gate a ship."""
from __future__ import annotations

import collections
import importlib.util
import json
import multiprocessing as mp
import os
import statistics
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
QA = os.path.abspath(os.path.join(HERE, ".."))
for p in (HERE, os.path.join(QA, "xc-template"), os.path.join(QA, "rr-study", "coh-fallback"), os.path.join(QA, "rr-study", "n2-coherent-llr-extractor")):
    sys.path.insert(0, p)
import xc_sup as S   # noqa: E402  (classification helpers; the window constants are the Architect's)
import xt_lib as L   # noqa: E402

ON_DIR = "D:/Projects/claude/_qa-scratch/xc-chain/full/ON"
TEST_NIGHT = "D:/Projects/claude/OpenWSFZ/artefacts/20260808_live_run_0016-8080"
ALLTXT = TEST_NIGHT + "/wsjt-x/ALL.TXT"
WAVDIR = TEST_NIGHT + "/owsfz/wav"
DLL = "D:/Projects/claude/_qa-scratch/xc-chain/bin_new/libft8.dll"
DLL_PIN = "bbde6eb66af4cd429ffc46f67291ba718c1ae36ae39665faac24629bcb6e6528"
CALIB_S = 0.48                                           # TA-CHECK's frozen start-minus-dt (xt_score.py)
SYNC_A, DATA1, SYNC_B, DATA2, SYNC_C = range(0, 7), range(7, 36), range(36, 43), range(43, 72), range(72, 79)
SYNC = list(SYNC_A) + list(SYNC_B) + list(SYNC_C)
EXPECT_PAIRS = 583                                       # the Architect's / XC-SUP's sender-sharing SUP-W rows
EXPECT_CLASSES = {"COR": 904, "SUP-W": 641, "SUP-O": 16, "FREE": 1018}
BARS = (0.90, 0.90)
assert (len(SYNC), len(DATA1), len(DATA2)) == (21, 29, 29) and EXPECT_PAIRS == 583
_W = {}


def sha(path):
    import hashlib
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def load_instrument():
    path = os.path.join(QA, "rr-study", "coh-fallback", "cf_fbid.py")
    want = subprocess.run(["git", "-C", os.path.dirname(path), "rev-parse", "ecc4c5e7:qa/rr-study/coh-fallback/cf_fbid.py"], capture_output=True, text=True, check=True).stdout.strip()
    have = subprocess.run(["git", "-C", os.path.dirname(path), "hash-object", path], capture_output=True, text=True, check=True).stdout.strip()
    assert want == have, "instrument blob mismatch"
    spec = importlib.util.spec_from_file_location("cf_fbid_frozen", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def classify():
    """[(class, row, colocated different WSJT-X texts sharing the sender token (list of (df, text)), tones-of-publish-text-later)] for every batch-6 publish.  Text stays in this process."""
    nc = S.load_nc(ON_DIR + "/nc.tsv")
    ref = S.load_wsjtx(ALLTXT, set(nc))
    out = []
    for s, rows in nc.items():
        w = ref.get(s, [])
        own = [r for r in rows if r["kind"] in (1, 2, 3, 4, 5)]
        for r in rows:
            if r["kind"] != 6:
                continue
            tok = S.sender(r["text"])
            wd = [x for x in w if x[2] != r["text"] and S.in_window_w(x[0] - r["freq"], x[1] - r["dt"])]
            od = [x for x in own if x["text"] != r["text"] and S.in_window(x["freq"] - r["freq"], x["dt"] - r["dt"])]
            if r["matched"] == 1:
                c = "COR"
            elif wd:
                c = "SUP-W"
            elif od:
                c = "SUP-O"
            else:
                c = "FREE"
            share = [(x[0] - r["freq"], x[2]) for x in wd if tok and tok in x[2].split()]
            out.append((c, s, r, share))
    assert dict(collections.Counter(c for c, _, _, _ in out)) == EXPECT_CLASSES, collections.Counter(c for c, _, _, _ in out)
    return out


def p0(out_path):
    assert sha(DLL) == DLL_PIN
    F = load_instrument()
    enc = F.encoder(DLL)
    rows = [(c, s, r, sh) for c, s, r, sh in classify() if c == "SUP-W" and sh]
    assert len(rows) == EXPECT_PAIRS, len(rows)
    sync_eq, b1, b2, unenc, hashed = [], [], [], 0, 0
    for c, s, r, sh in rows:
        wtxt = min(sh, key=lambda x: abs(x[0]))[1]
        if "<" in r["text"] or "<" in wtxt:
            hashed += 1
        a, b = enc(r["text"]), enc(wtxt)
        if a is None or b is None:
            unenc += 1
            continue
        a, b = np.asarray(a), np.asarray(b)
        sync_eq.append(int((a[SYNC] == b[SYNC]).sum()))
        b1.append(int((a[list(DATA1)] == b[list(DATA1)]).sum()))
        b2.append(int((a[list(DATA2)] == b[list(DATA2)]).sum()))
    res = {"pairs": len(rows), "scored": len(b2), "unencodable": unenc, "hashed_in_pair": hashed,
           "sync_equal_of_21": {"mean": statistics.mean(sync_eq), "min": min(sync_eq)},
           "data_block1_equal_of_29": {"mean": statistics.mean(b1), "median": statistics.median(b1), "min": min(b1), "max": max(b1)},
           "data_block2_equal_of_29": {"mean": statistics.mean(b2), "median": statistics.median(b2), "min": min(b2), "max": max(b2),
                                      "hist": dict(sorted(collections.Counter(b2).items())), "chance_expectation": 29 / 8},
           "frame_fact_holds": abs(statistics.mean(b2) - 29 / 8) <= 1.0 and statistics.mean(sync_eq) >= 20.9}
    json.dump(res, open(out_path, "w"), indent=1)
    print(json.dumps(res, indent=1))


# ------------------------------------------------------------------------------------------------ P1
def _init():
    import coherent_extract as CE
    import wavio
    _W["CE"], _W["wavio"], _W["buf"] = CE, wavio, {}


def _pcm(stamp):
    b = _W["buf"]
    if stamp not in b:
        if len(b) > 4:
            b.clear()
        b[stamp] = _W["wavio"].load_cycle_pcm(f"{WAVDIR}/{stamp}.wav")
    return b[stamp]


def s_block(P, den, tones, idx):
    num = P[np.asarray(list(idx)), np.asarray(tones)[list(idx)]]
    d = den[np.asarray(list(idx))]
    return float(np.where(d > 0, num / np.where(d > 0, d, 1.0), 1.0).mean())


def work(task):
    """task: stamp, f, dt_c (WSJT-X convention), tones -> S_E* and its argmax, S_P at the argmax, and S_Pmax (own search over the block-2 statistic)."""
    CE = _W["CE"]
    pcm = _pcm(task["stamp"])
    tones = task["tones"]
    bb = CE.downconvert_decimate(pcm, float(task["f"]))
    best, best_sp, best_spmax, arg = -1.0, None, -1.0, None
    for d in L.df_grid():
        sb = L.shift_baseband(bb, d)
        for e in L.dt_grid():
            smp = int(round((task["dt_c"] + e + CALIB_S) * L.FS_OUT))
            X = CE.correlate_symbols(sb, smp)
            P = X.real ** 2 + X.imag ** 2
            den = P.sum(axis=1) / L.N_TONES
            se = float(np.where(den > 0, P[np.arange(L.N_SYM), np.asarray(tones)] / np.where(den > 0, den, 1.0), 1.0).mean())
            sp = s_block(P, den, tones, DATA2)
            if sp > best_spmax:
                best_spmax = sp
            if se > best:
                best, best_sp, arg = se, sp, (task["f"] + d, task["dt_c"] + e)
    return {"S_E": best, "S_P": best_sp, "S_Pmax": best_spmax, "af": arg[0], "adt": arg[1]}


def p1(out_path, limit=None):
    assert sha(DLL) == DLL_PIN
    F = load_instrument()
    enc = F.encoder(DLL)
    rows = [x for x in classify() if x[0] in ("COR", "SUP-W", "FREE")]
    if limit:
        keep, cnt = [], collections.Counter()
        for x in rows:
            if cnt[x[0]] < limit:
                keep.append(x)
                cnt[x[0]] += 1
        rows = keep
    tasks, meta, unenc = [], [], collections.Counter()
    for c, s, r, sh in rows:
        t = enc(r["text"])
        if t is None:
            unenc[c] += 1
            continue
        tasks.append({"stamp": s, "f": r["freq"], "dt_c": r["dt"] - S.DT_CONV_S, "tones": [int(v) for v in t]})
        meta.append((c, bool(sh), r["snr"]))
    with mp.Pool(8, initializer=_init) as pool:
        res = pool.map(work, tasks, chunksize=16)
    out = collections.defaultdict(list)
    for (c, shared, snr), r in zip(meta, res):
        out[c].append({"S_E": r["S_E"], "S_P": r["S_P"], "S_Pmax": r["S_Pmax"], "shared": shared, "snr": snr})
    summary = {"unencodable": dict(unenc), "n_scored": {c: len(v) for c, v in out.items()}}
    cor = np.array([x["S_P"] for x in out["COR"]])
    sw = np.array([x["S_P"] for x in out["SUP-W"]])
    fr = np.array([x["S_P"] for x in out["FREE"]])
    summary["S_P_quantiles"] = {c: [float(np.percentile(np.array([x["S_P"] for x in out[c]]), q)) for q in (5, 25, 50, 75, 95)] for c in out}
    summary["S_E_quantiles"] = {c: [float(np.percentile(np.array([x["S_E"] for x in out[c]]), q)) for q in (5, 25, 50, 75, 95)] for c in out}
    cands = np.unique(np.concatenate([cor, sw, fr]))
    best = None
    table = []
    for t in cands:
        keep, rem_w, rem_f = float((cor >= t).mean()), float((sw < t).mean()), float((fr < t).mean())
        if keep >= BARS[0] and rem_w >= BARS[1]:
            if best is None or rem_w + keep > best[1] + best[2]:
                best = (float(t), keep, rem_w, rem_f)
    # the trade-off table at a few thresholds (descriptive)
    for q in (50, 75, 90, 95, 99):
        t = float(np.percentile(sw, q))
        table.append({"T_P": t, "removes_SUPW": float((sw < t).mean()), "keeps_COR": float((cor >= t).mean()), "removes_FREE": float((fr < t).mean())})
    # the same on the sender-sharing SUP-W subset, and an AUC (COR above SUP-W)
    swsh = np.array([x["S_P"] for x in out["SUP-W"] if x["shared"]])
    auc = float((cor[:, None] > sw[None, :]).mean() + 0.5 * (cor[:, None] == sw[None, :]).mean())
    summary.update({"feasible": best is not None, "best": None if best is None else {"T_P": best[0], "keeps_COR": best[1], "removes_SUPW": best[2], "removes_FREE": best[3]},
                    "table": table, "auc_COR_over_SUPW": auc, "n_SUPW_sender_sharing_scored": int(len(swsh)),
                    "max_S_P_keep90_cor": float(np.percentile(cor, 10)), "SUPW_removed_at_COR_keep90": float((sw < np.percentile(cor, 10)).mean()),
                    "FREE_removed_at_COR_keep90": float((fr < np.percentile(cor, 10)).mean())})
    json.dump(summary, open(out_path, "w"), indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    if sys.argv[1] == "p0":
        p0(sys.argv[2])
    else:
        p1(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else None)
