"""P0 size and a label-permutation null for the Stage 0 FEASIBLE row (COH-RES-CAND v2 (k) review).
HK-037: message text is read only to decide 'new text' inside this process; aggregates only are printed.
Columns used: 0 stamp, 1 kind, 2 matched, 3 freq, 4 dt, 5 snr. Nothing computed here relates a feature to a class.
"""
import collections
import random
import sys

S = "D:/Projects/claude/_qa-scratch/coh-res-cand/scratch"


def load(arm):
    d = collections.defaultdict(list)
    with open(f"{S}/{arm}/nc_dump.tsv", encoding="utf-8", errors="replace") as f:
        for line in f:
            r = line.rstrip("\n").split("\t")
            d[r[0]].append(dict(kind=int(r[1]), matched=int(r[2]), f=int(r[3]), dt=float(r[4]), snr=int(r[5]), text="\t".join(r[10:])))
    return d


A, B = load("A"), load("B")
P0 = []
for st, rows in B.items():
    atexts = {x["text"] for x in A.get(st, [])}
    for x in rows:
        if x["kind"] == 4 and x["text"] not in atexts:
            P0.append(x)
n = len(P0)
c1 = sum(x["matched"] for x in P0)
print("P0 rows", n, "| matched=1 (class C)", c1, "| matched=0", n - c1)
assert (n, c1) == (149, 119), (n, c1)

FEATS = ("snr", "dt", "f")
N_TA, N_C = 19, 119   # the report's split; 11 'other' carried
rng = random.Random(20261112)
labels = ["C"] * N_C + ["TA"] * N_TA + ["O"] * (n - N_C - N_TA)


def best(lbl):
    top = (-1, None)
    for ft in FEATS:
        vals = sorted({x[ft] for x in P0})
        for d in (">=", "<="):
            for t in vals:
                kc = kt = 0
                for x, l in zip(P0, lbl):
                    ok = x[ft] >= t if d == ">=" else x[ft] <= t
                    if ok:
                        kc += l == "C"
                        kt += l == "TA"
                if kt <= 4 and kc > top[0]:
                    top = (kc, (ft, d, t, kt))
    return top


N_PERM = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
hits = 0
kcs = []
for _ in range(N_PERM):
    rng.shuffle(labels)
    kc, _ = best(labels)
    kcs.append(kc)
    hits += kc >= 40
kcs.sort()
print(f"null (labels permuted, {N_PERM} draws, 3 features x 2 directions x observed thresholds): P(kept_C >= 40 with kept_TA <= 4) = {hits / N_PERM:.3f}")
print("null kept_C quantiles 50/90/95/99:", [kcs[int(q * (len(kcs) - 1))] for q in (0.5, 0.9, 0.95, 0.99)])
