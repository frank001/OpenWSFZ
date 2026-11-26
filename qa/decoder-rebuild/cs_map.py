#!/usr/bin/env python3
"""CS-MAP (spec-cs-map-crowded-misses.md): what the crowded WSJT-X decodes that lean misses look like. Data on disk only: no replay, no build.

  python -I cs_map.py        -> D:\\Projects\\claude\\_qa-scratch\\lc-base\\cs_map.json (counts only)

Per WSJT-X decode T of a slice: its nearest WSJT-X neighbour N in the same cycle (smallest |df|; ties go to the lower list index), df = f(N) - f(T),
dSNR = SNR(N) - SNR(T), dDT = DT(N) - DT(T), n50 = the number of other WSJT-X decodes within +-50 Hz of T. Only crowded T (n50 >= 1) are tabulated.
Match status comes from the harness's matched.csv / matchedbatch.csv (LC-BASE's rule: same text, same cycle, within 10 Hz, one-to-one), so NO message text is read
here: the WSJT-X list is rebuilt from ALL.TXT with the harness's own parser (Rx, FT8, integer SNR and frequency, file order) keeping only numbers.
"""
import csv
import json
import os

SC = r"D:\Projects\claude\_qa-scratch"
ART = r"D:\Projects\claude\OpenWSFZ\artefacts"
SLICES = {
    "S40": ({"C": SC + r"\dr0\full_A6_n170", "L": SC + r"\dr2e\threads16_L5_n170"}, "20261114_2312_endurance_run-gathered"),
    "H40": ({"C": SC + r"\lc-base\runs\full_H40_C_n240", "L": SC + r"\lc-base\runs\full_H40_L_n240"}, "20261028_2233_endurance_run-gathered"),
    "H20": ({"C": SC + r"\lc-base\runs\full_H20_C_n240", "L": SC + r"\lc-base\runs\full_H20_L_n240"}, "20260808_live_run_0016-8080"),
}
DF_BINS = [("<6.25", 0, 6.25), ("6.25-12.5", 6.25, 12.5), ("12.5-25", 12.5, 25.0), ("25-50", 25.0, 50.0001)]          # |dF| in Hz, lower edge included
DSNR_BINS = [("weaker>3", -10**6, -3), ("within3", -3, 3.0001), ("stronger3-10", 3.0001, 10.0001), ("stronger>10", 10.0001, 10**6)]   # dSNR in dB: -3 and +3 belong to 'within3'
DT_BINS = [("<0.16", 0, 0.16), ("0.16-0.5", 0.16, 0.5), (">0.5", 0.5, 10**6)]
N50_BINS = [("1", 1, 2), ("2", 2, 3), ("3+", 3, 10**6)]
CROWD_HZ = 50
assert DF_BINS[0][1] == 0 and DF_BINS[-1][2] > CROWD_HZ


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
                snr, freq, dt = int(f[4]), int(f[6]), float(f[5])
            except ValueError:
                continue
            out[f[0]].append((snr, freq, dt))                 # numbers only; the message (f[7:]) is dropped here
    return out


def load_matched(d):
    m, mb = {}, {}
    with open(os.path.join(d, "matched.csv"), newline="") as fh:
        for row in csv.DictReader(fh):
            v = row["wsjtx_idx"]
            m[row["stamp"]] = {int(x) for x in v.split(";")} if v else set()
    with open(os.path.join(d, "matchedbatch.csv"), newline="") as fh:
        for row in csv.DictReader(fh):
            for x in (row["wsjtx_idx_batch"].split(";") if row["wsjtx_idx_batch"] else []):
                j, k = x.split(":")
                mb[(row["stamp"], int(j))] = int(k)
    return m, mb


def binof(bins, v):
    for name, lo, hi in bins:
        if lo <= v < hi:
            return name
    raise ValueError(v)


class Tab:
    """count of crowded T and misses by L and by C per key."""
    def __init__(self):
        self.d = {}

    def add(self, key, missL, missC):
        c = self.d.setdefault(key, [0, 0, 0])
        c[0] += 1
        c[1] += missL
        c[2] += missC

    def out(self):
        return {k: {"n": v[0], "missL": v[1], "missC": v[2]} for k, v in self.d.items()}


def main():
    res = {}
    for name, (dirs, folder) in SLICES.items():
        sel = json.load(open(os.path.join(dirs["C"], "sel.json")))
        stamps = list(sel["runs"][sel["run"]]["FULL"])
        w = load_wsjtx(os.path.join(ART, folder, "wsjt-x", "ALL.TXT"), stamps)
        M, MB = {}, {}
        for a in "CL":
            M[a], MB[a] = load_matched(dirs[a])
        t_df, t_snr, t_nbl, t_dt, t_n50, t_2d = Tab(), Tab(), Tab(), Tab(), Tab(), Tab()
        n_all = n_crowded = 0
        key_n = key_nbr_decoded = 0                             # crowded T missed by L; of those, N decoded by L
        key_by_batch = {}
        key_snr_nbr_decoded = {}                                # L's crowded misses whose neighbour L decoded, by dSNR bin
        for s in stamps:
            lst = w[s]
            ml, mc = M["L"].get(s, set()), M["C"].get(s, set())
            for j, (snr, f, dt) in enumerate(lst):
                n_all += 1
                others = [(abs(lst[i][1] - f), i) for i in range(len(lst)) if i != j]
                n50 = sum(1 for d, _ in others if d <= CROWD_HZ)
                if n50 < 1:
                    continue
                n_crowded += 1
                _, ni = min(others)                             # nearest neighbour: smallest |df|, ties to the lower index
                nsnr, nf, ndt = lst[ni][0], lst[ni][1], lst[ni][2]
                df, dsnr, ddt = nf - f, nsnr - snr, ndt - dt
                missL, missC = int(j not in ml), int(j not in mc)
                n_by_l = ni in ml
                nb = MB["L"].get((s, ni), 0) if n_by_l else 0
                dfk, dsk = binof(DF_BINS, abs(df)), binof(DSNR_BINS, dsnr)
                t_df.add(dfk, missL, missC)
                t_snr.add(dsk, missL, missC)
                t_nbl.add("N decoded by L, batch %d" % nb if n_by_l else "N not decoded by L", missL, missC)
                t_dt.add(binof(DT_BINS, abs(ddt)), missL, missC)
                t_n50.add(binof(N50_BINS, n50), missL, missC)
                t_2d.add("%s|%s" % (dfk, dsk), missL, missC)
                if missL:
                    key_n += 1
                    key_nbr_decoded += int(n_by_l)
                    if n_by_l:
                        key_by_batch[nb] = key_by_batch.get(nb, 0) + 1
                        key_snr_nbr_decoded[dsk] = key_snr_nbr_decoded.get(dsk, 0) + 1
        res[name] = {"cycles": len(stamps), "wsjtx_decodes": n_all, "crowded": n_crowded,
                     "by_dF": t_df.out(), "by_dSNR": t_snr.out(), "by_N_decoded": t_nbl.out(), "by_dDT": t_dt.out(), "by_n50": t_n50.out(), "dF_x_dSNR": t_2d.out(),
                     "key": {"crowded_missed_by_L": key_n, "neighbour_decoded_by_L": key_nbr_decoded, "by_batch": {str(k): v for k, v in sorted(key_by_batch.items())},
                                "nbr_decoded_by_dSNR": dict(sorted(key_snr_nbr_decoded.items()))}}
        assert sum(v["n"] for v in res[name]["by_dF"].values()) == n_crowded
    json.dump(res, open(os.path.join(SC, "lc-base", "cs_map.json"), "w"), indent=1)
    for k, v in res.items():
        print(k, v["wsjtx_decodes"], "crowded", v["crowded"], "key", v["key"])


if __name__ == "__main__":
    main()
