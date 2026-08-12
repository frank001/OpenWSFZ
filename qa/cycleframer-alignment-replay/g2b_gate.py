#!/usr/bin/env python3
"""G2(b) passband gate -- the MECHANICAL evaluator for the pre-registration at
qa/cycleframer-alignment-replay/2026-08-12-1524-qa-to-architect-prereg-g2b-passband-decomposed.md

HK-021 requires a pre-registered check to be drafted by writing the code that
evaluates it. This IS that code, and it was written before the held-out legs were
run. It takes replay JSONs produced by g2_verification_replay.py and prints exactly
one ROW. It draws no conclusion the rows do not license.

  Preconditions P1/P2/P3 are evaluated FIRST and can each change the verdict
  (HK-021(k)); rows are hard-thresholded, mutually exclusive, and read in strict
  order with an explicit ROW 0 and a pre-committed catch-all ROW 0d.

Usage:
    python g2b_gate.py --band 20m \
        --baseline base_20m.json --widened wide_20m.json \
        --repeat  base_20m_repeat.json \
        --ref-share-low 0.0078 --ref-share-high 0.00028
"""
from __future__ import annotations

import argparse
import json
import random
import sys

# ── Pre-registered constants. Set 2026-08-12, BEFORE any held-out leg was run. ──

OLD_F_MIN, OLD_F_MAX = 200, 3000
NEW_F_MIN, NEW_F_MAX = 140, 3030

# ROW 1/2 bar on the intended mechanism, as a rate of baseline decodes.
# ANCHORED TO THE DERIVATION, NOT TO THE BURNED 20m-250 SAMPLE: the pooled
# reference distribution puts 0.78% of decodes in [140, 200). A widening that
# recovers less than the share its own derivation predicts has not delivered its
# own mechanism. The bar is that derived 0.78% plus margin, at a round 1.00%.
G_NEW_MIN_RATE = 0.0100          # +1.00% of baseline decodes, 95% LOWER bound

# ROW 1/2 bar on in-band churn, as a signed rate of baseline decodes.
# ANCHOR: churn may not consume more than one quarter of the mechanism's own
# predicted yield (0.78% / 4 = 0.195%), rounded to 0.20%.
CHURN_MIN_RATE = -0.0020         # -0.20% of baseline decodes, 95% LOWER bound

# P1: an ABSENCE check needs lambda >= 5 (HK-021(j)).
LAMBDA_MIN = 5.0

BOOTSTRAP_N = 10000
BOOTSTRAP_SEED = 20260812


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def phys_by_cycle(leg):
    """{ts: set((f, dt))} -- physical identity, the correct key for recall.

    Sorted at construction. Set iteration order is hash-randomised per process,
    so any downstream seeded resampling over an unsorted set silently differs
    run to run despite a fixed seed (the p23_common/load_ref defect class).
    """
    out = {}
    for f in leg["per_file"]:
        out.setdefault(f["ts"], set())
        for d in f["decodes"]:
            out[f["ts"]].add((d["f"], round(d["dt"], 2)))
    return {ts: out[ts] for ts in sorted(out)}


def in_new_band(freq):
    return (NEW_F_MIN <= freq < OLD_F_MIN) or (OLD_F_MAX <= freq < NEW_F_MAX)


def per_cycle_terms(base, wide):
    """Per-cycle (g_new, g_elsewhere, lost, n_base). Cycle is the CLUSTER unit.

    HK-021(i): the unit of OBSERVATION is a decode; the unit of INDEPENDENCE is a
    cycle -- decodes within a cycle share one noise realisation and one candidate
    ordering. Bootstrap resamples CYCLES, never decodes.
    """
    b, w = phys_by_cycle(base), phys_by_cycle(wide)
    shared = sorted(set(b) & set(w))
    rows = []
    for ts in shared:
        gained, lost = w[ts] - b[ts], b[ts] - w[ts]
        g_new = sum(1 for (f, _) in gained if in_new_band(f))
        rows.append((g_new, len(gained) - g_new, len(lost), len(b[ts])))
    return rows


def rates(rows):
    """(g_new_rate, churn_rate) over a set of cycles."""
    d = sum(r[3] for r in rows)
    if d == 0:
        return 0.0, 0.0
    g_new = sum(r[0] for r in rows)
    churn = sum(r[1] for r in rows) - sum(r[2] for r in rows)
    return g_new / d, churn / d


def bootstrap_lower95(rows, fn):
    rng = random.Random(BOOTSTRAP_SEED)
    n = len(rows)
    vals = []
    for _ in range(BOOTSTRAP_N):
        sample = [rows[rng.randrange(n)] for _ in range(n)]
        vals.append(fn(sample))
    vals.sort()
    return vals[int(0.05 * BOOTSTRAP_N)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--band", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--widened", required=True)
    ap.add_argument("--repeat", required=True,
                    help="second baseline-binary leg; the P3 determinism control")
    ap.add_argument("--ref-share-low", type=float, required=True,
                    help="share of THIS band's reference decodes in [140,200)")
    ap.add_argument("--ref-share-high", type=float, required=True,
                    help="share of THIS band's reference decodes in [3000,3030)")
    args = ap.parse_args()

    base, wide, rep = load(args.baseline), load(args.widened), load(args.repeat)
    print(f"\n{'=' * 78}\nG2(b) GATE -- band {args.band}\n{'=' * 78}")
    for leg in (base, wide, rep):
        print(f"  {leg['label']:12s} sha={leg['dll_sha256'][:16]}... "
              f"shim={leg['shim_version']} files={leg['n_files']}")

    # ── P2 (VALIDITY): are these the legs the gate names? ────────────────────
    p2 = []
    if base["dll_sha256"] == wide["dll_sha256"]:
        p2.append("baseline and widened are the SAME binary")
    if base["dll_sha256"] != rep["dll_sha256"]:
        p2.append("repeat leg is not the baseline binary")
    if not (base["n_files"] == wide["n_files"] == rep["n_files"]):
        p2.append("legs cover different file counts")
    if set(phys_by_cycle(base)) != set(phys_by_cycle(wide)):
        p2.append("legs cover different cycles")

    # ── P3 (VALIDITY): is churn identified at all? ───────────────────────────
    rep_rows = per_cycle_terms(base, rep)
    rep_churn_abs = sum(r[1] + r[2] for r in rep_rows)
    p3_fired = rep_churn_abs != 0

    # ── P1 (VALIDITY): is the HIGH-END absence question powered? ─────────────
    d_base = sum(len(f["decodes"]) for f in base["per_file"])
    lam_high = d_base * args.ref_share_high
    lam_low = d_base * args.ref_share_low
    p1_fired = lam_high < LAMBDA_MIN

    print(f"\n  P1 power   lambda_low={lam_low:.1f}  lambda_high={lam_high:.1f} "
          f"(need >= {LAMBDA_MIN}) -> "
          f"{'HIGH END UNDERPOWERED' if p1_fired else 'both ends powered'}")
    print(f"  P2 legs    {'FAIL: ' + '; '.join(p2) if p2 else 'ok'}")
    print(f"  P3 determinism  baseline-vs-repeat physical differences="
          f"{rep_churn_abs} -> {'FAIL -- churn NOT identified' if p3_fired else 'ok'}")

    if p2 or p3_fired:
        print("\n  ROW 0 -- NO READ. A precondition failed; the quantity is not an "
              "estimate of what this gate names. Do not interpret the numbers below.")
        return 0

    # ── The measurement ──────────────────────────────────────────────────────
    rows = per_cycle_terms(base, wide)
    g_rate, c_rate = rates(rows)
    g_lo = bootstrap_lower95(rows, lambda s: rates(s)[0])
    c_lo = bootstrap_lower95(rows, lambda s: rates(s)[1])

    g_new = sum(r[0] for r in rows)
    g_else = sum(r[1] for r in rows)
    lost = sum(r[2] for r in rows)
    print(f"\n  cycles={len(rows)}  baseline decodes={d_base}")
    print(f"  intended mechanism  gains in newly-opened spectrum = {g_new}")
    print(f"  perturbation        gains elsewhere = {g_else}   losses = {lost}")
    print(f"  net = {g_new + g_else - lost:+d}   "
          f"({'churn accounts for ' + format(g_else - lost, '+d')})")
    print(f"\n  G_new  = {g_rate * 100:+.3f}%  (95% lower {g_lo * 100:+.3f}%, "
          f"bar {G_NEW_MIN_RATE * 100:+.2f}%)")
    print(f"  churn  = {c_rate * 100:+.3f}%  (95% lower {c_lo * 100:+.3f}%, "
          f"bar {CHURN_MIN_RATE * 100:+.2f}%)")

    # ── Rows, in strict order, mutually exclusive ────────────────────────────
    scope = " (LOW END ONLY -- P1 fired, the high end is NOT adjudicated)" if p1_fired else ""
    if g_lo >= G_NEW_MIN_RATE and c_lo >= CHURN_MIN_RATE:
        print(f"\n  ROW 1 -- SHIP the widening{scope}. The mechanism clears its own "
              "derived yield and churn is bounded.")
    elif g_lo >= G_NEW_MIN_RATE and c_lo < CHURN_MIN_RATE:
        print(f"\n  ROW 2 -- MECHANISM CONFIRMED, PERTURBATION REAL{scope}. Do NOT ship "
              "the raw widening. Escalate decoupling the noise-floor estimate from "
              "the passband as its own change; the widening returns on top of it.")
    elif g_lo < G_NEW_MIN_RATE:
        print(f"\n  ROW 3 -- the mechanism does not deliver at scale{scope}. CLOSE the "
              "passband family; do not re-propose without new evidence.")
    else:
        print("\n  ROW 0d -- CATCH-ALL. The result did not fall in any anticipated row. "
              "STOP and escalate; do not improvise a reading.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
