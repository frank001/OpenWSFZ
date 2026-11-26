#!/usr/bin/env python3
"""LC-BASE scoring (spec-lc-base-lean-vs-classic.md section 5): where the decodes of arm C (classic) and arm L (lean) differ, on one slice.

  python -I lc_base_score.py <slice S40|H40|H20> <tag>      (reads the two full runs <tag>_<slice>_C_n<N> and <tag>_<slice>_L_n<N>)

HK-037: message text is read ONLY inside load_nc / load_wsjtx (as a dedup key, never stored or printed); every output is a count, a number or a stamp.
The WSJT-X decode list of a cycle is rebuilt exactly as the harness builds it (LoadWsjtx: 'Rx' 'FT8', integer SNR and frequency, file order), so the
harness's matched.csv indices (stamp, wsjtx_idx) refer to the same list. Everything below is derived from that list's numbers (SNR, frequency).
"""
import csv
import json
import os
import sys

SC = r"D:\Projects\claude\_qa-scratch"
ART = r"D:\Projects\claude\OpenWSFZ\artefacts"
RUNS = SC + r"\lc-base\runs"
FOLDERS = {"S40": "20261114_2312_endurance_run-gathered", "H40": "20261028_2233_endurance_run-gathered", "H20": "20260808_live_run_0016-8080"}
S40_DIRS = {"C": SC + r"\dr0\full_A6_n170", "L": SC + r"\dr2e\threads16_L5_n170"}   # DR-0's A6 (shipped 66b3ddf1) and DR-2e's L5 (fc4fb788)
CROWD_HZ = 50                                            # spec 5.2: another WSJT-X decode within +-50 Hz in the same cycle
# Spec 5.2 SNR bands (dB), WSJT-X's own SNR field: >= -10, -10 to -15, -15 to -18, -18 to -21, < -21. Each band includes its upper edge's lower neighbour:
# [-10, inf), [-15, -10), [-18, -15), [-21, -18), (-inf, -21).
BANDS = [("ge-10", -10, 10**6), ("-10..-15", -15, -10), ("-15..-18", -18, -15), ("-18..-21", -21, -18), ("lt-21", -10**6, -21)]
assert [b[0] for b in BANDS][0] == "ge-10" and len(BANDS) == 5


def band_of(snr):
    for name, lo, hi in BANDS:
        if lo <= snr < hi:
            return name
    raise ValueError(snr)


def load_wsjtx(path, stamps):
    out = {s: [] for s in stamps}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line[:13] not in out:
                continue
            f = line.split(" ")
            f = [x for x in f if x]
            if len(f) < 8 or f[2] != "Rx" or f[3] != "FT8":
                continue
            try:
                snr, freq = int(f[4]), int(f[6])
            except ValueError:
                continue
            out[f[0]].append((snr, freq))                  # numbers only; the text (f[7:]) is dropped here
    return out


def load_matched(d):
    m = {}
    with open(os.path.join(d, "matched.csv"), newline="") as fh:
        for row in csv.DictReader(fh):
            v = row["wsjtx_idx"]
            m[row["stamp"]] = {int(x) for x in v.split(";")} if v else set()
    mb = {}
    with open(os.path.join(d, "matchedbatch.csv"), newline="") as fh:
        for row in csv.DictReader(fh):
            v = row["wsjtx_idx_batch"]
            if v:
                for x in v.split(";"):
                    j, k = x.split(":")
                    mb[(row["stamp"], int(j))] = int(k)
    return m, mb


def load_nc(d):
    """Our decodes, one per distinct (stamp, text), as numbers only: (stamp, kind, matched, freq, snr, same_text_elsewhere, path, ap)."""
    rows, seen = [], set()
    with open(os.path.join(d, "nc.tsv"), encoding="utf-8", errors="replace") as fh:
        for line in fh:
            c = line.rstrip("\n").split("\t")
            if len(c) < 11:
                continue
            key = (c[0], c[10])
            if key in seen:
                continue
            seen.add(key)
            ap = int(c[11]) if len(c) > 11 and c[11].lstrip("-").isdigit() else 0
            rows.append((c[0], int(c[1]), int(c[2]), int(c[3]), int(c[5]), int(c[6]), int(c[9]), ap))
    return rows


def same_text_other_freq(d):
    """Our decodes WSJT-X did not corroborate (not matched within 10 Hz) whose text WSJT-X decoded in the same cycle at another frequency.
    Numbers only: (batch kind, path, apKind, smallest frequency offset in Hz to a WSJT-X decode of the same text, our SNR estimate)."""
    rows, seen = [], set()
    with open(os.path.join(d, "nc.tsv"), encoding="utf-8", errors="replace") as fh:
        for line in fh:
            c = line.rstrip("\n").split("\t")
            if len(c) < 11:
                continue
            key = (c[0], c[10])
            if key in seen:
                continue
            seen.add(key)
            if c[2] == "0" and c[6] == "1":
                ap = int(c[11]) if len(c) > 11 and c[11].lstrip("-").isdigit() else 0
                rows.append([int(c[1]), int(c[9]), ap, int(c[7]), int(c[5])])
    return rows


def per_cycle_last_ms(d):
    out = {}
    with open(os.path.join(d, "run.csv"), newline="") as fh:
        for row in csv.DictReader(fh):
            tbs = [float(row[k]) for k in row if k.startswith("tb") and k.endswith("_ms") and row[k] not in ("", None)]
            out[row["stamp"]] = max(tbs) if tbs else -1.0
    return out


def crowded(wl, j):
    f = wl[j][1]
    return any(i != j and abs(wl[i][1] - f) <= CROWD_HZ for i in range(len(wl)))


def main():
    sl, tag = sys.argv[1], sys.argv[2]
    dirs = {}
    if sl == "S40":                                         # reused, not re-run (spec 3): DR-0's A6 and DR-2e's L5 per-row files, 170 cycles
        assert tag == "reuse"
        dirs = dict(S40_DIRS)
    else:
        for arm in ("C", "L"):
            cand = [x for x in os.listdir(RUNS) if x.startswith("%s_%s_%s_n" % (tag, sl, arm))]
            assert len(cand) == 1, cand
            dirs[arm] = os.path.join(RUNS, cand[0])
    arms = {a: json.load(open(os.path.join(dirs[a], "arm.json"))) for a in dirs}
    assert arms["C"]["cycles"] == arms["L"]["cycles"]
    sels = {a: json.load(open(os.path.join(dirs[a], "sel.json"))) for a in dirs}
    stamps = list(sels["C"]["runs"][sels["C"]["run"]]["FULL"])
    assert stamps == list(sels["L"]["runs"][sels["L"]["run"]]["FULL"]) and len(stamps) == arms["C"]["cycles"]
    arms["C"]["first_cycle"], arms["C"]["last_cycle"] = stamps[0], stamps[-1]
    wl = load_wsjtx(os.path.join(ART, FOLDERS[sl], "wsjt-x", "ALL.TXT"), stamps)
    n_w_list = sum(len(v) for v in wl.values())

    M, MB, NC, LAST = {}, {}, {}, {}
    for a in dirs:
        M[a], MB[a] = load_matched(dirs[a])
        NC[a] = load_nc(dirs[a])
        LAST[a] = per_cycle_last_ms(dirs[a])

    # --- 5.2 items 1 and 2: the WSJT-X decodes by who found them, split by SNR band and crowding -----------------------------------------------------------
    cells = {}                                              # (band, crowded) -> {both, c_only, l_only, neither}
    total = {"both": 0, "c_only": 0, "l_only": 0, "neither": 0}
    per_cycle = {}
    for s in stamps:
        w = wl[s]
        mc, ml = M["C"].get(s, set()), M["L"].get(s, set())
        pc = {"w": len(w), "c": len(mc), "l": len(ml)}
        per_cycle[s] = pc
        for j in range(len(w)):
            k = "both" if (j in mc and j in ml) else "c_only" if j in mc else "l_only" if j in ml else "neither"
            key = (band_of(w[j][0]), "crowded" if crowded(w, j) else "alone")
            cells.setdefault(key, {"both": 0, "c_only": 0, "l_only": 0, "neither": 0})[k] += 1
            total[k] += 1
    assert sum(total.values()) == n_w_list
    assert sum(total["both"] + total["c_only"] for _ in [0]) == sum(len(M["C"].get(s, ())) for s in stamps)
    assert total["both"] + total["l_only"] == sum(len(M["L"].get(s, ())) for s in stamps)

    # --- 5.2 item 3: matched decodes by origin (batch kind, path, apKind) ---------------------------------------------------------------------------------------
    origin = {}
    for a in ("C", "L"):
        o = {}
        for (s, kind, matched, freq, snr, same, path, ap) in NC[a]:
            if matched:
                o[(kind, path, ap)] = o.get((kind, path, ap), 0) + 1
        origin[a] = {"%d/%d/%d" % k: v for k, v in sorted(o.items())}
    by_batch = {a: {} for a in ("C", "L")}
    for a in ("C", "L"):
        for (s, j), k in MB[a].items():
            by_batch[a][k] = by_batch[a].get(k, 0) + 1
        by_batch[a] = {str(k): v for k, v in sorted(by_batch[a].items())}

    # --- 5.2 item 4: our decodes WSJT-X did not corroborate ("ours_only"), split the same way; SNR is OUR estimate for these rows ------------------------------
    ours_only = {}
    for a in ("C", "L"):
        cells_o = {}
        same_elsewhere = 0
        n_o = 0
        for (s, kind, matched, freq, snr, same, path, ap) in NC[a]:
            if matched:
                continue
            n_o += 1
            same_elsewhere += 1 if same else 0
            w = wl[s]
            crowd = any(abs(f - freq) <= CROWD_HZ for (_, f) in w)
            key = "%s|%s" % (band_of(snr), "crowded" if crowd else "alone")
            cells_o[key] = cells_o.get(key, 0) + 1
        ours_only[a] = {"n": n_o, "same_text_decoded_elsewhere_by_wsjtx": same_elsewhere, "cells": cells_o}

    # ours rows only one arm has is not computed (text is needed to pair them and must not leave the loaders); the counts above are the spec's.
    res = {"slice": sl, "tag": tag, "cycles": arms["C"]["cycles"], "first_cycle": stamps[0], "last_cycle": stamps[-1],
           "arm": arms, "wsjtx_lines_stamped": arms["C"]["wsjtx_decodes"], "wsjtx_list_parsed": n_w_list,
           "overlap": total, "cells": {"%s|%s" % k: v for k, v in sorted(cells.items())},
           "origin_kind_path_ap": origin, "matched_by_batch_kind": by_batch, "ours_only": ours_only,
           "same_text_other_freq": {a: same_text_other_freq(dirs[a]) for a in dirs},
           "per_cycle": per_cycle, "last_ms": LAST}
    out = os.path.join(SC, "lc-base", "score_%s_%s.json" % (tag, sl))
    json.dump(res, open(out, "w"))
    print(json.dumps({k: res[k] for k in ("slice", "cycles", "wsjtx_lines_stamped", "wsjtx_list_parsed", "overlap", "matched_by_batch_kind", "origin_kind_path_ap")}, indent=1))
    print({a: ours_only[a]["n"] for a in ours_only})


if __name__ == "__main__":
    main()
