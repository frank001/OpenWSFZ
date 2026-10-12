#!/usr/bin/env python
"""Leg B and leg A against the LIVE WSJT-X ALL.TXT, from the first run's working files (QA, 2026-10-12, Architect request; analysis only, no decoding).

  python score_vs_wsjtx.py --corpus <corpus> --passdir <first-run dir> --out <aggregates.json>

Orientation: 'live' rows = WSJT-X's own live decodes (the reference); 'own' rows = OpenWSFZ's decodes of the same cycle.
  leg B = OpenWSFZ on WSJT-X's recording (identical audio to WSJT-X's live decode: every difference is the decoder, spec section 4);
  leg A = OpenWSFZ on its own recording (the product view).
Match = sm_01: key = (cycle, text with every <...> collapsed), paired in order per key. Matched share of WSJT-X's rows = matched / WSJT-X rows.
OWS-only rows = own rows left unmatched. Both are given for non-hashed rows (primary) and for all rows by key.
Bins: WSJT-X row SNR (matched share) / OWS row SNR (OWS-only rows); crowding = the live WSJT-X row count of the cycle; per band.
CIs: cycle-clustered bootstrap (the cycle is the cluster). NFR-021 / HK-037: message text is read inside the readers and never leaves;
the output is counts and shares only.
"""
import argparse
import json
import os
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import refset_score as rs  # noqa: E402

SNR_BINS = [("<=-20", -999, -20), ("-19..-15", -19, -15), ("-14..-10", -14, -10), ("-9..-5", -9, -5), (">=-4", -4, 999)]
CROWD_BINS = [("<=10", 0, 10), ("11-20", 11, 20), ("21-30", 21, 30), (">30", 31, 10 ** 9)]
BOOT_N, BOOT_SEED = 2000, 20261012


def read_live(path, stamps):
    """WSJT-X ALL.TXT rows -> {stamp: [(snr, text)]}."""
    want = set(stamps)
    out = {s: [] for s in want}
    with open(path, "r", encoding="ascii", errors="replace") as fh:
        for line in fh:
            t = line.split()
            if len(t) < 8 or t[0] not in want:
                continue
            try:
                snr = int(t[4])
            except ValueError:
                continue
            out[t[0]].append((snr, " ".join(t[7:])))
    return out


def read_own(path):
    """Working TSV -> {stamp: [(snr, text)]}."""
    out = defaultdict(list)
    with open(path, "r", encoding="utf-8") as fh:
        next(fh)
        for line in fh:
            p = line.rstrip("\n").split("\t", 4)
            if len(p) == 5:
                try:
                    out[p[0]].append((int(float(p[1])), p[4]))
                except ValueError:
                    pass
    return out


def match_cycle(live, own):
    """sm_01 pairing per key, in order. Returns (live_matched flags, own_matched flags) as lists of bool."""
    by_own = defaultdict(list)
    for i, (_, t) in enumerate(own):
        by_own[rs.key_of(t)].append(i)
    lm = [False] * len(live)
    om = [False] * len(own)
    used = defaultdict(int)
    for i, (_, t) in enumerate(live):
        k = rs.key_of(t)
        j = used[k]
        if j < len(by_own[k]):
            lm[i] = True
            om[by_own[k][j]] = True
            used[k] += 1
    return lm, om


def sbin(v, bins):
    for name, lo, hi in bins:
        if lo <= v <= hi:
            return name
    return None


def ci(num, den):
    num, den = np.asarray(num, float), np.asarray(den, float)
    if den.sum() == 0:
        return {"share": None, "ci95": None, "num": int(num.sum()), "den": int(den.sum()), "cycles": int(len(num))}
    lo, hi = rs.cluster_bootstrap_share(list(num), list(den), BOOT_N, BOOT_SEED)
    return {"share": round(float(num.sum() / den.sum()), 4), "ci95": [round(lo, 4), round(hi, 4)], "num": int(num.sum()), "den": int(den.sum()), "cycles": int(len(num))}


def analyse(corpus, passdir, leg, blocks, wsjtx_audio):
    """leg 'A' or 'B'. Collects per-cycle tallies, then the shares."""
    cyc = []   # one dict per scored cycle
    for blk in blocks:
        scored = rs.block_scored_stamps(blk)
        live = read_live(os.path.join(corpus, "wsjt-x", blk["run"], "ALL.TXT"), scored)
        own = read_own(os.path.join(passdir, leg, blk["id"] + ".decodes.tsv"))
        for s in scored:
            L, O = live.get(s, []), own.get(s, [])
            lm, om = match_cycle(L, O)
            cyc.append({"band": blk["band"], "n_live": len(L), "n_own": len(O),
                        "live": [(snr, rs.is_hashed(t), m) for (snr, t), m in zip(L, lm)],
                        "own": [(snr, rs.is_hashed(t), m) for (snr, t), m in zip(O, om)]})
    def shares(sel, nonhashed):
        num = [sum(1 for (_, h, m) in c["live"] if m and (not nonhashed or not h)) for c in sel]
        den = [sum(1 for (_, h, _m) in c["live"] if (not nonhashed or not h)) for c in sel]
        ext = [sum(1 for (_, h, m) in c["own"] if (not m) and (not nonhashed or not h)) for c in sel]
        return ci(num, den), {"owsonly_rows": int(sum(ext)), "owsonly_per_cycle": round(sum(ext) / len(sel), 3) if sel else None,
                              "owsonly_share_of_wsjtx_rows": round(sum(ext) / max(1, sum(den)), 4)}
    out = {"cycles": len(cyc), "wsjtx_rows": sum(c["n_live"] for c in cyc), "ows_rows": sum(c["n_own"] for c in cyc)}
    for tag, nh in (("nonhashed", True), ("all_by_key", False)):
        m, e = shares(cyc, nh)
        out[tag] = {"matched_share_of_wsjtx_rows": m, "owsonly": e}
    out["by_crowding"] = {}
    for name, lo, hi in CROWD_BINS:
        sel = [c for c in cyc if lo <= c["n_live"] <= hi]
        if sel:
            m, e = shares(sel, True)
            out["by_crowding"][name] = {"matched_share_nonhashed": m, "owsonly": e}
    out["owsonly_per_cycle_by_crowding"] = {}      # distribution of OWS-only rows (non-hashed) per cycle, by crowding bin
    for name, lo, hi in CROWD_BINS:
        sel = [c for c in cyc if lo <= c["n_live"] <= hi]
        if not sel:
            continue
        v = sorted(sum(1 for (_, h, m) in c["own"] if (not m) and (not h)) for c in sel)
        out["owsonly_per_cycle_by_crowding"][name] = {
            "cycles": len(v), "mean": round(sum(v) / len(v), 3), "median": v[len(v) // 2], "p90": v[int(0.9 * (len(v) - 1))], "max": v[-1],
            "cycles_with_0": sum(1 for x in v if x == 0), "cycles_with_1": sum(1 for x in v if x == 1),
            "cycles_with_2": sum(1 for x in v if x == 2), "cycles_with_3_or_more": sum(1 for x in v if x >= 3)}
    out["by_band"] = {}
    for band in sorted({c["band"] for c in cyc}):
        sel = [c for c in cyc if c["band"] == band]
        m, e = shares(sel, True)
        out["by_band"][band] = {"matched_share_nonhashed": m, "owsonly": e}
    # SNR bin x crowding: matched share by WSJT-X SNR (non-hashed), OWS-only counts by OWS SNR
    out["snr_x_crowding"] = {}
    for sname, slo, shi in SNR_BINS:
        row = {}
        for cname, clo, chi in CROWD_BINS:
            sel = [c for c in cyc if clo <= c["n_live"] <= chi]
            if not sel:
                continue
            num = [sum(1 for (snr, h, m) in c["live"] if m and not h and slo <= snr <= shi) for c in sel]
            den = [sum(1 for (snr, h, _m) in c["live"] if not h and slo <= snr <= shi) for c in sel]
            ext = [sum(1 for (snr, h, m) in c["own"] if (not m) and (not h) and slo <= snr <= shi) for c in sel]
            row[cname] = {"matched": ci(num, den), "owsonly_rows": int(sum(ext))}
        out["snr_x_crowding"][sname] = row
    out["snr_overall"] = {}
    for sname, slo, shi in SNR_BINS:
        num = [sum(1 for (snr, h, m) in c["live"] if m and not h and slo <= snr <= shi) for c in cyc]
        den = [sum(1 for (snr, h, _m) in c["live"] if not h and slo <= snr <= shi) for c in cyc]
        ext = sum(1 for c in cyc for (snr, h, m) in c["own"] if (not m) and (not h) and slo <= snr <= shi)
        out["snr_overall"][sname] = {"matched": ci(num, den), "owsonly_rows": int(ext)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--passdir", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    man = rs.load_json(os.path.join(a.corpus, "manifest.json"))
    agg = rs.load_json(os.path.join(a.passdir, "aggregate.json"))
    pins = [json.loads(l) for l in open(os.path.join(a.passdir, "pins.jsonl")) if l.strip()]
    order = []
    for p in pins:
        if p.get("leg") == "A" and p["block"] not in order:
            order.append(p["block"])
    by_id = {b["id"]: b for b in man["blocks"]}
    blocks = [by_id[b] for b in order]
    res = {"label": "first run, OpenWSFZ legs only (A, D, B); leg E pending. Analysis of the working files, no new decoding.",
           "source_pass": agg["pass"], "native_sha256": agg["native_sha256"], "banner": agg["banner"], "blocks": len(blocks),
           "orientation": "live = WSJT-X ALL.TXT rows; matched share = share of WSJT-X's rows OWS reproduced (sm_01 key, paired in order); OWS-only = own rows left unmatched",
           "leg_B_vs_live_wsjtx": analyse(a.corpus, a.passdir, "B", blocks, True),
           "leg_A_vs_live_wsjtx": analyse(a.corpus, a.passdir, "A", blocks, False)}
    with open(a.out, "w") as fh:
        json.dump(res, fh, indent=1)
    for leg in ("leg_B_vs_live_wsjtx", "leg_A_vs_live_wsjtx"):
        r = res[leg]
        print(leg, "cycles", r["cycles"], "wsjtx rows", r["wsjtx_rows"], "ows rows", r["ows_rows"],
              "nonhashed matched", r["nonhashed"]["matched_share_of_wsjtx_rows"]["share"], r["nonhashed"]["matched_share_of_wsjtx_rows"]["ci95"],
              "owsonly", r["nonhashed"]["owsonly"]["owsonly_rows"])


if __name__ == "__main__":
    main()
