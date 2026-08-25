"""GAP-CENSUS-A Part C (DESCRIPTIVE -- NOT GATED) -- the residual. Spec Sec.6.

PROHIBITED, permanently: any stratification of bucket C by frequency
separation to a neighbouring decode, under any name (retired spectral-
locality metric, four attempts, zero readings, see closed-arms-prohibitions.md
and BOARD.md). This module contains no such stratification -- SNR stratum,
per-cycle density, and the two named diagnostics only.
"""
from __future__ import annotations

import statistics

# Pinned L1 SNR edges (X1/X2), never re-derived.
L1_SNR_EDGES = [-15.0, -10.0, -5.0, 2.0]

K_MAX_DECODED_CAPS = (340, 540)  # cited caps this diagnostic checks against, not re-derived


def _ordered_stratum_labels(edges: list[float]) -> list[str]:
    labels = []
    for i, e in enumerate(edges):
        lo = "-inf" if i == 0 else "%.0f" % edges[i - 1]
        labels.append("(%s, %.0f]" % (lo, e))
    labels.append("(%.0f, +inf)" % edges[-1])
    return labels


def _snr_stratum_index(edges: list[float], snr: float) -> int:
    for i, e in enumerate(edges):
        if snr <= e:
            return i
    return len(edges)


def run_part_c(pop, bucket_of: dict[tuple, str], log) -> dict:
    c_keys = [k for k, v in bucket_of.items() if v == "C"]
    n_c = len(c_keys)
    pp_c = pop.pp_of_d001(n_c)
    log("Part C: bucket C (genuine DSP miss) count=%d, pp-of-D-001=%.2f" % (n_c, pp_c))

    # ---- SNR stratum composition (pinned L1 edges) ----
    labels = _ordered_stratum_labels(L1_SNR_EDGES)
    strata_counts: dict[str, int] = {label: 0 for label in labels}
    for key in c_keys:
        snr = pop.theirs_only_rep_snr[key]
        idx = _snr_stratum_index(L1_SNR_EDGES, snr)
        strata_counts[labels[idx]] += 1
    log("Part C: SNR stratum composition (pinned L1 edges %s):" % L1_SNR_EDGES)
    for label in labels:
        log("Part C:   %-14s n=%d (%.1f%%)" % (label, strata_counts[label],
                                                100.0 * strata_counts[label] / n_c if n_c else float("nan")))

    # ---- per-cycle density composition (band is single-valued on this
    #      corpus -- 20m only -- so "by band" from the spec is not
    #      stratifiable here; disclosed rather than silently omitted) ----
    log("Part C: band stratification not applicable -- this corpus is single-band (20m, "
        "14.074 MHz) on both legs; nothing to stratify by band on.")

    c_by_cycle: dict[str, int] = {}
    for (ts, _msg) in c_keys:
        c_by_cycle[ts] = c_by_cycle.get(ts, 0) + 1
    density_values = sorted(c_by_cycle.values())
    if density_values:
        log("Part C: bucket-C decodes per cycle (cycles carrying >=1) -- n_cycles=%d "
            "median=%.1f mean=%.2f max=%d"
            % (len(density_values), statistics.median(density_values),
               statistics.mean(density_values), max(density_values)))

    # ---- diagnostic 1: max decodes per cycle vs K_MAX_DECODED caps ----
    max_ours_per_cycle = max((len(rows) for rows in pop.ours_by_cycle.values()), default=0)
    log("Part C: diagnostic -- max OURS decodes in any one cycle = %d, against "
        "K_MAX_DECODED caps %s (no consequence; informational only)"
        % (max_ours_per_cycle, K_MAX_DECODED_CAPS))

    # ---- diagnostic 2: miss rate [200,250) vs [700,3000) baseline ----
    def _miss_rate(lo: float, hi: float) -> tuple[int, int, float]:
        theirs_total_band = sum(1 for r in pop.theirs_rows if lo <= r["freq_hz"] < hi)
        theirs_only_band = sum(
            1 for k in pop.theirs_only_keys
            if lo <= pop.theirs_only_rep_freq[k] < hi)
        rate = theirs_only_band / theirs_total_band if theirs_total_band else float("nan")
        return theirs_only_band, theirs_total_band, rate

    miss_200_250 = _miss_rate(200.0, 250.0)
    miss_700_3000 = _miss_rate(700.0, 3000.0)
    log("Part C: diagnostic -- miss rate [200,250) = %d/%d = %.1f%%, baseline [700,3000) = "
        "%d/%d = %.1f%% (no consequence; informational only, per Sec.6)"
        % (miss_200_250[0], miss_200_250[1], miss_200_250[2] * 100,
           miss_700_3000[0], miss_700_3000[1], miss_700_3000[2] * 100))

    return {
        "n_C": n_c,
        "pp_of_d001": pp_c,
        "snr_strata": strata_counts,
        "density_by_cycle_summary": {
            "n_cycles_with_c": len(density_values),
            "median": statistics.median(density_values) if density_values else None,
            "mean": statistics.mean(density_values) if density_values else None,
            "max": max(density_values) if density_values else None,
        },
        "diagnostics": {
            "max_ours_decodes_per_cycle": max_ours_per_cycle,
            "k_max_decoded_caps": list(K_MAX_DECODED_CAPS),
            "miss_rate_200_250": {"n_miss": miss_200_250[0], "n_total": miss_200_250[1],
                                   "rate": miss_200_250[2]},
            "miss_rate_700_3000_baseline": {"n_miss": miss_700_3000[0], "n_total": miss_700_3000[1],
                                             "rate": miss_700_3000[2]},
        },
    }
