#!/usr/bin/env python
"""SUB-FEAS §8.1 real-band runtime replay: compute rows R0..R7 mechanically from the raw output.

Run AFTER the orchestrator has finished (status DONE). It reads only the harness CSVs, the harness
logs (text-safe by construction: rendered text only for two aggregate-only templates, warning
TEMPLATES otherwise), r0.json, selection.json and, for R5, the aggregate "Cycle ...: N decode(s)
found, elapsed=X ms" lines of the archived daemon log where one exists.

HK-037 / NFR-021: nothing here reads or prints message text. ALL.TXT is read only for the first
field (cycle stamp) to obtain the archived pass-0 count of a cycle.

Predicates are the Architect's (spec + Amendments 1, 2). Nothing here is tuned; thresholds are constants.

Usage:  python replay81_rows.py [OUT_DIR]   (default: artefacts/rr_2026-09-29_replay81)
"""
import collections
import csv
import json
import math
import os
import re
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
ART = os.path.join(REPO, "artefacts")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ART, "rr_2026-09-29_replay81")
SELECTION = os.path.join(REPO, "qa", "rr-study", "results", "2026-09-29-sub-feas-8-1-replay", "selection.json")
RUNS = ["20260922_2056", "20260923_1730", "20260925_2010"]

# ---- constants from the spec ------------------------------------------------------------------
HARD_MS = 13_000            # R1
HEAD_MAX_MS = 10_000        # R2 max
HEAD_P95_H_MS = 6_000       # R2 p95 over H
ABANDON_FLAG = 0.05         # R4 flag threshold over H
R6_ALLOWANCE_MS = 3_000     # Amendment 1: constant
R6_BAR_MS = HARD_MS + R6_ALLOWANCE_MS
CLAMP_NEAR_MS = 12_500      # descriptive: how many cycles sit at the guard

SUBFEAS_RE = re.compile(r"Sub-feas residual pass: residualDecodes=(\d+) elapsedMs=(\d+) "
                        r"deadlineAbandoned=(True|False) containedException=(True|False) fittedSignals=(\d+)")
CYCLE_RE = re.compile(r"Cycle (\d\d:\d\d:\d\d): (\d+) decode\(s\) found, elapsed=(\d+) ms")
GREP_SUBFEAS = "Sub-feas residual pass: residualDecodes="
GREP_AV = "WARN-TEMPLATE .*access violation"
GREP_CONTAINED = "WARN-TEMPLATE Sub-feas residual pass failed"
STAMP = re.compile(r"^\d{6}_\d{6}$")


def pct(vals, p):
    s = sorted(vals)
    if not s:
        return None
    k = max(0, min(len(s) - 1, math.ceil(p * len(s)) - 1))
    return s[k]


def med(vals):
    s = sorted(vals)
    n = len(s)
    if n == 0:
        return None
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def read_rows(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, newline="") as fh:
        for r in csv.DictReader(fh):
            r["elapsed_ms"] = float(r["elapsed_ms"])
            r["decodes"] = int(r["decodes"])
            r["seq"] = int(r["seq"])
            rows.append(r)
    return rows


def parse_log(path):
    """Return (subfeas_lines_per_on_row_order, av_count, contained_warn_count, other_warn_templates).

    A log may hold several harness segments (a restart appends a new '# harness label' header). In
    each segment the Sub-feas lines BEFORE the '# warm-up cycle decoded and discarded' marker belong
    to the discarded warm-up decode and are dropped.
    """
    sub, av, contained_w = [], 0, 0
    other = collections.Counter()
    if not os.path.exists(path):
        return sub, av, contained_w, other
    warm_done = False
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("# harness label"):
                warm_done = False
                continue
            if line.startswith("# warm-up"):
                warm_done = True
                continue
            m = SUBFEAS_RE.search(line)
            if m and "[Information]" in line:
                if warm_done:
                    sub.append({"residual": int(m.group(1)), "elapsed_ms": int(m.group(2)),
                                "abandoned": m.group(3) == "True", "contained": m.group(4) == "True",
                                "fitted": int(m.group(5))})
                continue
            if "WARN-TEMPLATE" in line:
                if re.search(GREP_AV, line):
                    av += 1
                elif "Sub-feas residual pass failed" in line:
                    contained_w += 1
                else:
                    other[line.split("WARN-TEMPLATE", 1)[1].strip()[:90]] += 1
    return sub, av, contained_w, other


def archived_counts(run):
    c = collections.Counter()
    p = os.path.join(ART, f"{run}_endurance_run-gathered", "owsfz", "ALL.TXT")
    with open(p, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            head = line.split(None, 1)
            if head and STAMP.match(head[0]):
                c[head[0]] += 1
    return c


def archived_timing(run):
    """{HH:MM:SS -> elapsed_ms} from the archived daemon log(s) where they exist (aggregate lines only)."""
    d = os.path.join(ART, f"{run}_endurance_run-gathered")
    out = {}
    if not os.path.isdir(d):
        return out
    for n in os.listdir(d):
        if n.startswith("openswfz-") and n.endswith(".log"):
            with open(os.path.join(d, n), encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    m = CYCLE_RE.search(line)
                    if m:
                        out[m.group(1)] = int(m.group(3))
    return out


def main():
    sel = json.load(open(SELECTION, encoding="utf-8"))
    res = {"out_dir": OUT, "greps": {"subfeas_line": GREP_SUBFEAS, "av": GREP_AV, "contained": GREP_CONTAINED},
           "constants": {"hard_ms": HARD_MS, "headroom_max_ms": HEAD_MAX_MS, "headroom_p95_H_ms": HEAD_P95_H_MS,
                         "abandon_flag": ABANDON_FLAG, "r6_bar_ms": R6_BAR_MS}}
    res["preflight"] = json.load(open(os.path.join(OUT, "preflight.json")))
    res["R0"] = json.load(open(os.path.join(OUT, "r0.json")))
    res["status"] = json.load(open(os.path.join(OUT, "status.json")))

    # process exits (R3)
    exits = []
    pe = os.path.join(OUT, "process_exits.log")
    if os.path.exists(pe):
        for line in open(pe):
            m = re.search(r"rc=(-?\d+)", line)
            if m:
                exits.append(int(m.group(1)))
    res["process_exits"] = {"harness_invocations": len(exits), "non_zero": sum(1 for x in exits if x != 0)}

    per = {}                 # (run, stratum) -> dict
    all_on = {"H": [], "M": []}
    all_off = {"H": [], "M": []}
    joined = []              # (run, stratum, stamp, on_elapsed, off_elapsed, on_decodes, off_decodes, residual, abandoned, contained)
    tot_av = tot_cont_w = tot_cont_lines = tot_exc_rows = 0
    other_warn = collections.Counter()
    for run in RUNS:
        arch = archived_counts(run)
        for stratum in ("H", "M"):
            tag = f"time_{stratum}_{run}"
            rows = read_rows(os.path.join(OUT, "time", tag + ".csv"))
            sub, av, cw, other = parse_log(os.path.join(OUT, "time", tag + ".log"))
            other_warn.update(other)
            on = [r for r in rows if r["flag"] == "ON"]
            off = [r for r in rows if r["flag"] == "OFF"]
            exc = [r for r in rows if r["exception"]]
            tot_av += av
            tot_cont_w += cw
            tot_cont_lines += sum(1 for s in sub if s["contained"])
            tot_exc_rows += len(exc)
            expected = len(sel["runs"][run][stratum])
            on_by_stamp = {r["stamp"]: r for r in on}
            off_by_stamp = {r["stamp"]: r for r in off}
            # join log lines to ON rows in order (one line per ON decode)
            lines_eq_cycles = (len(sub) == len(on))
            on_sorted = sorted(on, key=lambda r: r["seq"])
            for i, r in enumerate(on_sorted):
                s = sub[i] if i < len(sub) else None
                o = off_by_stamp.get(r["stamp"])
                joined.append({"run": run, "stratum": stratum, "stamp": r["stamp"], "arch": arch.get(r["stamp"], 0),
                               "on_ms": r["elapsed_ms"], "off_ms": o["elapsed_ms"] if o else None,
                               "on_n": r["decodes"], "off_n": o["decodes"] if o else None,
                               "residual": s["residual"] if s else None,
                               "abandoned": s["abandoned"] if s else None,
                               "contained": s["contained"] if s else None,
                               "fitted": s["fitted"] if s else None})
            ons = [r["elapsed_ms"] for r in on]
            offs = [r["elapsed_ms"] for r in off]
            all_on[stratum] += ons
            all_off[stratum] += offs
            per[(run, stratum)] = {
                "cycles_selected": expected, "rows_ON": len(on), "rows_OFF": len(off), "rows_with_exception": len(exc),
                "sub_feas_log_lines": len(sub), "lines_eq_cycles": lines_eq_cycles,
                "abandoned": sum(1 for s in sub if s["abandoned"]),
                "abandon_fraction": (sum(1 for s in sub if s["abandoned"]) / len(sub)) if sub else None,
                "contained_lines": sum(1 for s in sub if s["contained"]),
                "on_ms": {"n": len(ons), "median": med(ons), "p95": pct(ons, .95), "max": max(ons) if ons else None},
                "off_ms": {"n": len(offs), "median": med(offs), "p95": pct(offs, .95), "max": max(offs) if offs else None},
                "near_guard_ge_12500": sum(1 for x in ons if x >= CLAMP_NEAR_MS),
                "av_warnings": av, "contained_warnings": cw,
            }
    res["per_run_stratum"] = {f"{k[0]}|{k[1]}": v for k, v in per.items()}
    res["other_warning_templates"] = dict(other_warn.most_common(10))

    # ---- R1 / R2 / R4 overall and per run ----
    hm = all_on["H"] + all_on["M"]
    h_on = all_on["H"]
    res["R1"] = {"max_ON_ms": max(hm) if hm else None, "bar_ms": HARD_MS,
                 "over_bar": [j["stamp"] + f" (arch pass-0 {j['arch']}, {j['on_ms']:.0f} ms)" for j in joined if j["on_ms"] > HARD_MS][:50],
                 "n_over_bar": sum(1 for j in joined if j["on_ms"] > HARD_MS),
                 "verdict": None if not hm else ("PASS" if max(hm) <= HARD_MS else "FAIL")}
    r2_max_ok = bool(hm) and max(hm) <= HEAD_MAX_MS
    r2_p95_ok = bool(h_on) and pct(h_on, .95) <= HEAD_P95_H_MS
    res["R2"] = {"max_ON_ms": max(hm) if hm else None, "p95_H_ON_ms": pct(h_on, .95),
                 "bar_max_ms": HEAD_MAX_MS, "bar_p95_H_ms": HEAD_P95_H_MS,
                 "verdict": ("PASS" if (r2_max_ok and r2_p95_ok) else ("PARTIAL" if res["R1"]["verdict"] == "PASS" else "FAIL"))}
    res["R3"] = {"access_violation_warnings": tot_av, "contained_exception_warnings": tot_cont_w,
                 "contained_exception_log_lines": tot_cont_lines, "csv_rows_with_exception": tot_exc_rows,
                 "harness_process_exits_non_zero": res["process_exits"]["non_zero"],
                 "verdict": "PASS" if (tot_av == 0 and tot_cont_w == 0 and tot_cont_lines == 0 and tot_exc_rows == 0
                                       and res["process_exits"]["non_zero"] == 0) else "FAIL"}
    subs_h = [j for j in joined if j["stratum"] == "H" and j["abandoned"] is not None]
    aband_h = sum(1 for j in subs_h if j["abandoned"])
    res["R4"] = {"H_lines": len(subs_h), "H_abandoned": aband_h,
                 "H_abandon_fraction": (aband_h / len(subs_h)) if subs_h else None,
                 "H_flag_over_5pct": (aband_h / len(subs_h) > ABANDON_FLAG) if subs_h else None,
                 "lines_eq_cycles_every_block": all(v["lines_eq_cycles"] for v in per.values()),
                 "mismatched_blocks": [f"{k[0]}|{k[1]}" for k, v in per.items() if not v["lines_eq_cycles"]],
                 "verdict": "REPORT ONLY (flag threshold 5% over H)"}

    # ---- R5: OFF versus the archived daemon timing where it exists ----
    r5 = {}
    for run in RUNS:
        at = archived_timing(run)
        if not at:
            r5[run] = "archived daemon timing not available for this run"
            continue
        pairs = []
        for j in joined:
            if j["run"] == run and j["off_ms"] is not None:
                hhmmss = j["stamp"][7:9] + ":" + j["stamp"][9:11] + ":" + j["stamp"][11:13]
                if hhmmss in at:
                    pairs.append((j["off_ms"], at[hhmmss]))
        if pairs:
            r5[run] = {"cycles": len(pairs), "median_replay_OFF_ms": med([p[0] for p in pairs]),
                       "median_archived_ms": med([p[1] for p in pairs]),
                       "ratio_of_medians": med([p[0] for p in pairs]) / med([p[1] for p in pairs])}
    res["R5"] = r5

    # ---- R6: synthetic pair-sum stress ----
    r6rows = read_rows(os.path.join(OUT, "time", "time_R6.csv"))
    sub6, av6, cw6, oth6 = parse_log(os.path.join(OUT, "time", "time_R6.log"))
    res["R6"] = {"pairs": len(r6rows), "max_ON_ms": max((r["elapsed_ms"] for r in r6rows), default=None),
                 "bar_ms": R6_BAR_MS, "av_warnings": av6, "contained_warnings": cw6,
                 "contained_log_lines": sum(1 for s in sub6 if s["contained"]), "abandoned": sum(1 for s in sub6 if s["abandoned"]),
                 "rows_with_exception": sum(1 for r in r6rows if r["exception"]),
                 "decodes_pass0_plus_residual": {"min": min((r["decodes"] for r in r6rows), default=None),
                                                 "max": max((r["decodes"] for r in r6rows), default=None)},
                 "fitted_signals_max": max((s["fitted"] for s in sub6), default=None)}
    r6ok = (res["R6"]["max_ON_ms"] is not None and res["R6"]["max_ON_ms"] <= R6_BAR_MS and av6 == 0 and cw6 == 0
            and res["R6"]["contained_log_lines"] == 0 and res["R6"]["rows_with_exception"] == 0)
    res["R6"]["verdict"] = "PASS" if r6ok else "FAIL"

    # ---- R7: descriptive only, NO CLAIM, NO BAR ----
    r7 = {}
    for run in RUNS + ["ALL"]:
        js = [j for j in joined if (run == "ALL" or j["run"] == run) and j["off_n"] is not None]
        d = [j["on_n"] - j["off_n"] for j in js]
        rd = [j["residual"] for j in js if j["residual"] is not None]
        r7[run] = {"cycles": len(js), "on_minus_off_count_mean": (sum(d) / len(d)) if d else None,
                   "on_minus_off_hist": dict(sorted(collections.Counter(d).items())),
                   "residualDecodes_mean": (sum(rd) / len(rd)) if rd else None,
                   "fittedSignals_mean": (sum(j["fitted"] for j in js if j["fitted"] is not None) / max(1, len(rd)))}
    res["R7_descriptive_only_no_claim"] = r7

    # ---- strata and blocks ----
    res["selection_counts"] = {r: {"pilot": len(sel["runs"][r]["pilot"]), "M": len(sel["runs"][r]["M"]), "H": len(sel["runs"][r]["H"]),
                                   "blocks": sel["runs"][r]["blocks"]} for r in RUNS}
    json.dump(res, open(os.path.join(OUT, "rows.json"), "w"), indent=1, default=str)
    print(json.dumps({k: res[k] for k in ("R0", "R1", "R2", "R3", "R4", "R5", "R6", "process_exits")}, indent=1, default=str))
    print(json.dumps(res["per_run_stratum"], indent=1))
    print(json.dumps(res["R7_descriptive_only_no_claim"], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
