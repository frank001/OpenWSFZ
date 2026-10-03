#!/usr/bin/env python
"""SUB-FEAS speed-redesign acceptance: compute E1, R0, R1', R2', R3, R4', R5', R6, R7 and T mechanically.

Run AFTER replay_speed_run.py has finished (status DONE). Predicates are the Architect's
(qa/rr-study/2026-09-30-0641-architect-to-qa-spec-sub-feas-speed-redesign.md section 2 + Amendment 1).
Every threshold below is a constant taken from that spec and is NOT tuned. HK-037: stamps, integers and
timings only; no message text is read.

Reuses the parsing helpers of replay81_rows.py (same log grammar; the Sub-feas line is unchanged).
Usage: python replay_speed_rows.py
"""
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replay81_rows as B  # helpers: read_rows, parse_log, pct, med, archived_counts

ART = B.ART
OUT = os.path.join(ART, "sub_feas_speed_acceptance")
E1_SUMMARY = os.path.join(ART, "sub_feas_speed_e1", "e1_summary.json")
RUNS = B.RUNS

# ---- constants from the spec --------------------------------------------------------------------
R1_BAR_MS = 13_000            # R1': max whole call, H u M, flag ON (hard bound)
R2_MAX_MS = 10_000            # R2': max
R2_P95_H_MS = 6_000           # R2': p95 over H
R4_BAR = 0.05                 # R4': abandon over H <= 5 % (now a BAR)
R5_RATIO = 1.05               # R5': cand OFF median <= base OFF median x 1.05, per run
R6_BAR_MS = 13_000            # R6: synthetic, no allowance (dropped by the spec)
NEAR_MS = 12_500              # descriptive


def ms_stats(v):
    return {"n": len(v), "median": B.med(v), "p95": B.pct(v, .95), "max": max(v) if v else None}


def main():
    sel = json.load(open(B.SELECTION, encoding="utf-8"))
    res = {"out_dir": OUT,
           "constants": {"R1_bar_ms": R1_BAR_MS, "R2_max_ms": R2_MAX_MS, "R2_p95_H_ms": R2_P95_H_MS, "R4_bar": R4_BAR,
                         "R5_ratio": R5_RATIO, "R6_bar_ms": R6_BAR_MS},
           "greps": {"subfeas_line": B.GREP_SUBFEAS, "av": B.GREP_AV, "contained": B.GREP_CONTAINED}}
    res["preflight"] = json.load(open(os.path.join(OUT, "preflight.json")))
    res["status"] = json.load(open(os.path.join(OUT, "status.json")))
    res["R0"] = json.load(open(os.path.join(OUT, "r0.json")))
    e1 = json.load(open(E1_SUMMARY))
    res["E1"] = {"pass": e1["e1_pass"], "cycles": e1["cycles"], "base_dll": e1["base_dll"], "cand_dll": e1["cand_dll"],
                 "comparisons": e1["comparisons"], "ref_kind_rc_counts": e1["ref_kind_rc_counts"]}

    exits = []
    import re
    for line in open(os.path.join(OUT, "process_exits.log")):
        m = re.search(r"rc=(-?\d+)", line)
        if m:
            exits.append(int(m.group(1)))
    res["process_exits"] = {"harness_invocations": len(exits), "non_zero": sum(1 for x in exits if x != 0)}

    per = {}
    on_all = {"H": [], "M": []}
    by_run = collections.defaultdict(lambda: {"on": [], "cand_off": [], "base_off": [], "baseB_off": []})
    joined = []
    tot_av = tot_cw = tot_cl = tot_exc = 0
    other_warn = collections.Counter()
    for run in RUNS:
        arch = B.archived_counts(run)
        for stratum in ("H", "M"):
            tag = f"time_{stratum}_{run}"
            rows = B.read_rows(os.path.join(OUT, "time", tag + ".csv"))
            sub, av, cw, other = B.parse_log(os.path.join(OUT, "time", tag + ".log"))
            other_warn.update(other)
            on = [r for r in rows if r["flag"] == "ON"]
            off = [r for r in rows if r["flag"] == "OFF"]
            exc = [r for r in rows if r["exception"]]
            tot_av += av
            tot_cw += cw
            tot_cl += sum(1 for s in sub if s["contained"])
            tot_exc += len(exc)
            off_by = {r["stamp"]: r for r in off}
            on_sorted = sorted(on, key=lambda r: r["seq"])
            for i, r in enumerate(on_sorted):
                s = sub[i] if i < len(sub) else None
                o = off_by.get(r["stamp"])
                joined.append({"run": run, "stratum": stratum, "stamp": r["stamp"], "arch": arch.get(r["stamp"], 0),
                               "on_ms": r["elapsed_ms"], "off_ms": o["elapsed_ms"] if o else None,
                               "on_n": r["decodes"], "off_n": o["decodes"] if o else None,
                               "residual": s["residual"] if s else None, "abandoned": s["abandoned"] if s else None,
                               "contained": s["contained"] if s else None, "fitted": s["fitted"] if s else None})
            ons = [r["elapsed_ms"] for r in on]
            on_all[stratum] += ons
            by_run[run]["on"] += ons
            by_run[run]["cand_off"] += [r["elapsed_ms"] for r in off]
            for btag, key in (("base", "base_off"), ("baseB", "baseB_off")):
                brows = B.read_rows(os.path.join(OUT, "time", f"{btag}_{stratum}_{run}.csv"))
                by_run[run][key] += [r["elapsed_ms"] for r in brows if r["flag"] == "NA"]
            per[f"{run}|{stratum}"] = {
                "cycles_selected": len(sel["runs"][run][stratum]), "rows_ON": len(on), "rows_OFF": len(off),
                "rows_with_exception": len(exc), "sub_feas_log_lines": len(sub), "lines_eq_cycles": len(sub) == len(on),
                "abandoned": sum(1 for s in sub if s["abandoned"]),
                "abandon_fraction": (sum(1 for s in sub if s["abandoned"]) / len(sub)) if sub else None,
                "contained_lines": sum(1 for s in sub if s["contained"]),
                "on_ms": ms_stats(ons), "off_ms": ms_stats([r["elapsed_ms"] for r in off]),
                "near_guard_ge_12500": sum(1 for x in ons if x >= NEAR_MS), "av_warnings": av, "contained_warnings": cw}
    res["per_run_stratum"] = per
    res["other_warning_templates"] = dict(other_warn.most_common(12))

    hm = on_all["H"] + on_all["M"]
    h = on_all["H"]
    res["R1prime"] = {"max_ON_ms": max(hm) if hm else None, "bar_ms": R1_BAR_MS,
                      "n_over_bar": sum(1 for x in hm if x > R1_BAR_MS), "n": len(hm),
                      "over_bar": [f"{j['stamp']} ({j['on_ms']:.0f} ms)" for j in joined if j["on_ms"] > R1_BAR_MS][:50],
                      "pass": bool(hm) and max(hm) <= R1_BAR_MS}
    res["R2prime"] = {"max_ON_ms": max(hm) if hm else None, "p95_H_ON_ms": B.pct(h, .95),
                      "bar_max_ms": R2_MAX_MS, "bar_p95_H_ms": R2_P95_H_MS,
                      "max_ok": bool(hm) and max(hm) <= R2_MAX_MS, "p95_ok": bool(h) and B.pct(h, .95) <= R2_P95_H_MS}
    res["R2prime"]["pass"] = res["R2prime"]["max_ok"] and res["R2prime"]["p95_ok"]
    res["R3"] = {"access_violation_warnings": tot_av, "contained_exception_warnings": tot_cw,
                 "contained_exception_log_lines": tot_cl, "csv_rows_with_exception": tot_exc,
                 "harness_process_exits_non_zero": res["process_exits"]["non_zero"],
                 "pass": tot_av == tot_cw == tot_cl == tot_exc == 0 and res["process_exits"]["non_zero"] == 0}
    subs_h = [j for j in joined if j["stratum"] == "H" and j["abandoned"] is not None]
    ab_h = sum(1 for j in subs_h if j["abandoned"])
    res["R4prime"] = {"H_lines": len(subs_h), "H_abandoned": ab_h,
                      "H_abandon_fraction": (ab_h / len(subs_h)) if subs_h else None, "bar": R4_BAR,
                      "lines_eq_cycles_every_block": all(v["lines_eq_cycles"] for v in per.values()),
                      "mismatched_blocks": [k for k, v in per.items() if not v["lines_eq_cycles"]],
                      "pass": bool(subs_h) and ab_h / len(subs_h) <= R4_BAR}
    # per-run abandon over H (descriptive, the blocks are not independent draws)
    res["R4prime"]["per_run_H"] = {run: {"lines": sum(1 for j in subs_h if j["run"] == run),
                                         "abandoned": sum(1 for j in subs_h if j["run"] == run and j["abandoned"])}
                                   for run in RUNS}

    # R5': flag-OFF whole-call median, candidate vs the base DLL re-measured this session (per run, H u M)
    r5 = {}
    for run in RUNS:
        c, b, b2 = by_run[run]["cand_off"], by_run[run]["base_off"], by_run[run]["baseB_off"]
        ratio = (B.med(c) / B.med(b)) if c and b else None
        r5[run] = {"cand_off_median_ms": B.med(c), "base_off_median_ms": B.med(b), "ratio": ratio,
                   "n_cand": len(c), "n_base": len(b),
                   "base_repeat_median_ms": B.med(b2) if b2 else None,
                   "base_repeat_over_base": (B.med(b2) / B.med(b)) if b2 and b else None,  # noise floor of the row
                   "pass": ratio is not None and ratio <= R5_RATIO}
    res["R5prime"] = r5
    res["R5prime_pass"] = all(v["pass"] for v in r5.values())

    r6rows = B.read_rows(os.path.join(OUT, "time", "time_R6.csv"))
    sub6, av6, cw6, _ = B.parse_log(os.path.join(OUT, "time", "time_R6.log"))
    res["R6"] = {"pairs": len(r6rows), "max_ON_ms": max((r["elapsed_ms"] for r in r6rows), default=None),
                 "bar_ms": R6_BAR_MS, "av_warnings": av6, "contained_warnings": cw6,
                 "contained_log_lines": sum(1 for s in sub6 if s["contained"]),
                 "abandoned": sum(1 for s in sub6 if s["abandoned"]),
                 "rows_with_exception": sum(1 for r in r6rows if r["exception"])}
    res["R6"]["pass"] = (res["R6"]["max_ON_ms"] is not None and res["R6"]["max_ON_ms"] <= R6_BAR_MS and av6 == 0 and
                         cw6 == 0 and res["R6"]["contained_log_lines"] == 0 and res["R6"]["rows_with_exception"] == 0)

    r7 = {}
    for run in RUNS + ["ALL"]:
        js = [j for j in joined if (run == "ALL" or j["run"] == run) and j["off_n"] is not None]
        d = [j["on_n"] - j["off_n"] for j in js]
        rd = [j["residual"] for j in js if j["residual"] is not None]
        r7[run] = {"cycles": len(js), "on_minus_off_count_mean": (sum(d) / len(d)) if d else None,
                   "on_minus_off_hist": dict(sorted(collections.Counter(d).items())),
                   "residualDecodes_mean": (sum(rd) / len(rd)) if rd else None}
    res["R7_descriptive_only_no_claim"] = r7

    # T (report only): H stratum at subtractionMaxThreads = 4
    t = {}
    for run in RUNS:
        rows = B.read_rows(os.path.join(OUT, "time", f"T4_H_{run}.csv"))
        sub, av, cw, _ = B.parse_log(os.path.join(OUT, "time", f"T4_H_{run}.log"))
        ons = [r["elapsed_ms"] for r in rows if r["flag"] == "ON"]
        t[run] = {"on_ms": ms_stats(ons), "abandoned": sum(1 for s in sub if s["abandoned"]), "lines": len(sub),
                  "av": av, "contained_warnings": cw}
    res["T_threads4_H_report_only"] = t

    stage_a = {"E1": res["E1"]["pass"], "R0": all(v["pass"] for v in res["R0"].values()), "R1prime": res["R1prime"]["pass"],
               "R2prime": res["R2prime"]["pass"], "R3": res["R3"]["pass"], "R4prime": res["R4prime"]["pass"],
               "R5prime": res["R5prime_pass"], "R6": res["R6"]["pass"]}
    res["STAGE_A"] = {"rows": stage_a, "verdict": "PASS" if all(stage_a.values()) else "FAIL",
                      "failed_rows": [k for k, v in stage_a.items() if not v],
                      "stage_B_trigger": (not stage_a["R2prime"]) or (not stage_a["R4prime"])}
    res["selection_counts"] = {r: {"pilot": len(sel["runs"][r]["pilot"]), "M": len(sel["runs"][r]["M"]),
                                   "H": len(sel["runs"][r]["H"]), "blocks": sel["runs"][r]["blocks"]} for r in RUNS}
    json.dump(res, open(os.path.join(OUT, "rows.json"), "w"), indent=1, default=str)
    keys = ("STAGE_A", "E1", "R0", "R1prime", "R2prime", "R3", "R4prime", "R5prime", "R6", "process_exits")
    print(json.dumps({k: res[k] for k in keys}, indent=1, default=str))
    print(json.dumps(res["per_run_stratum"], indent=1))
    print(json.dumps(res["R7_descriptive_only_no_claim"], indent=1))
    print(json.dumps(res["T_threads4_H_report_only"], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
