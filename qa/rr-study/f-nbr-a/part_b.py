"""F-NBR-A Part B (gated, independent of Gate A) -- how often is the pass-1
suppression stage active in production?

Population: the OpenWSFZ leg of the LIVE 20260803_live_run_1713 corpus (ROW 0e
verified this is the archived corpus copy, not a shared/production path, mtime
predates this session).

NFR-021: reads ONLY the SNR field (index [4]) and the cycle timestamp (index
[0], needed for clustering) from each ALL.TXT line. message_text (index [7:])
is never read, stored, or emitted anywhere -- not even transiently -- per the
spec's Sec.2.2 privacy instruction.

factor_i = 1 - clamp( (snr_i - (-5)) / (15 - (-5)), 0, 1 )   [ft8_shim.c:537-538]
Z        = fraction of decodes with factor_i >= 0.99   (effectively zero suppression)
Abar     = mean(1 - factor_i)                          (mean attenuation)

Clustering (HK-021(i)): decodes within one cycle are NOT independent. Cluster-
bootstrap by cycle timestamp, N_BOOT=2000, seed=20260823. Report CLUSTER counts
alongside row counts (the board's own ~3.8x CI-error precedent).
"""
from __future__ import annotations

import os
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

LIVE_ALL_TXT = os.path.join(REPO_ROOT, "artefacts", "20260803_live_run_1713", "owsfz", "ALL.TXT")

K_SOFT_SUPP_SNR_MIN_DB = -5.0   # ft8_shim.c:537
K_SOFT_SUPP_SNR_MAX_DB = 15.0   # ft8_shim.c:538
Z_INERT_THRESHOLD = 0.99        # "effectively zero suppression"
N_BOOT = 2000
BOOTSTRAP_SEED = 20260823

# ROW 4.2 hand-check: a known row from LIVE_ALL_TXT, verified by inspection,
# asserted against the parse before computing anything (spec Sec.4.2's own
# mandatory guard against the [5]/[6] DT/freq field-order inversion).
_HAND_CHECK_LINE = "260803_171330     14.074 Rx FT8    -11  1.1 2194 CQ BG7BMG OL66"
_HAND_CHECK_EXPECTED_SNR = -11
_HAND_CHECK_EXPECTED_DT = 1.1
_HAND_CHECK_EXPECTED_FREQ = 2194


def _parse_fields(line: str):
    """Returns (ts, snr, dt, freq) reading ONLY the numeric fields -- never
    joins or returns message_text (NFR-021)."""
    parts = line.split()
    ts = parts[0]
    snr = int(parts[4])
    dt = float(parts[5])
    freq = int(parts[6])
    return ts, snr, dt, freq


def _assert_field_order():
    ts, snr, dt, freq = _parse_fields(_HAND_CHECK_LINE)
    assert snr == _HAND_CHECK_EXPECTED_SNR, (snr, _HAND_CHECK_EXPECTED_SNR)
    assert abs(dt - _HAND_CHECK_EXPECTED_DT) < 1e-9, (dt, _HAND_CHECK_EXPECTED_DT)
    assert freq == _HAND_CHECK_EXPECTED_FREQ, (freq, _HAND_CHECK_EXPECTED_FREQ)


def _factor(snr_db: float) -> float:
    x = (snr_db - K_SOFT_SUPP_SNR_MIN_DB) / (K_SOFT_SUPP_SNR_MAX_DB - K_SOFT_SUPP_SNR_MIN_DB)
    x = min(1.0, max(0.0, x))
    return 1.0 - x


def load_live_snrs_by_cycle() -> dict:
    """Returns {cycle_ts: [snr, snr, ...]} -- counts and SNRs only, no text."""
    by_cycle: dict = defaultdict(list)
    with open(LIVE_ALL_TXT, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.strip():
                continue
            ts, snr, dt, freq = _parse_fields(line)
            by_cycle[ts].append(snr)
    return dict(by_cycle)


def cluster_bootstrap(by_cycle: dict, log) -> dict:
    cycle_ids = sorted(by_cycle.keys())
    n_clusters = len(cycle_ids)
    n_rows = sum(len(v) for v in by_cycle.values())
    log("Part B: %d clusters (cycles), %d rows (decodes) in the live leg" % (n_clusters, n_rows))

    all_snrs = np.concatenate([np.asarray(by_cycle[c], dtype=float) for c in cycle_ids])
    all_factors = np.array([_factor(s) for s in all_snrs])
    Z_point = float(np.mean(all_factors >= Z_INERT_THRESHOLD))
    Abar_point = float(np.mean(1.0 - all_factors))

    # SNR histogram, counts only (no text) -- 1 dB bins.
    lo_bin, hi_bin = int(np.floor(all_snrs.min())), int(np.ceil(all_snrs.max()))
    bins = np.arange(lo_bin, hi_bin + 2)
    hist, edges = np.histogram(all_snrs, bins=bins)
    snr_histogram = {int(edges[i]): int(hist[i]) for i in range(len(hist)) if hist[i] > 0}

    rng = np.random.default_rng(BOOTSTRAP_SEED)
    cluster_factor_lists = [np.array([_factor(s) for s in by_cycle[c]]) for c in cycle_ids]
    cluster_sizes = np.array([len(x) for x in cluster_factor_lists])

    boot_Z = np.empty(N_BOOT)
    boot_Abar = np.empty(N_BOOT)
    idx_range = np.arange(n_clusters)
    for b in range(N_BOOT):
        picks = rng.choice(idx_range, size=n_clusters, replace=True)
        factors = np.concatenate([cluster_factor_lists[i] for i in picks])
        boot_Z[b] = np.mean(factors >= Z_INERT_THRESHOLD)
        boot_Abar[b] = np.mean(1.0 - factors)

    Z_lo, Z_hi = float(np.percentile(boot_Z, 2.5)), float(np.percentile(boot_Z, 97.5))
    Abar_lo, Abar_hi = float(np.percentile(boot_Abar, 2.5)), float(np.percentile(boot_Abar, 97.5))

    log("Part B: Z (fraction factor>=0.99) = %.4f  95%% CI [%.4f, %.4f]" % (Z_point, Z_lo, Z_hi))
    log("Part B: Abar (mean attenuation)    = %.4f  95%% CI [%.4f, %.4f]" % (Abar_point, Abar_lo, Abar_hi))

    return {
        "n_clusters": n_clusters,
        "n_rows": n_rows,
        "Z_point": Z_point, "Z_ci_lo": Z_lo, "Z_ci_hi": Z_hi,
        "Abar_point": Abar_point, "Abar_ci_lo": Abar_lo, "Abar_ci_hi": Abar_hi,
        "snr_histogram": snr_histogram,
        "n_boot": N_BOOT, "bootstrap_seed": BOOTSTRAP_SEED,
    }


def run_part_b(log) -> dict:
    _assert_field_order()
    log("Part B: field-order hand-check PASSED (SNR=[4], DT=[5], freq=[6])")
    by_cycle = load_live_snrs_by_cycle()
    return cluster_bootstrap(by_cycle, log)


if __name__ == "__main__":
    def _log(msg):
        print(msg)
    result = run_part_b(_log)
    print({k: v for k, v in result.items() if k != "snr_histogram"})
