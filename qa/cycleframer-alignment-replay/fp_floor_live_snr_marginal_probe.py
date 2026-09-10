"""Drafting probe (HK-021 sibling (q)): does the proposed predicate MOVE?

Outcome-BLIND by construction: computes ONLY the marginal distribution of
OpenWSFZ's reported SNR. Does NOT join against the reference decoder, so it
cannot see the corroborated/uncorroborated split that the arm's row turns on.

Prints aggregate counts only -- no message text (NFR-021).
"""
import sys
from collections import Counter
from pathlib import Path

# excess = Snr + 26.5  (spec 2026-09-03-1616 §2.2)
# filter removes excess < T = 2.622  <=>  Snr < -23.878  <=>  Snr <= -24 (integer readout)
T_EXCESS = 2.622
SNR_CUT = T_EXCESS - 26.5  # -23.878

def snrs(path):
    out = []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            f = line.split()
            if len(f) < 7:
                continue
            try:
                out.append(int(f[4]))
            except ValueError:
                continue
    return out

for run in sys.argv[1:]:
    p = Path(run)
    if not p.exists():
        print(f"MISSING {run}")
        continue
    vals = snrs(p)
    if not vals:
        print(f"EMPTY   {run}")
        continue
    hist = Counter(vals)
    below = sum(n for s, n in hist.items() if s < SNR_CUT)
    print(f"\n=== {run}")
    print(f"n decodes                = {len(vals)}")
    print(f"min / max reported SNR   = {min(vals)} / {max(vals)}")
    print(f"SNR cut (excess {T_EXCESS} dB) = {SNR_CUT:.3f}  => removes SNR <= -24")
    print(f"decodes at or below cut  = {below}  ({100.0*below/len(vals):.4f}%)")
    print("low tail, SNR -30..-17:")
    for s in range(-30, -16):
        if hist.get(s):
            mark = "  <-- REMOVED" if s < SNR_CUT else ""
            print(f"   {s:>4} dB : {hist[s]:>7}{mark}")
