#!/usr/bin/env python
"""SUB-FEAS two-stage publish acceptance: compute S1, S2 and the managed flag-OFF control mechanically.

Run AFTER twostage_run.py has finished (status DONE). Predicates are the Architect's (spec sections 5b, 5c). Every
threshold is a constant from that spec and is NOT tuned. HK-037: stamps, integers, timings and 8-hex-digit text hashes
only; no message text is read here (the harness never wrote any).

S1  (161 E1 cycles, fresh processes, same order): PASS iff 161/161 for BOTH
      (a) union(batch1, batch2) == the single-batch flag-ON output of ca0bcd9b, per cycle
      (b) batch1 == the flag-OFF output of the same (two-stage) build, per cycle
    compared on the NUMERIC outcome fields (freqHz, dt, snr) as sorted multisets (stricter than "as a set"). The text
    hash is compared as a second, informational level: (a) has an identical native call sequence, so text should match
    too; (b) has a different history (flag OFF adds no residual decodes to the callsign hash table), so a text-level
    difference there is history, not the change, and is reported separately.
Managed flag-OFF control (14.4): DecodeAsync outcome fields, flag OFF, 2b39cf18 vs the two-stage build, same cycles, same
    order, identical native call sequence: expected identical at BOTH levels, ordered.
S2  (H u M): median per run of time-to-batch-1 <= 1.05 x the same-session flag-OFF whole-call median; the max term is read
    per cycle against the same-session flag-OFF call: cycles whose flag-OFF call itself exceeds 1000 ms are excluded and
    counted; if more than 1 % are excluded the max term is "not evaluable"; otherwise max(tb1 over the rest) <= 1000 ms.
"""
import collections
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replay81_rows as B

ART = B.ART
OUT = os.path.join(ART, "sub_feas_twostage_acceptance")
DERIVED = os.path.join(ART, "sub_feas_stage_a_e3_baseline", "e1_derived_selection.json")
RUNS = B.RUNS

S2_MEDIAN_RATIO = 1.05
S2_MAX_MS = 1000.0
S2_EXCLUDE_FRACTION = 0.01


def read_outcomes(path):
    """{stamp: {kind: [(freq, dt, snr, hash), ...]}} in file order (= decode order)."""
    d = collections.defaultdict(lambda: collections.defaultdict(list))
    if not os.path.exists(path):
        return d
    for line in open(path, encoding="utf-8"):
        p = line.rstrip("\n").split(",")
        if len(p) != 7:
            continue
        d[p[0]][p[1]].append((int(p[3]), float(p[4]), int(p[5]), p[6]))
    return d


def num(l):
    return sorted((f, dt, snr) for f, dt, snr, _ in l)


def txt(l):
    return sorted(l)


def main():
    sel = json.load(open(DERIVED, encoding="utf-8"))
    res = {"out_dir": OUT, "constants": {"s2_median_ratio": S2_MEDIAN_RATIO, "s2_max_ms": S2_MAX_MS,
                                         "s2_exclude_fraction": S2_EXCLUDE_FRACTION}}
    res["preflight"] = json.load(open(OUT + r"\preflight.json"))
    res["status"] = json.load(open(OUT + r"\status.json"))

    s1 = {"cycles": 0, "a_num_ok": 0, "a_txt_ok": 0, "b_num_ok": 0, "b_txt_ok": 0, "both_num_ok": 0,
          "ctl_ok_num": 0, "ctl_ok_txt": 0, "ctl_ordered_ok": 0, "b2_total": 0, "b2_cycles_nonempty": 0,
          "b1_total": 0, "ref_total": 0, "two_off_total": 0, "base_off_total": 0}
    bad = {"a_num": [], "b_num": [], "b_txt_only": [], "a_txt_only": [], "ctl": []}
    per_run = {}
    for run in RUNS:
        ref = read_outcomes(os.path.join(OUT, "s1", f"ref_on_{run}.outcomes.txt"))
        two = read_outcomes(os.path.join(OUT, "s1", f"two1_{run}.outcomes.txt"))
        toff = read_outcomes(os.path.join(OUT, "s1", f"two_off_{run}.outcomes.txt"))
        boff = read_outcomes(os.path.join(OUT, "s1", f"base_off_{run}.outcomes.txt"))
        pr = collections.Counter()
        for stamp in sel["runs"][run]["E1"]:
            r = ref[stamp]["single_on"]
            b1, b2 = two[stamp]["b1"], two[stamp]["b2"]
            o = toff[stamp]["single_off"]
            bo = boff[stamp]["single_off"]
            s1["cycles"] += 1
            pr["cycles"] += 1
            s1["b1_total"] += len(b1)
            s1["b2_total"] += len(b2)
            s1["b2_cycles_nonempty"] += 1 if b2 else 0
            s1["ref_total"] += len(r)
            s1["two_off_total"] += len(o)
            s1["base_off_total"] += len(bo)
            a_num = num(b1 + b2) == num(r)
            a_txt = txt(b1 + b2) == txt(r)
            b_num = num(b1) == num(o)
            b_txt = txt(b1) == txt(o)
            s1["a_num_ok"] += a_num
            s1["a_txt_ok"] += a_txt
            s1["b_num_ok"] += b_num
            s1["b_txt_ok"] += b_txt
            s1["both_num_ok"] += (a_num and b_num)
            if not a_num:
                bad["a_num"].append(f"{run}|{stamp}")
            if a_num and not a_txt:
                bad["a_txt_only"].append(f"{run}|{stamp}")
            if not b_num:
                bad["b_num"].append(f"{run}|{stamp}")
            if b_num and not b_txt:
                bad["b_txt_only"].append(f"{run}|{stamp}")
            # managed flag-OFF control: ordered equality, both levels
            c_num = [(f, dt, snr) for f, dt, snr, _ in bo] == [(f, dt, snr) for f, dt, snr, _ in o]
            c_ord = bo == o
            s1["ctl_ok_num"] += c_num
            s1["ctl_ok_txt"] += (txt(bo) == txt(o))
            s1["ctl_ordered_ok"] += c_ord
            if not c_ord:
                bad["ctl"].append(f"{run}|{stamp}")
        per_run[run] = dict(pr)
    for k in bad:
        bad[k] = bad[k][:40]
    s1["S1_pass"] = s1["cycles"] == 161 and s1["both_num_ok"] == 161
    s1["control_managed_flag_off_pass"] = s1["cycles"] == 161 and s1["ctl_ordered_ok"] == 161
    res["S1"] = s1
    res["S1_mismatch_stamps"] = bad

    # ---- S2 ---------------------------------------------------------------------------------------------
    rows_all = []
    per = {}
    av = cw = exc = 0
    ab_h = lines_h = 0
    for run in RUNS:
        for stratum in ("H", "M"):
            tag = f"two_{stratum}_{run}"
            path = os.path.join(OUT, "time", tag + ".csv")
            rows = list(csv.DictReader(open(path, newline="")))
            sub, a, c, other = B.parse_log(os.path.join(OUT, "time", tag + ".log"))
            av += a
            cw += c
            on = {r["stamp"]: r for r in rows if r["flag"] == "ON"}
            off = {r["stamp"]: r for r in rows if r["flag"] == "OFF"}
            exc += sum(1 for r in rows if r["exception"])
            if stratum == "H":
                lines_h += len(sub)
                ab_h += sum(1 for s in sub if s["abandoned"])
            for stamp, o in on.items():
                f = off.get(stamp)
                rows_all.append({"run": run, "stratum": stratum, "stamp": stamp, "tb1": float(o["tb1_ms"]),
                                 "whole": float(o["elapsed_ms"]), "off": float(f["elapsed_ms"]) if f else None,
                                 "b1_n": int(o["b1_n"]), "b2_n": int(o["b2_n"])})
            per[f"{run}|{stratum}"] = {"cycles": len(on), "off_rows": len(off), "log_lines": len(sub),
                                       "lines_eq_cycles": len(sub) == len(on)}
    s2 = {"n": len(rows_all), "per_block": per, "av_warnings": av, "contained_warnings": cw, "rows_with_exception": exc}
    med = {}
    for run in RUNS:
        rs = [r for r in rows_all if r["run"] == run]
        tb = [r["tb1"] for r in rs]
        of = [r["off"] for r in rs if r["off"] is not None]
        med[run] = {"n": len(rs), "tb1_median": B.med(tb), "tb1_p95": B.pct(tb, .95), "tb1_max": max(tb) if tb else None,
                    "off_median": B.med(of), "off_max": max(of) if of else None,
                    "ratio": (B.med(tb) / B.med(of)) if tb and of else None,
                    "whole_max": max(r["whole"] for r in rs) if rs else None}
        med[run]["median_ok"] = med[run]["ratio"] is not None and med[run]["ratio"] <= S2_MEDIAN_RATIO
    s2["per_run"] = med
    s2["median_term_pass"] = all(v["median_ok"] for v in med.values())
    excl = [r for r in rows_all if r["off"] is not None and r["off"] > S2_MAX_MS]
    kept = [r for r in rows_all if r["off"] is not None and r["off"] <= S2_MAX_MS]
    s2["max_term"] = {"excluded_cycles": len(excl), "excluded_fraction": (len(excl) / len(rows_all)) if rows_all else None,
                      "excluded_stamps": [f"{r['run']}|{r['stamp']} (off {r['off']:.0f} ms)" for r in excl][:30],
                      "evaluable": bool(rows_all) and (len(excl) / len(rows_all)) <= S2_EXCLUDE_FRACTION,
                      "max_tb1_over_kept_ms": max((r["tb1"] for r in kept), default=None),
                      "cycles_over_bar_kept": [f"{r['run']}|{r['stamp']} ({r['tb1']:.0f} ms)" for r in kept if r["tb1"] > S2_MAX_MS][:30]}
    if not s2["max_term"]["evaluable"]:
        s2["max_term"]["verdict"] = "NOT EVALUABLE"
    else:
        s2["max_term"]["verdict"] = "PASS" if (s2["max_term"]["max_tb1_over_kept_ms"] or 0) <= S2_MAX_MS else "FAIL"
    s2["S2_pass"] = s2["median_term_pass"] and s2["max_term"]["verdict"] == "PASS"
    s2["batch_sizes"] = {"b1_total": sum(r["b1_n"] for r in rows_all), "b2_total": sum(r["b2_n"] for r in rows_all),
                         "cycles_with_b2": sum(1 for r in rows_all if r["b2_n"] > 0)}
    s2["whole_call_max_ms"] = max((r["whole"] for r in rows_all), default=None)
    s2["H_abandoned"] = {"lines": lines_h, "abandoned": ab_h}
    res["S2"] = s2

    json.dump(res, open(os.path.join(OUT, "rows.json"), "w"), indent=1, default=str)
    print(json.dumps({"S1": res["S1"], "S1_mismatch_stamps": res["S1_mismatch_stamps"]}, indent=1))
    print(json.dumps(res["S2"], indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
