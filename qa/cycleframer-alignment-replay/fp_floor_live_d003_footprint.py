"""EXPLORATORY refinement. Two corrections to the first pass:

 1. S3b is EXCLUDED and S3 is broken out. S3b shows a uniform -15/-16 dB error on
    100% of rows -- that is the DOCUMENTED modulator positive-DT clamp / WSJT-X DT
    convention defect (MEMORY: "S3 parts 8/9 mislabeled since 2026-06-06"), not a
    noise-floor pathology. Leaving it in contaminates the WIDEBAND control.
 2. Per-scenario breakdown of the quantity that actually matters: a TRUTH-MATCHED
    decode REPORTED at <= -24 dB, i.e. one the proposed filter would destroy.

Aggregates only (NFR-021).
"""
import csv
import glob
from collections import defaultdict

WIDEBAND_CLEAN = {"S1", "S1b", "S2"}      # single-signal, wideband AWGN
SUSPECT        = {"S3", "S3b"}            # wideband but carry the known DT defect
BANDLIMITED    = {"S4", "S7", "S8", "S8HN"}

CUT = -24.0

per = defaultdict(lambda: {"n": 0, "cut": 0, "err": [], "cut_true": []})

for path in glob.glob("qa/rr-study/**/*_matched.csv", recursive=True):
    if ".venv" in path:
        continue
    with open(path, newline="", encoding="utf-8", errors="replace") as fh:
        for r in csv.DictReader(fh):
            if (r.get("appraiser") or "").strip() != "OpenWSFZ":
                continue
            if (r.get("matched") or "").strip() != "True":
                continue
            sid = (r.get("scenario_id") or "").strip()
            try:
                t = float(r["true_snr_db"]); rep = float(r["reported_snr_db"])
            except (ValueError, KeyError, TypeError):
                continue
            d = per[sid]
            d["n"] += 1
            d["err"].append(rep - t)
            if rep <= CUT:
                d["cut"] += 1
                d["cut_true"].append(t)

def grp(sid):
    if sid in WIDEBAND_CLEAN: return "WIDEBAND"
    if sid in SUSPECT:        return "suspect"
    if sid in BANDLIMITED:    return "BANDLIMITED"
    return "other"

print("TRUTH-MATCHED OpenWSFZ decodes REPORTED at <= -24 dB (destroyed by the cut)")
print(f"{'scen':<7}{'group':<13}{'n':>7}{'killed':>8}{'rate':>9}   true-SNR of killed (min/median/max)")
tot = defaultdict(lambda: [0, 0])
for sid in sorted(per, key=lambda s: (grp(s), s)):
    d = per[sid]; g = grp(sid)
    ct = sorted(d["cut_true"])
    rng = f"{ct[0]:.0f} / {ct[len(ct)//2]:.0f} / {ct[-1]:.0f}" if ct else "-"
    print(f"{sid:<7}{g:<13}{d['n']:>7}{d['cut']:>8}{100*d['cut']/d['n']:>8.3f}%   {rng}")
    if g in ("WIDEBAND", "BANDLIMITED"):
        tot[g][0] += d["n"]; tot[g][1] += d["cut"]

print()
for g in ("WIDEBAND", "BANDLIMITED"):
    n, c = tot[g]
    print(f"{g:<12} {c:>5} of {n:>6} truth-matched decodes killed by the cut  ({100*c/n:.3f}%)")

# rule-of-three style read on the wideband zero
n_w = tot["WIDEBAND"][0]
print(f"\nWIDEBAND control is {tot['WIDEBAND'][1]}/{n_w}; 95% upper bound on its true rate "
      f"= {100*3.0/n_w:.3f}% (rule of three)")
