#!/usr/bin/env python3
"""LC-BASE slice preparation (spec-lc-base-lean-vs-classic.md section 3): finds the busiest 240 contiguous cycles of a night.

Same method as test-set.md: a per-cycle count of the WSJT-X ALL.TXT lines stamped with the cycle (line[:13]); a window is eligible only if
all of its 240 cycles are exactly 15 s apart AND the owsfz/wav file exists for every one of them AND the cycle before the window (the warm-up) exists.
Writes the selection files (cycle stamps only, no text) to _qa-scratch/lc-base/. Prints aggregates only (HK-037: no message text is read out of the counting loop).

  python -I lc_base_prep.py
"""
import datetime as dt
import json
import os
from collections import Counter

ART = r"D:\Projects\claude\OpenWSFZ\artefacts"
OUT = r"D:\Projects\claude\_qa-scratch\lc-base"
WINDOW = 240
NIGHTS = {
    # slice: (artefacts folder, expected start (None = to be found), expected count (None = to be found))
    "H40": ("20261028_2233_endurance_run-gathered", "261029_021045", 8983),     # test-set.md: QA's busiest-hour search, 40 m
    "H20": ("20260808_live_run_0016-8080", None, None),                          # to be found by this script
}
assert WINDOW == 240


def parse(stamp):
    return dt.datetime.strptime(stamp, "%y%m%d_%H%M%S")


def main():
    os.makedirs(OUT, exist_ok=True)
    summary = {}
    for name, (folder, exp_start, exp_count) in NIGHTS.items():
        g = os.path.join(ART, folder)
        wavs = sorted(f[:-4] for f in os.listdir(os.path.join(g, "owsfz", "wav")) if f.endswith(".wav") and len(f) == 17)
        cnt = Counter()
        with open(os.path.join(g, "wsjt-x", "ALL.TXT"), encoding="utf-8", errors="replace") as fh:
            for line in fh:
                cnt[line[:13]] += 1                       # the stamp only; nothing else of the line is kept
        t = [parse(s) for s in wavs]
        best = None
        # prefix sums over the wav list; a window [i, i+240) is contiguous iff t[i+239] - t[i] == 239 * 15 s (the list is sorted and distinct)
        pre = [0]
        for s in wavs:
            pre.append(pre[-1] + cnt.get(s, 0))
        step = dt.timedelta(seconds=15)
        for i in range(1, len(wavs) - WINDOW + 1):          # i >= 1: the warm-up cycle wavs[i-1] must exist and be the cycle just before
            if t[i + WINDOW - 1] - t[i] != step * (WINDOW - 1):
                continue
            if t[i] - t[i - 1] != step:
                continue
            total = pre[i + WINDOW] - pre[i]
            if best is None or total > best[0]:
                best = (total, i)
        total, i = best
        start = wavs[i]
        if exp_start is not None:
            assert start == exp_start and total == exp_count, "%s: found %s %d, test-set.md says %s %d" % (name, start, total, exp_start, exp_count)
        cycles = wavs[i:i + WINDOW]
        sel = {"note": "LC-BASE %s" % name, "run": folder.replace("_endurance_run-gathered", ""), "runs": {}, "outage_dropped": []}
        sel["runs"][sel["run"]] = {"warmup": wavs[i - 1], "FULL": cycles}
        json.dump(sel, open(os.path.join(OUT, "sel_%s.json" % name), "w"))
        summary[name] = {"folder": folder, "wav_files": len(wavs), "start": start, "end": cycles[-1], "warmup": wavs[i - 1],
                         "wsjtx_lines_in_window": total, "cycles_with_zero_wsjtx": sum(1 for s in cycles if cnt.get(s, 0) == 0)}
    json.dump(summary, open(os.path.join(OUT, "slices.json"), "w"), indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
