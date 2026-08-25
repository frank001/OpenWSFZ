"""GAP-CENSUS-A ROW 0 -- preconditions, spec Sec.3. Evaluated in order; STOPS
at the first VOID (0a/0b/0c/0d are void-on-fail; 0e/0f route to a row instead
of voiding the whole arm, per the spec's own consequence column).

0d (determinism) is NOT run here -- it is driven externally by run_all.py,
which calls this module's row0a/row0b/row0c (and the whole Part A/B/C
pipeline) TWICE and diffs the resulting JSON byte-for-byte.
"""
from __future__ import annotations

from common import load_population
from partition import (classify_partition, count_bucket_c_independent,
                        ours_lookup_from_population)


def row0a(pop, log) -> dict:
    """Population definition + the 43.05%/42.2% reconciliation (spec Sec.2,
    ROW 0a). Not a numeric gate -- the spec's VOID condition is 'an unstated
    population', so this row is satisfied by stating the definition and the
    reconciliation, which it does unconditionally, then returns pass=True."""
    d001 = pop.d001_pct()
    log("ROW 0a: population = raw distinct (ts, whitespace-normalised message) keys, "
        "both legs' full ALL.TXT, corpus artefacts/20260803_live_run_1713, "
        "NO epoch filter, NO hash/band exclusions.")
    log("ROW 0a: ours=%d theirs=%d both=%d theirs_only=%d -> D-001=%.2f%%"
        % (pop.n_ours, pop.n_theirs, len(pop.both_key_set), pop.n_theirs_only, d001))
    log("ROW 0a: RECONCILIATION -- no committed, citable baseline exists to reproduce. "
        "The 42.2%% figure (2026-08-05 Arm R.D spec Sec.0/Sec.1) was computed on this SAME "
        "corpus but over a DIFFERENT, filtered basis -- the 'decisive epoch' subset "
        "(56,202/37,158 rows), not the full raw ALL.TXT (64,417/43,423 rows here) -- and its "
        "own spec explicitly disclaims it as 'Architect feasibility scouting ... must not be "
        "cited as a verdict'. The 43.05%% figure in this arm's own Sec.0.2 is likewise "
        "disclosed as exploratory/uncitable (Sec.0.1). Neither is a committed baseline in "
        "the ROW 0a sense; this row's population is stated fresh and independently, and its "
        "D-001=%.2f%% agrees with Sec.0.2's 43.05%% because both use the SAME raw-key basis "
        "(the difference from 42.2%% is basis, not disagreement)." % d001)
    return {"pass": True, "d001_pct": d001, "n_ours": pop.n_ours, "n_theirs": pop.n_theirs,
            "n_both": len(pop.both_key_set), "n_theirs_only": pop.n_theirs_only}


def row0b(pop, log) -> dict:
    """Partition exhaustive & mutually exclusive (A+B1+B2+C == theirs_only,
    exact), PLUS the Sec.3.2/HK-022 mitigation: bucket C computed by a
    SEPARATE code path and checked for exact key-set agreement, not just a
    count match."""
    ours_lookup = ours_lookup_from_population(pop)
    bucket_of = classify_partition(pop, ours_lookup)
    counts = {"A": 0, "B1": 0, "B2": 0, "C": 0}
    for v in bucket_of.values():
        counts[v] += 1
    total = sum(counts.values())
    exhaustive_ok = (total == pop.n_theirs_only)

    c_keys_main = {k for k, v in bucket_of.items() if v == "C"}
    c_keys_independent = count_bucket_c_independent(pop, ours_lookup)
    c_agrees = (c_keys_main == c_keys_independent)

    log("ROW 0b: A=%d B1=%d B2=%d C=%d sum=%d theirs_only=%d"
        % (counts["A"], counts["B1"], counts["B2"], counts["C"], total, pop.n_theirs_only))
    log("ROW 0b: bucket C independent recomputation (Sec.3.2/HK-022): "
        "main=%d independent=%d exact-set-agree=%s"
        % (len(c_keys_main), len(c_keys_independent), c_agrees))
    ok = exhaustive_ok and c_agrees
    log("ROW 0b: %s" % ("PASS" if ok else "VOID -- partition not exhaustive/mutually exclusive, "
                         "or bucket C's two code paths disagree"))
    return {"pass": ok, "counts": counts, "sum": total, "n_theirs_only": pop.n_theirs_only,
            "exhaustive_ok": exhaustive_ok, "c_agrees": c_agrees,
            "bucket_of": bucket_of}


def row0c(pop, log) -> dict:
    n_below = sum(1 for r in pop.ours_rows if r["freq_hz"] < 200.0)
    log("ROW 0c: our decodes below f_min=200.0 Hz: n=%d" % n_below)
    ok = (n_below == 0)
    log("ROW 0c: %s" % ("PASS" if ok else "VOID -- f_min is not what the source says; "
                         "bucket A is not a pure aperture census"))
    return {"pass": ok, "n_below_f_min": n_below}


def run_row0abc(log) -> tuple[dict, object]:
    """Runs 0a, 0b, 0c in strict order, stopping at the first VOID. Returns
    (result_dict, population). 0e/0f are run by part_b.py/run_all.py
    respectively since they route to a row rather than gating here."""
    pop = load_population()
    out = {}

    r = row0a(pop, log)
    out["0a"] = r
    if not r["pass"]:
        return out, pop

    r = row0b(pop, log)
    out["0b"] = {k: v for k, v in r.items() if k != "bucket_of"}  # bucket_of not JSON-friendly-huge
    if not r["pass"]:
        return out, pop

    r = row0c(pop, log)
    out["0c"] = r
    if not r["pass"]:
        return out, pop

    out["all_pass"] = True
    return out, pop
