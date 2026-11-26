#!/usr/bin/env python3
"""LC-BASE follow-up (Architect, 2026-11-26): for lean's 'same text at another frequency' rows, is lean's frequency ABOVE or BELOW WSJT-X's?

  python -I lc_base_sign.py

HK-037: message text is read ONLY inside this function (to pair a row of ours with WSJT-X's decode of the same text in the same cycle) and is never stored or printed;
the output is counts and a histogram of signed offsets. Pairing rule as the harness's: same text (right-trimmed), same cycle. Rows = lean's decodes not corroborated
(not matched within 10 Hz) whose text WSJT-X decoded in that cycle. offset = our frequency minus WSJT-X's frequency of the nearest same-text decode (Hz).
"""
import json
import os
from collections import Counter

SC = r"D:\Projects\claude\_qa-scratch"
ART = r"D:\Projects\claude\OpenWSFZ\artefacts"
RUNS = {"S40": (SC + r"\dr2e\threads16_L5_n170", "20261114_2312_endurance_run-gathered"),
        "H40": (SC + r"\lc-base\runs\full_H40_L_n240", "20261028_2233_endurance_run-gathered")}
EXPECT = {"S40": 14, "H40": 10}                                # the counts of the report's section 5.1, as assertions


def wsjtx_by_stamp(path, stamps):
    out = {s: [] for s in stamps}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line[:13] not in out:
                continue
            f = [x for x in line.split(" ") if x]
            if len(f) < 8 or f[2] != "Rx" or f[3] != "FT8":
                continue
            try:
                freq = int(f[6])
                int(f[4])
            except ValueError:
                continue
            out[f[0]].append((freq, " ".join(f[7:]).strip()))   # text kept in memory only, inside this function
    return out


def main():
    res = {}
    for name, (d, folder) in RUNS.items():
        stamps = set(json.load(open(os.path.join(d, "sel.json")))["runs"][json.load(open(os.path.join(d, "sel.json")))["run"]]["FULL"])
        w = wsjtx_by_stamp(os.path.join(ART, folder, "wsjt-x", "ALL.TXT"), stamps)
        offs, seen = [], set()
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
                    mine = int(c[3])
                    cands = [f for (f, t) in w.get(c[0], []) if t == c[10].rstrip()]
                    assert cands, "same-text row without a WSJT-X partner"
                    near = min(cands, key=lambda f: abs(f - mine))
                    offs.append(mine - near)
        assert len(offs) == EXPECT[name], (name, len(offs))
        res[name] = {"n": len(offs), "above": sum(1 for o in offs if o > 0), "below": sum(1 for o in offs if o < 0), "zero": sum(1 for o in offs if o == 0),
                     "signed_offsets_hz_sorted": sorted(offs), "histogram": dict(sorted(Counter(offs).items()))}
    json.dump(res, open(os.path.join(SC, "lc-base", "sign_same_text.json"), "w"), indent=1)
    for k, v in res.items():
        print(k, {x: v[x] for x in ("n", "above", "below", "zero")}, v["histogram"])


if __name__ == "__main__":
    main()
