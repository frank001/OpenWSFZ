#!/usr/bin/env python3
"""
C.5c -- candidate rank-conversion, from RC1's retained _work/ artefacts.

Question: do the candidates at the BOTTOM of the ranked pass-0 list convert into
decodes at all?  If they convert at ~0%, then RC3 (widening the search band)
displaces nothing that was working, and its cap-interaction objection retires.

Read-only.  No src/ change, no capture, no replay.  Reads only frequency, timing
and score columns -- message text is never loaded, printed, or written (NFR-021).

Inputs (git-ignored, produced by RC1's replay):
  <rc1>/_work/run{1,2,3}/candidate_lists.json   {cycle_hhmmss: {pass: [[t_off, f_off, score], ...]}}
  <rc1>/_work/run{1,2,3}/our_rows_p1.json       [{ts, snr, dt, freq_hz, message}, ...]

Units, per RC1's own stated derivation (f_min=200, sample_rate=12000, time_osr=2,
freq_osr=2 are compile-time constants):
    symbol_period = 0.160 s ; min_bin = 32
    freq_hz = (min_bin + freq_offset) / symbol_period   [= (32 + f_off) * 6.25]
    dt_s    = time_offset * symbol_period
The omitted sub-bin/sub-block terms add +-1.5625 Hz / +-0.04 s beyond the
pre-registered tolerance; reported separately, never folded in.
"""

import json
import os
import sys
from collections import defaultdict

SYMBOL_PERIOD = 0.160
MIN_BIN = 32
FREQ_TOL_HZ = 6.25   # RC1's pre-registered tolerance
DT_TOL_S = 0.5
N_DECILES = 10

# ROW 0 guards -- an instrument that cannot fire must say so, not return a null.
MIN_BOTTOM_DECILE_N = 500
MIN_MATCH_COVERAGE = 0.80
# Added after the first run: the two attribution policies diverged by 36 pp at D10
# and INVERTED at D1 (0.36% vs 83.69%), which means the tie-break -- not the data --
# was setting the answer. A gate whose verdict flips with a modelling choice inside
# its own metric is not mechanical (HK-021). See ATTRIBUTION note below.
MAX_POLICY_DIVERGENCE_TOP = 0.10   # D1 rate must agree within 10 pp, else no verdict

# ── ATTRIBUTION: which candidate is credited with a decode? ──────────────────
# Verified in src/OpenWSFZ.Ft8/Native/ft8_shim.c on 2026-08-07, not assumed:
#   * :1354  `for (int ci = 0; ci < ncands; ++ci)` iterates the array exactly as
#            ftx_find_candidates() returned it -- descending sync score.
#   * :1387  cross-pass dedup is by MESSAGE HASH: the first candidate to decode a
#            message commits it; any later candidate producing the same message is
#            dropped before it can be recorded.
# The highest-ranked policy therefore models the decoder BETTER than the lowest-ranked
# one -- but not well enough to gate on, and the difference matters:
#
#   The "first matching candidate wins" model holds only if that candidate actually
#   DECODES. RC1's whole result is that ~90% of candidates fail LDPC/OSD. So inside a
#   cluster of ~4 candidates around one signal, ranks 3/40/90 may all fail and rank 130
#   succeed -- and the highest-ranked policy would then credit rank 3 for a decode it
#   never produced. Under exactly the failure regime RC1 measured, the model breaks.
#
# CONCLUSION: candidate_lists.json records which candidates EXISTED, not which one
# DECODED. No attribution recoverable from frequency and timing alone can close that
# gap, and the median-4 candidate multiplicity below makes the ambiguity structural
# rather than marginal. Answering C.5c needs a per-decode originating-candidate index
# -- a src/ change, not a re-analysis. Both policies are reported as bounds; the gate
# returns ROW 0 by design.
#
# Recorded for the record: the Architect predicted ROW 1 ("displacement is free") in
# advance and in writing, in the 2117 spec section 4.3. This measurement did not
# deliver it, and the prediction remains untested rather than confirmed.

def load_run(run_dir):
    with open(os.path.join(run_dir, "candidate_lists.json")) as fh:
        cand = json.load(fh)
    with open(os.path.join(run_dir, "our_rows_p1.json")) as fh:
        rows = json.load(fh)
    return cand, rows


def cycle_key(ts):
    """'260807_183930' -> '18:39:30' to match candidate_lists.json's keys."""
    hms = ts.split("_")[1]
    return "%s:%s:%s" % (hms[0:2], hms[2:4], hms[4:6])


def analyse(run_dirs):
    # rank -> [n_candidates, n_converted] under each assignment policy
    tot = defaultdict(int)
    conv_worst = defaultdict(int)   # decode -> LOWEST-ranked matching candidate
    conv_best = defaultdict(int)    # decode -> HIGHEST-ranked matching candidate
    sorted_violations = 0
    n_cand_total = 0
    our_total = 0
    our_matched = 0
    cycles_used = 0
    cand_dt = []
    our_dt = []
    multiplicity = []

    for run_dir in run_dirs:
        cand, rows = load_run(run_dir)

        by_cycle = defaultdict(list)
        for r in rows:
            by_cycle[cycle_key(r["ts"])].append((r["freq_hz"], r["dt"]))
            our_dt.append(r["dt"])
        our_total += len(rows)

        for cyc, passes in cand.items():
            p0 = passes.get("0")
            if not p0:
                continue
            cycles_used += 1

            scores = [c[2] for c in p0]
            if any(scores[i] < scores[i + 1] for i in range(len(scores) - 1)):
                sorted_violations += 1

            cands = []
            for rank, (t_off, f_off, score) in enumerate(p0):
                f_hz = (MIN_BIN + f_off) / SYMBOL_PERIOD
                dt_s = t_off * SYMBOL_PERIOD
                cands.append((rank, f_hz, dt_s))
                cand_dt.append(dt_s)
                tot[rank] += 1
            n_cand_total += len(cands)

            taken_worst = set()
            taken_best = set()
            for (f_hz, dt) in by_cycle.get(cyc, []):
                hits = [rk for (rk, cf, cdt) in cands
                        if abs(cf - f_hz) <= FREQ_TOL_HZ and abs(cdt - dt) <= DT_TOL_S]
                if not hits:
                    continue
                our_matched += 1
                multiplicity.append(len(hits))
                # Two bounds, neither authoritative -- see ATTRIBUTION above.
                for rk in sorted(hits, reverse=True):
                    if rk not in taken_worst:
                        taken_worst.add(rk)
                        conv_worst[rk] += 1
                        break
                for rk in sorted(hits):
                    if rk not in taken_best:
                        taken_best.add(rk)
                        conv_best[rk] += 1
                        break

    return dict(tot=tot, conv_worst=conv_worst, conv_best=conv_best,
                sorted_violations=sorted_violations, n_cand_total=n_cand_total,
                our_total=our_total, our_matched=our_matched,
                cycles_used=cycles_used, cand_dt=cand_dt, our_dt=our_dt,
                multiplicity=multiplicity)


def deciles(tot, conv, max_rank):
    """Deciles of the 0..max_rank lattice -- populated by construction."""
    width = (max_rank + 1) / float(N_DECILES)
    out = []
    for d in range(N_DECILES):
        lo = int(round(d * width))
        hi = int(round((d + 1) * width)) - 1
        n = sum(tot[r] for r in range(lo, hi + 1))
        c = sum(conv[r] for r in range(lo, hi + 1))
        out.append((d + 1, lo, hi, n, c, (c / float(n) if n else float("nan"))))
    return out


def c5c_row(c_bottom, n_bottom, coverage, top_divergence):
    """Pre-registered gate. Strict order; boundaries fall to ROW 3."""
    if n_bottom < MIN_BOTTOM_DECILE_N or coverage < MIN_MATCH_COVERAGE:
        return "ROW 0"
    if top_divergence > MAX_POLICY_DIVERGENCE_TOP:
        return "ROW 0"
    if c_bottom < 0.01:
        return "ROW 1"
    if c_bottom > 0.05:
        return "ROW 2"
    return "ROW 3"


def main():
    base = sys.argv[1]
    run_dirs = [os.path.join(base, "run%d" % i) for i in (1, 2, 3)]
    missing = [d for d in run_dirs if not os.path.isdir(d)]
    if missing:
        sys.exit("missing run dirs: %s" % missing)

    r = analyse(run_dirs)
    max_rank = max(r["tot"]) if r["tot"] else 0
    coverage = r["our_matched"] / float(r["our_total"]) if r["our_total"] else 0.0

    print("C.5c -- candidate rank-conversion (pass 0), pooled over 3 runs")
    print("=" * 72)
    print("cycles pooled            : %d" % r["cycles_used"])
    print("pass-0 candidates        : %d" % r["n_cand_total"])
    print("max rank index           : %d" % max_rank)
    print("our decodes (all)        : %d" % r["our_total"])
    print("  attributed to a cand.  : %d  (coverage %.3f)" % (r["our_matched"], coverage))
    print("descending-sort violations: %d cycles" % r["sorted_violations"])
    print("cand dt_s  range         : %.2f .. %.2f" % (min(r["cand_dt"]), max(r["cand_dt"])))
    print("our  dt    range         : %.2f .. %.2f" % (min(r["our_dt"]), max(r["our_dt"])))
    print()

    mult = r["multiplicity"]
    mult_sorted = sorted(mult)
    print("candidates matching one decode (the ambiguity this measurement lives with):")
    print("  median %d   mean %.2f   p90 %d   max %d"
          % (mult_sorted[len(mult_sorted) // 2], sum(mult) / float(len(mult)),
             mult_sorted[int(0.9 * len(mult))], max(mult)))
    print()

    for label, conv in (("PRIMARY  (decode -> HIGHEST-ranked match; models the decoder)", r["conv_best"]),
                        ("BOUND    (decode -> LOWEST-ranked match; models nothing)", r["conv_worst"])):
        print(label)
        print("  decile  ranks      n      converted   rate")
        rows = deciles(r["tot"], conv, max_rank)
        for (d, lo, hi, n, c, rate) in rows:
            print("    D%-2d   %3d-%-3d  %6d   %7d   %6.3f%%" % (d, lo, hi, n, c, rate * 100))
        print()

    prim = deciles(r["tot"], r["conv_best"], max_rank)
    bound = deciles(r["tot"], r["conv_worst"], max_rank)
    _, _, _, n_bottom, c_bottom_n, c_bottom = prim[-1]
    top_div = abs(prim[0][5] - bound[0][5])
    row = c5c_row(c_bottom, n_bottom, coverage, top_div)

    print("=" * 72)
    print("c_bottom (D10, primary)  : %.5f  (%d / %d)" % (c_bottom, c_bottom_n, n_bottom))
    print("n_bottom                 : %d  (floor %d)" % (n_bottom, MIN_BOTTOM_DECILE_N))
    print("coverage                 : %.3f  (floor %.2f)" % (coverage, MIN_MATCH_COVERAGE))
    print("D1 policy divergence     : %.3f  (ceiling %.2f)" % (top_div, MAX_POLICY_DIVERGENCE_TOP))
    print("c5c_row                  : %s" % row)

    out = dict(
        cycles=r["cycles_used"], candidates=r["n_cand_total"], max_rank=max_rank,
        our_decodes=r["our_total"], attributed=r["our_matched"], coverage=coverage,
        sort_violations=r["sorted_violations"],
        primary_policy="highest-ranked match (models decoder: shim.c:1354 order + :1387 hash dedup)",
        primary_deciles=[dict(decile=d, rank_lo=lo, rank_hi=hi, n=n, converted=c, rate=rate)
                         for (d, lo, hi, n, c, rate) in prim],
        bound_deciles=[dict(decile=d, rank_lo=lo, rank_hi=hi, n=n, converted=c, rate=rate)
                       for (d, lo, hi, n, c, rate) in bound],
        d1_policy_divergence=top_div,
        c_bottom=c_bottom, n_bottom=n_bottom, c5c_row=row,
        tolerance=dict(freq_hz=FREQ_TOL_HZ, dt_s=DT_TOL_S,
                       subbin_residual_hz=1.5625, subblock_residual_s=0.04),
    )
    dest = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "c5c_rank_conversion_result.json")
    with open(dest, "w") as fh:
        json.dump(out, fh, indent=2)
    print("wrote %s" % dest)


if __name__ == "__main__":
    main()
