#!/usr/bin/env python3
"""LATE-SUB L1' B-TOOL-2 (Architect ruling 73dc9036 s4): rows T2-1..T2-5 on cycles 1-60, OFF then ON, build b1d8a06e, instrument = the Replay81 commit cfdf724c.
T2-1 third.csv non-ms columns ON vs OFF: 0 of 60 differ.
T2-2 ON: exactly one 'Late subtraction round:' line per cycle (60 of 60), every one matching the regex (unmatched 0); OFF: 0 lines.
T2-3 ON: published in the line = b5_n in run.csv, 60 of 60.
T2-4 ON: cycle 55 carries a 'skipped-...' outcome and no round started; the reason is reported. Cycle 55 is cross-checked against QA's own segmentation of the
     s3 ON arm (log order R T F T C): the first cycle with no inner Third pass line.
T2-5 nc_dump and run.csv content columns of both arms equal the s3 arms' on cycles 1-60.
Reads message text ONLY inside this code from _qa-scratch (HK-037); prints aggregates and stamps. usage: python t2_analyse.py [out.json]"""
import collections, csv, json, re, sys

S = "D:/Projects/claude/_qa-scratch/late-sub"
T2 = S + "/raw_t2"
SC2 = S + "/scratch_t2"
LR = S + "/raw_lr"
SCL = S + "/scratch_lr"
N = 60
RX_LATE = re.compile(r"^Late subtraction round: outcome=([a-z0-9-]+), buffer=(\S+), fit=(\d+), refused=(-?\d+), new=(\d+), published=(\d+), fbEndMs=(-?\d+), startMs=(-?\d+), elapsedMs=(-?\d+), endMs=(-?\d+), batch=(\d+), batch5PublishMs=(-?\d+)\.$")


def rows(p):
    with open(p, newline="") as f:
        return list(csv.DictReader(f))


def nc(path, stamps):
    d = collections.defaultdict(list)
    keep = set(stamps)
    with open(path, encoding="utf-8") as f:
        for line in f:
            r = line.rstrip("\n").split("\t")
            if r and r[0] in keep:
                d[r[0]].append(tuple(r))
    return {s: sorted(d.get(s, [])) for s in stamps}


def paired_first_noround(path):
    """QA's own segmentation (log order R T F T C): index (1-based, after the warm-up) of the first cycle with a Third pass line and no inner round line."""
    trx = re.compile(r"\] Third pass: newDecodes=")
    cyc, cur, seen_f = [], None, False
    for line in open(path, encoding="utf-8", errors="replace"):
        if "] Sub-feas residual pass:" in line:
            cur = {"t": 0, "r": 0}
            cyc.append(cur)
            seen_f = False
        elif "] Coherent fallback:" in line:
            seen_f = True
        elif trx.search(line) and cur is not None:
            cur["r" if seen_f else "t"] += 1
    if cyc and cyc[0]["t"] == 0 and cyc[0]["r"] == 0:
        cyc = cyc[1:]
    return [i + 1 for i, c in enumerate(cyc) if c["t"] and not c["r"]][:5], len(cyc)


def main():
    sel = json.load(open(S + "/selection60.json"))["runs"]["20260925_2010"]["FULL"]
    stamps = [e if isinstance(e, str) else e[0] for e in sel]
    assert len(stamps) == N
    res = {}
    t_off, t_on = rows(T2 + "/off/third.csv"), rows(T2 + "/on/third.csv")
    keep = [k for k in t_off[0] if "ms" not in k.lower()]
    d1 = [r1["stamp"] for r1, r2 in zip(t_off, t_on) if [r1[k] for k in keep] != [r2[k] for k in keep]]
    res["T2-1"] = {"rows_off": len(t_off), "rows_on": len(t_on), "cycles_differing_non_ms": len(d1), "stamps": d1,
                   "PASS": len(t_off) == len(t_on) == N and not d1}
    l_on, l_off = rows(T2 + "/on/late.csv"), rows(T2 + "/off/late.csv")
    one = sum(1 for r in l_on if r["lines"] == "1")
    unm = sum(int(r["unmatched"]) for r in l_on)
    off_lines = sum(int(r["lines"]) for r in l_off)
    off_unm = sum(int(r["unmatched"]) for r in l_off)
    # an independent regex pass over the ON log's raw lines, so the CSV is not graded by its own parser
    n_log = sum(1 for line in open(T2 + "/on/log.log", encoding="utf-8", errors="replace") if "] Late subtraction round:" in line)
    n_log_match = sum(1 for line in open(T2 + "/on/log.log", encoding="utf-8", errors="replace")
                      if "] Late subtraction round:" in line and RX_LATE.match(line.split("] ", 1)[1].rstrip("\n")))
    n_log_off = sum(1 for line in open(T2 + "/off/log.log", encoding="utf-8", errors="replace") if "Late subtraction round" in line)
    res["T2-2"] = {"on_rows": len(l_on), "on_cycles_with_exactly_one_line": one, "on_unmatched_lines": unm, "on_log_lines": n_log, "on_log_lines_matching_regex_independent": n_log_match,
                   "off_late_csv_lines_total": off_lines, "off_late_csv_unmatched": off_unm, "off_log_lines": n_log_off,
                   "PASS": len(l_on) == N and one == N and unm == 0 and n_log == N and n_log_match == N and off_lines == 0 and off_unm == 0 and n_log_off == 0}
    r_on = {r["stamp"]: r for r in rows(T2 + "/on/run.csv")}
    r_off = {r["stamp"]: r for r in rows(T2 + "/off/run.csv")}
    bad3 = [r["stamp"] for r in l_on if r["published"] != r_on[r["stamp"]]["b5_n"]]
    res["T2-3"] = {"cycles_published_eq_b5_n": N - len(bad3), "of": N, "mismatching_stamps": bad3, "PASS": not bad3 and len(l_on) == N}
    c55 = l_on[54]
    first_none, ncyc = paired_first_noround(LR + "/on/log.log")
    res["T2-4"] = {"cycle_55_stamp": c55["stamp"], "cycle_55_outcome": c55["outcome"], "cycle_55_buffer": c55["buffer"], "cycle_55_fit": c55["fit"], "cycle_55_new": c55["new"],
                   "cycle_55_published": c55["published"], "cycle_55_elapsedMs": c55["elapsedMs"], "cycle_55_startMs": c55["startMs"], "cycle_55_endMs": c55["endMs"],
                   "cycle_55_fbEndMs": c55["fbEndMs"], "cycle_55_batch5PublishMs": c55["batch5PublishMs"],
                   "cycle_55_is_first_skipped_outcome_in_1_60": next((i + 1 for i, r in enumerate(l_on) if r["outcome"].startswith("skipped")), None),
                   "qa_own_segmentation_s3_on_arm_first_cycles_with_no_inner_line": first_none[:4], "s3_on_arm_cycles_seen": ncyc,
                   "on_outcomes_1_60": dict(collections.Counter(r["outcome"] for r in l_on)),
                   "PASS": c55["outcome"].startswith("skipped") and c55["elapsedMs"] in ("0", "-0") and (first_none and first_none[0] == 55)}
    # T2-5
    content = ["decodes", "b1_n", "b2_n", "b3_n", "b4_n", "b5_n", "exception"]
    r_off3, r_on3 = {r["stamp"]: r for r in rows(LR + "/off/run.csv")}, {r["stamp"]: r for r in rows(LR + "/on/run.csv")}
    run_diff = sum(1 for s in stamps for (a, b) in ((r_off, r_off3), (r_on, r_on3)) if any(a[s][c] != b[s][c] for c in content))
    ncs = {}
    for arm in ("off", "on"):
        a, b = nc(SC2 + f"/{arm}/nc_dump.tsv", stamps), nc(SCL + f"/{arm}/nc_dump.tsv", stamps)
        ncs[arm] = {"cycles_differing": sum(1 for s in stamps if a[s] != b[s]), "rows_t2": sum(len(v) for v in a.values()), "rows_s3": sum(len(v) for v in b.values())}
    res["T2-5"] = {"run_csv_content_columns_differing_cycle_arms": run_diff, "nc_dump": ncs,
                   "PASS": run_diff == 0 and all(v["cycles_differing"] == 0 and v["rows_t2"] == v["rows_s3"] and v["rows_t2"] > 0 for v in ncs.values())}
    # ruling s6: the inner lines' new vs published, cycles 1-60 (descriptive)
    tot_new = sum(int(r["new"]) for r in l_on)
    tot_pub = sum(int(r["published"]) for r in l_on)
    res["s6_descriptive"] = {"inner_new_total_1_60": tot_new, "published_total_1_60": tot_pub,
                              "cycles_new_ne_published": [[r["stamp"], r["new"], r["published"]] for r in l_on if r["new"] != r["published"]]}
    res["ALL_PASS"] = all(res[k]["PASS"] for k in ("T2-1", "T2-2", "T2-3", "T2-4", "T2-5"))
    json.dump(res, open(sys.argv[1] if len(sys.argv) > 1 else S + "/t2_result.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
