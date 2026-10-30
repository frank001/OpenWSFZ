#!/usr/bin/env python3
"""LATE-SUB L1 build acceptance rows on the PC (build spec 33c50bd6 section 3 with Amendment 1 F3/F5).
Rows: B-OFF (arm off vs the continuous main reference, batches 1-4), B-EQ-1 (on vs off, F3), B-EQ-2 (batch 5 vs the harness L1' refset rows),
B-AB (abandoned counts), descriptive round timing. Reads message text ONLY inside this code from _qa-scratch (HK-037); writes aggregates and stamps.
usage: python lr_analyse.py [out.json]"""
import collections, csv, json, os, re, statistics, sys

S = "D:/Projects/claude/_qa-scratch"
LS = S + "/late-sub"
REF = S + "/coh-gate-r-f4"
RAW = LS + "/raw_lr"
SCR = LS + "/scratch_lr"
HARNESS_ROWS = LS + "/ls/l1p_refoff/ls_rows.tsv"
SEL = REF + "/selection1200.json"
SEL_SHA = "328c85d4263b8c35191d1370dc2f4b5ab675f0f396bca84042f303c1725a7ea4"
HASHED = re.compile(r"<[^>]*>")
FLOAT_TOL = 0.006   # dt is printed to 2 dp in nc_dump


def sha(p):
    import hashlib
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def load_nc(path):
    """stamp -> list of (kind, matched, freq, dt, snr, same_any, min_df, wcount, path, text)"""
    d = collections.defaultdict(list)
    with open(path, encoding="utf-8") as f:
        for line in f:
            r = line.rstrip("\n").split("\t")
            if len(r) < 11:
                continue
            d[r[0]].append((int(r[1]), r[2], int(r[3]), float(r[4]), int(r[5]), r[6], r[7], r[8], r[9], r[10]))
    return d


def core(row):
    """the fields that do not depend on how WSJT-X lines were assigned: kind, freq, dt, snr, path, text"""
    return (row[0], row[2], row[3], row[4], row[8], row[9])


def main():
    assert sha(SEL) == SEL_SHA, "selection file differs from the frozen one"
    sel = json.load(open(SEL))["runs"]["20260925_2010"]["FULL"]
    stamps = [e if isinstance(e, str) else e[0] for e in sel]
    assert len(stamps) == 1200
    main_nc = load_nc(REF + "/scratch_main/main/nc_dump.tsv")
    off = load_nc(SCR + "/off/nc_dump.tsv")
    on = load_nc(SCR + "/on/nc_dump.tsv")
    res = {"cycles": len(stamps)}

    # ---- B-OFF: the off arm's batches 1-4 equal the continuous main arm, every field of the dump, 1,200 cycles ---------------------------------------
    bad, first_bad, bad_core = 0, None, 0
    for i, s in enumerate(stamps):
        a, b = sorted(off.get(s, [])), sorted(main_nc.get(s, []))
        if a != b:
            bad += 1
            first_bad = first_bad or i + 1
        if sorted(map(core, a)) != sorted(map(core, b)):
            bad_core += 1
    kinds_off = collections.Counter(r[0] for rows in off.values() for r in rows)
    # run.csv: shared content columns equal; the off arm must have b5_n == 0 everywhere
    def runcsv(p):
        with open(p, newline="") as f:
            return {r["stamp"]: r for r in csv.DictReader(f)}
    ro, rm, rn = runcsv(RAW + "/off/run.csv"), runcsv(REF + "/raw_main/main/run.csv"), runcsv(RAW + "/on/run.csv")
    shared = ["decodes", "b1_n", "b2_n", "b3_n", "b4_n", "exception"]
    run_diff = sum(1 for s in stamps if any(ro[s][c] != rm[s][c] for c in shared))
    b5_off_nonzero = sum(1 for s in stamps if ro[s].get("b5_n", "0") not in ("0", ""))
    res["B-OFF"] = {"cycles_differing_full_dump": bad, "cycles_differing_core_fields": bad_core, "first_differing_cycle_index": first_bad,
                    "run_csv_shared_columns_differing": run_diff, "off_arm_cycles_with_b5": b5_off_nonzero, "off_arm_row_kinds": dict(sorted(kinds_off.items())),
                    "PASS": bad == 0 and run_diff == 0 and b5_off_nonzero == 0 and 5 not in kinds_off}

    # ---- B-EQ-1 (F3): on vs off, batches 1-4 ------------------------------------------------------------------------------------------------------------
    first_b5 = next((i for i, s in enumerate(stamps) if any(r[0] == 5 for r in on.get(s, []))), None)
    part1_bad, part2_other, part2_hashed_only = 0, 0, []
    first_other = None
    for i, s in enumerate(stamps):
        a = sorted(core(r) for r in off.get(s, []) if r[0] <= 4)
        b = sorted(core(r) for r in on.get(s, []) if r[0] <= 4)
        if a == b:
            continue
        if first_b5 is not None and i <= first_b5:
            part1_bad += 1
            first_other = first_other or i + 1
            continue
        # after the first batch 5: identical modulo hashed tokens, same row count
        na = sorted(core(r)[:5] + (HASHED.sub("<>", core(r)[5]),) for r in off.get(s, []) if r[0] <= 4)
        nb = sorted(core(r)[:5] + (HASHED.sub("<>", core(r)[5]),) for r in on.get(s, []) if r[0] <= 4)
        # the wildcard also hides a changed Dt/Snr/Freq of a hashed row? no: only the text is wildcarded
        if na == nb:
            part2_hashed_only.append(stamps[i])
        else:
            part2_other += 1
            first_other = first_other or i + 1
    matched_diff = sum(1 for s in stamps if sorted((r[0], r[1]) for r in off.get(s, []) if r[0] <= 4) != sorted((r[0], r[1]) for r in on.get(s, []) if r[0] <= 4))
    res["B-EQ-1"] = {"first_cycle_with_batch5_index": None if first_b5 is None else first_b5 + 1,
                     "part_i_cycles_differing_up_to_and_including_first_b5": part1_bad,
                     "part_ii_cycles_differing_other_than_hashed_token": part2_other,
                     "part_ii_cycles_differing_only_in_hashed_token": len(part2_hashed_only), "hashed_only_stamps": part2_hashed_only,
                     "first_stopping_cycle_index": first_other, "cycles_where_match_flags_differ_descriptive": matched_diff,
                     "PASS": first_b5 is not None and part1_bad == 0 and part2_other == 0}

    # ---- B-EQ-2: batch 5 vs the harness L1' refset published rows (plain text) ---------------------------------------------------------------------
    harness = collections.defaultdict(list)
    with open(HARNESS_ROWS, encoding="utf-8") as f:
        for line in f:
            r = line.rstrip("\n").split("\t")
            if len(r) >= 6 and r[1] == "L1":
                harness[r[0]].append((int(r[2]), float(r[3]), int(r[4]), r[5]))
    plain_diff, hashed_diff, first_plain, first_hash = 0, 0, None, None
    hashed_listed, dtsnr_mismatch, plain_rows_h, plain_rows_p = [], 0, 0, 0
    n5_rows = sum(1 for s in stamps for r in on.get(s, []) if r[0] == 5)
    h_rows = sum(len(harness.get(s, [])) for s in stamps)
    for i, s in enumerate(stamps):
        h = harness.get(s, [])
        p = [(r[2], r[3], r[4], r[9]) for r in on.get(s, []) if r[0] == 5]
        hp = sorted((f, t) for f, d, sn, t in h if "<" not in t)
        pp = sorted((f, t) for f, d, sn, t in p if "<" not in t)
        plain_rows_h += len(hp)
        plain_rows_p += len(pp)
        if hp != pp:
            plain_diff += 1
            first_plain = first_plain or i + 1
        elif hp:
            hd = {(f, t): (d, sn) for f, d, sn, t in h if "<" not in t}
            for f, d, sn, t in p:
                if "<" in t:
                    continue
                d0, s0 = hd[(f, t)]
                if abs(d0 - d) > FLOAT_TOL or s0 != sn:
                    dtsnr_mismatch += 1
        # hashed text: counts per cycle
        hh = sum(1 for f, d, sn, t in h if "<" in t)
        ph = sum(1 for f, d, sn, t in p if "<" in t)
        if hh != ph:
            hashed_diff += 1
            hashed_listed.append([stamps[i], hh, ph])
            first_hash = first_hash or i + 1
    res["B-EQ-2"] = {"harness_batch5_rows": h_rows, "product_batch5_rows": n5_rows, "plain_rows_harness": plain_rows_h, "plain_rows_product": plain_rows_p,
                     "cycles_differing_on_plain_text": plain_diff, "first_plain_differing_cycle_index": first_plain,
                     "plain_rows_with_dt_or_snr_mismatch_descriptive": dtsnr_mismatch,
                     "cycles_with_hashed_count_difference_listed_allowed": hashed_diff, "hashed_count_differences_[stamp,harness,product]": hashed_listed,
                     "PASS": plain_diff == 0}

    # ---- B-AB: residual pass, third pass, fallback abandoned in ON = in OFF; the round's own count ------------------------------------------------
    def col(path, name):
        with open(path, newline="") as f:
            return {r["stamp"]: r[name] for r in csv.DictReader(f)}
    ab = {}
    for nm, p, c in [("residual_abandoned", "abandon.csv", "abandoned"), ("residual_contained", "abandon.csv", "contained"),
                     ("fallback_abandoned", "coh.csv", "abandoned")]:
        a, b = col(f"{RAW}/off/{p}", c), col(f"{RAW}/on/{p}", c)
        ab[nm] = {"off_total": sum(int(a[s] or 0) for s in a), "on_total": sum(int(b[s] or 0) for s in b), "cycles_differing": sum(1 for s in stamps if a.get(s) != b.get(s))}
    t_off, t_on = open(RAW + "/off/third.csv").read().splitlines(), open(RAW + "/on/third.csv").read().splitlines()
    hdr = t_off[0].split(",")
    keep = [i for i, h in enumerate(hdr) if "ms" not in h.lower()]
    third_diff = sum(1 for a, b in zip(t_off, t_on) if [a.split(",")[i] for i in keep] != [b.split(",")[i] for i in keep]) + abs(len(t_off) - len(t_on))
    ab["third_pass_rows_differing_excluding_ms_columns"] = third_diff
    res["B-AB"] = dict(ab, PASS=all(v["cycles_differing"] == 0 for k, v in ab.items() if isinstance(v, dict)) and third_diff == 0)

    # ---- descriptive: the round's own outcomes and times (the on arm's log, aggregates only) ------------------------------------------------------
    rx = re.compile(r"Late subtraction round: outcome=(\S+), buffer=(\S+), fit=(\d+), refused=(-?\d+), new=(\d+), published=(\d+), fbEndMs=(-?\d+), startMs=(\d+), elapsedMs=(\d+), endMs=(\d+), batch=5, batch5PublishMs=(-?\d+)")
    outc, el, ends, n_lines, buf = collections.Counter(), [], [], 0, collections.Counter()
    for line in open(RAW + "/on/log.log", encoding="utf-8", errors="replace"):
        m = rx.search(line)
        if not m:
            continue
        n_lines += 1
        outc[m.group(1)] += 1
        if not m.group(1).startswith("skipped"):
            buf[m.group(2)] += 1
        if m.group(1) in ("ran", "no-new", "abandoned", "failed"):
            el.append(int(m.group(9)))
            ends.append(int(m.group(10)))

    def q(v, p):
        v = sorted(v)
        return v[min(len(v) - 1, int(round(p * (len(v) - 1))))] if v else None
    res["round_timing_descriptive"] = {"log_lines": n_lines, "outcomes": dict(outc), "buffer_when_started": dict(buf),
                                       "elapsedMs_median": q(el, .5), "elapsedMs_p90": q(el, .9), "elapsedMs_max": max(el) if el else None,
                                       "endMs_max": max(ends) if ends else None}
    res["ALL_PASS"] = all(res[k]["PASS"] for k in ("B-OFF", "B-EQ-1", "B-EQ-2", "B-AB"))
    out = sys.argv[1] if len(sys.argv) > 1 else LS + "/lr_result.json"
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps({k: (v if k in ("cycles", "ALL_PASS") else {kk: vv for kk, vv in v.items() if not isinstance(vv, list) or len(vv) < 12}) for k, v in res.items()}, indent=1))


if __name__ == "__main__":
    main()
