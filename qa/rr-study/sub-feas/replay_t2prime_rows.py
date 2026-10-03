#!/usr/bin/env python
"""SUB-FEAS Stage B (Amendment 5): the T2' predicate, as code. Pre-registered, committed BEFORE the first Stage B measurement.

    T2_replay = DECODE_START_S + time-to-batch-1 + residual-pass elapsedMs          (per cycle)
    population = every cycle whose residual pass was deadline-ABANDONED, counted as T2 = +infinity
               + every cycle with >= 1 residual decode that completed, counted at its finite T2
               (a cycle that COMPLETED with 0 residual decodes is OUT: nothing to answer;
                a cycle whose pass did not run at all is OUT too)
    PASS  iff  median(population) <= T2_BAR_S   (equal passes)         UNDEFINED if the population is empty

The +infinity rule is the Architect's (spec section 5h, commit 4301e8c5, QA (k) review note (b)); it removes the survivorship bias of
medianing only the cycles that finished. More than half the population abandoned makes the median +infinity, a FAIL.
HK-037: stamps, integers and timings only; no message text is read. The inputs are the replay81 'two1' CSV, the harness's
--abandon-out file and the 'Sub-feas residual pass:' log lines (the same grammar replay_speed_rows.py reads).

    python replay_t2prime_rows.py --csv time_X.csv --log time_X.log --abandon abandon_X.csv [--label NAME] [--json out.json]
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import math
import os
import sys
from dataclasses import dataclass

# ---- constants from the spec: asserted here, not carried in prose -------------------------------------------------------------
DECODE_START_S = 0.032          # the on-air median decode-start offset, a LABELLED CONSTANT (not measured in a replay)
T2_BAR_S = 2.50                 # T2': median T2_replay <= 2.50 s
SAME_SLOT_S = 2.95              # lateness ruling: same-slot condition median T2 <= 2.95 s - k
KEYING_MARGIN_S = 0.45          # the margin T2' leaves for the unmeasured keying latency k and replay-vs-live
SELECTION_SHA256 = "55a951c86147e92a8262be9d84ffd29362ecd7b63995f62caa7981bd53c977cf"   # LF-normalised bytes, as onoff_replay_run.py:52
LIST_STRIDE = 4                 # every fourth cycle of the frozen 10-01 selection (index = 0 mod 4)
assert abs((SAME_SLOT_S - T2_BAR_S) - KEYING_MARGIN_S) < 1e-9, "the margin must equal 2.95 - 2.50"
PASS, FAIL, UNDEFINED = "PASS", "FAIL", "UNDEFINED"


@dataclass(frozen=True)
class Cycle:
    stamp: str                       # YYMMDD_HHMMSS
    ran: bool                        # the residual pass ran for this cycle
    abandoned: bool                  # ... and was deadline-abandoned
    tb1_ms: float | None             # time to batch 1 (two1 CSV)
    residual_decodes: int | None     # residualDecodes from the Sub-feas line
    elapsed_ms: float | None         # residual pass elapsedMs from the Sub-feas line


def t2_of(c: Cycle):
    """T2 in seconds: +inf (abandoned), a finite value (completed with >= 1 residual decode), or None (out of the population)."""
    if not c.ran:
        return None
    if c.abandoned:
        return math.inf
    if c.residual_decodes is None or c.residual_decodes < 1:
        return None
    if c.tb1_ms is None or c.elapsed_ms is None:
        raise ValueError(f"cycle {c.stamp}: a completed residual pass without tb1_ms/elapsed_ms cannot be timed")
    return DECODE_START_S + c.tb1_ms / 1000.0 + c.elapsed_ms / 1000.0


def median(values):
    """Median with +inf allowed: the mean of two middle values is +inf if either is (never inf - inf: no subtraction)."""
    s = sorted(values)
    n = len(s)
    if n == 0:
        return None
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def pct(values, p):
    s = sorted(values)
    if not s:
        return None
    return s[max(0, min(len(s) - 1, math.ceil(p * len(s)) - 1))]


def evaluate(cycles: list[Cycle]) -> dict:
    ran = [c for c in cycles if c.ran]
    t2 = [(c, t2_of(c)) for c in cycles]
    pop = [t for _, t in t2 if t is not None]
    finite = [t for t in pop if math.isfinite(t)]
    n_abandoned = sum(1 for c in ran if c.abandoned)
    n_zero = sum(1 for c in ran if not c.abandoned and (c.residual_decodes is None or c.residual_decodes < 1))
    med = median(pop)
    # Inputs are whole milliseconds, so rounding to microseconds is exact; it stops float noise (2.5000000000000004) failing an exact 2.50 s.
    verdict = UNDEFINED if med is None else (PASS if round(med, 6) <= T2_BAR_S else FAIL)
    by_hour = collections.defaultdict(lambda: [0, 0])          # UTC hour -> [cycles in population, cycles with T2 <= SAME_SLOT_S]
    for c, t in t2:
        if t is None:
            continue
        h = c.stamp[7:9]
        by_hour[h][0] += 1
        by_hour[h][1] += 1 if t <= SAME_SLOT_S else 0
    return {
        "verdict": verdict,
        "median_t2_s": (None if med is None else ("inf" if math.isinf(med) else round(med, 3))),
        "bar_s": T2_BAR_S,
        "population": len(pop), "finite": len(finite), "abandoned_inf": n_abandoned,
        "completed_zero_residual_excluded": n_zero, "pass_did_not_run_excluded": len(cycles) - len(ran),
        "abandon_fraction": (n_abandoned / len(ran)) if ran else None,
        "abandon_fraction_denominator": "cycles whose residual pass ran",
        "p5_s": None if not finite else round(pct(finite, 0.05), 3),
        "p95_s": None if not finite else round(pct(finite, 0.95), 3),
        "max_finite_s": None if not finite else round(max(finite), 3),
        "fraction_t2_le_2p95_overall": (sum(1 for t in pop if t <= SAME_SLOT_S) / len(pop)) if pop else None,
        "by_utc_hour_le_2p95": {h: {"n": v[0], "le_2p95": v[1]} for h, v in sorted(by_hour.items())},
        "reading_the_bar": ("a PASS is not by itself 'same-slot answerable': the acceptance ruling reads 2.95 s - k_PC; "
                            f"if k_PC > {KEYING_MARGIN_S} s, T2' can pass while that fails"),
    }


# ---- loading (thin; reuses replay81_rows.py's grammar) -------------------------------------------------------------------------
def load_cycles(csv_path: str, log_path: str, abandon_path: str) -> list[Cycle]:
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, here)
    import replay81_rows as B                                   # read_rows, parse_log (same log grammar)
    rows = [r for r in B.read_rows(csv_path) if r["flag"] == "ON"]
    rows.sort(key=lambda r: r["seq"])
    sub, _av, _cw, _other = B.parse_log(log_path)
    if len(sub) != len(rows):
        raise ValueError(f"{len(sub)} Sub-feas lines for {len(rows)} ON rows: the i-th line belongs to the i-th row, so a count mismatch voids the join")
    ab = {}
    with open(abandon_path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            ab[r["stamp"]] = (r["ran"] == "1", r["abandoned"] == "1")
    cycles = []
    for r, s in zip(rows, sub):
        ran, abandoned = ab.get(r["stamp"], (False, False))
        cycles.append(Cycle(stamp=r["stamp"], ran=ran, abandoned=abandoned, tb1_ms=float(r["tb1_ms"]),
                            residual_decodes=s["residual"], elapsed_ms=float(s["elapsed_ms"])))
    return cycles


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--csv", required=True)
    ap.add_argument("--log", required=True)
    ap.add_argument("--abandon", required=True)
    ap.add_argument("--label", default="")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    res = evaluate(load_cycles(a.csv, a.log, a.abandon))
    res["label"] = a.label
    res["constants"] = {"DECODE_START_S": DECODE_START_S, "T2_BAR_S": T2_BAR_S, "SAME_SLOT_S": SAME_SLOT_S,
                        "KEYING_MARGIN_S": KEYING_MARGIN_S, "selection_sha256": SELECTION_SHA256, "stride": LIST_STRIDE}
    text = json.dumps(res, indent=1, sort_keys=True)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            fh.write(text)
    print(text)
    return 0 if res["verdict"] == PASS else 1


if __name__ == "__main__":
    sys.exit(main())
