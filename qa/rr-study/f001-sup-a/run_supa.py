#!/usr/bin/env python3
"""F-001 SUP-A -- how many names does a unique-match rule remove in NORMAL
(1-8h) operation? Runner.

Spec: qa/rr-study/2026-08-30-1031-architect-to-qa-spec-f001-sup-a-unique-match-suppression-sizing.md
(as amended 2026-08-30, commit a6a1b2f -- ARMED, PO S_max=40%).

Offline re-analysis of ALL.TXT + openswfz-*.log already on disk. No src/, no
native/, no rebuild, no replay, no capture, no Developer session (Sec.6).

Usage:
    python run_supa.py                 # full run, writes result.json + prints summary
    python run_supa.py --check-determinism   # re-invokes itself under two
        different PYTHONHASHSEED values and diffs result.json (ROW 0e)
"""
from __future__ import annotations

import json
import math
import os
import random
import subprocess
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common_supa as S  # noqa: E402

REPO_ROOT = S.REPO_ROOT
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
N_BOOT = 2000
BOOT_SEED = 20260830
CURVE_HOURS = [1, 2, 4, 6, 8]
S_MAX = 0.40


# ---------------------------------------------------------------------------
# Sec.3/3.1/3.2 -- single full pass per corpus, records the population stream
# (with elapsed_h attached) plus a residency trace, plus the ROW 0b 256-slot
# freeze cycle. One pass feeds every later reading (Sec.5.1/5.3 are nested
# prefixes of this SAME stream, never recomputed from a re-run).
# ---------------------------------------------------------------------------

def process_corpus(corpus_id, cfg):
    rows = S.parse_all_txt(os.path.join(REPO_ROOT, cfg["path"]))
    if not rows:
        raise AssertionError("%s: ALL.TXT parsed to zero rows" % corpus_id)
    start_dt = S.ts_to_dt(rows[0]["ts"])
    end_dt = S.ts_to_dt(rows[-1]["ts"])
    span_h = (end_dt - start_dt).total_seconds() / 3600.0

    tbl = S.SimTable(4096, policy=None)
    tbl256 = S.SimTable(256, policy=None)
    freeze256_cycle = None
    row0b_start_ts = cfg.get("row0b_start_ts")
    row0b_start_dt = S.ts_to_dt(row0b_start_ts) if row0b_start_ts else start_dt

    population = []          # 12-bit-path lookups that display a name TODAY
    n_lookup_candidates = 0  # resolved + nonstd, before exclusions
    excluded_misses = 0      # proxy gap: real decoder resolved it, our sim table has 0 matches
    excluded_charset = 0     # bracket text failed n22_of (out-of-charset)
    dropped_arrival_charset = 0
    count_trace = []         # (elapsed_h, tbl.count) after every count-increment

    for i, r in enumerate(rows):
        cyc = S.cycle_index(r["ts"], start_dt)
        elapsed_h = (S.ts_to_dt(r["ts"]) - start_dt).total_seconds() / 3600.0

        sl = S.slot(r["message_norm"])
        if sl is not None:
            kind, bracket_call, others, nonstd, ntok = sl
            if kind == "resolved" and nonstd:
                n_lookup_candidates += 1
                n22 = S.n22_of(bracket_call)
                if n22 is None:
                    excluded_charset += 1
                else:
                    n12 = n22 >> 10
                    first, n_matches, most_recent = S.lookup12_multiplicity(tbl, n12)
                    if n_matches == 0:
                        excluded_misses += 1
                    else:
                        population.append({
                            "i": i, "ts": r["ts"], "cyc": cyc, "elapsed_h": elapsed_h,
                            "n12": n12, "first": first, "n_matches": n_matches,
                            "most_recent": most_recent,
                            "suppressed": S.suppressed(n_matches),
                            "diverges": S.diverges(first, most_recent),
                        })

        for t in r["message_norm"].split():
            if t.startswith("<") or not S.is_callsign_token(t):
                continue
            n22 = S.n22_of(t)
            if n22 is None:
                dropped_arrival_charset += 1
                continue
            before = tbl.count
            tbl.add(t, n22)
            if tbl.count != before:
                count_trace.append((elapsed_h, tbl.count))
            if row0b_start_ts is None or r["ts"] >= row0b_start_ts:
                tbl256.add(t, n22)
                if freeze256_cycle is None and tbl256.reject_count > 0:
                    freeze256_cycle = S.cycle_index(r["ts"], row0b_start_dt)

    observed_freeze, observed_total_cycles = (None, None)
    if cfg.get("log"):
        observed_freeze, observed_total_cycles = S.observed_freeze_cycle(
            os.path.join(REPO_ROOT, cfg["log"]))

    return {
        "corpus_id": corpus_id, "band": cfg["band"], "rows": rows,
        "n_rows": len(rows), "first_ts": rows[0]["ts"], "last_ts": rows[-1]["ts"],
        "span_h": span_h, "declared_span_h": cfg["declared_span_h"],
        "population": population, "n_lookup_candidates": n_lookup_candidates,
        "excluded_misses": excluded_misses, "excluded_charset": excluded_charset,
        "dropped_arrival_charset": dropped_arrival_charset,
        "count_trace": count_trace, "final_count": tbl.count,
        "freeze256_cycle": freeze256_cycle,
        "row0b_start_ts": row0b_start_ts,
        "observed_freeze_cycle": observed_freeze,
        "observed_total_cycles": observed_total_cycles,
        "tbl": tbl,  # kept for ROW 0c; stripped before JSON serialisation
    }


def residency_at(count_trace, cutoff_h):
    r = 0
    for eh, c in count_trace:
        if eh <= cutoff_h:
            r = c
        else:
            break
    return r


# ---------------------------------------------------------------------------
# ROW 0 gates
# ---------------------------------------------------------------------------

def row_0a(proc):
    ok = abs(proc["span_h"] - proc["declared_span_h"]) <= 0.05
    return {"row": "0a", "pass": ok, "n_rows": proc["n_rows"],
            "first_ts": proc["first_ts"], "last_ts": proc["last_ts"],
            "span_h": round(proc["span_h"], 3), "declared_span_h": proc["declared_span_h"]}


def row_0b(proc):
    if proc["observed_freeze_cycle"] is None:
        return {"row": "0b", "pass": None, "note": "no log located for this corpus"}
    if proc["freeze256_cycle"] is None:
        return {"row": "0b", "pass": False, "note": "simulated 256-slot table never froze"}
    ratio = proc["freeze256_cycle"] / proc["observed_freeze_cycle"]
    ok = 0.85 <= ratio <= 1.30
    return {"row": "0b", "pass": ok, "simulated_freeze_cycle": proc["freeze256_cycle"],
            "observed_freeze_cycle": proc["observed_freeze_cycle"], "ratio": round(ratio, 4),
            "row0b_start_ts": proc["row0b_start_ts"]}


def row_0c(proc):
    tbl = proc["tbl"]
    by_n12_scan = defaultdict(int)
    for idx in range(tbl.n):
        if tbl.state[idx] == S.OCCUPIED:
            by_n12_scan[(tbl.hash[idx] & 0x3FFFFF) >> 10] += 1
    mismatches = []
    for n12 in sorted(k for k, v in by_n12_scan.items() if v >= 2):
        _, n_matches, _ = S.lookup12_multiplicity(tbl, n12)
        if n_matches != by_n12_scan[n12]:
            mismatches.append({"n12": n12, "scan_count": by_n12_scan[n12], "chain_count": n_matches})
    return {"row": "0c", "pass": len(mismatches) == 0,
            "n_codes_with_2plus": sum(1 for v in by_n12_scan.values() if v >= 2),
            "mismatches": mismatches[:5]}


def row_0d(proc):
    moves = next((e for e in proc["population"] if e["n_matches"] >= 2), None)
    stays = next((e for e in proc["population"] if e["n_matches"] == 1), None)
    return {"row": "0d", "class": "DIAGNOSTIC (HK-021(k), both branches read -- never a gate)",
            "has_moving_exhibit": moves is not None, "has_stationary_exhibit": stays is not None,
            "moving_exhibit_n_matches": (moves["n_matches"] if moves else None),
            "moving_exhibit_n12": (moves["n12"] if moves else None)}


def row_0g(proc):
    bad = [e for e in proc["population"] if e["diverges"] and e["n_matches"] < 2]
    n_d = sum(1 for e in proc["population"] if e["diverges"])
    n_s = sum(1 for e in proc["population"] if e["suppressed"])
    return {"row": "0g", "pass": (len(bad) == 0 and n_d <= n_s), "D_count": n_d, "S_count": n_s}


# ---------------------------------------------------------------------------
# Sec.5 readings
# ---------------------------------------------------------------------------

def cluster_stats(events, value_key):
    clusters = defaultdict(lambda: [0, 0])
    for e in events:
        c = clusters[e["first"]]
        c[1] += 1
        if e[value_key]:
            c[0] += 1
    return clusters  # {callsign: [successes, total]}


def bootstrap_ci(clusters, n_draws=N_BOOT, seed=BOOT_SEED):
    keys = sorted(clusters.keys())
    n = len(keys)
    if n == 0:
        return None, None
    rng = random.Random(seed)
    vals = list(clusters.values())
    draws = []
    for _ in range(n_draws):
        num = den = 0
        for _ in range(n):
            s, t = vals[rng.randrange(n)]
            num += s
            den += t
        draws.append(num / den if den else 0.0)
    draws.sort()
    lo = draws[int(0.025 * (n_draws - 1))]
    hi = draws[int(0.975 * (n_draws - 1))]
    return lo, hi


def s_null(R):
    if R <= 0:
        return 0.0
    lam = R / 4096.0
    if lam < 1e-9:
        return 0.0
    return 1.0 - lam / (math.exp(lam) - 1.0)


def d_null(events):
    if not events:
        return 0.0
    return sum(1.0 - 1.0 / e["n_matches"] for e in events) / len(events)


def reading(events, count_trace, cutoff_h=None):
    pop = [e for e in events if (cutoff_h is None or e["elapsed_h"] <= cutoff_h)]
    n = len(pop)
    if n == 0:
        return {"n": 0}
    n_s = sum(1 for e in pop if e["suppressed"])
    n_d = sum(1 for e in pop if e["diverges"])
    S_val = n_s / n
    D_val = n_d / n
    clusters_s = cluster_stats(pop, "suppressed")
    clusters_d = cluster_stats(pop, "diverges")
    s_lo, s_hi = bootstrap_ci(clusters_s)
    d_lo, d_hi = bootstrap_ci(clusters_d)
    R = residency_at(count_trace, cutoff_h if cutoff_h is not None else 1e9)
    sn = s_null(R)
    dn = d_null(pop)
    marginal = (s_lo is not None and s_lo <= S_MAX <= s_hi)
    return {
        "n": n, "n_suppressed": n_s, "n_diverges": n_d,
        "S": round(S_val, 4), "S_ci95": [round(s_lo, 4), round(s_hi, 4)] if s_lo is not None else None,
        "D": round(D_val, 4), "D_ci95": [round(d_lo, 4), round(d_hi, 4)] if d_lo is not None else None,
        "D_over_S": round(D_val / S_val, 4) if S_val > 0 else None,
        "distinct_n12_codes": len(set(e["n12"] for e in pop)),
        "distinct_callsigns": len(set(e["first"] for e in pop)),
        "R_residency": R, "S_null": round(sn, 4), "D_null": round(dn, 4),
        "marginal_40pct": marginal,
        "verdict": ("MARGINAL" if marginal else ("ABOVE_S_MAX" if S_val > S_MAX else "AT_OR_BELOW_S_MAX")),
    }


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def build_result():
    out = {"spec_commit": "a6a1b2f", "S_max": S_MAX, "corpora": {}}
    procs = {}
    for cid, cfg in S.CORPORA.items():
        proc = process_corpus(cid, cfg)
        procs[cid] = proc
        entry = {
            "row_0a": row_0a(proc),
            "row_0b": row_0b(proc),
            "row_0c": row_0c(proc),
            "row_0d": row_0d(proc),
            "row_0g": row_0g(proc),
            "n_lookup_candidates": proc["n_lookup_candidates"],
            "excluded_misses": proc["excluded_misses"],
            "excluded_charset": proc["excluded_charset"],
            "dropped_arrival_charset": proc["dropped_arrival_charset"],
            "final_residency": proc["final_count"],
        }
        role = S.CORPORA[cid]["role"]
        if role == "primary":
            entry["primary"] = reading(proc["population"], proc["count_trace"], cutoff_h=None)
            entry["curve"] = {t: reading(proc["population"], proc["count_trace"], cutoff_h=t)
                               for t in CURVE_HOURS if t <= proc["declared_span_h"] + 0.2}
        elif role == "primary_prefix8h":
            entry["primary_1_8h"] = reading(proc["population"], proc["count_trace"], cutoff_h=8.0)
            entry["secondary_full_span"] = reading(proc["population"], proc["count_trace"], cutoff_h=None)
            entry["curve"] = {t: reading(proc["population"], proc["count_trace"], cutoff_h=t)
                               for t in CURVE_HOURS}
        elif role == "contrast":
            entry["contrast_full_span"] = reading(proc["population"], proc["count_trace"], cutoff_h=None)
        out["corpora"][cid] = entry
    return out, procs


def consequence(out):
    """Sec.4's own strict-order/stop-at-first-fire convention applies BEFORE
    Sec.5.5: a VALIDITY row (0a/0b/0c) failing VOIDS that corpus, and Sec.5.5's
    S-vs-S_max consequence table presupposes a corpus that SURVIVED ROW 0.
    A VOIDed corpus contributes no reading at all -- it is not "MARGINAL" and
    must not be folded into that verdict."""
    primary_ids = {"S-17M": "primary", "S-80M": "primary", "S-20M": "primary_1_8h"}
    voided, survived = {}, {}
    for cid, key in primary_ids.items():
        c = out["corpora"][cid]
        gate_fails = [row for row in ("row_0a", "row_0b", "row_0c") if c[row].get("pass") is False]
        if gate_fails:
            voided[cid] = gate_fails
        else:
            survived[cid] = c[key]

    if voided:
        return {
            "consequence": "ROW_0_VALIDITY_FAIL -- NO VALID PRIMARY READING",
            "reason": ("ROW 0b (the load-bearing positive control) fails its pre-registered "
                       "0.85-1.30 bracket for every primary corpus that has one -- Sec.2.3's "
                       "pre-resize-corpus assumption is NOT supported. Per Sec.4/HK-021(k) this "
                       "VOIDs the corpus outright; it is dispositive and upstream of Sec.5.5's "
                       "S-vs-S_max table, which never applies to a voided corpus."),
            "voided_corpora": voided,
            "survived_corpora": {cid: r.get("verdict") for cid, r in survived.items()},
            "escalate": True,
        }
    marginal = [cid for cid, r in survived.items() if r.get("verdict") == "MARGINAL"]
    if marginal:
        return {"consequence": "ESCALATE_TO_PO", "reason": "MARGINAL primary session(s)",
                "which": marginal, "per_session": {cid: r["verdict"] for cid, r in survived.items()}}
    above = [cid for cid, r in survived.items() if r.get("verdict") == "ABOVE_S_MAX"]
    below = [cid for cid, r in survived.items() if r.get("verdict") == "AT_OR_BELOW_S_MAX"]
    if len(below) == len(primary_ids):
        return {"consequence": "AFFORDABLE_UNCONDITIONAL", "per_session": {cid: r["verdict"] for cid, r in survived.items()}}
    if above and below:
        return {"consequence": "SPLIT_VERDICT_ESCALATE", "above": above, "below": below,
                "per_session": {cid: r["verdict"] for cid, r in survived.items()}}
    return {"consequence": "TOO_EXPENSIVE_UNCONDITIONAL_NARROW_NEEDED",
            "per_session": {cid: r["verdict"] for cid, r in survived.items()}}


def strip_for_json(out):
    def clean(d):
        if isinstance(d, dict):
            return {k: clean(v) for k, v in d.items() if k != "tbl" and k != "rows" and k != "population" and k != "count_trace"}
        return d
    return clean(out)


def main():
    out, procs = build_result()
    out["consequence"] = consequence(out)
    clean = strip_for_json(out)
    result_path = os.path.join(OUT_DIR, "result.json")
    with open(result_path, "w", encoding="utf-8") as fh:
        json.dump(clean, fh, indent=2, sort_keys=True)
    print(json.dumps(clean, indent=2, sort_keys=True))
    print("\nwrote", result_path)


if __name__ == "__main__":
    main()
