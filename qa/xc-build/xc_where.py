#!/usr/bin/env python3
"""XC-BUILD lead 1: where do the batch-6 matched rows come from?  COUNTS ONLY (HK-037): WSJT-X's ALL.TXT is read here for SNR and row order, text never kept.
Usage: python -I xc_where.py <chain full dir> <out json>
Bands as the harness: A snr >= 0, B -10..-1, C -15..-11, D < -15 (the xc_count.py rule)."""
from __future__ import annotations

import collections
import csv
import json
import os
import sys

ALLTXT = "D:/Projects/claude/OpenWSFZ/artefacts/20260808_live_run_0016-8080/wsjt-x/ALL.TXT"
EXPECT_B6 = 904          # the first chain's TEST night; None for another night
assert EXPECT_B6 == 904


def band(snr):
    return "A" if snr >= 0 else "B" if snr >= -10 else "C" if snr >= -15 else "D"


def main(root, out, alltxt=ALLTXT):
    mb = {}
    for r in csv.reader(open(os.path.join(root, "ON", "matchedbatch.csv"), encoding="utf-8")):
        if r and r[0] != "stamp":
            mb[r[0]] = {int(a.split(":")[0]): int(a.split(":")[1]) for a in r[1].split(";") if a}
    stamps = [r["stamp"] for r in csv.DictReader(open(os.path.join(root, "ON", "run.csv"), encoding="utf-8"))]
    want, ref = set(stamps), {}
    with open(alltxt, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            f = line.split()
            if len(f) < 8 or f[2] != "Rx" or f[3] != "FT8" or f[0] not in want:
                continue
            try:
                ref.setdefault(f[0], []).append(int(f[4]))
            except ValueError:
                continue
    b6_band, ref_band, on_band = collections.Counter(), collections.Counter(), collections.Counter()
    b6_by_pos = collections.Counter()
    for i, s in enumerate(stamps):
        rows = ref.get(s, [])
        for j, snr in enumerate(rows):
            ref_band[band(snr)] += 1
            b = mb.get(s, {}).get(j)
            if b is not None:
                on_band[band(snr)] += 1
            if b == 6:
                b6_band[band(snr)] += 1
                b6_by_pos[min(i // 100, 9)] += 1
    # the OFF arm's matched rows by band, for the unreached share by band
    mo = {}
    for r in csv.reader(open(os.path.join(root, "OFF", "matchedbatch.csv"), encoding="utf-8")):
        if r and r[0] != "stamp":
            mo[r[0]] = {int(a.split(":")[0]) for a in r[1].split(";") if a}
    off_band = collections.Counter()
    for s in stamps:
        for j, snr in enumerate(ref.get(s, [])):
            if j in mo.get(s, set()):
                off_band[band(snr)] += 1
    res = {"b6_total": sum(b6_band.values()), "b6_by_band": dict(b6_band), "ref_by_band": dict(ref_band),
           "matched_off_by_band": dict(off_band), "matched_on_by_band": dict(on_band),
           "b6_by_100_cycle_block": {str(k): v for k, v in sorted(b6_by_pos.items())},
           "first_100_cycles_b6": b6_by_pos.get(0, 0)}
    res["gain_pp_by_band_of_all_ref"] = {b: 100.0 * (on_band[b] - off_band[b]) / sum(ref_band.values()) for b in "ABCD"}
    res["share_of_unreached_recovered_by_band"] = {b: (on_band[b] - off_band[b]) / max(1, ref_band[b] - off_band[b]) for b in "ABCD"}
    if alltxt == ALLTXT:
        assert res["b6_total"] == EXPECT_B6, res["b6_total"]
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else ALLTXT)
