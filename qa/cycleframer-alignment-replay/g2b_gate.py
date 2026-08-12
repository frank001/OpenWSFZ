#!/usr/bin/env python3
"""G2(b) passband gate -- the MECHANICAL evaluator for the pre-registration at
qa/cycleframer-alignment-replay/2026-08-12-1600-qa-to-architect-prereg-g2b-passband-decomposed-v2.md

HK-021 requires a pre-registered check to be drafted by writing the code that
evaluates it. This IS that code, and it is written before any ladder rung is run.
It takes replay JSONs produced by g2_verification_replay.py and prints exactly one
ROW per rung. It draws no conclusion the rows do not license.

REVISION 2 (2026-08-12 16:00Z) -- rewritten against the Architect's twelve-finding
review (`2026-08-12-1545-architect-to-qa-g2b-prereg-review-and-fmin-ruling.md`).
Findings A1, A2, A4, A7, A8, A9, A10, A11, A12 are fixed here; A3, A5, A6 are
policy/derivation fixes and are documented in the revised pre-registration, with
the mechanical half of each (the combination-rule flag, the non-circular P1
observation rule, the CLI-supplied non-derived bars) landing in this file too.
A1 was ALSO formally refused under HK-025 before this revision was written -- see
the covering document. This file does not "arm" the refused version; it replaces
it.

  Preconditions (P1 observation rule aside, which now changes the verdict rather
  than merely the printed scope -- see A1) are evaluated FIRST and can each change
  the verdict (HK-021(k)); rows are hard-thresholded, mutually exclusive, and read
  in strict order with an explicit ROW 0 and a reachable ROW 0d that fires for a
  named reason (A10), not as dead code.

Usage:
    python g2b_gate.py --band 20m --f-min 140 --f-max 3030 \
        --baseline base_20m.json --widened wide_20m_f140.json \
        --repeat  base_20m_repeat.json \
        --manifest g2b_dll_manifest.json --held-out-from 20260808_0016_000251Z \
        --is-widest-rung no \
        --g-new-min-rate 0.0100 --churn-net-min-rate -0.0025 \
        --churn-gross-max-rate 0.0200
"""
from __future__ import annotations

import argparse
import json
import random
import sys

# ── Fixed protocol constants. The OLD band is what shipped as G2 item (a)+(b)'s ─
# ── predecessor; NEW_F_MAX is fixed across the whole f_min ladder (pre-reg §4). ─

OLD_F_MIN, OLD_F_MAX = 200, 3000
NEW_F_MAX_DEFAULT = 3030

# A6 fix: an ABSENCE/power check (HK-021(j)) needs >= 5 to be trusted. Previously
# this was a PREDICTED lambda computed from the reference decoder's own decode
# frequency distribution -- which HK-026 rules circular, because that distribution
# cannot see past its own passband. It is now an OBSERVED count from THIS run: no
# decoder output is used to bound a decoder's own blind spot. Run more cycles, or
# declare the high end unadjudicated; do not predict from a contaminated share.
MIN_HIGH_BAND_OBSERVATIONS = 5

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


def in_new_band_low(freq, f_min):
    return f_min <= freq < OLD_F_MIN


def in_new_band_high(freq, f_max):
    return OLD_F_MAX <= freq < f_max


def per_cycle_terms(base, other, f_min, f_max):
    """Per-cycle (g_low, g_high, g_elsewhere, lost, n_base). Cycle is the CLUSTER
    unit (HK-021(i)): decodes within a cycle share one noise realisation and one
    candidate ordering. Bootstrap resamples CYCLES, never decodes.

    A1 fix: low-band and high-band gains are counted SEPARATELY, never pooled at
    this layer. Pooling happens (or does not) only at the row-decision layer,
    and only conditioned on whether the high end is adjudicated (A1/P1 below).
    """
    b, o = phys_by_cycle(base), phys_by_cycle(other)
    shared = sorted(set(b) & set(o))
    rows = []
    for ts in shared:
        gained, lost = o[ts] - b[ts], b[ts] - o[ts]
        g_lo = sum(1 for (f, _) in gained if in_new_band_low(f, f_min))
        g_hi = sum(1 for (f, _) in gained if in_new_band_high(f, f_max))
        g_else = len(gained) - g_lo - g_hi
        rows.append((g_lo, g_hi, g_else, len(lost), len(b[ts])))
    return rows


def rates(rows):
    """Rates dict, all as fractions of baseline decodes (the DE-DUPLICATED
    per-cycle population -- A8 fix: this is now the ONLY denominator anywhere in
    this file; the earlier raw per-file row count is gone)."""
    d = sum(r[4] for r in rows)
    if d == 0:
        return {"g_low": 0.0, "g_high": 0.0, "g_pooled": 0.0,
                "churn_net": 0.0, "churn_gross": 0.0}
    g_lo = sum(r[0] for r in rows)
    g_hi = sum(r[1] for r in rows)
    g_else = sum(r[2] for r in rows)
    lost = sum(r[3] for r in rows)
    return {
        "g_low": g_lo / d,
        "g_high": g_hi / d,
        "g_pooled": (g_lo + g_hi) / d,
        "churn_net": (g_else - lost) / d,
        "churn_gross": (g_else + lost) / d,
    }


def bootstrap_bound(rows, metric_fn, pct):
    """pct=0.05 -> 95% LOWER bound; pct=0.95 -> 95% UPPER bound. Gross churn (A4)
    is a harm metric, so it is bounded above, not below -- everything else in
    this gate is bounded below, as before."""
    rng = random.Random(BOOTSTRAP_SEED)
    n = len(rows)
    vals = []
    for _ in range(BOOTSTRAP_N):
        sample = [rows[rng.randrange(n)] for _ in range(n)]
        vals.append(metric_fn(rates(sample)))
    vals.sort()
    idx = min(max(int(pct * BOOTSTRAP_N), 0), BOOTSTRAP_N - 1)
    return vals[idx]


def load_manifest(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--band", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--widened", required=True)
    ap.add_argument("--repeat", required=True,
                     help="second baseline-binary leg; the P3 determinism control")

    # A2 fix: f_min is a required argument, not a module constant. f_max stays
    # fixed at 3030 across the ladder per pre-reg §4, but is overridable.
    ap.add_argument("--f-min", type=int, required=True,
                     help="this rung's low-end cutoff, e.g. 180 / 140 / 100")
    ap.add_argument("--f-max", type=int, default=NEW_F_MAX_DEFAULT)

    # A3 fix: the combination rule (family closes only if the WIDEST rung reads
    # ROW 3, per the Architect's recommendation, accepted in the revised pre-reg)
    # is pre-registered in prose but only MECHANICAL if the gate knows which
    # invocation is the widest rung. Required, not defaulted, so it cannot be
    # silently forgotten.
    ap.add_argument("--is-widest-rung", required=True, choices=["yes", "no"])

    # A7 fix: nothing previously bound a leg's binary to the rung it claims to
    # be. The manifest is pre-registered (SHA256 -> {f_min, f_max}) BEFORE the
    # run; P2 asserts the widened leg's SHA is in it and matches this invocation.
    ap.add_argument("--manifest", required=True,
                     help="path to a JSON SHA256 -> {f_min, f_max} manifest, "
                          "pre-registered before any rung is built")

    # A11 fix: nothing previously stopped the gate being pointed at the burned
    # 250-cycle 20m leg. Required; the gate refuses to read if any leg's earliest
    # cycle timestamp does not exceed this floor. Lexical compare, matching the
    # UTC-sortable `ts` convention already used by phys_by_cycle's own sort and
    # by every other harness in this directory (measure_drift_8080_session.py,
    # measurement_b_capture_chain.py, measurement_c_realign.py all rely on the
    # same lexical-equals-chronological property of these timestamps).
    ap.add_argument("--held-out-from", required=True,
                     help="ts floor (exclusive) -- every leg's minimum ts must "
                          "exceed this, e.g. the burned leg's last cycle ts")

    # A5 fix: no bar in this file is derived from anything that passes through a
    # decoder. These are supplied by the caller (the pre-registration document),
    # per-rung, as pre-committed round floors with NO claimed derivational
    # authority -- exactly the honest restatement A5 required. See the revised
    # pre-reg for the actual per-rung numbers and how they were chosen.
    ap.add_argument("--g-new-min-rate", type=float, required=True,
                     help="this rung's own pre-committed low-band G_new floor, "
                          "as a fraction of baseline decodes (e.g. 0.0100)")
    ap.add_argument("--churn-net-min-rate", type=float, required=True,
                     help="net churn floor (negative), fraction of baseline "
                          "decodes (e.g. -0.0025)")

    # A4 fix: gross churn is now a co-primary metric with its own bar and its
    # own place in the row logic, not folded into net churn.
    ap.add_argument("--churn-gross-max-rate", type=float, required=True,
                     help="gross churn ceiling, fraction of baseline decodes "
                          "(e.g. 0.0200) -- must be well below the burned leg's "
                          "observed 4.8%%, per the Architect's instruction that "
                          "a bar that number clears comfortably is not a bar")

    args = ap.parse_args()

    base, wide, rep = load(args.baseline), load(args.widened), load(args.repeat)
    print(f"\n{'=' * 78}\nG2(b) GATE -- band {args.band}  f_min={args.f_min} "
          f"f_max={args.f_max}  widest_rung={args.is_widest_rung}\n{'=' * 78}")
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

    cycles_base = set(phys_by_cycle(base))
    cycles_wide = set(phys_by_cycle(wide))
    cycles_rep = set(phys_by_cycle(rep))
    if cycles_base != cycles_wide:
        p2.append("baseline and widened legs cover different cycles")
    # A9 fix: the repeat leg was previously checked only by n_files. Compare its
    # cycle SET too, not just a count that different timestamps can still match.
    if cycles_base != cycles_rep:
        p2.append("baseline and repeat legs cover different cycles")

    # A7: manifest binds the widened leg's SHA to the rung it claims to be.
    manifest = load_manifest(args.manifest)
    entry = manifest.get(wide["dll_sha256"])
    if entry is None:
        p2.append(f"widened leg's SHA {wide['dll_sha256'][:16]}... is not in "
                   f"the pre-registered manifest {args.manifest}")
    elif entry.get("f_min") != args.f_min or entry.get("f_max") != args.f_max:
        p2.append(f"manifest says {wide['dll_sha256'][:16]}... was built for "
                   f"f_min={entry.get('f_min')} f_max={entry.get('f_max')}, "
                   f"not this invocation's f_min={args.f_min} f_max={args.f_max}")

    # A11: no leg may include the burned held-out-from cycle or anything before it.
    all_ts = list(cycles_base) + list(cycles_wide) + list(cycles_rep)
    if all_ts and min(all_ts) <= args.held_out_from:
        p2.append(f"a leg includes cycle(s) at or before the held-out floor "
                  f"{args.held_out_from} (min ts seen: {min(all_ts)}) -- the "
                  f"burned leg must not be read")

    # ── P3 (VALIDITY): is churn identified at all? ───────────────────────────
    rep_rows = per_cycle_terms(base, rep, args.f_min, args.f_max)
    rep_churn_abs = sum(r[2] + r[3] for r in rep_rows)
    p3_fired = rep_churn_abs != 0

    print(f"  P2 legs    {'FAIL: ' + '; '.join(p2) if p2 else 'ok'}")
    print(f"  P3 determinism  baseline-vs-repeat physical differences="
          f"{rep_churn_abs} -> {'FAIL -- churn NOT identified' if p3_fired else 'ok'}")

    if p2 or p3_fired:
        print("\n  ROW 0 -- NO READ. A precondition failed; the quantity is not an "
              "estimate of what this gate names. Do not interpret the numbers below.")
        return 0

    # ── The measurement ──────────────────────────────────────────────────────
    rows = per_cycle_terms(base, wide, args.f_min, args.f_max)
    r = rates(rows)
    d_base = sum(len(v) for v in phys_by_cycle(base).values())  # A8: same
    # denominator as rates(), de-duplicated per-cycle -- not the raw per-file
    # row count the old d_base used.

    g_high_total = sum(row[1] for row in rows)

    # A1/A6 fix: P1 is now an OBSERVED-count check (A6), and it changes WHICH
    # metric decides the row (A1) -- previously it fired into printed text only,
    # which made it diagnostic-only and refusal-grade under HK-025.
    p1_fired = g_high_total < MIN_HIGH_BAND_OBSERVATIONS
    print(f"\n  P1 high-band power  observed high-band gains={g_high_total} "
          f"(need >= {MIN_HIGH_BAND_OBSERVATIONS}) -> "
          f"{'HIGH END UNADJUDICATED -- low-band metric governs the row' if p1_fired else 'both ends adjudicated -- pooled metric governs the row'}")

    print(f"\n  cycles={len(rows)}  baseline decodes (de-duplicated)={d_base}")
    print(f"  intended mechanism   low-band gains  = {sum(x[0] for x in rows)}   "
          f"({r['g_low'] * 100:+.3f}%)")
    print(f"  intended mechanism   high-band gains = {g_high_total}   "
          f"({r['g_high'] * 100:+.3f}%)")
    print(f"  perturbation         gains elsewhere = {sum(x[2] for x in rows)}   "
          f"losses = {sum(x[3] for x in rows)}")
    print(f"  churn (net)   = {r['churn_net'] * 100:+.3f}%")
    print(f"  churn (gross) = {r['churn_gross'] * 100:+.3f}%   "
          f"(gross = |elsewhere| + |lost|; net can hide re-ordering that gross cannot)")

    g_sel_fn = (lambda rr: rr["g_low"]) if p1_fired else (lambda rr: rr["g_pooled"])
    g_sel_val = g_sel_fn(r)
    g_sel_lo = bootstrap_bound(rows, g_sel_fn, 0.05)
    churn_net_lo = bootstrap_bound(rows, lambda rr: rr["churn_net"], 0.05)
    churn_gross_hi = bootstrap_bound(rows, lambda rr: rr["churn_gross"], 0.95)

    sel_label = "G_new (low-band only)" if p1_fired else "G_new (pooled, both ends)"
    print(f"\n  {sel_label} = {g_sel_val * 100:+.3f}%  "
          f"(95% lower {g_sel_lo * 100:+.3f}%, bar {args.g_new_min_rate * 100:+.2f}%)")
    print(f"  churn net  = {r['churn_net'] * 100:+.3f}%  "
          f"(95% lower {churn_net_lo * 100:+.3f}%, "
          f"bar {args.churn_net_min_rate * 100:+.2f}%)")
    print(f"  churn gross = {r['churn_gross'] * 100:+.3f}%  "
          f"(95% upper {churn_gross_hi * 100:+.3f}%, "
          f"bar {args.churn_gross_max_rate * 100:+.2f}%)")

    scope = (" (LOW END ONLY -- P1 fired, the high end is NOT adjudicated; "
             f"licensed consequence is [{args.f_min}, {OLD_F_MAX}) only)"
             if p1_fired else
             f" (both ends adjudicated; licensed consequence is "
             f"[{args.f_min}, {args.f_max}))")

    g_ok = g_sel_lo >= args.g_new_min_rate
    net_ok = churn_net_lo >= args.churn_net_min_rate
    gross_ok = churn_gross_hi <= args.churn_gross_max_rate

    # ── Rows, in strict order, mutually exclusive ────────────────────────────
    # A10 fix: ROW 0d is now reachable for a NAMED reason -- catastrophic gross
    # churn (perturbation) landing together with a mechanism that does not clear
    # its own bar. That combination is worse than a plain "mechanism underdelivers"
    # (ROW 3) and worse than "mechanism confirmed, perturbation real" (ROW 2,
    # which requires the mechanism to have cleared its bar). It gets its own stop.
    if not g_ok and not gross_ok:
        print(f"\n  ROW 0d -- CATCH-ALL, reached for a named reason (A10): the "
              f"mechanism does not clear its own bar AND gross churn is "
              f"catastrophic{scope}. This is worse than 'mechanism underdelivers' "
              f"-- STOP and escalate; do not improvise a reading.")
    elif g_ok and net_ok and gross_ok:
        print(f"\n  ROW 1 -- ELIGIBLE{scope}. The mechanism clears its own "
              "pre-committed floor and both churn metrics are bounded. The "
              "Captain chooses among eligible rungs; this gate does not.")
    elif g_ok and (not net_ok or not gross_ok):
        reason = []
        if not net_ok:
            reason.append("net churn exceeds its floor")
        if not gross_ok:
            reason.append("gross churn exceeds its ceiling")
        print(f"\n  ROW 2 -- MECHANISM CONFIRMED, PERTURBATION REAL "
              f"({'; '.join(reason)}){scope}. Do NOT ship the raw widening. "
              "Escalate decoupling the noise-floor estimate from the passband "
              "as its own change; the widening returns on top of it.")
    elif not g_ok:
        if args.is_widest_rung == "yes":
            print(f"\n  ROW 3 -- the mechanism does not deliver at scale{scope}. "
                  "This IS the widest rung, so per the pre-registered "
                  "combination rule (family closes only if the widest rung "
                  "reads ROW 3): CLOSE the passband family; do not re-propose "
                  "without new evidence.")
        else:
            print(f"\n  ROW 3 -- this rung does not deliver{scope}. This is NOT "
                  "the widest rung, so per the pre-registered combination rule "
                  "this is evidence about THIS rung's width only -- it does "
                  "not close the passband family by itself.")
    else:
        # Structurally unreachable given the branches above are exhaustive over
        # (g_ok, gross_ok) x net_ok; kept as a safety net, same discipline A10
        # applied to the previous unreachable branch -- if this ever prints, that
        # is itself a finding to report, not a row to trust.
        print("\n  ROW 0d -- CATCH-ALL, reached via the UNEXPECTED branch (should "
              "be structurally unreachable). STOP and escalate; report this as a "
              "gate defect, do not improvise a reading.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
