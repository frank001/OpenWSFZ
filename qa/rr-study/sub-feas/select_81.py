#!/usr/bin/env python
"""SUB-FEAS §8.1 real-band replay: build selection.json from the Architect's pre-registered rule.

Spec: qa/rr-study/2026-09-29-2010-architect-sub-feas-8-1-real-band-runtime-replay-spec.md
      (+ Amendment 1 (R0 per-run producing DLL, R6 allowance) and Amendment 2 (build 2b39cf18)).

Interpretations made HERE, before any timing is read (disclosed in the report):
  * Pilot = 20 cycles PER RUN (Amendment 1: "pilot drawn per run so every run's producing DLL is
    exercised"). All pilots are drawn first, in run order, from the same RNG stream.
  * Pilot pool = every cycle of that run with pass-0 count >= 20 and a daemon WAV present.
  * H = every non-pilot cycle with count >= 25. M = 100 per run sampled from the non-pilot cycles
    with 20 <= count <= 24. Warm-up cycle per run = the smallest stamp in the >= 20 pool that is
    in none of pilot/H/M (discarded, one per process start).
  * R6 pairs: the 20 lowest stamps of the pooled H list (sorted by stamp string), each paired with
    the next H stamp in that sorted list (the last of the 20 pairs with the 21st).
  * Pass-0 count = OpenWSFZ decodes for that cycle stamp in that run's own ALL.TXT (its own build).
  * Contiguous block = maximal run of stamps exactly 15 s apart within one run and one stratum.

HK-037 / NFR-021: ALL.TXT lines are read ONLY for their first field (the cycle stamp). No message
text is read, kept or printed. The output holds stamps and integers only.

Hash-order guard: every list is sorted at construction, before any RNG use.
"""
import collections
import datetime
import hashlib
import json
import os
import random
import re
import sys

ROOT = r"D:\Projects\claude\OpenWSFZ\worktrees\qa\artefacts"
RUNS = ["20260922_2056", "20260923_1730", "20260925_2010"]
SEED = 20260929
PILOT_PER_RUN = 20
M_PER_RUN = 100
H_MIN = 25
M_MIN, M_MAX = 20, 24
R6_PAIRS = 20
STAMP = re.compile(r"^\d{6}_\d{6}$")

# Constants the spec fixes; asserted so a drift in this script cannot go unnoticed.
assert SEED == 20260929 and PILOT_PER_RUN == 20 and M_PER_RUN == 100 and H_MIN == 25


def counts_for(run):
    path = os.path.join(ROOT, f"{run}_endurance_run-gathered", "owsfz", "ALL.TXT")
    c = collections.Counter()
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            head = line.split(None, 1)
            if head and STAMP.match(head[0]):
                c[head[0]] += 1
    return c


def wav_set(run):
    d = os.path.join(ROOT, f"{run}_endurance_run-gathered", "owsfz", "wav")
    return {n[:-4] for n in os.listdir(d) if n.lower().endswith(".wav")}


def to_dt(stamp):
    return datetime.datetime.strptime(stamp, "%y%m%d_%H%M%S")


def blocks(stamps):
    s = sorted(stamps)
    if not s:
        return 0
    n = 1
    for a, b in zip(s, s[1:]):
        if (to_dt(b) - to_dt(a)).total_seconds() != 15:
            n += 1
    return n


def main():
    out_dir = sys.argv[1]
    os.makedirs(out_dir, exist_ok=True)
    data = {}
    for run in RUNS:
        c = counts_for(run)
        w = wav_set(run)
        pool = sorted(s for s, k in c.items() if k >= 20 and s in w)
        data[run] = {"counts": c, "pool": pool}

    rng = random.Random(SEED)
    sel = {"seed": SEED, "runs": {}, "rule": "see select_81.py header and the Architect's spec"}

    # 1. All pilots first (same stream), run order.
    pilots = {}
    for run in RUNS:
        pilots[run] = sorted(rng.sample(data[run]["pool"], PILOT_PER_RUN))

    # 2. M per run, from the non-pilot 20..24 pool.
    M = {}
    for run in RUNS:
        c = data[run]["counts"]
        mpool = sorted(s for s in data[run]["pool"] if M_MIN <= c[s] <= M_MAX and s not in set(pilots[run]))
        M[run] = sorted(rng.sample(mpool, M_PER_RUN))
        data[run]["m_pool_size"] = len(mpool)

    # 3. H = everything >= 25 not in a pilot.
    H = {}
    for run in RUNS:
        c = data[run]["counts"]
        H[run] = sorted(s for s in data[run]["pool"] if c[s] >= H_MIN and s not in set(pilots[run]))

    # 4. Warm-up: smallest stamp in the pool in none of the strata.
    for run in RUNS:
        used = set(pilots[run]) | set(M[run]) | set(H[run])
        warm = sorted(s for s in data[run]["pool"] if s not in used)[0]
        sel["runs"][run] = {
            "pilot": pilots[run], "M": M[run], "H": H[run], "warmup": warm,
            "pool_ge20": len(data[run]["pool"]), "m_pool_size": data[run]["m_pool_size"],
            "counts_summary": {
                "cycles_with_decodes": len(data[run]["counts"]),
                "pilot_min_max": [min(data[run]["counts"][s] for s in pilots[run]),
                                  max(data[run]["counts"][s] for s in pilots[run])],
                "H_max": max(data[run]["counts"][s] for s in H[run]) if H[run] else None,
            },
            "blocks": {"pilot": blocks(pilots[run]), "M": blocks(M[run]), "H": blocks(H[run])},
        }
    # 5. R6 pairs from the pooled H list, sorted by stamp string.
    pooled_h = sorted(s for run in RUNS for s in H[run])
    origin = {s: run for run in RUNS for s in H[run]}
    sel["R6_pairs"] = [{"a": pooled_h[i], "a_run": origin[pooled_h[i]],
                        "b": pooled_h[i + 1], "b_run": origin[pooled_h[i + 1]]} for i in range(R6_PAIRS)]
    sel["totals"] = {
        "pilot": sum(len(pilots[r]) for r in RUNS),
        "M": sum(len(M[r]) for r in RUNS),
        "H": sum(len(H[r]) for r in RUNS),
        "R6_pairs": R6_PAIRS,
    }
    p = os.path.join(out_dir, "selection.json")
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(sel, fh, indent=1, sort_keys=True)
        fh.write("\n")
    h = hashlib.sha256(open(p, "rb").read()).hexdigest()
    print("selection.json", p)
    print("sha256", h)
    print(json.dumps(sel["totals"]))
    for run in RUNS:
        r = sel["runs"][run]
        print(run, "pool>=20", r["pool_ge20"], "pilot", len(r["pilot"]), "M", len(r["M"]), "H", len(r["H"]),
              "blocks", r["blocks"], "warmup", r["warmup"])


if __name__ == "__main__":
    main()
