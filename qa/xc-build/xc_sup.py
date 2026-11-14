#!/usr/bin/env python3
"""XC-SUP (Architect's lead 1, E194, HK-026): is a batch-6 template publish a STALE template scored on the SAME station's next, DIFFERENT message?
The opposite-parity shadow cannot see that case.  COUNTS ONLY (HK-037): message text is read INSIDE the functions below and never leaves them.
Usage: python -I xc_sup.py <arm dir (the ON arm of a chain)> <ALL.TXT of that night> <out json>

Classes, the FIRST that matches wins, in the Architect's order:
  COR    Test B corroborated (the harness's own `matched` flag in nc.tsv)
  SUP-W  a WSJT-X row of the SAME cycle with a DIFFERENT text, |df| <= 3.125 Hz and |ddt| <= 0.2 s
  SUP-O  ON's own batch 1-5 decode of the same cycle with a different text in the same window
  FREE   none of the above
Reading rule (Architect): SUP-CLEAN iff n(SUP-W) <= 4 (SHADOW's own rule: 25 + n <= 29).
If SUP-FOUND also: the SUP-W rows an R14 co-location veto would remove (the SUP-O-located ones) and the COR rows it would remove (its NET cost in pp).
The veto flag (flag_O) is computed independently of the class order.  Window constants are the Architect's, asserted below."""
from __future__ import annotations

import collections
import csv
import json
import statistics
import sys

DF_HZ = 3.125
DDT_S = 0.2
CORR_DF_HZ = 10                      # the harness's corroboration window (Replay81 CorroborationDeltaHz)
EXPECT_B6, EXPECT_COR = 2579, 904    # ON's batch-6 publishes and the Test B corroborated rows (chain analysis, 8dd5ed1f)
N_REF = 25493
SUP_W_MAX = 4
DT_CONV_S = 0.6                      # OpenWSFZ dt minus WSJT-X DT, a fixed convention offset (the 904 COR rows: median 0.600, p05-p95 [0.600, 0.700]); a raw |ddt| <= 0.2 sees nothing
DT_CONV_TOL_S = 0.05
assert (DF_HZ, DDT_S, CORR_DF_HZ, SUP_W_MAX) == (3.125, 0.2, 10, 4)


def sender(msg):
    """the sending station's token: 2nd token, or the 3rd after 'CQ <modifier>' (a short letters-only word)."""
    t = msg.split()
    if not t:
        return ""
    if t[0] == "CQ":
        if len(t) >= 4 and t[1].isalpha() and len(t[1]) <= 4:
            return t[2]
        return t[1] if len(t) >= 2 else ""
    return t[1] if len(t) >= 2 else ""


def load_wsjtx(alltxt, stamps):
    ref = collections.defaultdict(list)           # stamp -> [(freq, dt, text)]
    with open(alltxt, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            f = line.split()
            if len(f) < 8 or f[2] != "Rx" or f[3] != "FT8" or f[0] not in stamps:
                continue
            try:
                snr, dt, freq = int(f[4]), float(f[5]), int(f[6])
            except ValueError:
                continue
            ref[f[0]].append((freq, dt, " ".join(f[7:]).strip()))
    return ref


def load_nc(path):
    rows = collections.defaultdict(list)          # stamp -> [dict]
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            f = line.rstrip("\n").split("\t")
            if len(f) < 11:
                continue
            rows[f[0]].append({"kind": int(f[1]), "matched": int(f[2]), "freq": int(f[3]), "dt": float(f[4]), "snr": int(f[5]), "text": f[10].strip()})
    return rows


def in_window(df, ddt):
    return abs(df) <= DF_HZ and abs(ddt) <= DDT_S


def in_window_w(df, ddt_raw):
    """WSJT-X row vs our decode: ddt_raw = WSJT-X DT - our dt, centred on the convention offset (-DT_CONV_S)."""
    return abs(df) <= DF_HZ and abs(ddt_raw + DT_CONV_S) <= DDT_S


def main(arm, alltxt, out):
    nc = load_nc(arm.rstrip("/\\") + "/nc.tsv")
    stamps = set(nc)
    ref = load_wsjtx(alltxt, stamps)
    cls = collections.Counter()
    snr = collections.defaultdict(list)
    share = collections.Counter()                 # publishes with >= 1 co-located different text that contains the sender token
    colocated_n = collections.defaultdict(list)   # per class: number of co-located different texts (W and O together)
    flag_o = collections.Counter()                # per class: publishes with flag_O (the R14 veto would remove them)
    ddt_cor = []                                  # ows dt - wsjtx dt for the COR rows' own matched WSJT-X row (instrument alignment)
    n_b6 = n_cor_flag = 0
    for s, rows in nc.items():
        w = ref.get(s, [])
        own = [r for r in rows if r["kind"] in (1, 2, 3, 4, 5)]
        for r in rows:
            if r["kind"] != 6:
                continue
            n_b6 += 1
            tok = sender(r["text"])
            wd = [x for x in w if x[2] != r["text"] and in_window_w(x[0] - r["freq"], x[1] - r["dt"])]
            od = [x for x in own if x["text"] != r["text"] and in_window(x["freq"] - r["freq"], x["dt"] - r["dt"])]
            fw, fo = bool(wd), bool(od)
            if r["matched"] == 1:
                c = "COR"
                same = [x for x in w if x[2] == r["text"] and abs(x[0] - r["freq"]) <= CORR_DF_HZ]
                if same:
                    best = min(same, key=lambda x: abs(x[0] - r["freq"]))
                    ddt_cor.append(r["dt"] - best[1])
            elif fw:
                c = "SUP-W"
            elif fo:
                c = "SUP-O"
            else:
                c = "FREE"
            cls[c] += 1
            snr[c].append(r["snr"])
            colocated_n[c].append(len(wd) + len(od))
            if fo:
                flag_o[c] += 1
            if tok and any(tok in x[2].split() for x in wd) or tok and any(tok in x["text"].split() for x in od):
                share[c] += 1
    res = {"n_b6_publishes": n_b6, "classes": dict(cls)}
    res["per_class"] = {c: {"n": cls[c], "snr_median": statistics.median(snr[c]) if snr[c] else None,
                            "with_a_colocated_text_sharing_the_sender_token": share[c],
                            "mean_colocated_texts": (sum(colocated_n[c]) / len(colocated_n[c])) if colocated_n[c] else None,
                            "flag_O_veto_would_remove": flag_o[c]} for c in ("COR", "SUP-W", "SUP-O", "FREE")}
    res["instrument_checks"] = {"b6_expected": EXPECT_B6, "cor_expected": EXPECT_COR,
                                "cor_ddt_median_s": statistics.median(ddt_cor) if ddt_cor else None,
                                "cor_ddt_p05_p95_s": [sorted(ddt_cor)[int(0.05 * len(ddt_cor))], sorted(ddt_cor)[int(0.95 * len(ddt_cor)) - 1]] if ddt_cor else None,
                                "cor_rows_with_equal_text_wsjtx_row_within_10Hz": len(ddt_cor)}
    # chance level of a different-text WSJT-X co-location for ordinary (batch 1-5) matched decodes: the baseline the SUP-W count is read against
    base_n = base_hit = 0
    for s, rows in nc.items():
        w = ref.get(s, [])
        for r in rows:
            if r["kind"] in (1, 2, 3, 4, 5) and r["matched"] == 1:
                base_n += 1
                if any(x[2] != r["text"] and in_window_w(x[0] - r["freq"], x[1] - r["dt"]) for x in w):
                    base_hit += 1
    res["baseline_b1to5_matched"] = {"n": base_n, "with_different_text_wsjtx_row_in_window": base_hit, "rate": base_hit / base_n if base_n else None}
    res["reading"] = {"sup_w": cls["SUP-W"], "limit": SUP_W_MAX, "SUP-CLEAN": cls["SUP-W"] <= SUP_W_MAX}
    res["veto_R14_if_found"] = {"sup_w_rows_removed_by_O_veto": None, "cor_rows_removed_by_O_veto": flag_o["COR"],
                                "net_cost_pp": 100.0 * flag_o["COR"] / N_REF}
    # SUP-W rows that carry flag_O are the ones an O-located veto removes; computed from the same files in a second pass
    sw_o = 0
    for s, rows in nc.items():
        w = ref.get(s, [])
        own = [r for r in rows if r["kind"] in (1, 2, 3, 4, 5)]
        for r in rows:
            if r["kind"] != 6 or r["matched"] == 1:
                continue
            fw = any(x[2] != r["text"] and in_window_w(x[0] - r["freq"], x[1] - r["dt"]) for x in w)
            fo = any(x["text"] != r["text"] and in_window(x["freq"] - r["freq"], x["dt"] - r["dt"]) for x in own)
            if fw and fo:
                sw_o += 1
    res["veto_R14_if_found"]["sup_w_rows_removed_by_O_veto"] = sw_o
    assert n_b6 == EXPECT_B6 and cls["COR"] == EXPECT_COR, (n_b6, dict(cls))
    assert abs(statistics.median(ddt_cor) - DT_CONV_S) <= DT_CONV_TOL_S, ("COR ddt median is not the convention offset", statistics.median(ddt_cor))
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
