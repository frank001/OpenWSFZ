#!/usr/bin/env python3
"""SUB-PROBE analysis (spec-sub-probe.md section 4): classify the crowded WSJT-X decodes that lean missed although their nearest neighbour was decoded.

  python -I sub_probe_analyze.py [tag]        (tag default "probe"; reads lc-base\\runs\\<tag>_<slice>_L_n<cycles>\\{probe.tsv, matched.csv, matchedbatch.csv, sel.json})

Counts and numbers only (HK-037): the WSJT-X list is rebuilt with SNR, DT and frequency only; the probe rows carry no text; match status comes from the harness's numeric match lists.
Definitions (CS-MAP's): T = a crowded WSJT-X decode (another one within +-50 Hz in the cycle) that lean missed; N = T's nearest WSJT-X neighbour (smallest |df|, ties to the lower list index);
only T whose N lean decoded are classified. "Near T" = a probe row within +-3.2 Hz and +-0.16 s of T. Times: the probe's time_s is the decoder's convention; WSJT-X's DT differs by a constant,
calibrated here from the decodes lean published in round 0 (median offset, with its spread printed): time_probe = DT_wsjtx + OFFSET.
Rows that are nearer to N than to T are attributed to N and ignored for T. Classes, first match wins (the spec's order, with one addition K0 placed first so the partition is complete):
  K0  lean published a decode at that position that was not matched to T (a wrong text or frequency off by more than 10 Hz)
  K1  a kept CAND near T with outcome DUP or GATE (decoded, dropped)
  K2  a kept CAND near T that was tried and failed (A_BP, A_CRC, B_NE, B_BP, B_CRC, CQ_FAIL, B_SKIP, B_NOC3)
  K3  a CAND near T not kept (NOT_KEPT_PATCH) or a LOW row near T (found only by the floor-0 search)
  K4  none of the above
"""
import csv
import json
import math
import os
import statistics
import sys
from collections import Counter

SC = r"D:\Projects\claude\_qa-scratch"
ART = r"D:\Projects\claude\OpenWSFZ\artefacts"
SL = {"S40": (170, "20261114_2312_endurance_run-gathered"), "H40": (240, "20261028_2233_endurance_run-gathered"), "H20": (240, "20260808_live_run_0016-8080")}
TAG = sys.argv[1] if len(sys.argv) > 1 else "probe"
TOL_HZ, TOL_S = 3.2, 0.16
CROWD_HZ = 50
KIND_SUB, KIND_CAND, KIND_LOW = 1, 2, 3
PUBLISHED = {1, 5, 8}                              # A_OK, B_OK, CQ_OK
DROPPED = {10, 11}                                 # DUP, GATE
FAILED = {2, 3, 4, 6, 7, 9, 14, 15}                # A_BP, A_CRC, B_NE, B_BP, B_CRC, CQ_FAIL, B_SKIP, B_NOC3
NOT_KEPT = {12, 13}
SNR_BANDS = [("ge-10", -10, 10**6), ("-10..-15", -15, -10), ("-15..-18", -18, -15), ("-18..-21", -21, -18), ("lt-21", -10**6, -21)]
DSNR = [("weaker>3", -10**6, -3), ("within3", -3, 3.0001), ("stronger3-10", 3.0001, 10.0001), ("stronger>10", 10.0001, 10**6)]
NOT_MEASURED = -999.0


def ceiling_db(snr_2500):
    """The most the footprint power can fall when a signal of this WSJT-X SNR (dB in 2500 Hz) is removed PERFECTLY: the footprint holds 8 tone columns per symbol, the signal sits in one of them, the other
    seven and the signal's own column keep their noise. Per column the signal-to-noise ratio is SNR + 10*log10(2500 / 6.25) = SNR + 26 dB, so before / after = 1 + S / (8 N) at best.
    An approximation (WSJT-X's SNR scale and the bin's noise bandwidth are good to a dB or two); it only says how much suppression the noise allows, not how good the fit was."""
    return 10.0 * math.log10(1.0 + 10.0 ** ((snr_2500 + 26.0) / 10.0) / 8.0)


def band(snr):
    for n, lo, hi in SNR_BANDS:
        if lo <= snr < hi:
            return n


def dsnr_bin(v):
    for n, lo, hi in DSNR:
        if lo <= v < hi:
            return n


def load_wsjtx(path, stamps):
    out = {s: [] for s in stamps}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line[:13] not in out:
                continue
            f = [x for x in line.split(" ") if x]
            if len(f) < 8 or f[2] != "Rx" or f[3] != "FT8":
                continue
            try:
                out[f[0]].append((int(f[4]), int(f[6]), float(f[5])))      # numbers only; the message (f[7:]) is dropped here
            except ValueError:
                continue
    return out


def load_matched(d):
    m = {}
    for row in csv.DictReader(open(os.path.join(d, "matched.csv"), newline="")):
        v = row["wsjtx_idx"]
        m[row["stamp"]] = {int(x) for x in v.split(";")} if v else set()
    return m


def load_batch(d):
    """(stamp, wsjtx index) -> the batch (1 round 0, 2 rounds 1 to 3, 3 cross-cycle) of the lean decode that matched it."""
    mb = {}
    for row in csv.DictReader(open(os.path.join(d, "matchedbatch.csv"), newline="")):
        for x in (row["wsjtx_idx_batch"].split(";") if row["wsjtx_idx_batch"] else []):
            j, k = x.split(":")
            mb[(row["stamp"], int(j))] = int(k)
    return mb


def load_probe(path):
    rows, overflow = {}, set()
    with open(path, encoding="utf-8") as fh:
        next(fh)
        for line in fh:
            c = line.rstrip("\n").split("\t")
            if len(c) == 2:
                overflow.add(c[0])
                continue
            rows.setdefault(c[0], []).append((int(c[1]), int(c[2]), float(c[3]), float(c[4]), float(c[5]), float(c[6]), int(c[7]), int(c[8]), int(c[9]), int(c[10]),
                                              int(c[11]), int(c[12]), int(c[13]), int(c[14]), int(c[15]), int(c[16])))
    return rows, overflow


# row tuple indices
R_KIND, R_ROUND, R_F, R_T, R_AMP, R_SUPP, R_SCORE, R_KEPT, R_OUT, R_GATE, R_ACODE, R_AUNS, R_BCODE, R_BUNS, R_CQC, R_CQU = range(16)


def quart(v):
    if not v:
        return None
    s = sorted(v)
    q = lambda p: s[min(len(s) - 1, int(p * (len(s) - 1) + 0.5))]
    return {"n": len(s), "q1": round(q(0.25), 1), "median": round(statistics.median(s), 1), "q3": round(q(0.75), 1)}


def calibrate(wl, M, prb):
    """Median of (probe time of the published round-0 CAND near a matched WSJT-X decode) - (that decode's DT)."""
    diffs = []
    for s, w in wl.items():
        ml = M.get(s, set())
        pr = [r for r in prb.get(s, []) if r[R_KIND] == KIND_CAND and r[R_ROUND] == 0 and r[R_OUT] in PUBLISHED]
        for j, (snr, f, dt) in enumerate(w):
            if j not in ml:
                continue
            near = [r for r in pr if abs(r[R_F] - f) <= TOL_HZ]
            if len(near) == 1:
                diffs.append(near[0][R_T] - dt)
    return diffs


def run_slice(name):
    n, folder = SL[name]
    d = SC + r"\lc-base\runs\%s_%s_L_n%d" % (TAG, name, n)
    stamps = list(json.load(open(os.path.join(d, "sel.json")))["runs"][json.load(open(os.path.join(d, "sel.json")))["run"]]["FULL"])
    wl = load_wsjtx(os.path.join(ART, folder, "wsjt-x", "ALL.TXT"), stamps)
    M = load_matched(d)
    MB = load_batch(d)
    nsub_batch = {k: Counter() for k in ("K0", "K1", "K2", "K3", "K4")}      # the batch that found the neighbour, for the neighbours that were never subtracted
    r0_cand = Counter()
    prb, overflow = load_probe(os.path.join(d, "probe.tsv"))
    diffs = calibrate(wl, M, prb)
    off = statistics.median(diffs)
    spread = {"n": len(diffs), "median": round(off, 3), "p10": round(sorted(diffs)[int(0.1 * len(diffs))], 3), "p90": round(sorted(diffs)[int(0.9 * len(diffs))], 3)}
    classes = ["K0", "K1", "K2", "K3", "K4"]
    cnt = {k: 0 for k in classes}
    by_dsnr = {k: Counter() for k in classes}
    supp = {k: [] for k in classes}
    n_not_subtracted = {k: 0 for k in classes}
    n_not_measured = {k: 0 for k in classes}
    unsat = []
    n_universe = n_crowded_missed = 0
    all_sub = []
    sub_by_band = {b[0]: [] for b in SNR_BANDS}
    gap_by_band = {b[0]: [] for b in SNR_BANDS}                                  # ceiling(snr) - measured suppression, dB
    n_gap = {k: [] for k in classes}                                              # the same for the classified neighbours N (N's own WSJT-X SNR)
    n_ceiling = {k: [] for k in classes}
    for s in stamps:
        w = wl[s]
        rows = prb.get(s, [])
        ml = M.get(s, set())
        subs = [r for r in rows if r[R_KIND] == KIND_SUB]
        cand_low = [r for r in rows if r[R_KIND] in (KIND_CAND, KIND_LOW)]

        def sub_of(fx, dtx):
            best = None
            for r in subs:
                if abs(r[R_F] - fx) <= TOL_HZ and abs(r[R_T] - (dtx + off)) <= TOL_S:
                    dist = abs(r[R_F] - fx) / TOL_HZ + abs(r[R_T] - (dtx + off)) / TOL_S
                    if best is None or dist < best[0]:
                        best = (dist, r)
            return best[1] if best else None

        for r in subs:                                                  # N's suppression overall, by the SNR band of the WSJT-X decode the SUB row belongs to
            if r[R_SUPP] != NOT_MEASURED:
                all_sub.append(r[R_SUPP])
            for (snr, f, dt) in w:
                if abs(r[R_F] - f) <= TOL_HZ and abs(r[R_T] - (dt + off)) <= TOL_S:
                    if r[R_SUPP] != NOT_MEASURED:
                        sub_by_band[band(snr)].append(r[R_SUPP])
                        gap_by_band[band(snr)].append(ceiling_db(snr) - r[R_SUPP])
                    break
        for j, (snr, f, dt) in enumerate(w):
            others = [(abs(w[i][1] - f), i) for i in range(len(w)) if i != j]
            if not others or sum(1 for dd, _ in others if dd <= CROWD_HZ) < 1:
                continue
            if j in ml:
                continue
            n_crowded_missed += 1
            _, ni = min(others)
            if ni not in ml:
                continue
            n_universe += 1
            nsnr, nf, ndt = w[ni]
            ds = dsnr_bin(nsnr - snr)
            tt = dt + off
            near = []
            for r in cand_low:
                if abs(r[R_F] - f) <= TOL_HZ and abs(r[R_T] - tt) <= TOL_S and abs(r[R_F] - f) <= abs(r[R_F] - nf):
                    near.append(r)
            cls = None
            if any(r[R_KIND] == KIND_CAND and r[R_OUT] in PUBLISHED for r in near):
                cls = "K0"
            elif any(r[R_KIND] == KIND_CAND and r[R_OUT] in DROPPED for r in near):
                cls = "K1"
            elif any(r[R_KIND] == KIND_CAND and r[R_OUT] in FAILED for r in near):
                cls = "K2"
                u = []
                for r in near:
                    if r[R_KIND] == KIND_CAND and r[R_OUT] in FAILED:
                        if r[R_ACODE] == 2 and r[R_AUNS] >= 0:
                            u.append(r[R_AUNS])
                        if r[R_BCODE] == 4 and r[R_BUNS] >= 0:
                            u.append(r[R_BUNS])
                if u:
                    unsat.append(min(u))
            elif any((r[R_KIND] == KIND_CAND and r[R_OUT] in NOT_KEPT) or r[R_KIND] == KIND_LOW for r in near):
                cls = "K3"
            else:
                cls = "K4"
            cnt[cls] += 1
            by_dsnr[cls][ds] += 1
            sr = sub_of(nf, ndt)
            if sr is None:
                n_not_subtracted[cls] += 1
                nsub_batch[cls][MB.get((s, ni), 0)] += 1
                if cls == "K2" and MB.get((s, ni), 0) == 1:           # round-0 neighbour never subtracted: did the missed signal have a round-0 candidate (the fit-skip rule keys on one)?
                    r0_cand["with_round0_candidate" if any(r[R_KIND] == KIND_CAND and r[R_ROUND] == 0 for r in near) else "no_round0_candidate"] += 1
            elif sr[R_SUPP] == NOT_MEASURED:
                n_not_measured[cls] += 1
            else:
                supp[cls].append(sr[R_SUPP])
                n_ceiling[cls].append(ceiling_db(nsnr))
                n_gap[cls].append(ceiling_db(nsnr) - sr[R_SUPP])
    res = {"cycles": n, "calibration_dt_offset": spread, "overflow_cycles": len(overflow), "crowded_missed_by_L": n_crowded_missed, "classified": n_universe, "counts": cnt,
           "by_dsnr": {k: dict(v) for k, v in by_dsnr.items()}, "n_supp": {k: quart(v) for k, v in supp.items()}, "n_not_subtracted": n_not_subtracted, "n_not_subtracted_by_batch": {k: {str(b): c for b, c in sorted(v.items())} for k, v in nsub_batch.items()}, "k2_round0_neighbour_never_subtracted": dict(r0_cand), "n_supp_not_measured": n_not_measured,
           "k2_unsat_best": quart(unsat), "n_ceiling": {k: quart(v) for k, v in n_ceiling.items()}, "n_gap_to_ceiling": {k: quart(v) for k, v in n_gap.items()},
           "gap_by_snr_band": {b: quart(v) for b, v in gap_by_band.items()}, "sub_all": quart(all_sub), "sub_by_snr_band": {b: quart(v) for b, v in sub_by_band.items()},
           "probe_rows": {"SUB": sum(1 for rr in prb.values() for r in rr if r[R_KIND] == 1), "CAND": sum(1 for rr in prb.values() for r in rr if r[R_KIND] == 2),
                          "LOW": sum(1 for rr in prb.values() for r in rr if r[R_KIND] == 3)}}
    assert sum(cnt.values()) == n_universe
    return res


def main():
    out = {s: run_slice(s) for s in SL if os.path.exists(SC + r"\lc-base\runs\%s_%s_L_n%d\arm.json" % (TAG, s, SL[s][0]))}      # finished runs only (arm.json is written last)
    json.dump(out, open(os.path.join(SC, "lc-base", "sub_probe_%s.json" % TAG), "w"), indent=1)
    for s, v in out.items():
        print(s, "calibration", v["calibration_dt_offset"], "| overflow cycles", v["overflow_cycles"], "| rows", v["probe_rows"])
        print("  crowded misses", v["crowded_missed_by_L"], "with N decoded", v["classified"], "classes", v["counts"])
        print("  N suppression by class", v["n_supp"], "not subtracted", v["n_not_subtracted"], "not measured", v["n_supp_not_measured"])


if __name__ == "__main__":
    main()
