"""SNR-gap mix check, extended to the third leg (2026-09-25, direct-CODEC repeat).
Same methodology as the prior 2-run scratchpad (snr_gap_mix.py), reused verbatim for the
binning/mix-decomposition logic. Aggregates only (NFR-021 / HK-037): match_pairs() already
discards message text.
"""
import sys, statistics as st
from collections import defaultdict
sys.path.insert(0, r"D:\Projects\claude\OpenWSFZ\worktrees\qa\qa\endurance")
import anova_common as ac

ROOT = r"D:\Projects\claude\OpenWSFZ\worktrees\qa\artefacts"
RUNS = {"0922_VM": ROOT + r"\20260922_2056_endurance_run-gathered",
        "0923_DIRECT": ROOT + r"\20260923_1730_endurance_run-gathered",
        "0925_DIRECT": ROOT + r"\20260925_2010_endurance_run-gathered"}


def binof(x):  # 3 dB bins of WSJT-X SNR, clamped
    return max(-24, min(12, int((x // 3) * 3)))


res = {}
for name, d in RUNS.items():
    a = ac.parse_all_txt(d + r"\owsfz\ALL.TXT")
    b = ac.parse_all_txt(d + r"\wsjt-x\ALL.TXT")
    pairs = ac.match_pairs(a, b)
    bins = defaultdict(list)
    for p in pairs:
        g = p["a_snr"] - p["b_snr"]
        bins[binof(p["b_snr"])].append(g)
    gaps = [p["a_snr"] - p["b_snr"] for p in pairs]
    res[name] = {"n": len(pairs), "mean": st.fmean(gaps),
                 "bins": {k: (len(v), st.fmean(v)) for k, v in bins.items()},
                 "ref_mean_snr": st.fmean(p["b_snr"] for p in pairs)}
    print(f"{name}: n={len(pairs)} mean gap={res[name]['mean']:+.3f} dB  mean WSJT-X SNR={res[name]['ref_mean_snr']:+.2f}")


def decompose(A, B, label_a, label_b):
    common = [k for k in sorted(set(A["bins"]) | set(B["bins"])) if k in A["bins"] and k in B["bins"]]
    wA = sum(A["bins"][k][0] for k in common)
    wB = sum(B["bins"][k][0] for k in common)
    B_on_Amix = sum(A["bins"][k][0] * B["bins"][k][1] for k in common) / wA
    A_on_Bmix = sum(B["bins"][k][0] * A["bins"][k][1] for k in common) / wB
    A_own = sum(A["bins"][k][0] * A["bins"][k][1] for k in common) / wA
    B_own = sum(B["bins"][k][0] * B["bins"][k][1] for k in common) / wB
    print(f"\n=== {label_a} -> {label_b} ===")
    print("bin(WSJT-X SNR)  nA  shareA  gapA   nB  shareB  gapB   dGap")
    for k in sorted(set(A["bins"]) | set(B["bins"])):
        na, ga = A["bins"].get(k, (0, float("nan")))
        nb, gb = B["bins"].get(k, (0, float("nan")))
        print(f"{k:+4d}..{k+3:+4d}  {na:6d} {na/A['n']:.3f} {ga:+.2f}  {nb:6d} {nb/B['n']:.3f} {gb:+.2f}  {gb-ga:+.2f}")
    print(f"raw move                : {B['mean']-A['mean']:+.3f} dB")
    print(f"within-bin move @A mix  : {B_on_Amix-A_own:+.3f} dB")
    print(f"within-bin move @B mix  : {B_own-A_on_Bmix:+.3f} dB")
    print(f"mix-only move           : {A_on_Bmix-A_own:+.3f} dB")


decompose(res["0922_VM"], res["0923_DIRECT"], "0922_VM", "0923_DIRECT")
decompose(res["0923_DIRECT"], res["0925_DIRECT"], "0923_DIRECT", "0925_DIRECT")
decompose(res["0922_VM"], res["0925_DIRECT"], "0922_VM", "0925_DIRECT")
