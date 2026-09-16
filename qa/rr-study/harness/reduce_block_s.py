"""E4-BENCH block S (0 dB, descriptive, spec Sec.3.5 A3) -- proper reduction.

Block S was pre-registered as descriptive only (no gate), but nobody had
reduced it into dose-response curves comparable to block P's -- it existed
only as an ad-hoc read of `e4_truth_with_hits.json`. This computes the same
statistics block P's own gate reduction used (paired bootstrap, N_BOOT=2000,
seed=20260915, Bonferroni and 90% intervals per bench spec Sec.3.1), on
block S's 50-trial cells, for both families, and reports them side by side
with block P so a genuine 0 dB vs -8 dB shift is visible rather than asserted.

Usage:
    python harness/reduce_block_s.py [--out <path.json>]

Source: qa/rr-study/e4_truth_with_hits.json (merged truth+hits, both blocks,
already committed data from the 2026-09-15 live E4-BENCH run). No callsigns
or ALL.TXT excerpts in the output -- aggregate counts and statistics only
(NFR-021: this corpus's own contamination tokens, already disposed under
ROW 0e, are never touched here).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

_QA_ROOT = Path(__file__).resolve().parent.parent
if str(_QA_ROOT) not in sys.path:
    sys.path.insert(0, str(_QA_ROOT))

N_BOOT = 2000
BOOT_SEED = 20260915          # bench spec Sec.3.1's own seed
ALPHA = 0.05

FADE_DOSES = [0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0]     # k = 8
DRIFT_DOSES = [0.5, 1.0, 2.0, 4.0, 8.0, 16.0]                  # k = 6, signed in the data


def _load(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _cell_rows(rows: list, family: str, block: str, dose_key) -> list:
    if family == "FADE":
        return [r for r in rows if r["e4_family"] == "FADE" and r["e4_block"] == block
                 and float(r["e4_fade_spread_hz"]) == dose_key]
    # DRIFT: pool the +/- sign pair for a given magnitude (bench spec: "DRIFT
    # signs are 75/75" in block P -- one magnitude, two signed sub-populations).
    return [r for r in rows if r["e4_family"] == "DRIFT" and r["e4_block"] == block
             and abs(float(r["e4_drift_hz"])) == dose_key]


def _reduce_cell(rows: list, seed: int) -> dict:
    hit_o = np.array([1.0 if r["hit_O"] else 0.0 for r in rows])
    hit_w = np.array([1.0 if r["hit_W"] else 0.0 for r in rows])
    n = len(rows)
    r_o = float(np.mean(hit_o))
    r_w = float(np.mean(hit_w))
    delta = float(np.mean(hit_w - hit_o))

    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(N_BOOT, n))
    boot_delta = np.mean(hit_w[idx] - hit_o[idx], axis=1)
    boot_r_o = np.mean(hit_o[idx], axis=1)
    boot_r_w = np.mean(hit_w[idx], axis=1)

    return {
        "n": n, "r_o": r_o, "r_w": r_w, "delta": delta,
        "r_o_95": [float(np.percentile(boot_r_o, 2.5)), float(np.percentile(boot_r_o, 97.5))],
        "r_w_95": [float(np.percentile(boot_r_w, 2.5)), float(np.percentile(boot_r_w, 97.5))],
        "boot_delta_mean": float(np.mean(boot_delta)),
        "p90_lo": float(np.percentile(boot_delta, 5)),
        "p90_hi": float(np.percentile(boot_delta, 95)),
    }


def _bonferroni(cell: dict, k: int, seed: int, rows: list) -> dict:
    hit_o = np.array([1.0 if r["hit_O"] else 0.0 for r in rows])
    hit_w = np.array([1.0 if r["hit_W"] else 0.0 for r in rows])
    n = len(rows)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(N_BOOT, n))
    boot_delta = np.mean(hit_w[idx] - hit_o[idx], axis=1)
    lo_pct = 100.0 * (ALPHA / (2 * k))
    hi_pct = 100.0 * (1.0 - ALPHA / (2 * k))
    return {
        "bonf_lo": float(np.percentile(boot_delta, lo_pct)),
        "bonf_hi": float(np.percentile(boot_delta, hi_pct)),
    }


def reduce_block(rows: list, family: str, block: str, doses: list, k: int, seed_base: int) -> dict:
    out = {}
    for i, dose in enumerate(doses):
        cell_rows = _cell_rows(rows, family, block, dose)
        seed = seed_base + i
        cell = _reduce_cell(cell_rows, seed)
        cell.update(_bonferroni(cell, k, seed, cell_rows))
        out[dose] = cell
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--truth", type=str, default=str(_QA_ROOT / "e4_truth_with_hits.json"))
    ap.add_argument("--out", type=str, default=None)
    args = ap.parse_args()

    rows = _load(args.truth)

    result = {
        "FADE": {
            "block_S_0dB": reduce_block(rows, "FADE", "S", FADE_DOSES, k=8, seed_base=BOOT_SEED),
            "block_P_m8dB": reduce_block(rows, "FADE", "P", FADE_DOSES, k=8, seed_base=BOOT_SEED + 100),
        },
        "DRIFT": {
            "block_S_0dB": reduce_block(rows, "DRIFT", "S", DRIFT_DOSES, k=6, seed_base=BOOT_SEED + 200),
            "block_P_m8dB": reduce_block(rows, "DRIFT", "P", DRIFT_DOSES, k=6, seed_base=BOOT_SEED + 300),
        },
    }

    out_path = args.out or str(_QA_ROOT / "e4_block_s_reduced.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    for fam in ["FADE", "DRIFT"]:
        print(f"=== {fam} ===")
        s = result[fam]["block_S_0dB"]
        p = result[fam]["block_P_m8dB"]
        for dose in sorted(s.keys()):
            cs, cp = s[dose], p[dose]
            print(f"  dose={dose:>5}  S(0dB): n={cs['n']:<3} delta={cs['delta']:+.4f} "
                  f"90%=[{cs['p90_lo']:+.4f},{cs['p90_hi']:+.4f}]   |  "
                  f"P(-8dB): n={cp['n']:<3} delta={cp['delta']:+.4f} "
                  f"90%=[{cp['p90_lo']:+.4f},{cp['p90_hi']:+.4f}]")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
