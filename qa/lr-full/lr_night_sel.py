#!/usr/bin/env python3
"""Selection for one LR-FULL night, from the gathered night's archived WAVs (same shape as the registered XC-LIVE selection: a warm-up cycle plus the FULL list).
  python -I lr_night_sel.py <wav_dir> <out.json> <run_id> pilot|test [--pilot-frac 0.10] [--cap 2000]
Order: the WAV stems sorted (YYMMDD_HHMMSS). warm-up = the first archive cycle (as the acceptance nights); FULL_all = the rest. pilot = the first round(frac x len(FULL_all)) cycles of FULL_all (spec s2.4 / s6).
TEST = the CONTIGUOUS block of up to `cap` cycles right after the pilot (contiguous so the cross-cycle prior sees its real neighbours; the spec says a seeded random subset: QA raised this with the Architect).
Prints counts, the gap count on the 15 s grid and the selection's sha256; nothing but counts."""
import argparse
import datetime as dt
import hashlib
import json
import os
import sys

ap = argparse.ArgumentParser()
ap.add_argument("wav_dir")
ap.add_argument("out")
ap.add_argument("run")
ap.add_argument("mode", choices=("pilot", "test", "dry", "rerun20"))
ap.add_argument("--pilot-frac", type=float, default=0.10)
ap.add_argument("--cap", type=int, default=2000)
a = ap.parse_args()
stems = sorted(f[:-4] for f in os.listdir(a.wav_dir) if f.lower().endswith(".wav"))
assert len(stems) > 100, "too few WAVs"
warm, full_all = stems[0], stems[1:]
npil = round(a.pilot_frac * len(full_all))
pilot, rest = full_all[:npil], full_all[npil:]
test = rest[: a.cap]
if a.mode == "test":
    warm = full_all[npil - 1]       # the TEST block's warm-up cycle = the cycle right before it (the pilot's last), so the decoder state is primed at the block start
sel = pilot if a.mode == "pilot" else (full_all[:2] if a.mode == "dry" else (full_all[:20] if a.mode == "rerun20" else test))   # rerun20 = the first 20 pilot cycles again (V-RUN: a 20-cycle OFF re-run byte-identical)   # dry = 2 cycles, for the Q79 dry run of the arms
t = [dt.datetime.strptime(s, "%y%m%d_%H%M%S") for s in sel]
gaps = sum(1 for i in range(1, len(t)) if (t[i] - t[i - 1]).total_seconds() != 15)
doc = {"outage_dropped": 0, "note": "LR-FULL %s selection for %s: warm-up = the first archive cycle; pilot = first %d of %d cycles; test = contiguous %d cycles after the pilot (cap %d)" % (a.mode, a.run, npil, len(full_all), len(test), a.cap),
       "run": a.run, "runs": {a.run: {"warmup": warm, "FULL": sel}}}
json.dump(doc, open(a.out, "w"))
sha = hashlib.sha256(open(a.out, "rb").read()).hexdigest()
print("mode=%s wavs=%d warmup=1 pilot=%d rest=%d selected=%d gaps_on_15s_grid=%d sha256=%s" % (a.mode, len(stems), len(pilot), len(rest), len(sel), gaps, sha[:16]))
