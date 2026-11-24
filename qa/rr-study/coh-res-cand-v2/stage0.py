#!/usr/bin/env python3
"""COH-RES-CAND v2, Stage 0 (spec 2026-11-12-1340 section 1 + Amendment 1 section 8; QA (k) review 1fe6b588 froze the features).

  python stage0.py derive   step 1: re-derive P0's classes with #272's frozen instrument into a NEW path; STOP (exit 2) if the counts differ.
  python stage0.py select   steps 2 and 3: the selection rule once, then p_perm (5,000 label permutations, seed 20261112, p0_null.py's procedure).

Frozen decision values (each with its source):
  features, in this order ...... snr, dt, freq (QA (k) review, commit 1fe6b588; WSJT-X-derived columns and constants excluded).
  admissible ................... kept_TA <= 4 (spec section 1; unchanged by Amendment 1 K3).
  FEASIBLE ..................... kept_C >= 40 AND p_perm <= 0.05 (Amendment 1 K1).
  tie rule ..................... larger kept_C, then smaller kept_TA, then the earlier feature, then the threshold that keeps more rows (spec section 1);
                                 then '>=' before '<=' (the spec is silent; stated here before any output).
  p_perm ....................... share of PERMS label permutations whose best admissible kept_C is >= the observed one; RNG random.Random(20261112),
                                 one list shuffled in place per draw, exactly as p0_null.py at 1fe6b588.
  instrument ................... crc_analyse.py at 87c5486a imported (never copied); classes file sha256 prefix 8046a4be4b806fcd08b9; selection sha prefix 2575e115.
HK-037: message text exists only in this process's memory; what is written is numeric (snr, dt, freq, class) and aggregates.
"""
import csv
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = "D:/Projects/claude/_qa-scratch/coh-res-cand-v2"
ROWS_CSV = OUT + "/p0_rows.csv"
RESULT_JSON = OUT + "/stage0_result.json"

FEATURES = ("snr", "dt", "freq")
DIRECTIONS = (">=", "<=")
KEPT_TA_MAX = 4
KEPT_C_MIN = 40
P_PERM_MAX = 0.05
SEED = 20261112
PERMS = 5000
EXPECT = {"P0": 149, "C": 119, "TA": 19, "tested_present": 9, "hashed_or_unencodable": 2, "untestable_class": 0}
CLASSES_SHA_PREFIX = "8046a4be4b806fcd08b9"
assert (KEPT_TA_MAX, KEPT_C_MIN, P_PERM_MAX, SEED, PERMS) == (4, 40, 0.05, 20261112, 5000)
assert EXPECT["P0"] == EXPECT["C"] + EXPECT["TA"] + EXPECT["tested_present"] + EXPECT["hashed_or_unencodable"] + EXPECT["untestable_class"]


def derive():
    sys.path.insert(0, os.path.join(HERE, "..", "gap-residual-run"))
    assert os.environ.get("CRC_DRY") != "1"
    import crc_analyse as M
    assert M.sha(M.CLASSES).startswith(CLASSES_SHA_PREFIX), "classes file differs from the frozen one"
    stamps = M.stamps_of()                       # asserts the frozen selection sha
    M.C.ALLTXT = M.NIGHT + "/wsjt-x/ALL.TXT"
    ref = M.C.load_ref(set(stamps))
    a, b = M.load_nc(f"{M.SCR}/{M.ARM_A}/nc_dump.tsv"), M.load_nc(f"{M.SCR}/{M.ARM_B}/nc_dump.tsv")
    status = M.instrument(None)
    rows, counts = [], {"tested_present": 0, "hashed_or_unencodable": 0, "untestable_class": 0}
    for s in stamps:
        r = ref.get(s, [])
        b_rows = b.get(s, [])
        _, b_uo = M.L.match(r, [(x["kind"], x["f"], x["text"]) for x in b_rows])
        a_texts = {x["text"] for x in a.get(s, [])}
        for i, x in enumerate(b_rows):
            if x["kind"] != M.KIND_FALLBACK or x["text"] in a_texts:
                continue
            if i in b_uo:
                cls = "C"
            else:
                sx = status(s, x["text"], x["f"], x["dt"])
                if sx == "tested_absent":
                    cls = "TA"
                else:
                    cls = "O"
                    counts[sx] += 1
            rows.append((x["snr"], x["dt"], x["f"], cls))
    got = {"P0": len(rows), "C": sum(1 for r in rows if r[3] == "C"), "TA": sum(1 for r in rows if r[3] == "TA"), **counts}
    print("re-derived:", got)
    print("expected  :", EXPECT)
    if got != EXPECT:
        print("STOP: the re-derived counts differ from #272's report; no feature has been looked at (spec section 1).")
        sys.exit(2)
    os.makedirs(OUT, exist_ok=True)
    with open(ROWS_CSV, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["snr", "dt", "freq", "cls"])
        for r in rows:
            w.writerow([r[0], f"{r[1]:.2f}", r[2], r[3]])
    print("wrote", ROWS_CSV, "(numeric only)")


def load_rows():
    with open(ROWS_CSV, newline="") as f:
        return [dict(snr=int(r["snr"]), dt=round(float(r["dt"]), 2), freq=int(r["freq"]), cls=r["cls"]) for r in csv.DictReader(f)]


def gates(rows):
    for fi, ft in enumerate(FEATURES):
        for t in sorted({x[ft] for x in rows}):
            for di, d in enumerate(DIRECTIONS):
                yield fi, ft, di, d, t


def keep(x, ft, d, t):
    return x[ft] >= t if d == ">=" else x[ft] <= t


def evaluate(rows, g):
    _, ft, _, d, t = g
    kc = sum(1 for x in rows if x["cls"] == "C" and keep(x, ft, d, t))
    kt = sum(1 for x in rows if x["cls"] == "TA" and keep(x, ft, d, t))
    ko = sum(1 for x in rows if x["cls"] == "O" and keep(x, ft, d, t))
    return kc, kt, ko


def choose(rows):
    best_key, best = None, None
    for g in gates(rows):
        kc, kt, ko = evaluate(rows, g)
        if kt > KEPT_TA_MAX:
            continue
        key = (-kc, kt, g[0], -(kc + kt + ko), g[2])
        if best_key is None or key < best_key:
            best_key, best = key, (g, kc, kt, ko)
    return best


def best_kept_c(rows, labels):
    """Best admissible kept_C under the given labels (the permutation null; identical family to p0_null.py)."""
    top = -1
    for ft in FEATURES:
        vals = sorted({x[ft] for x in rows})
        for d in DIRECTIONS:
            for t in vals:
                kc = kt = 0
                for x, l in zip(rows, labels):
                    if keep(x, ft, d, t):
                        kc += l == "C"
                        kt += l == "TA"
                if kt <= KEPT_TA_MAX and kc > top:
                    top = kc
    return top


def select():
    rows = load_rows()
    n_c = sum(1 for x in rows if x["cls"] == "C")
    n_ta = sum(1 for x in rows if x["cls"] == "TA")
    assert (len(rows), n_c, n_ta) == (EXPECT["P0"], EXPECT["C"], EXPECT["TA"])
    ch = choose(rows)
    if ch is None:
        print("no admissible gate at all (kept_TA <= 4 never holds): NOT-FEASIBLE")
        verdict, out = "NOT-FEASIBLE", {"admissible": False}
    else:
        g, kc, kt, ko = ch
        rng = random.Random(SEED)
        labels = ["C"] * n_c + ["TA"] * n_ta + ["O"] * (len(rows) - n_c - n_ta)
        ge = 0
        for _ in range(PERMS):
            rng.shuffle(labels)
            ge += best_kept_c(rows, labels) >= kc
        p_perm = ge / PERMS
        feasible = kc >= KEPT_C_MIN and p_perm <= P_PERM_MAX
        verdict = "FEASIBLE" if feasible else "NOT-FEASIBLE"
        per_feature = {}
        for ft in FEATURES:
            cand = [(g2, *evaluate(rows, g2)) for g2 in gates(rows) if g2[1] == ft]
            cand = [c for c in cand if c[2] <= KEPT_TA_MAX]
            per_feature[ft] = max((c[1] for c in cand), default=None)
        out = {"admissible": True, "feature": g[1], "direction": g[3], "threshold": g[4], "kept_C": kc, "kept_TA": kt, "kept_other": ko,
               "p_perm": p_perm, "perms_ge_observed": ge, "perms": PERMS, "kept_C_ge_40": kc >= KEPT_C_MIN, "p_perm_le_0.05": p_perm <= P_PERM_MAX,
               "descriptive_best_kept_C_per_feature_at_kept_TA_le_4": per_feature, "P0": len(rows), "C": n_c, "TA": n_ta}
    out["verdict"] = verdict
    print(json.dumps(out, indent=1))
    json.dump(out, open(RESULT_JSON, "w"), indent=1)


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("derive", "select"):
        sys.exit(__doc__)
    derive() if sys.argv[1] == "derive" else select()
